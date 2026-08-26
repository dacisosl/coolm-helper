# -*- coding: utf-8 -*-
"""펭귄 자유 이동 + 📌 위치 고정 (2026-08-25 사용자 요청).

예전엔 오른쪽 벽에 붙은 채 위아래로만 움직였다. 이제 어디로든(다른
모니터로도) 끌 수 있고, 놓은 자리를 기억하며, 📌로 붙박이도 된다.
"""
import os
import shutil
import sys
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["COOLM_NO_CAPTURE"] = "1"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtCore import QPoint, QRect, QSize
from PyQt6.QtWidgets import QApplication

_app = QApplication.instance() or QApplication(sys.argv)

from parser import pipeline
from ui import widget_base
from ui.mini_widget import MiniWidget, _IconBar


def _screen():
    return QApplication.primaryScreen().availableGeometry()


class TestScreenHelpers(unittest.TestCase):
    """화면 계산 — 보조 모니터 좌표(음수 포함)를 견뎌야 한다."""

    def test_clamp_keeps_window_inside(self):
        g = _screen()
        far = QPoint(g.right() + 5000, g.bottom() + 5000)
        pos = widget_base.clamp_to_screens(far, QSize(60, 60))
        self.assertTrue(g.contains(QRect(pos, QSize(60, 60))))

    def test_clamp_leaves_valid_position_alone(self):
        g = _screen()
        inside = QPoint(g.left() + 40, g.top() + 40)
        self.assertEqual(widget_base.clamp_to_screens(inside, QSize(60, 60)),
                         inside)

    def test_clamp_uses_anchor_screen(self):
        """드래그 중엔 커서가 있는 화면이 기준 — 경계에서 끈적이지 않게."""
        g = _screen()
        pos = widget_base.clamp_to_screens(
            QPoint(g.right() + 900, g.top() + 10), QSize(60, 60), g.center())
        self.assertTrue(g.contains(QRect(pos, QSize(60, 60))))

    def test_screen_at_falls_back_to_nearest(self):
        # 화면 사이 틈이나 아주 먼 좌표라도 None이 아니라 가까운 화면을 준다
        self.assertIsNotNone(widget_base.screen_at(QPoint(-99999, -99999)))

    def test_on_any_screen(self):
        g = _screen()
        self.assertTrue(widget_base.on_any_screen(QRect(g.center(), QSize(10, 10))))
        self.assertFalse(widget_base.on_any_screen(
            QRect(QPoint(g.right() + 4000, g.bottom() + 4000), QSize(10, 10))))


