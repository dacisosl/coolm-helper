# -*- coding: utf-8 -*-
"""포스트잇: 상단 날짜·시간 인라인 편집 + 처음 켜질 때 잠깐 맨 앞 (2026-08-02)."""
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtCore import QDate, Qt
from PyQt6.QtWidgets import QApplication

from store.event_store import EventStore

_app = QApplication.instance() or QApplication([])


def _make_note(store, ev):
    from ui.desk_note import PostItWidget
    conf = {"event_id": ev.id, "geometry": None, "opacity": 95,
            "always_on_top": False, "font_scale": 100}
    config = {"desk_widgets": {"notes": [conf]}}
    return PostItWidget(store, config, store.path, conf, ev)


class TestWhenEdit(unittest.TestCase):
    def setUp(self):
        self.store = EventStore(tempfile.mkdtemp())
        self.ev = self.store.add("교직원 연수", datetime(2026, 8, 5, 15, 0),
                                 all_day=False)
        self.note = _make_note(self.store, self.ev)

    def _combo(self, h=None, m=None, all_day=False):
        from ui.review_dialog import TimeCombo
        tc = TimeCombo()
        if all_day:
            tc.set_all_day()
        else:
            tc.set_time(h, m)
        return tc

    def _saved(self):
        return self.store.all()[0]

    def test_label_shows_date_and_time(self):
        self.assertIn("8/5", self.note.when_label.text())
        self.assertIn("15:00", self.note.when_label.text())

    def test_clickable(self):
        # 라벨이 아니라 누를 수 있는 버튼이어야 한다
        self.assertTrue(hasattr(self.note.when_label, "clicked"))

    def test_date_and_time_saved(self):
        self.note._apply_when(QDate(2026, 8, 7), self._combo(9, 30))
        saved = self._saved()
        self.assertEqual(saved.start_dt, datetime(2026, 8, 7, 9, 30))
        self.assertFalse(saved.all_day)
        self.assertIn("09:30", self.note.when_label.text())

    def test_all_day_clears_time(self):
        self.note._apply_when(QDate(2026, 8, 7), self._combo(all_day=True))
        saved = self._saved()
        self.assertTrue(saved.all_day)
        self.assertEqual(saved.start_dt, datetime(2026, 8, 7, 0, 0))
        self.assertNotIn(":", self.note.when_label.text())

    def test_period_keeps_length(self):
        ev = self.store.add("수련회", datetime(2026, 9, 1, 9, 0),
                            end=datetime(2026, 9, 3, 17, 0), all_day=False)
        note = _make_note(self.store, ev)
        note._apply_when(QDate(2026, 9, 8), self._combo(9, 0))
        cur = next(e for e in self.store.all() if e.id == ev.id)
        self.assertEqual(cur.end_dt - cur.start_dt, timedelta(days=2, hours=8))

    def test_no_change_no_write(self):
        before = self._saved().start
        self.note._apply_when(QDate(2026, 8, 5), self._combo(15, 0))
        self.assertEqual(self._saved().start, before)

    def test_popup_opens(self):
        self.note._open_when_popup()      # 예외 없이 떠야 한다


class TestFlashToFront(unittest.TestCase):
    """처음 켜질 때만 잠깐 맨 앞 — '항상 위 고정'은 건드리지 않는다."""

    def setUp(self):
        self.store = EventStore(tempfile.mkdtemp())
        ev = self.store.add("알림장 쓰기", datetime(2026, 8, 5, 9, 0))
        self.note = _make_note(self.store, ev)
        self.note.apply_window_conf(first=True)

    def _top(self):
        return bool(self.note.windowFlags()
                    & Qt.WindowType.WindowStaysOnTopHint)

    def test_raises_then_settles(self):
        self.assertFalse(self._top())          # 평소엔 맨 아래
        self.note.flash_to_front(ms=10)
        self.assertTrue(self._top())           # 잠깐 맨 위
        self.note._end_flash()
        self.assertFalse(self._top())          # 다시 원래대로

    def test_setting_untouched(self):
        self.note.flash_to_front(ms=10)
        self.note._end_flash()
        self.assertFalse(self.note.conf.get("always_on_top"))

    def test_always_on_top_stays(self):
        self.note.conf["always_on_top"] = True
        self.note.apply_window_conf()
        self.note.flash_to_front(ms=10)
        self.note._end_flash()
        self.assertTrue(self._top())           # 켜 둔 고정은 그대로


if __name__ == "__main__":
    unittest.main()
