# -*- coding: utf-8 -*-
"""안내문구 보정 창 — 붙여넣은 글을 AI로 다듬는다 (공개용 글 전용).

쪽지 자동 불러오기 없음. 입력창에 직접 붙여넣은 텍스트만 전송된다.
디자인(2026-07-21 v2): 미니멀 — 가운데 열(최대 680px)에 인사 문구 +
둥근 입력 카드(원형 ↑ 보내기 버튼). 보정 중엔 얇은 진행선, 완료되면
다듬은 글 카드가 아래에서 페이드로 등장. 버튼·칩·닫기 줄 최소화.
"""
from __future__ import annotations

import threading

from PyQt6.QtCore import Qt, QObject, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication, QDialog, QFrame, QHBoxLayout, QLabel, QProgressBar,
    QPushButton, QScrollArea, QTextEdit, QVBoxLayout, QWidget,
)

from ui import motion, theme

_TIP = ("공개용 글 전용 — 붙여넣은 내용은 AI 서버(Gemini/OpenRouter)로 "
        "전송돼요.\n개인정보가 들어간 글은 넣지 마세요. "
        "쪽지는 자동으로 불러오지 않아요.")


class _PromptEdit(QTextEdit):
    """Enter=보내기, Shift+Enter=줄바꿈."""
    submitted = pyqtSignal()

    def keyPressEvent(self, ev):
        if ev.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and \
                not (ev.modifiers() & Qt.KeyboardModifier.ShiftModifier):
            self.submitted.emit()
            return
        super().keyPressEvent(ev)


class _Worker(QObject):
    done = pyqtSignal(str)
    failed = pyqtSignal(str)

    def __init__(self, text: str, config: dict, parent=None):
        super().__init__(parent)
        self.text, self.config = text, config

    def start(self) -> None:
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self) -> None:
        import proofread
        try:
            self.done.emit(proofread.proofread(self.text, self.config))
        except Exception as e:
            self.failed.emit(str(e))


