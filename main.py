# -*- coding: utf-8 -*-
"""쿨메신저 일정 도우미 — 진입점.

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

from ui.floating_widget import FloatingWidget


def main() -> None:
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)    # 캘린더 창 닫아도 위젯은 유지
    w = FloatingWidget(BASE_DIR)
    # 우측 하단에 배치
    screen = app.primaryScreen().availableGeometry()
    w.move(screen.right() - w.width() - 24, screen.bottom() - w.height() - 24)
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
