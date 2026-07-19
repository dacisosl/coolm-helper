# -*- coding: utf-8 -*-
"""바탕화면 캘린더 위젯 — 화면 반절, 항상 다른 창들 아래.

상단: 주간(월~금 + 접힌 토·일) 보기, ◀ ▶ 로 주 이동.
하단: 월간 달력(개수 배지) — 날짜 클릭 시 상세 모달.
투명도는 설정에서 조절. '항상 맨 뒤'라 바탕화면 위젯처럼 동작한다.
"""
from __future__ import annotations

from datetime import date, timedelta

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QDialog, QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea,
    QSplitter, QVBoxLayout, QWidget, QApplication,
)

from store.event_store import Event, EventStore
from ui import theme
from ui.calendar_view import EventCalendar, EventItemCard, WEEKDAY_KO


class DayDetailDialog(QDialog):
    """날짜 클릭 시 뜨는 상세 모달 — 아코디언 카드로 편집·삭제 가능."""

    def __init__(self, store: EventStore, d: date, parent=None):
        super().__init__(parent)
        self.store, self.d = store, d
        self.setWindowTitle(f"{d.month}월 {d.day}일 ({WEEKDAY_KO[d.weekday()]})")
        self.resize(420, 460)
        self.setStyleSheet(theme.BASE_QSS)
        lay = QVBoxLayout(self)
        head = QLabel(f"{d.month}월 {d.day}일 ({WEEKDAY_KO[d.weekday()]})")
        head.setStyleSheet(
            f"font-size:15px;font-weight:bold;color:{theme.PRIMARY_DARK}")
        lay.addWidget(head)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        inner.setStyleSheet(f"background:{theme.BG}")
        self.items_lay = QVBoxLayout(inner)
        self.items_lay.setSpacing(8)
        scroll.setWidget(inner)
        lay.addWidget(scroll)
        close_btn = QPushButton("닫기")
        close_btn.clicked.connect(self.accept)
        lay.addWidget(close_btn)
        self._fill()

    def _fill(self) -> None:
        while self.items_lay.count():
            item = self.items_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        events = self.store.on_date(self.d)
        order = {"높음": 0, "보통": 1, "낮음": 2}
        events.sort(key=lambda e: (order.get(e.priority, 1), e.start))
        if not events:
            empty = QLabel("일정이 없습니다.")
            empty.setStyleSheet(f"color:{theme.SUBTLE}")
            self.items_lay.addWidget(empty)
        for e in events:
            self.items_lay.addWidget(
                EventItemCard(e, self.store,
                              lambda reload_day: QTimer.singleShot(0, self._fill)))
        self.items_lay.addStretch()


class _DayColumn(QFrame):
    """주간 보기의 하루 열."""

    def __init__(self, owner: "DesktopCalendar", d: date, slim: bool = False):
        super().__init__()
        self.owner, self.d = owner, d
        today = d == date.today()
        self.setStyleSheet(
            f"_DayColumn{{background:{theme.PRIMARY_LIGHT if today else theme.CARD};"
            f"border-radius:10px}}")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 6, 8, 6)
        lay.setSpacing(3)
        wd = WEEKDAY_KO[d.weekday()]
        color = ("#e57373" if d.weekday() == 6 else
                 theme.PRIMARY if d.weekday() == 5 else theme.SUBTLE)
        head = QLabel(f"{d.day} ({wd})")
        head.setStyleSheet(f"color:{color};font-size:11px;font-weight:bold;"
                           f"background:transparent")
        lay.addWidget(head)
        events = owner.store.on_date(d)
        order = {"높음": 0, "보통": 1, "낮음": 2}
        events.sort(key=lambda e: (order.get(e.priority, 1), e.start))
        limit = 3 if slim else 6
        for e in events[:limit]:
            fg, bg = theme.PRIORITY_COLORS.get(
                e.priority, theme.PRIORITY_COLORS["보통"])
            t = "" if e.all_day else e.start_dt.strftime("%H:%M ")
            chip = QLabel(f"{t}{e.title[:14]}")
            chip.setStyleSheet(
                f"background:{bg};color:{fg};border-radius:6px;"
                f"padding:2px 6px;font-size:10px")
            lay.addWidget(chip)
        if len(events) > limit:
            more = QLabel(f"+{len(events) - limit}건 더")
            more.setStyleSheet(f"color:{theme.SUBTLE};font-size:10px;"
                               f"background:transparent")
            lay.addWidget(more)
        lay.addStretch()

    def mousePressEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton:
            self.owner.open_day(self.d)


