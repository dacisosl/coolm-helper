# -*- coding: utf-8 -*-
"""⚡ 간편 등록: 최근 300통 대조 + 못 찾으면 쪽지함 전체 (2026-10-10 사용자 결정).

오래된 쪽지도 쪽지함과 연결돼야 받은 시각(지문)이 남고, '제출'이 회신 창을 찾는다.
"""
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from parser import pipeline


def _make_db(memo_dir: str, n: int) -> None:
    """key가 클수록 최신. 본문은 쪽지마다 다르고 충분히 길다."""
    con = sqlite3.connect(os.path.join(memo_dir, "test.udb"))
    con.execute(
        "CREATE TABLE tbl_recv (MessageKey INTEGER PRIMARY KEY, Sender TEXT,"
        " ReceiveDate DATE, Title TEXT, MessageText TEXT, IsUnRead INTEGER,"
        " DeletedDate DATE)")
    base = datetime(2026, 1, 5, 8, 0, 0)
    for k in range(1, n + 1):
        d = base + timedelta(hours=7 * k, seconds=k % 60)
        con.execute("INSERT INTO tbl_recv VALUES (?,?,?,?,?,0,NULL)",
                    (k, f"선생님{k}", d.strftime("%Y/%m/%d %H:%M:%S (월)"),
                     f"안내 제목 {k}번",
                     f"{k}번 쪽지 본문입니다. 10월 {k % 28 + 1}일까지 제출 부탁드립니다."))
    con.commit()
    con.close()


class TestQuickMatchWindow(unittest.TestCase):
    N = 320                                   # 최근 300통보다 20통 더

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.memo = os.path.join(self.tmp, "memo")
        os.makedirs(self.memo)
        _make_db(self.memo, self.N)
        with open(os.path.join(self.tmp, "config.json"), "w", encoding="utf-8") as f:
            json.dump({"memo_dir": self.memo}, f)
        pipeline._quick_cache.clear()

    def tearDown(self):
        pipeline._quick_cache.clear()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _body(self, k):
        return f"{k}번 쪽지 본문입니다. 10월 {k % 28 + 1}일까지 제출 부탁드립니다."

    def test_window_is_300(self):
        self.assertEqual(pipeline.QUICK_MATCH_COUNT, 300)

    def test_recent_message_matched_without_whole_db(self):
        real = pipeline._match_whole_db
        pipeline._match_whole_db = lambda *a, **k: (_ for _ in ()).throw(
            AssertionError("최근 300통 안이면 전체 조회를 하지 않아야 한다"))
        try:
            _c, msg, matched = pipeline.quick_candidates(self.tmp, "", self._body(30))
        finally:
            pipeline._match_whole_db = real
        self.assertTrue(matched)
        self.assertEqual(msg.key, 30)            # 320-30 = 290번째로 최신 → 300 안

    def test_old_message_found_in_whole_db(self):
        _c, msg, matched = pipeline.quick_candidates(self.tmp, "", self._body(3))
        self.assertTrue(matched)                 # 300통 밖이지만 전체에서 찾았다
        self.assertEqual(msg.key, 3)
        self.assertEqual(msg.sender, "선생님3")
        fp = pipeline.msg_fingerprint(msg)       # → '제출'이 회신 창을 찾을 지문
        self.assertTrue(fp["msg_received"].startswith("2026/01/06 "))

    def test_quoting_reply_does_not_steal_old_original(self):
        """'283번 …'은 '3번 …'을 글자로 포함한다(쿨메신저 회신 인용과 같은 꼴).

        최근 300통엔 포함 일치(283)만 있고, 정확한 원본(3)은 300통 밖이다 →
        전체에서 정확 일치를 찾아 원본을 고른다.
        """
        _c, msg, matched = pipeline.quick_candidates(self.tmp, "", self._body(3))
        self.assertTrue(matched)
        self.assertEqual(msg.key, 3)

    def test_exact_beats_containment_in_same_list(self):
        from parser.db_reader import Message
        orig = Message(1, "가", datetime(2026, 9, 1), "원문", "회의는 10월 5일 오후 3시 교무실에서 합니다")
        quote = Message(2, "나", datetime(2026, 9, 2), "RE",
                        "네 알겠습니다 가님이 보낸글 >> 회의는 10월 5일 오후 3시 교무실에서 합니다")
        m, exact = pipeline.match_captured_ex([quote, orig], "", orig.body)
        self.assertEqual((m.key, exact), (1, True))

    def test_unknown_text_still_unmatched(self):
        _c, msg, matched = pipeline.quick_candidates(
            self.tmp, "", "어느 쪽지에도 없는 완전히 다른 글자들로 된 긴 본문입니다")
        self.assertFalse(matched)
        self.assertEqual(msg.key, -1)

    def test_too_short_text_skips_whole_db(self):
        self.assertFalse(pipeline._match_possible("짧음", "본문"))
        self.assertIsNone(pipeline._match_whole_db({"memo_dir": self.memo},
                                                   "짧음", "본문", set()))


if __name__ == "__main__":
    unittest.main(verbosity=2)
