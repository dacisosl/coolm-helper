# -*- coding: utf-8 -*-
"""로컬 일정·할일 저장소 (store/events.json).

전부 로컬 파일 — 이 모듈은 네트워크를 전혀 쓰지 않는다.
"""
from __future__ import annotations

import json
import os
import uuid
from dataclasses import asdict, dataclass, field
from datetime import date, datetime


PRIORITIES = ("높음", "보통", "낮음")


@dataclass
class Event:
    title: str
    start: str                      # ISO 8601
    end: str | None = None
    all_day: bool = True
    is_deadline: bool = False
    done: bool = False              # 할일(마감형)의 완료 여부
    priority: str = "보통"          # 중요도: 높음 | 보통 | 낮음
    memo: str = ""                  # 상세 메모 (로컬 전용)
    demo: bool = False              # 데모 모드에서 등록된 테스트 일정
    source_ref: str = ""            # 원본 쪽지 참조 "쪽지key|시작일시" — 등록 표시 유지용
    google_id: str | None = None    # 구글에도 등록한 경우의 이벤트 ID
    created: str = ""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])

    @property
    def start_dt(self) -> datetime:
        return datetime.fromisoformat(self.start)

    @property
    def end_dt(self) -> datetime | None:
        return datetime.fromisoformat(self.end) if self.end else None


class EventStore:
    """로컬 일정 저장소. subscribe()로 변경 알림을 받을 수 있다 (창 간 실시간 동기화)."""

    def __init__(self, base_dir: str, store_dir: str = "store"):
        self.path = os.path.join(base_dir, store_dir, "events.json")
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        self._events: list[Event] = []
        self._listeners: list = []
        self._load()

    def subscribe(self, callback) -> None:
        self._listeners.append(callback)

    def unsubscribe(self, callback) -> None:
        if callback in self._listeners:
            self._listeners.remove(callback)

    def _notify(self) -> None:
        for cb in list(self._listeners):
            try:
                cb()
            except RuntimeError:      # 이미 닫힌 창의 콜백은 제거
                self._listeners.remove(cb)

    def _load(self) -> None:
        try:
            with open(self.path, encoding="utf-8") as f:
                self._events = [Event(**e) for e in json.load(f)]
        except (FileNotFoundError, json.JSONDecodeError, TypeError):
            self._events = []

    def _save(self) -> None:
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump([asdict(e) for e in self._events], f,
                      ensure_ascii=False, indent=1)
        os.replace(tmp, self.path)
        self._notify()

    # ── CRUD ────────────────────────────────────────────────
    def add(self, title: str, start: datetime, end: datetime | None = None,
            all_day: bool = True, is_deadline: bool = False,
            google_id: str | None = None, demo: bool = False,
            memo: str = "", source_ref: str = "") -> Event:
        ev = Event(title=title, start=start.isoformat(),
                   end=end.isoformat() if end else None,
                   all_day=all_day, is_deadline=is_deadline,
                   google_id=google_id, demo=demo, memo=memo,
                   source_ref=source_ref,
                   created=datetime.now().isoformat())
        self._events.append(ev)
        self._save()
        return ev

    def remove(self, event_id: str) -> None:
        self._events = [e for e in self._events if e.id != event_id]
        self._save()

    def registered_refs(self) -> set[str]:
        """등록된 일정들의 원본 쪽지 참조 — 일정등록 목록의 '등록됨' 배경 표시용."""
        return {e.source_ref for e in self._events if e.source_ref}

    def demo_count(self) -> int:
        return sum(1 for e in self._events if e.demo)

    def archive_old(self, days: int) -> int:
        """지난 지 N일 넘은 일정을 보관 파일(events_archive.json)로 옮긴다."""
        if days <= 0:
            return 0
        cutoff = date.today().toordinal() - days
        old, keep = [], []
        for e in self._events:
            last = e.end_dt.date() if e.end_dt else e.start_dt.date()
            (old if last.toordinal() < cutoff else keep).append(e)
        if not old:
            return 0
        archive_path = os.path.join(os.path.dirname(self.path),
                                    "events_archive.json")
        try:
            with open(archive_path, encoding="utf-8") as f:
                archived = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            archived = []
        archived.extend(asdict(e) for e in old)
        with open(archive_path, "w", encoding="utf-8") as f:
            json.dump(archived, f, ensure_ascii=False, indent=1)
        self._events = keep
        self._save()
        return len(old)

    def remove_demo(self) -> int:
        """데모 모드에서 등록한 테스트 일정을 모두 삭제한다."""
        n = self.demo_count()
        self._events = [e for e in self._events if not e.demo]
        self._save()
        return n

    def set_done(self, event_id: str, done: bool) -> None:
        for e in self._events:
            if e.id == event_id:
                e.done = done
        self._save()

    def update(self, event_id: str, **fields) -> None:
        """상세보기 인라인 편집 저장. datetime 값은 ISO 문자열로 넘길 것."""
        for e in self._events:
            if e.id == event_id:
                for k, v in fields.items():
                    if hasattr(e, k):
                        setattr(e, k, v)
        self._save()

    def set_google_id(self, event_id: str, google_id: str) -> None:
        for e in self._events:
            if e.id == event_id:
                e.google_id = google_id
        self._save()

    # ── 조회 ────────────────────────────────────────────────
    def all(self) -> list[Event]:
        return sorted(self._events, key=lambda e: e.start)

    def on_date(self, d: date) -> list[Event]:
        out = []
        for e in self.all():
            start_d = e.start_dt.date()
            end_d = e.end_dt.date() if e.end_dt else start_d
            if start_d <= d <= end_d:
                out.append(e)
        return out

    def dates_with_events(self) -> set[date]:
        out: set[date] = set()
        for e in self._events:
            start_d = e.start_dt.date()
            end_d = e.end_dt.date() if e.end_dt else start_d
            d = start_d
            while d <= end_d:
                out.add(d)
                d = date.fromordinal(d.toordinal() + 1)
        return out

    def todos(self) -> list[Event]:
        """기한형([마감]) 일정 = 할일 목록. 미완료 먼저, 기한순."""
        items = [e for e in self._events if e.is_deadline]
        return sorted(items, key=lambda e: (e.done, e.start))
