# -*- coding: utf-8 -*-
"""공용 테마 — 쿨메신저 블루 + 화이트, 라이트 모드 고정."""

PRIMARY = "#1e88e5"
PRIMARY_DARK = "#1565c0"
PRIMARY_LIGHT = "#e8f2fd"
BG = "#f4f8fd"
CARD = "#ffffff"
BORDER = "#dce6f2"
TEXT = "#222b36"
SUBTLE = "#78859a"
DANGER = "#e53935"
SUCCESS_BG = "#e9f7ec"
SUCCESS_BORDER = "#bfe5c8"

BASE_QSS = f"""
* {{ font-family:'Malgun Gothic','Segoe UI',sans-serif; }}
QWidget {{ background:{BG}; color:{TEXT}; font-size:13px; }}
QLabel {{ background:transparent; }}
QLineEdit, QDateTimeEdit, QComboBox {{
    background:{CARD}; color:{TEXT};
    border:1px solid {BORDER}; border-radius:8px; padding:6px 8px;
    selection-background-color:{PRIMARY}; selection-color:white; }}
QLineEdit:focus, QDateTimeEdit:focus, QComboBox:focus {{ border:2px solid {PRIMARY}; }}
QComboBox::drop-down {{ border:none; width:22px; }}
QComboBox QAbstractItemView {{
    background:{CARD}; color:{TEXT}; border:1px solid {BORDER};
    selection-background-color:{PRIMARY_LIGHT}; selection-color:{PRIMARY_DARK}; }}
QCheckBox {{ background:transparent; spacing:6px; color:{TEXT}; }}
QTextBrowser {{ background:#fbfdff; color:{TEXT};
    border:1px solid {BORDER}; border-radius:8px; padding:8px; }}
QPushButton {{ background:{CARD}; color:{PRIMARY_DARK};
    border:1px solid {BORDER}; border-radius:8px; padding:7px 14px; }}
QPushButton:hover {{ background:{PRIMARY_LIGHT}; border-color:{PRIMARY}; }}
QScrollArea {{ border:none; background:transparent; }}
QScrollBar:vertical {{ background:transparent; width:10px; margin:2px; }}
QScrollBar::handle:vertical {{ background:#c3d2e5; border-radius:5px; min-height:30px; }}
QScrollBar::handle:vertical:hover {{ background:{PRIMARY}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height:0; }}
QListWidget {{ background:{CARD}; border:1px solid {BORDER};
    border-radius:10px; padding:4px; }}
QListWidget::item {{ padding:7px; border-radius:6px; }}
QListWidget::item:selected {{ background:{PRIMARY_LIGHT}; color:{PRIMARY_DARK}; }}
QTabWidget::pane {{ border:none; background:{BG}; }}
QTabBar::tab {{ background:transparent; color:{SUBTLE};
    padding:9px 20px; border:none; font-weight:bold; font-size:13px; }}
QTabBar::tab:selected {{ color:{PRIMARY_DARK}; border-bottom:3px solid {PRIMARY}; }}
QSplitter::handle {{ background:{BG}; }}
"""

# 파란 배경의 주요 액션 버튼
PRIMARY_BTN = (
    f"QPushButton{{background:{PRIMARY};color:white;border:none;"
    f"border-radius:8px;padding:9px 18px;font-weight:bold}}"
    f"QPushButton:hover{{background:{PRIMARY_DARK}}}"
    f"QPushButton:disabled{{background:#a5c9ef;color:white}}")

# 테두리 없는 파란 텍스트 버튼
TEXT_BTN = (
    f"QPushButton{{background:transparent;color:{PRIMARY_DARK};border:none;"
    f"padding:6px 10px;font-weight:bold}}"
    f"QPushButton:hover{{background:{PRIMARY_LIGHT};border-radius:6px}}")

# 달력 위젯 — 테두리 없는 플랫 스타일
CALENDAR_QSS = f"""
QCalendarWidget {{ background:{CARD}; border:none; }}
QCalendarWidget QWidget#qt_calendar_navigationbar {{
    background:{CARD}; border:none; padding:6px; }}
QCalendarWidget QToolButton {{ background:transparent; color:{PRIMARY_DARK};
    font-weight:bold; font-size:15px; border-radius:8px; padding:6px 14px; }}
QCalendarWidget QToolButton:hover {{ background:{PRIMARY_LIGHT}; }}
QCalendarWidget QToolButton::menu-indicator {{ image:none; }}
QCalendarWidget QMenu {{ background:{CARD}; color:{TEXT}; }}
QCalendarWidget QSpinBox {{ background:{CARD}; color:{TEXT}; }}
QCalendarWidget QAbstractItemView {{ background:{CARD}; color:{TEXT};
    border:none; outline:0; font-size:13px;
    selection-background-color:{PRIMARY}; selection-color:white; }}
"""

# 포스트잇 위젯 (은은한 노란 메모지)
POSTIT_BG = "#fff9e6"
POSTIT_BORDER = "#f0e0b0"
POSTIT_HEADER = "#8a7a45"

# 중요도 색상 (글자색, 연한 배경색)
PRIORITY_COLORS = {
    "높음": ("#c62828", "#fdecea"),
    "보통": (PRIMARY_DARK, PRIMARY_LIGHT),
    "낮음": ("#66738a", "#eef1f5"),
}


def priority_chip(priority: str) -> str:
    """중요도 라벨용 스타일시트."""
    fg, bg = PRIORITY_COLORS.get(priority, PRIORITY_COLORS["보통"])
    return (f"background:{bg};color:{fg};"
            f"border-radius:9px;padding:2px 9px;font-size:11px;font-weight:bold")
