# -*- coding: utf-8 -*-
"""일정 등록 창 — 2분할 레이아웃 (왼쪽 목록 / 오른쪽 상세보기).

- 왼쪽: 후보 목록. 등록된 항목은 연두 배경 + ✓ 등록됨 마크 (재시작 유지,
  캘린더에서 삭제 시 실시간 원복).
- 오른쪽: 제목·일시(모던 피커)·마감 + 상세내용(원문이 채워진 인라인 편집기,
  빨간 표시 포함, 수정하면 일정의 상세내용으로 저장) + 등록 버튼.
"""
from __future__ import annotations

import html
from datetime import date, datetime, timedelta

from PyQt6.QtCore import Qt, QDate, pyqtSignal
from PyQt6.QtWidgets import (
    QCalendarWidget, QCheckBox, QComboBox, QDialog, QFrame, QHBoxLayout,
    QLabel, QLineEdit, QListWidget, QListWidgetItem, QMessageBox,
    QPushButton, QSplitter, QTextEdit, QVBoxLayout, QWidget,
)

from parser.pii_detector import PiiSpan
from parser.pipeline import Candidate
from store.event_store import EventStore
from ui import theme

WEEK_KO = "월화수목금토일"


def kr_date(dt: datetime | date) -> str:
    return f"{dt.month}/{dt.day}({WEEK_KO[dt.weekday()]})"


def cand_ref(cand: Candidate) -> str:
    return f"{cand.message.key}|{cand.start.isoformat()}"


def highlight_html(text: str, spans: list[PiiSpan]) -> str:
    parts, pos = [], 0
    for s in sorted(spans, key=lambda s: s.start):
        parts.append(html.escape(text[pos:s.start]))
        parts.append(f'<span style="color:#c62828;font-weight:bold;'
                     f'text-decoration:underline">{html.escape(s.text)}</span>')
        pos = s.end
    parts.append(html.escape(text[pos:]))
    return "".join(parts).replace("\n", "<br>")


# ── 왼쪽 목록의 행 위젯 (배경·마크를 직접 관리해 스타일시트에 안 덮인다) ──
class CandRow(QFrame):
    def __init__(self, cand: Candidate, parent=None):
        super().__init__(parent)
        self.registered = False
        self.selected = False
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 7, 10, 7)
        lay.setSpacing(2)

        top = QHBoxLayout()
        when = kr_date(cand.start)
        if not cand.all_day:
            when += cand.start.strftime(" %H:%M")
        unread = "● " if cand.message.is_unread else ""   # 안읽은 쪽지 표시
        date_label = QLabel(unread + when + ("  ⏰" if cand.is_deadline else ""))
        date_label.setStyleSheet(
            f"color:{theme.PRIMARY_DARK};font-size:11px;font-weight:bold;"
            f"background:transparent")
        top.addWidget(date_label)
        top.addStretch()
        self.mark = QLabel("✓ 등록됨")
        self.mark.setStyleSheet(
            "background:#2e7d32;color:white;border-radius:8px;"
            "padding:1px 8px;font-size:10px;font-weight:bold")
        self.mark.setVisible(False)
        top.addWidget(self.mark)
        lay.addLayout(top)

        title = QLabel(cand.suggested_title[:38])
        title.setStyleSheet(
            f"color:{theme.TEXT};font-size:12px;background:transparent")
        lay.addWidget(title)
        self._restyle()

    def set_registered(self, registered: bool) -> None:
        self.registered = registered
        self.mark.setVisible(registered)
        self._restyle()

    def set_selected(self, selected: bool) -> None:
        self.selected = selected
        self._restyle()

    def _restyle(self) -> None:
        if self.registered:
            bg = "#dff0e2" if self.selected else theme.SUCCESS_BG
            border = theme.SUCCESS_BORDER
        elif self.selected:
            bg, border = theme.PRIMARY_LIGHT, theme.PRIMARY
        else:
            bg, border = "transparent", "transparent"
        self.setStyleSheet(
            f"CandRow{{background:{bg};border:1px solid {border};"
            f"border-radius:8px}}")


