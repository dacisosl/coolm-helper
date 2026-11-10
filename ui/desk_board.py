# -*- coding: utf-8 -*-
"""바탕화면 위젯 '일정 · 할 일 보드' — 체킹(Checking) 리디자인 (2026-11-10).

사용자 요청: 2열 고정, 크기 조절·반응형, 넘치면 위젯 안 스크롤.
사용자 결정: 왼쪽 = 등록한 일정 전부, 오른쪽 = 사용자가 직접 추가하는 할 일
(store/todo_store.py — 일정과 따로 저장).

보기 두 가지(헤더 [표|날짜] 전환, 사용자가 보낸 두 구조):
- 표(기본): 한 줄 = 일정 하나 ↔ 그 일정의 할 일. 맨 아래 '미분류' 줄.
  두 칸이 같은 줄에 맞춰지므로 아무리 좁아도 2열이 의미를 잃지 않는다.
- 날짜: 주의 일~토를 한 줄씩(빈 날도 얇게). 일정 카드 안에 그 할 일이 들어간다.

색: 일정마다 파스텔(theme.BOARD_HUES)을 한 주 안 순서대로 돌려 쓴다 — 이웃
일정끼리 색이 겹치지 않게. 미분류는 회색(theme.BOARD_LOOSE). 오늘은 시그니처 오렌지.
"""
from __future__ import annotations

from datetime import date, timedelta

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QApplication, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QMenu,
    QPushButton, QScrollArea, QSizePolicy, QVBoxLayout, QWidget,
)

from store.event_store import Event, day_sort_key
from store.todo_store import Todo, TodoStore
from ui import theme
from ui.calendar_view import WEEKDAY_KO
from ui.desk_base import DeskWidgetBase
from ui.desk_widgets import EditPopup, _add_event_button, _clear_layout, _make_card

VIEW_TABLE, VIEW_DAYS = "table", "days"
LEFT_STRETCH, RIGHT_STRETCH = 20, 23        # 일정 : 할 일 = 1 : 1.15


# ── 순수 함수 (테스트용) ─────────────────────────────────────
def week_bounds(d: date) -> tuple[date, date]:
    """d가 든 주의 (일요일, 토요일) — 예시 화면의 '11.8 – 11.14'와 같은 일~토."""
    start = d - timedelta(days=(d.weekday() + 1) % 7)
    return start, start + timedelta(days=6)


def week_title(start: date) -> str:
    """'11월 2주차' — 그 주의 목요일이 속한 달·순번 (월말 걸친 주도 한 달에만 속하게)."""
    thu = start + timedelta(days=4)
    return f"{thu.month}월 {(thu.day - 1) // 7 + 1}주차"


def week_range_text(start: date) -> str:
    end = start + timedelta(days=6)
    return f"{start.month}.{start.day} – {end.month}.{end.day}"


def event_span(e: Event) -> tuple[date, date]:
    s = e.start_dt.date()
    return s, (e.end_dt.date() if e.end_dt else s)


def events_in_week(events, start: date) -> list[Event]:
    end = start + timedelta(days=6)
    out = [e for e in events if event_span(e)[0] <= end and event_span(e)[1] >= start]
    return sorted(out, key=lambda e: (event_span(e)[0], day_sort_key(e)))


def hue_map(events) -> dict[str, int]:
    """한 주의 일정 순서대로 색 번호 0..5를 돌려 쓴다."""
    return {e.id: i % len(theme.BOARD_HUES) for i, e in enumerate(events)}


