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
# 정장 비서 리디자인 팔레트 (2026-07-23 사용자 레퍼런스 반영)
_BEAK_D = "#d9861a"    # 부리 음영
_SHIRT = "#f4f6f9"     # 흰 셔츠
_TIE = "#274060"       # 넥타이(네이비)
_SUIT = "#23262c"      # 재킷 라펠(살짝 밝은 검정)
_CHEEK = "#f2a9b4"     # 볼 발그레

# 정장 입고 태블릿(달력) 든 쿨비서 — '비서' 정체성 (레퍼런스 반영)
PENGUIN_SVG = f"""
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 132">
  <ellipse cx="46" cy="120" rx="12" ry="6.5" fill="{_ORANGE}"/>
  <ellipse cx="74" cy="120" rx="12" ry="6.5" fill="{_ORANGE}"/>
  <ellipse cx="60" cy="70" rx="44" ry="50" fill="{_BODY}"/>
  <path d="M60 64 L78 82 L74 116 L46 116 L42 82 Z" fill="{_SHIRT}"/>
  <path d="M60 68 l5 7 l-5 30 l-5 -30 z" fill="{_TIE}"/>
  <path d="M55 75 l5 -7 l5 7 l-5 5 z" fill="{_TIE}"/>
  <path d="M60 66 L44 74 L52 100 L58 78 Z" fill="{_SUIT}"/>
  <path d="M60 66 L76 74 L68 100 L62 78 Z" fill="{_SUIT}"/>
  <circle cx="48" cy="44" r="13" fill="#ffffff"/>
  <circle cx="72" cy="44" r="13" fill="#ffffff"/>
  <circle cx="50" cy="46" r="5.2" fill="{_BODY}"/>
  <circle cx="70" cy="46" r="5.2" fill="{_BODY}"/>
  <circle cx="51.6" cy="44.4" r="1.6" fill="#ffffff"/>
  <circle cx="71.6" cy="44.4" r="1.6" fill="#ffffff"/>
  <path d="M39 33 L55 39" stroke="{_BODY}" stroke-width="4.2"
        fill="none" stroke-linecap="round"/>
  <path d="M81 33 L65 39" stroke="{_BODY}" stroke-width="4.2"
        fill="none" stroke-linecap="round"/>
  <path d="M51 52 Q60 50 69 52 L60 63 Z" fill="{_ORANGE}"/>
  <path d="M51 52 Q60 55 69 52" stroke="{_BEAK_D}" stroke-width="1.4" fill="none"/>
  <path d="M18 66 Q6 80 16 96 Q24 104 30 92 L28 68 Z" fill="{_BODY}"/>
  <g transform="rotate(-13 92 96)">
    <rect x="72" y="78" width="42" height="32" rx="4" fill="#2b3440"/>
    <rect x="75" y="81" width="36" height="26" rx="2" fill="#eef3f8"/>
    <rect x="75" y="81" width="36" height="6" rx="2" fill="#3f7fc4"/>
    <g fill="#c7d5e6">
      <rect x="78" y="90" width="5" height="4" rx="1"/>
      <rect x="86" y="90" width="5" height="4" rx="1"/>
      <rect x="94" y="90" width="5" height="4" rx="1"/>
      <rect x="102" y="90" width="5" height="4" rx="1"/>
      <rect x="78" y="97" width="5" height="4" rx="1"/>
      <rect x="86" y="97" width="5" height="4" rx="1"/>
      <rect x="102" y="97" width="5" height="4" rx="1"/>
    </g>
    <rect x="94" y="97" width="5" height="4" rx="1" fill="{_ORANGE}"/>
    <rect x="78" y="103" width="5" height="3" rx="1" fill="#c7d5e6"/>
    <rect x="86" y="103" width="5" height="3" rx="1" fill="#c7d5e6"/>
  </g>
  <path d="M96 70 Q108 78 100 92 L84 86 Z" fill="{_BODY}"/>
</svg>
"""

