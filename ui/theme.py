# -*- coding: utf-8 -*-
"""공용 테마 — COOL-비서 딥 네이비 (MD3 톤), 라이트 모드 고정.

디자인 토큰(2026-07-22 v1.3 프리미엄 신뢰 무드):
- 팔레트: 딥 네이비 프라이머리(#006699/#004d75) + 옅은 회청 배경(#f9f9fc).
  강조는 중립 슬레이트, 포인트는 시그니처 오렌지('오늘'). 보라 폐기.
- 모서리 4단(6/10/16/20 — 넉넉한 라운드), 타이포 5단+, 간격 4배수
- 카드는 무테 + 은은한 그림자(make_shadow)로 분리
- 색은 전부 이 파일의 상수로 (하드코딩 hex 금지)
- 눌림 피드백(:pressed)은 배경 한 단계 어둡게 + 1px 하강(레이아웃 시프트 없음)
- 그림자는 make_shadow(parent, level) 한 함수로 통일
"""

# ── 색상 (MD3 시안 매핑) ──────────────────────────────
PRIMARY = "#006699"             # primary-container — 주요 버튼·활성
PRIMARY_DARK = "#004d75"        # primary — 제목·강조 글자
PRIMARY_PRESSED = "#003f5e"     # 버튼 눌림
PRIMARY_LIGHT = "#cce5ff"       # primary-fixed — 연한 파랑 배경·칩
LIGHT_PRESSED = "#b3d7f5"       # 연파랑 눌림(텍스트/아이콘 버튼)
BG = "#f9f9fc"                  # background
CARD = "#ffffff"                # surface-container-lowest
CARD_TINT = "#f3f3f6"           # surface-container-low (hover·에디터 배경)
BORDER = "#d3dae2"              # outline-variant(연화)
BORDER_SUBTLE = "#e6eaef"       # 아주 옅은 hairline — 카드 내부 구분·데스크위젯
TEXT = "#1a1c1e"                # on-surface
SUBTLE = "#40484f"              # on-surface-variant — 보조 글자
DANGER = "#ba1a1a"              # error
DANGER_FG = "#93000a"           # on-error-container(중요도 '높음' 등)
DANGER_BG = "#ffdad6"           # error-container
DANGER_PRESSED = "#f5c2bc"      # 삭제류 눌림
SUCCESS_BG = "#e9f7ec"
SUCCESS_BORDER = "#bfe5c8"
SUCCESS_FG = "#2e7d32"          # 등록됨 초록 글자
SUCCESS_SEL = "#dff0e2"         # 등록됨 + 선택 배경
SUNDAY = "#d05a5a"              # 일요일 빨강(차분하게)
ACCENT = "#4a5b6e"              # 중립 슬레이트 — 은은한 강조(보라 폐기, v1.3)
ACCENT_BG = "#eef1f5"           # 아주 연한 회청 강조 배경
SIGNATURE = "#f59300"           # 시그니처 '쿨쿠리 오렌지' — 부리색.
                                # 네이비의 보색 포인트: '오늘'·캐릭터 강조 전용
SIGNATURE_BG = "#fff1dd"        # 시그니처 연한 배경
SIGNATURE_SOFT = "#ffe0c2"      # 파스텔 주황 — 달력 선택 날짜 배경(아주 연하게)
SIGNATURE_DARK = "#a96800"      # 시그니처 진한 글자용 (연한 배경 위)
LOW_FG = "#40484f"              # 중요도 '낮음' 글자 (on-surface-variant)
LOW_BG = "#eeeef0"              # 중요도 '낮음' 배경 (surface-container)
DISABLED_BG = "#9cbcd1"        # 비활성 네이비 버튼
SCROLL_HANDLE = "#c0c7d0"      # 스크롤바 핸들 (outline-variant)
TOAST_BG = "#2f3133"           # 토스트 어두운 배경 (inverse-surface)
TOAST_ACTION = "#90cdff"       # 토스트 액션 글자 (inverse-primary)
TOAST_ACTION_HOVER = "#bfe0ff"

