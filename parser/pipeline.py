# -*- coding: utf-8 -*-
"""파싱 파이프라인: 쪽지 → 일정 후보 (제목·일시·마스킹 포함).

이 모듈까지가 '로컬 존'이다. 여기서 만든 Candidate 중
masked_title / start / end 만이 (사용자 확인 후) 온라인 존으로 넘어갈 수 있다.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from . import date_parser, pii_detector
from .db_reader import DbReader, Message, SchemaMismatch
from .pii_detector import PiiSpan


@dataclass
class Candidate:
    message: Message
    start: datetime
    end: datetime | None
    all_day: bool
    is_deadline: bool
    suggested_title: str            # 마스킹 전 (로컬 표시·편집용)
    masked_title: str               # 마스킹 후 (기본 제안값)
    title_spans: list[PiiSpan] = field(default_factory=list)
    body_spans: list[PiiSpan] = field(default_factory=list)
    source_text: str = ""


DEFAULT_CONFIG = {
    "udb_select_rule": "memo_dir 안에서 가장 최근 수정된 *.udb",
    "excel_file_pattern": "coolmsg_*.xls*",
    "db_tables": {"received": "tbl_recv", "sent": "tbl_send", "members": "tbl_member"},
    "date_format": "yyyy/MM/dd HH:mm:ss (요일)",
    "access_mode": "copy-then-read-only",
    "students_path": "students.txt",
    "store_dir": "store",
    "recent_count": 10,          # 가장 최근 쪽지 N개 (날짜 기준 아님)
    "google_sync_enabled": False,   # 저장 모드: False=로컬(기본) / True=구글 연동
    "widget_style": "mini",         # mini(펭귄 도킹) | detail(카드형)
    "widget_always_on_top": True,
    "widget_opacity": 100,          # 50~100 (%)
    "favorites_enabled": False,     # 즐겨찾기 보관함
    "proof_enabled": False,         # 안내문구 보정 (공개용 글 전용)
    "proof_provider": "gemini",
    "proof_model": "gemini-2.0-flash",
    "proof_api_key": "",            # 로컬에만 저장 (gitignore 대상 config.json)
    "desk_widgets": {               # 바탕화면 위젯 (v0.10.0~)
        # planner(캘린더·할일)는 빠른메뉴의 캘린더 아이콘을 대신하므로 기본 켬
        "planner": {"enabled": True, "geometry": None, "opacity": 95,
                    "always_on_top": False, "font_scale": 100},
        "simple":  {"enabled": False, "geometry": None, "opacity": 90,
                    "always_on_top": False, "font_scale": 100},
        "weekly":  {"enabled": False, "geometry": None, "opacity": 90,
                    "always_on_top": False, "font_scale": 100},
        "monthly": {"enabled": False, "geometry": None, "opacity": 90,
                    "always_on_top": False, "font_scale": 100},
        "notes": [],   # 포스트잇: {event_id, geometry, opacity, always_on_top, font_scale}
    },
    "demo_mode": False,             # 내장 가짜 쪽지로 테스트 (쿨메신저 불필요)
    "alert_days": [3, 1],           # 마감 며칠 전에 알림할지
    "auto_archive_days": 90,        # 지난 일정 자동 보관 (0=끔)
    "intro_done": False,            # 첫 실행 기능 안내를 봤는지
    "auto_update_check": True,      # 시작 시 새 버전 확인 (update_url 있을 때만)
    "update_url": "https://raw.githubusercontent.com/dacisosl/coolm-helper/main/version.json"
}


DESK_KINDS = ("planner", "simple", "weekly", "monthly")


def _desk_default() -> dict:
    return {"enabled": False, "geometry": None, "opacity": 90,
            "always_on_top": False, "font_scale": 100}


def desk_conf(config: dict, kind: str):
    """desk_widgets에서 kind("simple"/"weekly"/"monthly"/"notes") 설정을 꺼낸다.

    구버전 config라 키가 없거나 일부만 있어도 기본값을 채워서 돌려준다.
    반환된 dict/list는 config 내부 객체라 수정 후 save_config 하면 저장된다.
    """
    dw = config.setdefault("desk_widgets", {})
    if kind == "notes":
        return dw.setdefault("notes", [])
    cur = dw.setdefault(kind, {})
    for k, v in _desk_default().items():
        cur.setdefault(k, v)
    return cur


def migrate_desk_config(config: dict) -> bool:
    """구 '바탕화면 반절 캘린더' 설정을 위젯 4종 체계로 옮긴다. 변경 시 True.

    반절 캘린더를 켜두었던 사용자는 주간+월간 위젯이 대신 켜지고
    투명도를 물려받는다. desk_migration_notice_done=False로 남겨
    최초 1회 안내 말풍선을 띄운다.
    """
    if "desk_widgets" in config:
        return False
    was_on = bool(config.pop("desktop_widget_enabled", False))
    opacity = int(config.pop("desktop_widget_opacity", 90) or 90)
    config["desk_widgets"] = {k: _desk_default() for k in DESK_KINDS}
    config["desk_widgets"]["notes"] = []
    # 캘린더·할일 위젯은 빠른메뉴의 캘린더 아이콘을 대신하므로 기본 켬
    config["desk_widgets"]["planner"]["enabled"] = True
    if was_on:
        for k in ("weekly", "monthly"):
            config["desk_widgets"][k]["enabled"] = True
            config["desk_widgets"][k]["opacity"] = max(40, min(100, opacity))
    config["desk_migration_notice_done"] = not was_on
    return True


def ensure_planner(config: dict) -> bool:
    """v0.11.0 마이그레이션: 기존 사용자에게 캘린더·할일 위젯을 켜준다.

    빠른메뉴에서 캘린더 아이콘이 빠지는 대신이므로 최초 1회 자동 켬.
    """
    dw = config.get("desk_widgets")
    if not isinstance(dw, dict) or "planner" in dw:
        return False
    dw["planner"] = _desk_default()
    dw["planner"]["enabled"] = True
    dw["planner"]["opacity"] = 95
    return True


def prune_notes(config: dict, existing_ids: set[str]) -> bool:
    """삭제된 일정을 가리키는 포스트잇 항목을 정리한다. 변경 시 True."""
    notes = desk_conf(config, "notes")
    keep = [n for n in notes if n.get("event_id") in existing_ids]
    if len(keep) == len(notes):
        return False
    config["desk_widgets"]["notes"] = keep
    return True


def clamp_geometry(geo, screen):
    """저장된 위젯 위치·크기가 현재 화면에 맞는지 검증한다 (해상도 변경 대비).

    geo/screen: [x, y, w, h]. 화면과 거의 안 겹치면 None(기본 배치로 폴백),
    일부만 벗어났으면 화면 안으로 끌어들인 값을 반환한다.
    """
    if not geo or len(geo) != 4:
        return None
    try:
        x, y, w, h = (int(v) for v in geo)
        sx, sy, sw, sh = (int(v) for v in screen)
    except (TypeError, ValueError):
        return None
    if w <= 0 or h <= 0 or sw <= 0 or sh <= 0:
        return None
    # 겹치는 영역이 가로·세로 40px 미만이면 다른 해상도의 잔재로 본다
    ox = min(x + w, sx + sw) - max(x, sx)
    oy = min(y + h, sy + sh) - max(y, sy)
    if ox < 40 or oy < 40:
        return None
    w, h = min(w, sw), min(h, sh)
    x = max(sx, min(x, sx + sw - w))
    y = max(sy, min(y, sy + sh - h))
    return [x, y, w, h]


def save_config(base_dir: str, config: dict) -> None:
    path = os.path.join(base_dir, "config.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def load_config(base_dir: str) -> dict:
    """config.json 로드. 없으면(새 PC에 설치 직후) 경로 자동 탐지로 생성한다."""
    path = os.path.join(base_dir, "config.json")
    try:
        with open(path, encoding="utf-8") as f:
            config = json.load(f)
        changed = migrate_desk_config(config)
        changed = ensure_planner(config) or changed
        if changed:
            save_config(base_dir, config)
        return config
    except FileNotFoundError:
        config = json.loads(json.dumps(DEFAULT_CONFIG))   # 깊은 복사
        local = os.environ.get("LOCALAPPDATA", "")
        profile = os.environ.get("USERPROFILE", "")
        config["memo_dir"] = os.path.join(local, "CoolMessenger", "Memo")
        config["excel_export_path"] = os.path.join(
            profile, "Documents", "CoolMessenger Files", "Received Files")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        return config


def build_roster(base_dir: str, config: dict, reader: DbReader | None) -> set[str]:
    students_path = config.get("students_path", "students.txt")
    if not os.path.isabs(students_path):
        students_path = os.path.join(base_dir, students_path)
    roster = pii_detector.load_students(students_path)
    if reader is not None:
        roster |= reader.member_names()
    return roster


def make_title(msg: Message, base: datetime) -> str:
    """제목 우선순위: ① 쪽지 제목에서 날짜 표현 제거 ② 본문 첫 문장."""
    title = date_parser.strip_date_expressions(msg.title, base)
    if len(title) >= 2:
        return title[:60]
    for line in msg.body.splitlines():
        line = date_parser.strip_date_expressions(line, base)
        if len(line) >= 2:
            return line[:60]
    return "(제목 없음)"


def candidates_from_message(msg: Message, roster: set[str]) -> list[Candidate]:
    events = date_parser.extract_events(msg.title + "\n" + msg.body, msg.received)
    # 쪽지 수신일보다 과거인 일정은 제외 (본문에 인용된 과거 날짜 등)
    events = [ev for ev in events if ev.start.date() >= msg.received.date()]
    if not events:
        return []
    title = make_title(msg, msg.received)
    title_spans = pii_detector.detect(title, roster)
    body_spans = pii_detector.detect(msg.body, roster)
    masked = pii_detector.mask(title, title_spans)
    out = []
    for ev in events:
        end = ev.end
        if end is None and not ev.all_day:
            end = ev.start + timedelta(hours=1)
        prefix = "[마감] " if ev.is_deadline else ""
        out.append(Candidate(
            message=msg, start=ev.start, end=end, all_day=ev.all_day,
            is_deadline=ev.is_deadline,
            suggested_title=prefix + title,
            masked_title=prefix + masked,
            title_spans=title_spans, body_spans=body_spans,
            source_text=ev.source_text,
        ))
    return out


def _normalize_for_match(s: str) -> str:
    return "".join(s.split())


def match_captured(messages: list[Message], title: str, body: str) -> Message | None:
    """화면에서 읽은 제목/본문으로 DB의 원본 쪽지를 찾는다.

    포함 비교는 양쪽 모두 충분히 길 때만 한다 —
    본문이 짧거나 빈 쪽지가 아무 텍스트와나 매칭되는 오탐 방지.
    """
    MIN = 20
    nb = _normalize_for_match(body)
    nt = _normalize_for_match(title)
    for m in messages:
        mb = _normalize_for_match(m.body)
        if len(nb) >= MIN and len(mb) >= MIN:
            if mb[:60] == nb[:60] or nb[:40] in mb or mb[:40] in nb:
                return m
    if len(nt) >= 6:
        for m in messages:
            mt = _normalize_for_match(m.title)
            if len(mt) >= 6 and mt[:40] == nt[:40]:
                return m
    return None


_quick_cache: dict = {}   # 매칭용 축약 쪽지 + 명단 캐시 (DB 변경 감지로 무효화)


def _db_stamp(config: dict):
    """DB가 바뀌었는지 감지하는 스탬프 (원본 파일 수정시각·WAL 크기)."""
    import glob as _glob
    try:
        src = max(_glob.glob(os.path.join(config["memo_dir"], "*.udb")),
                  key=os.path.getmtime)
        wal = src + "-wal"
        return (src, os.path.getmtime(src),
                os.path.getsize(wal) if os.path.exists(wal) else 0)
    except (ValueError, OSError, KeyError):
        return None


def _quick_rows(base_dir: str, config: dict):
    """매칭용 쪽지(축약)와 명단을 캐시와 함께 가져온다."""
    import time as _time
    stamp = _db_stamp(config)
    c = _quick_cache
    if (stamp is not None and c.get("stamp") == stamp
            and _time.time() - c.get("t", 0) < 120):
        return c["rows"], c["roster"]
    rows, roster = None, None
    for direct in (True, False):   # 직접 읽기 → 복사 폴백
        try:
            with DbReader(config["memo_dir"], direct=direct) as reader:
                rows = reader.match_rows(50)
                roster = build_roster(base_dir, config, reader)
            break
        except Exception:
            continue
    if roster is None:
        roster = build_roster(base_dir, config, None)
    c.update(stamp=stamp, rows=rows or [], roster=roster, t=_time.time())
    return rows or [], roster


def prefetch_quick(base_dir: str) -> None:
    """⚡ 클릭 전에 미리 데이터를 데워둔다 (펭귄 메뉴 열릴 때 호출)."""
    try:
        _quick_rows(base_dir, load_config(base_dir))
    except Exception:
        pass


def quick_candidates(base_dir: str, title: str, body: str
                     ) -> tuple[list[Candidate], Message, bool]:
    """간편 등록용: 화면/클립보드에서 얻은 텍스트를 일정 후보로 바꾼다.

    DB에서 원본 쪽지를 찾으면 그 쪽지 기준(수신시각·등록표시 연동),
    못 찾으면 텍스트 자체를 지금 시각 기준으로 파싱한다.
    반환: (후보들, 사용한 메시지, DB 매칭 여부)
    """
    config = load_config(base_dir)
    rows, roster = _quick_rows(base_dir, config)
    matched_row = match_captured(rows, title, body)
    matched = None
    if matched_row is not None:
        # 축약본으로 매칭했으니 전문은 한 건만 빠르게 가져온다
        for direct in (True, False):
            try:
                with DbReader(config["memo_dir"], direct=direct) as reader:
                    matched = reader.get_message(matched_row.key)
                break
            except Exception:
                continue
        matched = matched or matched_row
    msg = matched or Message(
        key=-1, sender="(화면에서 가져옴)", received=datetime.now(),
        title=title or body.splitlines()[0][:40], body=body)
    return candidates_from_message(msg, roster), msg, matched is not None


def collect(base_dir: str, count: int | None = None) -> tuple[list[Candidate], list[Message], str]:
    """가장 최근 쪽지 N개에서 일정 후보를 수집한다.

    반환: (후보 목록, 일정 없는 쪽지 목록, 사용한 소스 'db'|'excel')
    """
    config = load_config(base_dir)
    count = count or int(config.get("recent_count", 10))

    # 데모 모드: 쿨메신저 없이 내장 가짜 쪽지로 전체 기능 체험
    if config.get("demo_mode"):
        from . import demo_data
        messages = demo_data.demo_messages()[:count]
        roster = build_roster(base_dir, config, None) | demo_data.demo_roster()
        candidates, no_event = [], []
        for msg in messages:
            found = candidates_from_message(msg, roster)
            candidates.extend(found) if found else no_event.append(msg)
        return candidates, no_event, "demo"

    source = "db"
    try:
        with DbReader(config["memo_dir"]) as reader:
            messages = reader.latest_messages(count)
            roster = build_roster(base_dir, config, reader)
    except (SchemaMismatch, FileNotFoundError):
        # Plan B 폴백: 엑셀 내보내기
        from . import excel_reader
        source = "excel"
        path = excel_reader.find_latest_export(
            config.get("excel_export_path", ""), config.get("excel_file_pattern", "coolmsg_*.xls*"))
        if not path:
            raise FileNotFoundError(excel_reader.EXPORT_GUIDE)
        messages = excel_reader.read_messages(path)[:count]
        roster = build_roster(base_dir, config, None)

    candidates: list[Candidate] = []
    no_event: list[Message] = []
    for msg in messages:
        found = candidates_from_message(msg, roster)
        if found:
            candidates.extend(found)
        else:
            no_event.append(msg)
    return candidates, no_event, source
