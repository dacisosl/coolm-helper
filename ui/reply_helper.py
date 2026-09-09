# -*- coding: utf-8 -*-
"""포스트잇 '제출' 버튼 — 그 쪽지를 보낸 사람에게 **쪽지 쓰기**를 열어 준다.

(2026-09-08 사용자 재설계) 관리함에서 옛 쪽지를 찾는 방식은 목록에 없는
쪽지가 많아 자주 실패했다. 이제는 일정에 저장해 둔 **보낸 사람 이름**으로
쿨메신저 조직도에서 그 사람을 찾아 새 쪽지 창을 연다 — DB도, 관리함 목록도
필요 없으니 아무리 오래된 포스트잇도 동작한다.
이름이 저장돼 있지 않은 옛 포스트잇은 한 번 물어보고(NameAskDialog) 기억한다.


(2026-09-04 사용자 요청) 회신하러 갈 때 "누가 보낸 쪽지였지?"를 바로 확인하는
회신 도우미. 쿨메신저를 자동 조작하지는 않는다 — 보낸 사람 이름을 복사해
두고 쿨메신저 창을 앞으로 올려 주는 데서 멈춘다. 쪽지 내용·목록은 건드리지
않는다(capture.py 정책).

되찾는 열쇠는 일정의 source_ref("쪽지key|시작일시", review_dialog.cand_ref).
화면·클립보드에서 등록해 DB와 매칭이 안 된 일정은 key가 없어서, 그때는
등록할 때 저장한 메모(=쪽지 본문)를 대신 보여준다.
"""
from __future__ import annotations

import threading

from PyQt6.QtCore import QObject, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication, QDialog, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTextEdit, QVBoxLayout,
)

from ui import theme


def parse_source_key(ref: str) -> int | None:
    """'3841|2026-08-05T15:00:00' → 3841. 비었거나 DB에 없는 표식(음수)은 None."""
    head = (ref or "").split("|", 1)[0].strip()
    try:
        key = int(head)
    except ValueError:
        return None
    return key if key > 0 else None


def sender_name(sender: str) -> str:
    """'정주은(정주은)' → '정주은'. 받는 사람 칸에 붙여 넣기 좋게 이름만."""
    name = (sender or "").split("(", 1)[0].strip()
    return name or (sender or "").strip()


def find_source_message(base_dir: str, config: dict, event):
    """일정의 원본 쪽지와 본문의 개인정보 위치. 못 찾으면 (None, []).

    pipeline.quick_candidates와 같은 순서로 직접 읽기 → 복사 폴백.
    원본(udb)은 읽기 전용으로만 연다 (CLAUDE.md 절대 규칙).
    """
    key = parse_source_key(getattr(event, "source_ref", "") or "")
    memo_dir = (config or {}).get("memo_dir")
    if key is None or not memo_dir:
        return None, []
    from parser import pii_detector, pipeline
    from parser.db_reader import DbReader
    for direct in (True, False):
        try:
            with DbReader(memo_dir, direct=direct) as reader:
                msg = reader.get_message(key)
                if msg is None:
                    return None, []
                try:
                    roster = pipeline.build_roster(base_dir, config, reader)
                except Exception:
                    roster = set()
            return msg, pii_detector.detect(msg.body or "", roster)
        except Exception:
            continue
    return None, []


