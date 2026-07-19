# -*- coding: utf-8 -*-
"""간편 등록의 DB 매칭 로직 검증."""
import os
import sys
import unittest
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from parser.db_reader import Message
from parser.pipeline import match_captured


def msg(key, title, body):
    return Message(key=key, sender="발신자", received=datetime(2026, 7, 16),
                   title=title, body=body)


class TestMatchCaptured(unittest.TestCase):
    MESSAGES = [
        msg(1, "[7월 21일 일정 안내]", "1교시 정상수업\n3교시 봉사활동입니다. "
            "각별히 신경써 주세요. 여름방학식 안내도 포함되어 있습니다."),
        msg(2, "성적 입력 안내", "성적 입력을 7월 20일까지 완료해 주세요. "
            "늦지 않게 부탁드립니다."),
    ]

    def test_body_prefix_match(self):
        m = match_captured(self.MESSAGES, "",
                           "1교시 정상수업 3교시 봉사활동입니다. 각별히 신경써 "
                           "주세요. 여름방학식 안내도 포함")
        self.assertEqual(m.key, 1)

    def test_whitespace_insensitive(self):
        m = match_captured(self.MESSAGES, "",
                           "성적입력을 7월20일까지 완료해주세요. 늦지않게 부탁드립니다.")
        self.assertEqual(m.key, 2)

    def test_short_body_not_false_matched(self):
        """본문이 짧은 쪽지가 아무 텍스트와나 매칭되면 안 된다 (v0.8.0 버그 재발 방지)."""
        with_short = self.MESSAGES + [msg(9, "", "")]
        m = match_captured(with_short, "",
                           "다음 주 화요일 14:00 교직원 회의가 있습니다.")
        self.assertIsNone(m)

    def test_title_fallback(self):
        m = match_captured(self.MESSAGES, "[7월 21일 일정 안내]", "짧음")
        self.assertEqual(m.key, 1)

    def test_no_match(self):
        self.assertIsNone(match_captured(
            self.MESSAGES, "다른 제목", "완전히 다른 내용의 글입니다. "
            "이 텍스트는 어떤 쪽지와도 일치하지 않습니다."))


if __name__ == "__main__":
    unittest.main(verbosity=2)