# 정장 입고 책상에 앉아 자는 쿨비서 (할 일 없을 때) — 감은 눈·하품 부리·
# 발그레 볼·커피잔·오른쪽 위로 커지는 Z z z (레퍼런스 반영)
SLEEP_SVG = f"""
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 132">
  <ellipse cx="48" cy="122" rx="12" ry="6.5" fill="{_ORANGE}"/>
  <ellipse cx="72" cy="122" rx="12" ry="6.5" fill="{_ORANGE}"/>
  <ellipse cx="60" cy="74" rx="43" ry="46" fill="{_BODY}"/>
  <path d="M60 70 L76 86 L72 116 L48 116 L44 86 Z" fill="{_SHIRT}"/>
  <path d="M60 74 l4 6 l-4 24 l-4 -24 z" fill="{_TIE}"/>
  <path d="M60 66 L46 76 L54 98 L58 80 Z" fill="{_SUIT}"/>
  <path d="M60 66 L74 76 L66 98 L62 80 Z" fill="{_SUIT}"/>
  <circle cx="49" cy="50" r="13" fill="#ffffff"/>
  <circle cx="71" cy="50" r="13" fill="#ffffff"/>
  <ellipse cx="40" cy="56" rx="6" ry="4" fill="{_CHEEK}" opacity="0.9"/>
  <ellipse cx="80" cy="56" rx="6" ry="4" fill="{_CHEEK}" opacity="0.9"/>
  <path d="M42 50 Q49 58 56 50" stroke="{_BODY}" stroke-width="3.2"
        fill="none" stroke-linecap="round"/>
  <path d="M64 50 Q71 58 78 50" stroke="{_BODY}" stroke-width="3.2"
        fill="none" stroke-linecap="round"/>
  <path d="M52 55 Q60 51 68 55 Q66 66 60 68 Q54 66 52 55 Z" fill="{_ORANGE}"/>
  <ellipse cx="60" cy="61" rx="3.2" ry="4.2" fill="#7a3b12"/>
  <rect x="10" y="96" width="20" height="16" rx="3" fill="#e8ecf1"/>
  <path d="M30 100 q8 0 8 6 t-8 6" fill="none" stroke="#c3cbd6" stroke-width="2.5"/>
  <ellipse cx="20" cy="97" rx="9" ry="3" fill="#6b4a2b"/>
  <path d="M74 34 h7.5 l-7.5 8 h7.5" stroke="{_BODY}" stroke-width="3"
        fill="none" stroke-linecap="round" stroke-linejoin="round"/>
  <path d="M86 22 h8.5 l-8.5 9 h8.5" stroke="{_BODY}" stroke-width="3.4"
        fill="none" stroke-linecap="round" stroke-linejoin="round"/>
  <path d="M99 9 h10 l-10 10 h10" stroke="{_BODY}" stroke-width="3.9"
        fill="none" stroke-linecap="round" stroke-linejoin="round"/>
</svg>
"""

# 정장 입고 노트북에 받아 적는 쿨비서 (간편 등록 창)
WORK_SVG = f"""
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 120">
  <ellipse cx="50" cy="60" rx="36" ry="44" fill="{_BODY}"/>
  <circle cx="38" cy="40" r="11" fill="#ffffff"/>
  <circle cx="62" cy="40" r="11" fill="#ffffff"/>
  <circle cx="40" cy="42" r="5" fill="{_BODY}"/>
  <circle cx="60" cy="42" r="5" fill="{_BODY}"/>
  <circle cx="41.2" cy="40.6" r="1.5" fill="#ffffff"/>
  <circle cx="61.2" cy="40.6" r="1.5" fill="#ffffff"/>
  <path d="M30 31 L44 36" stroke="{_BODY}" stroke-width="3.6" stroke-linecap="round"/>
  <path d="M70 31 L56 36" stroke="{_BODY}" stroke-width="3.6" stroke-linecap="round"/>
  <path d="M43 48 Q50 46 57 48 L50 57 Z" fill="{_ORANGE}"/>
  <path d="M50 58 L60 66 L58 79 L42 79 L40 66 Z" fill="{_SHIRT}"/>
  <path d="M50 60 l3 5 l-3 12 l-3 -12 z" fill="{_TIE}"/>
  <path d="M50 58 L41 65 L46 78 Z" fill="{_SUIT}"/>
  <path d="M50 58 L59 65 L54 78 Z" fill="{_SUIT}"/>
  <path d="M16 62 Q8 74 18 82 L30 74 Z" fill="{_BODY}"/>
  <path d="M84 62 Q92 74 82 82 L70 74 Z" fill="{_BODY}"/>
  <path d="M22 80 L78 80 L84 106 L16 106 Z" fill="#aab4bf"/>
  <rect x="14" y="104" width="72" height="7" rx="3.5" fill="#8f9aa6"/>
  <circle cx="50" cy="93" r="4" fill="#e8ecf1"/>
</svg>
"""

