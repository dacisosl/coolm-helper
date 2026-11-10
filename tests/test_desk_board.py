# -*- coding: utf-8 -*-
"""'일정 · 할 일' 2열 보드 위젯 (2026-11-10, 체킹 리디자인)."""
import os
import shutil
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("COOLM_NO_CAPTURE", "1")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication

from store.event_store import EventStore
from store.todo_store import TodoStore
from ui import desk_board as db
from ui import theme

_app = QApplication.instance() or QApplication([])


class TestPure(unittest.TestCase):
    def test_week_is_sunday_to_saturday(self):
        self.assertEqual(db.week_bounds(date(2026, 11, 10)),
                         (date(2026, 11, 8), date(2026, 11, 14)))
        self.assertEqual(db.week_bounds(date(2026, 11, 8))[0], date(2026, 11, 8))
        self.assertEqual(db.week_bounds(date(2026, 11, 14))[0], date(2026, 11, 8))

    def test_week_title_and_range(self):
        self.assertEqual(db.week_title(date(2026, 11, 8)), "11월 2주차")
        self.assertEqual(db.week_title(date(2026, 11, 1)), "11월 1주차")
        self.assertEqual(db.week_title(date(2026, 10, 25)), "10월 5주차")   # 월말 걸친 주
        self.assertEqual(db.week_range_text(date(2026, 11, 8)), "11.8 – 11.14")

    def test_density_steps(self):
        self.assertEqual(db.density(200), "normal")
        self.assertEqual(db.density(150), "compact")
        self.assertEqual(db.density(110), "tiny")
        self.assertEqual(db.density(150, 85), "normal")    # 글씨를 줄이면 덜 압축

    def test_hues_rotate_within_week(self):
        class E:
            def __init__(self, i):
                self.id = i
        m = db.hue_map([E(f"e{i}") for i in range(8)])
        self.assertEqual([m[f"e{i}"] for i in range(8)], [0, 1, 2, 3, 4, 5, 0, 1])


class _Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.events = EventStore(self.tmp)
        self.todos = TodoStore(self.tmp)
        db.TodoStore._shared[os.path.abspath(self.tmp)] = self.todos
        self.today = date.today()
        self.week = db.week_bounds(self.today)[0]

    def tearDown(self):
        db.TodoStore._shared.pop(os.path.abspath(self.tmp), None)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _ev(self, title, d):
        return self.events.add(title, datetime(d.year, d.month, d.day))


class TestSplitTodos(_Base):
    def test_linked_loose_and_other_weeks(self):
        mine = self._ev("이번 주 일정", self.week + timedelta(days=2))
        other = self._ev("다음 주 일정", self.week + timedelta(days=9))
        a = self.todos.add("이번 주 일정의 할 일", event_id=mine.id)
        self.todos.add("다음 주 일정의 할 일", event_id=other.id)
        c = self.todos.add("날짜 없는 할 일")
        d = self.todos.add("지운 일정의 할 일", event_id="gone")
        self.todos.add("다음 주로 정한 할 일", day=self.week + timedelta(days=8))
        week = db.events_in_week(self.events.all(), self.week)
        by_ev, loose = db.split_todos(self.todos.all(), week,
                                      {e.id for e in self.events.all()},
                                      self.week, self.today)
        self.assertEqual([t.id for t in by_ev[mine.id]], [a.id])
        self.assertNotIn(other.id, by_ev)
        self.assertEqual({t.id for t in loose}, {c.id, d.id})   # 지운 일정 → 미분류

    def test_floating_todo_not_shown_in_other_weeks(self):
        self.todos.add("떠 있는 할 일")
        _by, loose = db.split_todos(self.todos.all(), [], set(),
                                    self.week + timedelta(days=7), self.today)
        self.assertEqual(loose, [])