# ── 모서리 4단 (v1.3 프리미엄: 넉넉한 라운드) ─────────
RADIUS_SM = 6      # 칩·인라인 소형 버튼·리스트 항목
RADIUS_MD = 10     # 입력칸·버튼·토스트·열(column)
RADIUS_LG = 16     # 카드·말풍선
RADIUS_XL = 20     # 창·대형 카드 (시안의 20~24px 감성)

# ── 타이포 5단 ────────────────────────────────────────
FONT_XS = 11       # 힌트·메타·칩
FONT_SM = 12       # 보조 라벨·작은 버튼
FONT_MD = 13       # 본문 기본
FONT_LG = 15       # 섹션 헤더
FONT_XL = 18       # 창 제목
FONT_XXL = 22      # 큰 헤드라인(업데이트 진행 등)
FONT_HERO = 26     # 히어로 헤드라인(안내문구 보정 첫 화면)

# ── 간격 (4의 배수) ──────────────────────────────────
SPACE_XS = 4
SPACE_SM = 8
SPACE_MD = 12
SPACE_LG = 16


def _check_icon_path() -> str:
    """체크박스 ✓용 흰색 SVG를 임시 폴더에 만들어 QSS url로 쓴다.

    (QSS는 data: URI를 지원하지 않아 파일이 필요. 전역 스타일시트가 걸리면
    Qt가 기본 인디케이터를 못 그리므로 직접 정의해야 한다.)
    """
    import os
    import tempfile
    path = os.path.join(tempfile.gettempdir(), "coolm_check.svg")
    if not os.path.exists(path):
        svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
               '<path d="M9 16.2 4.8 12l-1.4 1.4L9 19 21 7l-1.4-1.4z" '
               'fill="white"/></svg>')
        with open(path, "w", encoding="utf-8") as f:
            f.write(svg)
    return path.replace("\\", "/")


def make_shadow(parent, level: int = 1):
    """카드/팝오버용 표준 그림자. level 1=가벼움(팝오버·말풍선), 2=창 카드."""
    from PyQt6.QtGui import QColor
    from PyQt6.QtWidgets import QGraphicsDropShadowEffect
    # v1.3: 더 크고 부드럽고 옅게 — 프리미엄 calm (테두리 대신 그림자로 분리)
    blur, dy, alpha = {1: (20, 4, 38), 2: (34, 8, 30)}[level]
    s = QGraphicsDropShadowEffect(parent)
    s.setBlurRadius(blur)
    s.setOffset(0, dy)
    s.setColor(QColor(20, 40, 70, alpha))   # 짙은 네이비 그림자(중립)
    return s


