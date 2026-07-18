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
    "widget_always_on_top": True,
    "widget_opacity": 100,          # 50~100 (%)
    "auto_update_check": True,      # 시작 시 새 버전 확인 (update_url 있을 때만)
    "update_url": "",               # version.json 주소 (updater.py 참고)
}


def save_config(base_dir: str, config: dict) -> None:
    path = os.path.join(base_dir, "config.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def load_config(base_dir: str) -> dict:
    """config.json 로드. 없으면(새 PC에 설치 직후) 경로 자동 탐지로 생성한다."""
    path = os.path.join(base_dir, "config.json")
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        config = dict(DEFAULT_CONFIG)
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


def collect(base_dir: str, count: int | None = None) -> tuple[list[Candidate], list[Message], str]:
    """가장 최근 쪽지 N개에서 일정 후보를 수집한다.

    반환: (후보 목록, 일정 없는 쪽지 목록, 사용한 소스 'db'|'excel')
    """
    config = load_config(base_dir)
    count = count or int(config.get("recent_count", 10))
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
