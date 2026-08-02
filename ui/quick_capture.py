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

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QApplication


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


def _say(owner, text: str) -> None:
    """펭귄 옆 말풍선으로 알린다.

    토스트(ui.toast)는 부모 위젯 '안'에 그려져서 70px짜리 펭귄에서는
    글자가 잘려 안 보인다 — 그래서 독립 창인 AlertBubble을 쓴다.
    """
    try:
        from ui.alerts import AlertBubble
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

    loader = _Loader(owner.base_dir, parent=owner)
    loader.done.connect(lambda r: _finish(*r))
    loader.failed.connect(_fallback)
    owner._quick_loader = loader          # GC 방지
    loader.start()
