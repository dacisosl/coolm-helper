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


class FakePerson:
    """조직도 항목 대역."""

    def __init__(self, label, offscreen=False):
        self.label, self.offscreen = label, offscreen


class FakeTreeUi:
    """compose_to용 가짜 어댑터. steps에 적은 방법에서만 창이 뜬다."""

    def __init__(self, people=(), running=True, main=99, opens_on=None,
                 fail_steps=()):
        self.people = list(people)
        self.running, self._main = running, main
        self.opens_on = opens_on            # 이 방법에서 새 창이 뜬다
        self.fail_steps = set(fail_steps)   # 이 방법은 예외를 던진다
        self.calls, self._opened = [], False

    def coolm_running(self):
        return self.running

    def main_hwnd(self):
        return self._main

    def front(self, hwnd):
        self.calls.append(("front", hwnd))
        return True

    def search_person(self, hwnd, name):
        self.calls.append(("search", name))

    def find_person(self, hwnd, name):
        for p in self.people:
            if f"({name})" in p.label:
                return p
        for p in self.people:
            if name in p.label:
                return p
        return None

    def select_person(self, el):
        self.calls.append(("select", el.label))

    def windows(self):
        return [self._main, 100] if self._opened else [self._main]

    def _step(self, kind):
        self.calls.append(kind)
        if kind in self.fail_steps:
            raise RuntimeError(f"{kind} 안 통함")
        if self.opens_on == kind:
            self._opened = True

    def do_default_action(self, el, hwnd):
        self._step("default")

    def press_enter(self, el, hwnd):
        self._step("enter")

    def double_click(self, el, hwnd):
        self._step("dblclick")

    def new_window_after(self, before, timeout=4.0):
        for h in self.windows():
            if h not in before:
                return h
        return None


PEOPLE = [FakePerson("(고선임)연구부/영어/8525"),
          FakePerson("(정주은)3-1/수학/8531"),
          FakePerson("정주은 관련 그룹")]


class TestComposeTo(unittest.TestCase):
    """'제출' = 그 사람에게 쪽지 쓰기 (2026-09-08 사용자 재설계)."""

    def test_opens_on_first_method(self):
        ui = FakeTreeUi(PEOPLE, opens_on="default")
        state, why = cc.compose_to("정주은(정주은)", ui)
        self.assertEqual((state, why), ("opened", ""))
        self.assertIn(("select", "(정주은)3-1/수학/8531"), ui.calls)
        self.assertIn(("search", "정주은"), ui.calls)
        self.assertNotIn("enter", ui.calls)        # 첫 방법에서 됐으니 그만

    def test_falls_back_through_methods(self):
        ui = FakeTreeUi(PEOPLE, opens_on="dblclick", fail_steps=("default",))
        state, _ = cc.compose_to("정주은", ui)
        self.assertEqual(state, "opened")
        self.assertEqual([c for c in ui.calls if isinstance(c, str)],
                         ["default", "enter", "dblclick"])

    def test_selected_when_no_window_opens(self):
        ui = FakeTreeUi(PEOPLE)                    # 어느 방법으로도 안 뜸
        state, why = cc.compose_to("정주은", ui)
        self.assertEqual(state, "selected")
        self.assertIn("더블클릭", why)
        self.assertIn("정주은", why)

    def test_person_not_in_tree(self):
        ui = FakeTreeUi(PEOPLE)
        state, why = cc.compose_to("없는사람", ui)
        self.assertEqual(state, "failed")
        self.assertIn("찾지 못했어요", why)

    def test_exact_match_wins(self):
        """'(정주은)…' 항목이 '정주은 관련 그룹'보다 먼저."""
        ui = FakeTreeUi(list(reversed(PEOPLE)), opens_on="default")
        cc.compose_to("정주은", ui)
        self.assertIn(("select", "(정주은)3-1/수학/8531"), ui.calls)

    def test_no_name(self):
        self.assertEqual(cc.compose_to("", FakeTreeUi(PEOPLE)),
                         ("failed", cc.MSG_NO_NAME))

    def test_coolm_off(self):
        state, why = cc.compose_to("정주은", FakeTreeUi(PEOPLE, running=False))
        self.assertEqual((state, why), ("failed", cc.MSG_NO_COOLM))

    def test_exception_swallowed(self):
        class Boom(FakeTreeUi):
            def find_person(self, hwnd, name):
                raise RuntimeError("boom")

        state, why = cc.compose_to("정주은", Boom(PEOPLE))
        self.assertEqual(state, "failed")
        self.assertIn("문제가 생겼어요", why)

    def test_default_adapter_off_windows(self):
        if sys.platform == "win32":
            self.skipTest("윈도우에서는 실제 UIA를 탄다")
        self.assertEqual(cc.compose_to("정주은"),
                         ("failed", cc.MSG_NOT_WINDOWS))


if __name__ == "__main__":
    unittest.main(verbosity=2)
