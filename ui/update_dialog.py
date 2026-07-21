# -*- coding: utf-8 -*-
"""업데이트 안내·진행 창 (2026-07-21 리디자인).

클로드(Claude) 앱 감성: 크림 배경, 세리프 헤드라인, 테라코타 CTA,
넉넉한 여백. 앱 본체(파랑·화이트)와 달리 '특별한 순간' 전용 무드다.

① 안내 화면: 헤드라인 + 버전 알약 + 변경사항 카드 + [나중에 / 지금 업데이트]
② 진행 화면: 다운로드 게이지(MB·%) → 끝나면 조용히 설치 실행 + 앱 종료
다운로드는 백그라운드 스레드 — 창은 살아 있고 게이지만 움직인다.
"""
from __future__ import annotations

import threading

from PyQt6.QtCore import Qt, QObject, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog, QFrame, QHBoxLayout, QLabel, QProgressBar, QPushButton,
    QScrollArea, QStackedWidget, QVBoxLayout, QWidget,
)

from ui import motion

# ── 클로드 무드 팔레트 (이 창 전용 — theme.py의 앱 팔레트와 별개) ──
CREAM = "#faf9f5"        # 배경
INK = "#1f1e1d"          # 본문 글자
INK_SOFT = "#6e6a63"     # 보조 글자
CARD = "#ffffff"
CARD_BORDER = "#e8e4db"
CORAL = "#c96442"        # CTA (테라코타)
CORAL_HOVER = "#b5573a"
CORAL_PRESSED = "#9e4b32"
PILL_BG = "#f0ede4"

_SERIF = "font-family:'Georgia','Malgun Gothic',serif"


class _Downloader(QObject):
    progress = pyqtSignal(int, int)   # (받은 바이트, 전체 바이트)
    done = pyqtSignal(str)            # 설치파일 경로
    failed = pyqtSignal(str)

    def __init__(self, url: str, parent=None):
        super().__init__(parent)
        self.url = url

    def start(self) -> None:
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self) -> None:
        import updater
        try:
            path = updater.download_installer(
                self.url, progress=self.progress.emit)
            self.done.emit(path)
        except Exception as e:
            self.failed.emit(str(e))


