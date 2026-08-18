# -*- coding: utf-8 -*-
"""위젯 편집 기능 — 날짜별 ＋, 기간 일정, 편집 모드 이동·삭제 (2026-08-17)."""
import os
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication

from parser.pipeline import DEFAULT_CONFIG
from store.event_store import EventStore

_app = QApplication.instance() or QApplication([])
TODAY = date.today()
MONDAY = TODAY - timedelta(days=TODAY.weekday())


def _conf():
    return {"enabled": True, "geometry": None, "opacity": 100,
            "always_on_top": False, "font_scale": 100}


def _widget(cls, store, tmp):
    config = dict(DEFAULT_CONFIG)
    config["desk_widgets"] = {"notes": []}
    return cls(store, config, tmp, _conf())


class TestAddDialogDate(unittest.TestCase):
    """＋를 누른 그 날짜가 미리 채워져야 한다."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.store = EventStore(self.tmp)
        from ui.desk_widgets import AddEventDialog
        self.cls = AddEventDialog

    def test_prefills_given_date(self):
        d = date(2026, 9, 3)
        dlg = self.cls(self.store, default_date=d)
        self.assertEqual(dlg.date_btn.get_date(), d)

    def test_defaults_to_today_without_date(self):
        dlg = self.cls(self.store)
        self.assertEqual(dlg.date_btn.get_date(), date.today())

    def test_saves_on_that_date(self):
        d = date(2026, 9, 3)
        dlg = self.cls(self.store, default_date=d)
        dlg.title_edit.setText("학년 협의회")
        dlg.time_combo.set_all_day()
        dlg._save()
        self.assertEqual(self.store.all()[0].start_dt.date(), d)


class TestRangeEvent(unittest.TestCase):
    """기간 일정 — 시작일부터 끝나는 날까지 매일 보여야 한다."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.store = EventStore(self.tmp)
        from ui.desk_widgets import AddEventDialog
        self.dlg = AddEventDialog(self.store, default_date=date(2026, 9, 7))

    def _save_range(self, end):
        self.dlg.title_edit.setText("수련회")
        self.dlg.time_combo.set_all_day()
        self.dlg.range_cb.setChecked(True)
        self.dlg.end_btn.set_date(end)
        self.dlg._save()

    def test_range_hidden_until_checked(self):
        self.assertFalse(self.dlg.end_btn.isVisible())

    def test_saved_with_end(self):
        self._save_range(date(2026, 9, 9))
        ev = self.store.all()[0]
        self.assertIsNotNone(ev.end)
        self.assertEqual(ev.end_dt.date(), date(2026, 9, 9))

    def test_shows_on_every_day(self):
        self._save_range(date(2026, 9, 9))
        for day in (7, 8, 9):
            self.assertEqual(len(self.store.on_date(date(2026, 9, day))), 1,
                             f"9/{day}")
        self.assertEqual(self.store.on_date(date(2026, 9, 10)), [])

    def test_backwards_range_rejected(self):
        from PyQt6.QtWidgets import QMessageBox
        warned = []
        real = QMessageBox.warning
        QMessageBox.warning = lambda *a, **k: warned.append(a)
        try:
            self._save_range(date(2026, 9, 1))   # 끝이 시작보다 빠름
        finally:
            QMessageBox.warning = real
        self.assertTrue(warned)                  # 안내를 띄우고
        self.assertEqual(self.store.all(), [])   # 저장하지 않는다

    def test_end_follows_start(self):
        # 시작일을 뒤로 옮기면 끝나는 날도 따라온다
        self.dlg.range_cb.setChecked(True)
        self.dlg.date_btn.set_date(date(2026, 10, 1))
        self.dlg._sync_end_date(date(2026, 10, 1))
        self.assertGreaterEqual(self.dlg.end_btn.get_date(), date(2026, 10, 1))


