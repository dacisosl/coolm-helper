# -*- coding: utf-8 -*-
"""나이스(NEIS) 교육정보 개방 포털 — 학교 검색 + 학사일정 가져오기 (온라인 존).

⚠ 개인정보 경계:
- 밖으로 나가는 것은 **학교 이름/학교 코드와 조회 기간**뿐이다.
  쪽지·일정·학생 이름은 이 모듈을 거치지 않는다 (parser/·store/를 import하지 않음).
- 받아오는 것은 학교가 공개한 학사일정(행사명·날짜)이라 개인정보가 아니다.

API 문서: https://open.neis.go.kr  (schoolInfo / SchoolSchedule)
인증키는 없어도 호출되지만 한 번에 5건만 온다 — 그래서 키를 함께 쓴다.
"""
from __future__ import annotations

import base64
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date, timedelta

BASE_URL = "https://open.neis.go.kr/hub"
TIMEOUT = 15
MAX_ROWS = 1000            # 한 번에 받아올 최대 행 수 (API 상한)
KEYLESS_ROWS = 5           # 인증키 없이 부를 때 API가 주는 행 수

# 응답 코드 → 사람이 읽을 안내 (없는 코드는 원문 메시지를 그대로 보여준다)
_CODE_MESSAGES = {
    "INFO-200": "",        # 데이터 없음 — 오류가 아니라 빈 결과로 처리
    "INFO-300": "인증키가 유효하지 않습니다. 설정에서 키를 다시 확인해 주세요.",
    "ERROR-290": "인증키가 등록되지 않았습니다. 나이스에서 키를 신청해 주세요.",
    "ERROR-300": "요청 값이 잘못되었습니다.",
    "ERROR-333": "요청 위치 값의 타입이 잘못되었습니다.",
    "ERROR-336": "요청 항목이 너무 많습니다.",
    "ERROR-337": "오늘 조회 한도를 넘었습니다. 내일 다시 시도해 주세요.",
    "ERROR-500": "나이스 서버에 문제가 있습니다. 잠시 후 다시 시도해 주세요.",
    "ERROR-600": "나이스 서버에 문제가 있습니다. 잠시 후 다시 시도해 주세요.",
    "ERROR-601": "나이스 서버에 문제가 있습니다. 잠시 후 다시 시도해 주세요.",
}


class NeisError(Exception):
    """나이스 호출 실패 — 메시지를 그대로 사용자에게 보여줄 수 있게 다듬어 둔다."""


@dataclass(frozen=True)
class School:
    name: str              # 학교 이름
    code: str              # 표준학교코드 (SD_SCHUL_CODE)
    office: str            # 시도교육청코드 (ATPT_OFCDC_SC_CODE)
    office_name: str = ""  # 시도교육청 이름
    kind: str = ""         # 초등학교 / 중학교 / 고등학교 …
    address: str = ""      # 도로명주소 (같은 이름 학교 구분용)

    def label(self) -> str:
        """목록에 보여줄 한 줄 — 이름 + 종류."""
        return f"{self.name} ({self.kind})" if self.kind else self.name

    def to_conf(self) -> dict:
        return {"name": self.name, "code": self.code, "office": self.office,
                "office_name": self.office_name, "kind": self.kind,
                "address": self.address}

    @staticmethod
    def from_conf(d) -> "School | None":
        if not isinstance(d, dict) or not (d.get("code") and d.get("office")):
            return None
        return School(name=str(d.get("name", "")), code=str(d["code"]),
                      office=str(d["office"]),
                      office_name=str(d.get("office_name", "")),
                      kind=str(d.get("kind", "")),
                      address=str(d.get("address", "")))


@dataclass
class NeisEvent:
    """학사일정 한 건 — 연속된 같은 행사는 start~end 한 건으로 묶는다."""
    title: str
    start: date
    end: date | None = None      # 하루짜리면 None
    memo: str = ""
    ref: str = ""                # 중복 등록 방지용 표식 (source_ref)

    def when_text(self) -> str:
        if self.end and self.end != self.start:
            return (f"{self.start.month}/{self.start.day}"
                    f" ~ {self.end.month}/{self.end.day}")
        return f"{self.start.month}/{self.start.day}"


