# -*- coding: utf-8 -*-
"""창을 옮기는 규칙 — 펭귄과 바탕화면 위젯 (2026-08-25~26 사용자 요청).

- 펭귄: 오른쪽 벽 도킹을 풀고 어디로든(다른 모니터로도). 📌로 고정도 된다.
- 위젯: 제목줄만 잡히던 것을 몸통 아무 데나 잡아도 옮겨지게.
- 공통: 놓은 자리를 기억하고, 보조 모니터 자리를 주 화면으로 끌고 오지 않는다.
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

    def test_bar_has_only_three_icons(self):
        """아이콘 바는 📌 고정 · ✉ 쪽지 목록 · ⚙ 설정 셋뿐 (2026-09-03)."""
        from PyQt6.QtWidgets import QPushButton
        self.w.config["neis_enabled"] = True       # 켜져 있어도 바에는 안 는다
        self.w.config["proof_enabled"] = True
        bar = _IconBar(self.w)
        tips = [b.toolTip() for b in bar.findChildren(QPushButton)]
        self.assertEqual(len(tips), 3)
        self.assertIn("고정", tips[0])
        self.assertIn("쪽지 목록", tips[1])
        self.assertIn("설정", tips[2])
        joined = " ".join(tips)
        self.assertNotIn("바로 등록", joined)      # ⚡는 우클릭·더블클릭으로
        self.assertNotIn("학사일정", joined)
        bar.close()

    def test_right_click_menu_keeps_moved_features(self):
        """바에서 뺀 기능은 우클릭 메뉴에 살아 있어야 한다 (기능 유실 방지)."""
        from PyQt6.QtWidgets import QMenu
        self.w.config["neis_enabled"] = True
        self.w.config["proof_enabled"] = True
        opened = []
        real = QMenu.exec
        QMenu.exec = lambda self, *a: (
            opened.extend(a.text() for a in self.actions()), None)[1]
        try:
            self.w.contextMenuEvent(_FakeContext(QPoint(0, 0)))
        finally:
            QMenu.exec = real
        joined = " ".join(opened)
        self.assertIn("바로 등록", joined)
        self.assertIn("학사일정", joined)
        self.assertIn("문구 보정", joined)

    def test_bar_flips_when_penguin_is_at_left_edge(self):
        g = _screen()
        self.w.move(g.left(), g.center().y())
        self.w._open_bar()
        bar = self.w._bar
        self.assertIsNotNone(bar)
        self.assertGreaterEqual(bar.x(), g.left())
        self.assertLessEqual(bar.x() + bar.width(), g.right() + 1)
        bar.close()


class _FakeContext:
    """contextMenuEvent에 넘길 가짜 이벤트 — 우클릭 좌표만 있으면 된다."""

    def __init__(self, glob: QPoint):
        self._g = glob

    def globalPos(self):
        return self._g


class _FakePress:
    """mousePressEvent/ReleaseEvent에 넘길 가짜 이벤트 (지역·전역 좌표)."""

    def __init__(self, local: QPoint, glob: QPoint):
        self._l, self._g = local, glob

    def button(self):
        from PyQt6.QtCore import Qt
        return Qt.MouseButton.LeftButton

    def buttons(self):
        from PyQt6.QtCore import Qt
        return Qt.MouseButton.LeftButton

    def position(self):
        return _FakePointF(self._l)

    def globalPosition(self):
        return _FakePointF(self._g)


class TestDeskWidgetMove(unittest.TestCase):
    """바탕화면 위젯도 아무 데나 잡아 옮긴다 (2026-08-26 사용자 요청).

    예전엔 제목줄(위 40px)을 정확히 집어야만 움직였다.
    """

    def setUp(self):
        from parser.pipeline import desk_conf, load_config
        from store.event_store import EventStore
        from ui.desk_widgets import TodayTodoWidget
        self.tmp = tempfile.mkdtemp()
        conf = load_config(self.tmp)
        self.w = TodayTodoWidget(EventStore(self.tmp), conf, self.tmp,
                                 desk_conf(conf, "today"))
        self.w.show()

    def tearDown(self):
        self.w.close()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _grab(self, local):
        return _FakePress(local, self.w.mapToGlobal(local))

    def test_body_center_starts_a_move(self):
        mid = QPoint(self.w.width() // 2, self.w.height() // 2)
        self.w.mousePressEvent(self._grab(mid))
        self.assertEqual(self.w._mode, "move")

    def test_drag_moves_widget(self):
        g = _screen()
        self.w.move(g.left() + 120, g.top() + 120)
        mid = QPoint(self.w.width() // 2, self.w.height() // 2)
        self.w.mousePressEvent(self._grab(mid))
        self.w.mouseMoveEvent(_FakePress(
            mid, self.w.mapToGlobal(mid) + QPoint(90, 60)))
        self.assertEqual(self.w.pos(), QPoint(g.left() + 210, g.top() + 180))

    def test_drag_stays_on_screen(self):
        mid = QPoint(self.w.width() // 2, self.w.height() // 2)
        self.w.mousePressEvent(self._grab(mid))
        self.w.mouseMoveEvent(_FakePress(
            mid, self.w.mapToGlobal(mid) + QPoint(9000, 9000)))
        self.assertTrue(widget_base.on_any_screen(self.w.frameGeometry()))

    def test_release_saves_only_when_moved(self):
        mid = QPoint(self.w.width() // 2, self.w.height() // 2)
        self.w.conf.pop("geometry", None)
        self.w.mousePressEvent(self._grab(mid))       # 클릭만 (이동 없음)
        self.w.mouseReleaseEvent(self._grab(mid))
        self.assertIsNone(self.w.conf.get("geometry"))

        self.w.mousePressEvent(self._grab(mid))
        self.w.mouseMoveEvent(_FakePress(
            mid, self.w.mapToGlobal(mid) + QPoint(30, 20)))
        self.w.mouseReleaseEvent(self._grab(mid))
        self.assertIsNotNone(self.w.conf.get("geometry"))

    def test_saved_spot_on_second_monitor_is_kept(self):
        """보조 모니터 자리를 주 화면 기준으로 자르면 안 된다."""
        from ui import screens
        g = _screen()
        self.w.conf["geometry"] = [g.left() + 60, g.top() + 60, 240, 180]
        self.w.show_at_saved()
        self.assertEqual(self.w.pos(), QPoint(g.left() + 60, g.top() + 60))
        # 어느 화면에도 없는 자리는 기본 배치로 구조된다
        self.w.conf["geometry"] = [50000, 50000, 240, 180]
        self.w.show_at_saved()
        self.assertTrue(screens.on_any_screen(self.w.frameGeometry()))

    def test_ensure_on_screen_leaves_valid_spot(self):
        g = _screen()
        self.w.move(g.left() + 200, g.top() + 200)
        self.w._ensure_on_screen()
        self.assertEqual(self.w.pos(), QPoint(g.left() + 200, g.top() + 200))


class TestBestScreenRect(unittest.TestCase):
    def test_picks_overlapping_screen(self):
        from ui import screens
        g = _screen()
        rect = screens.best_screen_rect([g.left() + 10, g.top() + 10, 100, 100])
        self.assertEqual(rect, [g.x(), g.y(), g.width(), g.height()])

    def test_broken_value_is_none(self):
        from ui import screens
        for bad in (None, [], [1, 2, 3], ["a", "b", "c", "d"], "문자열"):
            self.assertIsNone(screens.best_screen_rect(bad))


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
