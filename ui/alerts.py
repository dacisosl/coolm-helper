# -*- coding: utf-8 -*-
"""시작 알림 — 말풍선 하나로 차례대로 보여주고 클릭하면 넘어간다.

프로그램을 켤 때 딱 한 번만 뜬다 (앱 수준 플래그로 보장).
"""
from __future__ import annotations

from datetime import date

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QFrame, QGraphicsDropShadowEffect, QLabel, QVBoxLayout, QWidget,
)

from store.event_store import EventStore
from ui import theme


def build_alerts(store: EventStore, today: date | None = None) -> list[str]:
    """마감 알림(3일/1일 전) → 오늘 할일 순서로 알림 문구를 만든다."""
    today = today or date.today()
    alerts: list[str] = []
    for e in store.all():
        if e.is_deadline and not e.done:
            days_left = (e.start_dt.date() - today).days
            if days_left in (3, 1):
                alerts.append(f"⏰ 마감 {days_left}일 전\n{e.title}")
    n = len(store.on_date(today))
    if n:
        alerts.append(f"📋 오늘 일정이 {n}건 있습니다")
    return alerts


class AlertBubble(QWidget):
    """앵커 위젯 위에 뜨는 말풍선. 클릭하면 다음 알림, 끝나면 사라진다."""

    def __init__(self, alerts: list[str], anchor: QWidget):
        super().__init__(None, Qt.WindowType.Tool
                         | Qt.WindowType.FramelessWindowHint
                         | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.alerts = alerts
        self.anchor = anchor
        self.idx = 0
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 10)
        card = QFrame()
        card.setObjectName("bubble")
        card.setStyleSheet(
            f"#bubble{{background:{theme.CARD};border:2px solid {theme.PRIMARY};"
            f"border-radius:12px}}")
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(16)
        shadow.setOffset(0, 3)
        shadow.setColor(QColor(30, 136, 229, 80))
        card.setGraphicsEffect(shadow)
        outer.addWidget(card)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(12, 9, 12, 9)
        lay.setSpacing(3)
        self.text = QLabel()
        self.text.setWordWrap(True)
        self.text.setStyleSheet(
            f"color:{theme.TEXT};font-size:12px;font-weight:bold;"
            f"background:transparent")
        lay.addWidget(self.text)
        self.hint = QLabel()
        self.hint.setStyleSheet(
            f"color:{theme.SUBTLE};font-size:10px;background:transparent")
        lay.addWidget(self.hint)
        self._sync()

    def _sync(self) -> None:
        self.text.setText(self.alerts[self.idx])
        remain = len(self.alerts) - self.idx - 1
        self.hint.setText(f"클릭하면 {'다음 알림' if remain else '닫기'} "
                          f"({self.idx + 1}/{len(self.alerts)})")
        self.adjustSize()
        self.reposition()

    def reposition(self) -> None:
        """앵커 위에 오른쪽 정렬로 배치 (펭귄 머리 위 / 위젯 위)."""
        if self.anchor is None or not self.anchor.isVisible():
            return
        x = self.anchor.x() + self.anchor.width() - self.width()
        y = self.anchor.y() - self.height() - 2
        self.move(max(0, x), max(0, y))

    def mousePressEvent(self, ev) -> None:
        self.idx += 1
        if self.idx >= len(self.alerts):
            self.close()
        else:
            self._sync()


def show_startup_alerts(widget) -> None:
    """앱 세션당 한 번만 알림 말풍선을 띄운다. widget = WidgetBase 인스턴스."""
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance()
    if getattr(app, "_coolm_alerts_shown", False):
        return
    app._coolm_alerts_shown = True
    alerts = build_alerts(widget.store)
    if not alerts:
        return
    bubble = AlertBubble(alerts, widget)
    widget._alert_bubble = bubble          # GC 방지
    bubble.show()
