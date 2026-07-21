# -*- coding: utf-8 -*-
"""안내문구 보정 창 — 붙여넣은 글을 AI로 다듬는다 (공개용 글 전용).

쪽지 자동 불러오기 없음. 입력창에 직접 붙여넣은 텍스트만 전송된다.
디자인(2026-07-21): Gemini 홈 스타일 — 가운데 인사 문구 + 둥근 입력창.
보정/Enter → 로딩 진행바 → 다듬은 글이 아래에서 페이드로 등장.
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
    """Enter=보내기, Shift+Enter=줄바꿈 (Gemini 입력창처럼)."""
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
        self.resize(760, 640)
        self.setStyleSheet(theme.BASE_QSS + f"QDialog{{background:{theme.BG}}}")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 24, 28, 20)
        outer.setSpacing(0)

        # ── 인사 문구 (가운데) ──
        greet = QLabel("어떤 글을 다듬어 드릴까요?")
        greet.setAlignment(Qt.AlignmentFlag.AlignCenter)
        greet.setStyleSheet(
            f"font-size:24px;font-weight:bold;color:{theme.TEXT};"
            f"background:transparent")
        outer.addWidget(greet)
        sub_row = QHBoxLayout()
        sub_row.addStretch()
        sub = QLabel("가정통신문 같은 공개용 글을 붙여넣으면 정중하게 다듬어 드려요")
        sub.setStyleSheet(
            f"color:{theme.SUBTLE};font-size:{theme.FONT_SM}px;"
            f"background:transparent")
        sub_row.addWidget(sub)
        info = QLabel("?")
        info.setFixedSize(18, 18)
        info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info.setToolTip(_TIP)
        info.setCursor(Qt.CursorShape.WhatsThisCursor)
        info.setStyleSheet(
            f"background:{theme.PRIMARY_LIGHT};color:{theme.PRIMARY_DARK};"
            f"border-radius:9px;font-size:{theme.FONT_XS}px;font-weight:bold")
        sub_row.addWidget(info)
        sub_row.addStretch()
        outer.addSpacing(6)
        outer.addLayout(sub_row)
        outer.addSpacing(18)

        # ── 둥근 입력창 (가운데, 최대폭 제한) ──
        pill_row = QHBoxLayout()
        pill_row.addStretch()
        pill = QFrame()
        pill.setObjectName("pill")
        pill.setMaximumWidth(660)
        pill.setStyleSheet(
            f"#pill{{background:{theme.CARD};border:1px solid {theme.BORDER};"
            f"border-radius:24px}}")
        pill.setGraphicsEffect(theme.make_shadow(self, 1))
        pl = QVBoxLayout(pill)
        pl.setContentsMargins(18, 14, 14, 10)
        pl.setSpacing(6)
        self.input_edit = _PromptEdit()
        self.input_edit.setPlaceholderText("다듬고 싶은 글을 붙여넣거나 써보세요")
        self.input_edit.setToolTip(_TIP)
        self.input_edit.setStyleSheet(
            f"QTextEdit{{background:transparent;border:none;"
            f"font-size:{theme.FONT_MD}px;line-height:150%;color:{theme.TEXT}}}")
        self.input_edit.setMinimumHeight(58)
        self.input_edit.setMaximumHeight(150)
        self.input_edit.submitted.connect(self._go)
        self.input_edit.textChanged.connect(self._sync_count)
        pl.addWidget(self.input_edit)
        # 입력창 하단 줄: 공급자 칩 + 글자 수 + 보내기 버튼
        bar = QHBoxLayout()
        bar.setSpacing(8)
        prov = ("OpenRouter" if self.config.get("proof_provider") == "openrouter"
                else "Gemini")
        prov_chip = QLabel(prov)
        prov_chip.setStyleSheet(
            f"background:{theme.PRIMARY_LIGHT};color:{theme.PRIMARY_DARK};"
            f"border-radius:{theme.RADIUS_SM}px;padding:2px 9px;"
            f"font-size:{theme.FONT_XS}px;font-weight:bold")
        bar.addWidget(prov_chip)
        bar.addStretch()
        self.in_count = QLabel("")
        self.in_count.setStyleSheet(
            f"color:{theme.SUBTLE};font-size:{theme.FONT_XS}px")
        bar.addWidget(self.in_count)
        self.go_btn = QPushButton("✨ 다듬기")
        self.go_btn.setStyleSheet(
            theme.PRIMARY_BTN
            + f"QPushButton{{font-size:{theme.FONT_MD}px;padding:8px 18px;"
              f"border-radius:18px}}")
        self.go_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.go_btn.setToolTip("Enter로도 보낼 수 있어요 (Shift+Enter는 줄바꿈)")
        self.go_btn.clicked.connect(self._go)
        bar.addWidget(self.go_btn)
        pl.addLayout(bar)
        pill_row.addWidget(pill, stretch=1)
        pill_row.addStretch()
        outer.addLayout(pill_row)

        # ── 로딩 진행바 (기본 숨김) ──
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)          # 불확정(진행 중) 애니메이션
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(4)
        self.progress.setStyleSheet(
            f"QProgressBar{{background:{theme.PRIMARY_LIGHT};border:none;"
            f"border-radius:2px;margin:12px 60px 0 60px}}"
            f"QProgressBar::chunk{{background:{theme.PRIMARY};border-radius:2px}}")
        self.progress.setVisible(False)
        outer.addWidget(self.progress)
        self.loading_label = QLabel("✨ 글을 다듬고 있어요…")
        self.loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.loading_label.setStyleSheet(
            f"color:{theme.PRIMARY_DARK};font-size:{theme.FONT_SM}px;"
            f"font-weight:bold;background:transparent;padding-top:6px")
        self.loading_label.setVisible(False)
        outer.addWidget(self.loading_label)

        # ── 결과 카드 (기본 숨김, 완료 시 페이드 등장) ──
        self.result_card = QFrame()
        self.result_card.setObjectName("rcard")
        self.result_card.setStyleSheet(
            f"#rcard{{background:{theme.CARD};border:1px solid {theme.BORDER};"
            f"border-radius:{theme.RADIUS_LG}px}}")
        rc = QVBoxLayout(self.result_card)
        rc.setContentsMargins(16, 12, 16, 14)
        rc.setSpacing(8)
        rhead = QHBoxLayout()
        rlab = QLabel("✨ 다듬은 글")
        rlab.setStyleSheet(
            f"font-size:{theme.FONT_MD}px;font-weight:bold;"
            f"color:{theme.PRIMARY_DARK};background:transparent")
        rhead.addWidget(rlab)
        rhead.addStretch()
        copy_btn = QPushButton("📋 복사")
        copy_btn.setStyleSheet(theme.TEXT_BTN + f"QPushButton{{font-size:{theme.FONT_XS}px}}")
        copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        copy_btn.clicked.connect(self._copy)
        rhead.addWidget(copy_btn)
        rc.addLayout(rhead)
        self.result_edit = QTextEdit()
        self.result_edit.setReadOnly(False)   # 살짝 손볼 수 있게
        self.result_edit.setStyleSheet(
            f"QTextEdit{{background:{theme.CARD_TINT};border:1px solid "
            f"{theme.BORDER};border-radius:{theme.RADIUS_MD}px;padding:12px;"
            f"font-size:{theme.FONT_MD}px;line-height:150%}}")
        rc.addWidget(self.result_edit)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setWidget(self.result_card)
        self.result_card.setVisible(False)
        outer.addSpacing(4)
        outer.addWidget(scroll, stretch=1)

        # ── 하단: 상태 + 닫기 ──
        bottom = QHBoxLayout()
        self.status = QLabel("")
        self.status.setStyleSheet(
            f"color:{theme.SUBTLE};font-size:{theme.FONT_XS}px")
        bottom.addWidget(self.status)
        bottom.addStretch()
        close_btn = QPushButton("닫기")
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(self.accept)
        bottom.addWidget(close_btn)
        outer.addSpacing(8)
        outer.addLayout(bottom)

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
        self.go_btn.setText("다듬는 중…" if on else "✨ 다듬기")
        self.input_edit.setReadOnly(on)
        self.progress.setVisible(on)
        self.loading_label.setVisible(on)

    def _on_done(self, result: str) -> None:
        self._set_loading(False)
        self.result_edit.setPlainText(result)
        self.status.setText("완료 — 결과를 확인하고 📋 복사해 쓰세요.")
        motion.fade_in_widget(self.result_card, ms=220)   # 아래에서 페이드 등장

    def _on_fail(self, msg: str) -> None:
        self._set_loading(False)
        self.status.setText(f"실패: {msg}")

    def _copy(self) -> None:
        QApplication.clipboard().setText(self.result_edit.toPlainText())
        self.status.setText("복사했습니다. 쿨메신저나 문서에 붙여넣으세요.")
