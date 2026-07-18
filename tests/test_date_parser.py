# -*- coding: utf-8 -*-
import sys, os, unittest
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from parser.date_parser import extract_events, strip_date_expressions, normalize

BASE = datetime(2026, 7, 16, 17, 0)  # 목요일


class TestAbsoluteDates(unittest.TestCase):
    def test_month_day_with_time(self):
        evs = extract_events("7월 21일(화) 14:00 학폭위 심의", BASE)
        self.assertEqual(len(evs), 1)
        self.assertEqual(evs[0].start, datetime(2026, 7, 21, 14, 0))
        self.assertFalse(evs[0].all_day)

    def test_slash_date(self):
        evs = extract_events("회의는 7/21 오후 2시입니다", BASE)
        self.assertEqual(evs[0].start, datetime(2026, 7, 21, 14, 0))

    def test_dot_date_no_time(self):
        evs = extract_events("7.21(화) 현장체험학습", BASE)
        self.assertEqual(evs[0].start.date(), datetime(2026, 7, 21).date())
        self.assertTrue(evs[0].all_day)

    def test_full_date(self):
        evs = extract_events("2026-09-01 09:00 개학식", BASE)
        self.assertEqual(evs[0].start, datetime(2026, 9, 1, 9, 0))

    def test_korean_hour_minute(self):
        evs = extract_events("9월 1일 9시 30분 개학식", BASE)
        self.assertEqual(evs[0].start, datetime(2026, 9, 1, 9, 30))

    def test_half_hour(self):
        evs = extract_events("7월 21일 2시반 상담", BASE)
        self.assertEqual(evs[0].start.minute, 30)

    def test_year_rollover(self):
        """기준일이 12월일 때 '1월 10일'은 이듬해로 해석."""
        evs = extract_events("1월 10일 방학식", datetime(2026, 12, 20))
        self.assertEqual(evs[0].start.date(), datetime(2027, 1, 10).date())

    def test_evening(self):
        evs = extract_events("7월 21일 저녁 7시 학부모 모임", BASE)
        self.assertEqual(evs[0].start.hour, 19)


class TestRelativeDates(unittest.TestCase):
    def test_tomorrow(self):
        evs = extract_events("내일 10시 부장회의", BASE)
        self.assertEqual(evs[0].start, datetime(2026, 7, 17, 10, 0))

    def test_next_week_weekday(self):
        # BASE는 목요일(7/16) → 다음 주 화요일 = 7/21
        evs = extract_events("다음 주 화요일 14:00 회의", BASE)
        self.assertEqual(evs[0].start, datetime(2026, 7, 21, 14, 0))

    def test_relative_uses_receive_date_not_today(self):
        old_base = datetime(2026, 7, 1, 9, 0)
        evs = extract_events("내일 오전 9시 제출", old_base)
        self.assertEqual(evs[0].start.date(), datetime(2026, 7, 2).date())


class TestRangeAndDeadline(unittest.TestCase):
    def test_range(self):
        evs = extract_events("7/21(월)~7/25(금) 여름방학 캠프", BASE)
        self.assertEqual(len(evs), 1)
        self.assertEqual(evs[0].start.date(), datetime(2026, 7, 21).date())
        self.assertEqual(evs[0].end.date(), datetime(2026, 7, 25).date())

    def test_deadline(self):
        evs = extract_events("7월 21일까지 제출 바랍니다", BASE)
        self.assertTrue(evs[0].is_deadline)

    def test_no_date(self):
        self.assertEqual(extract_events("안녕하세요 감사합니다", BASE), [])

    def test_duplicate_date_merged(self):
        evs = extract_events("7월 21일 회의. 다시 안내: 7월 21일 회의", BASE)
        self.assertEqual(len(evs), 1)


class TestHelpers(unittest.TestCase):
    def test_normalize_fullwidth(self):
        self.assertEqual(normalize("１４：００"), "14:00")

    def test_strip_dates_for_title(self):
        t = strip_date_expressions("[7월 21일(화) 14:00] 학폭위 심의", BASE)
        self.assertNotIn("7월", t)
        self.assertIn("학폭위", t)


if __name__ == "__main__":
    unittest.main(verbosity=2)