class SourceMessageDialog(QDialog):
    """"○○○ 선생님이 보낸 쪽지" — 원본을 보여주고 회신 준비를 돕는다.

    바탕화면 위젯의 자식으로 두면 뒤로 깔리므로 부모 없이 '항상 위'로 띄운다
    (ui/desk_widgets.py의 관례). 개인정보는 빨간 표시만, 마스킹은 하지 않는다.
    """

    BODY_CHARS = 8000

    def __init__(self, event, msg, spans, near=None, reason: str = ""):
        super().__init__(None)
        self.setWindowFlags(Qt.WindowType.Dialog
                            | Qt.WindowType.WindowStaysOnTopHint)
        self.setWindowTitle("원본 쪽지")
        self.setStyleSheet(theme.BASE_QSS)
        self.setMinimumWidth(480)
        self.event, self.msg, self._near = event, msg, near

        from ui.review_dialog import highlight_html, kr_date

        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 18, 20, 16)
        lay.setSpacing(10)

        if msg is not None:
            head_text = f"{sender_name(msg.sender)} 선생님이 보낸 쪽지"
            sub_text = ("쿨메신저에서 이 쪽지를 자동으로 열지 못해 여기에 보여드려요. "
                        "이 일정은 아래 쪽지에서 등록됐어요.")
            when = kr_date(msg.received) + msg.received.strftime(" %H:%M")
            chip_text = f"📌 {when}    {(msg.title or '').strip()}"
            body_html = highlight_html((msg.body or "")[:self.BODY_CHARS], spans)
        else:
            head_text = "원본 쪽지를 찾지 못했어요"
            sub_text = ("화면이나 클립보드에서 등록한 일정이라 쪽지함과 연결돼 있지 "
                        "않아요. 등록할 때 저장해 둔 내용을 대신 보여드려요.")
            chip_text = f"📌 {(getattr(event, 'title', '') or '').strip()}"
            body_html = highlight_html(
                (getattr(event, "memo", "") or "")[:self.BODY_CHARS], [])

        head = QLabel(head_text)
        head.setWordWrap(True)
        head.setStyleSheet(
            f"font-size:{theme.FONT_LG}px;font-weight:bold;color:{theme.TEXT}")
        lay.addWidget(head)

        sub = QLabel(sub_text)
        sub.setWordWrap(True)
        sub.setStyleSheet(f"color:{theme.SUBTLE};font-size:{theme.FONT_SM}px")
        lay.addWidget(sub)

        chip = QLabel(chip_text)
        chip.setWordWrap(True)
        chip.setStyleSheet(
            f"background:{theme.PRIMARY_LIGHT};color:{theme.PRIMARY_DARK};"
            f"border-radius:{theme.RADIUS_MD}px;padding:8px 10px;"
            f"font-size:{theme.FONT_MD}px;font-weight:bold")
        lay.addWidget(chip)

        view = QTextEdit()
        view.setHtml(body_html)
        view.setReadOnly(True)
        view.setMinimumHeight(180)
        view.setStyleSheet(
            f"QTextEdit{{background:{theme.CARD_TINT};border:1px solid "
            f"{theme.BORDER_SUBTLE};border-radius:{theme.RADIUS_MD}px;"
            f"padding:10px;font-size:{theme.FONT_MD}px;color:{theme.TEXT}}}")
        self.body_view = view
        lay.addWidget(view, stretch=1)

        hint = QLabel("회신하려면 쿨메신저에서 '쪽지 보내기'를 열고, "
                      "받는 사람 칸에 복사한 이름을 붙여 넣으세요.")
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color:{theme.SUBTLE};font-size:{theme.FONT_SM}px")
        lay.addWidget(hint)

        self.status = QLabel(reason or "")
        self.status.setWordWrap(True)
        self.status.setStyleSheet(
            f"color:{theme.PRIMARY_DARK};font-size:{theme.FONT_SM}px")
        lay.addWidget(self.status)

        row = QHBoxLayout()
        self.copy_btn = QPushButton("이름 복사")
        self.copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.copy_btn.setStyleSheet(theme.TEXT_BTN)
        self.copy_btn.setEnabled(msg is not None and bool(sender_name(msg.sender)))
        self.copy_btn.setToolTip("보낸 사람 이름을 복사해요 — 받는 사람 칸에 붙여 넣기")
        self.copy_btn.clicked.connect(self.copy_name)
        row.addWidget(self.copy_btn)
        self.front_btn = QPushButton("쿨메신저 창 앞으로")
        self.front_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.front_btn.setStyleSheet(theme.TEXT_BTN)
        self.front_btn.clicked.connect(self.bring_coolm_front)
        row.addWidget(self.front_btn)
        self.find_btn = QPushButton("관리함에서 이 쪽지 찾기")
        self.find_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.find_btn.setStyleSheet(theme.TEXT_BTN)
        self.find_btn.setEnabled(msg is not None)
        self.find_btn.setToolTip("쿨메신저 메시지 관리함에서 이 쪽지를 찾아 열어 봐요")
        self.find_btn.clicked.connect(self.find_in_manager)
        row.addWidget(self.find_btn)
        row.addStretch()
        close = QPushButton("닫기")
        close.setCursor(Qt.CursorShape.PointingHandCursor)
        close.setStyleSheet(theme.PRIMARY_BTN)
        close.setDefault(True)
        close.clicked.connect(self.accept)
        row.addWidget(close)
        lay.addLayout(row)
        self.resize(560, 440)

    # ── 버튼 동작 ─────────────────────────────────────────────
    def copy_name(self) -> None:
        if self.msg is None:
            return
        name = sender_name(self.msg.sender)
        cb = QApplication.clipboard()
        if cb is not None:
            cb.setText(name)
        self.status.setText(f"복사했어요: {name} — 쿨메신저 받는 사람 칸에 붙여 넣으세요.")

    def find_in_manager(self) -> None:
        """예전 방식 — 관리함 목록에서 이 쪽지를 찾아 연다 (되면 가장 정확하다)."""
        if self.msg is None:
            return
        ok = False
        why = ""
        try:
            import coolm_control
            ok, why = coolm_control.open_message(self.msg)
        except Exception as e:
            why = str(e)
        if ok:
            self.accept()
        else:
            self.status.setText(why or "관리함에서 찾지 못했어요.")

    def bring_coolm_front(self) -> None:
        ok = False
        try:
            import capture
            ok = capture.bring_to_front()
        except Exception:
            ok = False
        self.status.setText("" if ok else
                            "쿨메신저 창을 찾지 못했어요 — 쿨메신저가 켜져 있는지 확인해 주세요.")

    # ── 뜨는 자리: 포스트잇이 있는 화면의 가운데 ─────────────
    def showEvent(self, ev):
        super().showEvent(ev)
        self._center_on_screen()
        self.raise_()
        self.activateWindow()

    def _center_on_screen(self) -> None:
        scr = None
        if self._near is not None:
            try:
                from ui.widget_base import screen_at
                scr = screen_at(self._near)
            except Exception:
                scr = None
        scr = scr or self.screen() or QApplication.primaryScreen()
        if scr is None:
            return
        g = scr.availableGeometry()
        self.move(g.center().x() - self.width() // 2,
                  g.center().y() - self.height() // 2)


class NameAskDialog(QDialog):
    """보낸 사람이 저장돼 있지 않은 옛 포스트잇 — 이름을 한 번 물어본다.

    (2026-09-08 사용자 결정) 적은 이름으로 바로 쪽지 쓰기를 실행하고,
    그 이름을 일정에 저장해 다음부터는 묻지 않는다.
    """

    def __init__(self, event, guess: str = "", parent=None):
        super().__init__(None)
        self.setWindowFlags(Qt.WindowType.Dialog
                            | Qt.WindowType.WindowStaysOnTopHint)
        self.setWindowTitle("누구에게 쪽지를 보낼까요?")
        self.setStyleSheet(theme.BASE_QSS)
        self.setMinimumWidth(420)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 18, 20, 16)
        lay.setSpacing(10)

        head = QLabel("누구에게 쪽지를 보낼까요?")
        head.setStyleSheet(
            f"font-size:{theme.FONT_LG}px;font-weight:bold;color:{theme.TEXT}")
        lay.addWidget(head)

        sub = QLabel("이 포스트잇에는 보낸 사람이 저장돼 있지 않아요.\n"
                     "쿨메신저 조직도에 있는 이름을 적어 주세요. "
                     "한 번 적으면 이 포스트잇이 기억해요.")
        sub.setWordWrap(True)
        sub.setStyleSheet(f"color:{theme.SUBTLE};font-size:{theme.FONT_SM}px")
        lay.addWidget(sub)

        chip = QLabel(f"📌 {(getattr(event, 'title', '') or '').strip()}")
        chip.setWordWrap(True)
        chip.setStyleSheet(
            f"background:{theme.PRIMARY_LIGHT};color:{theme.PRIMARY_DARK};"
            f"border-radius:{theme.RADIUS_MD}px;padding:8px 10px;"
            f"font-size:{theme.FONT_MD}px;font-weight:bold")
        lay.addWidget(chip)

        self.edit = QLineEdit(sender_name(guess))
        self.edit.setPlaceholderText("예: 정주은")
        self.edit.setStyleSheet(
            f"QLineEdit{{background:{theme.CARD};border:1px solid "
            f"{theme.BORDER};border-radius:{theme.RADIUS_MD}px;padding:8px 10px;"
            f"font-size:{theme.FONT_MD}px;color:{theme.TEXT}}}")
        self.edit.returnPressed.connect(self._ok)
        lay.addWidget(self.edit)

        row = QHBoxLayout()
        row.addStretch()
        cancel = QPushButton("취소")
        cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel.setStyleSheet(theme.TEXT_BTN)
        cancel.clicked.connect(self.reject)
        row.addWidget(cancel)
        ok = QPushButton("쪽지 쓰기")
        ok.setCursor(Qt.CursorShape.PointingHandCursor)
        ok.setStyleSheet(theme.PRIMARY_BTN)
        ok.setDefault(True)
        ok.clicked.connect(self._ok)
        row.addWidget(ok)
        lay.addLayout(row)

    def _ok(self) -> None:
        if self.name():
            self.accept()

    def name(self) -> str:
        return sender_name(self.edit.text())


