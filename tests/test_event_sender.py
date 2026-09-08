# -*- coding: utf-8 -*-
"""일정이 '보낸 사람'을 기억한다 — 포스트잇 '제출'의 재료 (2026-09-08)."""
import json
import os
import shutil
import sys
import tempfile
import unittest
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from parser.db_reader import Message
from parser.pipeline import SCREEN_SENDER, real_sender
from store.event_store import Event, EventStore


class TestSenderField(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.store = EventStore(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_default_is_empty(self):
        ev = self.store.add("일정", datetime(2026, 9, 8, 9, 0))
        self.assertEqual(ev.sender, "")

    def test_saved_and_reloaded(self):
        ev = self.store.add("일정", datetime(2026, 9, 8, 9, 0),
                            sender="정주은(정주은)")
        again = [e for e in EventStore(self.tmp).all() if e.id == ev.id][0]
        self.assertEqual(again.sender, "정주은(정주은)")

    def test_update_remembers_name(self):
        ev = self.store.add("일정", datetime(2026, 9, 8, 9, 0))
        self.store.update(ev.id, sender="남다영")
        again = [e for e in EventStore(self.tmp).all() if e.id == ev.id][0]
        self.assertEqual(again.sender, "남다영")

    def test_old_json_without_sender_still_loads(self):
        """sender 키가 없는 예전 events.json도 그대로 열려야 한다."""
        path = os.path.join(self.tmp, "store", "events.json")
        old = [{"title": "옛 일정", "start": "2026-01-02T09:00:00",
                "end": None, "all_day": True, "is_deadline": False,
                "done": False, "priority": "보통", "memo": "메모",
                "demo": False, "order": 0, "source_ref": "5|x",
                "google_id": None, "created": "2026-01-01T00:00:00",
                "id": "abc123"}]
        with open(path, "w", encoding="utf-8") as f:
            json.dump(old, f, ensure_ascii=False)
        events = EventStore(self.tmp).all()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].title, "옛 일정")
        self.assertEqual(events[0].sender, "")        # 기본값으로 채워진다


class TestRealSender(unittest.TestCase):
    """화면 캡처의 가짜 발신자는 저장하지 않는다."""

    def _msg(self, sender):
        return Message(1, sender, datetime(2026, 9, 8, 9, 0), "제목", "본문")

    def test_real_name_kept(self):
        self.assertEqual(real_sender(self._msg("정주은(정주은)")), "정주은(정주은)")

    def test_placeholder_dropped(self):
        self.assertEqual(real_sender(self._msg(SCREEN_SENDER)), "")
        self.assertEqual(real_sender(self._msg("(어디선가)")), "")

    def test_empty_dropped(self):
        self.assertEqual(real_sender(self._msg("")), "")
        self.assertEqual(real_sender(self._msg("   ")), "")


if __name__ == "__main__":
    unittest.main(verbosity=2)
