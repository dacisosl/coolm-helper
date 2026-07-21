# -*- coding: utf-8 -*-
"""토스트 — 창 하단에 잠깐 떴다 사라지는 알림 (되돌리기 버튼 지원)."""
from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton

from ui import theme


class Toast(QFrame):
    def __init__(self, parent, text: str, action_text: str | None = None,
                 on_action=None, msec: int = 5000):
        super().__init__(parent)
        self.setStyleSheet(
            f"Toast{{background:{theme.TOAST_BG};border-radius:{theme.RADIUS_MD}px}}"
            f"QLabel{{color:white;font-size:{theme.FONT_SM}px;background:transparent}}")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 8, 14, 8)
        lay.addWidget(QLabel(text))
        if action_text:
            btn = QPushButton(action_text)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(
                f"QPushButton{{background:transparent;color:{theme.TOAST_ACTION};"
                f"border:none;font-weight:bold;font-size:{theme.FONT_SM}px;"
                f"padding:0 4px}}"
                f"QPushButton:hover{{color:{theme.TOAST_ACTION_HOVER}}}")
            btn.clicked.connect(lambda: (on_action and on_action(), self.close()))
            lay.addWidget(btn)
        self.adjustSize()
        self.move((parent.width() - self.width()) // 2,
                  parent.height() - self.height() - 18)
        self.show()
        self.raise_()
        QTimer.singleShot(msec, self.close)


def show_toast(parent, text: str, action_text: str | None = None,
               on_action=None, msec: int = 5000) -> Toast:
    return Toast(parent, text, action_text, on_action, msec)
