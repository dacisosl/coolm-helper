# -*- coding: utf-8 -*-
"""db_reader의 '안읽음 전부 + 읽은 것 N개' 로직 검증 (가짜 DB 사용)."""
import os
import shutil
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from parser.db_reader import DbReader


def make_fake_db(memo_dir: str, unread: int, read: int) -> None:
    """최신 쪽지일수록 늦은 시각. 안읽음이 읽음보다 최신이라고 가정."""
    con = sqlite3.connect(os.path.join(memo_dir, "test.udb"))
    con.execute(
        "CREATE TABLE tbl_recv (MessageKey INTEGER PRIMARY KEY, Sender TEXT,"
        " ReceiveDate DATE, Title TEXT, MessageText TEXT, IsUnRead INTEGER,"
        " DeletedDate DATE)")
    key = 0
    for i in range(read):           # 오래된 읽은 쪽지들
        key += 1
        con.execute("INSERT INTO tbl_recv VALUES (?,?,?,?,?,0,NULL)",
                    (key, "발신자", f"2026/07/10 {i % 24:02d}:{key % 60:02d}:00 (금)",
                     f"읽은쪽지{key}", "본문"))
    for i in range(unread):         # 최신 안읽은 쪽지들
        key += 1
        con.execute("INSERT INTO tbl_recv VALUES (?,?,?,?,?,1,NULL)",
                    (key, "발신자", f"2026/07/18 {i % 24:02d}:{key % 60:02d}:00 (토)",
                     f"안읽은쪽지{key}", "본문"))
    con.commit()
    con.close()


class TestUnreadAllPlusReadN(unittest.TestCase):
    def _run(self, unread: int, read: int, limit: int):
        tmp = tempfile.mkdtemp()
        try:
            make_fake_db(tmp, unread=unread, read=read)
            with DbReader(tmp) as r:
                return r.latest_messages(limit)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_unread_pile_fully_included(self):
        """안읽음 15개가 쌓여도 전부 + 읽은 것 10개."""
        msgs = self._run(unread=15, read=30, limit=10)
        self.assertEqual(len(msgs), 25)
        self.assertEqual(sum(1 for m in msgs if m.is_unread), 15)

    def test_normal_day(self):
        """안읽음 없으면 기존처럼 최근 N개."""
        msgs = self._run(unread=0, read=30, limit=10)
        self.assertEqual(len(msgs), 10)

    def test_sorted_newest_first(self):
        msgs = self._run(unread=5, read=10, limit=10)
        received = [m.received for m in msgs]
        self.assertEqual(received, sorted(received, reverse=True))
        self.assertTrue(msgs[0].is_unread)   # 최신은 안읽음


if __name__ == "__main__":
    unittest.main(verbosity=2)
