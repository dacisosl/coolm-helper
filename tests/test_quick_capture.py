# -*- coding: utf-8 -*-
"""⚡ 간편 등록(포스트잇 직행)과 자는 무드 조건 회귀 테스트."""
import os
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from parser.pipeline import Message, candidates_from_message
from store.event_store import EventStore


class _Owner:
    """WidgetBase 대역 — 등록·핀만 확인한다."""

    def __init__(self, tmp):
        self.base_dir = tmp
        self.store = EventStore(tmp)
        self.config = {"desk_widgets": {"notes": []}}
        self.changed = 0

    def on_events_changed(self):
        self.changed += 1


class TestQuickRegister(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.owner = _Owner(self.tmp)

    def _run(self, title, body, cands=None, matched=False):
        from ui import quick_capture
        msg = Message(-1, "교무기획부", datetime(2026, 7, 26, 9, 0), title, body)
        if cands is None:
            cands = candidates_from_message(msg, set())
        # pin_note는 실행 중인 앱 컨텍스트가 필요하므로 호출만 확인
        called = []
        orig = quick_capture._register_and_pin.__globals__
        import ui.desk_base as desk_base
        real = desk_base.pin_note
        desk_base.pin_note = lambda eid: called.append(eid) or True
        try:
            ok = quick_capture._register_and_pin(self.owner, cands, msg, matched)
        finally:
            desk_base.pin_note = real
        return ok, called

    def test_registers_and_pins(self):
        ok, pinned = self._run("7월 30일 교직원 연수",
                               "7월 30일 오후 3시에 연수가 있습니다.")
        self.assertTrue(ok)
        events = self.owner.store.all()
        self.assertEqual(len(events), 1)
        self.assertEqual(pinned, [events[0].id])          # 포스트잇으로 붙었나

    def test_body_saved_as_memo(self):
        self._run("연수 안내", "7월 30일 오후 3시 연수. 준비물은 노트북입니다.")
        self.assertIn("노트북", self.owner.store.all()[0].memo)

    def test_no_date_still_registers(self):
        ok, pinned = self._run("제목만 있는 쪽지", "날짜가 없는 본문", cands=[])
        self.assertTrue(ok)
        self.assertEqual(len(self.owner.store.all()), 1)
        self.assertEqual(len(pinned), 1)

    def test_empty_title_rejected(self):
        ok, pinned = self._run("", "", cands=[])
        self.assertFalse(ok)
        self.assertEqual(self.owner.store.all(), [])
        self.assertEqual(pinned, [])


class TestSleepMood(unittest.TestCase):
    """완료한 일은 '남은 할 일'이 아니다 — 다 끝내면 자야 한다."""

    def setUp(self):
        self.store = EventStore(tempfile.mkdtemp())

    def _left(self):
        overdue, today, _ = self.store.sections(date.today())
        return overdue, [e for e in today if not e.done]

    def test_sleeps_when_empty(self):
        overdue, left = self._left()
        self.assertFalse(overdue or left)

    def test_awake_with_open_task(self):
        self.store.add("할 일", datetime.now(), is_deadline=True)
        _, left = self._left()
        self.assertTrue(left)

    def test_sleeps_after_completing_today(self):
        ev = self.store.add("할 일", datetime.now(), is_deadline=True)
        self.store.set_done(ev.id, True)
        overdue, left = self._left()
        self.assertFalse(overdue or left)      # 예전엔 여기서 깨어 있었다

    def test_awake_with_overdue(self):
        self.store.add("지난 마감", datetime.now() - timedelta(days=2),
                       is_deadline=True)
        overdue, _ = self._left()
        self.assertTrue(overdue)


if __name__ == "__main__":
    unittest.main()
