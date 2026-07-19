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
    QHBoxLayout, QLabel, QLineEdit, QPushButton, QScrollArea, QSplitter,
    QTextEdit, QVBoxLayout, QWidget,
)

from store.event_store import Event, EventStore, PRIORITIES
from ui import theme

WEEKDAY_KO = "월화수목금토일"


class EventCalendar(QCalendarWidget):
    """날짜 셀에 일정 개수 배지를 그리는 달력."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._counts: dict[date, int] = {}
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

    def set_counts(self, counts: dict[date, int]) -> None:
        self._counts = counts
        self.updateCells()

    def paintCell(self, painter: QPainter, rect, qdate: QDate) -> None:
        super().paintCell(painter, rect, qdate)
        n = self._counts.get(date(qdate.year(), qdate.month(), qdate.day()))
        if not n:
            return
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        selected = qdate == self.selectedDate()
        chip_w, chip_h = (20 if n < 10 else 26), 14
        x = rect.center().x() - chip_w / 2
        y = rect.bottom() - chip_h - 3
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("white") if selected else QColor(theme.PRIMARY))
        painter.drawRoundedRect(QRectF(x, y, chip_w, chip_h), 7, 7)
        painter.setPen(QColor(theme.PRIMARY) if selected else QColor("white"))
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
        self.store.update(
            self.event.id,
            title=title,
            start=self.start_edit.dateTime().toPyDateTime().isoformat(),
            all_day=self.all_day_cb.isChecked(),
            priority=self.priority_combo.currentText(),
            memo=self.memo_edit.toPlainText(),
        )
        # 로컬 객체도 갱신해 접힌 줄 표시를 즉시 반영
        self.event.title = title
        self.event.start = self.start_edit.dateTime().toPyDateTime().isoformat()
        self.event.all_day = self.all_day_cb.isChecked()
        self.event.priority = self.priority_combo.currentText()
        self.event.memo = self.memo_edit.toPlainText()
        self._update_labels()
        self.detail.setVisible(False)
        self.on_change(reload_day=False)

    def _delete(self) -> None:
        self.store.remove(self.event.id)
        self.on_change(reload_day=True)


class CalendarWindow(QWidget):
    def __init__(self, store: EventStore, parent=None):
        super().__init__(parent)
        self.store = store
        self.setWindowTitle("내 캘린더 — 쿨 일정 도우미")
        self.resize(780, 500)
        self.setStyleSheet(theme.BASE_QSS + theme.CALENDAR_QSS)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 14, 14, 14)
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
        self.refresh()
        # 다른 창(일정 등록 등)에서 저장/삭제 시 실시간 반영.
        # 지연 호출: 카드 내부 저장 도중 위젯이 파괴되는 재진입을 피한다.
        store.subscribe(lambda: QTimer.singleShot(0, self.refresh))

    # ── 갱신 ────────────────────────────────────────────────
    def refresh(self) -> None:
        counts: dict[date, int] = {}
        for d in self.store.dates_with_events():
            counts[d] = len(self.store.on_date(d))
        self.cal.set_counts(counts)
        self.refresh_day()

    def _on_item_change(self, reload_day: bool) -> None:
        self.refresh() if reload_day else self.cal.set_counts(
            {d: len(self.store.on_date(d)) for d in self.store.dates_with_events()})

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