# ── 인증키 ────────────────────────────────────────────────────
def _app_root() -> str:
    """assets/가 놓이는 앱 루트 (main.py의 BASE_DIR과 같은 규칙)."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def embedded_key() -> str:
    """빌드 때 심어둔 공용 나이스 키 (assets/neis.key, base64).

    소스·깃에는 없고 릴리스 빌드에서만 주입된다. 없으면 빈 문자열.
    """
    try:
        with open(os.path.join(_app_root(), "assets", "neis.key"), "rb") as f:
            return base64.b64decode(f.read().strip()).decode("utf-8").strip()
    except Exception:
        return ""


def api_key(config: dict | None = None) -> str:
    """쓸 인증키: 사용자가 직접 넣은 키 → 내장 키 → 빈 값(키 없이 5건만)."""
    own = str((config or {}).get("neis_api_key", "")).strip()
    return own or embedded_key()


# ── 호출 ──────────────────────────────────────────────────────
def _request(path: str, params: dict, key: str) -> list[dict]:
    """나이스 API 한 번 호출 → row 목록. 데이터가 없으면 빈 목록."""
    q = {"Type": "json", "pIndex": 1,
         "pSize": MAX_ROWS if key else KEYLESS_ROWS, **params}
    if key:
        q["KEY"] = key
    url = f"{BASE_URL}/{path}?" + urllib.parse.urlencode(q)
    req = urllib.request.Request(url, headers={"User-Agent": "CoolmHelper"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            raw = r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        raise NeisError(f"나이스 서버가 응답하지 않았습니다. (HTTP {e.code})")
    except Exception as e:
        raise NeisError(
            "나이스에 연결하지 못했습니다. 인터넷 연결이나 학교 방화벽을 "
            f"확인해 주세요.\n({type(e).__name__})") from e
    try:
        data = json.loads(raw)
    except ValueError:
        raise NeisError("나이스 응답을 알아볼 수 없습니다. 잠시 후 다시 시도해 주세요.")
    return _rows(data, path)


def _rows(data, path: str) -> list[dict]:
    """응답에서 row 목록을 뽑는다. 오류 코드는 NeisError로 바꾼다.

    성공: {"<path>": [{"head": [...]}, {"row": [...]}]}
    실패: {"RESULT": {"CODE": "...", "MESSAGE": "..."}}
    (응답 형태가 조금 달라져도 견디도록 방어적으로 훑는다.)
    """
    if not isinstance(data, dict):
        raise NeisError("나이스 응답 형식이 예상과 다릅니다.")
    if "RESULT" in data and path not in data:
        _raise_for_code(data.get("RESULT"))
        return []
    blocks = data.get(path)
    if blocks is None:                      # 키 이름이 대소문자만 다를 때 대비
        for k, v in data.items():
            if k.lower() == path.lower():
                blocks = v
                break
    if not isinstance(blocks, list):
        raise NeisError("나이스 응답에서 결과를 찾지 못했습니다.")
    rows: list[dict] = []
    for block in blocks:
        if not isinstance(block, dict):
            continue
        for head in block.get("head", []) or []:
            if isinstance(head, dict) and "RESULT" in head:
                _raise_for_code(head["RESULT"])
        for row in block.get("row", []) or []:
            if isinstance(row, dict):
                rows.append(row)
    return rows


def _raise_for_code(result) -> None:
    """RESULT 블록이 오류면 NeisError. 정상·데이터없음이면 조용히 통과."""
    if not isinstance(result, dict):
        return
    code = str(result.get("CODE", ""))
    if code in ("INFO-000", "INFO-200", ""):
        return
    msg = _CODE_MESSAGES.get(code) or str(result.get("MESSAGE", "")).strip()
    raise NeisError(msg or f"나이스 오류 ({code})")


# ── 학교 검색 ─────────────────────────────────────────────────
def search_schools(name: str, config: dict | None = None) -> list[School]:
    """학교 이름(일부만 넣어도 됨)으로 검색. 최대 MAX_ROWS건."""
    name = (name or "").strip()
    if len(name) < 2:
        raise NeisError("학교 이름을 두 글자 이상 입력해 주세요.")
    rows = _request("schoolInfo", {"SCHUL_NM": name}, api_key(config))
    out = []
    for r in rows:
        code, office = r.get("SD_SCHUL_CODE"), r.get("ATPT_OFCDC_SC_CODE")
        if not (code and office):
            continue
        out.append(School(
            name=str(r.get("SCHUL_NM", "")).strip(),
            code=str(code), office=str(office),
            office_name=str(r.get("ATPT_OFCDC_SC_NM", "")).strip(),
            kind=str(r.get("SCHUL_KND_SC_NM", "")).strip(),
            address=str(r.get("ORG_RDNMA", "")).strip()))
    return out


# ── 학사일정 ──────────────────────────────────────────────────
_SKIP_TITLES = ("토요휴업일", "공휴일", "휴업일", "방학")   # 일정으로 굳이 안 담는 것


def _parse_ymd(s) -> date | None:
    m = re.fullmatch(r"(\d{4})(\d{2})(\d{2})", str(s or "").strip())
    if not m:
        return None
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def fetch_schedule(school: School, start: date, end: date,
                   config: dict | None = None,
                   skip_holidays: bool = True) -> list[NeisEvent]:
    """학사일정을 가져와 연속된 같은 행사를 기간 하나로 묶어 돌려준다.

    나이스는 3일짜리 행사를 '하루 한 줄'로 세 줄 준다 — 그대로 등록하면
    같은 이름이 세 번 쌓이므로 여기서 기간 일정 한 건으로 합친다.
    """
    rows = _request("SchoolSchedule", {
        "ATPT_OFCDC_SC_CODE": school.office,
        "SD_SCHUL_CODE": school.code,
        "AA_FROM_YMD": start.strftime("%Y%m%d"),
        "AA_TO_YMD": end.strftime("%Y%m%d"),
    }, api_key(config))
    return merge_rows(rows, school, skip_holidays=skip_holidays)


def merge_rows(rows: list[dict], school: School,
               skip_holidays: bool = True) -> list[NeisEvent]:
    """API 행들을 (행사명별) 연속 날짜로 묶어 NeisEvent 목록으로."""
    picked: list[tuple[date, str, str]] = []
    for r in rows:
        d = _parse_ymd(r.get("AA_YMD"))
        title = str(r.get("EVENT_NM", "")).strip()
        if d is None or not title:
            continue
        if skip_holidays and any(k in title for k in _SKIP_TITLES):
            continue
        memo = str(r.get("EVENT_CNTNT", "")).strip()
        picked.append((d, title, memo))
    picked.sort(key=lambda t: (t[1], t[0]))

    out: list[NeisEvent] = []
    for d, title, memo in picked:
        last = out[-1] if out else None
        # 같은 행사명이 바로 다음 날로 이어지면 기간으로 늘린다
        if last is not None and last.title == title and \
                (last.end or last.start) + timedelta(days=1) == d:
            last.end = d
            if memo and memo not in last.memo:
                last.memo = (last.memo + "\n" + memo).strip()
            continue
        out.append(NeisEvent(title=title, start=d, memo=memo,
                             ref=event_ref(school, d, title)))
    out.sort(key=lambda e: (e.start, e.title))
    return out


def event_ref(school: School, d: date, title: str) -> str:
    """중복 등록 방지 표식 — 같은 학교·시작일·행사명이면 같은 값."""
    return f"neis|{school.code}|{d.strftime('%Y%m%d')}|{title}"


# ── 진단 (설정 → 데이터에서 실행) ──────────────────────────────
def diagnose(config: dict | None = None) -> str:
    """학사일정을 못 가져올 때 어디서 막혔는지 알려준다."""
    lines: list[str] = []
    key = api_key(config)
    if not key:
        lines.append("① 인증키: 없음 — 키 없이도 되지만 한 번에 5건만 옵니다.")
    else:
        own = bool(str((config or {}).get("neis_api_key", "")).strip())
        lines.append(f"① 인증키: 있음 ({'직접 넣은 키' if own else '앱 내장 키'},"
                     f" 끝 4자리 …{key[-4:]})")
    try:
        schools = search_schools("초등학교", config)
        lines.append(f"② 나이스 연결: 정상 (학교 검색 {len(schools)}건)")
    except NeisError as e:
        lines.append(f"② 나이스 연결 실패: {e}")
        return "\n".join(lines)
    school = School.from_conf((config or {}).get("neis_school"))
    if school is None:
        lines.append("③ 우리 학교: 아직 안 정했어요 — 학사일정 창에서 검색해 주세요.")
        return "\n".join(lines)
    lines.append(f"③ 우리 학교: {school.label()}")
    today = date.today()
    try:
        evs = fetch_schedule(school, today, today + timedelta(days=90), config)
        lines.append(f"④ 앞으로 3개월 학사일정: {len(evs)}건")
        for e in evs[:3]:
            lines.append(f"   · {e.when_text()} {e.title[:20]}")
    except NeisError as e:
        lines.append(f"④ 학사일정 조회 실패: {e}")
    return "\n".join(lines)
