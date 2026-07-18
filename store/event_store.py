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
    def __init__(self, base_dir: str, store_dir: str = "store"):
        self.path = os.path.join(base_dir, store_dir, "events.json")
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        self._events: list[Event] = []
        self._load()

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

    # ── CRUD ────────────────────────────────────────────────
    def add(self, title: str, start: datetime, end: datetime | None = None,
            all_day: bool = True, is_deadline: bool = False,
            google_id: str | None = None) -> Event:
        ev = Event(title=title, start=start.isoformat(),
                   end=end.isoformat() if end else None,
                   all_day=all_day, is_deadline=is_deadline,
                   google_id=google_id, created=datetime.now().isoformat())
        self._events.append(ev)
        self._save()
        return ev

    def remove(self, event_id: str) -> None:
        self._events = [e for e in self._events if e.id != event_id]
        self._save()

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
