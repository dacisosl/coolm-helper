# -*- coding: utf-8 -*-
"""미니 위젯용 펭귄 아이콘.

assets/penguin.png 파일이 있으면 그걸 쓰고, 없으면 내장 SVG 펭귄을 그린다.
(나중에 원하는 이미지를 assets\\penguin.png로 넣기만 하면 자동 교체된다)
"""
from __future__ import annotations

import os

from PyQt6.QtCore import Qt, QByteArray
from PyQt6.QtGui import QPixmap, QPainter
from PyQt6.QtSvg import QSvgRenderer

# 손 흔드는 미니멀 펭귄 (검정 몸통, 흰 배, 주황 부리·발)
PENGUIN_SVG = """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 120">
  <ellipse cx="52" cy="66" rx="38" ry="48" fill="#1d1f24"/>
  <ellipse cx="52" cy="78" rx="24" ry="30" fill="#ffffff"/>
  <circle cx="38" cy="42" r="12" fill="#ffffff"/>
  <circle cx="66" cy="42" r="12" fill="#ffffff"/>
  <circle cx="40" cy="44" r="5" fill="#1d1f24"/>
  <circle cx="64" cy="44" r="5" fill="#1d1f24"/>
  <path d="M42 56 Q52 66 62 56 Q52 62 42 56 Z" fill="#f5a623"/>
  <ellipse cx="52" cy="57" rx="10" ry="6" fill="#f5a623"/>
  <path d="M14 52 Q2 38 12 28 Q20 22 26 34 L20 56 Z" fill="#1d1f24"/>
  <path d="M90 66 Q100 74 94 88 Q88 96 82 86 Z" fill="#1d1f24"/>
  <ellipse cx="40" cy="112" rx="10" ry="5" fill="#f5a623"/>
  <ellipse cx="64" cy="112" rx="10" ry="5" fill="#f5a623"/>
</svg>
"""


def penguin_pixmap(base_dir: str, size: int = 44) -> QPixmap:
    custom = os.path.join(base_dir, "assets", "penguin.png")
    if os.path.exists(custom):
        pm = QPixmap(custom)
        if not pm.isNull():
            return pm.scaled(size, size,
                             Qt.AspectRatioMode.KeepAspectRatio,
                             Qt.TransformationMode.SmoothTransformation)
    renderer = QSvgRenderer(QByteArray(PENGUIN_SVG.encode()))
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    renderer.render(p)
    p.end()
    return pm
