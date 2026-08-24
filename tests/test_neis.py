# -*- coding: utf-8 -*-
"""나이스 학사일정 연동 — 응답 파싱·기간 병합·중복 방지 (2026-08-24).

실제 서버는 부르지 않는다. urlopen을 갈아끼워 저장해 둔 응답으로만 검증한다.
(개발 환경에서 open.neis.go.kr이 막혀 있어도 회귀 검증이 되도록.)
"""
import io
import json
import os
import sys
import unittest
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import neis


def _ok(path, rows):
    """정상 응답 봉투 — 나이스 실제 형식과 같은 모양."""
    return {path: [
        {"head": [{"list_total_count": len(rows)},
                  {"RESULT": {"CODE": "INFO-000", "MESSAGE": "정상 처리되었습니다."}}]},
        {"row": rows},
    ]}


def _err(code, msg):
    return {"RESULT": {"CODE": code, "MESSAGE": msg}}


class _FakeUrlopen:
    """urlopen 대역 — 마지막 URL을 기억하고 준비된 JSON을 돌려준다."""

    def __init__(self, payload):
        self.payload = payload
        self.url = ""

    def __call__(self, req, timeout=None):
        self.url = req.full_url if hasattr(req, "full_url") else str(req)
        body = json.dumps(self.payload, ensure_ascii=False).encode("utf-8")
        return io.BytesIO(body)          # with 문에서 쓰이려면 컨텍스트 지원 필요

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class _Patch:
    """neis.urllib.request.urlopen 임시 교체."""

    def __init__(self, payload):
        self.fake = _FakeUrlopen(payload)

    def __enter__(self):
        self._real = neis.urllib.request.urlopen
        neis.urllib.request.urlopen = self.fake
        return self.fake

    def __exit__(self, *exc):
        neis.urllib.request.urlopen = self._real
        return False


SCHOOL = neis.School(name="가온초등학교", code="7000000", office="B10",
                     office_name="서울특별시교육청", kind="초등학교")


class TestSchoolSearch(unittest.TestCase):
    ROWS = [{
        "ATPT_OFCDC_SC_CODE": "B10", "ATPT_OFCDC_SC_NM": "서울특별시교육청",
        "SD_SCHUL_CODE": "7000000", "SCHUL_NM": "가온초등학교",
        "SCHUL_KND_SC_NM": "초등학교", "ORG_RDNMA": "서울특별시 ○○구 ○○로 1",
    }]

    def test_parses_rows(self):
        with _Patch(_ok("schoolInfo", self.ROWS)):
            schools = neis.search_schools("가온초")
        self.assertEqual(len(schools), 1)
        s = schools[0]
        self.assertEqual((s.name, s.code, s.office), ("가온초등학교", "7000000", "B10"))
        self.assertEqual(s.label(), "가온초등학교 (초등학교)")

    def test_sends_name_and_key(self):
        with _Patch(_ok("schoolInfo", self.ROWS)) as fake:
            neis.search_schools("가온초", {"neis_api_key": "TESTKEY"})
        self.assertIn("SCHUL_NM=", fake.url)
        self.assertIn("KEY=TESTKEY", fake.url)

    def test_short_name_rejected(self):
        with self.assertRaises(neis.NeisError):
            neis.search_schools("가")

    def test_no_data_is_empty_not_error(self):
        with _Patch(_err("INFO-200", "해당하는 데이터가 없습니다.")):
            self.assertEqual(neis.search_schools("없는학교이름"), [])

    def test_bad_key_message(self):
        with _Patch(_err("INFO-300", "인증키가 유효하지 않습니다.")):
            with self.assertRaises(neis.NeisError) as cm:
                neis.search_schools("가온초")
        self.assertIn("인증키", str(cm.exception))

    def test_rows_without_code_skipped(self):
        with _Patch(_ok("schoolInfo", [{"SCHUL_NM": "코드없는학교"}])):
            self.assertEqual(neis.search_schools("코드없는"), [])


