# -*- coding: utf-8 -*-
"""미리보기 카드 다이얼로그.

일정 후보를 카드로 보여주고, 인라인 편집 후 [등록]하면 로컬 저장소에 들어간다.
원문은 개인정보가 빨간색으로 하이라이트된 '마스킹된 보기'로만 표시된다(로컬 전용).
구글 연동이 켜져 있으면 카드마다 [구글에도 등록] 체크박스가 나타난다.
"""
from __future__ import annotations

import html
from datetime import timedelta

from PyQt6.QtCore import Qt, QDateTime
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QDateTimeEdit, QDialog, QFrame, QHBoxLayout,
    QLabel, QLineEdit, QMessageBox, QPushButton, QScrollArea, QTextBrowser,
    QVBoxLayout, QWidget,
)

from parser.pii_detector import PiiSpan
from parser.pipeline import Candidate
from store.event_store import EventStore
from ui import theme


def highlight_html(text: str, spans: list[PiiSpan]) -> str:
    """원문을 그대로 두고, 탐지된 부분만 빨간 글씨로 표시한 HTML을 만든다.

    마스킹하지 않는다 — 지울지 여부는 사용자가 인라인 편집으로 결정한다.
    """
    parts, pos = [], 0
    for s in sorted(spans, key=lambda s: s.start):
        parts.append(html.escape(text[pos:s.start]))
        parts.append(f'<span style="color:#c62828;font-weight:bold;'
                     f'text-decoration:underline">{html.escape(s.text)}</span>')
        pos = s.end
    parts.append(html.escape(text[pos:]))
    return "".join(parts).replace("\n", "<br>")


class CandidateCard(QFrame):
    def __init__(self, cand: Candidate, store: EventStore,
                 google_enabled: bool, demo: bool = False, parent=None):
        super().__init__(parent)
        self.cand = cand
        self.store = store
        self.demo = demo   # 데모 모드 등록분은 표식을 남겨 나중에 일괄 삭제 가능
        self.registered = False
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet(
            f"CandidateCard{{background:{theme.CARD};"
            f"border:1px solid {theme.BORDER};border-radius:12px;margin:4px}}")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 10)
        lay.setSpacing(7)

        # 제목 (원문 그대로, 자유 편집 — 마스킹 없음)
        self.title_edit = QLineEdit(cand.suggested_title)
        self.title_edit.setStyleSheet(
            f"QLineEdit{{font-size:14px;font-weight:bold;background:#fbfdff;"
            f"border:1px solid {theme.BORDER};border-radius:8px;padding:7px}}"
            f"QLineEdit:focus{{border:2px solid {theme.PRIMARY}}}")
        lay.addWidget(self.title_edit)
        if cand.title_spans:
            found = ", ".join(s.text for s in cand.title_spans)
            warn = QLabel(f"⚠ 개인정보로 보이는 부분: {found} — "
                          "등록 전 확인하고 필요하면 지워주세요.")
            warn.setWordWrap(True)
            warn.setStyleSheet(
                f"color:{theme.DANGER};font-size:11px;font-weight:bold;"
                f"background:#fdecea;border-radius:6px;padding:5px")
            lay.addWidget(warn)

        # 일시
        row = QHBoxLayout()
        self.start_edit = QDateTimeEdit(QDateTime(cand.start))
        self.start_edit.setCalendarPopup(True)
        self.start_edit.setDisplayFormat("yyyy-MM-dd (ddd) HH:mm")
        row.addWidget(QLabel("일시:"))
        row.addWidget(self.start_edit)
        self.all_day_cb = QCheckBox("종일")
        self.all_day_cb.setChecked(cand.all_day)
        row.addWidget(self.all_day_cb)
        self.deadline_cb = QCheckBox("마감(할일)")
        self.deadline_cb.setChecked(cand.is_deadline)
        row.addWidget(self.deadline_cb)
        row.addStretch()
        lay.addLayout(row)

        # 근거 + 원문 보기 (마스킹·하이라이트, 로컬 전용)
        src = QLabel(f'근거: "{cand.source_text.strip()}"  ·  '
                     f'받은 쪽지 {cand.message.received:%m/%d %H:%M}')
        src.setStyleSheet(f"color:{theme.SUBTLE};font-size:11px")
        lay.addWidget(src)
        self.body_view = QTextBrowser()
        self.body_view.setHtml(highlight_html(cand.message.body, cand.body_spans))
        self.body_view.setMaximumHeight(110)
        self.body_view.setVisible(False)
        lay.addWidget(self.body_view)

        # 버튼 줄
        btns = QHBoxLayout()
        toggle = QPushButton("원문 보기 ▾")
        toggle.setStyleSheet(theme.TEXT_BTN + "QPushButton{font-size:12px}")
        toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        toggle.clicked.connect(
            lambda: self.body_view.setVisible(not self.body_view.isVisible()))
        btns.addWidget(toggle)
        btns.addStretch()
        if google_enabled:
            self.google_cb = QCheckBox("구글에도 등록")
            self.google_cb.setChecked(True)   # 구글 연동 모드에선 기본 켬
            btns.addWidget(self.google_cb)
        else:
            self.google_cb = None
        self.register_btn = QPushButton("등록")
        self.register_btn.setStyleSheet(theme.PRIMARY_BTN)
        self.register_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.register_btn.clicked.connect(self.register)
        btns.addWidget(self.register_btn)
        lay.addLayout(btns)

    def register(self) -> None:
        title = self.title_edit.text().strip()
        if not title:
            QMessageBox.warning(self, "확인", "제목을 입력하세요.")
            return
        start = self.start_edit.dateTime().toPyDateTime()
        all_day = self.all_day_cb.isChecked()
        end = None
        if self.cand.end:
            end = self.cand.end
        elif not all_day:
            end = start + timedelta(hours=1)

        google_id = None
        if self.google_cb and self.google_cb.isChecked():
            # 온라인 존 경계: 넘어가는 값은 제목·시작·종료 세 가지뿐이다.
            try:
                from calendar_sync import google_sync
                google_id = google_sync.register_event(title, start, end, all_day)
            except Exception as e:  # 네트워크·인증 실패 시 로컬 저장은 계속
                QMessageBox.warning(self, "구글 등록 실패",
                                    f"로컬에만 저장합니다.\n{e}")

        self.store.add(title=title, start=start, end=end, all_day=all_day,
                       is_deadline=self.deadline_cb.isChecked(),
                       google_id=google_id, demo=self.demo)
        self.registered = True
        self.setStyleSheet(
            f"CandidateCard{{background:{theme.SUCCESS_BG};"
            f"border:1px solid {theme.SUCCESS_BORDER};"
            f"border-radius:12px;margin:4px}}")
        self.register_btn.setText("등록됨 ✓")
        self.register_btn.setEnabled(False)


