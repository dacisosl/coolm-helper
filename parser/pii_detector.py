# -*- coding: utf-8 -*-
"""개인정보 탐지기 — 4종 규칙 (전화번호 / 주민번호 / 호칭 / 명단 대조).

완벽한 필터가 아니라 '사용자 확인을 돕는 하이라이터'다.
탐지 결과는 span 목록으로 반환되고, UI에서 빨간 표시 + 마스킹에 쓰인다.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

MASK = "○○○"

PHONE_RE = re.compile(
    r"(?<!\d)(?:01[016789]|0[2-6]\d?)\)?[-.\s]?\d{3,4}[-.\s]?\d{4}(?!\d)")
RRN_RE = re.compile(r"(?<!\d)\d{6}[-\s]?[1-4](?:\d{6}|\*{4,6})(?!\d)")
# 호칭: 이름(한글 2~4자) + 학생/님/선생님/학부모 등.
# 호칭 뒤에는 비한글, 문장 끝, 또는 조사(께/이/은/는...)만 허용해 오탐을 줄인다.
HONORIFIC_RE = re.compile(
    r"(?P<name>[가-힣]{2,4})\s*"
    r"(?P<title>학부모님|보호자님|선생님|어머님|아버님|학생|쌤|군|양|님)"
    r"(?=$|[^가-힣]|[께은는이의과와에들도])")
# 호칭 앞이 이름이 아닌 흔한 일반 명사들 (오탐 방지)
NAME_STOPWORDS = {
    "선생", "선생님", "부모", "학부모", "여러분", "회원", "고객", "구성원",
    "교장", "교감", "교사", "담임", "관리자", "사용자", "담당자", "학년",
    "우리", "저희", "모든", "해당", "신청자", "대상자", "참가자", "지원자",
    # '~학생' 합성어의 앞부분 (위기학생, 전입학생 등 — 이름 아님)
    "위기", "다문화", "배려", "전입", "전출", "신입", "재학", "졸업",
    "대상", "전체", "일부", "미인정", "미등교", "부적응",
}


@dataclass(frozen=True)
class PiiSpan:
    start: int
    end: int
    kind: str        # phone | rrn | honorific | roster
    text: str
    masked: str      # 이 구간을 대체할 문자열


def _merge(spans: list[PiiSpan]) -> list[PiiSpan]:
    """겹치는 span은 먼저 시작하는(넓은) 쪽을 남긴다."""
    spans.sort(key=lambda s: (s.start, -(s.end - s.start)))
    out: list[PiiSpan] = []
    for s in spans:
        if out and s.start < out[-1].end:
            continue
        out.append(s)
    return out


def detect(text: str, roster: set[str] | None = None) -> list[PiiSpan]:
    """텍스트에서 개인정보 구간을 찾는다. roster = 학생 명단 + 교직원 명단."""
    spans: list[PiiSpan] = []

    for m in PHONE_RE.finditer(text):
        spans.append(PiiSpan(m.start(), m.end(), "phone", m.group(), MASK))
    for m in RRN_RE.finditer(text):
        spans.append(PiiSpan(m.start(), m.end(), "rrn", m.group(), MASK))
    for m in HONORIFIC_RE.finditer(text):
        name = m.group("name")
        if name in NAME_STOPWORDS or name.endswith(("학년", "학기", "번째")):
            continue
        # 이름 부분만 가리고 호칭은 남긴다: '김철수 학생' → '○○○ 학생'
        spans.append(PiiSpan(m.start("name"), m.end("name"), "honorific",
                             name, MASK))
    for name in (roster or set()):
        if len(name) < 2:
            continue
        # 단어 경계: 다른 한글 단어 속에 우연히 포함된 경우는 제외
        # (예: 명단의 '이수'가 '이수 기준'의 일부로 오탐되는 것 방지)
        pat = re.compile(rf"(?<![가-힣]){re.escape(name)}(?![가-힣])")
        for m in pat.finditer(text):
            spans.append(PiiSpan(m.start(), m.end(), "roster", name, MASK))

    return _merge(spans)


def mask(text: str, spans: list[PiiSpan] | None = None,
         roster: set[str] | None = None) -> str:
    """탐지 구간을 마스킹한 텍스트를 돌려준다."""
    if spans is None:
        spans = detect(text, roster)
    for s in sorted(spans, key=lambda s: s.start, reverse=True):
        text = text[:s.start] + s.masked + text[s.end:]
    return text


def load_students(path: str) -> set[str]:
    """students.txt 로드 — 한 줄에 이름 하나, '#' 주석 무시."""
    names: set[str] = set()
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    names.add(line)
    except FileNotFoundError:
        pass
    return names
