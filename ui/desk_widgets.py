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

from store.event_store import Event, EventStore, day_sort_key
from ui import motion, theme
from ui.calendar_view import EventCalendar, EventItemCard, WEEKDAY_KO
from ui.desk_base import DeskWidgetBase

_PRIORITY_ORDER = {"높음": 0, "보통": 1, "낮음": 2}


class DayDetailDialog(motion.FadeInMixin, QDialog):
    """날짜 클릭 시 뜨는 상세 모달 — 아코디언 카드로 편집·삭제 가능."""

    def __init__(self, store: EventStore, d: date, parent=None):
        super().__init__(parent)
        self.store, self.d = store, d
        self.setWindowTitle(f"{d.month}월 {d.day}일 ({WEEKDAY_KO[d.weekday()]})")
        self.resize(420, 460)
        self.setStyleSheet(theme.BASE_QSS)
        lay = QVBoxLayout(self)
        head = QLabel(f"{d.month}월 {d.day}일 ({WEEKDAY_KO[d.weekday()]})")
        head.setStyleSheet(theme.DIALOG_HEADER)
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
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(self.accept)
        lay.addWidget(close_btn)
        self._fill()

    def _fill(self) -> None:
        while self.items_lay.count():
            item = self.items_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        events = self.store.on_date(self.d)
        events.sort(key=day_sort_key)
        if not events:
            empty = QLabel("일정이 없습니다.")
            empty.setStyleSheet(f"color:{theme.SUBTLE}")
            self.items_lay.addWidget(empty)
        for e in events:
            self.items_lay.addWidget(
                EventItemCard(e, self.store,
                              lambda reload_day: QTimer.singleShot(0, self._fill)))
        self.items_lay.addStretch()


