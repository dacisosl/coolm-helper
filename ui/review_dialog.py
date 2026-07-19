# -*- coding: utf-8 -*-
"""일정 등록 창 — 2분할 레이아웃 (왼쪽 목록 / 오른쪽 상세보기).

- 왼쪽: 일정 후보 목록. 등록된 항목은 연두색 배경으로 구분되며,
  이 표시는 재시작해도 유지되고(source_ref) 캘린더에서 삭제하면 즉시 원복된다.
- 오른쪽: 제목·일시·마감 + 원문(빨간 표시) + 메모(인라인 편집) + 등록 버튼.
"""
from __future__ import annotations

import html
from datetime import timedelta

from PyQt6.QtCore import Qt, QDateTime
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QDateTimeEdit, QDialog, QHBoxLayout, QLabel,
    QLineEdit, QListWidget, QListWidgetItem, QMessageBox, QPushButton,
    QSplitter, QTextBrowser, QTextEdit, QVBoxLayout, QWidget,
)

from parser.pii_detector import PiiSpan
from parser.pipeline import Candidate
from store.event_store import EventStore
from ui import theme

REGISTERED_BG = QColor("#e9f7ec")   # 등록된 항목의 목록 배경


def cand_ref(cand: Candidate) -> str:
    """후보의 고유 참조 — Event.source_ref와 대조해 등록 여부를 판단한다."""
    return f"{cand.message.key}|{cand.start.isoformat()}"


def highlight_html(text: str, spans: list[PiiSpan]) -> str:
    """원문 유지 + 탐지 부분만 빨간 글씨 (마스킹하지 않음 — 사용자가 결정)."""
    parts, pos = [], 0
    for s in sorted(spans, key=lambda s: s.start):
        parts.append(html.escape(text[pos:s.start]))
        parts.append(f'<span style="color:#c62828;font-weight:bold;'
                     f'text-decoration:underline">{html.escape(s.text)}</span>')
        pos = s.end
    parts.append(html.escape(text[pos:]))
    return "".join(parts).replace("\n", "<br>")


