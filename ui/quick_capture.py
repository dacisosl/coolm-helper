# -*- coding: utf-8 -*-
"""⚡ 간편 등록 — 수정 창 없이 '보는 즉시 등록 + 포스트잇'.

흐름 (2026-07-26 사용자 결정):
1) 쿨메신저에서 보고 있는 쪽지를 읽는다 (capture, 백그라운드 스레드)
2) 첫 번째 일정 후보를 그대로 **자동 등록**한다
3) 그 일정을 **포스트잇**으로 바탕화면에 붙인다 → 제목·메모를 인라인 편집

읽지 못하면(쿨메신저가 없거나 쪽지를 안 보는 중) 클립보드를 시도하고,
그것도 없으면 무엇을 하면 되는지 말풍선으로 알려준다.
"""
from __future__ import annotations

import threading
from datetime import timedelta

from PyQt6.QtCore import Qt, QObject, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication, QDialog, QHBoxLayout, QLabel, QPushButton, QTextEdit,
    QVBoxLayout,
)

from ui import theme


class _Loader(QObject):
    """캡처·파싱은 느릴 수 있어 백그라운드에서 (UI 멈춤 방지)."""
    done = pyqtSignal(object)      # (candidates, msg, matched) | None
    failed = pyqtSignal(str)

    def __init__(self, base_dir: str, parent=None):
        super().__init__(parent)
        self.base_dir = base_dir

    def start(self) -> None:
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self) -> None:
        try:
            title = body = ""
            try:
                import capture
                got = capture.read_current_message()
                if got:
                    title, body = got.title, got.body
            except Exception:
                pass                      # 캡처 불가 → 아래 클립보드로
            if not body:
                self.failed.emit("no_capture")
                return
            from parser import pipeline
            self.done.emit(pipeline.quick_candidates(self.base_dir, title, body))
        except Exception as e:            # 파싱 실패까지 대비
            self.failed.emit(str(e))


def _register_and_pin(owner, cands, msg, matched: bool) -> bool:
    """첫 후보를 등록하고 포스트잇으로 붙인다. 성공하면 True."""
    from ui.desk_base import pin_note
    from ui.review_dialog import cand_ref

    if cands:
        c = cands[0]
        title = (c.suggested_title or msg.title or "").strip()
        start, all_day, is_deadline = c.start, c.all_day, c.is_deadline
        end = c.end or (None if all_day else start + timedelta(hours=1))
        ref = cand_ref(c) if matched else ""
    else:
        # 날짜를 못 찾았어도 '오늘'로 등록해 메모처럼 쓸 수 있게 한다
        from datetime import datetime
        title = (msg.title or "").strip()
        start = datetime.now().replace(second=0, microsecond=0)
        all_day, is_deadline, ref = False, False, ""
        end = start + timedelta(hours=1)
    if not title:
        return False
    ev = owner.store.add(title=title, start=start, end=end, all_day=all_day,
                         is_deadline=is_deadline,
                         memo=(msg.body or "").strip(), source_ref=ref)
    pin_note(ev.id)                       # 바탕화면 포스트잇에서 바로 수정
    return True


class ClipboardConfirmDialog(QDialog):
    """클립보드에서 가져올 때만 뜨는 확인 창 (2026-08-02 사용자 요청).

    화면에서 읽은 쪽지는 '지금 보고 있는 것'이라 바로 등록해도 되지만,
    클립보드는 언제 복사한 것인지 모른다 — 그래서 내용을 보여주고 묻는다.
    """

    PREVIEW_CHARS = 600

    def __init__(self, title: str, when: str, body: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("클립보드에서 등록")
        self.setStyleSheet(theme.BASE_QSS)
        self.setMinimumWidth(420)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 18, 20, 16)
        lay.setSpacing(10)

        head = QLabel("클립보드에서 아래와 같은 내용을 등록하시겠습니까?")
        head.setWordWrap(True)
        head.setStyleSheet(
            f"font-size:{theme.FONT_LG}px;font-weight:bold;color:{theme.TEXT}")
        lay.addWidget(head)

        summary = QLabel(f"📌 {when}    {title}" if when else f"📌 {title}")
        summary.setWordWrap(True)
        summary.setStyleSheet(
            f"background:{theme.PRIMARY_LIGHT};color:{theme.PRIMARY_DARK};"
            f"border-radius:{theme.RADIUS_MD}px;padding:8px 10px;"
            f"font-size:{theme.FONT_MD}px;font-weight:bold")
        lay.addWidget(summary)

        text = (body or "").strip()
        if len(text) > self.PREVIEW_CHARS:
            text = text[:self.PREVIEW_CHARS] + " …"
        view = QTextEdit()
        view.setPlainText(text)
        view.setReadOnly(True)
        view.setFixedHeight(150)
        view.setStyleSheet(
            f"QTextEdit{{background:{theme.CARD_TINT};border:1px solid "
            f"{theme.BORDER_SUBTLE};border-radius:{theme.RADIUS_MD}px;"
            f"padding:8px;font-size:{theme.FONT_MD}px;color:{theme.TEXT}}}")
        lay.addWidget(view)

        hint = QLabel("등록하면 바탕화면 포스트잇으로 붙어서 바로 고칠 수 있어요.")
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color:{theme.SUBTLE};font-size:{theme.FONT_SM}px")
        lay.addWidget(hint)

        row = QHBoxLayout()
        row.addStretch()
        cancel = QPushButton("취소")
        cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel.setStyleSheet(theme.TEXT_BTN)
        cancel.clicked.connect(self.reject)
        row.addWidget(cancel)
        ok = QPushButton("등록하기")
        ok.setCursor(Qt.CursorShape.PointingHandCursor)
        ok.setStyleSheet(theme.PRIMARY_BTN)
        ok.setDefault(True)
        ok.clicked.connect(self.accept)
        row.addWidget(ok)
        lay.addLayout(row)


