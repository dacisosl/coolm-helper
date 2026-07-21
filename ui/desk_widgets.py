# -*- coding: utf-8 -*-
"""바탕화면 위젯: 할일 간단판·주간·월간 (v0.10.0).

옛 '반절 캘린더'(desktop_calendar.py)를 대체 — 주간/월간을 따로 띄우고
드래그 이동·크기 조절·위치 저장은 DeskWidgetBase가 담당한다.
DayDetailDialog·_DayColumn은 반절 캘린더에서 이식.
"""
from __future__ import annotations

from datetime import date, timedelta

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QCursor
from PyQt6.QtWidgets import (
    QApplication, QCheckBox, QDialog, QFrame, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from store.event_store import Event, EventStore
from ui import theme
from ui.calendar_view import EventCalendar, EventItemCard, WEEKDAY_KO
from ui.desk_base import DeskWidgetBase

_PRIORITY_ORDER = {"높음": 0, "보통": 1, "낮음": 2}


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
        events.sort(key=lambda e: (_PRIORITY_ORDER.get(e.priority, 1), e.start))
        if not events:
            empty = QLabel("일정이 없습니다.")
            empty.setStyleSheet(f"color:{theme.SUBTLE}")
            self.items_lay.addWidget(empty)
        for e in events:
            self.items_lay.addWidget(
                EventItemCard(e, self.store,
                              lambda reload_day: QTimer.singleShot(0, self._fill)))
        self.items_lay.addStretch()


def open_day_dialog(store: EventStore, d: date) -> None:
    """바탕화면(맨 뒤) 위젯에서 열므로 항상 위로 띄운다."""
    dlg = DayDetailDialog(store, d)
    dlg.setWindowFlags(dlg.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
    dlg.exec()


class EditPopup(QDialog):
    """일정 1건 인라인 편집 팝오버 — EventItemCard를 펼친 채로 담는다.

    좁은 위젯 안에서는 일시·중요도 입력칸이 깨지므로 커서 근처에 띄운다.
    """

    def __init__(self, event: Event, store: EventStore):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.Dialog
                            | Qt.WindowType.WindowStaysOnTopHint)
        self.setWindowTitle("일정 수정")
        self.setStyleSheet(theme.BASE_QSS + f"QDialog{{background:{theme.BG}}}")
        self.setFixedWidth(430)
        lay = QVBoxLayout(self)
        card = EventItemCard(event, store,
                             lambda reload_day: QTimer.singleShot(0, self.accept))
        card.detail.setVisible(True)     # 처음부터 펼친 상태로
        lay.addWidget(card)

    def show_near_cursor(self) -> None:
        pos = QCursor.pos()
        screen = QApplication.primaryScreen().availableGeometry()
        self.adjustSize()
        x = min(max(screen.left(), pos.x() - 40),
                screen.right() - self.width())
        y = min(max(screen.top(), pos.y() + 12),
                screen.bottom() - self.height())
        self.move(x, y)
        self.exec()


def _make_card(widget: DeskWidgetBase, title_text: str,
               extra_qss: str = "") -> tuple[QVBoxLayout, QHBoxLayout]:
    """공통 골격: 투명 여백(리사이즈 감지 영역) 안의 둥근 카드 + 헤더줄.

    헤더 맨 오른쪽에 🔧(편집 모드) 버튼, 그 아래에 편집 도구줄
    (투명도·글씨 크기 — 편집 모드에서만 보임)이 자동으로 붙는다.
    반환: (카드 내부 레이아웃, 헤더 레이아웃 — 🔧 앞에 버튼 추가용)
    """
    outer = QVBoxLayout(widget)
    outer.setContentsMargins(8, 8, 8, 8)
    card = QFrame()
    card.setObjectName("deskcard")
    card.setStyleSheet(
        theme.BASE_QSS + extra_qss
        + f"#deskcard{{background:{theme.BG};border-radius:14px;"
          f"border:1px solid {theme.BORDER}}}")
    outer.addWidget(card)
    root = QVBoxLayout(card)
    root.setContentsMargins(12, 8, 12, 10)
    root.setSpacing(6)
    head = QHBoxLayout()
    title = QLabel(title_text)
    title.setStyleSheet(
        f"font-size:13px;font-weight:bold;color:{theme.PRIMARY_DARK};"
        f"background:transparent")
    head.addWidget(title)
    head.addStretch()
    head.addWidget(widget.make_edit_button())
    root.addLayout(head)
    root.addWidget(widget.build_edit_bar())
    return root, head


# ── ① 할일 간단판 ────────────────────────────────────────────
class _TodoRow(QFrame):
    """간단판의 한 줄 — 체크박스 + 내용 (투두리스트 스타일).

    편집 모드에서는 제목이 입력칸으로 바뀌어 그 자리에서 바로 고친다.
    """

    def __init__(self, event: Event, store: EventStore, show_date: bool,
                 owner: "SimpleTodoWidget"):
        super().__init__()
        self.event, self.store, self.owner = event, store, owner
        fpx = owner.font_px
        self.setStyleSheet(
            f"_TodoRow{{background:{theme.CARD};border-radius:8px}}"
            f"_TodoRow:hover{{background:#fbfdff}}")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 4, 6, 4)
        lay.setSpacing(6)
        # 모든 항목에 체크박스 — 끝낸 일은 체크 (투두리스트처럼)
        cb = QCheckBox()
        cb.setChecked(event.done)
        cb.setToolTip("완료 표시")
        cb.stateChanged.connect(
            lambda st: store.set_done(event.id, bool(st)))
        lay.addWidget(cb)
        fg, _bg = theme.PRIORITY_COLORS.get(
            event.priority, theme.PRIORITY_COLORS["보통"])
        dot = QLabel("●")
        dot.setStyleSheet(
            f"color:{fg};font-size:{fpx(9)}px;background:transparent")
        lay.addWidget(dot)
        done_style = ";text-decoration:line-through" if event.done else ""
        if owner.edit_mode:
            # 인라인 편집: 그 자리에서 제목을 바로 타이핑
            self.title_edit = QLineEdit(event.title)
            self.title_edit.setStyleSheet(
                f"QLineEdit{{background:#fbfdff;border:1px solid "
                f"{theme.BORDER};border-radius:5px;padding:1px 4px;"
                f"font-size:{fpx(12)}px;color:{theme.TEXT}}}")
            self.title_edit.editingFinished.connect(self._save_title)
            lay.addWidget(self.title_edit, stretch=1)
        else:
            title = QLabel(event.title)
            title.setStyleSheet(
                f"font-size:{fpx(12)}px;color:{theme.TEXT};"
                f"background:transparent" + done_style)
            lay.addWidget(title, stretch=1)
        d = event.start_dt
        when = "" if not show_date else f"{d.month}/{d.day}({WEEKDAY_KO[d.weekday()]}) "
        if not event.all_day:
            when += d.strftime("%H:%M")
        if when:
            time_label = QLabel(when.strip())
            time_label.setStyleSheet(
                f"color:{theme.SUBTLE};font-size:{fpx(10)}px;"
                f"background:transparent")
            lay.addWidget(time_label)
        edit = QPushButton("✎")
        edit.setToolTip("자세히 수정 (일시·중요도·메모)")
        edit.setStyleSheet(
            theme.TEXT_BTN + f"QPushButton{{font-size:{fpx(12)}px;padding:2px 6px}}")
        edit.setCursor(Qt.CursorShape.PointingHandCursor)
        edit.clicked.connect(self._edit)
        lay.addWidget(edit)

    def _save_title(self) -> None:
        new = self.title_edit.text().strip()
        if new and new != self.event.title:
            self.store.update(self.event.id, title=new)

    def _edit(self) -> None:
        EditPopup(self.event, self.store).show_near_cursor()

    def mousePressEvent(self, ev):
        # 편집 모드에서는 입력칸이 클릭을 받으므로 여기로 안 온다
        if ev.button() == Qt.MouseButton.LeftButton and not self.owner.edit_mode:
            self._edit()