class ReviewDialog(QDialog):
    """일정 후보 미리보기.

    loader: 쪽지 개수를 받아 (candidates, no_event, source)를 돌려주는 함수.
    상단 콤보박스로 10/50/100개를 고르면 그 자리에서 다시 불러온다.
    """

    COUNTS = (10, 50, 100)

    def __init__(self, candidates: list[Candidate], store: EventStore,
                 google_enabled: bool = False, source: str = "db",
                 loader=None, count: int = 10, parent=None):
        super().__init__(parent)
        self.setWindowTitle("일정 후보 미리보기 — 확인 후 등록하세요")
        self.resize(560, 640)
        # 항상 밝은 테마로 고정 (다크 모드에서 입력칸이 검게 그려지는 문제 방지)
        self.setStyleSheet(
            theme.BASE_QSS +
            f"QScrollArea > QWidget > QWidget{{background:{theme.BG}}}")
        self.store = store
        self.google_enabled = google_enabled
        self.loader = loader
        lay = QVBoxLayout(self)

        # 상단: 가져올 쪽지 개수 선택
        top = QHBoxLayout()
        self.head = QLabel()
        self.head.setWordWrap(True)
        top.addWidget(self.head, stretch=1)
        top.addWidget(QLabel("가져올 쪽지:"))
        self.count_combo = QComboBox()
        for n in self.COUNTS:
            self.count_combo.addItem(f"{n}개", n)
        idx = self.COUNTS.index(count) if count in self.COUNTS else 0
        self.count_combo.setCurrentIndex(idx)
        self.count_combo.currentIndexChanged.connect(self._reload)
        top.addWidget(self.count_combo)
        lay.addLayout(top)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        self.cards_lay = QVBoxLayout(inner)
        scroll.setWidget(inner)
        lay.addWidget(scroll)

        close_btn = QPushButton("닫기")
        close_btn.clicked.connect(self.accept)
        lay.addWidget(close_btn)

        self.cards: list[CandidateCard] = []
        self._populate(candidates, source)

    def _populate(self, candidates: list[Candidate], source: str) -> None:
        while self.cards_lay.count():
            item = self.cards_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.cards = []
        demo = source == "demo"
        for c in candidates:
            card = CandidateCard(c, self.store, self.google_enabled, demo=demo)
            self.cards.append(card)
            self.cards_lay.addWidget(card)
        self.cards_lay.addStretch()
        src_label = {"db": "쿨메신저 DB", "excel": "엑셀 내보내기(Plan B)",
                     "demo": "데모 데이터 (가짜 쪽지, 테스트용)"}.get(source, source)
        head = (f"최근 쪽지 {self.count_combo.currentData()}개에서 "
                f"일정 후보 {len(candidates)}건을 찾았습니다. (소스: {src_label})\n"
                "빨간 글씨는 전화번호·이름으로 보이는 부분입니다. "
                "지울지 여부는 제목을 직접 편집해서 결정하세요.")
        if demo:
            head += "\n※ 데모 일정은 설정 → 데이터에서 한 번에 삭제할 수 있습니다."
        self.head.setText(head)

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