class InfoDialog(QDialog):
    """사람은 찾았지만 쪽지 창이 안 뜬 경우의 짧은 안내."""

    def __init__(self, text: str):
        super().__init__(None)
        self.setWindowFlags(Qt.WindowType.Dialog
                            | Qt.WindowType.WindowStaysOnTopHint)
        self.setWindowTitle("쪽지 쓰기")
        self.setStyleSheet(theme.BASE_QSS)
        self.setMinimumWidth(380)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 18, 20, 16)
        lay.setSpacing(12)
        lab = QLabel(text)
        lab.setWordWrap(True)
        lab.setStyleSheet(f"font-size:{theme.FONT_MD}px;color:{theme.TEXT}")
        lay.addWidget(lab)
        row = QHBoxLayout()
        row.addStretch()
        ok = QPushButton("확인")
        ok.setCursor(Qt.CursorShape.PointingHandCursor)
        ok.setStyleSheet(theme.PRIMARY_BTN)
        ok.setDefault(True)
        ok.clicked.connect(self.accept)
        row.addWidget(ok)
        lay.addLayout(row)


class _Opener(QObject):
    """조직도에서 사람을 찾아 쪽지 쓰기 — 몇 초 걸릴 수 있어 백그라운드에서.

    memory({"compose_method": …})는 이 스레드에서만 만지고, 끝난 뒤 UI 스레드가
    config에 옮겨 저장한다 (통한 방법을 기억해 다음부터 바로 그 방법으로).
    """
    done = pyqtSignal(str, str)          # (상태, 안내문)

    def __init__(self, name: str, parent=None, memory: dict | None = None):
        super().__init__(parent)
        self.name = name
        self.memory = memory if memory is not None else {}

    def start(self) -> None:
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self) -> None:
        try:
            import coolm_control
            state, why = coolm_control.compose_to(self.name, memory=self.memory)
        except Exception as e:
            state, why = "failed", str(e)
        self.done.emit(state, why or "")


