# -*- coding: utf-8 -*-
"""안내문구 보정 창 — 붙여넣은 글을 AI로 다듬는다 (공개용 글 전용).

쪽지 자동 불러오기 없음. 입력창에 직접 붙여넣은 텍스트만 전송된다.
"""
from __future__ import annotations

import threading

from PyQt6.QtCore import Qt, QObject, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication, QDialog, QHBoxLayout, QLabel, QPushButton, QTextEdit,
    QVBoxLayout,
)

from ui import theme


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


class ProofDialog(QDialog):
    def __init__(self, config: dict, parent=None):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("안내문구 보정 — 공개용 글 전용")
        self.resize(620, 560)
        self.setStyleSheet(theme.BASE_QSS)
        lay = QVBoxLayout(self)

        # 긴 주의 문단 대신 ℹ 툴팁으로 간략히 (2026-07-21 사용자 결정)
        _tip = ("공개용 글 전용 — 붙여넣은 내용은 구글(Gemini) 서버로 "
                "전송돼요.\n개인정보가 들어간 글은 넣지 마세요. "
                "쪽지는 자동으로 불러오지 않아요.")
        info = QLabel("ℹ 공개할 글(가정통신문 등) 전용")
        info.setToolTip(_tip)
        info.setStyleSheet(f"color:{theme.SUBTLE};font-size:11px")
        lay.addWidget(info)

        self.input_edit = QTextEdit()
        self.input_edit.setPlaceholderText("다듬을 글을 여기에 붙여넣으세요…")
        self.input_edit.setToolTip(_tip)
        lay.addWidget(self.input_edit, stretch=1)

        mid = QHBoxLayout()
        self.status = QLabel("")
        self.status.setStyleSheet(f"color:{theme.SUBTLE};font-size:11px")
        mid.addWidget(self.status)
        mid.addStretch()
        self.go_btn = QPushButton("✨ 보정하기")
        self.go_btn.setStyleSheet(theme.PRIMARY_BTN)
        self.go_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.go_btn.clicked.connect(self._go)
        mid.addWidget(self.go_btn)
        lay.addLayout(mid)

        self.result_edit = QTextEdit()
        self.result_edit.setPlaceholderText("보정된 글이 여기에 표시됩니다.")
        lay.addWidget(self.result_edit, stretch=1)

        bottom = QHBoxLayout()
        bottom.addStretch()
        copy_btn = QPushButton("📋 결과 복사")
        copy_btn.clicked.connect(self._copy)
        bottom.addWidget(copy_btn)
        close_btn = QPushButton("닫기")
        close_btn.clicked.connect(self.accept)
        bottom.addWidget(close_btn)
        lay.addLayout(bottom)

    def _go(self) -> None:
        text = self.input_edit.toPlainText().strip()
        if not text:
            self.status.setText("보정할 글을 먼저 붙여넣어 주세요.")
            return
        self.go_btn.setEnabled(False)
        self.status.setText("보정 중…")
        self._worker = _Worker(text, self.config, self)
        self._worker.done.connect(self._on_done)
        self._worker.failed.connect(self._on_fail)
        self._worker.start()

    def _on_done(self, result: str) -> None:
        self.result_edit.setPlainText(result)
        self.status.setText("완료 — 결과를 확인하고 복사해 쓰세요.")
        self.go_btn.setEnabled(True)

    def _on_fail(self, msg: str) -> None:
        self.status.setText(f"실패: {msg}")
        self.go_btn.setEnabled(True)

    def _copy(self) -> None:
        QApplication.clipboard().setText(self.result_edit.toPlainText())
        self.status.setText("복사했습니다.")