class SimpleTodoWidget(DeskWidgetBase):
    """밀린 일 / 오늘 할 일 / 앞으로 할 일 — 가장 작은 위젯."""

    MIN_W, MIN_H = 220, 180

    def __init__(self, store, config, base_dir, conf):
        super().__init__(store, config, base_dir, conf)
        root, _head = _make_card(self, "✓ 할 일")
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea{border:none;background:transparent}")
        inner = QWidget()
        inner.setStyleSheet("background:transparent")
        self.items_lay = QVBoxLayout(inner)
        self.items_lay.setContentsMargins(0, 0, 0, 0)
        self.items_lay.setSpacing(4)
        scroll.setWidget(inner)
        root.addWidget(scroll)
        self.refresh()

    def place_default(self) -> None:
        screen = QApplication.primaryScreen().availableGeometry()
        self.resize(280, 320)
        self.move(screen.right() - self.width() - 40, screen.top() + 60)

    def refresh(self) -> None:
        while self.items_lay.count():
            item = self.items_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        fpx = self.font_px
        overdue, today, upcoming = self.store.sections(date.today())
        sections = (("😰 밀린 일", "#c62828", overdue, True),
                    ("📌 오늘", theme.PRIMARY_DARK, today, False),
                    ("🌱 앞으로", "#66738a", upcoming, True))
        for label, color, events, show_date in sections:
            if not events and label != "📌 오늘":
                continue
            head = QLabel(label)
            head.setStyleSheet(
                f"color:{color};font-size:{fpx(11)}px;font-weight:bold;"
                f"background:transparent;padding-top:4px")
            self.items_lay.addWidget(head)
            if not events:
                empty = QLabel("일정이 없어요")
                empty.setStyleSheet(
                    f"color:{theme.SUBTLE};font-size:{fpx(11)}px;"
                    f"background:transparent")
                self.items_lay.addWidget(empty)
            for e in events:
                self.items_lay.addWidget(
                    _TodoRow(e, self.store, show_date, owner=self))
        self.items_lay.addStretch()


