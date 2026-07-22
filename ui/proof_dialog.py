# -*- coding: utf-8 -*-
"""안내문구 보정 창 — 붙여넣은 글을 AI로 다듬는다 (공개용 글 전용).

쪽지 자동 불러오기 없음. 입력창에 직접 붙여넣은 텍스트만 전송된다.
디자인(2026-07-22 v1.3, 프리미엄 신뢰 무드): 2화면 전환 구조 —
① 입력: 단색 네이비 헤드라인 + 무테 입력 카드 + 네이비 CTA (톤은 격식·명확 고정)
② 결과: ← 다시 작성하기 / 원본 요약 / 제안 카드(타이핑 효과) / 🔄 다른 버전
복사하면 토스트. 창을 늘려도 내용은 가운데 열(최대 560px)에 머문다.
"""
from __future__ import annotations

import threading

from PyQt6.QtCore import Qt, QObject, QTimer, pyqtSignal
from PyQt6.QtGui import QTextCursor
from PyQt6.QtWidgets import (
    QDialog, QFrame, QHBoxLayout, QLabel,
    QProgressBar, QPushButton, QScrollArea, QStackedWidget, QTextEdit,
    QVBoxLayout, QWidget,
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

    def __init__(self, text: str, config: dict, tone: str, parent=None):
        super().__init__(parent)
        self.text, self.config, self.tone = text, config, tone

    def start(self) -> None:
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self) -> None:
        import proofread
        try:
            self.done.emit(
                proofread.proofread(self.text, self.config, self.tone))
        except Exception as e:
            self.failed.emit(str(e))


