# -*- coding: utf-8 -*-
"""? 도움말 점 — 클릭하면 설명 말풍선이 뜬다 (호버 툴팁도 유지).

툴팁은 마우스를 정확히 올려 기다려야만 보여서 놓치기 쉽다는
피드백(2026-07-22) — 누르면 바로 뜨는 말풍선으로 전 화면 통일.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QLabel, QPushButton, QVBoxLayout

from ui import theme


class HelpDot(QPushButton):
    """제목 옆 둥근 ? 버튼. 클릭 → 아래에 설명 말풍선 (밖을 누르면 닫힘)."""

    def __init__(self, text: str, parent=None):
        super().__init__("?", parent)
        self._text = text
        self.setFixedSize(16, 16)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(text)              # 호버로도 여전히 보인다
        self.setStyleSheet(
            f"QPushButton{{background:{theme.PRIMARY_LIGHT};"
            f"color:{theme.PRIMARY_DARK};border:none;border-radius:8px;"
            f"font-size:{theme.FONT_XS}px;font-weight:bold;padding:0}}"
            f"QPushButton:hover{{background:{theme.PRIMARY};color:white}}"
            f"QPushButton:pressed{{background:{theme.PRIMARY_DARK};"
            f"color:white}}")
        self.clicked.connect(self._show_bubble)

    def _show_bubble(self) -> None:
        pop = QFrame(None, Qt.WindowType.Popup
                     | Qt.WindowType.FramelessWindowHint)
        pop.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        pop.setStyleSheet(
            f"QFrame{{background:{theme.TOAST_BG};"
            f"border-radius:{theme.RADIUS_MD}px}}")
        lay = QVBoxLayout(pop)
        lay.setContentsMargins(12, 9, 12, 9)
        lab = QLabel(self._text)
        lab.setWordWrap(True)
        lab.setMaximumWidth(300)
        lab.setStyleSheet(
            f"color:white;font-size:{theme.FONT_SM}px;background:transparent")
        lay.addWidget(lab)
        pop.adjustSize()
        # 점 바로 아래, 화면 밖으로 나가지 않게
        g = self.mapToGlobal(self.rect().bottomLeft())
        scr = self.screen().availableGeometry()
        x = min(max(scr.left() + 4, g.x() - 8), scr.right() - pop.width() - 4)
        y = g.y() + 6
        if y + pop.height() > scr.bottom():
            y = self.mapToGlobal(self.rect().topLeft()).y() - pop.height() - 6
        pop.move(x, y)
        pop.show()