def split_todos(todos, week_events, all_event_ids: set, start: date, today: date):
    """이번 주 화면에 보일 할 일 나누기.

    반환: (일정별 {event_id: [할 일]}, 미분류 [할 일])
    - 이번 주 일정에 연결된 할 일 → 그 일정 줄.
    - 다른 주 일정에 연결된 할 일 → 이번 주엔 안 보임.
    - 연결이 없거나 연결된 일정이 지워진 할 일(= 미분류):
      날짜를 정했으면 그 날짜가 든 주, 끝냈으면 끝낸 날이 든 주,
      아무것도 없으면 '아직 안 끝낸 일'로 보고 오늘이 든 주(이번 주)에 계속 보인다.
    """
    end = start + timedelta(days=6)
    in_week = {e.id for e in week_events}
    by_event: dict[str, list[Todo]] = {e.id: [] for e in week_events}
    loose: list[Todo] = []

    def inside(d):
        return d is not None and start <= d <= end

    for t in todos:
        if t.event_id and t.event_id in all_event_ids:
            if t.event_id in in_week:
                by_event[t.event_id].append(t)
            continue
        if t.day_date is not None:
            keep = inside(t.day_date)
        elif t.done:
            keep = inside(t.done_date or t.created_date)
        else:
            keep = inside(today)
        if keep:
            loose.append(t)
    return by_event, loose


def density(panel_w: int, scale_pct: int = 100) -> str:
    """칸 폭(글씨 배율로 나눈 값)에 따른 압축 단계: normal / compact / tiny."""
    w = panel_w * 100 / max(50, scale_pct)
    if w < 130:
        return "tiny"
    if w < 170:
        return "compact"
    return "normal"


def done_count(todos) -> tuple[int, int]:
    return sum(1 for t in todos if t.done), len(todos)


# ── 조각: 할 일 알약 ─────────────────────────────────────────
class _TodoPill(QFrame):
    """둥근 알약 안에 ○ 체크 + 제목(줄바꿈). 더블클릭 = 그 자리 수정, 우클릭 = 메뉴."""

    def __init__(self, board: "BoardWidget", todo: Todo, hue):
        super().__init__()
        self.board, self.todo, self.hue = board, todo, hue
        fpx, dens = board.font_px, board.dens
        bg, line, ink = hue
        self.setObjectName("pill")
        self.setStyleSheet(
            f"#pill{{background:{theme.CARD};border:1px solid {line};"
            f"border-radius:{fpx(9)}px}}")      # 반 높이보다 크면 Qt가 모서리를 안 둥글린다
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        lay = QHBoxLayout(self)
        pad = 4 if dens == "tiny" else 6
        lay.setContentsMargins(pad, 3, pad + 4, 3)
        lay.setSpacing(5)
        box = fpx(13)
        self.check = QPushButton("✓" if todo.done else "")
        self.check.setCheckable(True)
        self.check.setChecked(todo.done)
        self.check.setFixedSize(box, box)
        self.check.setCursor(Qt.CursorShape.PointingHandCursor)
        self.check.setToolTip("끝냄 표시")
        fill = ink if todo.done else theme.CARD
        self.check.setStyleSheet(
            f"QPushButton{{background:{fill};border:1.5px solid "
            f"{ink if todo.done else theme.SCROLL_HANDLE};border-radius:{box // 2}px;"
            f"color:{theme.CARD};font-size:{max(7, box - 5)}px;font-weight:bold;padding:0}}"
            f"QPushButton:hover{{border-color:{ink}}}")
        self.check.clicked.connect(lambda on: board.todos.toggle(todo.id, on))
        lay.addWidget(self.check, alignment=Qt.AlignmentFlag.AlignTop)
        self.label = QLabel(todo.title)
        self.label.setWordWrap(True)
        self.label.setMinimumWidth(30)
        color = theme.SUBTLE if todo.done else theme.TEXT
        deco = "text-decoration:line-through;" if todo.done else ""
        self.label.setStyleSheet(
            f"color:{color};{deco}font-size:{fpx(11)}px;background:transparent")
        self.label.setToolTip("더블클릭하면 고칠 수 있어요 · 우클릭하면 메뉴")
        lay.addWidget(self.label, stretch=1)

    def mouseDoubleClickEvent(self, ev):
        self.board.start_edit(self.todo.id)

    def contextMenuEvent(self, ev):
        m = QMenu(self)
        m.addAction("고치기", lambda: self.board.start_edit(self.todo.id))
        t, st = self.todo, self.board.todos
        if t.day_date != date.today():
            m.addAction("오늘 할 일로", lambda: st.update(t.id, day=date.today().isoformat()))
        if t.day:
            m.addAction("날짜 빼기", lambda: st.update(t.id, day=""))
        if t.event_id:
            m.addAction("일정 연결 끊기 (미분류로)", lambda: st.update(t.id, event_id=""))
        m.addSeparator()
        m.addAction("삭제", lambda: st.remove(t.id))
        m.exec(ev.globalPos())


