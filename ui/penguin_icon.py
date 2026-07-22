# -*- coding: utf-8 -*-
"""펭귄 캐릭터 '쿨쿠리' 아이콘 — 상황별 무드 SVG.

- base: 손 흔드는 기본 쿨쿠리 (assets/penguin.png가 있으면 그걸 우선 사용)
- sleep: 옆으로 누워 자는 모습 — 오늘 일정이 없을 때 (자고 있으면 안심!)
- work: 노트북으로 받아 적는 모습 — 간편 등록 창
- surprise: 놀란 모습 — 밀린 일 알림 말풍선

무드 표시는 config "character_mode"(설정 → 일반 → 기능)로 켜고 끈다.
"""
from __future__ import annotations

import os

from PyQt6.QtCore import Qt, QByteArray
from PyQt6.QtGui import QPixmap, QPainter
from PyQt6.QtSvg import QSvgRenderer

_BODY = "#1d1f24"
_ORANGE = "#f5a623"

# 손 흔드는 미니멀 펭귄 (검정 몸통, 흰 배, 주황 부리·발)
PENGUIN_SVG = f"""
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 120">
  <ellipse cx="52" cy="66" rx="38" ry="48" fill="{_BODY}"/>
  <ellipse cx="52" cy="78" rx="24" ry="30" fill="#ffffff"/>
  <circle cx="38" cy="42" r="12" fill="#ffffff"/>
  <circle cx="66" cy="42" r="12" fill="#ffffff"/>
  <circle cx="40" cy="44" r="5" fill="{_BODY}"/>
  <circle cx="64" cy="44" r="5" fill="{_BODY}"/>
  <path d="M42 56 Q52 66 62 56 Q52 62 42 56 Z" fill="{_ORANGE}"/>
  <ellipse cx="52" cy="57" rx="10" ry="6" fill="{_ORANGE}"/>
  <path d="M14 52 Q2 38 12 28 Q20 22 26 34 L20 56 Z" fill="{_BODY}"/>
  <path d="M90 66 Q100 74 94 88 Q88 96 82 86 Z" fill="{_BODY}"/>
  <ellipse cx="40" cy="112" rx="10" ry="5" fill="{_ORANGE}"/>
  <ellipse cx="64" cy="112" rx="10" ry="5" fill="{_ORANGE}"/>
</svg>
"""

# 옆으로 누워 자는 쿨쿠리 + Zz (레퍼런스 '잠자기' 포즈)
SLEEP_SVG = f"""
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 100">
  <ellipse cx="58" cy="70" rx="46" ry="26" fill="{_BODY}"/>
  <ellipse cx="66" cy="74" rx="30" ry="17" fill="#ffffff"/>
  <circle cx="26" cy="62" r="20" fill="{_BODY}"/>
  <path d="M14 58 Q20 64 26 58" stroke="#ffffff" stroke-width="3"
        fill="none" stroke-linecap="round"/>
  <path d="M28 62 Q34 68 40 62" stroke="#ffffff" stroke-width="3"
        fill="none" stroke-linecap="round"/>
  <ellipse cx="22" cy="70" rx="7" ry="4" fill="{_ORANGE}"/>
  <ellipse cx="104" cy="82" rx="8" ry="4" fill="{_ORANGE}"/>
  <ellipse cx="96" cy="88" rx="8" ry="4" fill="{_ORANGE}"/>
  <path d="M58 22 h16 l-16 14 h16" stroke="#6aa9e9" stroke-width="5"
        fill="none" stroke-linecap="round" stroke-linejoin="round"/>
  <path d="M86 8 h11 l-11 10 h11" stroke="#9cc3ef" stroke-width="4"
        fill="none" stroke-linecap="round" stroke-linejoin="round"/>
</svg>
"""

# 노트북으로 받아 적는 쿨쿠리 (레퍼런스 '작업중' 포즈)
WORK_SVG = f"""
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 120">
  <ellipse cx="50" cy="60" rx="36" ry="44" fill="{_BODY}"/>
  <circle cx="38" cy="40" r="11" fill="#ffffff"/>
  <circle cx="62" cy="40" r="11" fill="#ffffff"/>
  <circle cx="40" cy="43" r="5" fill="{_BODY}"/>
  <circle cx="60" cy="43" r="5" fill="{_BODY}"/>
  <ellipse cx="50" cy="54" rx="9" ry="5" fill="{_ORANGE}"/>
  <path d="M16 62 Q8 74 18 82 L30 74 Z" fill="{_BODY}"/>
  <path d="M84 62 Q92 74 82 82 L70 74 Z" fill="{_BODY}"/>
  <path d="M22 78 L78 78 L84 106 L16 106 Z" fill="#aab4bf"/>
  <rect x="14" y="104" width="72" height="7" rx="3.5" fill="#8f9aa6"/>
  <circle cx="50" cy="92" r="4" fill="#e8ecf1"/>
</svg>
"""

# 놀란 쿨쿠리 — 부리가 벌어지고 !! (레퍼런스 '놀람' 포즈)
SURPRISE_SVG = f"""
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 120">
  <ellipse cx="48" cy="66" rx="38" ry="48" fill="{_BODY}"/>
  <ellipse cx="48" cy="80" rx="24" ry="28" fill="#ffffff"/>
  <circle cx="34" cy="42" r="13" fill="#ffffff"/>
  <circle cx="62" cy="42" r="13" fill="#ffffff"/>
  <circle cx="36" cy="44" r="6" fill="{_BODY}"/>
  <circle cx="60" cy="44" r="6" fill="{_BODY}"/>
  <ellipse cx="48" cy="60" rx="8" ry="9" fill="{_ORANGE}"/>
  <ellipse cx="48" cy="61" rx="4.5" ry="5.5" fill="#c97d0e"/>
  <path d="M10 56 Q0 44 8 34 L20 44 Z" fill="{_BODY}"/>
  <path d="M86 56 Q96 44 88 34 L76 44 Z" fill="{_BODY}"/>
  <ellipse cx="36" cy="112" rx="10" ry="5" fill="{_ORANGE}"/>
  <ellipse cx="60" cy="112" rx="10" ry="5" fill="{_ORANGE}"/>
  <path d="M84 10 L90 26" stroke="{_ORANGE}" stroke-width="6"
        stroke-linecap="round"/>
  <circle cx="92" cy="36" r="3.5" fill="{_ORANGE}"/>
  <path d="M96 6 L100 18" stroke="{_ORANGE}" stroke-width="4"
        stroke-linecap="round"/>
</svg>
"""

_MOODS = {"base": PENGUIN_SVG, "sleep": SLEEP_SVG,
          "work": WORK_SVG, "surprise": SURPRISE_SVG}
_cache: dict = {}


def penguin_pixmap(base_dir: str, size: int = 44,
                   mood: str = "base") -> QPixmap:
    """쿨쿠리 픽스맵. mood=base일 때만 assets/penguin.png 대체를 허용."""
    if mood == "base":
        custom = os.path.join(base_dir, "assets", "penguin.png")
        if os.path.exists(custom):
            pm = QPixmap(custom)
            if not pm.isNull():
                return pm.scaled(size, size,
                                 Qt.AspectRatioMode.KeepAspectRatio,
                                 Qt.TransformationMode.SmoothTransformation)
    key = (mood, size)
    if key in _cache:
        return _cache[key]
    renderer = QSvgRenderer(
        QByteArray(_MOODS.get(mood, PENGUIN_SVG).encode()))
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    renderer.render(p)
    p.end()
    _cache[key] = pm
    return pm
