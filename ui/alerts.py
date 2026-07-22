# -*- coding: utf-8 -*-
"""시작 알림 — 말풍선 하나로 차례대로 보여주고 클릭하면 넘어간다.

프로그램을 켤 때 딱 한 번만 뜬다 (앱 수준 플래그로 보장).
"""
from __future__ import annotations

from datetime import date

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame, QLabel, QVBoxLayout, QWidget,
)

from store.event_store import EventStore
from ui import theme


def build_alerts(store: EventStore, today: date | None = None,
                 days: tuple = (3, 1)) -> list[str]:
    """마감 알림(N일 전, 설정 가능) → 오늘 할일 순서로 알림 문구를 만든다."""
    today = today or date.today()
    alerts: list[str] = []
    for e in store.all():
        if e.is_deadline and not e.done:
            days_left = (e.start_dt.date() - today).days
            if days_left in days:
                alerts.append(f"⏰ 마감 {days_left}일 전\n{e.title}")
    n = len(store.on_date(today))
    if n:
        alerts.append(f"📋 오늘 일정 {n}건")
    return alerts


class AlertBubble(QWidget):
    """앵커 위젯 위에 뜨는 말풍선. 클릭하면 다음 알림, 끝나면 사라진다."""

    def __init__(self, alerts: list[str], anchor: QWidget, on_done=None):
        super().__init__(None, Qt.WindowType.Tool
                         | Qt.WindowType.FramelessWindowHint
                         | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.alerts = alerts
        self.anchor = anchor
        self.on_done = on_done
        self._popped = False
        self.idx = 0
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 10)
        card = QFrame()
        card.setObjectName("bubble")
        card.setStyleSheet(
            f"#bubble{{background:{theme.CARD};border:2px solid {theme.PRIMARY};"
            f"border-radius:{theme.RADIUS_LG}px}}")
        card.setGraphicsEffect(theme.make_shadow(self, 1))
        outer.addWidget(card)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(12, 9, 12, 9)
        lay.setSpacing(3)
        body = QHBoxLayout()
        body.setSpacing(8)
        # 놀란 쿨쿠리 — 알림이 있다는 걸 캐릭터가 대신 말해준다
        if getattr(anchor, "config", {}).get("character_mode", True):
            from ui.penguin_icon import penguin_pixmap
            base_dir = getattr(anchor, "base_dir", "")
            kookuri = QLabel()
            kookuri.setPixmap(penguin_pixmap(base_dir, 38, "surprise"))
            kookuri.setStyleSheet("background:transparent")
            body.addWidget(kookuri, alignment=Qt.AlignmentFlag.AlignTop)
        self.text = QLabel()
        self.text.setWordWrap(True)
        self.text.setStyleSheet(
            f"color:{theme.TEXT};font-size:12px;font-weight:bold;"
            f"background:transparent")
        body.addWidget(self.text, stretch=1)
        lay.addLayout(body)
        self.hint = QLabel()
        self.hint.setStyleSheet(
            f"color:{theme.SUBTLE};font-size:10px;background:transparent")
        lay.addWidget(self.hint)
        self._sync()

    def _sync(self) -> None:
        # 'N건'·'N일 전' 같은 숫자는 빨간 배경+흰 글씨로 강조해 눈에 띄게
        import html
        import re
        esc = html.escape(self.alerts[self.idx]).replace("\n", "<br>")
        esc = re.sub(
            r"(\d+건|\d+일 전)",
            rf'<span style="background-color:{theme.DANGER};color:white;'
            r'font-weight:bold;">&nbsp;\1&nbsp;</span>', esc)
        self.text.setTextFormat(Qt.TextFormat.RichText)
        self.text.setText(esc)
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

    def showEvent(self, ev):
        super().showEvent(ev)
        if not self._popped:          # 첫 등장만 살짝 올라오며 페이드
            self._popped = True
            from ui import motion
            motion.pop_in(self, ms=200, rise=6)

    def mousePressEvent(self, ev) -> None:
        self.idx += 1
        if self.idx >= len(self.alerts):
            self.close()
            if self.on_done:
                self.on_done()
        else:
            self._sync()


INTRO_STEPS = [
    "👋 반가워요! 쿨메신저에서 쪽지를 보다가\n"
    "⚡(바로 등록)를 누르면 그 쪽지가 일정이 돼요.\n"
    "펭귄을 더블클릭해도 열립니다.",
    "🗓 등록한 일정은 캘린더에서\n확인하고 수정할 수 있어요.\n"
    "중요도가 '높음'인 날은 빨간 배지로 표시돼요.",
    "⚙ 설정에서 즐겨찾기·알림·자동 시작 같은\n기능을 켜고 끌 수 있어요.\n"
    "그럼, 시작해 볼까요?",
]


def show_startup_alerts(widget) -> None:
    """앱 세션당 한 번만 알림 말풍선을 띄운다. widget = WidgetBase 인스턴스.

    첫 실행이면 알림 대신 기능 안내(인트로) 3장을 먼저 보여준다.
    """
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance()
    if getattr(app, "_coolm_alerts_shown", False):
        return
    app._coolm_alerts_shown = True

    if not widget.config.get("intro_done"):
        def finish_intro():
            from parser import pipeline
            widget.config["intro_done"] = True
            pipeline.save_config(widget.base_dir, widget.config)
        bubble = AlertBubble(INTRO_STEPS, widget, on_done=finish_intro)
        widget._alert_bubble = bubble
        bubble.show()
        return

    days = tuple(widget.config.get("alert_days", [3, 1])) or (3, 1)
    alerts = build_alerts(widget.store, days=days)
    # 구 '반절 캘린더' 사용자에게 위젯 개편을 최초 1회만 안내
    if not widget.config.get("desk_migration_notice_done", True):
        alerts.insert(0,
            "🔄 바탕화면 캘린더가 주간·월간 위젯 2개로 바뀌었어요.\n"
            "이제 드래그로 옮기고 모서리를 끌어 크기를 조절할 수 있어요.\n"
            "펭귄 → 위젯 메뉴에서 켜고 끕니다.")
        from parser import pipeline
        widget.config["desk_migration_notice_done"] = True
        pipeline.save_config(widget.base_dir, widget.config)
    if not alerts:
        return
    bubble = AlertBubble(alerts, widget)
    widget._alert_bubble = bubble          # GC 방지
    bubble.show()
