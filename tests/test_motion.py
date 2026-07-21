# -*- coding: utf-8 -*-
"""모션 시스템 검증 — 애니메이션 on/off 즉시성, 토스트 호버 일시정지,
   자주 쓰는 창의 무애니메이션 보증."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QWidget

_app = QApplication.instance() or QApplication(sys.argv)
from ui import motion


class TestMotionEnabledFlag(unittest.TestCase):
    def tearDown(self):
        motion.set_enabled(True)

    def test_disabled_fade_in_is_instant(self):
        motion.set_enabled(False)
        w = QWidget()
        motion.fade_in(w)
        self.assertEqual(w.windowOpacity(), 1.0)
        self.assertFalse(hasattr(w, "_motion_anim"))

    def test_enabled_fade_in_runs_then_full(self):
        from PyQt6.QtCore import QAbstractAnimation
        motion.set_enabled(True)
        w = QWidget()
        w.show()
        motion.fade_in(w, ms=40)
        self.assertTrue(hasattr(w, "_motion_anim"))
        self.assertEqual(w._motion_anim.state(),
                         QAbstractAnimation.State.Running)
        for _ in range(20):
            _app.processEvents()
            import time
            time.sleep(0.01)
        self.assertEqual(w.windowOpacity(), 1.0)

    def test_disabled_pop_in_is_instant(self):
        motion.set_enabled(False)
        w = QWidget()
        motion.pop_in(w)
        self.assertEqual(w.windowOpacity(), 1.0)

    def test_fade_out_close_guard(self):
        # 두 번 호출해도 close는 한 번만 (재진입 가드)
        motion.set_enabled(False)
        calls = []
        w = QWidget()
        w.close = lambda: calls.append(1)     # 감시
        motion.fade_out_close(w)
        motion.fade_out_close(w)
        self.assertEqual(len(calls), 1)


class TestToastHoverPause(unittest.TestCase):
    def test_hover_stops_timer(self):
        from ui.toast import Toast
        motion.set_enabled(True)
        host = QWidget()
        host.resize(400, 300)
        t = Toast(host, "테스트", msec=5000)
        self.assertTrue(t._timer.isActive())
        t.enterEvent(None)                    # 마우스 올림
        self.assertFalse(t._timer.isActive())
        t.leaveEvent(None)                    # 마우스 뗌
        self.assertTrue(t._timer.isActive())


class TestNoAnimationOnHotPaths(unittest.TestCase):
    """자주 쓰는 창(펭귄 메뉴·⚡ 등록)에는 모션이 끼지 않아야 한다."""

    def test_quick_dialog_has_no_motion_import(self):
        src = open(os.path.join(os.path.dirname(__file__), "..",
                                "ui", "quick_dialog.py"), encoding="utf-8").read()
        self.assertNotIn("import motion", src)
        self.assertNotIn("FadeInMixin", src)

    def test_iconbar_has_no_motion(self):
        src = open(os.path.join(os.path.dirname(__file__), "..",
                                "ui", "mini_widget.py"), encoding="utf-8").read()
        # _IconBar는 애니메이션 없이 즉시 떠야 한다
        self.assertNotIn("FadeInMixin", src)
        self.assertNotIn("pop_in", src)
        self.assertNotIn("fade_in", src)


if __name__ == "__main__":
    unittest.main()
