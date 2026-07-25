# -*- coding: utf-8 -*-
"""인트로 문구 구성 + 업데이트 감지 (창을 띄우지 않는 순수 로직)."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ui.intro import CHEERS, update_lines
from version import APP_VERSION


class _FakeWidget:
    def __init__(self, config):
        self.config = config
        self.base_dir = tempfile.mkdtemp()


class TestUpdateLines(unittest.TestCase):
    def test_version_first_and_cheer_last(self):
        lines = update_lines("1.7.2", "- 첫 번째 변경\n- 두 번째 변경")
        self.assertIn("1.7.2", lines[0])
        self.assertIn(lines[-1], CHEERS)

    def test_at_most_two_note_lines(self):
        lines = update_lines("1.0.0", "\n".join(f"- 변경 {i}" for i in range(6)))
        self.assertEqual(len(lines), 4)      # 버전 + 변경 2 + 응원

    def test_empty_notes_gets_placeholder(self):
        lines = update_lines("1.0.0", "")
        self.assertEqual(len(lines), 3)
        self.assertIn("개선", lines[1])

    def test_long_line_truncated(self):
        lines = update_lines("1.0.0", "- " + "가" * 90)
        self.assertLessEqual(len(lines[1]), 42)
        self.assertTrue(lines[1].endswith("…"))

    def test_bullet_marks_stripped(self):
        self.assertEqual(update_lines("1.0.0", "• 불릿 제거")[1], "불릿 제거")


class TestVersionDetect(unittest.TestCase):
    def setUp(self):
        from ui import alerts
        self.alerts = alerts

    def test_fresh_install_is_not_update(self):
        # 기록이 없으면(최초 설치) 업데이트 인트로가 아니라 첫 실행 인트로
        self.assertFalse(self.alerts._is_new_version(_FakeWidget({})))

    def test_older_version_is_update(self):
        w = _FakeWidget({"last_seen_version": "0.0.1"})
        self.assertTrue(self.alerts._is_new_version(w))

    def test_same_version_is_not_update(self):
        w = _FakeWidget({"last_seen_version": APP_VERSION})
        self.assertFalse(self.alerts._is_new_version(w))

    def test_mark_seen_records_and_clears_notes(self):
        w = _FakeWidget({"last_seen_version": "0.0.1",
                         "pending_update_notes": "무언가"})
        self.alerts._mark_version_seen(w)
        self.assertEqual(w.config["last_seen_version"], APP_VERSION)
        self.assertNotIn("pending_update_notes", w.config)


if __name__ == "__main__":
    unittest.main()