# ── ② 주간 일정 ──────────────────────────────────────────────
class _DayColumn(QFrame):
    """주간 보기의 하루 열 (반절 캘린더에서 이식)."""

    def __init__(self, owner: "WeeklyWidget", d: date, slim: bool = False):
        super().__init__()
        self.owner, self.d = owner, d
        today = d == date.today()
        has_events = bool(owner.store.on_date(d))
        # 주말(접힌 열)에 일정이 있으면 강조해서 놓치지 않게 한다
        weekend_accent = slim and has_events
        bg = (theme.PRIMARY_LIGHT if today
              else "#fff8e6" if weekend_accent else theme.CARD)
        border = "#f5a623" if weekend_accent else "transparent"
        self.setStyleSheet(
            f"_DayColumn{{background:{bg};border:1.5px solid {border};"
            f"border-radius:10px}}")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 6, 8, 6)
        lay.setSpacing(3)
        fpx = owner.font_px
        wd = WEEKDAY_KO[d.weekday()]
        color = ("#e57373" if d.weekday() == 6 else
                 theme.PRIMARY if d.weekday() == 5 else theme.SUBTLE)
        head = QLabel(f"{d.day} ({wd})")
        head.setStyleSheet(f"color:{color};font-size:{fpx(11)}px;"
                           f"font-weight:bold;background:transparent")
        lay.addWidget(head)
        events = owner.store.on_date(d)
        events.sort(key=lambda e: (_PRIORITY_ORDER.get(e.priority, 1), e.start))
        limit = 3 if slim else 6
        for e in events[:limit]:
            fg, bg = theme.PRIORITY_COLORS.get(
                e.priority, theme.PRIORITY_COLORS["보통"])
            t = "" if e.all_day else e.start_dt.strftime("%H:%M ")
            chip = QLabel(f"{t}{e.title[:14]}")
            chip.setStyleSheet(
                f"background:{bg};color:{fg};border-radius:6px;"
                f"padding:2px 6px;font-size:{fpx(10)}px")
            lay.addWidget(chip)
        if len(events) > limit:
            more = QLabel(f"+{len(events) - limit}건 더")
            more.setStyleSheet(f"color:{theme.SUBTLE};font-size:{fpx(10)}px;"
                               f"background:transparent")
            lay.addWidget(more)
        lay.addStretch()

    def mousePressEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton:
            open_day_dialog(self.owner.store, self.d)