def _scale_calendar(cal: EventCalendar, widget_h: int, scale_pct: int,
                    divisor: int) -> None:
    """달력 글씨를 위젯 크기(반응형)×사용자 배율에 맞춰 조정.

    테마의 CALENDAR_QSS가 font-size를 px로 고정하고 있어 setFont로는
    안 바뀐다 — 달력 자체 스타일시트로 덮어써야 한다.
    """
    px = max(9, min(16, widget_h // divisor))
    px = max(8, round(px * scale_pct / 100))
    cal.setStyleSheet(
        f"QCalendarWidget QAbstractItemView{{font-size:{px}px}}"
        f"QCalendarWidget QToolButton{{font-size:{px + 1}px}}")


def open_day_dialog(store: EventStore, d: date) -> None:
    """바탕화면(맨 뒤) 위젯에서 열므로 항상 위로 띄운다."""
    dlg = DayDetailDialog(store, d)
    dlg.setWindowFlags(dlg.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
    dlg.exec()


class EditPopup(motion.FadeInMixin, QDialog):
    """일정 1건 인라인 편집 팝오버 — EventItemCard를 펼친 채로 담는다.

    좁은 위젯 안에서는 일시·중요도 입력칸이 깨지므로 커서 근처에 띄운다.
    """
    _fade_ms = 120

    def __init__(self, event: Event, store: EventStore):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.Dialog
                            | Qt.WindowType.WindowStaysOnTopHint)
        self.setWindowTitle("일정 수정")
        self.setStyleSheet(theme.BASE_QSS + f"QDialog{{background:{theme.BG}}}")
        self.setFixedWidth(520)   # 제목·일시·중요도 한 줄 바가 들어가는 폭
        lay = QVBoxLayout(self)
        card = EventItemCard(event, store,
                             lambda reload_day: QTimer.singleShot(0, self.accept),
                             full=True)   # ✎ 자세히 수정 — 제목·일시·중요도까지
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


class AddEventDialog(motion.FadeInMixin, QDialog):
    """위젯의 ＋ 버튼으로 그 자리에서 일정을 추가하는 작은 모달.

    등록 창과 같은 한 줄 바(제목/날짜/시간) + 중요도·할 일 여부 + 상세내용.
    로컬에만 저장한다 (구글 연동은 등록 창에서).
    """

    def __init__(self, store: EventStore, default_deadline: bool = False,
                 parent=None):
        super().__init__(parent)
        self.store = store
        self.setWindowFlags(Qt.WindowType.Dialog
                            | Qt.WindowType.WindowStaysOnTopHint)
        self.setWindowTitle("일정 추가")
        self.setStyleSheet(theme.BASE_QSS + f"QDialog{{background:{theme.BG}}}")
        self.setFixedWidth(520)
        from PyQt6.QtWidgets import QComboBox, QTextEdit
        from ui.review_dialog import DatePickerButton, TimeCombo

        lay = QVBoxLayout(self)
        lay.setSpacing(8)
        head = QLabel("＋ 새 일정")
        head.setStyleSheet(theme.DIALOG_HEADER)
        lay.addWidget(head)

        bar = QHBoxLayout()
        bar.setSpacing(6)
        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("일정 제목")
        self.title_edit.setStyleSheet(theme.TITLE_EDIT)
        bar.addWidget(self.title_edit, stretch=1)
        self.date_btn = DatePickerButton()
        bar.addWidget(self.date_btn)
        self.time_combo = TimeCombo()
        bar.addWidget(self.time_combo)
        lay.addLayout(bar)

        opts = QHBoxLayout()
        self.priority_combo = QComboBox()
        from store.event_store import PRIORITIES
        self.priority_combo.addItems(PRIORITIES)
        self.priority_combo.setCurrentText("보통")
        self.priority_combo.setToolTip("중요도")
        opts.addWidget(self.priority_combo)
        self.deadline_cb = QCheckBox("할 일(기한)")
        self.deadline_cb.setToolTip("체크하면 기한이 지나도 완료할 때까지 "
                                    "할 일 보드의 '지난 일'에 남아요")
        self.deadline_cb.setChecked(default_deadline)
        opts.addWidget(self.deadline_cb)
        opts.addStretch()
        lay.addLayout(opts)

        self.memo_edit = QTextEdit()
        self.memo_edit.setPlaceholderText("상세내용 (선택 — 로컬에만 저장됩니다)")
        self.memo_edit.setMaximumHeight(90)
        lay.addWidget(self.memo_edit)

        btns = QHBoxLayout()
        btns.addStretch()
        cancel = QPushButton("취소")
        cancel.setStyleSheet(theme.TEXT_BTN)
        cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel.clicked.connect(self.reject)
        btns.addWidget(cancel)
        save = QPushButton("일정 등록")   # 등록 창들과 같은 문구로 통일
        save.setStyleSheet(theme.PRIMARY_BTN)
        save.setCursor(Qt.CursorShape.PointingHandCursor)
        save.clicked.connect(self._save)
        btns.addWidget(save)
        lay.addLayout(btns)
        self.title_edit.setFocus()

    def _save(self) -> None:
        from datetime import datetime
        title = self.title_edit.text().strip()
        if not title:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "확인", "제목을 입력하세요.")
            return
        all_day = self.time_combo.is_all_day()
        d = self.date_btn.get_date()
        h, m = (0, 0) if all_day else self.time_combo.get_time()
        self.store.add(title=title, start=datetime(d.year, d.month, d.day, h, m),
                       all_day=all_day,
                       is_deadline=self.deadline_cb.isChecked(),
                       priority=self.priority_combo.currentText(),
                       memo=self.memo_edit.toPlainText().strip())
        self.accept()


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
        + f"#deskcard{{background:{theme.CARD};border-radius:{theme.RADIUS_XL}px;"
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
    head.addWidget(widget.make_pin_button())   # 📌 바로 고정 (v1.4)
    head.addWidget(widget.make_edit_button())
    root.addLayout(head)
    root.addWidget(widget.build_edit_bar())
    return root, head


def _add_event_button(widget: DeskWidgetBase,
                      default_deadline: bool = False) -> QPushButton:
    """위젯 헤더의 ＋ 버튼 — 그 자리에서 일정 추가 모달을 띄운다."""
    b = QPushButton("＋")
    b.setToolTip("여기서 바로 일정 추가")
    b.setStyleSheet(
        theme.TEXT_BTN
        + "QPushButton{font-size:15px;font-weight:bold;padding:1px 8px}")
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    b.clicked.connect(
        lambda: AddEventDialog(widget.store, default_deadline).exec())
    return b


# ── 공용: ⠿ 드래그로 순서를 바꾸는 일정 필드 ─────────────────
class _DragField(QFrame):
    """맨 앞 ⠿ 그립을 잡고 위아래로 끌면 같은 칸 안에서 순서가 바뀐다.

    필드들만 담긴 레이아웃(부모 위젯의 layout) 안에서 움직이고,
    놓는 순간 EventStore.set_orders()로 순서를 저장한다.
    """

    GRIP_W = 18       # 왼쪽 그립 클릭 판정 폭(px)

    def __init__(self, event: Event, store: EventStore):
        super().__init__()
        self.event = event
        self.store = store
        self._dragging = False

    def make_grip(self, color: str, size_px: int) -> QLabel:
        g = QLabel("⠿")
        g.setStyleSheet(
            f"color:{color};font-size:{size_px}px;background:transparent")
        g.setToolTip("잡고 위아래로 끌면 순서가 바뀌어요")
        g.setCursor(Qt.CursorShape.OpenHandCursor)   # 손바닥 = 잡을 수 있음
        return g

    def _clicked(self, ev) -> None:
        """그립 밖을 눌렀을 때 — 서브클래스에서 재정의."""

    # ── 들어올리기 모션: 잡는 순간 그림자가 퍼지며 살짝 떠오른다 ──
    def _lift(self) -> None:
        from PyQt6.QtGui import QColor
        from PyQt6.QtWidgets import QGraphicsDropShadowEffect
        eff = QGraphicsDropShadowEffect(self)
        eff.setColor(QColor(21, 101, 192, 90))   # PRIMARY_DARK 반투명
        eff.setOffset(0, 5)                      # 아래 그림자 = 위로 뜬 느낌
        eff.setBlurRadius(0)
        self.setGraphicsEffect(eff)
        self.raise_()                            # 형제 필드들 위로
        self.setCursor(Qt.CursorShape.ClosedHandCursor)   # 쥔 손
        if motion.is_enabled():
            from PyQt6.QtCore import QEasingCurve, QPropertyAnimation
            a = QPropertyAnimation(eff, b"blurRadius", self)
            a.setDuration(140)
            a.setStartValue(0.0)
            a.setEndValue(16.0)
            a.setEasingCurve(QEasingCurve.Type.OutCubic)
            a.start()
            self._lift_anim = a                  # GC 방지
        else:
            eff.setBlurRadius(16)

    def _drop(self) -> None:
        self.setGraphicsEffect(None)             # 놓으면 원래 자리로 가라앉음
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, ev):
        if ev.button() != Qt.MouseButton.LeftButton:
            return
        if ev.position().x() <= self.GRIP_W:
            self._dragging = True
            self._lift()
        else:
            self._clicked(ev)

    def mouseMoveEvent(self, ev):
        if not self._dragging:
            return
        lay = self.parentWidget().layout()
        gy = ev.globalPosition().toPoint().y()
        idx = lay.indexOf(self)
        target = idx
        for i in range(lay.count()):
            w = lay.itemAt(i).widget()
            if w is None or w is self:
                continue
            cy = w.mapToGlobal(w.rect().center()).y()
            if i < idx and gy < cy:
                target = min(target, i)
            elif i > idx and gy > cy:
                target = max(target, i)
        if target != idx:
            lay.removeWidget(self)
            lay.insertWidget(target, self)

    def mouseReleaseEvent(self, ev):
        if not self._dragging:
            return
        self._dragging = False
        self._drop()
        lay = self.parentWidget().layout()
        orders = {}
        for i in range(lay.count()):
            w = lay.itemAt(i).widget()
            if isinstance(w, _DragField):
                orders[w.event.id] = len(orders)
        self.store.set_orders(orders)   # 저장 → 모든 위젯이 새 순서로 갱신