def _row(ymd, name, memo=""):
    return {"AA_YMD": ymd, "EVENT_NM": name, "EVENT_CNTNT": memo}


class TestSchedule(unittest.TestCase):
    def _fetch(self, rows, **kw):
        with _Patch(_ok("SchoolSchedule", rows)) as fake:
            out = neis.fetch_schedule(SCHOOL, date(2026, 9, 1),
                                      date(2026, 9, 30), **kw)
            self.url = fake.url          # 호출 뒤에 기록해야 값이 들어 있다
        return out

    def test_single_day(self):
        evs = self._fetch([_row("20260903", "학부모 상담주간 시작")])
        self.assertEqual(len(evs), 1)
        self.assertEqual(evs[0].start, date(2026, 9, 3))
        self.assertIsNone(evs[0].end)
        self.assertEqual(evs[0].when_text(), "9/3")

    def test_consecutive_days_merge_into_range(self):
        # 나이스는 3일짜리 행사를 하루 한 줄로 준다 → 기간 한 건으로 합쳐야 한다
        evs = self._fetch([_row("20260907", "수련회"), _row("20260908", "수련회"),
                           _row("20260909", "수련회")])
        self.assertEqual(len(evs), 1)
        self.assertEqual((evs[0].start, evs[0].end),
                         (date(2026, 9, 7), date(2026, 9, 9)))
        self.assertEqual(evs[0].when_text(), "9/7 ~ 9/9")

    def test_gap_breaks_the_range(self):
        evs = self._fetch([_row("20260907", "체육대회"), _row("20260909", "체육대회")])
        self.assertEqual(len(evs), 2)

    def test_different_names_not_merged(self):
        evs = self._fetch([_row("20260907", "수련회"), _row("20260908", "체험학습")])
        self.assertEqual({e.title for e in evs}, {"수련회", "체험학습"})

    def test_holidays_skipped_by_default(self):
        evs = self._fetch([_row("20260905", "토요휴업일"), _row("20260907", "개학식")])
        self.assertEqual([e.title for e in evs], ["개학식"])

    def test_holidays_kept_when_asked(self):
        evs = self._fetch([_row("20260905", "토요휴업일")], skip_holidays=False)
        self.assertEqual([e.title for e in evs], ["토요휴업일"])

    def test_memo_carried(self):
        evs = self._fetch([_row("20260907", "수련회", "1박 2일, 준비물 안내 참고")])
        self.assertIn("준비물", evs[0].memo)

    def test_sends_school_and_period(self):
        self._fetch([_row("20260903", "개학식")])
        for part in ("SD_SCHUL_CODE=7000000", "ATPT_OFCDC_SC_CODE=B10",
                     "AA_FROM_YMD=20260901", "AA_TO_YMD=20260930"):
            self.assertIn(part, self.url)

    def test_bad_date_skipped(self):
        evs = self._fetch([_row("2026-09-03", "잘못된 날짜"), _row("20260903", "개학식")])
        self.assertEqual([e.title for e in evs], ["개학식"])

    def test_sorted_by_date(self):
        evs = self._fetch([_row("20260920", "나중"), _row("20260902", "먼저")])
        self.assertEqual([e.title for e in evs], ["먼저", "나중"])


class TestDuplicateRef(unittest.TestCase):
    """같은 행사는 같은 표식 — 두 번 등록되지 않게."""

    def test_ref_is_stable(self):
        a = neis.event_ref(SCHOOL, date(2026, 9, 7), "수련회")
        b = neis.event_ref(SCHOOL, date(2026, 9, 7), "수련회")
        self.assertEqual(a, b)
        self.assertIn("7000000", a)

    def test_ref_differs_by_date_and_title(self):
        base = neis.event_ref(SCHOOL, date(2026, 9, 7), "수련회")
        self.assertNotEqual(base, neis.event_ref(SCHOOL, date(2026, 9, 8), "수련회"))
        self.assertNotEqual(base, neis.event_ref(SCHOOL, date(2026, 9, 7), "체육대회"))

    def test_merged_range_uses_start_date(self):
        rows = [_row("20260907", "수련회"), _row("20260908", "수련회")]
        evs = neis.merge_rows(rows, SCHOOL)
        self.assertEqual(evs[0].ref,
                         neis.event_ref(SCHOOL, date(2026, 9, 7), "수련회"))