class WeeklyWidget(DeskWidgetBase):
    """이번 주(월~금 + 접힌 토·일) 보기."""

    MIN_W, MIN_H = 360, 170

    def __init__(self, store, config, base_dir, conf):
        super().__init__(store, config, base_dir, conf)
        self._monday = date.today() - timedelta(days=date.today().weekday())
        root, head = _make_card(self, "🗓 주간 일정")
        self.week_label = QLabel()
        self.week_label.setStyleSheet(
            f"color:{theme.SUBTLE};font-size:12px;background:transparent")
        head.insertWidget(1, self.week_label)
        for text, fn in (("◀", self._prev), ("오늘", self._today), ("▶", self._next)):
            b = QPushButton(text)
            b.setStyleSheet(theme.TEXT_BTN + "QPushButton{font-size:12px}")
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(fn)
            head.insertWidget(head.count() - 1, b)   # 🔧 버튼 앞에
        self.week_row = QHBoxLayout()
        self.week_row.setSpacing(6)
        root.addLayout(self.week_row, stretch=1)
        self.refresh()

    def place_default(self) -> None:
        screen = QApplication.primaryScreen().availableGeometry()
        self.resize(min(560, screen.width() // 2), 240)
        self.move(screen.right() - self.width() - 40, screen.top() + 40)

    def _prev(self) -> None:
        self._monday -= timedelta(days=7)
        self.refresh()

    def _next(self) -> None:
        self._monday += timedelta(days=7)
        self.refresh()

    def _today(self) -> None:
        self._monday = date.today() - timedelta(days=date.today().weekday())
        self.refresh()

    def refresh(self) -> None:
        fri = self._monday + timedelta(days=4)
        self.week_label.setText(
            f"{self._monday.month}/{self._monday.day} ~ {fri.month}/{fri.day}")
        self.week_label.setStyleSheet(
            f"color:{theme.SUBTLE};font-size:{self.font_px(12)}px;"
            f"background:transparent")
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


# ── ③ 월간 달력 ──────────────────────────────────────────────
class MonthlyWidget(DeskWidgetBase):
    """한 달 달력(개수 배지) — 날짜 클릭 시 상세 모달."""

    MIN_W, MIN_H = 260, 240

    def __init__(self, store, config, base_dir, conf):
        super().__init__(store, config, base_dir, conf)
        root, _head = _make_card(self, "📅 월간 달력", extra_qss=theme.CALENDAR_QSS)
        self.cal = EventCalendar()
        self.cal.clicked.connect(
            lambda qd: open_day_dialog(self.store,
                                       date(qd.year(), qd.month(), qd.day())))
        root.addWidget(self.cal, stretch=1)
        self.refresh()

    def place_default(self) -> None:
        screen = QApplication.primaryScreen().availableGeometry()
        self.resize(360, 340)
        self.move(screen.right() - self.width() - 40,
                  screen.bottom() - self.height() - 60)

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        self._apply_cal_font()

    def _apply_cal_font(self) -> None:
        """위젯 크기에 비례한 달력 글씨 (반응형) × 사용자 글씨 배율."""
        pt = max(7, min(13, self.height() // 32))
        pt = max(6, round(pt * self.font_scale() / 100))
        f = self.cal.font()
        if f.pointSize() != pt:
            f.setPointSize(pt)
            self.cal.setFont(f)

    def refresh(self) -> None:
        self._apply_cal_font()
        counts: dict[date, tuple[int, bool]] = {}
        for d in self.store.dates_with_events():
            evs = self.store.on_date(d)
            counts[d] = (len(evs), any(e.priority == "높음" for e in evs))
        self.cal.set_counts(counts)