PREPARING_TEXT = "제출을 위한 준비중입니다."


def _show_preparing(note):
    """기다리는 동안 포스트잇 위에 은은한 안내 (2026-09-09 사용자 요청).

    끝나면 _finish가 지운다. 포스트잇이 없는(테스트) 환경이면 None.
    """
    try:
        from ui.toast import show_toast
        toast = show_toast(note, PREPARING_TEXT, msec=60000)
    except Exception:
        return None
    note._preparing_toast = toast          # GC 방지
    return toast


def _remember_method(note, memory: dict) -> None:
    """통한 활성화 방법을 config에 저장 — 다음 '제출'은 그 방법부터 시도한다."""
    try:
        from coolm_control import MEMORY_KEY
        method = memory.get(MEMORY_KEY, "")
        cfg = getattr(note, "config", None)
        if not method or cfg is None or cfg.get(MEMORY_KEY, "") == method:
            return
        cfg[MEMORY_KEY] = method
        from parser import pipeline
        pipeline.save_config(note.base_dir, cfg)
    except Exception:
        pass


def remembered_sender(note) -> str:
    """이 포스트잇이 기억하는 보낸 사람. 없으면 쪽지함에서 찾아 기억한다."""
    name = (getattr(note.event, "sender", "") or "").strip()
    if name:
        return name
    msg, _spans = find_source_message(note.base_dir, note.config, note.event)
    if msg is None:
        return ""
    name = (msg.sender or "").strip()
    if name:
        _remember(note, name)
    return name