class TestPenguinMove(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.w = MiniWidget(self.tmp)
        self.w.show()

    def tearDown(self):
        self.w.close()
        shutil.rmtree(self.tmp, ignore_errors=True)

    # ── 자유 이동 ────────────────────────────────────────────
    def test_moves_horizontally_too(self):
        """예전엔 x가 오른쪽 벽에 붙박여 있었다 — 이제 가로로도 움직인다."""
        g = _screen()
        target = QPoint(g.left() + 120, g.top() + 90)
        self.w.move(widget_base.clamp_to_screens(target, self.w.size()))
        self.assertEqual(self.w.pos(), target)

    def test_resize_keeps_place(self):
        """펭귄 크기를 바꿔도 오른쪽 벽으로 되돌아가지 않는다."""
        g = _screen()
        self.w.move(g.left() + 200, g.top() + 200)
        before = self.w.pos()
        self.w.config["penguin_scale"] = 200
        self.w._resize_to_penguin()
        self.assertLess(abs(self.w.x() - before.x()), 60)   # 커진 폭만큼만
        self.assertEqual(self.w.y(), before.y())

    def test_ensure_on_screen_does_not_dock_right(self):
        g = _screen()
        self.w.move(g.left() + 150, g.top() + 150)
        self.w._ensure_on_screen()
        self.assertEqual(self.w.x(), g.left() + 150)

    def test_ensure_on_screen_rescues_lost_penguin(self):
        self.w.move(30000, 30000)
        self.w._ensure_on_screen()
        self.assertTrue(widget_base.on_any_screen(self.w.frameGeometry()))

    # ── 자리 기억 ────────────────────────────────────────────
    def test_save_and_restore_position(self):
        g = _screen()
        self.w.move(g.left() + 77, g.top() + 88)
        self.w.save_position()
        self.assertEqual(self.w.config["penguin_pos"],
                         [g.left() + 77, g.top() + 88])
        saved = pipeline.load_config(self.tmp)
        self.assertEqual(saved["penguin_pos"], [g.left() + 77, g.top() + 88])

        self.w.move(g.left(), g.top())
        self.w.restore_position()
        self.assertEqual(self.w.pos(), QPoint(g.left() + 77, g.top() + 88))

    def test_restore_ignores_position_from_unplugged_monitor(self):
        """모니터를 뽑아 그 자리가 사라졌으면 기본 자리로."""
        self.w.config["penguin_pos"] = [40000, 40000]
        self.w.restore_position()
        self.assertTrue(widget_base.on_any_screen(self.w.frameGeometry()))

    def test_restore_survives_broken_value(self):
        for bad in ("문자열", [1], None, ["a", "b"], {}):
            self.w.config["penguin_pos"] = bad
            self.w.restore_position()          # 죽지 않고 기본 자리로
            self.assertTrue(widget_base.on_any_screen(self.w.frameGeometry()))

    # ── 📌 고정 ─────────────────────────────────────────────
    def test_lock_defaults_off(self):
        self.assertFalse(self.w.is_locked())

    def test_toggle_lock_persists(self):
        self.w.toggle_lock()
        self.assertTrue(self.w.is_locked())
        self.assertTrue(pipeline.load_config(self.tmp)["penguin_locked"])
        self.w.toggle_lock()
        self.assertFalse(self.w.is_locked())
        self.assertFalse(pipeline.load_config(self.tmp)["penguin_locked"])

    def test_locked_penguin_ignores_drag(self):
        g = _screen()
        self.w.move(g.left() + 100, g.top() + 100)
        self.w.toggle_lock()
        before = self.w.pos()
        # 드래그 중이라 치고 이동 로직을 직접 부른다 (마우스 없이)
        self.w._drag = QPoint(0, 0)
        self.w.mouseMoveEvent(_FakeMove(QPoint(g.left() + 400, g.top() + 400)))
        self.assertEqual(self.w.pos(), before)

    def test_unlocked_penguin_follows_drag(self):
        g = _screen()
        self.w.move(g.left() + 100, g.top() + 100)
        self.w._drag = QPoint(0, 0)
        self.w.mouseMoveEvent(_FakeMove(QPoint(g.left() + 300, g.top() + 250)))
        self.assertEqual(self.w.pos(), QPoint(g.left() + 300, g.top() + 250))

    def test_tooltip_mentions_lock_state(self):
        self.assertIn("드래그", self.w.penguin.toolTip())
        self.w.toggle_lock()
        self.assertIn("고정", self.w.penguin.toolTip())

    # ── 아이콘 바 ────────────────────────────────────────────
    def test_bar_has_pin_button_first(self):
        from PyQt6.QtWidgets import QPushButton
        bar = _IconBar(self.w)
        bar.adjustSize()
        btns = bar.findChildren(QPushButton)
        self.assertTrue(btns)
        self.assertIn("고정", btns[0].toolTip())
        bar.close()

    def test_bar_flips_when_penguin_is_at_left_edge(self):
        g = _screen()
        self.w.move(g.left(), g.center().y())
        self.w._open_bar()
        bar = self.w._bar
        self.assertIsNotNone(bar)
        self.assertGreaterEqual(bar.x(), g.left())
        self.assertLessEqual(bar.x() + bar.width(), g.right() + 1)
        bar.close()


class _FakeMove:
    """mouseMoveEvent에 넘길 최소한의 가짜 이벤트."""

    def __init__(self, global_pos: QPoint):
        self._p = global_pos

    def buttons(self):
        from PyQt6.QtCore import Qt
        return Qt.MouseButton.LeftButton

    def globalPosition(self):
        return _FakePointF(self._p)


class _FakePointF:
    def __init__(self, p):
        self._p = p

    def toPoint(self):
        return self._p


if __name__ == "__main__":
    unittest.main()
