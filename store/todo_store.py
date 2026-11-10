# -*- coding: utf-8 -*-
"""내 할 일 저장소 (store/todos.json) — '일정 · 할 일 보드' 위젯용 (2026-11-10).

일정(events.json)과 따로 둔다. 일정은 쪽지에서 등록한 것, 할 일은 사용자가
직접 적는 것이다(사용자 결정). 할 일은 일정에 연결(event_id)하거나 날짜(day)를
정하거나, 둘 다 없이 둘 수 있다. 전부 로컬 파일 — 네트워크·구글 연동 없음.

일정이 지워져도 연결된 할 일은 지우지 않는다(사용자가 쓴 글) — 보드에서는
'미분류'로 보인다.
"""
from __future__ import annotations

import json
import os
import uuid
from dataclasses import asdict, dataclass, field
from datetime import date, datetime


@dataclass
class Todo:
    title: str
    done: bool = False
    event_id: str = ""              # 연결된 일정 id (없으면 '')
    day: str = ""                   # 그날로 정한 날짜 ISO 'YYYY-MM-DD' (없으면 '')
    order: int = 0
    created: str = ""
    done_at: str = ""               # 끝낸 시각 ISO — 끝낸 할 일을 그 주에 남겨 보이기용
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])

    @property
    def day_date(self) -> date | None:
        try:
            return date.fromisoformat(self.day) if self.day else None
        except ValueError:
            return None

    @property
    def done_date(self) -> date | None:
        try:
            return datetime.fromisoformat(self.done_at).date() if self.done_at else None
        except ValueError:
            return None

    @property
    def created_date(self) -> date | None:
        try:
            return datetime.fromisoformat(self.created).date() if self.created else None
        except ValueError:
            return None


def todo_sort_key(t: Todo):
    return (t.order, t.created, t.id)


class TodoStore:
    """할 일 저장소. subscribe()로 변경 알림 (EventStore와 같은 규약)."""

    _shared: dict = {}

    def __init__(self, base_dir: str, store_dir: str = "store"):
        self.path = os.path.join(base_dir, store_dir, "todos.json")
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        self._todos: list[Todo] = []
        self._listeners: list = []
        self._load()

    @classmethod
    def shared(cls, base_dir: str) -> "TodoStore":
        """같은 폴더면 같은 저장소 하나를 함께 쓴다 (창끼리 실시간 동기화)."""
        key = os.path.abspath(base_dir)
        st = cls._shared.get(key)
        if st is None:
            st = cls._shared[key] = cls(base_dir)
        return st

    # ── 알림 ────────────────────────────────────────────────
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

    # ── 파일 ────────────────────────────────────────────────
    def _load(self) -> None:
        try:
            with open(self.path, encoding="utf-8") as f:
                raw = json.load(f)
            known = set(Todo.__dataclass_fields__)
            self._todos = [Todo(**{k: v for k, v in t.items() if k in known})
                           for t in raw if isinstance(t, dict) and t.get("title")]
        except (FileNotFoundError, json.JSONDecodeError, TypeError, AttributeError):
            self._todos = []

    def _save(self) -> None:
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump([asdict(t) for t in self._todos], f,
                      ensure_ascii=False, indent=1)
        os.replace(tmp, self.path)
        self._notify()

    # ── 읽기 ────────────────────────────────────────────────
    def all(self) -> list[Todo]:
        return sorted(self._todos, key=todo_sort_key)

    def get(self, todo_id: str) -> Todo | None:
        return next((t for t in self._todos if t.id == todo_id), None)

    def for_event(self, event_id: str) -> list[Todo]:
        return [t for t in self.all() if event_id and t.event_id == event_id]

    def for_day(self, d: date) -> list[Todo]:
        return [t for t in self.all() if t.day_date == d]

    # ── 쓰기 ────────────────────────────────────────────────
    def add(self, title: str, event_id: str = "", day: date | None = None) -> Todo | None:
        title = (title or "").strip()
        if not title:
            return None
        order = max((t.order for t in self._todos), default=0) + 1
        t = Todo(title=title, event_id=event_id or "",
                 day=day.isoformat() if day else "", order=order,
                 created=datetime.now().isoformat(timespec="seconds"))
        self._todos.append(t)
        self._save()
        return t

    def update(self, todo_id: str, **fields) -> None:
        t = self.get(todo_id)
        if t is None:
            return
        for k, v in fields.items():
            if hasattr(t, k):
                setattr(t, k, v)
        self._save()

    def toggle(self, todo_id: str, done: bool | None = None) -> None:
        t = self.get(todo_id)
        if t is None:
            return
        t.done = (not t.done) if done is None else bool(done)
        t.done_at = datetime.now().isoformat(timespec="seconds") if t.done else ""
        self._save()

    def remove(self, todo_id: str) -> None:
        self._todos = [t for t in self._todos if t.id != todo_id]
        self._save()