# ── ① 할일 간단판 ────────────────────────────────────────────
class _TodoRow(_DragField):
    """할 일 보드의 필드 한 줄: ⠿ + 체크박스 + '시간 ↵ 제목'.

    주간 위젯의 필드(_WeekField)와 같은 중요도색 알약 모양 —
    ⠿를 잡고 끌면 열 안에서 순서가 바뀌고, 누르면 수정 팝오버가 뜬다.
    편집 모드에서는 제목이 입력칸으로 바뀌어 그 자리에서 바로 고친다.
    """

    def __init__(self, event: Event, store: EventStore,
                 owner: "SimpleTodoWidget"):
        super().__init__(event, store)
        self.owner = owner
        fpx = owner.font_px
        fg, bg = theme.PRIORITY_COLORS.get(
            event.priority, theme.PRIORITY_COLORS["보통"])
        self.setStyleSheet(f"_TodoRow{{background:{bg};border-radius:{theme.RADIUS_SM}px}}")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(3, 2, 6, 2)
        lay.setSpacing(3)
        lay.addWidget(self.make_grip(fg, fpx(11)))
        # 모든 항목에 체크박스 — 끝낸 일은 체크 (투두리스트처럼)
        cb = QCheckBox()
        cb.setChecked(event.done)
        cb.setToolTip("완료 표시")
        # 전역 18px은 좁은 열에서 너무 크다 — A−/A＋ 글씨 배율을 따라간다
        ind = max(10, fpx(13))
        cb.setStyleSheet(
            f"QCheckBox::indicator{{width:{ind}px;height:{ind}px;"
            f"border-radius:{max(3, round(ind * 0.28))}px}}")
        cb.stateChanged.connect(
            lambda st: store.set_done(event.id, bool(st)))
        lay.addWidget(cb)
        done_style = ";text-decoration:line-through" if event.done else ""
        # '시간 ↵ 제목' 두 줄 (종일이면 제목 한 줄), 잘리지 않게 줄바꿈
        text_col = QVBoxLayout()
        text_col.setSpacing(0)
        text_col.setContentsMargins(0, 0, 0, 0)
        if not event.all_day:
            t = QLabel(event.start_dt.strftime("%H:%M"))
            t.setStyleSheet(
                f"color:{fg};font-size:{fpx(8)}px;font-weight:bold;"
                f"background:transparent")
            text_col.addWidget(t)
        if owner.edit_mode:
            # 인라인 편집: 그 자리에서 제목을 바로 타이핑
            self.title_edit = QLineEdit(event.title)
            self.title_edit.setMinimumWidth(10)   # 좁은 열에서도 안 넘치게
            self.title_edit.setStyleSheet(
                f"QLineEdit{{background:{theme.CARD_TINT};border:1px solid "
                f"{theme.BORDER};border-radius:5px;padding:1px 4px;"
                f"font-size:{fpx(9)}px;color:{theme.TEXT}}}")
            self.title_edit.editingFinished.connect(self._save_title)
            text_col.addWidget(self.title_edit)
        else:
            title = QLabel(event.title)
            title.setWordWrap(True)
            title.setMinimumWidth(10)   # 최소폭 주장 않기 — 열 너비에 맞춰 줄바꿈
            title.setStyleSheet(
                f"font-size:{fpx(9)}px;color:{fg};"
                f"background:transparent" + done_style)
            text_col.addWidget(title)
        lay.addLayout(text_col, stretch=1)

    def _save_title(self) -> None:
        new = self.title_edit.text().strip()
        if new and new != self.event.title:
            self.store.update(self.event.id, title=new)

    def _edit(self) -> None:
        EditPopup(self.event, self.store).show_near_cursor()

    def _clicked(self, ev) -> None:
        # 편집 모드에서는 입력칸이 클릭을 받으므로 여기로 안 온다
        if not self.owner.edit_mode:
            self._edit()


