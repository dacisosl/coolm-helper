# -*- coding: utf-8 -*-
"""포스트잇 '제출' 버튼 — 그 일정이 나온 원본 쪽지를 되찾아 보여준다.

(2026-09-04 사용자 요청) 회신하러 갈 때 "누가 보낸 쪽지였지?"를 바로 확인하는
회신 도우미. 쿨메신저를 자동 조작하지는 않는다 — 보낸 사람 이름을 복사해
두고 쿨메신저 창을 앞으로 올려 주는 데서 멈춘다. 쪽지 내용·목록은 건드리지
않는다(capture.py 정책).

되찾는 열쇠는 일정의 source_ref("쪽지key|시작일시", review_dialog.cand_ref).
화면·클립보드에서 등록해 DB와 매칭이 안 된 일정은 key가 없어서, 그때는
등록할 때 저장한 메모(=쪽지 본문)를 대신 보여준다.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication, QDialog, QHBoxLayout, QLabel, QPushButton, QTextEdit,
    QVBoxLayout,
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

    def __init__(self, event, msg, spans, near=None):
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
            sub_text = "이 일정은 아래 쪽지에서 등록됐어요."
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

        self.status = QLabel("")
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


def open_source_message(note) -> None:
    """포스트잇(PostItWidget)에서 부른다 — 원본을 찾아 창을 띄운다."""
    app = QApplication.instance()
    if app is not None:
        app.setOverrideCursor(Qt.CursorShape.WaitCursor)
    try:
        msg, spans = find_source_message(note.base_dir, note.config, note.event)
    finally:
        if app is not None:
            app.restoreOverrideCursor()
    near = None
    try:
        near = note.frameGeometry().center()
    except Exception:
        pass
    dlg = SourceMessageDialog(note.event, msg, spans, near=near)
    note._source_dlg = dlg                 # GC 방지
    dlg.exec()
