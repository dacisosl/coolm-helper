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
    QApplication, QCheckBox, QDialog, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QVBoxLayout,
)

from ui import theme

# 날짜 선택 모달에 한 번에 보여줄 최대 개수 — 긴 안내문에서 날짜가 우수수
# 잡히면 창이 화면을 넘긴다. 앞쪽(본문에서 먼저 나온) 것부터 보여준다.
MAX_DATE_OPTIONS = 8


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


def date_options(cands) -> list:
    """후보에서 '날짜 선택지'를 뽑는다 — 같은 날짜·시각은 하나로 합친다.

    파서는 같은 날짜를 문장마다 다시 잡아낼 수 있는데, 사용자에게는
    똑같아 보이는 줄이 여러 개면 고르기만 어려워진다.
    """
    seen, out = set(), []
    for c in cands:
        key = (c.start, c.all_day)
        if key in seen:
            continue
        seen.add(key)
        out.append(c)
        if len(out) >= MAX_DATE_OPTIONS:
            break
    return out


def option_label(c) -> str:
    """선택지 한 줄: '8/7(금) 오후 2:30 · 방학식' 형태."""
    from ui.review_dialog import kr_date
    when = kr_date(c.start)
    if not c.all_day:
        h, m = c.start.hour, c.start.minute
        ampm = "오전" if h < 12 else "오후"
        h12 = h % 12 or 12
        when += f" {ampm} {h12}:{m:02d}"
    else:
        when += " (하루 종일)"
    title = (c.suggested_title or "").strip()
    return f"{when} · {title}" if title else when


def _add_event(owner, cand, msg, matched: bool):
    """후보 하나(또는 None=오늘)를 일정으로 저장한다. 제목이 없으면 None."""
    from ui.review_dialog import cand_ref

    if cand is not None:
        title = (cand.suggested_title or msg.title or "").strip()
        start, all_day = cand.start, cand.all_day
        is_deadline = cand.is_deadline
        end = cand.end or (None if all_day else start + timedelta(hours=1))
        ref = cand_ref(cand) if matched else ""
    else:
        # 날짜를 못 찾았거나 사용자가 아무것도 안 고른 경우 → '오늘'로 등록해
        # 메모처럼 쓸 수 있게 한다
        from datetime import datetime
        title = (msg.title or "").strip()
        start = datetime.now().replace(second=0, microsecond=0)
        all_day, is_deadline, ref = False, False, ""
        end = start + timedelta(hours=1)
    if not title:
        return None
    return owner.store.add(title=title, start=start, end=end, all_day=all_day,
                           is_deadline=is_deadline,
                           memo=(msg.body or "").strip(), source_ref=ref)


def _register_and_pin(owner, cands, msg, matched: bool, chosen=None) -> int:
    """고른 날짜들을 등록하고 포스트잇으로 붙인다. 등록한 개수를 돌려준다.

    chosen=None이면 예전처럼 첫 후보 하나만 (날짜 선택 모달을 거치지 않는
    경로용). chosen이 빈 리스트면 '아무 날짜도 안 고름' → 오늘로 등록한다.
    """
    from ui.desk_base import pin_note

    if chosen is None:
        picks = [cands[0]] if cands else [None]
    else:
        picks = list(chosen) or [None]
    ids = []
    for cand in picks:
        ev = _add_event(owner, cand, msg, matched)
        if ev is not None:
            ids.append(ev.id)
    for eid in ids:
        pin_note(eid)                     # 바탕화면 포스트잇에서 바로 수정
    return len(ids)


class DatePickDialog(QDialog):
    """본문에서 날짜를 찾았을 때 '어느 날짜로 등록할까요?'를 묻는다.

    (2026-09-03 사용자 요청) 자동으로 잡은 날짜가 여러 개거나 원하는 날짜가
    아닐 때가 있어서, 알아서 넣기 전에 한 번 확인받는다.
    - 여러 개 체크하면 그 날짜마다 하나씩 등록된다.
    - 아무것도 체크하지 않으면 오늘 날짜로 등록된다.
    첫 번째(예전에 자동으로 쓰이던) 날짜는 미리 체크해 둔다 — 그대로
    엔터를 치면 지금까지와 똑같이 동작한다.
    """

    PREVIEW_CHARS = 400

    def __init__(self, options: list, body: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle("날짜 선택")
        self.setStyleSheet(theme.BASE_QSS)
        self.setMinimumWidth(420)
        self.checks: list[QCheckBox] = []
        self._options = list(options)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 18, 20, 16)
        lay.setSpacing(10)

        head = QLabel("어떤 날짜에 일정을 등록하시겠습니까?")
        head.setWordWrap(True)
        head.setStyleSheet(
            f"font-size:{theme.FONT_LG}px;font-weight:bold;color:{theme.TEXT}")
        lay.addWidget(head)

        sub = QLabel("쪽지에서 찾은 날짜예요. 여러 개 고르면 각각 등록돼요.")
        sub.setWordWrap(True)
        sub.setStyleSheet(f"color:{theme.SUBTLE};font-size:{theme.FONT_SM}px")
        lay.addWidget(sub)

        for i, c in enumerate(self._options):
            cb = QCheckBox(option_label(c))
            cb.setChecked(i == 0)          # 예전 자동 선택값을 기본으로
            cb.setCursor(Qt.CursorShape.PointingHandCursor)
            cb.setStyleSheet(
                f"QCheckBox{{font-size:{theme.FONT_MD}px;color:{theme.TEXT};"
                f"padding:6px 8px;border-radius:{theme.RADIUS_SM}px}}"
                f"QCheckBox:hover{{background:{theme.CARD_TINT}}}")
            self.checks.append(cb)
            lay.addWidget(cb)

        if body:
            text = body.strip()
            if len(text) > self.PREVIEW_CHARS:
                text = text[:self.PREVIEW_CHARS] + " …"
            view = QTextEdit()
            view.setPlainText(text)
            view.setReadOnly(True)
            view.setFixedHeight(110)
            view.setStyleSheet(
                f"QTextEdit{{background:{theme.CARD_TINT};border:1px solid "
                f"{theme.BORDER_SUBTLE};border-radius:{theme.RADIUS_MD}px;"
                f"padding:8px;font-size:{theme.FONT_SM}px;color:{theme.TEXT}}}")
            lay.addWidget(view)

        hint = QLabel("아무것도 고르지 않으면 오늘 날짜로 등록해요.")
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color:{theme.SUBTLE};font-size:{theme.FONT_XS}px")
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

    def chosen(self) -> list:
        """체크된 날짜 후보들. 아무것도 안 골랐으면 빈 리스트(=오늘)."""
        return [c for c, cb in zip(self._options, self.checks) if cb.isChecked()]


