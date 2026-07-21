# -*- coding: utf-8 -*-
"""SVG 아이콘 세트 — 이모지 대신 어느 PC에서나 똑같이 보이는 아이콘.

Material Icons 경로(Apache 2.0)를 기반으로 이모지(⚡🗓💬⚙📅)와 최대한
비슷한 색·모양으로 구성했다.
"""
from __future__ import annotations

from PyQt6.QtCore import QByteArray, Qt, QSize
from PyQt6.QtGui import QIcon, QPainter, QPixmap
from PyQt6.QtSvg import QSvgRenderer

_PATHS = {
    # ⚡ 번개 (노랑)
    "bolt": ('<path d="M11 21h-1l1-7H7.5c-.58 0-.57-.32-.38-.66.19-.34.05-.08'
             '.07-.12C8.48 10.94 10.42 7.54 13 3h1l-1 7h3.5c.49 0 .56.33.47'
             '.51l-.07.15C12.96 17.55 11 21 11 21z" fill="#f5a623"/>'),
    # 📅 쪽지 목록 (파랑, 받은함 모양)
    "inbox": ('<path d="M19 3H4.99c-1.1 0-1.98.9-1.98 2L3 19c0 1.1.89 2 '
              '1.99 2H19c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm0 12h-4c0 1.66'
              '-1.35 3-3 3s-3-1.34-3-3H4.99V5H19v10z" fill="#1e88e5"/>'),
    # 🗓 캘린더 (파랑)
    "calendar": ('<path d="M17 12h-5v5h5v-5zM16 1v2H8V1H6v2H5c-1.11 0-1.99'
                 '.9-1.99 2L3 19c0 1.1.89 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1'
                 '-.9-2-2-2h-1V3h-2zm3 18H5V8h14v11z" fill="#1e88e5"/>'),
    # 💬 말풍선 (파랑)
    "chat": ('<path d="M20 2H4c-1.1 0-1.99.9-1.99 2L2 22l4-4h14c1.1 0 2-.9 '
             '2-2V4c0-1.1-.9-2-2-2z" fill="#42a5f5"/>'),
    # ⚙ 톱니 (회색)
    "gear": ('<path d="M19.14 12.94c.04-.3.06-.61.06-.94 0-.32-.02-.64-.07'
             '-.94l2.03-1.58c.18-.14.23-.41.12-.61l-1.92-3.32c-.12-.22-.37'
             '-.29-.59-.22l-2.39.96c-.5-.38-1.03-.7-1.62-.94l-.36-2.54c-.04'
             '-.24-.24-.41-.48-.41h-3.84c-.24 0-.43.17-.47.41l-.36 2.54c'
             '-.59.24-1.13.57-1.62.94l-2.39-.96c-.22-.08-.47 0-.59.22L2.74 '
             '8.87c-.12.21-.08.47.12.61l2.03 1.58c-.05.3-.09.63-.09.94s.02'
             '.64.07.94l-2.03 1.58c-.18.14-.23.41-.12.61l1.92 3.32c.12.22'
             '.37.29.59.22l2.39-.96c.5.38 1.03.7 1.62.94l.36 2.54c.05.24'
             '.24.41.48.41h3.84c.24 0 .44-.17.47-.41l.36-2.54c.59-.24 1.13'
             '-.56 1.62-.94l2.39.96c.22.08.47 0 .59-.22l1.92-3.32c.12-.22'
             '.07-.47-.12-.61l-2.01-1.58zM12 15.6c-1.98 0-3.6-1.62-3.6-3.6'
             's1.62-3.6 3.6-3.6 3.6 1.62 3.6 3.6-1.62 3.6-3.6 3.6z" '
             'fill="#78859a"/>'),
    # 🔧 편집 모드 (회색 렌치, Material build 모양)
    "tools": ('<path d="M22.7 19l-9.1-9.1c.9-2.3.4-5-1.5-6.9-2-2-5-2.4-7.4'
              '-1.3L9 6 6 9 1.6 4.7C.4 7.1.9 10.1 2.9 12.1c1.9 1.9 4.6 2.4 '
              '6.9 1.5l9.1 9.1c.4.4 1 .4 1.4 0l2.3-2.3c.5-.4.5-1.1.1-1.4z" '
              'fill="#78859a"/>'),
    # ▦ 바탕화면 위젯 (파랑, grid_view 모양)
    "widgets": ('<path d="M3 3h8v8H3V3zm10 0h8v8h-8V3zM3 13h8v8H3v-8zm10 0'
                'h8v8h-8v-8z" fill="#1e88e5"/>'),
    # ★ 즐겨찾기 (노랑)
    "star": ('<path d="M12 17.27 18.18 21l-1.64-7.03L22 9.24l-7.19-.61L12 '
             '2 9.19 8.63 2 9.24l5.46 4.73L5.82 21z" fill="#f5a623"/>'),
}

_cache: dict = {}


def svg(name: str) -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
            f'{_PATHS[name]}</svg>')


def icon(name: str, size: int = 22) -> QIcon:
    key = (name, size)
    if key in _cache:
        return _cache[key]
    renderer = QSvgRenderer(QByteArray(svg(name).encode()))
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    renderer.render(p)
    p.end()
    ic = QIcon(pm)
    _cache[key] = ic
    return ic


ICON_SIZE = QSize(22, 22)