class TestSchoolConf(unittest.TestCase):
    def test_round_trip(self):
        again = neis.School.from_conf(SCHOOL.to_conf())
        self.assertEqual(again, SCHOOL)

    def test_broken_conf_is_none(self):
        for bad in (None, {}, {"name": "이름만"}, "문자열", {"code": "1"}):
            self.assertIsNone(neis.School.from_conf(bad))


class TestApiKey(unittest.TestCase):
    def test_user_key_wins(self):
        self.assertEqual(neis.api_key({"neis_api_key": " MINE "}), "MINE")

    def test_falls_back_to_embedded(self):
        real = neis.embedded_key
        neis.embedded_key = lambda: "BUILTIN"
        try:
            self.assertEqual(neis.api_key({}), "BUILTIN")
            self.assertEqual(neis.api_key(None), "BUILTIN")
        finally:
            neis.embedded_key = real

    def test_no_key_is_empty(self):
        real = neis.embedded_key
        neis.embedded_key = lambda: ""
        try:
            self.assertEqual(neis.api_key({}), "")
        finally:
            neis.embedded_key = real

    def test_keyless_request_asks_fewer_rows(self):
        # 키가 없으면 API가 5건만 주므로 pSize도 그에 맞춘다
        real = neis.embedded_key
        neis.embedded_key = lambda: ""
        try:
            with _Patch(_ok("schoolInfo", [])) as fake:
                neis.search_schools("가온초", {})
            self.assertIn(f"pSize={neis.KEYLESS_ROWS}", fake.url)
            self.assertNotIn("KEY=", fake.url)
        finally:
            neis.embedded_key = real


class TestRangePicker(unittest.TestCase):
    """기간 선택지 → 실제 날짜 (창을 띄우지 않고 순수 함수로 검증)."""

    def setUp(self):
        from ui.neis_dialog import range_dates
        self.f = range_dates
        self.today = date(2026, 9, 15)

    def test_three_months(self):
        s, e = self.f("앞으로 3개월", self.today)
        self.assertEqual(s, self.today)
        self.assertEqual((e - s).days, 90)

    def test_this_month(self):
        s, e = self.f("이번 달", self.today)
        self.assertEqual((s, e), (date(2026, 9, 1), date(2026, 9, 30)))

    def test_this_year(self):
        s, e = self.f("올해 전체", self.today)
        self.assertEqual((s, e), (date(2026, 1, 1), date(2026, 12, 31)))

    def test_one_year(self):
        s, e = self.f("앞으로 1년", self.today)
        self.assertEqual((e - s).days, 365)


class TestNoSecretInRepo(unittest.TestCase):
    """공개 저장소에 나이스 키가 섞여 들어가지 않도록 지키는 안전장치."""

    def test_key_file_is_gitignored(self):
        root = os.path.join(os.path.dirname(__file__), "..")
        ignored = open(os.path.join(root, ".gitignore"), encoding="utf-8").read()
        self.assertIn("assets/neis.key", ignored)

    def test_source_has_no_hardcoded_key(self):
        src = open(os.path.join(os.path.dirname(__file__), "..", "neis.py"),
                   encoding="utf-8").read()
        import re
        self.assertIsNone(re.search(r"[0-9a-f]{32}", src),
                          "neis.py에 32자리 키처럼 보이는 문자열이 있습니다")


if __name__ == "__main__":
    unittest.main()
