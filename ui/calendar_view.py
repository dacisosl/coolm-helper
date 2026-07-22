# -*- coding: utf-8 -*-
"""내장 캘린더 (전부 로컬, 인터넷 불필요).

- 날짜 셀 아래에 일정 개수 배지만 표시
- 날짜 클릭 → 오른쪽에 투두리스트 스타일 목록 (중요도 칩 + 제목)
- 항목 클릭 → 아코디언 상세보기, 인라인 편집 후 [저장]
"""
from __future__ import annotations

from datetime import date

from PyQt6.QtCore import Qt, QDate, QRectF, QTimer
from PyQt6.QtGui import QColor, QFont, QPainter, QTextCharFormat
from PyQt6.QtWidgets import (
    QCalendarWidget, QComboBox, QFrame,
    QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QScrollArea, QSplitter, QTabWidget, QTextEdit, QVBoxLayout, QWidget,
)

from store.event_store import Event, EventStore, PRIORITIES
from ui import theme

WEEKDAY_KO = "월화수목금토일"


class EventCalendar(QCalendarWidget):
    """날짜 셀에 일정 개수 배지를 그리는 달력."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._counts: dict[date, tuple[int, bool]] = {}   # 날짜 → (개수, 높음 포함)
        self.setVerticalHeaderFormat(
            QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader)
        self.setGridVisible(False)
        # 요일 헤더를 연한 회색으로
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(theme.SUBTLE))
        fmt.setFontWeight(600)
        for d in (Qt.DayOfWeek.Monday, Qt.DayOfWeek.Tuesday,
                  Qt.DayOfWeek.Wednesday, Qt.DayOfWeek.Thursday,
                  Qt.DayOfWeek.Friday):
            self.setWeekdayTextFormat(d, fmt)
        sat = QTextCharFormat(fmt)
        sat.setForeground(QColor(theme.PRIMARY))
        self.setWeekdayTextFormat(Qt.DayOfWeek.Saturday, sat)
        sun = QTextCharFormat(fmt)
        sun.setForeground(QColor(theme.SUNDAY))
        self.setWeekdayTextFormat(Qt.DayOfWeek.Sunday, sun)

    def set_counts(self, counts: dict[date, tuple[int, bool]]) -> None:
        self._counts = counts
        self.updateCells()

    def paintCell(self, painter: QPainter, rect, qdate: QDate) -> None:
        super().paintCell(painter, rect, qdate)
        info = self._counts.get(date(qdate.year(), qdate.month(), qdate.day()))
        if not info:
            return
        n, has_high = info
        base = QColor(theme.DANGER) if has_high else QColor(theme.PRIMARY)
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        selected = qdate == self.selectedDate()
        painter.setPen(Qt.PenStyle.NoPen)
        # 셀 크기에 맞춰 배지를 줄인다(반응형) — 가운데 날짜 숫자와 안 겹치게
        # 오른쪽 아래 구석에 붙이고, 아주 작은 셀에서는 숫자 대신 점만 찍는다
        if rect.height() < 30:
            r = max(2, rect.height() // 8)
            painter.setBrush(QColor("white") if selected else base)
            painter.drawEllipse(rect.right() - r * 2 - 3,
                                rect.bottom() - r * 2 - 3, r * 2, r * 2)
            painter.restore()
            return
        chip_h = max(10, min(14, rect.height() // 4))
        chip_w = chip_h + (6 if n < 10 else 12)
        x = rect.right() - chip_w - 3
        y = rect.bottom() - chip_h - 2
        painter.setBrush(QColor("white") if selected else base)
        painter.drawRoundedRect(QRectF(x, y, chip_w, chip_h),
                                chip_h / 2, chip_h / 2)
        painter.setPen(base if selected else QColor("white"))
        f = QFont(self.font())
        f.setPointSize(6 if chip_h < 13 else 7)
        f.setBold(True)
        painter.setFont(f)
        painter.drawText(QRectF(x, y, chip_w, chip_h),
                         Qt.AlignmentFlag.AlignCenter, str(n))
        painter.restore()


class EventItemCard(QFrame):
    """일정 항목 — 클릭하면 아코디언 상세보기가 펼쳐진다.

    기본(full=False): 상세보기는 메모만. 중요도는 접힌 줄의 칩을 눌러 바꾼다.
    full=True: 제목·일시·중요도까지 편집(EditPopup 등 '자세히 수정'용).
    """

    def __init__(self, event: Event, store: EventStore, on_change,
                 parent=None, full: bool = False):
        super().__init__(parent)
        self.event = event
        self.store = store
        self.on_change = on_change   # 저장/삭제 후 부모 갱신 콜백
        self.full = full
        self._apply_card_style()     # 왼쪽 중요도색 막대 포함 (시안 agenda 스타일)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(6)

        # ── 접힌 줄: 시간(있을 때만, 윗줄) + [중요도] 제목 ──
        self.time_line = QLabel()
        self.time_line.setStyleSheet(
            f"color:{theme.SUBTLE};font-size:{theme.FONT_XS}px;background:transparent")
        lay.addWidget(self.time_line)
        row = QHBoxLayout()
        if full:
            self.chip = QLabel(event.priority)         # 중요도는 아래 콤보로 편집
        else:
            self.chip = QPushButton(event.priority)    # 눌러서 중요도 변경
            self.chip.setCursor(Qt.CursorShape.PointingHandCursor)
            self.chip.setToolTip("눌러서 중요도 변경")
            self.chip.clicked.connect(self._pick_priority)
        row.addWidget(self.chip)
        self.title_label = QLabel(event.title)
        self.title_label.setStyleSheet(
            f"font-size:{theme.FONT_MD}px;font-weight:bold;color:{theme.TEXT}")
        self.title_label.setWordWrap(True)
        row.addWidget(self.title_label, stretch=1)
        lay.addLayout(row)
        self._update_labels()

        # ── 상세보기 (아코디언, 기본 접힘) — 흰 패널 = 수정 중 표시 ──
        self.detail = QFrame()
        self.detail.setObjectName("editzone")
        self.detail.setStyleSheet(
            f"#editzone{{background:{theme.CARD};border:1.5px solid "
            f"{theme.BORDER};border-radius:{theme.RADIUS_SM + 2}px}}")
        self.detail.setVisible(False)
        d = QVBoxLayout(self.detail)
        d.setContentsMargins(8, 8, 8, 8)
        d.setSpacing(6)

        if not full:
            # 기본 모드에서도 제목은 그 자리에서 고칠 수 있게
            self.title_edit = QLineEdit(event.title)
            self.title_edit.setToolTip("제목")
            d.addWidget(self.title_edit)

        if full:
            # 한 줄 바: 제목 / 날짜 / 시간 / 중요도 — 등록 창들과 같은 부품
            from ui.review_dialog import DatePickerButton, TimeCombo
            bar = QHBoxLayout()
            bar.setSpacing(6)
            self.title_edit = QLineEdit(event.title)
            self.title_edit.setToolTip("제목")
            bar.addWidget(self.title_edit, stretch=1)
            self.date_btn = DatePickerButton()
            self.date_btn.set_date(event.start_dt.date())
            bar.addWidget(self.date_btn)
            self.time_combo = TimeCombo()
            if event.all_day:
                self.time_combo.set_all_day()
            else:
                self.time_combo.set_time(event.start_dt.hour,
                                         event.start_dt.minute)
            bar.addWidget(self.time_combo)
            self.priority_combo = QComboBox()
            self.priority_combo.addItems(PRIORITIES)
            self.priority_combo.setCurrentText(event.priority)
            self.priority_combo.setToolTip("중요도")
            bar.addWidget(self.priority_combo)
            d.addLayout(bar)

        self.memo_edit = QTextEdit(event.memo)
        self.memo_edit.setPlaceholderText("상세내용 (로컬에만 저장됩니다)")
        self.memo_edit.setMaximumHeight(70)
        d.addWidget(self.memo_edit)

        btns = QHBoxLayout()
        del_btn = QPushButton("삭제")
        del_btn.setStyleSheet(
            f"QPushButton{{background:transparent;color:{theme.DANGER};"
            f"border:none;font-size:{theme.FONT_SM}px;padding:5px}}"
            f"QPushButton:hover{{background:{theme.DANGER_BG};"
            f"border-radius:{theme.RADIUS_SM}px}}"
            f"QPushButton:pressed{{background:{theme.DANGER_PRESSED}}}")
        del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        del_btn.clicked.connect(self._delete)
        btns.addWidget(del_btn)
        pin_btn = QPushButton("📌 포스트잇")
        pin_btn.setToolTip("이 일정을 바탕화면에 메모지로 붙이기")
        pin_btn.setStyleSheet(theme.TEXT_BTN)
        pin_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        pin_btn.clicked.connect(self._pin)
        btns.addWidget(pin_btn)
        btns.addStretch()
        save_btn = QPushButton("저장")
        save_btn.setStyleSheet(theme.PRIMARY_BTN)
        save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_btn.clicked.connect(self._save)
        btns.addWidget(save_btn)
        d.addLayout(btns)
        lay.addWidget(self.detail)

    def _apply_card_style(self) -> None:
        """카드 골격 + 왼쪽 3px 중요도색 막대 — 중요도가 바뀌면 다시 칠한다."""
        fg, _bg = theme.PRIORITY_COLORS.get(
            self.event.priority, theme.PRIORITY_COLORS["보통"])
        self.setStyleSheet(
            f"EventItemCard{{background:{theme.CARD};border:none;"
            f"border-left:3px solid {fg};"
            f"border-radius:{theme.RADIUS_MD}px}}"
            f"EventItemCard:hover{{background:{theme.CARD_TINT}}}")

    def _update_labels(self) -> None:
        e = self.event
        self._apply_card_style()
        self.title_label.setText(e.title)
        self.chip.setText(e.priority)
        chip_qss = theme.priority_chip(e.priority)
        if isinstance(self.chip, QPushButton):
            chip_qss = f"QPushButton{{{chip_qss};border:none}}"
        self.chip.setStyleSheet(chip_qss)
        # 시간이 있으면 '시간 ↵ 제목' 두 줄, 종일이면 제목 한 줄
        if e.all_day:
            self.time_line.hide()
        else:
            self.time_line.setText(e.start_dt.strftime("%H:%M"))
            self.time_line.show()

    def _pick_priority(self) -> None:
        """접힌 줄의 칩을 눌러 중요도(높음/보통/낮음)를 바로 바꾼다."""
        from PyQt6.QtWidgets import QMenu
        menu = QMenu(self)
        menu.setStyleSheet(theme.BASE_QSS)
        for p in PRIORITIES:
            menu.addAction(p, lambda p=p: self._set_priority(p))
        menu.exec(self.chip.mapToGlobal(self.chip.rect().bottomLeft()))

    def _set_priority(self, priority: str) -> None:
        if priority == self.event.priority:
            return
        self.store.update(self.event.id, priority=priority)
        self.event.priority = priority
        self._update_labels()
        self.on_change(reload_day=False)

    # 접힌 줄 클릭 → 아코디언 토글 (버튼·입력칸 클릭은 제외)
    def mousePressEvent(self, ev):
        if not self.detail.isVisible():
            self.detail.setVisible(True)
        elif ev.position().y() < 34:   # 상단 요약줄을 다시 누르면 접기
            self.detail.setVisible(False)
        super().mousePressEvent(ev)

    def _save(self) -> None:
        if not self.full:
            # 기본 모드: 제목·상세내용 저장 (일시는 그대로, 중요도는 칩으로)
            title = self.title_edit.text().strip() or self.event.title
            self.store.update(self.event.id, title=title,
                              memo=self.memo_edit.toPlainText())
            if self.event.google_id and title != self.event.title:
                try:
                    from calendar_sync import google_sync
                    google_sync.update_event(
                        self.event.google_id, title, self.event.start_dt,
                        self.event.end_dt, self.event.all_day)
                except Exception:
                    pass   # 구글 사본 갱신 실패는 로컬 저장을 막지 않는다
            self.event.title = title
            self.event.memo = self.memo_edit.toPlainText()
            self._update_labels()
            self.detail.setVisible(False)
            self.on_change(reload_day=False)
            return
        title = self.title_edit.text().strip() or self.event.title
        from datetime import datetime as _dt
        nd = self.date_btn.get_date()
        new_all_day = self.time_combo.is_all_day()
        h, m = (0, 0) if new_all_day else self.time_combo.get_time()
        new_start = _dt(nd.year, nd.month, nd.day, h, m)
        self.store.update(
            self.event.id,
            title=title,
            start=new_start.isoformat(),
            all_day=new_all_day,
            priority=self.priority_combo.currentText(),
            memo=self.memo_edit.toPlainText(),
        )
        # 구글에 올린 일정이면 사본도 갱신 (제목·일시만)
        if self.event.google_id:
            try:
                from calendar_sync import google_sync
                google_sync.update_event(self.event.google_id, title,
                                         new_start, self.event.end_dt,
                                         new_all_day)
            except Exception:
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.information(
                    self, "안내", "구글 캘린더의 사본은 갱신하지 못했습니다.\n"
                    "구글 캘린더에서 직접 수정해 주세요.")
        # 로컬 객체도 갱신해 접힌 줄 표시를 즉시 반영
        self.event.title = title
        self.event.start = new_start.isoformat()
        self.event.all_day = new_all_day
        self.event.priority = self.priority_combo.currentText()
        self.event.memo = self.memo_edit.toPlainText()
        self._update_labels()
        self.detail.setVisible(False)
        self.on_change(reload_day=False)

    def _pin(self) -> None:
        from ui.desk_base import pin_note
        pin_note(self.event.id)

    def _delete(self) -> None:
        if self.event.google_id:
            try:
                from calendar_sync import google_sync
                google_sync.delete_event(self.event.google_id)
            except Exception:
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.information(
                    self, "안내", "구글 캘린더의 사본은 삭제하지 못했습니다.\n"
                    "구글 캘린더에서 직접 지워주세요.")
        # 실수 방지: 지우되 되돌리기 토스트 제공 (등록 취소와 같은 규약)
        e, store = self.event, self.store   # 카드 파괴 후에도 쓰도록 로컬로
        win = self.window()                 # 카드가 사라져도 창은 남는다
        store.remove(e.id)
        self.on_change(reload_day=True)

        def restore():
            from datetime import datetime as _dt
            store.add(
                title=e.title, start=_dt.fromisoformat(e.start),
                end=_dt.fromisoformat(e.end) if e.end else None,
                all_day=e.all_day, is_deadline=e.is_deadline,
                demo=e.demo, memo=e.memo, source_ref=e.source_ref,
                priority=e.priority)

        if win is not None and win.isVisible():
            from ui.toast import show_toast
            show_toast(win, "일정을 삭제했습니다", "되돌리기", restore)


class CalendarWindow(QWidget):
    """테두리 없는 캘린더 창 — 커스텀 타이틀바(최소화/닫기) + 탭(캘린더/즐겨찾기)."""

    def __init__(self, store: EventStore, fav_store=None,
                 favorites_enabled: bool = False, parent=None):
        super().__init__(parent)
        self.store = store
        self.setWindowTitle("내 캘린더 — COOL-비서")
        self.resize(800, 540)
        self.setWindowFlags(Qt.WindowType.Window
                            | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._drag = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 10, 10, 10)
        card = QFrame()
        card.setObjectName("calcard")
        card.setStyleSheet(
            theme.BASE_QSS + theme.CALENDAR_QSS
            + f"#calcard{{background:{theme.BG};border-radius:{theme.RADIUS_LG}px;"
              f"border:1px solid {theme.BORDER}}}")
        card.setGraphicsEffect(theme.make_shadow(self, 2))
        outer.addWidget(card)
        root = QVBoxLayout(card)
        root.setContentsMargins(14, 8, 14, 14)

        # ── 커스텀 타이틀바 ──
        bar = QHBoxLayout()
        self._titlebar = QLabel("🗓  내 캘린더")
        self._titlebar.setStyleSheet(
            f"font-size:14px;font-weight:bold;color:{theme.PRIMARY_DARK}")
        bar.addWidget(self._titlebar)
        bar.addStretch()
        for text, tip, handler in (("–", "최소화", self.showMinimized),
                                   ("✕", "닫기", self._close_anim)):
            b = QPushButton(text)
            b.setFixedSize(30, 26)
            b.setToolTip(tip)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            hover = f"{theme.DANGER_BG};color:{theme.DANGER_FG}" if text == "✕" \
                else f"{theme.PRIMARY_LIGHT};color:{theme.PRIMARY_DARK}"
            pressed = theme.DANGER_PRESSED if text == "✕" else theme.LIGHT_PRESSED
            b.setStyleSheet(
                f"QPushButton{{background:transparent;color:{theme.SUBTLE};"
                f"border:none;border-radius:{theme.RADIUS_SM}px;"
                f"font-size:{theme.FONT_MD}px}}"
                f"QPushButton:hover{{background:{hover}}}"
                f"QPushButton:pressed{{background:{pressed}}}")
            b.clicked.connect(handler)
            bar.addWidget(b)
        root.addLayout(bar)

        # ── 탭: 캘린더 / 즐겨찾기(옵션) ──
        self.tabs = QTabWidget()
        cal_page = QWidget()
        lay = QHBoxLayout(cal_page)
        lay.setContentsMargins(0, 8, 0, 0)
        split = QSplitter(Qt.Orientation.Horizontal)

        # 왼쪽: 달력 카드
        cal_card = QFrame()
        cal_card.setStyleSheet(
            f"QFrame{{background:{theme.CARD};border-radius:14px}}")
        cl = QVBoxLayout(cal_card)
        cl.setContentsMargins(10, 10, 10, 10)
        self.cal = EventCalendar()
        self.cal.selectionChanged.connect(self.refresh_day)
        cl.addWidget(self.cal)
        split.addWidget(cal_card)

        # 오른쪽: 선택한 날짜의 일정 목록
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(12, 4, 0, 0)
        self.day_label = QLabel()
        self.day_label.setStyleSheet(
            f"font-weight:bold;font-size:15px;color:{theme.TEXT}")
        rl.addWidget(self.day_label)
        self.count_label = QLabel()
        self.count_label.setStyleSheet(f"color:{theme.SUBTLE};font-size:12px")
        rl.addWidget(self.count_label)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        inner.setStyleSheet(f"background:{theme.BG}")
        self.items_lay = QVBoxLayout(inner)
        self.items_lay.setContentsMargins(0, 6, 4, 0)
        self.items_lay.setSpacing(8)
        scroll.setWidget(inner)
        rl.addWidget(scroll)

        split.addWidget(right)
        split.setSizes([420, 340])
        lay.addWidget(split)

        self.tabs.addTab(cal_page, "캘린더")
        if favorites_enabled and fav_store is not None:
            from ui.favorites_view import FavoritesTab
            self.tabs.addTab(FavoritesTab(fav_store), "★ 즐겨찾기")
        root.addWidget(self.tabs)

        self.refresh()
        # 다른 창(일정 등록 등)에서 저장/삭제 시 실시간 반영.
        # 지연 호출: 카드 내부 저장 도중 위젯이 파괴되는 재진입을 피한다.
        # 닫힌 동안에는 구독을 끊는다 — 설정 저장으로 창을 새로 만들 때
        # 옛 창이 구독을 붙잡고 남는 누수 방지 (다시 열면 재구독).
        self._store_cb = lambda: QTimer.singleShot(0, self.refresh)
        self._subscribed = False

    def closeEvent(self, ev):
        if self._subscribed:
            self.store.unsubscribe(self._store_cb)
            self._subscribed = False
        super().closeEvent(ev)

    # ── 등장/퇴장 애니메이션 ─────────────────────────────────
    def showEvent(self, ev):
        super().showEvent(ev)
        if not self._subscribed:
            self.store.subscribe(self._store_cb)
            self._subscribed = True
            self.refresh()           # 닫혀 있던 사이의 변경을 반영
        self._closing = False        # 다시 열 때 퇴장 가드 해제
        from ui import motion
        motion.fade_in(self, ms=160)

    def _close_anim(self) -> None:
        from ui import motion
        motion.fade_out_close(self, ms=120)

    # ── 커스텀 타이틀바 드래그 ───────────────────────────────
    def mousePressEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton and \
                ev.position().y() < 52:      # 타이틀바 영역에서만 이동
            self._drag = ev.globalPosition().toPoint() - self.pos()

    def mouseMoveEvent(self, ev):
        if self._drag and ev.buttons() & Qt.MouseButton.LeftButton:
            self.move(ev.globalPosition().toPoint() - self._drag)

    def mouseReleaseEvent(self, ev):
        self._drag = None

    # ── 갱신 ────────────────────────────────────────────────
    def _counts(self) -> dict[date, tuple[int, bool]]:
        out: dict[date, tuple[int, bool]] = {}
        for d in self.store.dates_with_events():
            evs = self.store.on_date(d)
            out[d] = (len(evs), any(e.priority == "높음" for e in evs))
        return out

    def refresh(self) -> None:
        self.cal.set_counts(self._counts())
        self.refresh_day()

    def _on_item_change(self, reload_day: bool) -> None:
        self.refresh() if reload_day else self.cal.set_counts(self._counts())

    def refresh_day(self) -> None:
        qd = self.cal.selectedDate()
        d = date(qd.year(), qd.month(), qd.day())
        events = self.store.on_date(d)
        # 중요도(높음 먼저) → 시간순 정렬
        from store.event_store import day_sort_key
        events.sort(key=day_sort_key)
        self.day_label.setText(f"{d.month}월 {d.day}일 ({WEEKDAY_KO[d.weekday()]})")
        self.count_label.setText(
            f"일정 {len(events)}건" if events else "일정이 없습니다")
        while self.items_lay.count():
            item = self.items_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for e in events:
            self.items_lay.addWidget(
                EventItemCard(e, self.store, self._on_item_change))
        self.items_lay.addStretch()
