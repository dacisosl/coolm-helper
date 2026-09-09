# -*- coding: utf-8 -*-
"""토스트 — show() 도중 마우스 이벤트가 먼저 와도 깨지지 않는다 (2026-09-09).

v2.9.3 '제출' 보고: 토스트가 커서 바로 아래에 나타나면 show() 안에서 enterEvent가
즉시 불리는데, _timer가 show() 뒤에 만들어져 AttributeError → 오류 창이 떴다.
"""
import os
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication, QWidget

_app = QApplication.instance() or QApplication([])


class TestToastEarlyEvents(unittest.TestCase):
    def setUp(self):
        self.parent = QWidget()
        self.parent.resize(300, 200)
        self.parent.show()
        self.hooked = []
        self._real_hook = sys.excepthook
        sys.excepthook = lambda *a: self.hooked.append(a)

    def tearDown(self):
        sys.excepthook = self._real_hook
        self.parent.close()

    def test_enter_leave_during_show_do_not_raise(self):
        from ui import toast as tmod
        def show_with_hover(self):
            # 실제 버그 순서: show() 도중 enter/leave가 먼저 온다
            self.enterEvent(None)
            self.leaveEvent(None)
            QWidget.show(self)

        tmod.Toast.show = show_with_hover
        try:
            t = tmod.show_toast(self.parent, "제출을 위한 준비중입니다.", msec=3000)
        finally:
            del tmod.Toast.show          # 상속된 QWidget.show로 되돌린다
        QApplication.processEvents()
        self.assertEqual(self.hooked, [])
        self.assertTrue(t._timer.isActive())
        t._dismiss()

    def test_state_exists_before_show(self):
        """show() 앞에 _timer·_remaining·_closing이 모두 준비돼 있어야 한다."""
        import inspect
        from ui import toast as tmod
        src = inspect.getsource(tmod.Toast.__init__)
        show_at = src.index("self.show()")
        for name in ("self._timer = ", "self._remaining = ", "self._closing = "):
            self.assertLess(src.index(name), show_at, name)


if __name__ == "__main__":
    unittest.main(verbosity=2)
