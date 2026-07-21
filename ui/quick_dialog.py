# -*- coding: utf-8 -*-
"""⚡ 간편 등록 모달 — 지금 보고 있는 쪽지가 자동으로 채워진 작은 창.

흐름: 쿨메신저에서 쪽지를 본다 → 펭귄 ⚡ → 이 모달(자동 채움) → 수정 → 등록.
폴백: 화면에서 못 찾으면 [클립보드에서 가져오기] / [전체 목록 열기].
"""
from __future__ import annotations

import threading
from datetime import datetime, timedelta

from PyQt6.QtCore import Qt, QObject, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QHBoxLayout, QLabel,
    QLineEdit, QMessageBox, QPushButton, QTextEdit, QVBoxLayout,
)

from parser import pipeline
from parser.pipeline import Candidate
from store.event_store import EventStore
from ui import theme
from ui.review_dialog import (
    DatePickerButton, TimeCombo, cand_ref, highlight_html, kr_date,
)


class _LoadWorker(QObject):
    """캡처·DB 매칭을 백그라운드에서 처리 — 모달은 즉시 뜨고 내용만 나중에 채운다."""
    loaded = pyqtSignal(object)   # (cands, msg, matched, origin) 또는 None

    def __init__(self, base_dir: str, mode: str, text: str = "", parent=None):
        super().__init__(parent)
        self.base_dir, self.mode, self.text = base_dir, mode, text

    def start(self) -> None:
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self) -> None:
        title, body, origin = "", self.text, "클립보드"
        if self.mode == "screen":
            try:
                import capture
                got = capture.read_current_message()
            except Exception:
                got = None
            if got is None:
                self.loaded.emit(None)
                return
            title, body, origin = got.title, got.body, "화면"
        cands, msg, matched = pipeline.quick_candidates(self.base_dir, title, body)
        self.loaded.emit((cands, msg, matched, origin))


