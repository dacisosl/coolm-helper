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
from PyQt6.QtGui import QColor, QTextCursor
from PyQt6.QtWidgets import (
    QApplication, QCheckBox, QDialog, QFrame, QHBoxLayout, QLabel,
    QPushButton, QScrollArea, QTextEdit, QVBoxLayout, QWidget,
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

    개수를 자를 때는 **본문에 먼저 나온 순서**로 자르고(맨 앞 후보 =
    예전에 자동으로 쓰이던 날짜라 항상 남는다), 보여줄 때는 **날짜순**으로
    정렬한다 (2026-09-03 사용자 요청 — 뒤죽박죽이면 고르기 어렵다).
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
    return sorted(out, key=lambda c: (c.start, not c.all_day))


def option_label(c) -> str:
    """선택지의 날짜 한 줄: '8/7(금) 오후 2:30' / '9/16(수) 하루 종일 · 마감'.

    제목은 넣지 않는다 — 어느 날짜든 제목이 같아서(쪽지 제목) 줄만 길어지고
    구분에 도움이 안 됐다. 무슨 일정인지는 옆의 본문 대목으로 판단한다.
    """
    from ui.review_dialog import kr_date
    when = kr_date(c.start)
    if not c.all_day:
        h, m = c.start.hour, c.start.minute
        ampm = "오전" if h < 12 else "오후"
        h12 = h % 12 or 12
        when += f" {ampm} {h12}:{m:02d}"
    else:
        when += " 하루 종일"
    return when + " · 마감" if c.is_deadline else when


def source_text_of(c) -> str:
    """후보를 뽑아낸 원문 — 파서가 본 것과 같은 '제목 + 줄바꿈 + 본문'.

    \\r을 공백으로 바꾼다(길이는 그대로) — 화면에 그릴 때 위치가 한 칸씩
    밀리면 아래 source_span 하이라이트가 엉뚱한 글자를 짚는다.
    """
    msg = getattr(c, "message", None)
    if msg is None:
        return ""
    text = f"{getattr(msg, 'title', '') or ''}\n{getattr(msg, 'body', '') or ''}"
    return text.replace("\r", " ")


def display_text(c):
    """화면에 보여줄 쪽지 내용과, 원문 위치를 그 안의 위치로 옮기는 함수.

    파서가 본 원문은 '제목 + 줄바꿈 + 본문'인데, 쿨메신저 쪽지는 제목이
    본문의 한 줄과 똑같은 경우가 흔하다(부재중 쪽지 등). 그대로 그리면
    같은 문장이 두 번 보인다(2026-09-04 사용자 지적) — 그럴 땐 제목 줄을
    빼고 본문만 보여준다.

    제목 줄을 빼면 글자 위치가 밀리므로, source_span을 그대로 쓸 수 없다.
    그래서 위치 변환 함수를 같이 돌려준다. 제목 쪽에서 찾은 날짜는 본문의
    같은 문장으로 옮겨 준다 — 안 그러면 하이라이트가 사라진다.
    """
    text = source_text_of(c)
    same = lambda p: p                       # noqa: E731 (한 줄짜리 항등 변환)
    if not text:
        return "", same
    msg = getattr(c, "message", None)
    raw_title = getattr(msg, "title", "") or ""
    body = (getattr(msg, "body", "") or "").replace("\r", " ")
    title = raw_title.strip()
    if not title or title not in [ln.strip() for ln in body.splitlines()]:
        return text, same                    # 제목이 겹치지 않으면 그대로

    # 제목 줄을 뺐으니 본문 맨 앞의 빈 줄도 함께 걷어낸다 (첫 줄이 비어 보임)
    blank = len(body) - len(body.lstrip("\n"))
    body = body[blank:]
    head = len(raw_title) + 1 + blank        # 원문에서 (남긴) 본문이 시작하는 자리
    lead = len(raw_title) - len(raw_title.lstrip())
    twin = body.find(title)                  # 본문 안의 같은 문장

    def to_body(p: int):
        if p >= head:
            return p - head                  # 본문에 있던 위치
        if twin >= 0 and lead <= p < lead + len(title):
            return twin + (p - lead)         # 제목에 있던 위치 → 본문의 같은 자리
        return None                          # 옮길 데가 없다 (표시 안 함)

    return body, to_body


def source_context(c, width: int = 46) -> str:
    """그 날짜가 적혀 있던 대목을 한 줄로 뽑는다 ('…9월 16일까지 제출…').

    날짜만 봐서는 어떤 일정인지 모른다는 지적(2026-09-03)에 따라,
    선택지마다 본문의 그 자리를 같이 보여주기 위한 것.
    """
    text = source_text_of(c)
    span = getattr(c, "source_span", None)
    if not text:
        return ""
    if span is None:                       # 위치를 모르면 원문 조각으로 찾는다
        frag = (getattr(c, "source_text", "") or "").strip()
        i = text.find(frag) if frag else -1
        if i < 0:
            return ""
        span = (i, i + len(frag))
    s, e = span
    if not (0 <= s < e <= len(text)):
        return ""
    # 같은 줄 안에서만 앞뒤로 넓힌다 — 줄을 넘어가면 다른 문단이 섞인다
    left = text.rfind("\n", 0, s) + 1
    right = text.find("\n", e)
    if right < 0:
        right = len(text)
    pad = max(0, (width - (e - s)) // 2)
    a, b = max(left, s - pad), min(right, e + pad)
    snippet = " ".join(text[a:b].split())
    if not snippet:
        return ""
    return ("…" if a > left else "") + snippet + ("…" if b < right else "")


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


class _OptionRow(QFrame):
    """날짜 선택지 한 줄 — 글자 아무 데나 눌러도 체크가 토글된다."""

    clicked = pyqtSignal()

    def mousePressEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(ev)


class DatePickDialog(QDialog):
    """본문에서 날짜를 찾았을 때 '어느 날짜로 등록할까요?'를 묻는다.

    (2026-09-03 사용자 요청) 자동으로 잡은 날짜가 여러 개거나 원하는 날짜가
    아닐 때가 있어서, 알아서 넣기 전에 한 번 확인받는다.
    - 여러 개 체크하면 그 날짜마다 하나씩 등록된다.
    - 아무것도 체크하지 않으면 오늘 날짜로 등록된다.

    화면 구성 (2026-09-03 2차 요청):
    - 왼쪽: 날짜순으로 정렬된 선택지. 날짜 밑에 그 날짜가 나온 본문 대목.
    - 오른쪽: 쪽지 내용 그대로 — 읽어 보고 결정할 수 있게.
    - 날짜를 누르면 오른쪽 본문에서 그 자리로 스크롤되며 노랗게 표시된다.
    미리 체크되는 것은 '예전에 자동으로 등록되던 그 날짜'다(날짜순으로는
    가운데일 수 있다) — 그대로 [등록하기]를 누르면 지금까지와 똑같이 된다.
    """

    BODY_CHARS = 8000          # 아주 긴 쪽지는 잘라서 창이 무거워지지 않게

    def __init__(self, options: list, body: str = "", parent=None,
                 default=None):
        super().__init__(parent)
        self.setWindowTitle("날짜 선택")
        self.setStyleSheet(theme.BASE_QSS)
        self.checks: list[QCheckBox] = []
        self._options = list(options)
        self._rows: list[_OptionRow] = []

        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 18, 20, 16)
        lay.setSpacing(10)

        head = QLabel("어떤 날짜에 일정을 등록하시겠습니까?")
        head.setWordWrap(True)
        head.setStyleSheet(
            f"font-size:{theme.FONT_LG}px;font-weight:bold;color:{theme.TEXT}")
        lay.addWidget(head)

        sub = QLabel("쪽지에서 찾은 날짜예요. 여러 개 고르면 각각 등록돼요. "
                     "날짜를 누르면 오른쪽 쪽지에서 그 자리를 보여줘요.")
        sub.setWordWrap(True)
        sub.setStyleSheet(f"color:{theme.SUBTLE};font-size:{theme.FONT_SM}px")
        lay.addWidget(sub)

        cols = QHBoxLayout()
        cols.setSpacing(14)
        cols.addWidget(self._date_column(default), stretch=0)
        cols.addWidget(self._body_column(body), stretch=1)
        lay.addLayout(cols, stretch=1)

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

        self.resize(820, 460)

    # ── 왼쪽: 날짜 선택지 ────────────────────────────────────
    def _date_column(self, default) -> QWidget:
        """날짜순 선택지 목록. 개수가 많아도 창이 커지지 않게 스크롤."""
        holder = QWidget()
        holder.setFixedWidth(330)
        col = QVBoxLayout(holder)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(6)
        col.addWidget(_column_title("날짜 (빠른 순서)"))

        inner = QWidget()
        rows = QVBoxLayout(inner)
        rows.setContentsMargins(0, 0, 0, 0)
        rows.setSpacing(4)
        for i, c in enumerate(self._options):
            row = _OptionRow()
            row.setCursor(Qt.CursorShape.PointingHandCursor)
            row.setStyleSheet(
                f"_OptionRow{{background:{theme.CARD_TINT};border:1px solid "
                f"{theme.BORDER_SUBTLE};border-radius:{theme.RADIUS_MD}px}}"
                f"_OptionRow:hover{{background:{theme.PRIMARY_LIGHT}}}")
            box = QVBoxLayout(row)
            box.setContentsMargins(8, 6, 8, 6)
            box.setSpacing(2)
            cb = QCheckBox(option_label(c))
            # 예전에 자동 등록되던 날짜를 기본으로 — 날짜순 정렬 뒤에도
            # 그 후보를 그대로 따라간다(첫 줄이 아닐 수 있다)
            cb.setChecked(c is default if default is not None else i == 0)
            cb.setCursor(Qt.CursorShape.PointingHandCursor)
            cb.setStyleSheet(
                f"QCheckBox{{font-size:{theme.FONT_MD}px;color:{theme.TEXT};"
                f"font-weight:bold;background:transparent}}")
            box.addWidget(cb)
            ctx = source_context(c)
            if ctx:
                note = QLabel(ctx)
                note.setWordWrap(True)
                note.setStyleSheet(
                    f"color:{theme.SUBTLE};font-size:{theme.FONT_SM}px;"
                    f"background:transparent")
                box.addWidget(note)
            row.clicked.connect(
                lambda _i=i: self._on_row_clicked(_i))
            self.checks.append(cb)
            self._rows.append(row)
            rows.addWidget(row)
        rows.addStretch()

        scroll = QScrollArea()
        scroll.setWidget(inner)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea{background:transparent}"
                             "QScrollArea>QWidget>QWidget{background:transparent}")
        col.addWidget(scroll, stretch=1)
        return holder

    def _on_row_clicked(self, i: int) -> None:
        """줄을 누르면 체크를 토글하고, 오른쪽 본문에서 그 자리를 보여준다."""
        cb = self.checks[i]
        cb.setChecked(not cb.isChecked())
        self.show_in_body(i)

    # ── 오른쪽: 쪽지 내용 그대로 ─────────────────────────────
    def _body_column(self, body: str) -> QWidget:
        holder = QWidget()
        col = QVBoxLayout(holder)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(6)
        col.addWidget(_column_title("쪽지 내용"))

        # 후보가 들고 있는 원문을 그대로 — 글자수가 파서가 본 것과 같아야
        # source_span으로 짚는 자리가 어긋나지 않는다. 제목이 본문에 이미
        # 있으면 그만큼 앞이 잘리므로 offset을 받아 하이라이트에서 뺀다.
        text, self._body_pos = "", (lambda p: p)
        if self._options:
            text, self._body_pos = display_text(self._options[0])
        if not text:
            text = (body or "").replace("\r", " ")
            self._body_pos = lambda p: p
        self._body_text = text[:self.BODY_CHARS]

        view = QTextEdit()
        view.setPlainText(self._body_text)
        view.setReadOnly(True)
        view.setStyleSheet(
            f"QTextEdit{{background:{theme.CARD_TINT};border:1px solid "
            f"{theme.BORDER_SUBTLE};border-radius:{theme.RADIUS_MD}px;"
            f"padding:10px;font-size:{theme.FONT_MD}px;color:{theme.TEXT}}}")
        self.body_view = view
        col.addWidget(view, stretch=1)
        return holder

    def show_in_body(self, i: int) -> bool:
        """i번째 날짜가 적힌 자리로 스크롤하고 노랗게 표시한다."""
        view = getattr(self, "body_view", None)
        if view is None or not (0 <= i < len(self._options)):
            return False
        span = getattr(self._options[i], "source_span", None)
        if span is None:
            return False
        to_body = getattr(self, "_body_pos", None) or (lambda p: p)
        s, last = to_body(span[0]), to_body(span[1] - 1)
        if s is None or last is None:
            return False        # 화면에 없는 자리 (걸러낸 제목 줄 등)
        e = last + 1
        if not (0 <= s < e <= len(self._body_text)):
            return False        # 아주 긴 쪽지라 잘려 나간 뒤쪽 날짜
        cursor = view.textCursor()
        cursor.setPosition(s)
        cursor.setPosition(e, QTextCursor.MoveMode.KeepAnchor)
        view.setTextCursor(cursor)
        view.ensureCursorVisible()
        sel = QTextEdit.ExtraSelection()
        sel.cursor = cursor
        sel.format.setBackground(QColor(theme.SIGNATURE_SOFT))
        view.setExtraSelections([sel])
        return True

    def chosen(self) -> list:
        """체크된 날짜 후보들. 아무것도 안 골랐으면 빈 리스트(=오늘)."""
        return [c for c, cb in zip(self._options, self.checks) if cb.isChecked()]

    # ── 뜨는 자리: 바탕화면 한가운데 ─────────────────────────
    def showEvent(self, ev):
        """펭귄 옆이 아니라 화면 가운데에 띄운다 (2026-09-03 사용자 요청).

        펭귄은 보통 화면 가장자리에 있어서, 그 옆에 뜨면 창이 구석에 붙어
        본문을 읽기 불편했다.
        """
        super().showEvent(ev)
        self._center_on_screen()
        self.raise_()
        self.activateWindow()
        for i, cb in enumerate(self.checks):      # 미리 체크된 자리를 보여준다
            if cb.isChecked() and self.show_in_body(i):
                break

    def _center_on_screen(self) -> None:
        scr = None
        parent = self.parent()
        if parent is not None:
            try:
                from ui.widget_base import screen_at
                scr = screen_at(parent.frameGeometry().center())
            except Exception:
                scr = None
        scr = scr or self.screen() or QApplication.primaryScreen()
        if scr is None:
            return
        g = scr.availableGeometry()
        self.move(g.center().x() - self.width() // 2,
                  g.center().y() - self.height() // 2)


def _column_title(text: str) -> QLabel:
    lab = QLabel(text)
    lab.setStyleSheet(
        f"color:{theme.SUBTLE};font-size:{theme.FONT_SM}px;font-weight:bold")
    return lab


def ask_dates(owner, cands, msg, body: str = ""):
    """날짜 선택 모달을 띄운다. 취소면 None, 아니면 고른 후보 리스트."""
    options = date_options(cands)
    if not options:
        return []                          # 찾은 날짜가 없으면 물을 것도 없다
    # cands[0] = 이 기능이 생기기 전 자동으로 등록되던 날짜 → 기본 체크
    default = cands[0] if cands else None
    dlg = DatePickDialog(options, body, owner, default=default)
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