def _remember(note, name: str) -> None:
    """찾은(또는 사용자가 적은) 이름을 일정에 저장 — 다음부터 바로 열린다."""
    try:
        note.store.update(note.event.id, sender=name)
        note.event.sender = name
    except Exception:
        pass


def _show_fallback(note, reason: str) -> None:
    """실패했을 때만 — 원본 쪽지 내용을 보여주는 대체 창."""
    msg, spans = find_source_message(note.base_dir, note.config, note.event)
    near = None
    try:
        near = note.frameGeometry().center()
    except Exception:
        pass
    dlg = SourceMessageDialog(note.event, msg, spans, near=near, reason=reason)
    note._source_dlg = dlg                 # GC 방지
    dlg.exec()


def open_source_message(note) -> None:
    """포스트잇 '제출' — 보낸 사람에게 쪽지 쓰기를 연다.

    ① 일정에 저장된 이름 → ② 없으면 쪽지함에서 찾아 기억 →
    ③ 그래도 없으면 사용자에게 한 번 물어본다(적은 이름을 기억).
    이름을 알면 쿨메신저 조직도에서 그 사람을 찾아 새 쪽지 창을 연다.
    """
    app = QApplication.instance()
    note._source_result = None
    if app is not None:
        app.setOverrideCursor(Qt.CursorShape.WaitCursor)
    try:
        name = remembered_sender(note)
    finally:
        if app is not None:
            app.restoreOverrideCursor()

    if not name:
        ask = NameAskDialog(note.event, parent=note)
        note._name_dlg = ask               # GC 방지
        if ask.exec() != QDialog.DialogCode.Accepted:
            note._source_result = ("cancelled", "")
            return
        name = ask.name()
        _remember(note, name)

    if app is not None:
        app.setOverrideCursor(Qt.CursorShape.WaitCursor)
    toast = _show_preparing(note)
    cfg = getattr(note, "config", None) or {}
    from coolm_control import MEMORY_KEY
    memory = {MEMORY_KEY: cfg.get(MEMORY_KEY, "") or ""}
    opener = _Opener(name, parent=note, memory=memory)

    def _finish(state: str, why: str) -> None:
        if app is not None:
            app.restoreOverrideCursor()
        if toast is not None:
            try:
                toast._dismiss()
            except RuntimeError:
                pass
        _remember_method(note, memory)
        note._source_result = (state, why)
        if state == "opened":
            return                         # 쪽지 쓰기 창이 떴으니 할 일 없음
        if state == "selected":
            info = InfoDialog(why)
            note._info_dlg = info          # GC 방지
            info.exec()
            return
        _show_fallback(note, why)

    opener.done.connect(_finish)
    note._source_opener = opener           # GC 방지
    opener.start()