class QuickDialog(QDialog):
    def __init__(self, base_dir: str, store: EventStore,
                 google_enabled: bool = False, parent=None):
        super().__init__(parent)
        self.base_dir = base_dir
        self.store = store
        self.google_enabled = google_enabled
        self.candidates: list[Candidate] = []
        self.matched = False
        self.setWindowTitle("⚡ 간편 등록")
        self.resize(520, 520)
        self.setStyleSheet(theme.BASE_QSS)

        lay = QVBoxLayout(self)
        self.status = QLabel()
        self.status.setWordWrap(True)
        self.status.setStyleSheet(
            f"background:{theme.PRIMARY_LIGHT};color:{theme.PRIMARY_DARK};"
            f"border-radius:8px;padding:7px;font-size:11px")
        lay.addWidget(self.status)

        # 감지된 일정이 여러 개면 여기서 선택
        self.event_combo = QComboBox()
        self.event_combo.currentIndexChanged.connect(self._apply_candidate)
        self.event_combo.setVisible(False)
        lay.addWidget(self.event_combo)

        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("일정 제목")
        self.title_edit.setStyleSheet(
            f"QLineEdit{{font-size:14px;font-weight:bold;background:{theme.CARD};"
            f"border:1px solid {theme.BORDER};border-radius:8px;padding:8px}}"
            f"QLineEdit:focus{{border:2px solid {theme.PRIMARY}}}")
        # 한 줄 바: 제목 / 날짜 / 시간 ('종일'은 시간 콤보의 첫 항목)
        bar = QHBoxLayout()
        bar.addWidget(self.title_edit, stretch=1)
        self.date_btn = DatePickerButton()
        bar.addWidget(self.date_btn)
        self.time_combo = TimeCombo()
        bar.addWidget(self.time_combo)
        lay.addLayout(bar)
        self._is_deadline = False   # 마감 여부는 쪽지에서 자동 감지된 값 유지

        self.warn = QLabel()
        self.warn.setWordWrap(True)
        self.warn.setStyleSheet(
            f"color:{theme.DANGER};font-size:11px;font-weight:bold;"
            f"background:#fdecea;border-radius:6px;padding:5px")
        self.warn.setVisible(False)
        lay.addWidget(self.warn)

        self.body_edit = QTextEdit()
        self.body_edit.setPlaceholderText("상세내용")
        lay.addWidget(self.body_edit, stretch=1)

        btns = QHBoxLayout()
        clip_btn = QPushButton("📋 클립보드에서 가져오기")
        clip_btn.setStyleSheet(theme.TEXT_BTN + "QPushButton{font-size:12px}")
        clip_btn.clicked.connect(self._from_clipboard)
        btns.addWidget(clip_btn)
        full_btn = QPushButton("전체 목록 열기")
        full_btn.setStyleSheet(theme.TEXT_BTN + "QPushButton{font-size:12px}")
        full_btn.clicked.connect(self._open_full)
        btns.addWidget(full_btn)
        btns.addStretch()
        if google_enabled:
            self.google_cb = QCheckBox("구글에도")
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

        self._start_load("screen")

    # ── 데이터 채우기 (백그라운드 → 즉시 뜨는 모달) ──────────
    def _start_load(self, mode: str, text: str = "") -> None:
        self.status.setText("쪽지를 읽는 중…")
        self.register_btn.setEnabled(False)
        self._worker = _LoadWorker(self.base_dir, mode, text, self)
        self._worker.loaded.connect(self._on_loaded)
        self._worker.start()

    def _on_loaded(self, result) -> None:
        if result is None:
            self.status.setText(
                "쿨메신저에서 보고 있는 쪽지를 찾지 못했습니다.\n"
                "쪽지 창을 열어두고 다시 ⚡를 누르거나, 아래 "
                "[클립보드에서 가져오기]를 이용하세요.")
            self.register_btn.setEnabled(False)
            return
        cands, msg, matched, origin = result
        self._apply_data(cands, msg, matched, origin)

    def _from_clipboard(self) -> None:
        text = QApplication.clipboard().text().strip()
        if not text:
            QMessageBox.information(self, "안내", "클립보드가 비어 있습니다.")
            return
        self._start_load("clip", text)

    def _fill_from_text(self, title: str, body: str, origin: str) -> None:
        """(테스트·동기 경로용) 텍스트로 바로 채운다."""
        cands, msg, matched = pipeline.quick_candidates(self.base_dir, title, body)
        self._apply_data(cands, msg, matched, origin)

    def _apply_data(self, cands, msg, matched, origin: str) -> None:
        self.candidates = cands
        self.matched = matched
        self._message = msg
        src = (f"지금 보고 있는 쪽지를 가져왔습니다 "
               f"(보낸사람 {msg.sender} · {kr_date(msg.received)})"
               if matched else f"{origin}의 내용을 가져왔습니다")
        if not cands:
            self.status.setText(
                f"{src}\n날짜를 찾지 못했어요 — 일시를 직접 선택해 주세요.")
            # 후보가 없어도 내용으로 등록할 수 있게 기본 후보 구성
            roster_spans = []
            self.title_edit.setText(msg.title)
            self.body_edit.setHtml(highlight_html(msg.body, roster_spans))
            self.date_btn.set_date(datetime.now().date())
            self.time_combo.set_all_day()
            self.register_btn.setEnabled(True)
            return
        self.status.setText(src)
        self.event_combo.blockSignals(True)
        self.event_combo.clear()
        for c in cands:
            when = kr_date(c.start)
            if not c.all_day:
                when += c.start.strftime(" %H:%M")
            self.event_combo.addItem(f"감지된 일정: {when} — {c.suggested_title[:24]}")
        self.event_combo.blockSignals(False)
        self.event_combo.setVisible(len(cands) > 1)
        self.event_combo.setCurrentIndex(0)
        self._apply_candidate(0)
        self.register_btn.setEnabled(True)

    def _apply_candidate(self, idx: int) -> None:
        if not (0 <= idx < len(self.candidates)):
            return
        c = self.candidates[idx]
        self.title_edit.setText(c.suggested_title)
        if c.title_spans:
            found = ", ".join(s.text for s in c.title_spans)
            self.warn.setText(f"⚠ 개인정보로 보이는 부분: {found}")
            self.warn.setVisible(True)
        else:
            self.warn.setVisible(False)
        self.date_btn.set_date(c.start.date())
        if c.all_day:
            self.time_combo.set_all_day()
        else:
            self.time_combo.set_time(c.start.hour, c.start.minute)
        self._is_deadline = c.is_deadline
        self.body_edit.setHtml(highlight_html(c.message.body, c.body_spans))

    # ── 등록 ────────────────────────────────────────────────
    def _register(self) -> None:
        title = self.title_edit.text().strip()
        if not title:
            QMessageBox.warning(self, "확인", "제목을 입력하세요.")
            return
        all_day = self.time_combo.is_all_day()
        d = self.date_btn.get_date()
        h, m = (0, 0) if all_day else self.time_combo.get_time()
        start = datetime(d.year, d.month, d.day, h, m)
        end = None if all_day else start + timedelta(hours=1)

        google_id = None
        if self.google_cb and self.google_cb.isChecked():
            try:
                from calendar_sync import google_sync
                google_id = google_sync.register_event(title, start, end, all_day)
            except Exception as e:
                QMessageBox.warning(self, "구글 등록 실패",
                                    f"로컬에만 저장합니다.\n{e}")

        # DB의 진짜 쪽지와 매칭됐으면 등록 표시(source_ref)도 연동
        idx = self.event_combo.currentIndex() if self.candidates else -1
        ref = ""
        if self.matched and 0 <= idx < len(self.candidates):
            ref = cand_ref(self.candidates[idx])
        self.store.add(title=title, start=start, end=end, all_day=all_day,
                       is_deadline=self._is_deadline,
                       google_id=google_id,
                       memo=self.body_edit.toPlainText().strip(),
                       source_ref=ref)
        self.accept()

    def _open_full(self) -> None:
        self.reject()
        parent = self.parent()
        if parent is not None and hasattr(parent, "open_review"):
            parent.open_review()
