# -*- coding: utf-8 -*-
"""즐겨찾기 보관함 (store/favorites.json) — 전부 로컬.

용도: 중요하거나 반복되는 내용을 제목 붙여 모아두고 계속 보는 보관함.
"""
from __future__ import annotations

import json
import os
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime


@dataclass
class Favorite:
    title: str
    content: str = ""
    created: str = ""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])


class FavStore:
    def __init__(self, base_dir: str, store_dir: str = "store"):
        self.path = os.path.join(base_dir, store_dir, "favorites.json")
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        self._items: list[Favorite] = []
        self._listeners: list = []
        self._load()

    def subscribe(self, callback) -> None:
        self._listeners.append(callback)

    def unsubscribe(self, callback) -> None:
        if callback in self._listeners:
            self._listeners.remove(callback)

    def _load(self) -> None:
        try:
            with open(self.path, encoding="utf-8") as f:
                self._items = [Favorite(**x) for x in json.load(f)]
        except (FileNotFoundError, json.JSONDecodeError, TypeError):
            self._items = []

    def _save(self) -> None:
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump([asdict(x) for x in self._items], f,
                      ensure_ascii=False, indent=1)
        os.replace(tmp, self.path)
        for cb in list(self._listeners):
            try:
                cb()
            except RuntimeError:
                self._listeners.remove(cb)

    def add(self, title: str, content: str = "") -> Favorite:
        fav = Favorite(title=title, content=content,
                       created=datetime.now().isoformat())
        self._items.insert(0, fav)          # 최신이 위로
        self._save()
        return fav

    def update(self, fav_id: str, title: str, content: str) -> None:
        for x in self._items:
            if x.id == fav_id:
                x.title, x.content = title, content
        self._save()

    def remove(self, fav_id: str) -> None:
        self._items = [x for x in self._items if x.id != fav_id]
        self._save()

    def all(self) -> list[Favorite]:
        return list(self._items)
