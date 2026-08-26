# -*- coding: utf-8 -*-
"""위젯 공통 로직 — 미니/상세 두 스타일이 공유하는 동작.

버튼 클릭 시에만 메시지함을 읽는다. 백그라운드 감시 없음.
"""
from __future__ import annotations

import threading

from PyQt6.QtCore import Qt, QPoint, QRect, QObject, QTimer, pyqtSignal
from PyQt6.QtWidgets import QApplication, QMessageBox, QWidget

from parser import pipeline
from store.event_store import EventStore
from store.favorites import FavStore
from ui.calendar_view import CalendarWindow
from ui.review_dialog import ReviewDialog


# ── 여러 모니터 다루기 (2026-08-25) ──────────────────────────
# 예전에는 어디서나 primaryScreen()만 봤다. 듀얼 모니터에서 보조 화면은
# 좌표가 음수이거나 주 화면 밖이라, 그 기준으로 자르면 펭귄이 주 화면으로
# 튕겨 돌아왔다. 아래 도우미들은 "그 지점이 속한 화면"을 찾아서 쓴다.
def screen_at(point: QPoint):
    """그 점이 놓인 화면. 화면 사이 틈이면 가장 가까운 화면."""
    app = QApplication.instance()
    scr = app.screenAt(point) if app else None
    if scr is not None:
        return scr
    best, best_d = None, None
    for s in (app.screens() if app else []):
        c = s.availableGeometry().center()
        d = (c.x() - point.x()) ** 2 + (c.y() - point.y()) ** 2
        if best_d is None or d < best_d:
            best, best_d = s, d
    return best or (app.primaryScreen() if app else None)