BASE_QSS = f"""
* {{ font-family:'Malgun Gothic','Segoe UI',sans-serif; }}
QWidget {{ background:{BG}; color:{TEXT}; font-size:{FONT_MD}px; }}
QLabel {{ background:transparent; }}
QToolTip {{ background:{TEXT}; color:white; border:none;
    border-radius:{RADIUS_SM}px; padding:5px 9px; font-size:{FONT_SM}px; }}
QLineEdit, QDateTimeEdit, QComboBox {{
    background:{CARD}; color:{TEXT};
    border:1px solid {BORDER}; border-radius:{RADIUS_MD}px; padding:7px 9px;
    selection-background-color:{PRIMARY}; selection-color:white; }}
QLineEdit:focus, QDateTimeEdit:focus, QComboBox:focus {{
    border:1px solid {PRIMARY}; padding:7px 9px; }}
QTextEdit {{ background:{CARD}; color:{TEXT};
    border:1px solid {BORDER}; border-radius:{RADIUS_MD}px; padding:8px;
    selection-background-color:{PRIMARY}; selection-color:white; }}
QTextEdit:focus {{ border:1px solid {PRIMARY}; }}
QComboBox::drop-down {{ border:none; width:22px; }}
QComboBox QAbstractItemView {{
    background:{CARD}; color:{TEXT}; border:1px solid {BORDER};
    selection-background-color:{PRIMARY_LIGHT}; selection-color:{PRIMARY_DARK}; }}
QCheckBox, QRadioButton {{ background:transparent; spacing:{SPACE_SM}px;
    color:{TEXT}; }}
QCheckBox::indicator {{ width:18px; height:18px; border:1.5px solid {BORDER};
    border-radius:5px; background:{CARD}; }}
QCheckBox::indicator:hover {{ border-color:{PRIMARY}; }}
QCheckBox::indicator:checked {{ background:{PRIMARY}; border-color:{PRIMARY};
    image:url("{_check_icon_path()}"); }}
QCheckBox::indicator:checked:hover {{ background:{PRIMARY_DARK}; }}
QRadioButton::indicator {{ width:18px; height:18px;
    border:1.5px solid {BORDER}; border-radius:10px; background:{CARD}; }}
QRadioButton::indicator:hover {{ border-color:{PRIMARY}; }}
QRadioButton::indicator:checked {{ border:2px solid {PRIMARY};
    background:qradialgradient(cx:0.5, cy:0.5, radius:0.5, fx:0.5, fy:0.5,
        stop:0 {PRIMARY}, stop:0.55 {PRIMARY}, stop:0.65 {CARD},
        stop:1 {CARD}); }}
QTextBrowser {{ background:{CARD_TINT}; color:{TEXT};
    border:1px solid {BORDER}; border-radius:{RADIUS_MD}px; padding:8px; }}
QPushButton {{ background:{CARD}; color:{PRIMARY_DARK};
    border:1px solid {BORDER}; border-radius:{RADIUS_MD}px; padding:7px 14px; }}
QPushButton:hover {{ background:{PRIMARY_LIGHT}; border-color:{PRIMARY}; }}
QPushButton:pressed {{ background:{LIGHT_PRESSED}; border-color:{PRIMARY_DARK};
    padding:8px 14px 6px 14px; }}
QScrollArea {{ border:none; background:transparent; }}
QScrollBar:vertical {{ background:transparent; width:10px; margin:2px; }}
QScrollBar::handle:vertical {{ background:{SCROLL_HANDLE}; border-radius:5px; min-height:30px; }}
QScrollBar::handle:vertical:hover {{ background:{PRIMARY}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height:0; }}
QListWidget {{ background:{CARD}; border:1px solid {BORDER};
    border-radius:{RADIUS_MD}px; padding:4px; }}
QListWidget::item {{ padding:7px; border-radius:{RADIUS_SM}px; }}
QListWidget::item:selected {{ background:{PRIMARY_LIGHT}; color:{PRIMARY_DARK}; }}
QTabWidget::pane {{ border:none; background:{BG}; }}
QTabBar::tab {{ background:transparent; color:{SUBTLE};
    padding:9px 20px; border:none; font-weight:bold; font-size:{FONT_MD}px; }}
QTabBar::tab:selected {{ color:{PRIMARY_DARK}; border-bottom:3px solid {PRIMARY}; }}
QSplitter::handle {{ background:{BG}; }}
"""

# 파란 배경의 주요 액션 버튼
PRIMARY_BTN = (
    f"QPushButton{{background:{PRIMARY};color:white;border:none;"
    f"border-radius:{RADIUS_MD}px;padding:9px 18px;font-weight:bold}}"
    f"QPushButton:hover{{background:{PRIMARY_DARK}}}"
    f"QPushButton:pressed{{background:{PRIMARY_PRESSED};"
    f"padding:10px 18px 8px 18px}}"
    f"QPushButton:disabled{{background:{DISABLED_BG};color:white}}")

# 테두리 없는 파란 텍스트 버튼
TEXT_BTN = (
    f"QPushButton{{background:transparent;color:{PRIMARY_DARK};border:none;"
    f"padding:6px 10px;font-weight:bold;border-radius:{RADIUS_SM}px}}"
    f"QPushButton:hover{{background:{PRIMARY_LIGHT}}}"
    f"QPushButton:pressed{{background:{LIGHT_PRESSED};"
    f"padding:7px 10px 5px 10px}}")

# 다이얼로그 헤더 라벨 (5종 창이 공유) — 밑줄 없이 크기·여백으로 위계
DIALOG_HEADER = (
    f"font-size:{FONT_XL}px;font-weight:bold;color:{PRIMARY_DARK};"
    f"background:transparent;border:none;padding:2px 0 6px 0")

# 섹션 위 작은 라벨 (시안의 uppercase label 대응 — 자간 살린 회색 소제목)
SECTION_LABEL = (
    f"font-size:{FONT_XS}px;font-weight:bold;color:{SUBTLE};"
    f"letter-spacing:1px;background:transparent")