class TestWidget(_Base):
    def _widget(self, view="table", w=380, h=440):
        conf = {"enabled": True, "geometry": None, "opacity": 100,
                "always_on_top": False, "font_scale": 100, "view": view}
        wdg = db.BoardWidget(self.events, {"desk_widgets": {}}, self.tmp, conf)
        wdg._save_config = lambda: None
        wdg.resize(w, h)
        wdg.show()
        for _ in range(3):
            QApplication.processEvents()
        wdg.refresh()
        for _ in range(3):                    # 다시 그린 칸들이 자리를 잡게
            QApplication.processEvents()
        self.addCleanup(wdg.close)
        return wdg

    def test_two_columns_even_when_narrow(self):
        ev = self._ev("1학년 수행평가 실시", self.week + timedelta(days=4))
        self.todos.add("수행평가 준비", event_id=ev.id)
        for width in (640, 380, 250):
            wdg = self._widget(w=width)
            card = wdg.grid.itemAtPosition(1, 0).widget()
            cell = wdg.grid.itemAtPosition(1, 1).widget()
            self.assertIsNotNone(card)
            self.assertIsNotNone(cell)
            self.assertLess(card.geometry().right(), cell.geometry().left())  # 나란히
        self.assertEqual(wdg.dens, "tiny")

    def test_add_link_in_event_row_links_todo(self):
        ev = self._ev("글로벌연수 발표", self.week + timedelta(days=6))
        wdg = self._widget()
        wdg.add_todo(f"ev:{ev.id}", "발표 준비")
        self.assertEqual(self.todos.for_event(ev.id)[0].title, "발표 준비")

    def test_day_and_loose_add(self):
        wdg = self._widget(view="days")
        day = self.week + timedelta(days=3)
        wdg.add_todo(f"day:{day.isoformat()}", "그날 할 일")
        wdg.add_todo("loose", "미분류 할 일")
        titles = {t.title: t for t in self.todos.all()}
        self.assertEqual(titles["그날 할 일"].day_date, day)
        self.assertEqual(titles["미분류 할 일"].day, "")     # 이번 주 미분류 = 날짜 없음

    def test_loose_add_in_other_week_keeps_it_there(self):
        wdg = self._widget()
        wdg.shift_week(2)
        t = wdg.add_todo("loose", "다다음 주 메모")
        self.assertEqual(t.day_date, self.week + timedelta(days=14))

    def test_check_saves(self):
        t = self.todos.add("체크할 일")
        wdg = self._widget()
        from ui.desk_board import _TodoPill
        pill = wdg.inner.findChildren(_TodoPill)[0]
        pill.check.click()
        self.assertTrue(TodoStore(self.tmp).get(t.id).done)

    def test_header_and_week_navigation(self):
        wdg = self._widget()
        self.assertEqual(wdg.title_lbl.text(), db.week_title(self.week))
        self.assertTrue(wdg.go_now.isHidden())
        wdg.shift_week(1)
        self.assertEqual(wdg.title_lbl.text(), db.week_title(self.week + timedelta(days=7)))
        self.assertFalse(wdg.go_now.isHidden())
        wdg.go_this_week()
        self.assertEqual(wdg.week_start, self.week)

    def test_view_toggle_saved_in_conf(self):
        wdg = self._widget()
        wdg.set_view(db.VIEW_DAYS)
        self.assertEqual(wdg.conf["view"], "days")
        self.assertTrue(wdg.seg_btns["days"].isChecked())

    def test_event_hue_matches_its_todo_cell(self):
        ev = self._ev("색 확인", self.week + timedelta(days=1))
        self.todos.add("할 일", event_id=ev.id)
        wdg = self._widget()
        bg = theme.BOARD_HUES[wdg.hues[ev.id]][0]
        self.assertIn(bg, wdg.grid.itemAtPosition(1, 0).widget().styleSheet())
        self.assertIn(bg, wdg.grid.itemAtPosition(1, 1).widget().styleSheet())

    def test_store_change_redraws(self):
        wdg = self._widget()
        self.todos.add("나중에 추가")
        for _ in range(3):
            QApplication.processEvents()
        from ui.desk_board import _TodoPill
        self.assertIn("나중에 추가",
                      [p.label.text() for p in wdg.inner.findChildren(_TodoPill)])


class TestRegistration(unittest.TestCase):
    def test_kind_registered(self):
        from parser import pipeline
        from ui.desk_base import _widget_class
        self.assertIn("board", pipeline.DESK_KINDS)
        self.assertEqual(pipeline.DEFAULT_CONFIG["desk_widgets"]["board"]["enabled"], False)
        self.assertIs(_widget_class("board"), db.BoardWidget)

    def test_settings_lists_board(self):
        import inspect
        from ui import settings_dialog
        self.assertIn('"board", "일정 · 할 일 보드"', inspect.getsource(settings_dialog))


if __name__ == "__main__":
    unittest.main(verbosity=2)