class TestWeeklyMove(unittest.TestCase):
    """주간 위젯: 편집 모드에서 다른 요일로 끌면 날짜가 바뀐다."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.store = EventStore(self.tmp)
        self.ev = self.store.add("교직원 회의",
                                 datetime.combine(MONDAY, datetime.min.time())
                                 .replace(hour=15), all_day=False)
        from ui.desk_widgets import WeeklyWidget
        self.w = _widget(WeeklyWidget, self.store, self.tmp)

    def _field(self):
        from ui.desk_widgets import _WeekField
        for col in self.w.day_columns:
            f = col.findChild(_WeekField)
            if f is not None:
                return f
        return None

    def test_seven_columns_tracked(self):
        self.assertEqual(len(self.w.day_columns), 7)
        self.assertEqual([c.d for c in self.w.day_columns],
                         [MONDAY + timedelta(days=i) for i in range(7)])

    def test_move_changes_date_keeps_time(self):
        f = self._field()
        self.assertIsNotNone(f)
        f._move_to(MONDAY + timedelta(days=2))
        cur = self.store.all()[0]
        self.assertEqual(cur.start_dt.date(), MONDAY + timedelta(days=2))
        self.assertEqual(cur.start_dt.hour, 15)      # 시각은 그대로

    def test_move_keeps_range_length(self):
        ev = self.store.add("수련회", datetime.combine(MONDAY, datetime.min.time()),
                            end=datetime.combine(MONDAY + timedelta(days=2),
                                                 datetime.min.time()))
        from ui.desk_widgets import WeeklyWidget, _WeekField
        w = _widget(WeeklyWidget, self.store, self.tmp)
        field = None
        for col in w.day_columns:
            for f in col.findChildren(_WeekField):
                if f.event.id == ev.id:
                    field = f
        self.assertIsNotNone(field)
        field._move_to(MONDAY + timedelta(days=3))
        cur = next(e for e in self.store.all() if e.id == ev.id)
        self.assertEqual(cur.end_dt - cur.start_dt, timedelta(days=2))

    def test_drop_highlight_reverts(self):
        col = self.w.day_columns[0]
        base = col.styleSheet()
        col.set_drop_target(True)
        self.assertNotEqual(col.styleSheet(), base)
        col.set_drop_target(False)
        self.assertEqual(col.styleSheet(), base)


class TestTodoBoardMove(unittest.TestCase):
    """할 일 보드: 밀린 일을 '오늘' 칸으로 끌어 당길 수 있다."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.store = EventStore(self.tmp)
        self.store.add("성적 입력 마감",
                       datetime.combine(TODAY - timedelta(days=3),
                                        datetime.min.time()),
                       is_deadline=True)
        from ui.desk_widgets import SimpleTodoWidget
        self.w = _widget(SimpleTodoWidget, self.store, self.tmp)

    def test_drop_dates_of_columns(self):
        dates = [c.drop_date for c in self.w.day_columns]
        self.assertEqual(dates, [None, TODAY, TODAY + timedelta(days=1)])

    def test_pull_overdue_to_today(self):
        from ui.desk_widgets import _TodoRow
        row = self.w.day_columns[0].findChild(_TodoRow)
        self.assertIsNotNone(row)
        row._move_to(TODAY)
        self.assertEqual(self.store.all()[0].start_dt.date(), TODAY)


class TestEditModeDelete(unittest.TestCase):
    """편집 모드에서만 ✕ 삭제 버튼이 붙는다."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.store = EventStore(self.tmp)
        self.ev = self.store.add("가정통신문 배부",
                                 datetime.combine(TODAY, datetime.min.time()),
                                 is_deadline=True)
        from ui.desk_widgets import TodayTodoWidget
        self.w = _widget(TodayTodoWidget, self.store, self.tmp)

    def _buttons(self):
        from PyQt6.QtWidgets import QPushButton
        from ui.desk_widgets import _TodoRow
        row = self.w.findChild(_TodoRow)
        return [b for b in row.findChildren(QPushButton) if b.text() == "✕"]

    def test_hidden_in_normal_mode(self):
        self.assertEqual(self._buttons(), [])

    def test_shown_in_edit_mode(self):
        self.w.toggle_edit_mode()
        self.assertEqual(len(self._buttons()), 1)

    def test_delete_removes_event(self):
        from ui.desk_widgets import _confirm_delete
        import ui.desk_widgets as dw
        from PyQt6.QtWidgets import QMessageBox
        real = QMessageBox.question
        QMessageBox.question = staticmethod(
            lambda *a, **k: QMessageBox.StandardButton.Yes)
        try:
            self.assertTrue(_confirm_delete(self.w, self.ev, self.store))
        finally:
            QMessageBox.question = real
        self.assertEqual(self.store.all(), [])

    def test_cancel_keeps_event(self):
        from ui.desk_widgets import _confirm_delete
        from PyQt6.QtWidgets import QMessageBox
        real = QMessageBox.question
        QMessageBox.question = staticmethod(
            lambda *a, **k: QMessageBox.StandardButton.No)
        try:
            self.assertFalse(_confirm_delete(self.w, self.ev, self.store))
        finally:
            QMessageBox.question = real
        self.assertEqual(len(self.store.all()), 1)


if __name__ == "__main__":
    unittest.main()
