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

    def test_missing_record_counts_as_update(self):
        # 이 기능이 없던 옛 버전에서 올라온 사용자 — 기록이 없어도 인사해야 한다
        # (v1.7.2에서 인사가 안 뜨던 버그)
        self.assertTrue(self.alerts._is_new_version(_FakeWidget({})))

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

    def test_marked_version_stops_repeat(self):
        # 인사한 뒤에는 같은 버전에서 다시 뜨지 않는다
        w = _FakeWidget({})
        self.alerts._mark_version_seen(w)
        self.assertFalse(self.alerts._is_new_version(w))

    def test_bundled_notes_read(self):
        import os
        d = tempfile.mkdtemp()
        with open(os.path.join(d, "release_notes.txt"), "w",
                  encoding="utf-8") as f:
            f.write("제목 줄\n\n- 변경 하나\n- 변경 둘\n")
        body = self.alerts._bundled_notes(d)
        self.assertIn("변경 하나", body)
        self.assertNotIn("제목 줄", body)
        self.assertEqual(self.alerts._bundled_notes(tempfile.mkdtemp()), "")


if __name__ == "__main__":
    unittest.main()
