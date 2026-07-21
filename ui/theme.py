# -*- coding: utf-8 -*-
"""공용 테마 — 쿨메신저 블루 + 화이트, 라이트 모드 고정.

디자인 토큰(2026-07-21 리마스터, emil-design-eng 기준):
- 모서리 3단(RADIUS_SM/MD/LG), 타이포 5단(FONT_XS~XL), 간격 4배수(SPACE_*)
- 색은 전부 이 파일의 상수로 (하드코딩 hex 금지)
- 눌림 피드백(:pressed)은 배경 한 단계 어둡게 + 1px 하강(레이아웃 시프트 없음)
- 그림자는 make_shadow(parent, level) 한 함수로 통일
"""

# ── 색상 ──────────────────────────────────────────────
PRIMARY = "#1e88e5"
PRIMARY_DARK = "#1565c0"
PRIMARY_PRESSED = "#0d47a1"     # 파란 버튼 눌림
PRIMARY_LIGHT = "#e8f2fd"
PRIMARY_TINT = "rgba(30,136,229,0.10)"   # 반투명 파랑 hover(리스트 행)
LIGHT_PRESSED = "#d8e9fb"       # 연파랑 눌림(텍스트/아이콘 버튼)
BG = "#f4f8fd"
CARD = "#ffffff"
CARD_TINT = "#fbfdff"           # 아주 연한 카드 톤(hover·에디터 배경)
BORDER = "#dce6f2"
TEXT = "#222b36"
SUBTLE = "#78859a"
DANGER = "#e53935"
DANGER_FG = "#c62828"           # 진한 빨강 글자(중요도 '높음' 등)
DANGER_BG = "#fdecea"           # 위험 연한 배경
DANGER_PRESSED = "#f9d9d5"      # 삭제류 눌림
SUCCESS_BG = "#e9f7ec"
SUCCESS_BORDER = "#bfe5c8"
SUCCESS_FG = "#2e7d32"          # 등록됨 초록 글자
SUCCESS_SEL = "#dff0e2"         # 등록됨 + 선택 배경
SUNDAY = "#e57373"              # 일요일 빨강
ACCENT = "#f5a623"             # 강조 노랑(뱃지·주말 강조·아이콘)
ACCENT_BG = "#fff8e6"          # 강조 연노랑 배경
LOW_FG = "#66738a"             # 중요도 '낮음' 글자
LOW_BG = "#eef1f5"             # 중요도 '낮음' 배경
DISABLED_BG = "#a5c9ef"        # 비활성 파란 버튼
SCROLL_HANDLE = "#c3d2e5"      # 스크롤바 핸들
TOAST_BG = "#323a45"           # 토스트 어두운 배경
TOAST_ACTION = "#82c8ff"       # 토스트 액션(되돌리기) 글자
TOAST_ACTION_HOVER = "#b3ddff"

# ── 모서리 3단 ────────────────────────────────────────
RADIUS_SM = 6      # 칩·인라인 소형 버튼·리스트 항목
RADIUS_MD = 10     # 입력칸·버튼·토스트·열(column)
RADIUS_LG = 14     # 카드·창·말풍선

# ── 타이포 5단 ────────────────────────────────────────
FONT_XS = 11       # 힌트·메타·칩
FONT_SM = 12       # 보조 라벨·작은 버튼
FONT_MD = 13       # 본문 기본
FONT_LG = 15       # 섹션 헤더
FONT_XL = 18       # 창 제목

# ── 간격 (4의 배수) ──────────────────────────────────
SPACE_XS = 4
SPACE_SM = 8
SPACE_MD = 12
SPACE_LG = 16


def make_shadow(parent, level: int = 1):
    """카드/팝오버용 표준 그림자. level 1=가벼움(팝오버·말풍선), 2=창 카드."""
    from PyQt6.QtGui import QColor
    from PyQt6.QtWidgets import QGraphicsDropShadowEffect
    blur, dy, alpha = {1: (16, 3, 70), 2: (24, 4, 55)}[level]
    s = QGraphicsDropShadowEffect(parent)
    s.setBlurRadius(blur)
    s.setOffset(0, dy)
    s.setColor(QColor(30, 136, 229, alpha))   # PRIMARY rgb
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
QComboBox::drop-down {{ border:none; width:22px; }}
QComboBox QAbstractItemView {{
    background:{CARD}; color:{TEXT}; border:1px solid {BORDER};
    selection-background-color:{PRIMARY_LIGHT}; selection-color:{PRIMARY_DARK}; }}
QCheckBox {{ background:transparent; spacing:{SPACE_SM}px; color:{TEXT}; }}
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

# 다이얼로그 헤더 라벨 (5종 창이 공유)
DIALOG_HEADER = (
    f"font-size:{FONT_LG}px;font-weight:bold;color:{PRIMARY_DARK};"
    f"background:transparent")

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
    selection-background-color:{PRIMARY}; selection-color:white; }}
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
    """중요도 라벨용 스타일시트."""
    fg, bg = PRIORITY_COLORS.get(priority, PRIORITY_COLORS["보통"])
    return (f"background:{bg};color:{fg};border-radius:{RADIUS_SM}px;"
            f"padding:2px 9px;font-size:{FONT_XS}px;font-weight:bold")