def ask_dates(owner, cands, msg, body: str = ""):
    """날짜 선택 모달을 띄운다. 취소면 None, 아니면 고른 후보 리스트."""
    options = date_options(cands)
    if not options:
        return []                          # 찾은 날짜가 없으면 물을 것도 없다
    dlg = DatePickDialog(options, body, owner)
    if dlg.exec() != QDialog.DialogCode.Accepted:
        return None
    return dlg.chosen()


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


def _hush(owner) -> None:
    """떠 있는 말풍선("읽는 중…" 등)을 닫는다 — 모달을 띄우기 전에 부른다.

    안 닫으면 사용자가 모달을 취소했을 때 '읽는 중' 말풍선만 덩그러니 남는다.
    """
    old = getattr(owner, "_quick_bubble", None)
    if old is not None:
        try:
            old.close()
        except Exception:
            pass
        owner._quick_bubble = None


def _say(owner, text: str) -> None:
    """펭귄 옆 말풍선으로 알린다.

    토스트(ui.toast)는 부모 위젯 '안'에 그려져서 70px짜리 펭귄에서는
    글자가 잘려 안 보인다 — 그래서 독립 창인 AlertBubble을 쓴다.
    """
    try:
        from ui.alerts import AlertBubble
        _hush(owner)                       # "읽는 중…" 등 이전 말풍선 정리
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
        # 클립보드에서 가져올 때만 내용을 보여주고 물어본다.
        # 날짜를 찾았으면 날짜 선택 모달이 그 확인 역할까지 겸한다
        # (본문 미리보기를 같이 보여줘서 창이 두 번 뜨지 않게).
        _hush(owner)                      # 모달 뒤에 '읽는 중' 말풍선이 남지 않게
        if cands:
            chosen = ask_dates(owner, cands, msg, text)
            if chosen is None:
                return
        else:
            if not confirm_clipboard(owner, cands, msg):
                return
            chosen = None
        _finish(cands, msg, matched, from_clipboard=True, chosen=chosen)

    def _finish(cands, msg, matched, from_clipboard: bool = False,
                chosen=None) -> None:
        try:
            n = _register_and_pin(owner, cands, msg, matched, chosen)
        except Exception:
            n = 0
        if not n:
            _say(owner, "등록할 내용을 찾지 못했어요")
            return
        owner.on_events_changed()
        head = ("일정으로 등록했어요!" if n == 1
                else f"{n}개 날짜로 등록했어요!")
        _say(owner, f"{head}\n포스트잇에서 바로 고칠 수 있어요."
             + ("\n(클립보드에서 가져옴)" if from_clipboard else ""))

    def _on_screen(cands, msg, matched) -> None:
        """화면에서 읽은 쪽지 — 본문에 날짜가 있을 때만 한 번 물어본다.

        날짜를 못 찾았으면 예전처럼 묻지 않고 오늘로 바로 등록한다.
        """
        if cands:
            _hush(owner)                  # 모달 뒤에 '읽는 중' 말풍선이 남지 않게
            chosen = ask_dates(owner, cands, msg)
            if chosen is None:
                return                    # 취소
        else:
            chosen = None
        _finish(cands, msg, matched, chosen=chosen)

    # 읽기가 오래 걸리면(예: 프리워밍 전 첫 시도) 조용히 있지 말고 알린다
    from PyQt6.QtCore import QTimer
    waiting = QTimer(owner)
    waiting.setSingleShot(True)
    waiting.setInterval(700)
    waiting.timeout.connect(
        lambda: _say(owner, "쪽지를 읽는 중이에요…\n잠깐만요!"))

    loader = _Loader(owner.base_dir, parent=owner)
    loader.done.connect(lambda r: (waiting.stop(), _on_screen(*r)))
    loader.failed.connect(lambda why: (waiting.stop(), _fallback(why)))
    owner._quick_loader = loader          # GC 방지
    waiting.start()
    loader.start()