class ReviewDialog(QDialog):
    COUNTS = (10, 50, 100)

    def __init__(self, candidates: list[Candidate], store: EventStore,
                 google_enabled: bool = False, source: str = "db",
                 loader=None, count: int = 10, parent=None):
        super().__init__(parent)
        self.setWindowTitle("일정 등록")
        self.resize(860, 560)
        self.setStyleSheet(theme.BASE_QSS)
        self.store = store
        self.google_enabled = google_enabled
        self.loader = loader
        self.candidates: list[Candidate] = []
        self.source = source
        self._current: Candidate | None = None
        self.config = getattr(parent, "config", {}) if parent else {}

        lay = QVBoxLayout(self)

        # ── 상단 메뉴바: 제목 + 쪽지 개수 ──
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

        # ── 2분할: 왼쪽 목록 / 오른쪽 상세 ──
        split = QSplitter(Qt.Orientation.Horizontal)
        self.list = QListWidget()
        self.list.setStyleSheet(
            f"QListWidget{{background:{theme.CARD};border:1px solid {theme.BORDER};"
            f"border-radius:10px;font-size:12px}}"
            f"QListWidget::item{{padding:9px;border-bottom:1px solid #f0f4f9}}"
            f"QListWidget::item:selected{{background:{theme.PRIMARY_LIGHT};"
            f"color:{theme.PRIMARY_DARK}}}")
        self.list.currentRowChanged.connect(self._show_detail)
        split.addWidget(self.list)
        split.addWidget(self._build_detail())
        split.setSizes([330, 530])
        lay.addWidget(split, stretch=1)

        close_btn = QPushButton("닫기")
        close_btn.clicked.connect(self.accept)
        lay.addWidget(close_btn)

        self._populate(candidates, source)
        # 캘린더에서 삭제하면 목록 배경 실시간 원복
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
        self.start_edit = QDateTimeEdit()
        self.start_edit.setCalendarPopup(True)
        self.start_edit.setDisplayFormat("yyyy-MM-dd (ddd) HH:mm")
        row.addWidget(self.start_edit)
        self.all_day_cb = QCheckBox("종일")
        row.addWidget(self.all_day_cb)
        self.deadline_cb = QCheckBox("마감(할일)")
        row.addWidget(self.deadline_cb)
        row.addStretch()
        lay.addLayout(row)

        self.src_info = QLabel()
        self.src_info.setStyleSheet(f"color:{theme.SUBTLE};font-size:11px")
        lay.addWidget(self.src_info)

        self.body_view = QTextBrowser()
        lay.addWidget(self.body_view, stretch=3)

        self.memo_edit = QTextEdit()
        self.memo_edit.setPlaceholderText(
            "일정 메모 (선택) — 등록하면 일정의 상세내용으로 저장됩니다")
        self.memo_edit.setMaximumHeight(72)
        lay.addWidget(self.memo_edit, stretch=1)

        btns = QHBoxLayout()
        self.fav_btn = QPushButton("☆ 즐겨찾기")
        self.fav_btn.setStyleSheet(theme.TEXT_BTN)
        self.fav_btn.setVisible(bool(self.config.get("favorites_enabled")))
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
        refs = self.store.registered_refs()
        for c in candidates:
            when = c.start.strftime("%m/%d(%a)")
            if not c.all_day:
                when += c.start.strftime(" %H:%M")
            flags = "⏰" if c.is_deadline else ""
            item = QListWidgetItem(
                f"{when} {flags}\n{c.suggested_title[:34]}")
            if cand_ref(c) in refs:
                item.setBackground(REGISTERED_BG)
            self.list.addItem(item)
        self.list.blockSignals(False)
        if candidates:
            self.list.setCurrentRow(0)
        else:
            self._current = None
            self.title_edit.setText("")
            self.body_view.setHtml(
                "<i>일정 후보가 없습니다. 위에서 쪽지 개수를 늘려보세요.</i>")
            self.register_btn.setEnabled(False)

    def _refresh_marks(self) -> None:
        refs = self.store.registered_refs()
        for i, c in enumerate(self.candidates):
            item = self.list.item(i)
            if item:
                registered = cand_ref(c) in refs
                item.setBackground(REGISTERED_BG if registered
                                   else QColor("transparent"))
        self._update_register_btn()

    # ── 상세 표시 ────────────────────────────────────────────
    def _show_detail(self, row: int) -> None:
        if not (0 <= row < len(self.candidates)):
            return
        c = self._current = self.candidates[row]
        self.title_edit.setText(c.suggested_title)
        if c.title_spans:
            found = ", ".join(s.text for s in c.title_spans)
            self.warn.setText(f"⚠ 개인정보로 보이는 부분: {found} — "
                              "등록 전 확인하고 필요하면 지워주세요.")
            self.warn.setVisible(True)
        else:
            self.warn.setVisible(False)
        self.start_edit.setDateTime(QDateTime(c.start))
        self.all_day_cb.setChecked(c.all_day)
        self.deadline_cb.setChecked(c.is_deadline)
        self.src_info.setText(
            f'근거: "{c.source_text.strip()}" · 보낸사람 {c.message.sender} '
            f'· 받은 시각 {c.message.received:%m/%d %H:%M}')
        self.body_view.setHtml(highlight_html(c.message.body, c.body_spans))
        self.memo_edit.setPlainText("")
        self._update_register_btn()

    def _update_register_btn(self) -> None:
        if self._current is None:
            return
        registered = cand_ref(self._current) in self.store.registered_refs()
        self.register_btn.setEnabled(not registered)
        self.register_btn.setText("등록됨 ✓" if registered else "일정 등록")

    # ── 등록 ────────────────────────────────────────────────
    def _register(self) -> None:
        c = self._current
        if c is None:
            return
        title = self.title_edit.text().strip()
        if not title:
            QMessageBox.warning(self, "확인", "제목을 입력하세요.")
            return
        start = self.start_edit.dateTime().toPyDateTime()
        all_day = self.all_day_cb.isChecked()
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
                       memo=self.memo_edit.toPlainText().strip(),
                       source_ref=cand_ref(c))
        # store._notify() → _refresh_marks가 배경·버튼을 갱신한다

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