class DesktopCalendar(QWidget):
    """항상 맨 뒤에 깔리는 반화면 캘린더 위젯."""

    def __init__(self, store: EventStore, config: dict):
        super().__init__()
        self.store = store
        self.config = config
        self.setWindowFlags(Qt.WindowType.Tool
                            | Qt.WindowType.FramelessWindowHint
                            | Qt.WindowType.WindowStaysOnBottomHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowOpacity(
            max(40, int(config.get("desktop_widget_opacity", 90))) / 100)
        self._monday = date.today() - timedelta(days=date.today().weekday())
        self._drag = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        card = QFrame()
        card.setObjectName("deskcard")
        card.setStyleSheet(
            theme.BASE_QSS + theme.CALENDAR_QSS
            + f"#deskcard{{background:{theme.BG};border-radius:16px;"
              f"border:1px solid {theme.BORDER}}}")
        outer.addWidget(card)
        root = QVBoxLayout(card)
        root.setContentsMargins(12, 8, 12, 12)

        # 헤더: 주 이동
        head = QHBoxLayout()
        title = QLabel("🗓 주간 일정")
        title.setStyleSheet(
            f"font-size:13px;font-weight:bold;color:{theme.PRIMARY_DARK}")
        head.addWidget(title)
        self.week_label = QLabel()
        self.week_label.setStyleSheet(f"color:{theme.SUBTLE};font-size:12px")
        head.addWidget(self.week_label)
        head.addStretch()
        for text, fn in (("◀", self._prev), ("오늘", self._today), ("▶", self._next)):
            b = QPushButton(text)
            b.setStyleSheet(theme.TEXT_BTN + "QPushButton{font-size:12px}")
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(fn)
            head.addWidget(b)
        root.addLayout(head)

        # 주간 보기 (월~금 + 접힌 토·일)
        self.week_row = QHBoxLayout()
        self.week_row.setSpacing(6)
        root.addLayout(self.week_row, stretch=4)

        # 하단 월간 달력
        self.cal = EventCalendar()
        self.cal.clicked.connect(
            lambda qd: self.open_day(date(qd.year(), qd.month(), qd.day())))
        root.addWidget(self.cal, stretch=5)

        self.refresh()
        store.subscribe(lambda: QTimer.singleShot(0, self.refresh))

    def place_default(self) -> None:
        screen = QApplication.primaryScreen().availableGeometry()
        w = screen.width() // 2
        self.setGeometry(screen.right() - w, screen.top(), w, screen.height())

    # ── 주 이동 ──────────────────────────────────────────────
    def _prev(self) -> None:
        self._monday -= timedelta(days=7)
        self.refresh()

    def _next(self) -> None:
        self._monday += timedelta(days=7)
        self.refresh()

    def _today(self) -> None:
        self._monday = date.today() - timedelta(days=date.today().weekday())
        self.refresh()

    # ── 갱신 ────────────────────────────────────────────────
    def refresh(self) -> None:
        fri = self._monday + timedelta(days=4)
        self.week_label.setText(
            f"{self._monday.month}/{self._monday.day} ~ {fri.month}/{fri.day}")
        while self.week_row.count():
            item = self.week_row.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                sub = item.layout()
                while sub.count():
                    s = sub.takeAt(0)
                    if s.widget():
                        s.widget().deleteLater()
        for i in range(5):                       # 월~금
            self.week_row.addWidget(
                _DayColumn(self, self._monday + timedelta(days=i)), stretch=3)
        weekend = QVBoxLayout()                  # 토·일 접이식 (얇게)
        weekend.setSpacing(6)
        weekend.addWidget(_DayColumn(self, self._monday + timedelta(days=5),
                                     slim=True))
        weekend.addWidget(_DayColumn(self, self._monday + timedelta(days=6),
                                     slim=True))
        self.week_row.addLayout(weekend, stretch=2)

        counts: dict[date, tuple[int, bool]] = {}
        for d in self.store.dates_with_events():
            evs = self.store.on_date(d)
            counts[d] = (len(evs), any(e.priority == "높음" for e in evs))
        self.cal.set_counts(counts)

    def open_day(self, d: date) -> None:
        dlg = DayDetailDialog(self.store, d)
        dlg.setWindowFlags(dlg.windowFlags()
                           | Qt.WindowType.WindowStaysOnTopHint)
        dlg.exec()