def clamp_to_screens(pos: QPoint, size, anchor: QPoint | None = None) -> QPoint:
    """창이 화면 밖으로 나가지 않게 자른다.

    기준 화면은 기본적으로 '창 한가운데가 놓인 화면'. 드래그 중에는
    anchor로 **커서 위치**를 넘긴다 — 그래야 듀얼 모니터 경계에서 창이
    반쯤 걸린 채 끈적이지 않고 커서를 따라 옆 화면으로 넘어간다.
    """
    center = anchor if anchor is not None else QPoint(
        pos.x() + size.width() // 2, pos.y() + size.height() // 2)
    scr = screen_at(center)
    if scr is None:
        return pos
    g = scr.availableGeometry()
    x = min(max(pos.x(), g.left()), max(g.left(), g.right() - size.width() + 1))
    y = min(max(pos.y(), g.top()), max(g.top(), g.bottom() - size.height() + 1))
    return QPoint(x, y)


def on_any_screen(rect) -> bool:
    """어느 화면에든 걸쳐 있으면 True (보조 모니터도 화면이다)."""
    app = QApplication.instance()
    return any(s.availableGeometry().intersects(rect)
               for s in (app.screens() if app else []))


def _desk_widgets_flat(app) -> list:
    """데스크 레지스트리의 모든 위젯 (notes는 {id: 위젯} dict라 평탄화)."""
    reg = getattr(app, "_coolm_desk", None) or {}
    out = []
    for k, v in reg.items():
        if k == "notes":
            out.extend(w for w in dict(v).values() if w is not None)
        elif v is not None:
            out.append(v)
    return out


def show_tray_tip(app) -> None:
    """트레이로 처음 보낼 때 한 번만 안내 풍선 — 어디서 보내든 공유."""
    tray = getattr(app, "_coolm_tray", None)
    if tray is None or getattr(app, "_coolm_tray_tip_shown", False):
        return
    app._coolm_tray_tip_shown = True
    try:
        tray.showMessage(
            "COOL-비서",
            "트레이로 보냈어요.\n"
            "이 아이콘을 클릭하면 전부 다시 나타납니다. 🐧",
            tray.icon(), 4000)
    except Exception:
        pass


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
        # 지난 일정 자동 보관 (설정 가능, 0이면 끔) — 세션당 1회
        if not getattr(app, "_coolm_archived", False):
            app._coolm_archived = True
            try:
                self.store.archive_old(int(self.config.get("auto_archive_days", 90)))
            except Exception:
                pass
        self.cal_win: CalendarWindow | None = None
        self._drag: QPoint | None = None
        app._coolm_widget = self     # 트레이·위젯 – 버튼이 참조 (스왑 시 갱신)
        QTimer.singleShot(2000, self._auto_update_check)
        QTimer.singleShot(300, self.ensure_desk_widgets)
        QTimer.singleShot(2500, self._show_startup_alerts)   # 세션당 1회
        # ⚡ 간편 등록이 첫 클릭부터 빠르도록 UIA를 백그라운드에서 미리 초기화
        threading.Thread(target=self._warmup_capture, daemon=True).start()
        # 해상도·모니터 변경(프로젝터 연결 등) 시 화면 밖으로 사라지지 않게
        self._watch_screen()

    # ── 해상도 변경 감시 ─────────────────────────────────────
    def _watch_screen(self) -> None:
        app = QApplication.instance()
        app.primaryScreenChanged.connect(self._on_screen_event)
        scr = app.primaryScreen()
        if scr is not None:
            scr.availableGeometryChanged.connect(self._on_screen_event)

    def _on_screen_event(self, *_args) -> None:
        # 해상도 전환 직후는 좌표가 요동치므로 잠깐 기다렸다 확인
        QTimer.singleShot(500, self._ensure_on_screen)
        scr = QApplication.primaryScreen()
        if scr is not None:               # 새 주 모니터도 계속 감시
            try:
                scr.availableGeometryChanged.connect(
                    self._on_screen_event, Qt.ConnectionType.UniqueConnection)
            except TypeError:
                pass                      # 이미 연결됨

    def _ensure_on_screen(self) -> None:
        """어느 화면에도 안 걸치면 기본 위치로 (펭귄 실종 방지).

        보조 모니터에 둔 창을 주 화면으로 끌고 오지 않는다 — 모니터를
        뽑아서 정말 갈 곳이 없을 때만 되돌린다.
        """
        if not QApplication.instance().screens():
            return
        if not on_any_screen(self.frameGeometry()):
            self.place_default()
        if getattr(self, "_in_tray", False):
            return               # 사용자가 트레이로 보낸 상태는 존중
        if not self.isVisible():
            self.show()
        self.raise_()

    # 프리워밍 감시 주기 — 새로 뜬 쿨메신저 창을 몇 초 안에 깨워
    # "앱/창을 켜자마자 첫 ⚡"도 바로 되게 한다 (2026-08-07 사용자 요청).
    # 이미 깨운 창은 창 목록 확인(수 ms)만 하므로 짧은 주기여도 부담이 없다.
    PREWARM_SCAN_SEC = 4      # 새 창 감시 (빠름·거의 공짜)
    PREWARM_FULL_SEC = 90     # 전체 재워밍 + 쪽지 캐시 (웹뷰 재시작 대비)

    def _warmup_capture(self) -> None:
        import os
        import time
        if os.environ.get("COOLM_NO_CAPTURE"):
            return          # CI/테스트 — Windows 러너에서 UIA가 멈출 수 있음
        base_dir = self.base_dir
        try:
            import capture
            capture.warmup()             # UIA COM — 켜자마자 가장 먼저
            capture.prewarm(force=True)  # 지금 떠 있는 쿨메신저 창 전부 깨움
            pipeline.prefetch_quick(base_dir)
        except Exception:
            pass
        last_full = time.time()
        while True:                      # 데몬 스레드 — 앱 종료와 함께 끝
            time.sleep(self.PREWARM_SCAN_SEC)
            try:
                import capture
                full = time.time() - last_full >= self.PREWARM_FULL_SEC
                capture.prewarm(force=full)   # 새 창은 몇 초 안에 깨어난다
                if full:
                    pipeline.prefetch_quick(base_dir)
                    last_full = time.time()
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
        self.ensure_desk_widgets()
        # 즐겨찾기 탭 등 설정이 바뀌었을 수 있으니 캘린더 창은 다음에 새로 만든다
        if self.cal_win is not None:
            self.cal_win.close()
            self.cal_win = None
        new_style = self.config.get("widget_style", "mini")
        if new_style != old_style:
            self._swap_style(new_style)

    def ensure_desk_widgets(self) -> None:
        """바탕화면 위젯(할일·주간·월간·포스트잇)을 설정에 맞춰 켜거나 끈다."""
        from ui.desk_base import ensure_desk_widgets
        ensure_desk_widgets(self)

    def apply_desk_widget(self, kind: str, on: bool) -> None:
        """설정 창 체크박스에서 실시간 반영 — 저장 버튼 없이 즉시 켜고 끈다."""
        from parser.pipeline import desk_conf
        desk_conf(self.config, kind)["enabled"] = bool(on)
        pipeline.save_config(self.base_dir, self.config)
        self.ensure_desk_widgets()

    def open_proof(self) -> None:
        """안내문구 보정 (공개용 글 전용, 붙여넣기만 지원)."""
        from ui.proof_dialog import ProofDialog
        ProofDialog(self.config, parent=self).exec()

    def open_neis(self) -> None:
        """🏫 학사일정 — 나이스에서 우리 학교 일정을 골라 등록한다."""
        from ui.neis_dialog import open_neis_schedule
        open_neis_schedule(self)

    def open_quick(self) -> None:
        """⚡ 간편 등록 — 보고 있는 쪽지를 곧바로 등록하고 포스트잇으로 붙인다.

        수정 창을 띄우지 않는다(2026-07-26 사용자 결정). 등록은 자동으로 되고,
        고칠 내용은 바탕화면에 붙은 포스트잇에서 그 자리에서 편집한다.
        """
        from ui.quick_capture import quick_pin
        quick_pin(self)

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

    # ── 위치 기억 ───────────────────────────────────────────
    POS_KEY = ""          # 설정에 위치를 남길 키. 빈 값이면 기억하지 않는다.

    def restore_position(self) -> None:
        """지난번 놓아둔 자리로. 없거나 그 화면이 사라졌으면 기본 자리."""
        saved = self.config.get(self.POS_KEY) if self.POS_KEY else None
        if isinstance(saved, (list, tuple)) and len(saved) == 2:
            try:
                pt = QPoint(int(saved[0]), int(saved[1]))
            except (TypeError, ValueError):
                pt = None
            if pt is not None:
                rect = QRect(pt, self.size())
                if on_any_screen(rect):       # 모니터를 뽑았으면 무시된다
                    self.move(pt)
                    return
        self.place_default()

    def save_position(self) -> None:
        """지금 자리를 설정에 남긴다 (드래그를 놓을 때)."""
        if not self.POS_KEY:
            return
        self.config[self.POS_KEY] = [self.x(), self.y()]
        pipeline.save_config(self.base_dir, self.config)

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

    def showEvent(self, ev):
        self._in_tray = False        # 어떤 경로로든 보이면 트레이 상태 해제
        super().showEvent(ev)

    def send_to_tray(self) -> None:
        """펭귄만 트레이로 보낸다 (위젯은 각자 – 버튼으로). 복귀는 트레이 클릭."""
        self._in_tray = True
        self.hide()
        show_tray_tip(QApplication.instance())

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
        # 안내·다운로드 진행·설치까지 UpdateDialog가 전담한다
        from ui.update_dialog import UpdateDialog
        UpdateDialog(info, self).exec()

    # ── 드래그 이동 (기본: 자유 이동, 미니는 재정의) ─────────
    def mousePressEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton:
            self._drag = ev.globalPosition().toPoint() - self.pos()

    def mouseMoveEvent(self, ev):
        # QPoint(0,0)은 거짓 — 'if self._drag'면 모서리를 정확히 집었을 때
        # 드래그가 안 먹는다 (mini_widget과 같은 이유, 2026-08-25)
        if self._drag is not None and ev.buttons() & Qt.MouseButton.LeftButton:
            cursor = ev.globalPosition().toPoint()
            self.move(clamp_to_screens(cursor - self._drag, self.size(), cursor))

    def mouseReleaseEvent(self, ev):
        if self._drag is not None:
            self.save_position()
        self._drag = None
