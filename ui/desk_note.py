# -*- coding: utf-8 -*-
"""포스트잇 위젯 — 일정 1건 = 메모지 1장 (v0.10.0).

캘린더의 📌 버튼으로 바탕화면에 붙인다. 제목·메모를 그 자리에서
바로 타이핑하면 잠시 후(디바운스) 일정에 저장된다.
일정이 삭제되면 포스트잇도 조용히 사라진다. ✕는 포스트잇만 내린다.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTextEdit, QVBoxLayout,
)

from store.event_store import Event, EventStore
from ui import theme
from ui.calendar_view import WEEKDAY_KO
from ui.desk_base import DeskWidgetBase


class PostItWidget(DeskWidgetBase):
    """노란 메모지 한 장. conf는 config["desk_widgets"]["notes"]의 한 항목."""

    MIN_W, MIN_H = 140, 110       # 명함만 하게도 줄일 수 있게
    OFF_LABEL = "포스트잇 내리기 (일정은 그대로)"

    def __init__(self, store: EventStore, config: dict, base_dir: str,
                 conf: dict, event: Event):
        super().__init__(store, config, base_dir, conf)
        self.event = event
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(1200)       # 타이핑 멈추고 1.2초 뒤 저장
        self._save_timer.timeout.connect(self._save_text)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        card = QFrame()
        card.setObjectName("postit")
        card.setStyleSheet(
            theme.BASE_QSS
            + f"#postit{{background:{theme.POSTIT_BG};"
              f"border-radius:{theme.RADIUS_LG}px;"
              f"border:1px solid {theme.POSTIT_BORDER}}}")
        outer.addWidget(card)
        root = QVBoxLayout(card)
        root.setContentsMargins(10, 6, 8, 8)
        root.setSpacing(4)

        head = QHBoxLayout()
        self.when_label = QLabel()
        head.addWidget(self.when_label)
        head.addStretch()
        head.addWidget(self.make_pin_button())   # 📌 바로 고정 (v1.4)
        head.addWidget(self.make_edit_button())
        close_btn = QPushButton("✕")
        close_btn.setToolTip("포스트잇 내리기 (일정은 그대로 남아요)")
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet(
            f"QPushButton{{background:transparent;border:none;"
            f"color:{theme.POSTIT_HEADER};font-size:12px;padding:0 4px}}"
            f"QPushButton:hover{{color:{theme.DANGER}}}"
            f"QPushButton:pressed{{color:{theme.DANGER_FG}}}")
        close_btn.clicked.connect(self.turn_off)
        head.addWidget(close_btn)
        root.addLayout(head)
        root.addWidget(self.build_edit_bar())

        self.title_edit = QLineEdit(event.title)
        self.title_edit.textEdited.connect(lambda _: self._save_timer.start())
        root.addWidget(self.title_edit)

        self.memo_edit = QTextEdit()
        self.memo_edit.setPlainText(event.memo)
        self.memo_edit.setPlaceholderText("여기에 바로 메모하세요")
        self.memo_edit.textChanged.connect(self._on_memo_changed)
        root.addWidget(self.memo_edit, stretch=1)

        self._apply_font()
        self._update_when()

    def _apply_font(self) -> None:
        """글씨 크기 설정(%)을 제목·메모·날짜에 적용."""
        fpx = self.font_px
        self.when_label.setStyleSheet(
            f"color:{theme.POSTIT_HEADER};font-size:{fpx(10)}px;"
            f"font-weight:bold;background:transparent")
        self.title_edit.setStyleSheet(
            f"QLineEdit{{background:transparent;border:none;padding:0;"
            f"font-size:{fpx(13)}px;font-weight:bold;color:{theme.TEXT}}}")
        self.memo_edit.setStyleSheet(
            f"QTextEdit{{background:transparent;border:none;padding:0;"
            f"font-size:{fpx(12)}px;color:{theme.TEXT}}}")

    def _on_memo_changed(self) -> None:
        # setPlainText(프로그램 갱신)에도 이 시그널이 오므로 값 비교로 거른다
        if self.memo_edit.toPlainText() != self.event.memo:
            self._save_timer.start()

    def place_default(self) -> None:
        screen = QApplication.primaryScreen().availableGeometry()
        # 여러 장 붙일 때 겹치지 않게 떠 있는 장수만큼 계단식으로 비껴 놓는다
        n = len(getattr(QApplication.instance(), "_coolm_desk",
                        {"notes": {}}).get("notes", {}))
        self.resize(220, 180)
        self.move(screen.left() + 60 + n * 32, screen.top() + 60 + n * 32)

    def _update_when(self) -> None:
        d = self.event.start_dt
        t = f"{d.month}/{d.day}({WEEKDAY_KO[d.weekday()]})"
        if not self.event.all_day:
            t += d.strftime(" %H:%M")
        self.when_label.setText("📌 " + t)

    # ── 저장 (디바운스 + 포커스 아웃 + 닫힐 때) ─────────────
    def _save_text(self) -> None:
        title = self.title_edit.text().strip() or self.event.title
        memo = self.memo_edit.toPlainText()
        if title == self.event.title and memo == self.event.memo:
            return
        self.event.title = title
        self.event.memo = memo
        self.store.update(self.event.id, title=title, memo=memo)
        # 구글에 올린 일정이면 제목 사본도 갱신 (실패해도 조용히 — 메모지에서 경고는 산만)
        if self.event.google_id:
            try:
                from calendar_sync import google_sync
                google_sync.update_event(self.event.google_id, title,
                                         self.event.start_dt, self.event.end_dt,
                                         self.event.all_day)
            except Exception:
                pass

    def focusOutEvent(self, ev):
        self._save_text()
        super().focusOutEvent(ev)

    def refresh(self) -> None:
        """다른 창에서 이 일정이 바뀌거나 삭제됐을 때 (글씨 크기 변경 포함)."""
        cur = next((e for e in self.store.all() if e.id == self.event.id), None)
        if cur is None:                          # 일정 삭제 → 포스트잇도 내림
            self.turn_off()
            return
        self.event = cur
        self._apply_font()
        self._update_when()
        # 사용자가 그 필드를 편집 중이면 덮어쓰지 않는다 (재진입 가드)
        if not self.title_edit.hasFocus() and self.title_edit.text() != cur.title:
            self.title_edit.setText(cur.title)
        if not self.memo_edit.hasFocus() and \
                self.memo_edit.toPlainText() != cur.memo:
            self.memo_edit.setPlainText(cur.memo)

    def turn_off(self) -> None:
        """notes 목록에서 이 항목을 빼고 닫는다 (일정은 유지)."""
        from parser.pipeline import desk_conf
        notes = desk_conf(self.config, "notes")
        self.config["desk_widgets"]["notes"] = \
            [n for n in notes if n.get("event_id") != self.event.id]
        self._save_config()
        app = QApplication.instance()
        reg = getattr(app, "_coolm_desk", None)
        if reg:
            reg["notes"].pop(self.event.id, None)
        self.close()

    def closeEvent(self, ev):
        self._save_timer.stop()
        self._save_text()
        super().closeEvent(ev)