# 정장 입고 놀란 쿨비서 — 부리 벌어지고 ! (밀린 일 알림 말풍선)
SURPRISE_SVG = f"""
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 110 122">
  <ellipse cx="52" cy="70" rx="40" ry="48" fill="{_BODY}"/>
  <path d="M52 64 L70 82 L66 116 L38 116 L34 82 Z" fill="{_SHIRT}"/>
  <path d="M52 68 l5 7 l-5 28 l-5 -28 z" fill="{_TIE}"/>
  <path d="M52 66 L36 74 L44 100 L50 78 Z" fill="{_SUIT}"/>
  <path d="M52 66 L68 74 L60 100 L54 78 Z" fill="{_SUIT}"/>
  <circle cx="38" cy="42" r="14" fill="#ffffff"/>
  <circle cx="66" cy="42" r="14" fill="#ffffff"/>
  <circle cx="39" cy="44" r="6.5" fill="{_BODY}"/>
  <circle cx="65" cy="44" r="6.5" fill="{_BODY}"/>
  <circle cx="41" cy="42" r="2" fill="#ffffff"/>
  <circle cx="67" cy="42" r="2" fill="#ffffff"/>
  <path d="M28 28 L44 33" stroke="{_BODY}" stroke-width="4" stroke-linecap="round"/>
  <path d="M76 28 L60 33" stroke="{_BODY}" stroke-width="4" stroke-linecap="round"/>
  <ellipse cx="52" cy="60" rx="7" ry="8" fill="{_ORANGE}"/>
  <ellipse cx="52" cy="61" rx="3.6" ry="4.6" fill="#7a3b12"/>
  <path d="M90 14 L96 30" stroke="{_ORANGE}" stroke-width="6" stroke-linecap="round"/>
  <circle cx="98" cy="40" r="3.5" fill="{_ORANGE}"/>
</svg>
"""

_MOODS = {"base": PENGUIN_SVG, "sleep": SLEEP_SVG,
          "work": WORK_SVG, "surprise": SURPRISE_SVG}

# 무드별 사용자 이미지 파일 — assets/에 올려두면 SVG 대신 이걸 쓴다.
# (사용자가 직접 그린 펭귄 PNG를 넣을 수 있게, 2026-07-23)
# 각 무드마다 여러 후보 파일명을 순서대로 찾는다(첫 번째로 존재하는 것 사용).
_MOOD_FILES = {
    "base": ("penguin.png", "penguin_base.png"),
    "sleep": ("penguin_sleep.png",),
    "work": ("penguin_work.png",),
    "surprise": ("penguin_surprise.png",),
}
_cache: dict = {}


def penguin_pixmap(base_dir: str, size: int = 44,
                   mood: str = "base") -> QPixmap:
    """쿨비서 픽스맵. assets/에 무드별 이미지가 있으면 그걸, 없으면 SVG."""
    for fname in _MOOD_FILES.get(mood, ()):
        custom = os.path.join(base_dir, "assets", fname)
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
