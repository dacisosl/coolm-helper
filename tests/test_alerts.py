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

    def test_deadline_3_and_1_days(self):
        self.store.add("3일 뒤 마감", datetime(2026, 7, 23), is_deadline=True)
        self.store.add("1일 뒤 마감", datetime(2026, 7, 21), is_deadline=True)
        self.store.add("2일 뒤 마감(알림 없음)", datetime(2026, 7, 22),
                       is_deadline=True)
        alerts = build_alerts(self.store, TODAY)
        joined = "\n".join(alerts)
        self.assertIn("마감 3일 전", joined)
        self.assertIn("마감 1일 전", joined)
        self.assertNotIn("2일", joined)

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
