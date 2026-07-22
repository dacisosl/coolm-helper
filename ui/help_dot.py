# -*- coding: utf-8 -*-
"""? 도움말 점 — 클릭하면 설명 모달 창이 뜬다.

말풍선(Popup)은 다른 곳을 누르면 사라져 읽다 놓치기 쉽다는 피드백
(2026-07-22) — [확인]을 눌러 닫는 모달 창으로 전 화면 통일.
호버 툴팁도 여전히 동작한다.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout,
)

from ui import theme


class HelpDot(QPushButton):
    """제목 옆 둥근 ? 버튼. 클릭 → 설명 모달 ([확인]으로 닫기)."""

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
        self.clicked.connect(self._show_modal)

    def _show_modal(self) -> None:
        dlg = QDialog(self.window())
        dlg.setWindowTitle("도움말")
        dlg.setStyleSheet(theme.BASE_QSS + f"QDialog{{background:{theme.BG}}}")
        dlg.setMinimumWidth(320)
        dlg.setMaximumWidth(420)
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(22, 18, 22, 18)
        lay.setSpacing(12)
        lab = QLabel(self._text)
        lab.setWordWrap(True)
        lab.setStyleSheet(
            f"color:{theme.TEXT};font-size:{theme.FONT_MD}px;"
            f"background:transparent;line-height:150%")
        lay.addWidget(lab)
        row = QHBoxLayout()
        row.addStretch()
        ok = QPushButton("확인")
        ok.setStyleSheet(theme.PRIMARY_BTN)
        ok.setCursor(Qt.CursorShape.PointingHandCursor)
        ok.clicked.connect(dlg.accept)
        row.addWidget(ok)
        lay.addLayout(row)
        dlg.exec()
