# -*- coding: utf-8 -*-
import sys, os, tempfile, shutil, unittest
from datetime import date, datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from store.event_store import EventStore
from ui.alerts import build_alerts

TODAY = date(2026, 7, 20)


class TestBuildAlerts(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.store = EventStore(self.tmp, "store")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_default_3_days_before(self):
        """기본값: 3일 전부터 마감 당일까지 매일 알린다."""
        self.store.add("3일 뒤 마감", datetime(2026, 7, 23), is_deadline=True)
        self.store.add("2일 뒤 마감", datetime(2026, 7, 22), is_deadline=True)
        self.store.add("1일 뒤 마감", datetime(2026, 7, 21), is_deadline=True)
        self.store.add("오늘 마감", datetime(2026, 7, 20), is_deadline=True)
        joined = "\n".join(build_alerts(self.store, TODAY))
        self.assertIn("마감 3일 전", joined)
        self.assertIn("마감 2일 전", joined)
        self.assertIn("마감 1일 전", joined)
        self.assertIn("오늘 마감", joined)

    def test_beyond_range_and_past_skipped(self):
        """고른 날보다 먼 마감과 이미 지난 마감은 알리지 않는다."""
        self.store.add("4일 뒤 마감", datetime(2026, 7, 24), is_deadline=True)
        self.store.add("지난 마감", datetime(2026, 7, 19), is_deadline=True)
        self.assertEqual(build_alerts(self.store, TODAY), [])

    def test_days_before_setting(self):
        """사용자가 고른 일수(기본 3 아님)를 그대로 따른다."""
        self.store.add("5일 뒤 마감", datetime(2026, 7, 25), is_deadline=True)
        self.assertEqual(build_alerts(self.store, TODAY), [])
        joined = "\n".join(build_alerts(self.store, TODAY, days_before=7))
        self.assertIn("마감 5일 전", joined)

    def test_urgent_first(self):
        """급한 마감이 위로 온다."""
        self.store.add("3일 뒤 마감", datetime(2026, 7, 23), is_deadline=True)
        self.store.add("1일 뒤 마감", datetime(2026, 7, 21), is_deadline=True)
        alerts = build_alerts(self.store, TODAY)
        self.assertIn("1일 전", alerts[0])
        self.assertIn("3일 전", alerts[1])

    def test_done_deadline_skipped(self):
        ev = self.store.add("완료된 마감", datetime(2026, 7, 21), is_deadline=True)
        self.store.set_done(ev.id, True)
        self.assertEqual(build_alerts(self.store, TODAY), [])

    def test_today_count(self):
        self.store.add("오늘 일정", datetime(2026, 7, 20, 14), all_day=False)
        self.store.add("오늘 종일", datetime(2026, 7, 20))
        alerts = build_alerts(self.store, TODAY)
        self.assertTrue(any("오늘 일정 2건" in a for a in alerts))

    def test_order_deadline_first(self):
        self.store.add("오늘 일정", datetime(2026, 7, 20))
        self.store.add("마감", datetime(2026, 7, 21), is_deadline=True)
        alerts = build_alerts(self.store, TODAY)
        self.assertIn("마감", alerts[0])
        self.assertIn("오늘", alerts[-1])

    def test_empty(self):
        self.assertEqual(build_alerts(self.store, TODAY), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
