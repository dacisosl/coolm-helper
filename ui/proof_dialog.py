# -*- coding: utf-8 -*-
"""안내문구 보정 창 — 붙여넣은 글을 AI로 다듬는다 (공개용 글 전용).

쪽지 자동 불러오기 없음. 입력창에 직접 붙여넣은 텍스트만 전송된다.
디자인: 원문 | 다듬은 글 2단 비교 뷰 — 글자 수 표시, 카드형 편집기
(2026-07-21 리마스터).
"""
from __future__ import annotations

import threading

from PyQt6.QtCore import Qt, QObject, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication, QDialog, QHBoxLayout, QLabel, QPushButton, QTextEdit,
    QVBoxLayout, QWidget,
)

from ui import motion, theme

_TIP = ("공개용 글 전용 — 붙여넣은 내용은 AI 서버(Gemini/OpenRouter)로 "
        "전송돼요.\n개인정보가 들어간 글은 넣지 마세요. "
        "쪽지는 자동으로 불러오지 않아요.")

_EDITOR_QSS = (
    f"QTextEdit{{background:{theme.CARD};border:1.5px solid {theme.BORDER};"
    f"border-radius:12px;padding:12px;font-size:13px;line-height:150%}}"
    f"QTextEdit:focus{{border-color:{theme.PRIMARY}}}")


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
        self.resize(880, 560)
        self.setStyleSheet(theme.BASE_QSS
                           + f"QDialog{{background:{theme.BG}}}")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 12)
        lay.setSpacing(10)

        # 헤더: 큰 제목 + ? 툴팁
        head = QHBoxLayout()
        title = QLabel("✨ 안내문구 보정")
        title.setStyleSheet(
            f"font-size:18px;font-weight:bold;color:{theme.PRIMARY_DARK}")
        head.addWidget(title)
        info = QLabel("?")
        info.setFixedSize(18, 18)
        info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info.setToolTip(_TIP)
        info.setStyleSheet(
            f"background:{theme.PRIMARY_LIGHT};color:{theme.PRIMARY_DARK};"
            f"border-radius:9px;font-size:12px;font-weight:bold")
        head.addWidget(info)
        head.addStretch()
        self.go_btn = QPushButton("✨ 다듬기")
        self.go_btn.setStyleSheet(
            theme.PRIMARY_BTN + "QPushButton{font-size:14px;padding:9px 22px}")
        self.go_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.go_btn.clicked.connect(self._go)
        head.addWidget(self.go_btn)
        lay.addLayout(head)

        # 본문: 원문 | 다듬은 글 — 나란히 비교
        panes = QHBoxLayout()
        panes.setSpacing(12)

        left = QVBoxLayout()
        left.setSpacing(4)
        lh = QHBoxLayout()
        lab = QLabel("원문")
        lab.setStyleSheet(
            f"font-size:12px;font-weight:bold;color:{theme.SUBTLE}")
        lh.addWidget(lab)
        lh.addStretch()
        self.in_count = QLabel("0자")
        self.in_count.setStyleSheet(f"font-size:11px;color:{theme.SUBTLE}")
        lh.addWidget(self.in_count)
        left.addLayout(lh)
        self.input_edit = QTextEdit()
        self.input_edit.setPlaceholderText(
            "다듬고 싶은 글을 붙여넣거나 바로 써보세요.\n\n"
            "예) 내일 체험학습 관련해서 안내드립니다…")
        self.input_edit.setStyleSheet(_EDITOR_QSS)
        self.input_edit.setToolTip(_TIP)
        self.input_edit.textChanged.connect(
            lambda: self.in_count.setText(
                f"{len(self.input_edit.toPlainText())}자"))
        left.addWidget(self.input_edit, stretch=1)
        lw = QWidget()
        lw.setLayout(left)
        panes.addWidget(lw, stretch=1)

        right = QVBoxLayout()
        right.setSpacing(4)
        rh = QHBoxLayout()
        rlab = QLabel("다듬은 글")
        rlab.setStyleSheet(
            f"font-size:12px;font-weight:bold;color:{theme.PRIMARY_DARK}")
        rh.addWidget(rlab)
        rh.addStretch()
        copy_btn = QPushButton("📋 복사")
        copy_btn.setStyleSheet(theme.TEXT_BTN + "QPushButton{font-size:11px}")
        copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        copy_btn.clicked.connect(self._copy)
        rh.addWidget(copy_btn)
        right.addLayout(rh)
        self.result_edit = QTextEdit()
        self.result_edit.setPlaceholderText(
            "✨ 다듬기를 누르면 여기에 결과가 나타나요.")
        self.result_edit.setStyleSheet(
            _EDITOR_QSS.replace(theme.CARD, theme.CARD_TINT, 1))
        right.addWidget(self.result_edit, stretch=1)
        rw = QWidget()
        rw.setLayout(right)
        panes.addWidget(rw, stretch=1)
        lay.addLayout(panes, stretch=1)

        # 하단: 상태 + 닫기
        bottom = QHBoxLayout()
        self.status = QLabel("")
        self.status.setStyleSheet(f"color:{theme.SUBTLE};font-size:11px")
        bottom.addWidget(self.status)
        bottom.addStretch()
        close_btn = QPushButton("닫기")
        close_btn.clicked.connect(self.accept)
        bottom.addWidget(close_btn)
        lay.addLayout(bottom)

    def _go(self) -> None:
        text = self.input_edit.toPlainText().strip()
        if not text:
            self.status.setText("다듬을 글을 먼저 붙여넣어 주세요.")
            return
        self.go_btn.setEnabled(False)
        self.go_btn.setText("다듬는 중…")
        self.status.setText("AI가 글을 다듬고 있어요…")
        self._worker = _Worker(text, self.config, self)
        self._worker.done.connect(self._on_done)
        self._worker.failed.connect(self._on_fail)
        self._worker.start()

    def _on_done(self, result: str) -> None:
        self.result_edit.setPlainText(result)
        self.status.setText("완료 — 오른쪽 결과를 확인하고 📋 복사해 쓰세요.")
        self.go_btn.setEnabled(True)
        self.go_btn.setText("✨ 다듬기")

    def _on_fail(self, msg: str) -> None:
        self.status.setText(f"실패: {msg}")
        self.go_btn.setEnabled(True)
        self.go_btn.setText("✨ 다듬기")

    def _copy(self) -> None:
        QApplication.clipboard().setText(self.result_edit.toPlainText())
        self.status.setText("복사했습니다. 쿨메신저나 문서에 붙여넣으세요.")
