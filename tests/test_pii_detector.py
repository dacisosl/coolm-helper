# -*- coding: utf-8 -*-
import sys, os, unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from parser.pii_detector import detect, mask


class TestPhone(unittest.TestCase):
    def test_mobile(self):
        self.assertEqual(mask("연락처 010-1234-5678 입니다"), "연락처 ○○○ 입니다")

    def test_area_code(self):
        spans = detect("교무실 031)123-4567")
        self.assertEqual(spans[0].kind, "phone")

    def test_no_false_positive_on_date(self):
        self.assertEqual(detect("2026-07-21 회의"), [])


class TestRrn(unittest.TestCase):
    def test_full(self):
        spans = detect("주민번호 990101-1234567")
        self.assertEqual(spans[0].kind, "rrn")

    def test_partially_masked(self):
        spans = detect("990101-1******")
        self.assertEqual(spans[0].kind, "rrn")


class TestHonorific(unittest.TestCase):
    def test_student(self):
        self.assertEqual(mask("김철수 학생 상담"), "○○○ 학생 상담")

    def test_nim(self):
        self.assertEqual(mask("박영수님께 전달"), "○○○님께 전달")

    def test_stopword_not_masked(self):
        self.assertEqual(mask("선생님들께 안내드립니다"), "선생님들께 안내드립니다")
        self.assertEqual(mask("학부모님 대상 연수"), "학부모님 대상 연수")


class TestRoster(unittest.TestCase):
    ROSTER = {"김철수", "이영희"}

    def test_roster_hit(self):
        out = mask("김철수, 이영희 참석", roster=self.ROSTER)
        self.assertEqual(out, "○○○, ○○○ 참석")

    def test_roster_and_honorific_overlap(self):
        out = mask("김철수 학생 학폭위", roster=self.ROSTER)
        self.assertEqual(out, "○○○ 학생 학폭위")


class TestCombined(unittest.TestCase):
    def test_example_from_prd(self):
        text = ("3학년 김철수 학생 학폭위 심의가 7월 21일(화) 14시에 열립니다. "
                "담당: 이영희 선생님(010-1234-5678)")
        out = mask(text, roster={"김철수"})
        self.assertNotIn("김철수", out)
        self.assertNotIn("이영희", out)
        self.assertNotIn("010-1234-5678", out)
        self.assertIn("학폭위", out)
        self.assertIn("7월 21일", out)  # 날짜는 남는다


if __name__ == "__main__":
    unittest.main(verbosity=2)
