# -*- coding: utf-8 -*-
"""위젯 공통 로직 — 미니/상세 두 스타일이 공유하는 동작.

버튼 클릭 시에만 메시지함을 읽는다. 백그라운드 감시 없음.
"""
from __future__ import annotations

import threading

from PyQt6.QtCore import Qt, QPoint, QObject, QTimer, pyqtSignal
from PyQt6.QtWidgets import QApplication, QMessageBox, QWidget

from parser import pipeline
from store.event_store import EventStore
from store.favorites import FavStore
from ui.calendar_view import CalendarWindow
from ui.review_dialog import ReviewDialog


class _UpdateChecker(QObject):
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


class WidgetBase(QWidget):
    """플로팅 위젯 공통 베이스. 서브클래스는 UI만 구성한다."""

    def __init__(self, base_dir: str):
        super().__init__()
        self.base_dir = base_dir
        self.config = pipeline.load_config(base_dir)
        # 저장소는 앱 전체에서 하나만 공유 — 창 간 실시간 동기화의 기반
        app = QApplication.instance()
        shared = getattr(app, "_coolm_stores", None)
        if shared is None:
            store_dir = self.config.get("store_dir", "store")
            shared = {"events": EventStore(base_dir, store_dir),
                      "favs": FavStore(base_dir, store_dir)}
            app._coolm_stores = shared
        self.store: EventStore = shared["events"]
        self.fav_store: FavStore = shared["favs"]
        self.cal_win: CalendarWindow | None = None
        self._drag: QPoint | None = None
        QTimer.singleShot(2000, self._auto_update_check)
        QTimer.singleShot(300, self.ensure_desktop_widget)
        QTimer.singleShot(2500, self._show_startup_alerts)   # 세션당 1회
        # ⚡ 간편 등록이 첫 클릭부터 빠르도록 UIA를 백그라운드에서 미리 초기화
        threading.Thread(target=self._warmup_capture, daemon=True).start()

    def _warmup_capture(self) -> None:
        try:
            import capture
            capture.warmup()
            pipeline.prefetch_quick(self.base_dir)   # 첫 ⚡ 클릭도 빠르게
        except Exception:
            pass

    def _show_startup_alerts(self) -> None:
        from ui.alerts import show_startup_alerts
        show_startup_alerts(self)

    # ── 설정 ────────────────────────────────────────────────
    def window_flags(self) -> Qt.WindowType:
        flags = Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool
        if self.config.get("widget_always_on_top", True):
            flags |= Qt.WindowType.WindowStaysOnTopHint
        return flags

    def apply_config(self) -> None:
        self.setWindowOpacity(int(self.config.get("widget_opacity", 100)) / 100)
        flags = self.window_flags()
        if flags != self.windowFlags():
            visible = self.isVisible()
            self.setWindowFlags(flags)
            if visible:
                self.show()

    def open_settings(self) -> None:
        from ui.settings_dialog import SettingsDialog
        old_style = self.config.get("widget_style", "mini")
        dlg = SettingsDialog(self.base_dir, self.config, self.store, parent=self)
        if not dlg.exec():
            return
        self.config = pipeline.load_config(self.base_dir)
        self.apply_config()
        self.ensure_desktop_widget()
        # 즐겨찾기 탭 등 설정이 바뀌었을 수 있으니 캘린더 창은 다음에 새로 만든다
        if self.cal_win is not None:
            self.cal_win.close()
            self.cal_win = None
        new_style = self.config.get("widget_style", "mini")
        if new_style != old_style:
            self._swap_style(new_style)

    def ensure_desktop_widget(self) -> None:
        """바탕화면 캘린더 위젯을 설정에 맞춰 켜거나 끈다."""
        app = QApplication.instance()
        cur = getattr(app, "_coolm_desktop", None)
        if self.config.get("desktop_widget_enabled"):
            if cur is None:
                from ui.desktop_calendar import DesktopCalendar
                cur = DesktopCalendar(self.store, self.config)
                cur.place_default()
                cur.show()
                app._coolm_desktop = cur
            else:
                cur.config = self.config
                cur.setWindowOpacity(
                    max(40, int(self.config.get("desktop_widget_opacity", 90))) / 100)
        elif cur is not None:
            cur.close()
            app._coolm_desktop = None

    def open_proof(self) -> None:
        """안내문구 보정 (공개용 글 전용, 붙여넣기만 지원)."""
        from ui.proof_dialog import ProofDialog
        ProofDialog(self.config, parent=self).exec()

    def open_quick(self) -> None:
        """⚡ 간편 등록 — 지금 쿨메신저에서 보고 있는 쪽지를 바로 등록."""
        from ui.quick_dialog import QuickDialog
        dlg = QuickDialog(self.base_dir, self.store,
                          google_enabled=self.google_enabled(), parent=self)
        dlg.exec()
        self.on_events_changed()

    def _swap_style(self, style: str) -> None:
        """설정에서 위젯 스타일 변경 시 즉시 교체."""
        from ui.floating_widget import FloatingWidget
        from ui.mini_widget import MiniWidget
        cls = MiniWidget if style == "mini" else FloatingWidget
        new = cls(self.base_dir)
        new.cal_win = self.cal_win
        new.place_default()
        new.show()
        QApplication.instance()._coolm_widget = new   # GC 방지 참조 유지
        self.close()

    def place_default(self) -> None:
        """화면 우측에 기본 배치 (서브클래스에서 재정의 가능)."""
        screen = QApplication.primaryScreen().availableGeometry()
        self.move(screen.right() - self.width() - 24,
                  screen.bottom() - self.height() - 24)

    # ── 동작 ────────────────────────────────────────────────
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
            ret = QMessageBox.question(
                self, "안내",
                "쿨메신저 메시지함을 찾을 수 없습니다.\n\n"
                "내장된 가짜 쪽지(데모 데이터)로 기능을 체험해 보시겠어요?\n"
                "데모로 등록한 일정은 설정 → 데이터에서 한 번에 삭제할 수 "
                f"있습니다.\n\n(원본 안내: {e})")
            if ret != QMessageBox.StandardButton.Yes:
                return
            self.config["demo_mode"] = True
            pipeline.save_config(self.base_dir, self.config)
            candidates, no_event, source = pipeline.collect(self.base_dir)
        except Exception as e:
            QMessageBox.critical(self, "오류", f"메시지함을 읽지 못했습니다.\n{e}")
            return
        count = int(self.config.get("recent_count", 10))
        dlg = ReviewDialog(candidates, self.store,
                           google_enabled=self.google_enabled(),
                           source=source,
                           loader=lambda n: pipeline.collect(self.base_dir, n),
                           count=count, fav_store=self.fav_store, parent=self)
        dlg.exec()
        self.on_events_changed()

    def open_calendar(self) -> None:
        if self.cal_win is None:
            self.cal_win = CalendarWindow(
                self.store, fav_store=self.fav_store,
                favorites_enabled=bool(self.config.get("favorites_enabled")))
        self.cal_win.refresh()
        self.cal_win.show()
        self.cal_win.raise_()
        self.cal_win.activateWindow()

    def on_events_changed(self) -> None:
        """일정 변경 후 후처리 — 서브클래스에서 뱃지 갱신 등에 사용."""

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
        if QMessageBox.question(self, "업데이트", msg) != \
                QMessageBox.StandardButton.Yes:
            return
        import updater
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            path = updater.download_installer(info["url"])
        except Exception as e:
            QApplication.restoreOverrideCursor()
            QMessageBox.warning(self, "업데이트 실패", f"다운로드하지 못했습니다.\n{e}")
            return
        QApplication.restoreOverrideCursor()
        updater.run_installer_and_quit(path)

    # ── 드래그 이동 (기본: 자유 이동, 미니는 재정의) ─────────
    def mousePressEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton:
            self._drag = ev.globalPosition().toPoint() - self.pos()

    def mouseMoveEvent(self, ev):
        if self._drag and ev.buttons() & Qt.MouseButton.LeftButton:
            self.move(ev.globalPosition().toPoint() - self._drag)

    def mouseReleaseEvent(self, ev):
        self._drag = None