class _InlineEdit(QLineEdit):
    """할 일 추가·수정 입력칸 — Enter 저장, Esc 취소, 비운 채 나가면 닫힘."""

    def __init__(self, board: "BoardWidget", text: str, on_submit, on_cancel, hue):
        super().__init__(text)
        self._submit, self._cancel = on_submit, on_cancel
        self._done = False
        bg, line, ink = hue
        self.setPlaceholderText("할 일을 쓰고 Enter")
        self.setStyleSheet(
            f"QLineEdit{{background:{theme.CARD};border:1.5px solid {ink};"
            f"border-radius:{board.font_px(9)}px;padding:3px 8px;"
            f"font-size:{board.font_px(11)}px;color:{theme.TEXT}}}")
        self.returnPressed.connect(self._enter)

    def _enter(self):
        self._done = True
        self._submit(self.text())

    def keyPressEvent(self, ev):
        if ev.key() == Qt.Key.Key_Escape:
            self._done = True
            self._cancel()
            return
        super().keyPressEvent(ev)

    def focusOutEvent(self, ev):
        super().focusOutEvent(ev)
        if not self._done:
            self._done = True
            text = self.text().strip()
            QTimer.singleShot(0, (lambda: self._submit(text)) if text else self._cancel)


# ── 보드 위젯 ────────────────────────────────────────────────
class BoardWidget(DeskWidgetBase):
    BASE_H = 460
    MIN_W, MIN_H = 240, 240

    def __init__(self, store, config, base_dir, conf):
        self.todos = TodoStore.shared(base_dir)
        self.week_start = week_bounds(date.today())[0]
        self.dens = "normal"
        self._adding: str | None = None      # 입력칸이 열린 자리 ("ev:<id>", "loose", "day:<iso>")
        self._editing: str | None = None     # 고치는 중인 할 일 id
        self._scroll_today = True
        self._popup = None
        super().__init__(store, config, base_dir, conf)
        self._todo_cb = lambda: QTimer.singleShot(0, self.refresh)
        self.todos.subscribe(self._todo_cb)

        root, head = _make_card(self, "")
        self.title_lbl = head.itemAt(0).widget()
        self.range_lbl = QLabel()
        self.now_tag = QLabel("이번 주")
        self.go_now = QPushButton("이번 주로")
        self.go_now.setStyleSheet(theme.TEXT_BTN)
        self.go_now.setCursor(Qt.CursorShape.PointingHandCursor)
        self.go_now.clicked.connect(self.go_this_week)
        head.insertWidget(1, self.range_lbl)
        head.insertWidget(2, self.now_tag)
        head.insertWidget(3, self.go_now)
        # 제목줄이 좁은 위젯에서 넘치지 않게 주 이동·보기 전환은 아래 도구줄로
        self.prev_btn = self._nav_btn("‹", "지난 주", lambda: self.shift_week(-1))
        self.next_btn = self._nav_btn("›", "다음 주", lambda: self.shift_week(1))
        self.seg = QWidget()
        seg_lay = QHBoxLayout(self.seg)
        seg_lay.setContentsMargins(2, 2, 2, 2)
        seg_lay.setSpacing(0)
        self.seg_btns = {}
        for key, text, tip in ((VIEW_TABLE, "표", "일정 ↔ 할 일을 한 줄씩"),
                               (VIEW_DAYS, "날짜", "일~토 하루씩, 빈 날도")):
            b = QPushButton(text)
            b.setCheckable(True)
            b.setToolTip(tip)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _on, k=key: self.set_view(k))
            seg_lay.addWidget(b)
            self.seg_btns[key] = b
        self.add_btn = _add_event_button(
            self, date_fn=self._add_default_day, tip="이 주에 일정 추가")
        head.insertWidget(head.count() - 3, self.add_btn)      # 📌 · – · 🔧 앞
        bar = QHBoxLayout()
        bar.setContentsMargins(0, 0, 0, 0)
        bar.setSpacing(2)
        head.removeWidget(self.go_now)
        for w in (self.prev_btn, self.go_now, self.next_btn):
            bar.addWidget(w)
        bar.addStretch()
        bar.addWidget(self.seg)
        root.addLayout(bar)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setStyleSheet("QScrollArea{border:none;background:transparent}")
        self.inner = QWidget()
        self.inner.setStyleSheet("background:transparent")
        self.grid = QGridLayout(self.inner)
        self.grid.setContentsMargins(0, 0, 2, 0)
        self.scroll.setWidget(self.inner)
        root.addWidget(self.scroll, stretch=1)
        self.refresh()

    # ── 헤더 ────────────────────────────────────────────────
    def _nav_btn(self, text, tip, fn) -> QPushButton:
        b = QPushButton(text)
        b.setToolTip(tip)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.setStyleSheet(theme.TEXT_BTN + "QPushButton{font-size:15px;padding:0 6px}")
        b.clicked.connect(fn)
        return b

    def view(self) -> str:
        v = self.conf.get("view", VIEW_TABLE)
        return v if v in (VIEW_TABLE, VIEW_DAYS) else VIEW_TABLE

    def set_view(self, v: str) -> None:
        self.conf["view"] = v
        self._save_config()
        self._scroll_today = True
        self.refresh()

    def shift_week(self, n: int) -> None:
        self.week_start += timedelta(days=7 * n)
        self._adding = self._editing = None
        self._scroll_today = True
        self.refresh()

    def go_this_week(self) -> None:
        self.week_start = week_bounds(date.today())[0]
        self._adding = self._editing = None
        self._scroll_today = True
        self.refresh()

    def _add_default_day(self) -> date:
        today = date.today()
        end = self.week_start + timedelta(days=6)
        return today if self.week_start <= today <= end else self.week_start

    def place_default(self) -> None:
        screen = QApplication.primaryScreen().availableGeometry()
        self.resize(400, min(460, screen.height() - 160))
        self.move(screen.right() - self.width() - 40, screen.top() + 80)

    def _style_header(self) -> None:
        fpx, tiny = self.font_px, self.dens == "tiny"
        is_now = self.week_start == week_bounds(date.today())[0]
        self.title_lbl.setText(week_title(self.week_start))
        self.title_lbl.setStyleSheet(
            f"font-size:{fpx(13)}px;font-weight:bold;color:{theme.TEXT};background:transparent")
        self.range_lbl.setText(week_range_text(self.week_start))
        self.range_lbl.setStyleSheet(
            f"font-size:{fpx(10)}px;color:{theme.SUBTLE};background:transparent")
        self.range_lbl.setVisible(self.dens == "normal")
        self.now_tag.setVisible(is_now and not tiny)
        self.now_tag.setStyleSheet(
            f"background:{theme.TEXT};color:{theme.CARD};font-size:{fpx(9)}px;"
            f"font-weight:bold;border-radius:{fpx(8)}px;padding:1px 7px")
        self.go_now.setVisible(not is_now)
        self.seg.setStyleSheet(
            f"background:{theme.CARD_TINT};border-radius:{fpx(8)}px")
        for key, b in self.seg_btns.items():
            on = key == self.view()
            b.setChecked(on)
            b.setStyleSheet(
                f"QPushButton{{background:{theme.PRIMARY if on else 'transparent'};"
                f"color:{theme.CARD if on else theme.SUBTLE};border:none;"
                f"border-radius:{fpx(7)}px;font-size:{fpx(10)}px;font-weight:bold;"
                f"padding:{1 if tiny else 2}px {6 if tiny else 9}px}}")

    # ── 반응형: 칸 폭이 단계를 넘을 때만 다시 그린다 ─────────
    def _panel_width(self) -> int:
        w = self.scroll.viewport().width() if hasattr(self, "scroll") else self.width()
        return int(w * LEFT_STRETCH / (LEFT_STRETCH + RIGHT_STRETCH))

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        if hasattr(self, "scroll"):
            d = density(self._panel_width(), self.font_scale())
            if d != self.dens:
                QTimer.singleShot(0, self.refresh)

    # ── 그리기 ──────────────────────────────────────────────
    def refresh(self) -> None:
        if not hasattr(self, "grid"):
            return
        self.dens = density(self._panel_width(), self.font_scale())
        self._style_header()
        _clear_layout(self.grid)
        for c in range(3):
            self.grid.setColumnStretch(c, 0)
            self.grid.setColumnMinimumWidth(c, 0)
        gap = 4 if self.dens == "tiny" else 6
        self.grid.setHorizontalSpacing(gap)
        self.grid.setVerticalSpacing(gap)
        today = date.today()
        all_events = self.store.all()
        week = events_in_week(all_events, self.week_start)
        self.hues = hue_map(week)
        by_event, loose = split_todos(self.todos.all(), week,
                                      {e.id for e in all_events},
                                      self.week_start, today)
        self._today_row = None
        if self.view() == VIEW_DAYS:
            self._draw_days(week, by_event, loose, today)
        else:
            self._draw_table(week, by_event, loose, today)
        if self._scroll_today and self._today_row is not None:
            QTimer.singleShot(30, self._scroll_to_today)
        self._scroll_today = False

    def _scroll_to_today(self) -> None:
        """오늘 줄이 보이게 — 그 사이 다시 그려져 줄이 바뀌었으면 지금 줄로."""
        row = self._today_row
        if row is None:
            return
        try:
            self.scroll.ensureWidgetVisible(row, 0, 40)
        except RuntimeError:          # 이미 지워진 옛 줄
            pass

    def _hue(self, ev: Event | None):
        if ev is None:
            return theme.BOARD_LOOSE
        return theme.BOARD_HUES[self.hues.get(ev.id, 0)]

    def _head_label(self, text: str) -> QLabel:
        lab = QLabel(text)
        lab.setStyleSheet(
            f"font-size:{self.font_px(10)}px;font-weight:bold;color:{theme.SUBTLE};"
            f"background:transparent;border-bottom:1px solid {theme.BORDER_SUBTLE};"
            f"padding:0 2px 4px 2px")
        return lab

    # 표 보기: 한 줄 = 일정 카드 | 그 일정의 할 일 칸
    def _draw_table(self, week, by_event, loose, today) -> None:
        g = self.grid
        g.setColumnStretch(0, LEFT_STRETCH)
        g.setColumnStretch(1, RIGHT_STRETCH)
        shown = [t for e in week for t in by_event.get(e.id, [])] + loose
        d, n = done_count(shown)
        g.addWidget(self._head_label("일정"), 0, 0)
        g.addWidget(self._head_label(f"할일   {d}/{n}" if n else "할일"), 0, 1)
        r = 1
        for ev in week:
            card = self._event_card(ev, today)
            g.addWidget(card, r, 0)
            g.addWidget(self._todo_cell(by_event.get(ev.id, []), self._hue(ev),
                                        f"ev:{ev.id}"), r, 1)
            if event_span(ev)[0] <= today <= event_span(ev)[1]:
                self._today_row = card
            r += 1
        if not week:
            empty = QLabel("이 주엔 일정이 없어요")
            empty.setWordWrap(True)
            empty.setStyleSheet(f"color:{theme.SUBTLE};font-size:{self.font_px(10)}px;"
                                f"background:transparent;padding:6px 2px")
            g.addWidget(empty, r, 0)
            r += 1
        g.addWidget(self._loose_card(), r, 0)
        g.addWidget(self._todo_cell(loose, theme.BOARD_LOOSE, "loose"), r, 1)
        g.setRowStretch(r + 1, 1)

    # 날짜 보기: 일~토 한 줄씩 — 왼쪽 날짜, 오른쪽 그날 일정 카드(할 일 포함)
    def _draw_days(self, week, by_event, loose, today) -> None:
        g = self.grid
        gutter = self.font_px(30 if self.dens == "tiny" else 36)
        g.setColumnMinimumWidth(0, gutter)
        g.setColumnStretch(1, 1)
        shown = [t for e in week for t in by_event.get(e.id, [])] + loose
        d, n = done_count(shown)
        g.addWidget(self._head_label(""), 0, 0)
        g.addWidget(self._head_label(f"일정 · 할일   {d}/{n}" if n else "일정 · 할일"), 0, 1)
        day_loose = {}
        no_day = []
        for t in loose:
            if t.day_date:
                day_loose.setdefault(t.day_date, []).append(t)
            else:
                no_day.append(t)
        r = 1
        for i in range(7):
            day = self.week_start + timedelta(days=i)
            evs = [e for e in week if event_span(e)[0] <= day <= event_span(e)[1]]
            lone = day_loose.get(day, [])
            busy = bool(evs or lone)
            g.addWidget(self._day_label(day, today, busy), r, 0)
            box = QWidget()
            box.setStyleSheet("background:transparent")
            v = QVBoxLayout(box)
            v.setContentsMargins(0, 0, 0, 0)
            v.setSpacing(4)
            for ev in evs:
                # 여러 날 일정은 첫날에만 할 일을 담는다(같은 할 일이 반복되지 않게)
                first = event_span(ev)[0] == day or (event_span(ev)[0] < self.week_start and i == 0)
                v.addWidget(self._event_card(ev, today, by_event.get(ev.id, []) if first else None,
                                             key=f"ev:{ev.id}" if first else None))
            if lone or self._adding == f"day:{day.isoformat()}":
                v.addWidget(self._todo_cell(lone, theme.BOARD_LOOSE,
                                            f"day:{day.isoformat()}", framed=False))
            elif not evs:
                v.addWidget(self._add_link(f"day:{day.isoformat()}", theme.BOARD_LOOSE,
                                           quiet=True))
            line = QFrame()
            line.setFixedHeight(1)
            line.setStyleSheet(f"background:{theme.BORDER_SUBTLE}")
            g.addWidget(box, r, 1)
            g.addWidget(line, r + 1, 0, 1, 2)
            if day == today:
                self._today_row = box
            r += 2
        lab = QLabel("미분류")
        lab.setStyleSheet(f"color:{theme.SUBTLE};font-size:{self.font_px(9)}px;"
                          f"background:transparent;padding-top:4px")
        lab.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        g.addWidget(lab, r, 0)
        g.addWidget(self._todo_cell(no_day, theme.BOARD_LOOSE, "loose", framed=False), r, 1)
        g.setRowStretch(r + 1, 1)

    def _day_label(self, day: date, today: date, busy: bool) -> QLabel:
        fpx = self.font_px
        dow = WEEKDAY_KO[day.weekday()]
        is_today = day == today
        color = theme.SUNDAY if day.weekday() == 6 else (
            theme.TEXT if busy else theme.SUBTLE)
        if is_today:                     # 오늘은 시그니처 오렌지, 빈 날이어도 크게
            num = f"<span style='color:{theme.SIGNATURE_DARK}'>{day.day}</span>"
            dow = "오늘"
            busy = True
        else:
            num = f"<span style='color:{color}'>{day.day}</span>"
        if busy:
            html = (f"<div style='text-align:center'><b style='font-size:{fpx(14)}px'>"
                    f"{num}</b><br><span style='font-size:{fpx(9)}px;"
                    f"color:{theme.SIGNATURE_DARK if is_today else theme.SUBTLE}'>"
                    f"{dow}</span></div>")
        else:
            html = (f"<div style='text-align:center;font-size:{fpx(9)}px;"
                    f"color:{theme.SUBTLE}'>{num} {dow}</div>")
        lab = QLabel(html)
        lab.setTextFormat(Qt.TextFormat.RichText)
        lab.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        lab.setStyleSheet("background:transparent;padding-top:3px")
        return lab

    # ── 일정 카드 ───────────────────────────────────────────
    def _date_text(self, ev: Event) -> tuple[str, str]:
        s, e = event_span(ev)
        if e != s:
            return f"{s.month}.{s.day}–{e.month}.{e.day}", ""
        return f"{s.month}.{s.day}", WEEKDAY_KO[s.weekday()]

    def _event_card(self, ev: Event, today: date, todos=None, key=None) -> QFrame:
        fpx, dens = self.font_px, self.dens
        bg, line, ink = self._hue(ev)
        s, e = event_span(ev)
        past = e < today
        is_today = s <= today <= e
        card = QFrame()
        card.setObjectName("evcard")
        card.setStyleSheet(
            f"#evcard{{background:{bg};border:1px solid "
            f"{theme.SIGNATURE if is_today else line};border-radius:{fpx(9)}px}}")
        v = QVBoxLayout(card)
        pad = 6 if dens == "tiny" else 9
        v.setContentsMargins(pad, pad - 2, pad, pad - 1)
        v.setSpacing(1 if dens == "tiny" else 2)
        date_txt, dow = self._date_text(ev)
        date_color = theme.SIGNATURE_DARK if is_today else (theme.SUBTLE if past else ink)
        if dow and dens != "tiny":
            date_html = (f"<b>{date_txt}</b> <span style='font-size:{fpx(9)}px;"
                         f"font-weight:normal'>{dow}</span>")
        else:
            date_html = f"<b>{date_txt}</b>"
        if is_today and dens != "tiny":
            date_html += (f" <span style='font-size:{fpx(9)}px;color:{theme.SIGNATURE_DARK}'>"
                          f"· 오늘</span>")
        if ev.is_deadline:
            date_html += f" <span style='font-size:{fpx(9)}px'>⏰</span>"
        top = QLabel(date_html)
        top.setTextFormat(Qt.TextFormat.RichText)
        top.setStyleSheet(f"color:{date_color};font-size:{fpx(11)}px;background:transparent")
        v.addWidget(top)
        title = QLabel(ev.title)
        title.setWordWrap(True)
        title.setMinimumWidth(30)
        title.setStyleSheet(
            f"color:{theme.SUBTLE if past else theme.TEXT};font-size:{fpx(11)}px;"
            f"font-weight:bold;background:transparent")
        v.addWidget(title)
        if todos is not None:           # 날짜 보기: 카드 안에 그 일정의 할 일
            v.addSpacing(2)
            v.addWidget(self._todo_cell(todos, (bg, line, ink), key, framed=False))
        v.addStretch()                  # 줄이 길어져도 날짜·제목은 붙어 있게
        card.setToolTip("더블클릭하면 일정 수정 · 우클릭하면 할 일 추가")
        card.mouseDoubleClickEvent = lambda _e, ev=ev: self._edit_event(ev)
        card.contextMenuEvent = lambda e, ev=ev: self._event_menu(ev, e)
        return card

    def _loose_card(self) -> QFrame:
        bg, line, ink = theme.BOARD_LOOSE
        card = QFrame()
        card.setObjectName("loosecard")
        card.setStyleSheet(f"#loosecard{{background:{bg};border-radius:{self.font_px(9)}px}}")
        v = QVBoxLayout(card)
        v.setContentsMargins(9, 7, 9, 7)
        lab = QLabel("미분류")
        lab.setStyleSheet(f"color:{ink};font-size:{self.font_px(11)}px;background:transparent")
        v.addWidget(lab)
        v.addStretch()
        card.setToolTip("일정에 묶이지 않은 내 할 일")
        return card

    def _edit_event(self, ev: Event) -> None:
        self._popup = EditPopup(ev, self.store)
        self._popup.show_near_cursor()

    def _event_menu(self, ev: Event, e) -> None:
        m = QMenu(self)
        m.addAction("이 일정에 할 일 추가", lambda: self.start_add(f"ev:{ev.id}"))
        m.addAction("일정 수정", lambda: self._edit_event(ev))
        m.exec(e.globalPos())

    # ── 할 일 칸 ────────────────────────────────────────────
    def _todo_cell(self, todos, hue, key, framed: bool = True) -> QWidget:
        """할 일 알약들 + '＋ 할일'. framed면 그 일정 색 점선 칸(표 보기 오른쪽)."""
        bg, line, ink = hue
        cell = QFrame()
        cell.setObjectName("tcell")
        if framed:
            cell.setStyleSheet(
                f"#tcell{{background:{bg if todos else 'transparent'};"
                f"border:1px dashed {line};border-radius:{self.font_px(9)}px}}")
        else:
            cell.setStyleSheet("#tcell{background:transparent;border:none}")
        v = QVBoxLayout(cell)
        pad = (4 if self.dens == "tiny" else 6) if framed else 0
        v.setContentsMargins(pad, pad, pad, pad)
        v.setSpacing(4)
        for t in todos:
            if t.id == self._editing:
                v.addWidget(self._editor(t, hue))
            else:
                v.addWidget(_TodoPill(self, t, hue))
        if key is not None:
            if self._adding == key:
                v.addWidget(self._adder(key, hue))
            else:
                v.addWidget(self._add_link(key, hue, quiet=bool(todos)),
                            alignment=Qt.AlignmentFlag.AlignLeft)
        v.addStretch()
        return cell

    def _add_link(self, key, hue, quiet=False) -> QPushButton:
        bg, line, ink = hue
        b = QPushButton("＋ 할일")
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.setToolTip("할 일 추가")
        b.setStyleSheet(
            f"QPushButton{{background:transparent;border:none;text-align:left;"
            f"color:{theme.SCROLL_HANDLE if quiet else theme.SUBTLE};"
            f"font-size:{self.font_px(10)}px;padding:2px 4px}}"
            f"QPushButton:hover{{color:{ink}}}")
        b.clicked.connect(lambda: self.start_add(key))
        return b

    def start_add(self, key: str) -> None:
        self._adding, self._editing = key, None
        self.refresh()

    def start_edit(self, todo_id: str) -> None:
        self._editing, self._adding = todo_id, None
        self.refresh()

    def add_todo(self, key: str, text: str) -> Todo | None:
        """key 자리에 할 일 추가 — ev:<id> = 그 일정에 연결, day:<iso> = 그날, loose = 미분류."""
        if key.startswith("ev:"):
            return self.todos.add(text, event_id=key[3:])
        if key.startswith("day:"):
            return self.todos.add(text, day=date.fromisoformat(key[4:]))
        today = date.today()
        end = self.week_start + timedelta(days=6)
        # 다른 주의 미분류에 적으면 그 주에 남도록 날짜를 정해 둔다
        day = None if self.week_start <= today <= end else self.week_start
        return self.todos.add(text, day=day)

    def _adder(self, key, hue) -> QLineEdit:
        def submit(text):
            if text.strip():
                self.add_todo(key, text)       # 저장 → 알림 → 다시 그림(입력칸 유지)
            else:
                cancel()

        def cancel():
            self._adding = None
            QTimer.singleShot(0, self.refresh)

        ed = _InlineEdit(self, "", submit, cancel, hue)
        QTimer.singleShot(0, ed.setFocus)
        return ed

    def _editor(self, t: Todo, hue) -> QLineEdit:
        def submit(text):
            self._editing = None
            if text.strip() and text.strip() != t.title:
                self.todos.update(t.id, title=text.strip())
            else:
                QTimer.singleShot(0, self.refresh)

        def cancel():
            self._editing = None
            QTimer.singleShot(0, self.refresh)

        ed = _InlineEdit(self, t.title, submit, cancel, hue)
        QTimer.singleShot(0, ed.setFocus)
        QTimer.singleShot(0, ed.selectAll)
        return ed

    def closeEvent(self, ev):
        self.todos.unsubscribe(self._todo_cb)
        super().closeEvent(ev)