# ── 모던 날짜·시간 피커 ─────────────────────────────────────
class DatePickerButton(QPushButton):
    """클릭하면 테마 적용된 달력 팝업이 뜨는 날짜 버튼."""
    dateChanged = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._date = date.today()
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(
            f"QPushButton{{background:{theme.CARD};color:{theme.TEXT};"
            f"border:1px solid {theme.BORDER};border-radius:8px;"
            f"padding:7px 14px;font-size:13px;text-align:left}}"
            f"QPushButton:hover{{border-color:{theme.PRIMARY}}}")
        self.clicked.connect(self._open)
        self._sync()

    def set_date(self, d: date) -> None:
        self._date = d
        self._sync()

    def get_date(self) -> date:
        return self._date

    def _sync(self) -> None:
        self.setText(f"📅  {self._date.year}-{self._date.month:02d}-"
                     f"{self._date.day:02d} ({WEEK_KO[self._date.weekday()]})")

    def _open(self) -> None:
        pop = QWidget(None, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        pop.setStyleSheet(theme.BASE_QSS + theme.CALENDAR_QSS)
        lay = QVBoxLayout(pop)
        lay.setContentsMargins(4, 4, 4, 4)
        cal = QCalendarWidget()
        cal.setVerticalHeaderFormat(
            QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader)
        cal.setGridVisible(False)
        cal.setSelectedDate(QDate(self._date.year, self._date.month, self._date.day))

        def picked(qd: QDate):
            self._date = date(qd.year(), qd.month(), qd.day())
            self._sync()
            self.dateChanged.emit(self._date)
            pop.close()

        cal.clicked.connect(picked)
        lay.addWidget(cal)
        pop.adjustSize()
        pos = self.mapToGlobal(self.rect().bottomLeft())
        pop.move(pos.x(), pos.y() + 4)
        pop.show()


class TimeCombo(QComboBox):
    """30분 단위 드롭다운 + 직접 입력(예: 14:05)도 되는 시간 선택."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setEditable(True)
        for h in range(0, 24):
            for m in (0, 30):
                self.addItem(f"{h:02d}:{m:02d}")
        self.setFixedWidth(92)

    def set_time(self, h: int, m: int) -> None:
        self.setCurrentText(f"{h:02d}:{m:02d}")

    def get_time(self) -> tuple[int, int]:
        try:
            h, m = self.currentText().strip().split(":")
            return max(0, min(23, int(h))), max(0, min(59, int(m)))
        except ValueError:
            return 0, 0


class ReviewDialog(QDialog):
    COUNTS = (10, 50, 100)

    def __init__(self, candidates: list[Candidate], store: EventStore,
                 google_enabled: bool = False, source: str = "db",
                 loader=None, count: int = 10, fav_store=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("일정 등록")
        self.resize(880, 580)
        self.setStyleSheet(theme.BASE_QSS)
        self.store = store
        self.google_enabled = google_enabled
        self.loader = loader
        self.candidates: list[Candidate] = []
        self.rows: list[CandRow] = []
        self.source = source
        self._current: Candidate | None = None
        self.fav_store = fav_store
        self.config = getattr(parent, "config", {}) if parent else {}

        lay = QVBoxLayout(self)

        top = QHBoxLayout()
        title = QLabel("일정 등록")
        title.setStyleSheet(
            f"font-size:16px;font-weight:bold;color:{theme.PRIMARY_DARK}")
        top.addWidget(title)
        self.src_label = QLabel()
        self.src_label.setStyleSheet(f"color:{theme.SUBTLE};font-size:11px")
        top.addWidget(self.src_label)
        top.addStretch()
        top.addWidget(QLabel("가져올 쪽지:"))
        self.count_combo = QComboBox()
        for n in self.COUNTS:
            self.count_combo.addItem(f"{n}개", n)
        idx = self.COUNTS.index(count) if count in self.COUNTS else 0
        self.count_combo.setCurrentIndex(idx)
        self.count_combo.currentIndexChanged.connect(self._reload)
        top.addWidget(self.count_combo)
        lay.addLayout(top)

        split = QSplitter(Qt.Orientation.Horizontal)
        self.list = QListWidget()
        self.list.setStyleSheet(
            f"QListWidget{{background:{theme.CARD};border:1px solid {theme.BORDER};"
            f"border-radius:10px;padding:4px}}"
            f"QListWidget::item{{border:none;padding:1px}}"
            f"QListWidget::item:selected{{background:transparent}}")
        self.list.currentRowChanged.connect(self._show_detail)
        split.addWidget(self.list)
        split.addWidget(self._build_detail())
        split.setSizes([330, 550])
        lay.addWidget(split, stretch=1)

        close_btn = QPushButton("닫기")
        close_btn.clicked.connect(self.accept)
        lay.addWidget(close_btn)

        self._populate(candidates, source)
        self.store.subscribe(self._refresh_marks)

    # ── 상세 패널 ────────────────────────────────────────────
    def _build_detail(self) -> QWidget:
        panel = QWidget()
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(10, 0, 0, 0)

        self.title_edit = QLineEdit()
        self.title_edit.setStyleSheet(
            f"QLineEdit{{font-size:14px;font-weight:bold;background:{theme.CARD};"
            f"border:1px solid {theme.BORDER};border-radius:8px;padding:8px}}"
            f"QLineEdit:focus{{border:2px solid {theme.PRIMARY}}}")
        lay.addWidget(self.title_edit)

        self.warn = QLabel()
        self.warn.setWordWrap(True)
        self.warn.setStyleSheet(
            f"color:{theme.DANGER};font-size:11px;font-weight:bold;"
            f"background:#fdecea;border-radius:6px;padding:5px")
        self.warn.setVisible(False)
        lay.addWidget(self.warn)

        row = QHBoxLayout()
        row.addWidget(QLabel("일시"))
        self.date_btn = DatePickerButton()
        row.addWidget(self.date_btn)
        self.time_combo = TimeCombo()
        row.addWidget(self.time_combo)
        self.all_day_cb = QCheckBox("종일")
        self.all_day_cb.toggled.connect(
            lambda on: self.time_combo.setEnabled(not on))
        row.addWidget(self.all_day_cb)
        self.deadline_cb = QCheckBox("마감(할일)")
        row.addWidget(self.deadline_cb)
        row.addStretch()
        lay.addLayout(row)

        self.src_info = QLabel()
        self.src_info.setStyleSheet(f"color:{theme.SUBTLE};font-size:11px")
        lay.addWidget(self.src_info)

        body_head = QLabel("상세내용 — 원문이 채워져 있습니다. 이 자리에서 바로 "
                           "수정하면 일정의 상세내용으로 저장됩니다.")
        body_head.setStyleSheet(f"color:{theme.SUBTLE};font-size:11px")
        lay.addWidget(body_head)
        self.body_edit = QTextEdit()      # 인라인 편집 (빨간 표시 포함 리치 텍스트)
        lay.addWidget(self.body_edit, stretch=1)

        btns = QHBoxLayout()
        self.fav_btn = QPushButton("☆ 즐겨찾기")
        self.fav_btn.setStyleSheet(theme.TEXT_BTN)
        self.fav_btn.setToolTip("제목과 상세내용을 즐겨찾기 보관함에 저장 "
                                "(캘린더 창 → ★ 즐겨찾기 탭)")
        self.fav_btn.setVisible(bool(self.config.get("favorites_enabled"))
                                and self.fav_store is not None)
        self.fav_btn.clicked.connect(self._save_favorite)
        btns.addWidget(self.fav_btn)
        btns.addStretch()
        if self.google_enabled:
            self.google_cb = QCheckBox("구글에도 등록")
            self.google_cb.setChecked(True)
            btns.addWidget(self.google_cb)
        else:
            self.google_cb = None
        self.register_btn = QPushButton("일정 등록")
        self.register_btn.setStyleSheet(theme.PRIMARY_BTN)
        self.register_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.register_btn.clicked.connect(self._register)
        btns.addWidget(self.register_btn)
        lay.addLayout(btns)
        return panel

    # ── 목록 ────────────────────────────────────────────────
    def _populate(self, candidates: list[Candidate], source: str) -> None:
        self.candidates = candidates
        self.source = source
        src_label = {"db": "쿨메신저 DB", "excel": "엑셀 내보내기(Plan B)",
                     "demo": "데모 데이터 (테스트용)"}.get(source, source)
        self.src_label.setText(
            f"후보 {len(candidates)}건 · 소스: {src_label}"
            + ("  ※ 데모 일정은 설정→데이터에서 일괄 삭제" if source == "demo" else ""))
        self.list.blockSignals(True)
        self.list.clear()
        self.rows = []
        refs = self.store.registered_refs()
        for c in candidates:
            row = CandRow(c)
            row.set_registered(cand_ref(c) in refs)
            item = QListWidgetItem()
            item.setSizeHint(row.sizeHint())
            self.list.addItem(item)
            self.list.setItemWidget(item, row)
            self.rows.append(row)
        self.list.blockSignals(False)
        if candidates:
            self.list.setCurrentRow(0)
        else:
            self._current = None
            self.title_edit.setText("")
            self.body_edit.setHtml(
                "<i>일정 후보가 없습니다. 위에서 쪽지 개수를 늘려보세요.</i>")
            self.register_btn.setEnabled(False)

    def _refresh_marks(self) -> None:
        refs = self.store.registered_refs()
        for c, row in zip(self.candidates, self.rows):
            row.set_registered(cand_ref(c) in refs)
        self._update_register_btn()

    # ── 상세 표시 ────────────────────────────────────────────
    def _show_detail(self, idx: int) -> None:
        for i, row in enumerate(self.rows):
            row.set_selected(i == idx)
        if not (0 <= idx < len(self.candidates)):
            return
        c = self._current = self.candidates[idx]
        self.title_edit.setText(c.suggested_title)
        if c.title_spans:
            found = ", ".join(s.text for s in c.title_spans)
            self.warn.setText(f"⚠ 개인정보로 보이는 부분: {found} — "
                              "등록 전 확인하고 필요하면 지워주세요.")
            self.warn.setVisible(True)
        else:
            self.warn.setVisible(False)
        self.date_btn.set_date(c.start.date())
        self.time_combo.set_time(c.start.hour, c.start.minute)
        self.all_day_cb.setChecked(c.all_day)
        self.time_combo.setEnabled(not c.all_day)
        self.deadline_cb.setChecked(c.is_deadline)
        self.src_info.setText(
            f'근거: "{c.source_text.strip()}" · 보낸사람 {c.message.sender} '
            f'· 받은 시각 {kr_date(c.message.received)} '
            f'{c.message.received:%H:%M}')
        self.body_edit.setHtml(highlight_html(c.message.body, c.body_spans))
        self._update_register_btn()

    def _update_register_btn(self) -> None:
        if self._current is None:
            return
        registered = cand_ref(self._current) in self.store.registered_refs()
        self.register_btn.setEnabled(True)
        if registered:
            self.register_btn.setText("등록 취소")
            self.register_btn.setStyleSheet(
                f"QPushButton{{background:{theme.CARD};color:{theme.DANGER};"
                f"border:1.5px solid {theme.DANGER};border-radius:8px;"
                f"padding:9px 18px;font-weight:bold}}"
                f"QPushButton:hover{{background:#fdecea}}")
        else:
            self.register_btn.setText("일정 등록")
            self.register_btn.setStyleSheet(theme.PRIMARY_BTN)

    def _save_favorite(self) -> None:
        if self.fav_store is None or self._current is None:
            return
        title = self.title_edit.text().strip() or "(제목 없음)"
        self.fav_store.add(title, self.body_edit.toPlainText().strip())
        self.fav_btn.setText("★ 저장됨")
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(1500, lambda: self.fav_btn.setText("☆ 즐겨찾기"))

    # ── 등록 / 등록 취소 ─────────────────────────────────────
    def _unregister(self, ref: str) -> None:
        """이 후보로 등록했던 일정을 삭제한다 (구글에 올린 것도 함께 시도)."""
        for e in list(self.store.all()):
            if e.source_ref == ref:
                if e.google_id:
                    try:
                        from calendar_sync import google_sync
                        google_sync.delete_event(e.google_id)
                    except Exception:
                        QMessageBox.information(
                            self, "안내",
                            "구글 캘린더의 사본은 삭제하지 못했습니다.\n"
                            "구글 캘린더에서 직접 지워주세요.")
                self.store.remove(e.id)

    def _register(self) -> None:
        c = self._current
        if c is None:
            return
        if cand_ref(c) in self.store.registered_refs():   # 등록 취소
            self._unregister(cand_ref(c))
            return
        title = self.title_edit.text().strip()
        if not title:
            QMessageBox.warning(self, "확인", "제목을 입력하세요.")
            return
        all_day = self.all_day_cb.isChecked()
        d = self.date_btn.get_date()
        h, m = (0, 0) if all_day else self.time_combo.get_time()
        start = datetime(d.year, d.month, d.day, h, m)
        end = c.end if c.end else (None if all_day else start + timedelta(hours=1))

        google_id = None
        if self.google_cb and self.google_cb.isChecked():
            # 온라인 존 경계: 제목·시작·종료만 넘어간다
            try:
                from calendar_sync import google_sync
                google_id = google_sync.register_event(title, start, end, all_day)
            except Exception as e:
                QMessageBox.warning(self, "구글 등록 실패",
                                    f"로컬에만 저장합니다.\n{e}")

        self.store.add(title=title, start=start, end=end, all_day=all_day,
                       is_deadline=self.deadline_cb.isChecked(),
                       google_id=google_id, demo=(self.source == "demo"),
                       memo=self.body_edit.toPlainText().strip(),
                       source_ref=cand_ref(c))

    def _reload(self) -> None:
        if not self.loader:
            return
        n = self.count_combo.currentData()
        try:
            candidates, _no_event, source = self.loader(n)
        except Exception as e:
            QMessageBox.critical(self, "오류", f"다시 불러오지 못했습니다.\n{e}")
            return
        self._populate(candidates, source)

    def done(self, r: int) -> None:
        self.store.unsubscribe(self._refresh_marks)
        super().done(r)
