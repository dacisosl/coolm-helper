# -*- coding: utf-8 -*-
import sys, os, tempfile, shutil, unittest
from datetime import date, datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from store.event_store import EventStore
from ui.alerts import (Alert, build_alerts, is_dismissed, mark_dismissed,
                       prune_dismissed)

TODAY = date(2026, 7, 20)


def texts(alerts) -> str:
    return "\n".join(a.text for a in alerts)


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
        joined = texts(build_alerts(self.store, TODAY))
        self.assertIn("마감 3일 전", joined)
        self.assertIn("마감 2일 전", joined)
        self.assertIn("마감 1일 전", joined)
        self.assertIn("오늘 마감", joined)

    def test_beyond_range_and_past_skipped(self):
        """고른 날보다 먼 일정과 이미 지난 일정은 알리지 않는다."""
        self.store.add("4일 뒤 마감", datetime(2026, 7, 24), is_deadline=True)
        self.store.add("지난 마감", datetime(2026, 7, 19), is_deadline=True)
        self.assertEqual(build_alerts(self.store, TODAY), [])

    def test_plain_events_also_alert(self):
        """마감 표시가 없어도 다가온 일정이면 알린다 (2026-08-31 결정)."""
        self.store.add("교육청 연수 교안", datetime(2026, 7, 21))
        self.store.add("모레 회의", datetime(2026, 7, 22))
        joined = texts(build_alerts(self.store, TODAY))
        self.assertIn("🗓 내일", joined)
        self.assertIn("🗓 모레", joined)
        self.assertIn("교육청 연수 교안", joined)

    def test_deadline_sorts_above_plain(self):
        """같은 날이라도 마감이 위에 온다 — ⏰로 강조."""
        self.store.add("그냥 일정", datetime(2026, 7, 20))
        self.store.add("먼 마감", datetime(2026, 7, 23), is_deadline=True)
        alerts = build_alerts(self.store, TODAY)
        self.assertIn("⏰ 마감 3일 전", alerts[0].text)
        self.assertIn("🗓 오늘", alerts[1].text)

    def test_running_multiday_event_counts_as_today(self):
        """어제 시작해 내일 끝나는 일정은 '오늘'로 알린다."""
        self.store.add("전시 주간", datetime(2026, 7, 19),
                       end=datetime(2026, 7, 21))
        alerts = build_alerts(self.store, TODAY)
        self.assertEqual(len(alerts), 1)
        self.assertIn("🗓 오늘", alerts[0].text)
        self.assertEqual(alerts[0].days_left, 0)

    def test_done_event_skipped(self):
        ev = self.store.add("끝낸 일", datetime(2026, 7, 21))
        self.store.set_done(ev.id, True)
        self.assertEqual(build_alerts(self.store, TODAY), [])

    def test_days_before_setting(self):
        """사용자가 고른 일수(기본 3 아님)를 그대로 따른다."""
        self.store.add("5일 뒤 마감", datetime(2026, 7, 25), is_deadline=True)
        self.assertEqual(build_alerts(self.store, TODAY), [])
        joined = texts(build_alerts(self.store, TODAY, days_before=7))
        self.assertIn("마감 5일 전", joined)

    def test_urgent_first(self):
        """급한 마감이 위로 온다."""
        self.store.add("3일 뒤 마감", datetime(2026, 7, 23), is_deadline=True)
        self.store.add("1일 뒤 마감", datetime(2026, 7, 21), is_deadline=True)
        alerts = build_alerts(self.store, TODAY)
        self.assertIn("1일 전", alerts[0].text)
        self.assertIn("3일 전", alerts[1].text)

    def test_done_deadline_skipped(self):
        ev = self.store.add("완료된 마감", datetime(2026, 7, 21), is_deadline=True)
        self.store.set_done(ev.id, True)
        self.assertEqual(build_alerts(self.store, TODAY), [])

    def test_today_events_listed_one_by_one(self):
        """오늘 것은 'N건' 요약이 아니라 제목이 보이게 한 줄씩 나온다."""
        self.store.add("오늘 회의", datetime(2026, 7, 20, 14), all_day=False)
        self.store.add("오늘 종일", datetime(2026, 7, 20))
        joined = texts(build_alerts(self.store, TODAY))
        self.assertIn("오늘 회의", joined)
        self.assertIn("오늘 종일", joined)
        self.assertNotIn("2건", joined)

    def test_empty(self):
        self.assertEqual(build_alerts(self.store, TODAY), [])

    def test_deadline_alert_carries_event_key(self):
        ev = self.store.add("마감", datetime(2026, 7, 21), is_deadline=True)
        alert = build_alerts(self.store, TODAY)[0]
        self.assertEqual(alert.key, f"ev:{ev.id}")
        self.assertEqual(alert.days_left, 1)


class TestDismiss(unittest.TestCase):
    """✕로 뗀 알림 기억하기 — 마감 당일만 예외로 한 번 더 뜬다."""

    def test_dismissed_alert_stays_hidden(self):
        config = {}
        alert = Alert("⏰ 마감 3일 전\n성적", key="ev:a1", days_left=3)
        self.assertFalse(is_dismissed(alert, config))
        self.assertTrue(mark_dismissed(alert, config))
        self.assertTrue(is_dismissed(alert, config))
        # 다음 날 더 급해져도(2일 전) 이미 뗐으므로 조용하다
        self.assertTrue(is_dismissed(
            Alert("⏰ 마감 2일 전\n성적", key="ev:a1", days_left=2), config))

    def test_deadline_day_shows_once_more(self):
        config = {}
        mark_dismissed(Alert("", key="ev:a1", days_left=3), config)
        final = Alert("⏰ 오늘 마감\n성적", key="ev:a1", days_left=0)
        self.assertFalse(is_dismissed(final, config))   # 당일은 예외
        mark_dismissed(final, config)                   # 당일에 뗐다면
        self.assertTrue(is_dismissed(final, config))    # 그걸로 끝

    def test_keyless_alert_never_remembered(self):
        config = {}
        notice = Alert("COOL-비서가 켜졌어요")
        self.assertFalse(mark_dismissed(notice, config))
        self.assertFalse(is_dismissed(notice, config))

    def test_junk_record_treated_as_final(self):
        config = {"alert_dismissed": {"ev:a1": "셋"}}
        self.assertTrue(is_dismissed(
            Alert("", key="ev:a1", days_left=0), config))


class TestPruneDismissed(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.store = EventStore(self.tmp, "store")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_deleted_event_record_removed(self):
        ev = self.store.add("마감", datetime(2026, 7, 21), is_deadline=True)
        config = {"alert_dismissed": {f"ev:{ev.id}": 1, "ev:없는것": 2}}
        self.assertTrue(prune_dismissed(config, self.store, TODAY))
        self.assertEqual(list(config["alert_dismissed"]), [f"ev:{ev.id}"])

    def test_stale_summary_key_removed(self):
        """옛 버전이 남긴 'today:...' 기록도 정리된다."""
        config = {"alert_dismissed": {"today:2026-07-19": 0}}
        self.assertTrue(prune_dismissed(config, self.store, TODAY))
        self.assertEqual(config["alert_dismissed"], {})

    def test_noop_when_nothing_to_clean(self):
        self.assertFalse(prune_dismissed({}, self.store, TODAY))


if __name__ == "__main__":
    unittest.main(verbosity=2)