class SimpleTodoWidget(DeskWidgetBase):
    """할 일 보드 — 주간 일정표 같은 3열 레이아웃.

    왼쪽 = 지난(밀린) 일, 가운데 = 오늘 할 일, 오른쪽 = 앞으로 할 일.
    각 열은 체크박스 + 내용의 투두리스트.
    """

    MIN_W, MIN_H = 340, 170

    def __init__(self, store, config, base_dir, conf):
        super().__init__(store, config, base_dir, conf)
        root, head = _make_card(self, "✓ 할 일")
        head.insertWidget(head.count() - 1,
                          _add_event_button(self, default_deadline=True))
        self.cols = QHBoxLayout()
        self.cols.setSpacing(6)
        root.addLayout(self.cols, stretch=1)
        self.refresh()

    def place_default(self) -> None:
        screen = QApplication.primaryScreen().availableGeometry()
        self.resize(min(560, screen.width() // 2), 250)
        self.move(screen.right() - self.width() - 40, screen.top() + 60)

    def _column(self, label: str, color: str, events,
                today_col: bool) -> QFrame:
        # 주간 위젯의 하루 열(_DayColumn)과 같은 골격·여백·크기
        fpx = self.font_px
        col = QFrame()
        # '오늘'은 시그니처 쿨쿠리 오렌지로 — 앱의 포인트 색
        bg = theme.SIGNATURE_BG if today_col else theme.CARD
        col.setStyleSheet(
            f"QFrame{{background:{bg};border-radius:{theme.RADIUS_MD}px}}")
        lay = QVBoxLayout(col)
        lay.setContentsMargins(8, 6, 8, 6)
        lay.setSpacing(3)
        head = QLabel(label)
        head.setStyleSheet(
            f"color:{color};font-size:{fpx(10)}px;font-weight:bold;"
            f"background:transparent")
        lay.addWidget(head)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        # 가로로 넘치지 않게 — 필드가 열 너비 안에서 줄바꿈되도록 강제
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea{border:none;background:transparent}")
        inner = QWidget()
        inner.setStyleSheet("background:transparent")
        rows = QVBoxLayout(inner)
        rows.setContentsMargins(0, 0, 0, 0)
        rows.setSpacing(3)
        if not events:
            if today_col and self.config.get("character_mode", True):
                # 오늘 할 일이 없으면 잠든 쿨쿠리 — 보면 안심
                pic = QLabel()
                from ui.penguin_icon import penguin_pixmap
                pic.setPixmap(penguin_pixmap(self.base_dir, 44, "sleep"))
                pic.setStyleSheet("background:transparent")
                pic.setToolTip("쿨쿠리가 자고 있어요 — 오늘은 한가해요")
                rows.addWidget(pic, alignment=Qt.AlignmentFlag.AlignHCenter)
                empty = QLabel("오늘은 한가해요")
            else:
                empty = QLabel("없음")
            empty.setStyleSheet(
                f"color:{theme.SUBTLE};font-size:{fpx(9)}px;"
                f"background:transparent")
            rows.addWidget(empty, alignment=(
                Qt.AlignmentFlag.AlignHCenter if today_col
                else Qt.AlignmentFlag.AlignLeft))
        for e in events:
            rows.addWidget(_TodoRow(e, self.store, owner=self))
        rows.addStretch()
        scroll.setWidget(inner)
        lay.addWidget(scroll)
        return col

    def refresh(self) -> None:
        while self.cols.count():
            item = self.cols.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        overdue, today, upcoming = self.store.sections(date.today())
        self.cols.addWidget(
            self._column("지난 일", theme.DANGER_FG, overdue, False), 1)
        self.cols.addWidget(
            self._column("오늘 할 일", theme.SIGNATURE_DARK, today, True), 1)
        self.cols.addWidget(
            self._column("앞으로 할 일", theme.LOW_FG, upcoming, False), 1)


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
        # '오늘'은 시그니처 오렌지, 주말+일정은 연네이비(보라 폐기)
        bg = (theme.SIGNATURE_BG if today
              else theme.PRIMARY_LIGHT if weekend_accent else theme.CARD)
        self.setStyleSheet(
            f"_DayColumn{{background:{bg};border:none;"
            f"border-radius:{theme.RADIUS_MD}px}}")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 6, 8, 6)
        lay.setSpacing(3)
        fpx = owner.font_px
        wd = WEEKDAY_KO[d.weekday()]
        color = (theme.SIGNATURE_DARK if today else
                 theme.SUNDAY if d.weekday() == 6 else
                 theme.PRIMARY if d.weekday() == 5 else theme.SUBTLE)
        head = QLabel(f"{d.day} ({wd})")
        head.setStyleSheet(f"color:{color};font-size:{fpx(10)}px;"
                           f"font-weight:bold;background:transparent")
        lay.addWidget(head)
        events = owner.store.on_date(d)
        events.sort(key=day_sort_key)
        limit = 3 if slim else 6
        # 필드들만 담는 컨테이너 — ⠿ 드래그 순서 조정의 범위
        fields = QWidget()
        fields.setStyleSheet("background:transparent")
        flay = QVBoxLayout(fields)
        flay.setContentsMargins(0, 0, 0, 0)
        flay.setSpacing(3)
        for e in events[:limit]:
            flay.addWidget(_WeekField(e, owner.store, d, fpx, owner))
        lay.addWidget(fields)
        if len(events) > limit:
            more = QLabel(f"+{len(events) - limit}건 더")
            more.setStyleSheet(f"color:{theme.SUBTLE};font-size:{fpx(9)}px;"
                               f"background:transparent")
            lay.addWidget(more)
        lay.addStretch()

    def mousePressEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton:
            open_day_dialog(self.owner.store, self.d)


class _WeekField(_DragField):
    """주간 열의 일정 필드 — ⠿ + '시간 ↵ 제목', 글씨가 잘리지 않는다.

    편집 모드에서는 할 일 보드처럼 제목이 입력칸으로 바뀌어 그 자리 수정.
    """

    def __init__(self, event: Event, store: EventStore, d: date, fpx,
                 owner: "WeeklyWidget" = None):
        super().__init__(event, store)
        self.d = d
        self.owner = owner
        fg, bg = theme.PRIORITY_COLORS.get(
            event.priority, theme.PRIORITY_COLORS["보통"])
        self.setStyleSheet(f"_WeekField{{background:{bg};border-radius:{theme.RADIUS_SM}px}}")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(3, 2, 6, 2)
        lay.setSpacing(3)
        lay.addWidget(self.make_grip(fg, fpx(11)))
        col = QVBoxLayout()
        col.setSpacing(0)
        col.setContentsMargins(0, 0, 0, 0)
        if not event.all_day:
            t = QLabel(event.start_dt.strftime("%H:%M"))
            t.setStyleSheet(f"color:{fg};font-size:{fpx(8)}px;"
                            f"font-weight:bold;background:transparent")
            col.addWidget(t)
        if owner is not None and owner.edit_mode:
            self.title_edit = QLineEdit(event.title)
            self.title_edit.setMinimumWidth(10)   # 좁은 열에서도 안 넘치게
            self.title_edit.setStyleSheet(
                f"QLineEdit{{background:{theme.CARD_TINT};border:1px solid "
                f"{theme.BORDER};border-radius:5px;padding:1px 4px;"
                f"font-size:{fpx(9)}px;color:{theme.TEXT}}}")
            self.title_edit.editingFinished.connect(self._save_title)
            col.addWidget(self.title_edit)
        else:
            title = QLabel(event.title)
            title.setWordWrap(True)
            title.setMinimumWidth(10)   # 최소폭 주장 않기 — 열 너비 줄바꿈
            title.setStyleSheet(f"color:{fg};font-size:{fpx(9)}px;"
                                f"background:transparent")
            col.addWidget(title)
        lay.addLayout(col, stretch=1)

    def _save_title(self) -> None:
        new = self.title_edit.text().strip()
        if new and new != self.event.title:
            self.store.update(self.event.id, title=new)

    def _clicked(self, ev) -> None:
        open_day_dialog(self.store, self.d)


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
        head.insertWidget(head.count() - 1, _add_event_button(self))
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


# ── ③ 캘린더 · 할일 (달력 위젯 단일 창구) ────────────────────
class PlannerWidget(DeskWidgetBase):
    """달력 + 선택한 날짜의 일정 목록이 한 위젯에.

    날짜를 클릭하면 아래 목록이 바뀌고, 일정을 클릭하면 그 자리에서
    아코디언(EventItemCard)으로 펼쳐져 바로 수정·삭제·📌 할 수 있다.
    """

    MIN_W, MIN_H = 280, 380

    def __init__(self, store, config, base_dir, conf):
        super().__init__(store, config, base_dir, conf)
        self._selected = date.today()
        root, _head = _make_card(self, "📋 캘린더 · 할 일",
                                 extra_qss=theme.CALENDAR_QSS)
        self.cal = EventCalendar()
        self.cal.clicked.connect(
            lambda qd: self._pick(date(qd.year(), qd.month(), qd.day())))
        root.addWidget(self.cal, stretch=5)
        self.day_label = QLabel()
        root.addWidget(self.day_label)
        self.detail_scroll = QScrollArea()
        self.detail_scroll.setWidgetResizable(True)
        self.detail_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.detail_scroll.setStyleSheet(
            "QScrollArea{border:none;background:transparent}")
        inner = QWidget()
        inner.setStyleSheet("background:transparent")
        self.items_lay = QVBoxLayout(inner)
        self.items_lay.setContentsMargins(0, 0, 0, 0)
        self.items_lay.setSpacing(6)
        self.detail_scroll.setWidget(inner)
        root.addWidget(self.detail_scroll, stretch=4)
        # 편집 도구줄에 '아래 상세보기' 토글 — 끄면 순수 달력처럼 쓴다
        self.detail_cb = QCheckBox("상세보기")
        self.detail_cb.setToolTip("달력 아래에 그날 일정 목록을 펼칠지")
        self.detail_cb.setStyleSheet(
            f"QCheckBox{{color:{theme.SUBTLE};font-size:10px;"
            f"background:transparent}}")
        self.detail_cb.setChecked(bool(conf.get("show_detail", True)))
        self.detail_cb.toggled.connect(self._set_show_detail)
        bar_lay = self._edit_bar.layout()
        bar_lay.insertWidget(bar_lay.count() - 2, self.detail_cb)  # 📌 앞에
        self._apply_detail()
        self.refresh()

    def _set_show_detail(self, on: bool) -> None:
        self.conf["show_detail"] = bool(on)
        self._save_config()
        self._apply_detail()

    def _apply_detail(self) -> None:
        vis = bool(self.conf.get("show_detail", True))
        self.day_label.setVisible(vis)
        self.detail_scroll.setVisible(vis)

    def place_default(self) -> None:
        screen = QApplication.primaryScreen().availableGeometry()
        self.resize(380, min(560, screen.height() - 160))
        self.move(screen.right() - self.width() - 40, screen.top() + 80)

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        self._apply_cal_font()

    def _apply_cal_font(self) -> None:
        _scale_calendar(self.cal, self.height(), self.font_scale(), 44)

    def _pick(self, d: date) -> None:
        self._selected = d
        self.refresh_day()

    def refresh(self) -> None:
        self._apply_cal_font()
        counts: dict[date, tuple[int, bool]] = {}
        for d in self.store.dates_with_events():
            evs = self.store.on_date(d)
            counts[d] = (len(evs), any(e.priority == "높음" for e in evs))
        self.cal.set_counts(counts)
        self.refresh_day()

    def refresh_day(self) -> None:
        d = self._selected
        self.day_label.setText(
            f"{d.month}월 {d.day}일 ({WEEKDAY_KO[d.weekday()]})")
        self.day_label.setStyleSheet(
            f"font-size:{self.font_px(12)}px;font-weight:bold;"
            f"color:{theme.PRIMARY_DARK};background:transparent;padding-top:2px")
        while self.items_lay.count():
            item = self.items_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        events = self.store.on_date(d)
        events.sort(key=day_sort_key)
        if not events:
            empty = QLabel("일정이 없습니다.")
            empty.setStyleSheet(
                f"color:{theme.SUBTLE};font-size:{self.font_px(11)}px;"
                f"background:transparent")
            self.items_lay.addWidget(empty)
        for e in events:
            self.items_lay.addWidget(
                EventItemCard(e, self.store,
                              lambda reload_day: QTimer.singleShot(0, self.refresh)))
        self.items_lay.addStretch()
