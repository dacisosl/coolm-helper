# -*- coding: utf-8 -*-
"""coolm_control — 관리함에서 쪽지 찾아 열기 (가짜 어댑터로 흐름 검증, 2026-09-08)."""
import os
import sys
import unittest
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import coolm_control as cc
from parser.db_reader import Message


def _msg(sender="정주은(정주은)", when=datetime(2026, 9, 4, 9, 0, 23)):
    return Message(7, sender, when, "빈칸 작성", "본문")


def _row(sender, date):
    return cc.Row(sender=sender, handle=None, _date=date)


class FakeUi:
    def __init__(self, running=True, manager=1234, opens=5678, rows=(), fail=None):
        self.running, self._manager, self._opens = running, manager, opens
        self._rows, self.fail = list(rows), fail
        self.calls, self.date_reads = [], 0

    def coolm_running(self):
        return self.running

    def manager_hwnd(self):
        self.calls.append("manager")
        return self._manager

    def open_manager(self, timeout=6.0):
        self.calls.append("open")
        return self._opens

    def ensure_received(self, hwnd):
        self.calls.append("received")

    def rows(self, hwnd):
        if self.fail == "rows":
            raise RuntimeError("boom")
        yield from self._rows

    def row_date(self, row):
        self.date_reads += 1
        return row._date

    def select(self, row):
        self.calls.append(("select", row.sender))

    def front(self, hwnd):
        self.calls.append(("front", hwnd))
        return True


ROWS = [
    _row("고선임(고선임)", "2026/09/08 12:07:50 (화)"),
    _row("정주은(정주은)", "2026/09/07 16:06:07 (월)"),      # 같은 사람, 다른 시각
    _row("정주은(정주은)", "2026/09/04 09:00:23 (금)"),      # ← 이것
    _row("남다영(남다영)", "2026/09/04 08:19:00 (금)"),
]


class TestMatching(unittest.TestCase):
    def test_date_key_and_row_match(self):
        m = _msg()
        self.assertEqual(cc.date_key(m.received), "2026/09/04 09:00:23")
        self.assertTrue(cc.row_matches("정주은(정주은)", "2026/09/04 09:00:23 (금)", m))
        self.assertTrue(cc.row_matches("정주은", "2026/09/04 09:00:23", m))   # 이름만
        self.assertFalse(cc.row_matches("정주은(정주은)", "2026/09/04 09:00:24 (금)", m))
        self.assertFalse(cc.row_matches("남다영(남다영)", "2026/09/04 09:00:23 (금)", m))

    def test_name_only(self):
        self.assertEqual(cc.name_only("김소연(해밀고)(김소연)"), "김소연")
        self.assertEqual(cc.name_only("교무기획부"), "교무기획부")
        self.assertEqual(cc.name_only(""), "")


class TestOpenMessage(unittest.TestCase):
    def test_selects_row_in_open_manager(self):
        ui = FakeUi(rows=ROWS)
        ok, why = cc.open_message(_msg(), ui)
        self.assertTrue(ok, why)
        self.assertIn(("select", "정주은(정주은)"), ui.calls)
        self.assertIn(("front", 1234), ui.calls)
        self.assertNotIn("open", ui.calls)               # 이미 열려 있어 열지 않음
        self.assertIn("received", ui.calls)

    def test_reads_dates_only_for_same_sender(self):
        ui = FakeUi(rows=ROWS)
        cc.open_message(_msg(), ui)
        self.assertEqual(ui.date_reads, 2)               # 정주은 행 둘만

    def test_opens_manager_when_missing(self):
        ui = FakeUi(manager=None, opens=5678, rows=ROWS)
        ok, _ = cc.open_message(_msg(), ui)
        self.assertTrue(ok)
        self.assertIn("open", ui.calls)
        self.assertIn(("front", 5678), ui.calls)

    def test_manager_cannot_open(self):
        ui = FakeUi(manager=None, opens=None, rows=ROWS)
        self.assertEqual(cc.open_message(_msg(), ui), (False, cc.MSG_NO_MANAGER))

    def test_coolm_not_running(self):
        ui = FakeUi(running=False, rows=ROWS)
        self.assertEqual(cc.open_message(_msg(), ui), (False, cc.MSG_NO_COOLM))

    def test_row_not_found(self):
        ui = FakeUi(rows=ROWS)
        ok, why = cc.open_message(_msg(when=datetime(2025, 1, 1, 0, 0, 0)), ui)
        self.assertFalse(ok)
        self.assertEqual(why, cc.MSG_NOT_FOUND)
        self.assertFalse(any(c[0] == "select" for c in ui.calls if isinstance(c, tuple)))

    def test_exception_is_swallowed(self):
        ui = FakeUi(rows=ROWS, fail="rows")
        ok, why = cc.open_message(_msg(), ui)
        self.assertFalse(ok)
        self.assertIn("문제가 생겼어요", why)

    def test_default_adapter_off_windows(self):
        if sys.platform == "win32":
            self.skipTest("윈도우에서는 실제 UIA를 탄다")
        self.assertEqual(cc.open_message(_msg()), (False, cc.MSG_NOT_WINDOWS))


if __name__ == "__main__":
    unittest.main(verbosity=2)
