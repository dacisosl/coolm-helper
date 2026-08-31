# -*- coding: utf-8 -*-
"""알림 포스트잇 — 시작할 때 뜨는 알림을 메모지 한 장에 모아 붙인다.

말풍선(AlertBubble)은 클릭할 때마다 한 줄씩 넘어가서, 급한 마감을 보기 전에
실수로 다 넘겨 버리기 쉬웠다. 포스트잇은 알림을 한눈에 펼쳐 두고
사용자가 ✕로 뗄 때까지 화면에 붙어 있는다.

설정 → 일반 → '알림'에서 끄고 켜며, 마감 며칠 전부터 알릴지도 거기서 고른다.
바탕화면 포스트잇(desk_note.py)과 달리 이 메모지는 저장되지 않는다 —
알림용이라 닫으면 그걸로 끝이고, 위치도 기억하지 않는다.
"""
from __future__ import annotations

from datetime import date

from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget,
)

from ui import theme
from ui.alerts import highlight_urgency
from ui.calendar_view import WEEKDAY_KO
from ui.screens import clamp_to_screens

MAX_ITEMS = 6           # 이보다 많으면 메모지가 화면을 덮는다 — 나머지는 한 줄로
MARGIN = 24             # 앵커가 없을 때 화면 가장자리에서 띄울 여백


class AlertNote(QWidget):
    """노란 메모지 한 장. 끌어서 옮기고 ✕로 뗀다."""

    WIDTH = 272

    def __init__(self, alerts: list[str], anchor: QWidget | None = None,
                 on_open=None, today: date | None = None):
        super().__init__(None, Qt.WindowType.Tool
                         | Qt.WindowType.FramelessWindowHint
                         | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.anchor = anchor
        self.on_open = on_open
        self._drag: QPoint | None = None
        self._popped = False
        bg, border, fg = theme.postit_colors("yellow")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 10, 10, 12)    # 그림자 자리
        card = QFrame()
        card.setObjectName("alertnote")
        card.setStyleSheet(
            theme.BASE_QSS
            + f"#alertnote{{background:{bg};"
              f"border:1px solid {border};"
              f"border-radius:{theme.RADIUS_LG}px}}")
        card.setGraphicsEffect(theme.make_shadow(self, 2))
        outer.addWidget(card)

        root = QVBoxLayout(card)
        root.setContentsMargins(14, 10, 10, 12)
        root.setSpacing(8)

        # ── 머리글: 오늘 날짜 + 닫기 ─────────────────────────
        head = QHBoxLayout()
        head.setSpacing(6)
        d = today or date.today()
        when = QLabel(f"🐧 {d.month}월 {d.day}일 ({WEEKDAY_KO[d.weekday()]}) 알림")
        when.setStyleSheet(
            f"color:{fg};font-size:11px;font-weight:bold;background:transparent")
        head.addWidget(when)
        head.addStretch()
        close_btn = QPushButton("✕")
        close_btn.setToolTip("알림 떼기")
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet(
            f"QPushButton{{background:transparent;border:none;"
            f"color:{fg};font-size:12px;padding:0 4px}}"
            f"QPushButton:hover{{color:{theme.DANGER}}}")
        close_btn.clicked.connect(self.dismiss)
        head.addWidget(close_btn)
        root.addLayout(head)

        # ── 알림 목록 ────────────────────────────────────────
        shown = alerts[:MAX_ITEMS]
        for i, text in enumerate(shown):
            if i:
                line = QFrame()
                line.setFixedHeight(1)
                line.setStyleSheet(f"background:{border};border:none")
                root.addWidget(line)
            item = QLabel()
            item.setTextFormat(Qt.TextFormat.RichText)
            item.setText(highlight_urgency(text))
            item.setWordWrap(True)
            item.setStyleSheet(
                f"color:{theme.TEXT};font-size:12px;font-weight:bold;"
                f"background:transparent")
            root.addWidget(item)
        if len(alerts) > MAX_ITEMS:
            more = QLabel(f"… 그리고 {len(alerts) - MAX_ITEMS}건 더")
            more.setStyleSheet(
                f"color:{fg};font-size:11px;background:transparent")
            root.addWidget(more)

        # ── 바닥: 캘린더 바로가기 + 안내 ─────────────────────
        foot = QHBoxLayout()
        foot.setSpacing(6)
        if on_open is not None:
            cal = QPushButton("🗓 캘린더 열기")
            cal.setCursor(Qt.CursorShape.PointingHandCursor)
            cal.setStyleSheet(
                f"QPushButton{{background:transparent;border:1px solid {border};"
                f"border-radius:{theme.RADIUS_MD}px;color:{fg};"
                f"font-size:11px;padding:4px 10px}}"
                f"QPushButton:hover{{border-color:{theme.SIGNATURE};"
                f"color:{theme.SIGNATURE_DARK}}}")
            cal.clicked.connect(self._open_calendar)
            foot.addWidget(cal)
        foot.addStretch()
        hint = QLabel("끌어서 옮기기")
        hint.setStyleSheet(
            f"color:{theme.SUBTLE};font-size:10px;background:transparent")
        foot.addWidget(hint)
        root.addLayout(foot)

        self.setFixedWidth(self.WIDTH)
        self.adjustSize()

    # ── 자리잡기 ────────────────────────────────────────────
    def place(self) -> None:
        """펭귄 위쪽에 붙인다. 펭귄이 없으면 화면 오른쪽 아래."""
        anchor = self.anchor
        if anchor is not None and anchor.isVisible():
            x = anchor.x() + anchor.width() - self.width()
            y = anchor.y() - self.height() - 6
        else:
            from PyQt6.QtWidgets import QApplication
            app = QApplication.instance()
            scr = app.primaryScreen() if app else None
            if scr is None:
                return
            g = scr.availableGeometry()
            x = g.right() - self.width() - MARGIN
            y = g.bottom() - self.height() - MARGIN
        self.move(clamp_to_screens(QPoint(x, y), self.size()))

    # ── 동작 ────────────────────────────────────────────────
    def _open_calendar(self) -> None:
        if self.on_open is not None:
            try:
                self.on_open()
            except Exception:
                pass            # 캘린더가 안 열려도 알림은 조용히 닫힌다
        self.dismiss()

    def dismiss(self) -> None:
        from ui import motion
        motion.fade_out_close(self, ms=120)

    # ── 드래그 이동 ─────────────────────────────────────────
    def mousePressEvent(self, ev) -> None:
        if ev.button() == Qt.MouseButton.LeftButton:
            self._drag = ev.globalPosition().toPoint() - self.pos()

    def mouseMoveEvent(self, ev) -> None:
        if self._drag is None:
            return
        cursor = ev.globalPosition().toPoint()
        self.move(clamp_to_screens(cursor - self._drag, self.size(), cursor))

    def mouseReleaseEvent(self, ev) -> None:
        self._drag = None

    def showEvent(self, ev):
        super().showEvent(ev)
        if not self._popped:            # 첫 등장만 살짝 올라오며 페이드
            self._popped = True
            from ui import motion
            motion.pop_in(self, ms=200, rise=8)
