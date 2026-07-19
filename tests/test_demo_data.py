# -*- coding: utf-8 -*-
import sys, os, unittest
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from parser import demo_data
from parser.pipeline import candidates_from_message


class TestDemoData(unittest.TestCase):
    NOW = datetime(2026, 7, 19, 9, 0)

    def test_messages_generated(self):
        msgs = demo_data.demo_messages(self.NOW)
        self.assertGreaterEqual(len(msgs), 8)
        for m in msgs:
            self.assertTrue(m.title and m.sender)
            self.assertLess(m.received, self.NOW)

    def test_candidates_extracted(self):
        roster = demo_data.demo_roster()
        msgs = demo_data.demo_messages(self.NOW)
        all_cands = [c for m in msgs for c in candidates_from_message(m, roster)]
        # 일정이 있는 쪽지 7건 이상에서 후보가 나와야 한다
        self.assertGreaterEqual(len(all_cands), 7)
        # 미래 일정만
        for c in all_cands:
            self.assertGreaterEqual(c.start.date(), self.NOW.date())

    def test_pii_detected_in_demo(self):
        roster = demo_data.demo_roster()
        msgs = demo_data.demo_messages(self.NOW)
        polri = [c for m in msgs for c in candidates_from_message(m, roster)]
        kinds = {s.kind for c in polri for s in c.body_spans}
        self.assertIn("phone", kinds)     # 010-1234-5678 (가짜)
        self.assertIn("roster", kinds)    # 김민준 등 데모 명단

    def test_no_event_message_exists(self):
        roster = demo_data.demo_roster()
        msgs = demo_data.demo_messages(self.NOW)
        no_event = [m for m in msgs if not candidates_from_message(m, roster)]
        self.assertGreaterEqual(len(no_event), 1)   # '감사 인사' 쪽지


if __name__ == "__main__":
    unittest.main(verbosity=2)
