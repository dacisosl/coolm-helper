# -*- coding: utf-8 -*-
"""쿨메신저 탐지 — 지역에 따라 프로그램 이름이 달라도 찾아야 한다.

2026-09-08 경기도 사례: 쪽지 프로그램이 SSAMBOARD.EXE / Chrome_WidgetWin_1로
떠서 이름·창클래스 힌트에 하나도 안 걸렸다. 그래서 **창 제목**으로도 찾는다.
진단 목록도 중복을 지우기 전에 12개에서 잘라 정작 메신저가 안 보였다.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import capture


class TestTitleDetection(unittest.TestCase):
    def test_messenger_titles(self):
        for t in ("쪽지 읽기", "쪽지 보내기", "메시지 관리함",
                  "[3학년 협의록 제출 안내] - 쪽지 읽기"):
            self.assertTrue(capture.looks_like_messenger_title(t), t)

    def test_other_titles(self):
        for t in ("", "   ", "제목 없음", "Chrome", "COOL-비서",
                  "카카오톡", "파일 탐색기"):
            self.assertFalse(capture.looks_like_messenger_title(t), t)

    def test_self_windows_are_not_messenger(self):
        self.assertTrue(capture._is_self("COOLMHELPER.EXE"))
        self.assertFalse(capture._is_self("SSAMBOARD.EXE"))
        self.assertFalse(capture._is_self(""))


class TestWindowListing(unittest.TestCase):
    """경기도 진단에서 실제로 나온 목록 — 중복 때문에 메신저가 잘렸다."""

    ROWS = [
        ("EXPLORER.EXE", "ThumbnailDeviceHelperWnd", ""),
        ("EXPLORER.EXE", "Shell_TrayWnd", ""),
        ("EXPLORER.EXE", "Shell_SecondaryTrayWnd", ""),
        ("EXPLORER.EXE", "CabinetWClass", "다운로드"),
        ("CHROME.EXE", "Chrome_WidgetWin_1", "새 탭"),
        ("MSEDGEWEBVIEW2.EXE", "Chrome_WidgetWin_1", ""),
        ("FONTCHECKER.EXE", "HwndWrapper[FontChecker.exe;;acf9]", ""),
        ("KAKAOTALK.EXE", "EVA_Window_Dblclk", ""),
        ("SSAMBOARD.EXE", "Chrome_WidgetWin_1", "쪽지 읽기"),
    ]

    def test_messenger_survives_dedupe(self):
        out = capture.dedupe_windows(self.ROWS)
        joined = " ".join(out)
        self.assertIn("SSAMBOARD.EXE", joined)
        self.assertIn("쪽지 읽기", joined)          # 제목까지 보여야 단서가 된다

    def test_titled_windows_come_first(self):
        out = capture.dedupe_windows(self.ROWS)
        self.assertIn("'", out[0])                  # 첫 줄은 제목이 있는 창

    def test_duplicates_merged(self):
        dup = [("EXPLORER.EXE", "Shell_TrayWnd", "")] * 10 + [
            ("SSAMBOARD.EXE", "Chrome_WidgetWin_1", "쪽지 읽기")]
        out = capture.dedupe_windows(dup, limit=5)
        self.assertEqual(len(out), 2)               # 탐색기 10개 → 한 줄
        self.assertIn("SSAMBOARD.EXE", " ".join(out))

    def test_limit_respected(self):
        many = [(f"P{i}.EXE", f"C{i}", "") for i in range(40)]
        self.assertEqual(len(capture.dedupe_windows(many, limit=7)), 7)

    def test_empty_rows_skipped(self):
        self.assertEqual(capture.dedupe_windows([("", "", "")]), [])


class TestCandidateRows(unittest.TestCase):
    """진단이 '어느 단계에서 막혔나'를 답하려면 후보를 골라 보여줘야 한다."""

    def test_picks_messenger_like_windows(self):
        rows = [("EXPLORER.EXE", "Shell_TrayWnd", ""),
                ("CHROME.EXE", "Chrome_WidgetWin_1", "새 탭"),
                ("COOLMESSENGER.EXE", "CoolMsg50SingleInstance", ""),
                ("SSAMBOARD.EXE", "Chrome_WidgetWin_1", "쪽지 읽기"),
                ("KAKAOTALK.EXE", "EVA_Window_Dblclk", "")]
        got = {r[0] for r in capture.candidate_rows(rows)}
        self.assertIn("COOLMESSENGER.EXE", got)     # 이름에 단서
        self.assertIn("SSAMBOARD.EXE", got)         # 제목에 단서
        self.assertNotIn("EXPLORER.EXE", got)
        self.assertNotIn("KAKAOTALK.EXE", got)

    def test_finds_by_class_even_without_name(self):
        """관리자 권한이면 실행파일 이름을 못 읽는다 — 창 종류로도 잡혀야."""
        rows = [("", "CoolMsg51SingleInstance", "")]
        self.assertEqual(len(capture.candidate_rows(rows)), 1)

    def test_empty_when_nothing_matches(self):
        self.assertEqual(capture.candidate_rows(
            [("NOTEPAD.EXE", "Notepad", "제목 없음")]), [])


class TestQuietOffWindows(unittest.TestCase):
    """리눅스에서도 죽지 않고 조용히 빈 결과·안내 문구를 준다."""

    def test_visible_windows_empty(self):
        if sys.platform == "win32":
            self.skipTest("윈도우에서는 실제 창을 훑는다")
        self.assertEqual(capture.visible_windows(), [])

    def test_pid_lookups_none(self):
        if sys.platform == "win32":
            self.skipTest("윈도우에서는 실제로 찾는다")
        self.assertIsNone(capture._pid_by_title())

    def test_diagnose_says_windows_only(self):
        if sys.platform == "win32":
            self.skipTest("윈도우에서는 실제 진단이 돈다")
        self.assertIn("윈도우에서만", capture.diagnose())


if __name__ == "__main__":
    unittest.main(verbosity=2)