def confirm_clipboard(owner, cands, msg) -> bool:
    """클립보드 내용을 보여주고 등록할지 묻는다 (화면 캡처 경로에서는 안 뜬다)."""
    from ui.review_dialog import kr_date
    if cands:
        c = cands[0]
        title = (c.suggested_title or msg.title or "").strip()
        when = kr_date(c.start) + ("" if c.all_day else c.start.strftime(" %H:%M"))
    else:
        title = (msg.title or "").strip()
        when = "날짜를 못 찾아 오늘로 등록해요"
    dlg = ClipboardConfirmDialog(title, when, msg.body or "", owner)
    return dlg.exec() == QDialog.DialogCode.Accepted


def _say(owner, text: str) -> None:
    """펭귄 옆 말풍선으로 알린다.

    토스트(ui.toast)는 부모 위젯 '안'에 그려져서 70px짜리 펭귄에서는
    글자가 잘려 안 보인다 — 그래서 독립 창인 AlertBubble을 쓴다.
    """
    try:
        from ui.alerts import AlertBubble
        old = getattr(owner, "_quick_bubble", None)
        if old is not None:                # "읽는 중…" 등 이전 말풍선 정리
            try:
                old.close()
            except Exception:
                pass
        bubble = AlertBubble([text], owner)
        owner._quick_bubble = bubble       # GC 방지
        bubble.show()
    except Exception:
        pass


def quick_pin(owner) -> None:
    """owner = WidgetBase(펭귄/상세 위젯). 캡처 → 자동 등록 → 포스트잇."""

    def _clipboard_text() -> str:
        cb = QApplication.clipboard()
        return (cb.text() or "").strip() if cb else ""

    def _fallback(_reason: str = "") -> None:
        text = _clipboard_text()
        if len(text) < 10:
            _say(owner, "읽을 쪽지가 없어요.\n쿨메신저에서 쪽지를 열어 두고\n다시 ⚡를 눌러 주세요.")
            return
        from parser import pipeline
        title = text.splitlines()[0][:40]
        try:
            cands, msg, matched = pipeline.quick_candidates(
                owner.base_dir, title, text)
        except Exception:
            _say(owner, "쪽지를 읽지 못했어요")
            return
        # 클립보드에서 가져올 때만 내용을 보여주고 물어본다
        if not confirm_clipboard(owner, cands, msg):
            return
        _finish(cands, msg, matched, from_clipboard=True)

    def _finish(cands, msg, matched, from_clipboard: bool = False) -> None:
        try:
            ok = _register_and_pin(owner, cands, msg, matched)
        except Exception:
            ok = False
        if not ok:
            _say(owner, "등록할 내용을 찾지 못했어요")
            return
        owner.on_events_changed()
        _say(owner, "일정으로 등록했어요!\n포스트잇에서 바로 고칠 수 있어요."
             + ("\n(클립보드에서 가져옴)" if from_clipboard else ""))

    # 읽기가 오래 걸리면(예: 프리워밍 전 첫 시도) 조용히 있지 말고 알린다
    from PyQt6.QtCore import QTimer
    waiting = QTimer(owner)
    waiting.setSingleShot(True)
    waiting.setInterval(700)
    waiting.timeout.connect(
        lambda: _say(owner, "쪽지를 읽는 중이에요…\n잠깐만요!"))

    loader = _Loader(owner.base_dir, parent=owner)
    loader.done.connect(lambda r: (waiting.stop(), _finish(*r)))
    loader.failed.connect(lambda why: (waiting.stop(), _fallback(why)))
    owner._quick_loader = loader          # GC 방지
    waiting.start()
    loader.start()