# 제목 입력칸 — 등록·간편등록·일정추가 창의 한 줄 바 공용
TITLE_EDIT = (
    f"QLineEdit{{font-size:{FONT_LG}px;font-weight:bold;background:{CARD};"
    f"border:1px solid {BORDER};border-radius:{RADIUS_MD}px;padding:9px 11px}}"
    f"QLineEdit:focus{{border:2px solid {PRIMARY};padding:8px 10px}}")

# 개인정보 경고 라벨 — 빨간 알약
WARN_LABEL = (
    f"color:{DANGER};font-size:{FONT_XS}px;font-weight:bold;"
    f"background:{DANGER_BG};border-radius:{RADIUS_SM}px;padding:5px")

# 달력 위젯 — 테두리 없는 플랫 스타일
CALENDAR_QSS = f"""
QCalendarWidget {{ background:{CARD}; border:none; }}
QCalendarWidget QWidget#qt_calendar_navigationbar {{
    background:{CARD}; border:none; padding:6px; }}
QCalendarWidget QToolButton {{ background:transparent; color:{PRIMARY_DARK};
    font-weight:bold; font-size:{FONT_LG}px; border-radius:{RADIUS_MD}px; padding:6px 14px; }}
QCalendarWidget QToolButton:hover {{ background:{PRIMARY_LIGHT}; }}
QCalendarWidget QToolButton::menu-indicator {{ image:none; }}
QCalendarWidget QMenu {{ background:{CARD}; color:{TEXT}; }}
QCalendarWidget QSpinBox {{ background:{CARD}; color:{TEXT}; }}
QCalendarWidget QAbstractItemView {{ background:{CARD}; color:{TEXT};
    border:none; outline:0; font-size:{FONT_MD}px;
    selection-background-color:{SIGNATURE}; selection-color:white; }}
"""

# 시스템 팝업 통일 — main.py에서 app.setStyleSheet로 전역 적용.
# ⚠ QMessageBox/QMenu 셀렉터만 담는다 — QWidget 전역 규칙을 넣으면
#   반투명 데스크위젯(WA_TranslucentBackground) 배경을 덮어 회귀함.
SYSTEM_QSS = f"""
QMessageBox {{ background:{CARD}; }}
QMessageBox QLabel {{ color:{TEXT}; font-size:{FONT_MD}px; background:transparent; }}
QMessageBox QPushButton {{ background:{CARD}; color:{PRIMARY_DARK};
    border:1px solid {BORDER}; border-radius:{RADIUS_MD}px;
    padding:6px 16px; font-weight:bold; min-width:64px; }}
QMessageBox QPushButton:hover {{ background:{PRIMARY_LIGHT}; border-color:{PRIMARY}; }}
QMessageBox QPushButton:default {{ background:{PRIMARY}; color:white; border:none; }}
QMenu {{ background:{CARD}; color:{TEXT}; border:1px solid {BORDER};
    border-radius:{RADIUS_MD}px; padding:4px; }}
QMenu::item {{ padding:6px 18px; border-radius:{RADIUS_SM}px; }}
QMenu::item:selected {{ background:{PRIMARY_LIGHT}; color:{PRIMARY_DARK}; }}
"""

# 포스트잇 위젯 (은은한 노란 메모지)
POSTIT_BG = "#fff9e6"
POSTIT_BORDER = "#f0e0b0"
POSTIT_HEADER = "#8a7a45"

# 중요도 색상 (글자색, 연한 배경색)
PRIORITY_COLORS = {
    "높음": (DANGER_FG, DANGER_BG),
    "보통": (PRIMARY_DARK, PRIMARY_LIGHT),
    "낮음": (LOW_FG, LOW_BG),
}


def priority_chip(priority: str) -> str:
    """중요도 칩 스타일 — 색 점(●) + 중립 알약 (색 배경 대신 점만 색).

    점은 아이콘(dot_icon)이나 리치텍스트 ●로 그린다 — 칩 자체는
    옅은 회색 알약이라 카드가 알록달록해지지 않는다.
    """
    return (f"background:{CARD_TINT};color:{TEXT};"
            f"border:1px solid {BORDER};border-radius:11px;"
            f"padding:2px 10px;font-size:{FONT_XS}px;font-weight:bold")
