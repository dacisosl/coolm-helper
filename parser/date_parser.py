# -*- coding: utf-8 -*-
"""한국어 날짜/시간 표현 파서 (정규식 기반, 오프라인).

기준일(base)은 오늘이 아니라 쪽지의 ReceiveDate다 —
지난주에 받은 쪽지의 "내일"은 지난주 기준이어야 하므로.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

WEEKDAYS = {"월": 0, "화": 1, "수": 2, "목": 3, "금": 4, "토": 5, "일": 6}

# ── 정규식 패턴 ──────────────────────────────────────────────
# 절대 날짜: 7월 21일 / 7/21 / 2026-07-21 / 7.21(화)
DATE_ABS = re.compile(
    r"(?:(?P<y>20\d{2})\s*[년./-]\s*)?"
    r"(?P<m>1[0-2]|0?[1-9])\s*(?P<sep>[월./-])\s*"
    r"(?P<d>3[01]|[12]\d|0?[1-9])\s*(?P<il>일)?"
    r"\s*(?:\(\s*(?P<wd>[월화수목금토일])\s*\))?"
)
# 상대 날짜: 오늘/내일/모레/글피, (이번|다음)주 X요일
DATE_REL_DAY = re.compile(r"오늘|내일|모레|글피")
DATE_REL_WEEK = re.compile(
    r"(?P<week>이번\s*주|금주|다음\s*주|차주)\s*(?P<wd>[월화수목금토일])요일")
# 시간: 14:00 / 오후 2시 / 2시 30분 / 14시 / 2시반
# ':' 형식은 분까지 있어야 인정한다 ('1:' 같은 조각의 오인 방지)
TIME = re.compile(
    r"(?:(?P<ampm>오전|오후|낮|저녁|밤|아침)\s*)?"
    r"(?:(?P<h1>2[0-3]|1\d|0?\d):(?P<min1>[0-5]\d)(?!\d)"
    r"|(?P<h2>2[0-3]|1\d|0?\d)\s*시\s*(?:(?P<min2>[0-5]?\d)\s*분|(?P<half>반))?)"
)
# 기한: '~7/21까지', '마감', '제출'
DEADLINE_HINT = re.compile(r"까지|마감|기한|제출|신청\s*마감")
# 기간 연결자: 날짜 ~ 날짜 / 날짜부터 날짜까지
RANGE_CONNECT = re.compile(r"^\s*(?:~|-|부터|에서)\s*$")

_FULLWIDTH = str.maketrans("０１２３４５６７８９：／．（）～", "0123456789:/.()~")


def normalize(text: str) -> str:
    """전각→반각, 널문자 제거. (길이 보존 — span 위치가 유지된다)"""
    return text.translate(_FULLWIDTH).replace("\x00", " ")


@dataclass
class ParsedEvent:
    start: datetime
    end: datetime | None = None
    all_day: bool = True
    is_deadline: bool = False
    source_text: str = ""          # 매칭된 원문 조각 (로컬 표시용)
    spans: list[tuple[int, int]] = field(default_factory=list)  # 제목 정리용


# ── 내부 헬퍼 ────────────────────────────────────────────────

def _resolve_year(month: int, day: int, base: datetime) -> date | None:
    """연도 생략 시: 기준일에서 30일 이상 과거면 이듬해로 해석."""
    for year in (base.year, base.year + 1):
        try:
            d = date(year, month, day)
        except ValueError:
            return None
        if d >= base.date() - timedelta(days=30):
            return d
    return d  # 둘 다 과거면 마지막 후보


def _resolve_abs(m: re.Match, base: datetime) -> date | None:
    month, day = int(m.group("m")), int(m.group("d"))
    if m.group("y"):
        try:
            return date(int(m.group("y")), month, day)
        except ValueError:
            return None
    # '.'/'-' 구분자의 연도 없는 날짜는 요일/일 표기가 있어야 인정
    # ('2. 3' 같은 목록 번호, '1-2교시' 같은 표현의 오인 방지)
    if m.group("sep") in ".-" and not (m.group("wd") or m.group("il")):
        return None
    return _resolve_year(month, day, base)


def _resolve_rel_day(word: str, base: datetime) -> date:
    offset = {"오늘": 0, "내일": 1, "모레": 2, "글피": 3}[word]
    return base.date() + timedelta(days=offset)


def _resolve_rel_week(m: re.Match, base: datetime) -> date:
    target_wd = WEEKDAYS[m.group("wd")]
    week = m.group("week").replace(" ", "")
    monday = base.date() - timedelta(days=base.weekday())
    if week in ("다음주", "차주"):
        monday += timedelta(days=7)
    return monday + timedelta(days=target_wd)


def _resolve_time(m: re.Match) -> tuple[int, int] | None:
    hour = int(m.group("h1") or m.group("h2"))
    minute_g = m.group("min1") or m.group("min2")
    minute = int(minute_g) if minute_g else (30 if m.group("half") else 0)
    ampm = m.group("ampm")
    if ampm == "오후" and hour < 12:
        hour += 12
    elif ampm in ("저녁", "밤") and hour < 12:
        hour += 12
    elif ampm == "낮" and hour <= 6:
        hour += 12
    if hour > 24 or minute > 59:
        return None
    return hour % 24, minute


def _find_dates(text: str, base: datetime) -> list[tuple[int, int, date]]:
    """텍스트에서 (시작, 끝, 날짜) 목록을 위치순으로 수집."""
    found: list[tuple[int, int, date]] = []
    for m in DATE_ABS.finditer(text):
        d = _resolve_abs(m, base)
        if d:
            found.append((m.start(), m.end(), d))
    covered = [(s, e) for s, e, _ in found]

    def overlaps(s: int, e: int) -> bool:
        return any(s < ce and e > cs for cs, ce in covered)

    for m in DATE_REL_WEEK.finditer(text):
        if not overlaps(m.start(), m.end()):
            found.append((m.start(), m.end(), _resolve_rel_week(m, base)))
            covered.append((m.start(), m.end()))
    for m in DATE_REL_DAY.finditer(text):
        if not overlaps(m.start(), m.end()):
            found.append((m.start(), m.end(), _resolve_rel_day(m.group(), base)))
            covered.append((m.start(), m.end()))
    found.sort()
    return found


def _find_times(text: str, date_spans: list[tuple[int, int]]) -> list[tuple[int, int, int, int]]:
    """(시작, 끝, 시, 분) — 날짜 매치와 겹치는 구간(예: '21일'의 21)은 제외."""
    out = []
    for m in TIME.finditer(text):
        if any(m.start() < e and m.end() > s for s, e in date_spans):
            continue
        hm = _resolve_time(m)
        if hm:
            out.append((m.start(), m.end(), hm[0], hm[1]))
    return out


# ── 공개 API ─────────────────────────────────────────────────

TIME_ATTACH_WINDOW = 30  # 날짜 뒤 이 거리(문자) 안의 시간을 그 날짜에 붙인다


def extract_events(text: str, base: datetime) -> list[ParsedEvent]:
    """쪽지 텍스트에서 일정 후보를 추출한다."""
    text = normalize(text)
    dates = _find_dates(text, base)
    if not dates:
        return []
    times = _find_times(text, [(s, e) for s, e, _ in dates])

    # 날짜별로 가장 가까운 뒤따르는 시간을 붙인다
    used_times: set[int] = set()

    def attach_time(dstart: int, dend: int):
        best = None
        for i, (ts, te, h, mi) in enumerate(times):
            if i in used_times:
                continue
            if dend <= ts <= dend + TIME_ATTACH_WINDOW:
                gap = ts - dend
                if best is None or gap < best[0]:
                    best = (gap, i, h, mi)
        if best:
            used_times.add(best[1])
            return best[2], best[3]
        return None

    events: list[ParsedEvent] = []
    i = 0
    while i < len(dates):
        s, e, d = dates[i]
        # 기간 감지: 이 날짜와 다음 날짜 사이가 '~' / '부터' 뿐인가
        if i + 1 < len(dates):
            ns, ne, nd = dates[i + 1]
            between = text[e:ns]
            if len(between) <= 8 and RANGE_CONNECT.match(between) and nd >= d:
                events.append(ParsedEvent(
                    start=datetime.combine(d, datetime.min.time()),
                    end=datetime.combine(nd, datetime.min.time()),
                    all_day=True,
                    is_deadline=bool(DEADLINE_HINT.search(text[ne:ne + 15])),
                    source_text=text[s:ne],
                    spans=[(s, ne)],
                ))
                i += 2
                continue
        hm = attach_time(s, e)
        tail = text[e:e + 15]
        ev = ParsedEvent(
            start=datetime.combine(d, datetime.min.time()),
            all_day=hm is None,
            is_deadline=bool(DEADLINE_HINT.search(tail)),
            source_text=text[s:e],
            spans=[(s, e)],
        )
        if hm:
            ev.start = ev.start.replace(hour=hm[0], minute=hm[1])
        events.append(ev)
        i += 1

    # 같은 시각 중복 제거 (본문에 같은 날짜가 여러 번 나오는 경우)
    seen: set[str] = set()
    unique = []
    for ev in events:
        k = ev.start.isoformat() + ("D" if ev.is_deadline else "")
        if k not in seen:
            seen.add(k)
            unique.append(ev)
    return unique


def strip_date_expressions(text: str, base: datetime) -> str:
    """제목 생성용: 날짜/시간 표현을 제거하고 다듬는다."""
    text = normalize(text)
    dates = _find_dates(text, base)
    times = _find_times(text, [(s, e) for s, e, _ in dates])
    spans = sorted([(s, e) for s, e, *_ in dates] + [(s, e, ) for s, e, _h, _m in [
        (t[0], t[1], t[2], t[3]) for t in times]], reverse=True)
    for s, e in spans:
        text = text[:s] + " " + text[e:]
    text = re.sub(r"[\[\(]\s*[\]\)]", " ", text)      # 빈 괄호 제거
    text = re.sub(r"\s{2,}", " ", text).strip(" -~,.·:/")
    return text.strip()
