# -*- coding: utf-8 -*-
"""토스트 — 창 하단에 잠깐 떴다 사라지는 알림 (되돌리기 버튼 지원).

emil 원칙: 아래서 살짝 올라오며 페이드 인, 소멸은 더 빠른 페이드 아웃,
마우스를 올려두면 타이머를 멈춰 되돌리기를 누를 시간을 준다.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton

from ui import theme
from ui import motion


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
            btn.clicked.connect(lambda: (on_action and on_action(), self._dismiss()))
            lay.addWidget(btn)
        self.adjustSize()
        self.move((parent.width() - self.width()) // 2,
                  parent.height() - self.height() - 18)
        self.show()
        self.raise_()
        motion.slide_fade_in(self, dy=8, ms=200)

        self._remaining = msec
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._dismiss)
        self._timer.start(msec)

    # 마우스를 올려두면 타이머 정지(되돌리기 누를 시간), 떼면 재개
    def enterEvent(self, ev):
        if self._timer.isActive():
            self._remaining = self._timer.remainingTime()
            self._timer.stop()
        super().enterEvent(ev)

    def leaveEvent(self, ev):
        if not getattr(self, "_closing", False):
            self._timer.start(max(600, self._remaining))
        super().leaveEvent(ev)

    def _dismiss(self) -> None:
        self._timer.stop()
        # 그림자 없는 자식 위젯이라 opacity 효과 안전
        if getattr(self, "_closing", False):
            return
        self._closing = True
        if not motion.is_enabled():
            self.close()
            return
        from PyQt6.QtCore import QPropertyAnimation, QEasingCurve
        from PyQt6.QtWidgets import QGraphicsOpacityEffect
        eff = self.graphicsEffect()
        if not isinstance(eff, QGraphicsOpacityEffect):
            eff = QGraphicsOpacityEffect(self)
            self.setGraphicsEffect(eff)
        a = QPropertyAnimation(eff, b"opacity", self)
        a.setDuration(150)
        a.setStartValue(1.0)
        a.setEndValue(0.0)
        a.setEasingCurve(QEasingCurve.Type.OutCubic)
        a.finished.connect(self.close)
        self._fade = a
        a.start()


def show_toast(parent, text: str, action_text: str | None = None,
               on_action=None, msec: int = 5000) -> Toast:
    return Toast(parent, text, action_text, on_action, msec)
