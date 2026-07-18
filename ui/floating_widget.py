# -*- coding: utf-8 -*-
"""플로팅 위젯 — 항상 위에 떠 있는 작은 런처 (쿨메신저 블루 테마).

[일정 등록] 클릭 시에만 메시지함을 읽는다. 백그라운드 감시 없음.
"""
from __future__ import annotations

import threading
from datetime import date

from PyQt6.QtCore import Qt, QPoint, QObject, QTimer, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QApplication, QFrame, QGraphicsDropShadowEffect, QHBoxLayout, QLabel,
    QMessageBox, QPushButton, QVBoxLayout, QWidget,
)

from parser import pipeline
from store.event_store import EventStore
from ui import theme
from ui.calendar_view import CalendarWindow
from ui.review_dialog import ReviewDialog


class _UpdateChecker(QObject):
    """백그라운드 스레드에서 버전 확인 후 신호로 결과 전달 (UI 비블로킹)."""
    found = pyqtSignal(dict)

    def __init__(self, url: str, parent=None):
        super().__init__(parent)
        self.url = url

    def start(self) -> None:
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self) -> None:
        import updater
        info = updater.check_for_update(self.url)
        if info:
            self.found.emit(info)


class FloatingWidget(QWidget):
    def __init__(self, base_dir: str):
        super().__init__()
        self.base_dir = base_dir
        self.config = pipeline.load_config(base_dir)
        self.store = EventStore(base_dir, self.config.get("store_dir", "store"))
        self.cal_win: CalendarWindow | None = None
        self._drag: QPoint | None = None

        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint
                            | Qt.WindowType.FramelessWindowHint
                            | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        card = QFrame()
        card.setObjectName("card")
        card.setStyleSheet(
            f"#card{{background:{theme.CARD};border-radius:16px;"
            f"border:1px solid {theme.BORDER}}}"
            f"QLabel{{background:transparent;font-family:'Malgun Gothic'}}")
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(24)
        shadow.setOffset(0, 4)
        shadow.setColor(QColor(30, 136, 229, 60))
        card.setGraphicsEffect(shadow)
        outer.addWidget(card)

        lay = QVBoxLayout(card)
        lay.setContentsMargins(14, 14, 14, 12)
        lay.setSpacing(8)

        title_row = QHBoxLayout()
        title = QLabel("쿨 일정 도우미")
        title.setStyleSheet(
            f"color:{theme.PRIMARY_DARK};font-weight:bold;font-size:14px")
        title_row.addWidget(title, stretch=1)
        gear = QPushButton("⚙")
        gear.setFixedSize(26, 26)
        gear.setStyleSheet(
            f"QPushButton{{background:transparent;color:{theme.SUBTLE};"
            f"border:none;font-size:15px}}"
            f"QPushButton:hover{{color:{theme.PRIMARY_DARK}}}")
        gear.setCursor(Qt.CursorShape.PointingHandCursor)
        gear.setToolTip("설정")
        gear.clicked.connect(self.open_settings)
        title_row.addWidget(gear)
        lay.addLayout(title_row)

        self.today_label = QLabel()
        self.today_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.today_label.setStyleSheet(
            f"background:{theme.PRIMARY_LIGHT};color:{theme.PRIMARY_DARK};"
            f"border-radius:9px;padding:5px;font-size:12px;font-weight:bold")
        lay.addWidget(self.today_label)

        add_btn = QPushButton("📅  일정 등록")
        add_btn.setStyleSheet(theme.PRIMARY_BTN + "QPushButton{font-size:13px}")
        add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_btn.clicked.connect(self.open_review)
        lay.addWidget(add_btn)

        cal_btn = QPushButton("🗓  캘린더 · 할일")
        cal_btn.setStyleSheet(
            f"QPushButton{{background:{theme.CARD};color:{theme.PRIMARY_DARK};"
            f"border:1.5px solid {theme.PRIMARY};border-radius:8px;"
            f"padding:8px;font-weight:bold;font-size:13px}}"
            f"QPushButton:hover{{background:{theme.PRIMARY_LIGHT}}}")
        cal_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cal_btn.clicked.connect(self.open_calendar)
        lay.addWidget(cal_btn)

        quit_btn = QPushButton("종료")
        quit_btn.setStyleSheet(
            f"QPushButton{{background:transparent;color:{theme.SUBTLE};"
            f"border:none;padding:4px;font-size:11px}}"
            f"QPushButton:hover{{color:{theme.DANGER}}}")
        quit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        quit_btn.clicked.connect(QApplication.instance().quit)
        lay.addWidget(quit_btn)

        self.refresh_badge()
        self.resize(190, 205)
        self.apply_config()
        QTimer.singleShot(2000, self._auto_update_check)   # 시작 2초 후 확인

    # ── 설정 ────────────────────────────────────────────────
    def apply_config(self) -> None:
        """설정 저장 후 위젯에 즉시 반영."""
        self.setWindowOpacity(int(self.config.get("widget_opacity", 100)) / 100)
        on_top = bool(self.config.get("widget_always_on_top", True))
        flags = Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool
        if on_top:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        if flags != self.windowFlags():
            visible = self.isVisible()
            self.setWindowFlags(flags)
            if visible:
                self.show()

    def open_settings(self) -> None:
        from ui.settings_dialog import SettingsDialog
        dlg = SettingsDialog(self.base_dir, self.config, self.store, parent=self)
        if dlg.exec():
            self.config = pipeline.load_config(self.base_dir)
            self.apply_config()

    # ── 자동 업데이트 ────────────────────────────────────────
    def _auto_update_check(self) -> None:
        url = self.config.get("update_url", "")
        if not (url and self.config.get("auto_update_check", True)):
            return
        self._checker = _UpdateChecker(url, self)
        self._checker.found.connect(self._offer_update)
        self._checker.start()

    def _offer_update(self, info: dict) -> None:
        notes = info.get("notes", "")
        msg = f"새 버전 v{info.get('version')}이 나왔습니다."
        if notes:
            msg += f"\n\n변경사항:\n{notes}"
        msg += "\n\n업데이트 후 재시작하시겠습니까?"
        ret = QMessageBox.question(self, "업데이트", msg)
        if ret != QMessageBox.StandardButton.Yes:
            return
        import updater
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            path = updater.download_installer(info["url"])
        except Exception as e:
            QApplication.restoreOverrideCursor()
            QMessageBox.warning(self, "업데이트 실패",
                                f"다운로드하지 못했습니다.\n{e}")
            return
        QApplication.restoreOverrideCursor()
        updater.run_installer_and_quit(path)

    # ── 동작 ────────────────────────────────────────────────
    def refresh_badge(self) -> None:
        n = len(self.store.on_date(date.today()))
        self.today_label.setText(f"오늘 일정 {n}건")

    def google_enabled(self) -> bool:
        if not self.config.get("google_sync_enabled"):
            return False
        try:
            from calendar_sync import google_sync
            return google_sync.is_available(self.base_dir)
        except Exception:
            return False

    def open_review(self) -> None:
        try:
            candidates, no_event, source = pipeline.collect(self.base_dir)
        except FileNotFoundError as e:
            QMessageBox.information(self, "안내", str(e))
            return
        except Exception as e:
            QMessageBox.critical(self, "오류", f"메시지함을 읽지 못했습니다.\n{e}")
            return
        # 후보가 없어도 창을 연다 — 콤보박스로 개수를 늘려 다시 찾을 수 있게
        count = int(self.config.get("recent_count", 10))
        dlg = ReviewDialog(candidates, self.store,
                           google_enabled=self.google_enabled(),
                           source=source,
                           loader=lambda n: pipeline.collect(self.base_dir, n),
                           count=count, parent=self)
        dlg.exec()
        self.refresh_badge()
        if self.cal_win:
            self.cal_win.refresh()

    def open_calendar(self) -> None:
        if self.cal_win is None:
            self.cal_win = CalendarWindow(self.store)
        self.cal_win.refresh()
        self.cal_win.show()
        self.cal_win.raise_()
        self.cal_win.activateWindow()   # 다른 창 뒤에 열리는 문제 방지

    # ── 드래그 이동 ──────────────────────────────────────────
    def mousePressEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton:
            self._drag = ev.globalPosition().toPoint() - self.pos()

    def mouseMoveEvent(self, ev):
        if self._drag and ev.buttons() & Qt.MouseButton.LeftButton:
            self.move(ev.globalPosition().toPoint() - self._drag)

    def mouseReleaseEvent(self, ev):
        self._drag = None