class ProofDialog(motion.FadeInMixin, QDialog):
    def __init__(self, config: dict, parent=None):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("안내문구 보정")
        self.resize(640, 720)
        self.setMinimumSize(560, 600)
        self.setMaximumSize(860, 980)     # 갑자기 전체 폭으로 커지는 것 방지
        self.setStyleSheet(theme.BASE_QSS + f"QDialog{{background:{theme.BG}}}")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 8, 24, 16)
        center = QHBoxLayout()
        col_w = QWidget()
        col_w.setMaximumWidth(560)        # 폰 화면 같은 좁은 열
        col_w.setStyleSheet("background:transparent")
        self.stack = QStackedWidget(col_w)
        col = QVBoxLayout(col_w)
        col.setContentsMargins(0, 0, 0, 0)
        col.addWidget(self.stack)
        center.addStretch()
        center.addWidget(col_w, stretch=1)
        center.addStretch()
        outer.addLayout(center, stretch=1)

        self.stack.addWidget(self._build_input_page())    # 0
        self.stack.addWidget(self._build_result_page())   # 1
        self.stack.setCurrentIndex(0)
        self.input_edit.setFocus()

    # ── ① 입력 화면 ─────────────────────────────────────────
    def _build_input_page(self) -> QWidget:
        page = QWidget()
        page.setStyleSheet("background:transparent")
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addSpacing(28)

        # 메인 문구 하나로 간결하게 (2026-07-22 사용자 결정)
        sub_row = QHBoxLayout()
        sub = QLabel("작성하신 글을 붙여넣으면\n격식 있고 명확하게 다듬어 드려요")
        sub.setWordWrap(True)
        sub.setStyleSheet(
            f"font-size:{theme.FONT_XXL}px;font-weight:bold;"
            f"color:{theme.TEXT};background:transparent")
        sub_row.addWidget(sub)
        from ui.help_dot import HelpDot
        sub_row.addWidget(HelpDot(_TIP), alignment=Qt.AlignmentFlag.AlignTop)
        sub_row.addStretch()
        lay.addLayout(sub_row)
        lay.addSpacing(20)

        # 유리 카드 입력
        card = QFrame()
        card.setObjectName("incard")
        card.setStyleSheet(
            f"#incard{{background:{theme.CARD};border:none;"
            f"border-radius:{theme.RADIUS_XL}px}}")
        card.setGraphicsEffect(theme.make_shadow(self, 1))
        cl = QVBoxLayout(card)
        cl.setContentsMargins(20, 14, 14, 10)
        cl.setSpacing(4)
        tag = QLabel("원본 글")
        tag.setStyleSheet(
            f"color:{theme.SUBTLE};font-size:10px;font-weight:bold;"
            f"letter-spacing:2px;background:transparent")
        cl.addWidget(tag)
        self.input_edit = _PromptEdit()
        self.input_edit.setPlaceholderText(
            "안내할 내용을 간략하게 적어주세요.")
        self.input_edit.setToolTip(_TIP)
        self.input_edit.setStyleSheet(
            f"QTextEdit{{background:transparent;border:none;padding:0;"
            f"font-size:{theme.FONT_LG}px;line-height:150%;color:{theme.TEXT}}}")
        self.input_edit.setMinimumHeight(110)
        self.input_edit.setMaximumHeight(200)
        self.input_edit.submitted.connect(self._go)
        cl.addWidget(self.input_edit)
        foot = QHBoxLayout()
        prov = ("OpenRouter"
                if self.config.get("proof_provider") == "openrouter"
                else "Gemini 3.5 Flash")
        model_label = QLabel(prov)
        model_label.setStyleSheet(
            f"color:{theme.SUBTLE};font-size:10px;background:transparent")
        foot.addWidget(model_label)
        foot.addStretch()
        clear_btn = QPushButton("✕")
        clear_btn.setFixedSize(26, 26)
        clear_btn.setToolTip("내용 지우기")
        clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        clear_btn.setStyleSheet(
            f"QPushButton{{background:transparent;border:none;"
            f"color:{theme.SUBTLE};border-radius:13px;font-size:12px}}"
            f"QPushButton:hover{{background:{theme.BG};color:{theme.TEXT}}}"
            f"QPushButton:pressed{{background:{theme.LIGHT_PRESSED}}}")
        clear_btn.clicked.connect(
            lambda: (self.input_edit.clear(), self.input_edit.setFocus()))
        foot.addWidget(clear_btn)
        cl.addLayout(foot)
        lay.addWidget(card)
        lay.addSpacing(18)

        lay.addSpacing(22)

        # CTA: 네이비 풀폭 버튼 (앱 주요 버튼과 통일)
        self.go_btn = QPushButton("글 다듬기")
        self.go_btn.setFixedHeight(52)
        self.go_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.go_btn.setToolTip("Enter로도 보낼 수 있어요 (Shift+Enter는 줄바꿈)")
        self.go_btn.setStyleSheet(
            f"QPushButton{{background:{theme.PRIMARY};color:white;border:none;"
            f"border-radius:{theme.RADIUS_LG}px;font-size:{theme.FONT_LG}px;"
            f"font-weight:bold}}"
            f"QPushButton:hover{{background:{theme.PRIMARY_DARK}}}"
            f"QPushButton:pressed{{background:{theme.PRIMARY_PRESSED};padding-top:2px}}"
            f"QPushButton:disabled{{background:{theme.DISABLED_BG}}}")
        self.go_btn.clicked.connect(self._go)
        lay.addWidget(self.go_btn)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(3)
        self.progress.setStyleSheet(
            f"QProgressBar{{background:{theme.PRIMARY_LIGHT};border:none;"
            f"border-radius:1px;margin-top:10px}}"
            f"QProgressBar::chunk{{background:{theme.PRIMARY};"
            f"border-radius:1px}}")
        self.progress.setVisible(False)
        lay.addWidget(self.progress)

        self.status = QLabel("")
        self.status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status.setWordWrap(True)
        self.status.setStyleSheet(
            f"color:{theme.DANGER};font-size:{theme.FONT_XS}px;"
            f"background:transparent;padding-top:8px")
        lay.addWidget(self.status)
        lay.addStretch()
        return page

    # ── ② 결과 화면 ─────────────────────────────────────────
    def _build_result_page(self) -> QWidget:
        page = QWidget()
        page.setStyleSheet("background:transparent")
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addSpacing(16)

        back = QPushButton("←  다시 작성하기")
        back.setStyleSheet(
            f"QPushButton{{background:transparent;border:none;"
            f"color:{theme.SUBTLE};font-size:{theme.FONT_SM}px;"
            f"font-weight:bold;padding:4px 0;text-align:left}}"
            f"QPushButton:hover{{color:{theme.TEXT}}}")
        back.setCursor(Qt.CursorShape.PointingHandCursor)
        back.clicked.connect(self._back_to_input)
        lay.addWidget(back, alignment=Qt.AlignmentFlag.AlignLeft)
        lay.addSpacing(12)

        # 원본 요약 카드
        orig = QFrame()
        orig.setStyleSheet(
            f"QFrame{{background:{theme.CARD_TINT};border:none;"
            f"border-radius:{theme.RADIUS_LG}px}}")
        ol = QVBoxLayout(orig)
        ol.setContentsMargins(16, 10, 16, 12)
        ol.setSpacing(4)
        otag = QLabel("● 원본")
        otag.setStyleSheet(
            f"color:{theme.SUBTLE};font-size:10px;font-weight:bold;"
            f"background:transparent;border:none")
        ol.addWidget(otag)
        self.orig_preview = QLabel()
        self.orig_preview.setWordWrap(True)
        self.orig_preview.setStyleSheet(
            f"color:{theme.SUBTLE};font-size:{theme.FONT_SM}px;"
            f"background:transparent;border:none")
        ol.addWidget(self.orig_preview)
        lay.addWidget(orig)
        lay.addSpacing(12)

        # 제안 카드 (타이핑 효과)
        self.result_card = QFrame()
        self.result_card.setObjectName("rcard")
        self.result_card.setStyleSheet(
            f"#rcard{{background:{theme.CARD};border:none;"
            f"border-radius:{theme.RADIUS_XL}px}}")
        self.result_card.setGraphicsEffect(theme.make_shadow(self, 1))
        rc = QVBoxLayout(self.result_card)
        rc.setContentsMargins(20, 14, 16, 16)
        rc.setSpacing(6)
        rhead = QHBoxLayout()
        self.tone_label = QLabel("✨ 다듬은 글")
        self.tone_label.setStyleSheet(
            f"color:{theme.PRIMARY_DARK};font-size:{theme.FONT_SM}px;"
            f"font-weight:bold;background:transparent")
        rhead.addWidget(self.tone_label)
        rhead.addStretch()
        # 복사 = 이 화면의 주인공 버튼 — 아이콘 + 채운 네이비로 강조
        from PyQt6.QtCore import QSize
        from ui.icons import icon
        copy_btn = QPushButton(" 복사하기")
        copy_btn.setIcon(icon("copy", 15))
        copy_btn.setIconSize(QSize(15, 15))
        copy_btn.setStyleSheet(
            f"QPushButton{{background:{theme.PRIMARY};color:white;border:none;"
            f"border-radius:{theme.RADIUS_MD}px;padding:7px 16px;"
            f"font-size:{theme.FONT_SM}px;font-weight:bold}}"
            f"QPushButton:hover{{background:{theme.PRIMARY_DARK}}}"
            f"QPushButton:pressed{{background:{theme.PRIMARY_PRESSED};"
            f"padding:8px 16px 6px 16px}}")
        copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        copy_btn.setToolTip("다듬은 글을 클립보드로 복사")
        copy_btn.clicked.connect(self._copy)
        rhead.addWidget(copy_btn)
        rc.addLayout(rhead)
        self.result_edit = QTextEdit()
        self.result_edit.setStyleSheet(
            f"QTextEdit{{background:transparent;border:none;padding:0;"
            f"font-size:{theme.FONT_LG}px;line-height:160%;color:{theme.TEXT}}}")
        self.result_edit.setMinimumHeight(150)
        rc.addWidget(self.result_edit, stretch=1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea{background:transparent}")
        scroll.setWidget(self.result_card)
        lay.addWidget(scroll, stretch=1)
        lay.addSpacing(10)

        # 🔄 다른 버전
        again = QPushButton("🔄  다른 버전 만들기")
        again.setStyleSheet(
            theme.TEXT_BTN + f"QPushButton{{font-size:{theme.FONT_SM}px}}")
        again.setCursor(Qt.CursorShape.PointingHandCursor)
        again.clicked.connect(self._go)
        lay.addWidget(again, alignment=Qt.AlignmentFlag.AlignCenter)
        lay.addSpacing(4)
        return page

    # ── 동작 ────────────────────────────────────────────────
    def _ask_api_key(self) -> bool:
        """API 키가 없을 때 그 자리에서 받는 모달. True=저장됨."""
        from PyQt6.QtWidgets import (
            QDialog, QHBoxLayout as _H, QLineEdit, QRadioButton,
            QVBoxLayout as _V)

        dlg = QDialog(self)
        dlg.setWindowTitle("AI 열쇠(API 키) 넣기")
        dlg.setStyleSheet(theme.BASE_QSS + f"QDialog{{background:{theme.BG}}}")
        dlg.setFixedWidth(420)
        lay = _V(dlg)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(10)
        head = QLabel("무료 AI 키가 필요해요 (최초 1회)")
        head.setStyleSheet(theme.DIALOG_HEADER)
        lay.addWidget(head)
        info = QLabel("글다듬기는 AI 서비스 키로 동작해요.\n"
                      "아래 버튼으로 무료 키를 발급받아 붙여넣어 주세요.")
        info.setWordWrap(True)
        info.setStyleSheet(f"color:{theme.SUBTLE};font-size:{theme.FONT_SM}px")
        lay.addWidget(info)

        prow = _H()
        r_gem = QRadioButton("Gemini 키")
        r_or = QRadioButton("OpenRouter 키")
        (r_or if self.config.get("proof_provider") == "openrouter"
         else r_gem).setChecked(True)
        prow.addWidget(r_gem)
        prow.addWidget(r_or)
        prow.addStretch()
        lay.addLayout(prow)

        key_edit = QLineEdit()
        key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        key_edit.setPlaceholderText("AIza… 또는 sk-or-… 키 붙여넣기")
        lay.addWidget(key_edit)

        link = QPushButton("무료 키 발급 페이지 열기")
        link.setStyleSheet(theme.TEXT_BTN)
        link.clicked.connect(lambda: __import__("webbrowser").open(
            "https://openrouter.ai/keys" if r_or.isChecked()
            else "https://aistudio.google.com/apikey"))
        lay.addWidget(link, alignment=Qt.AlignmentFlag.AlignLeft)

        btns = _H()
        btns.addStretch()
        cancel = QPushButton("나중에")
        cancel.setStyleSheet(theme.TEXT_BTN)
        cancel.clicked.connect(dlg.reject)
        btns.addWidget(cancel)
        ok = QPushButton("저장")
        ok.setStyleSheet(theme.PRIMARY_BTN)
        ok.clicked.connect(dlg.accept)
        btns.addWidget(ok)
        lay.addLayout(btns)
        key_edit.setFocus()

        while True:
            if dlg.exec() != QDialog.DialogCode.Accepted:
                return False
            key = key_edit.text().strip()
            if key:
                break
            info.setText("키가 비어 있어요 — 발급받은 키를 붙여넣어 주세요.")
        self.config["proof_provider"] = ("openrouter" if r_or.isChecked()
                                         else "gemini")
        self.config["proof_api_key"] = key
        parent = self.parent()
        base_dir = getattr(parent, "base_dir", None)
        if base_dir:                       # 설정 파일에도 저장 (재시작 유지)
            from parser import pipeline
            pipeline.save_config(base_dir, self.config)
        return True

    def _go(self) -> None:
        text = self.input_edit.toPlainText().strip()
        if not text:
            self.stack.setCurrentIndex(0)
            self.status.setText("다듬을 글을 먼저 입력해 주세요.")
            return
        if not str(self.config.get("proof_api_key", "")).strip():
            if not self._ask_api_key():    # 그 자리에서 키 입력 (2026-07-22)
                self.status.setText("AI 키를 넣으면 바로 쓸 수 있어요.")
                return
        self._set_loading(True)
        self.status.setText("")
        self._worker = _Worker(text, self.config, "formal", self)
        self._worker.done.connect(self._on_done)
        self._worker.failed.connect(self._on_fail)
        self._worker.start()

    def _set_loading(self, on: bool) -> None:
        self.go_btn.setEnabled(not on)
        self.go_btn.setText("⏳ 다듬는 중…" if on else "글 다듬기  ✨")
        self.input_edit.setReadOnly(on)
        self.progress.setVisible(on)

    def _on_done(self, result: str) -> None:
        self._set_loading(False)
        # 원본 요약 (3줄 정도로 컷)
        src = self.input_edit.toPlainText().strip()
        self.orig_preview.setText(src[:120] + ("…" if len(src) > 120 else ""))
        self.stack.setCurrentIndex(1)
        motion.fade_in_widget(self.stack.currentWidget(), ms=220)
        self._type_result(result)

    def _on_fail(self, msg: str) -> None:
        self._set_loading(False)
        self.stack.setCurrentIndex(0)
        self.status.setText(f"실패: {msg}")

    def _back_to_input(self) -> None:
        self._stop_typing()
        self.stack.setCurrentIndex(0)
        motion.fade_in_widget(self.stack.currentWidget(), ms=150)
        self.input_edit.setFocus()

    # ── 타이핑 효과 ─────────────────────────────────────────
    def _type_result(self, text: str) -> None:
        self._stop_typing()
        if not motion.is_enabled() or len(text) > 2000:
            self.result_edit.setPlainText(text)
            return
        self._type_text = text
        self._type_i = 0
        self.result_edit.clear()
        # 길이에 맞춰 속도 조절 — 전체 3초 안에 끝나게 (emil: 빠르게)
        chars_per_tick = max(1, len(text) // 100)
        self._type_step_n = chars_per_tick
        self._type_timer = QTimer(self)
        self._type_timer.setInterval(28)
        self._type_timer.timeout.connect(self._type_step)
        self._type_timer.start()

    def _type_step(self) -> None:
        self._type_i += self._type_step_n
        self.result_edit.setPlainText(self._type_text[:self._type_i])
        self.result_edit.moveCursor(QTextCursor.MoveOperation.End)
        if self._type_i >= len(self._type_text):
            self._stop_typing()
            self.result_edit.setPlainText(self._type_text)

    def _stop_typing(self) -> None:
        t = getattr(self, "_type_timer", None)
        if t is not None:
            t.stop()
            self._type_timer = None

    # ── 복사 ────────────────────────────────────────────────
    def _copy(self) -> None:
        from PyQt6.QtWidgets import QApplication
        self._stop_typing()
        if getattr(self, "_type_text", None) and \
                self.result_edit.toPlainText() != self._type_text:
            self.result_edit.setPlainText(self._type_text)   # 타이핑 중 복사 대비
        QApplication.clipboard().setText(self.result_edit.toPlainText())
        from ui.toast import show_toast
        show_toast(self, "복사되었습니다! ✨", msec=2500)