class UpdateDialog(motion.FadeInMixin, QDialog):
    """새 버전 안내 → (예를 누르면) 다운로드 진행 → 설치·재시작."""

    def __init__(self, info: dict, parent=None):
        super().__init__(parent)
        self.info = info
        self.setWindowTitle("업데이트")
        self.setFixedWidth(460)
        self.setStyleSheet(
            f"QDialog{{background:{CREAM}}}"
            f"QLabel{{color:{INK};background:transparent}}")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 24, 28, 24)
        self.stack = QStackedWidget()
        outer.addWidget(self.stack)
        self.stack.addWidget(self._offer_page())      # 0 안내
        self.stack.addWidget(self._progress_page())   # 1 진행

    # ── ① 안내 화면 ─────────────────────────────────────────
    def _offer_page(self) -> QWidget:
        from version import APP_VERSION
        page = QWidget()
        page.setStyleSheet("background:transparent")
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        head = QLabel("새로운 버전이<br>준비됐어요")
        head.setTextFormat(Qt.TextFormat.RichText)
        head.setStyleSheet(
            f"{_SERIF};font-size:26px;font-weight:bold;color:{INK}")
        lay.addWidget(head)
        lay.addSpacing(10)

        pill = QLabel(f"v{APP_VERSION}  →  v{self.info.get('version')}")
        pill.setStyleSheet(
            f"background:{PILL_BG};color:{INK};font-size:12px;"
            f"font-weight:bold;border-radius:11px;padding:4px 12px")
        prow = QHBoxLayout()
        prow.addWidget(pill)
        prow.addStretch()
        lay.addLayout(prow)
        lay.addSpacing(14)

        # 변경사항 카드 — 첫 줄은 소제목, 나머지는 그대로
        notes = str(self.info.get("notes", "")).strip()
        card = QFrame()
        card.setStyleSheet(
            f"QFrame{{background:{CARD};border:1px solid {CARD_BORDER};"
            f"border-radius:14px}}")
        cl = QVBoxLayout(card)
        cl.setContentsMargins(16, 12, 16, 12)
        cl.setSpacing(6)
        lines = [ln for ln in notes.splitlines() if ln.strip()]
        if lines:
            sub = QLabel(lines[0])
            sub.setWordWrap(True)
            sub.setStyleSheet(
                f"font-size:14px;font-weight:bold;color:{INK};border:none")
            cl.addWidget(sub)
        if len(lines) > 1:
            body = QLabel("\n".join(lines[1:]))
            body.setWordWrap(True)
            body.setStyleSheet(
                f"font-size:12px;color:{INK_SOFT};border:none;line-height:150%")
            cl.addWidget(body)
        if not lines:
            cl.addWidget(QLabel("자잘한 개선이 담겨 있어요."))
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea{background:transparent;border:none}")
        scroll.setWidget(card)
        scroll.setMaximumHeight(240)
        lay.addWidget(scroll)
        lay.addSpacing(18)

        btns = QHBoxLayout()
        later = QPushButton("나중에")
        later.setCursor(Qt.CursorShape.PointingHandCursor)
        later.setStyleSheet(
            f"QPushButton{{background:transparent;color:{INK_SOFT};"
            f"border:none;font-size:13px;padding:10px 14px}}"
            f"QPushButton:hover{{color:{INK}}}")
        later.clicked.connect(self.reject)
        btns.addWidget(later)
        btns.addStretch()
        go = QPushButton("지금 업데이트")
        go.setCursor(Qt.CursorShape.PointingHandCursor)
        go.setStyleSheet(
            f"QPushButton{{background:{CORAL};color:white;border:none;"
            f"border-radius:10px;padding:11px 22px;font-size:14px;"
            f"font-weight:bold}}"
            f"QPushButton:hover{{background:{CORAL_HOVER}}}"
            f"QPushButton:pressed{{background:{CORAL_PRESSED};"
            f"padding:12px 22px 10px 22px}}")
        go.clicked.connect(self._start_download)
        btns.addWidget(go)
        lay.addLayout(btns)
        return page

    # ── ② 진행 화면 ─────────────────────────────────────────
    def _progress_page(self) -> QWidget:
        page = QWidget()
        page.setStyleSheet("background:transparent")
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 8, 0, 8)
        lay.setSpacing(0)

        self.prog_head = QLabel("새 버전을 받고 있어요…")
        self.prog_head.setStyleSheet(
            f"{_SERIF};font-size:22px;font-weight:bold;color:{INK}")
        lay.addWidget(self.prog_head)
        lay.addSpacing(16)

        self.bar = QProgressBar()
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(8)
        self.bar.setRange(0, 0)          # 크기를 알기 전엔 물결(불확정)
        self.bar.setStyleSheet(
            f"QProgressBar{{background:{PILL_BG};border:none;"
            f"border-radius:4px}}"
            f"QProgressBar::chunk{{background:{CORAL};border-radius:4px}}")
        lay.addWidget(self.bar)
        lay.addSpacing(8)

        self.prog_label = QLabel("연결하는 중…")
        self.prog_label.setStyleSheet(f"font-size:12px;color:{INK_SOFT}")
        lay.addWidget(self.prog_label)
        lay.addSpacing(14)

        tip = QLabel("다 받으면 자동으로 설치되고, 끝나면 앱이 다시 켜져요.\n"
                     "이 창은 닫지 않아도 됩니다.")
        tip.setWordWrap(True)
        tip.setStyleSheet(f"font-size:12px;color:{INK_SOFT}")
        lay.addWidget(tip)
        lay.addStretch()
        return page

    def _start_download(self) -> None:
        self.stack.setCurrentIndex(1)
        self._dl = _Downloader(self.info["url"], self)
        self._dl.progress.connect(self._on_progress)
        self._dl.done.connect(self._on_done)
        self._dl.failed.connect(self._on_failed)
        self._dl.start()

    def _on_progress(self, done: int, total: int) -> None:
        mb = done / 1048576
        if total > 0:
            self.bar.setRange(0, 1000)
            self.bar.setValue(int(done * 1000 / total))
            self.prog_label.setText(
                f"{mb:.1f} / {total / 1048576:.1f} MB "
                f"({done * 100 // total}%)")
        else:
            self.prog_label.setText(f"{mb:.1f} MB 받음")

    def _on_done(self, path: str) -> None:
        self.bar.setRange(0, 1000)
        self.bar.setValue(1000)
        self.prog_head.setText("설치를 시작해요")
        self.prog_label.setText("잠시 뒤 앱이 새 버전으로 다시 켜집니다.")
        import updater
        updater.run_installer_and_quit(path)
        self.accept()

    def _on_failed(self, err: str) -> None:
        self.prog_head.setText("다운로드하지 못했어요")
        self.bar.setRange(0, 1000)
        self.bar.setValue(0)
        self.prog_label.setText(
            f"{err}\n인터넷 연결을 확인하고 다음에 다시 시도해 주세요.")
        close = QPushButton("닫기")
        close.setCursor(Qt.CursorShape.PointingHandCursor)
        close.setStyleSheet(
            f"QPushButton{{background:{PILL_BG};color:{INK};border:none;"
            f"border-radius:10px;padding:9px 18px;font-weight:bold}}"
            f"QPushButton:hover{{background:{CARD_BORDER}}}")
        close.clicked.connect(self.reject)
        page = self.stack.currentWidget()
        page.layout().addWidget(close, alignment=Qt.AlignmentFlag.AlignRight)
