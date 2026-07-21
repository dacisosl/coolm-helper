# -*- coding: utf-8 -*-
"""내장 캘린더 (전부 로컬, 인터넷 불필요).

- 날짜 셀 아래에 일정 개수 배지만 표시
- 날짜 클릭 → 오른쪽에 투두리스트 스타일 목록 (중요도 칩 + 제목)
- 항목 클릭 → 아코디언 상세보기, 인라인 편집 후 [저장]
"""
from __future__ import annotations

from datetime import date, datetime

from PyQt6.QtCore import Qt, QDate, QRectF, QTimer
from PyQt6.QtGui import QColor, QFont, QPainter, QTextCharFormat
from PyQt6.QtWidgets import (
    QCalendarWidget, QCheckBox, QComboBox, QDateTimeEdit, QFrame,
    QGraphicsDropShadowEffect, QHBoxLayout, QLabel, QLineEdit, QPushButton,
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
        sun.setForeground(QColor("#e57373"))
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
        base = QColor("#e53935") if has_high else QColor(theme.PRIMARY)
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        selected = qdate == self.selectedDate()
        chip_w, chip_h = (20 if n < 10 else 26), 14
        x = rect.center().x() - chip_w / 2
        y = rect.bottom() - chip_h - 3
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("white") if selected else base)
        painter.drawRoundedRect(QRectF(x, y, chip_w, chip_h), 7, 7)
        painter.setPen(base if selected else QColor("white"))
        f = QFont(self.font())
        f.setPointSize(7)
        f.setBold(True)
        painter.setFont(f)
        painter.drawText(QRectF(x, y, chip_w, chip_h),
                         Qt.AlignmentFlag.AlignCenter, str(n))
        painter.restore()


class EventItemCard(QFrame):
    """투두리스트 항목 — 클릭하면 아코디언으로 상세보기가 펼쳐진다."""

    def __init__(self, event: Event, store: EventStore, on_change, parent=None):
        super().__init__(parent)
        self.event = event
        self.store = store
        self.on_change = on_change   # 저장/삭제 후 부모 갱신 콜백
        self.setStyleSheet(
            f"EventItemCard{{background:{theme.CARD};border:none;"
            f"border-radius:12px}}"
            f"EventItemCard:hover{{background:#fbfdff}}")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(6)

        # ── 접힌 줄: [중요도] 제목  ·  시간 ──
        row = QHBoxLayout()
        self.chip = QLabel(event.priority)
        self.chip.setStyleSheet(theme.priority_chip(event.priority))
        row.addWidget(self.chip)
        self.title_label = QLabel(event.title)
        self.title_label.setStyleSheet(
            f"font-size:13px;font-weight:bold;color:{theme.TEXT}")
        self.title_label.setWordWrap(True)
        row.addWidget(self.title_label, stretch=1)
        self.time_label = QLabel()
        self.time_label.setStyleSheet(f"color:{theme.SUBTLE};font-size:11px")
        row.addWidget(self.time_label)
        lay.addLayout(row)
        self._update_labels()

        # ── 상세보기 (아코디언, 기본 접힘) ──
        self.detail = QWidget()
        self.detail.setVisible(False)
        d = QVBoxLayout(self.detail)
        d.setContentsMargins(0, 4, 0, 0)
        d.setSpacing(6)

        self.title_edit = QLineEdit(event.title)
        d.addWidget(self.title_edit)

        opts = QHBoxLayout()
        self.start_edit = QDateTimeEdit()
        self.start_edit.setCalendarPopup(True)
        self.start_edit.setDisplayFormat("yyyy-MM-dd (ddd) HH:mm")
        self.start_edit.setDateTime(event.start_dt)
        opts.addWidget(QLabel("일시"))
        opts.addWidget(self.start_edit)
        self.all_day_cb = QCheckBox("종일")
        self.all_day_cb.setChecked(event.all_day)
        opts.addWidget(self.all_day_cb)
        opts.addWidget(QLabel("중요도"))
        self.priority_combo = QComboBox()
        self.priority_combo.addItems(PRIORITIES)
        self.priority_combo.setCurrentText(event.priority)
        opts.addWidget(self.priority_combo)
        opts.addStretch()
        d.addLayout(opts)

        self.memo_edit = QTextEdit(event.memo)
        self.memo_edit.setPlaceholderText("메모 (로컬에만 저장됩니다)")
        self.memo_edit.setMaximumHeight(70)
        d.addWidget(self.memo_edit)

        btns = QHBoxLayout()
        del_btn = QPushButton("삭제")
        del_btn.setStyleSheet(
            f"QPushButton{{background:transparent;color:{theme.DANGER};"
            f"border:none;font-size:12px;padding:5px}}"
            f"QPushButton:hover{{background:#fdecea;border-radius:6px}}")
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

    def _update_labels(self) -> None:
        e = self.event
        self.title_label.setText(e.title)
        self.chip.setText(e.priority)
        self.chip.setStyleSheet(theme.priority_chip(e.priority))
        t = "종일" if e.all_day else e.start_dt.strftime("%H:%M")
        if e.end_dt and e.end_dt.date() != e.start_dt.date():
            t += f" ~{e.end_dt:%m/%d}"
        if e.google_id:
            t += " · G"
        self.time_label.setText(t)

    # 접힌 줄 클릭 → 아코디언 토글 (버튼·입력칸 클릭은 제외)
    def mousePressEvent(self, ev):
        if not self.detail.isVisible():
            self.detail.setVisible(True)
        elif ev.position().y() < 34:   # 상단 요약줄을 다시 누르면 접기
            self.detail.setVisible(False)
        super().mousePressEvent(ev)

    def _save(self) -> None:
        title = self.title_edit.text().strip() or self.event.title
        new_start = self.start_edit.dateTime().toPyDateTime()
        new_all_day = self.all_day_cb.isChecked()
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
        self.event.start = self.start_edit.dateTime().toPyDateTime().isoformat()
        self.event.all_day = self.all_day_cb.isChecked()
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
        self.store.remove(self.event.id)
        self.on_change(reload_day=True)


class CalendarWindow(QWidget):
    """테두리 없는 캘린더 창 — 커스텀 타이틀바(최소화/닫기) + 탭(캘린더/즐겨찾기)."""

    def __init__(self, store: EventStore, fav_store=None,
                 favorites_enabled: bool = False, parent=None):
        super().__init__(parent)
        self.store = store
        self.setWindowTitle("내 캘린더 — 쿨 일정 도우미")
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
            + f"#calcard{{background:{theme.BG};border-radius:16px;"
              f"border:1px solid {theme.BORDER}}}")
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(24)
        shadow.setOffset(0, 4)
        shadow.setColor(QColor(30, 136, 229, 55))
        card.setGraphicsEffect(shadow)
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
                                   ("✕", "닫기", self.close)):
            b = QPushButton(text)
            b.setFixedSize(30, 26)
            b.setToolTip(tip)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            hover = "#fdecea;color:#c62828" if text == "✕" else \
                f"{theme.PRIMARY_LIGHT};color:{theme.PRIMARY_DARK}"
            b.setStyleSheet(
                f"QPushButton{{background:transparent;color:{theme.SUBTLE};"
                f"border:none;border-radius:6px;font-size:13px}}"
                f"QPushButton:hover{{background:{hover}}}")
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
        store.subscribe(lambda: QTimer.singleShot(0, self.refresh))

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
        order = {"높음": 0, "보통": 1, "낮음": 2}
        events.sort(key=lambda e: (order.get(e.priority, 1), e.start))
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
