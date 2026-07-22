# -*- coding: utf-8 -*-
"""COOL-비서 — 진입점.

python main.py 로 실행하면 우측 하단에 플로팅 위젯이 뜬다.
"""
import os
import sys
from datetime import datetime

if getattr(sys, "frozen", False):           # PyInstaller exe로 실행된 경우
    BASE_DIR = os.path.dirname(sys.executable)
    # 주의: frozen 모드에서는 BASE_DIR를 sys.path에 넣지 않는다.
    # exe 옆에 생기는 store/ 데이터 폴더가 내부 store 모듈을 가려
    # 두 번째 실행부터 앱이 죽는 버그의 원인이었다.
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, BASE_DIR)

ERROR_LOG = os.path.join(BASE_DIR, "coolm_helper_error.log")


def _excepthook(exc_type, exc, tb):
    """예외로 조용히 죽는 대신 로그를 남기고 안내창을 띄운다."""
    import traceback
    text = "".join(traceback.format_exception(exc_type, exc, tb))
    try:
        with open(ERROR_LOG, "a", encoding="utf-8") as f:
            f.write(f"\n[{datetime.now():%Y-%m-%d %H:%M:%S}]\n{text}")
    except OSError:
        pass
    try:
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.critical(
            None, "오류",
            f"예상치 못한 오류가 발생했습니다.\n{exc}\n\n"
            f"자세한 내용: {ERROR_LOG}")
    except Exception:
        pass


sys.excepthook = _excepthook

from PyQt6.QtWidgets import QApplication


def main() -> None:
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)    # 캘린더 창 닫아도 위젯은 유지
    # 시스템 팝업(QMessageBox·QMenu)만 앱 팔레트로 — 스코프 스타일이라
    # 반투명 위젯 배경은 건드리지 않는다 (theme.SYSTEM_QSS 주석 참고).
    from ui import theme
    app.setStyleSheet(theme.SYSTEM_QSS)

    # 단일 실행 가드 — 이미 떠 있는데 또 실행하면 프로세스만 쌓이고
    # "창이 안 뜬다"고 느끼게 된다. 두 번째 실행은 안내 후 종료.
    import tempfile
    from PyQt6.QtCore import QLockFile
    lock = QLockFile(os.path.join(tempfile.gettempdir(), "coolm_helper.lock"))
    lock.setStaleLockTime(0)                 # 비정상 종료 잠금은 무시
    if not lock.tryLock(100):
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.information(
            None, "COOL-비서",
            "COOL-비서가 이미 실행되고 있어요.\n"
            "화면 오른쪽 가장자리의 펭귄을 확인해 주세요. 🐧")
        return
    app._coolm_lock = lock                   # GC 방지 — 잠금 유지

    # 앱 아이콘 (작업표시줄·창 제목) — 펭귄
    from PyQt6.QtGui import QIcon
    ico = os.path.join(BASE_DIR, "assets", "app.ico")
    if os.path.exists(ico):
        app.setWindowIcon(QIcon(ico))
    else:
        from ui.penguin_icon import penguin_pixmap
        app.setWindowIcon(QIcon(penguin_pixmap(BASE_DIR, 64)))

    from parser import pipeline
    config = pipeline.load_config(BASE_DIR)
    from ui import motion
    motion.set_enabled(bool(config.get("animations_enabled", True)))
    style = config.get("widget_style", "mini")
    if style == "mini":
        from ui.mini_widget import MiniWidget
        w = MiniWidget(BASE_DIR)
    else:
        from ui.floating_widget import FloatingWidget
        w = FloatingWidget(BASE_DIR)
    w.place_default()
    w.show()
    app._coolm_widget = w                   # 스타일 전환 시 참조 유지

    # 작업표시줄 트레이 아이콘 — 펭귄이 안 보일 때 여기서 꺼낸다
    from PyQt6.QtWidgets import QMenu, QSystemTrayIcon
    if QSystemTrayIcon.isSystemTrayAvailable():
        def _widget():
            return getattr(app, "_coolm_widget", None)

        def bring_back():
            # 트레이 클릭 = 최소화했던 것 전부 복귀 (펭귄 + 위젯들)
            cur = _widget()
            if cur is not None:
                # 펭귄이 숨어 있거나 화면 밖일 때만 제자리로 (안 그러면
                # 위젯만 최소화한 경우 펭귄이 괜히 튀지 않게 그대로 둔다)
                scr = app.primaryScreen()
                off = scr is not None and not \
                    scr.availableGeometry().intersects(cur.frameGeometry())
                if getattr(cur, "_in_tray", False) or not cur.isVisible() or off:
                    cur.place_default()
                    cur.show()
                    cur.raise_()
            from ui.widget_base import _desk_widgets_flat
            for dw in _desk_widgets_flat(app):
                try:
                    if getattr(dw, "_in_tray", False):
                        dw._in_tray = False
                        dw.show()
                        dw.raise_()
                except RuntimeError:
                    pass

        tray = QSystemTrayIcon(app.windowIcon(), app)
        tray.setToolTip("COOL-비서 — 펭귄 꺼내기")
        menu = QMenu()
        menu.addAction("🐧 펭귄 다시 보이기", bring_back)
        menu.addAction("🗓 캘린더 열기",
                       lambda: _widget() and _widget().open_calendar())
        menu.addAction("⚙ 설정",
                       lambda: _widget() and _widget().open_settings())
        menu.addSeparator()
        menu.addAction("종료", app.quit)
        tray.setContextMenu(menu)
        tray.activated.connect(
            lambda r: bring_back()
            if r == QSystemTrayIcon.ActivationReason.Trigger else None)
        tray.show()
        app._coolm_tray = tray              # GC 방지
        app._coolm_tray_menu = menu

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