class ProofDialog(motion.FadeInMixin, QDialog):
    def __init__(self, config: dict, parent=None):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("안내문구 보정")
        self.resize(720, 620)
        self.setMinimumSize(600, 520)
        self.setMaximumSize(960, 900)     # 갑자기 전체 폭으로 커지는 것 방지
        self.setStyleSheet(theme.BASE_QSS + f"QDialog{{background:{theme.BG}}}")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 0, 24, 16)
        outer.setSpacing(0)

        # 창이 아무리 넓어져도 내용은 가운데 열(최대 680px)에 머문다
        center = QHBoxLayout()
        col_w = QWidget()
        col_w.setMaximumWidth(680)
        col_w.setStyleSheet("background:transparent")
        col = QVBoxLayout(col_w)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(0)
        center.addStretch()
        center.addWidget(col_w, stretch=1)
        center.addStretch()
        outer.addLayout(center, stretch=1)

        col.addSpacing(40)

        # ── 인사 문구 ──
        greet = QLabel("어떤 글을 다듬어 드릴까요?")
        greet.setAlignment(Qt.AlignmentFlag.AlignCenter)
        greet.setStyleSheet(
            f"font-size:22px;font-weight:bold;color:{theme.TEXT};"
            f"background:transparent")
        col.addWidget(greet)
        col.addSpacing(6)
        sub_row = QHBoxLayout()
        sub_row.addStretch()
        sub = QLabel("공개용 글을 붙여넣으면 정중하게 다듬어 드려요")
        sub.setStyleSheet(
            f"color:{theme.SUBTLE};font-size:{theme.FONT_SM}px;"
            f"background:transparent")
        sub_row.addWidget(sub)
        info = QLabel("?")
        info.setFixedSize(16, 16)
        info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info.setToolTip(_TIP)
        info.setStyleSheet(
            f"background:{theme.PRIMARY_LIGHT};color:{theme.PRIMARY_DARK};"
            f"border-radius:8px;font-size:{theme.FONT_XS}px;font-weight:bold")
        sub_row.addWidget(info)
        sub_row.addStretch()
        col.addLayout(sub_row)
        col.addSpacing(24)

        # ── 둥근 입력 카드 ──
        pill = QFrame()
        pill.setObjectName("pill")
        pill.setStyleSheet(
            f"#pill{{background:{theme.CARD};border:1px solid {theme.BORDER};"
            f"border-radius:26px}}")
        pill.setGraphicsEffect(theme.make_shadow(self, 1))
        pl = QVBoxLayout(pill)
        pl.setContentsMargins(20, 16, 12, 10)
        pl.setSpacing(4)
        self.input_edit = _PromptEdit()
        self.input_edit.setPlaceholderText("다듬고 싶은 글을 붙여넣거나 써보세요")
        self.input_edit.setToolTip(_TIP)
        self.input_edit.setStyleSheet(
            f"QTextEdit{{background:transparent;border:none;padding:0;"
            f"font-size:{theme.FONT_MD}px;line-height:150%;color:{theme.TEXT}}}")
        self.input_edit.setMinimumHeight(56)
        self.input_edit.setMaximumHeight(140)
        self.input_edit.submitted.connect(self._go)
        self.input_edit.textChanged.connect(self._sync_count)
        pl.addWidget(self.input_edit)
        # 하단 줄: 모델 이름(연한 글씨) · 글자 수 · 원형 ↑ 보내기
        bar = QHBoxLayout()
        bar.setSpacing(10)
        prov = ("OpenRouter"
                if self.config.get("proof_provider") == "openrouter"
                else "Gemini 3.5 Flash")
        model_label = QLabel(prov)
        model_label.setStyleSheet(
            f"color:{theme.SUBTLE};font-size:{theme.FONT_XS}px;"
            f"background:transparent")
        bar.addWidget(model_label)
        bar.addStretch()
        self.in_count = QLabel("")
        self.in_count.setStyleSheet(
            f"color:{theme.SUBTLE};font-size:{theme.FONT_XS}px;"
            f"background:transparent")
        bar.addWidget(self.in_count)
        self.go_btn = QPushButton("↑")
        self.go_btn.setFixedSize(38, 38)
        self.go_btn.setToolTip("다듬기 — Enter로도 보낼 수 있어요 "
                               "(Shift+Enter는 줄바꿈)")
        self.go_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.go_btn.setStyleSheet(
            f"QPushButton{{background:{theme.PRIMARY};color:white;border:none;"
            f"border-radius:19px;font-size:16px;font-weight:bold}}"
            f"QPushButton:hover{{background:{theme.PRIMARY_DARK}}}"
            f"QPushButton:pressed{{background:{theme.PRIMARY_PRESSED}}}"
            f"QPushButton:disabled{{background:{theme.DISABLED_BG}}}")
        self.go_btn.clicked.connect(self._go)
        bar.addWidget(self.go_btn)
        pl.addLayout(bar)
        col.addWidget(pill)

        # ── 로딩: 얇은 진행선 + 작은 안내 (기본 숨김) ──
        col.addSpacing(10)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)          # 불확정 진행 애니메이션
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(3)
        self.progress.setStyleSheet(
            f"QProgressBar{{background:{theme.PRIMARY_LIGHT};border:none;"
            f"border-radius:1px}}"
            f"QProgressBar::chunk{{background:{theme.PRIMARY};"
            f"border-radius:1px}}")
        self.progress.setVisible(False)
        col.addWidget(self.progress)
        self.loading_label = QLabel("다듬고 있어요…")
        self.loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.loading_label.setStyleSheet(
            f"color:{theme.SUBTLE};font-size:{theme.FONT_XS}px;"
            f"background:transparent;padding-top:6px")
        self.loading_label.setVisible(False)
        col.addWidget(self.loading_label)

        # ── 상태 (오류·복사 알림) ──
        self.status = QLabel("")
        self.status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status.setWordWrap(True)
        self.status.setStyleSheet(
            f"color:{theme.SUBTLE};font-size:{theme.FONT_XS}px;"
            f"background:transparent;padding-top:6px")
        col.addWidget(self.status)

        # ── 결과 카드 (기본 숨김 → 완료 시 페이드 등장) ──
        col.addSpacing(8)
        self.result_card = QFrame()
        self.result_card.setObjectName("rcard")
        self.result_card.setStyleSheet(
            f"#rcard{{background:{theme.CARD};border:1px solid {theme.BORDER};"
            f"border-radius:{theme.RADIUS_LG}px}}")
        rc = QVBoxLayout(self.result_card)
        rc.setContentsMargins(20, 12, 16, 14)
        rc.setSpacing(4)
        rhead = QHBoxLayout()
        rlab = QLabel("다듬은 글")
        rlab.setStyleSheet(
            f"font-size:{theme.FONT_XS}px;font-weight:bold;"
            f"color:{theme.SUBTLE};background:transparent")
        rhead.addWidget(rlab)
        rhead.addStretch()
        copy_btn = QPushButton("복사")
        copy_btn.setStyleSheet(
            theme.TEXT_BTN + f"QPushButton{{font-size:{theme.FONT_XS}px}}")
        copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        copy_btn.clicked.connect(self._copy)
        rhead.addWidget(copy_btn)
        rc.addLayout(rhead)
        self.result_edit = QTextEdit()
        self.result_edit.setStyleSheet(
            f"QTextEdit{{background:transparent;border:none;padding:0;"
            f"font-size:{theme.FONT_MD}px;line-height:160%;color:{theme.TEXT}}}")
        rc.addWidget(self.result_edit)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea{background:transparent}")
        scroll.setWidget(self.result_card)
        self.result_card.setVisible(False)
        col.addWidget(scroll, stretch=1)
        col.addSpacing(8)

        self.input_edit.setFocus()

    def _sync_count(self) -> None:
        n = len(self.input_edit.toPlainText())
        self.in_count.setText(f"{n}자" if n else "")

    # ── 보정 ────────────────────────────────────────────────
    def _go(self) -> None:
        text = self.input_edit.toPlainText().strip()
        if not text:
            self.status.setText("다듬을 글을 먼저 붙여넣어 주세요.")
            return
        self._set_loading(True)
        self.status.setText("")
        self._worker = _Worker(text, self.config, self)
        self._worker.done.connect(self._on_done)
        self._worker.failed.connect(self._on_fail)
        self._worker.start()

    def _set_loading(self, on: bool) -> None:
        self.go_btn.setEnabled(not on)
        self.input_edit.setReadOnly(on)
        self.progress.setVisible(on)
        self.loading_label.setVisible(on)

    def _on_done(self, result: str) -> None:
        self._set_loading(False)
        self.result_edit.setPlainText(result)
        self.status.setText("")
        motion.fade_in_widget(self.result_card, ms=220)   # 페이드 등장

    def _on_fail(self, msg: str) -> None:
        self._set_loading(False)
        self.status.setText(f"실패: {msg}")

    def _copy(self) -> None:
        QApplication.clipboard().setText(self.result_edit.toPlainText())
        self.status.setText("복사했습니다 — 쿨메신저나 문서에 붙여넣으세요.")
