# -*- coding: utf-8 -*-
"""학사일정 가져오기 — 나이스에서 우리 학교 일정을 골라 등록한다 (v2.1.0).

흐름: (처음 한 번) 학교 검색 → 저장 → 기간 고르기 → 불러오기 →
목록에서 체크한 것만 등록. 이미 등록한 일정은 '✓ 등록됨'으로 표시돼
두 번 들어가지 않는다.

네트워크 호출은 모두 백그라운드 스레드에서 — 창이 멈추지 않게.
"""
from __future__ import annotations

import threading
from datetime import date, datetime, timedelta

from PyQt6.QtCore import Qt, QObject, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QMessageBox, QPushButton, QScrollArea,
    QVBoxLayout, QWidget,
)

import neis
from parser import pipeline
from store.event_store import EventStore
from ui import motion, theme


class _Worker(QObject):
    """네트워크 호출 하나를 백그라운드에서 — 결과/오류를 시그널로."""
    done = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, fn, parent=None):
        super().__init__(parent)
        self._fn = fn

    def start(self) -> None:
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self) -> None:
        try:
            self.done.emit(self._fn())
        except neis.NeisError as e:
            self.failed.emit(str(e))
        except Exception as e:                     # 예상 못 한 오류도 창에 표시
            self.failed.emit(f"알 수 없는 오류: {type(e).__name__}")


class SchoolPickerDialog(motion.FadeInMixin, QDialog):
    """학교 이름으로 검색해 우리 학교를 고른다. 고른 학교는 설정에 저장."""

    def __init__(self, config: dict, parent=None):
        super().__init__(parent)
        self.config = config
        self.picked: neis.School | None = None
        self._schools: list[neis.School] = []
        self.setWindowTitle("학교 찾기")
        self.setWindowFlags(self.windowFlags()
                            | Qt.WindowType.WindowStaysOnTopHint)
        self.setStyleSheet(theme.BASE_QSS + f"QDialog{{background:{theme.BG}}}")
        self.resize(460, 460)

        lay = QVBoxLayout(self)
        lay.setSpacing(8)
        head = QLabel("우리 학교 찾기")
        head.setStyleSheet(theme.DIALOG_HEADER)
        lay.addWidget(head)

        tip = QLabel("학교 이름을 두 글자 이상 넣고 검색하세요. "
                     "(예: 가온초, 대전중앙)")
        tip.setWordWrap(True)
        tip.setStyleSheet(f"color:{theme.SUBTLE};font-size:{theme.FONT_SM}px")
        lay.addWidget(tip)

        bar = QHBoxLayout()
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("학교 이름")
        self.name_edit.setStyleSheet(theme.TITLE_EDIT)
        self.name_edit.returnPressed.connect(self._search)
        bar.addWidget(self.name_edit, stretch=1)
        self.search_btn = QPushButton("검색")
        self.search_btn.setStyleSheet(theme.PRIMARY_BTN)
        self.search_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.search_btn.clicked.connect(self._search)
        bar.addWidget(self.search_btn)
        lay.addLayout(bar)

        self.status = QLabel("")
        self.status.setWordWrap(True)
        self.status.setStyleSheet(
            f"color:{theme.SUBTLE};font-size:{theme.FONT_SM}px")
        lay.addWidget(self.status)

        self.list = QListWidget()
        self.list.setStyleSheet(
            f"QListWidget{{background:{theme.CARD};border:1px solid "
            f"{theme.BORDER};border-radius:{theme.RADIUS_LG}px;padding:4px}}")
        self.list.itemDoubleClicked.connect(lambda _: self._choose())
        lay.addWidget(self.list, stretch=1)

        btns = QHBoxLayout()
        btns.addStretch()
        cancel = QPushButton("취소")
        cancel.setStyleSheet(theme.TEXT_BTN)
        cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel.clicked.connect(self.reject)
        btns.addWidget(cancel)
        self.ok_btn = QPushButton("이 학교로 정하기")
        self.ok_btn.setStyleSheet(theme.PRIMARY_BTN)
        self.ok_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.ok_btn.setEnabled(False)
        self.ok_btn.clicked.connect(self._choose)
        btns.addWidget(self.ok_btn)
        lay.addLayout(btns)
        self.name_edit.setFocus()

    def _search(self) -> None:
        name = self.name_edit.text().strip()
        if len(name) < 2:
            self.status.setText("학교 이름을 두 글자 이상 넣어 주세요.")
            return
        self.search_btn.setEnabled(False)
        self.status.setText("찾는 중이에요…")
        self.list.clear()
        self.ok_btn.setEnabled(False)
        self._worker = _Worker(
            lambda: neis.search_schools(name, self.config), self)
        self._worker.done.connect(self._show_results)
        self._worker.failed.connect(self._show_error)
        self._worker.start()

    def _show_results(self, schools) -> None:
        self.search_btn.setEnabled(True)
        self._schools = list(schools)
        if not self._schools:
            self.status.setText("그런 이름의 학교를 못 찾았어요. "
                                "이름을 조금 다르게 넣어 보세요.")
            return
        self.status.setText(f"{len(self._schools)}곳을 찾았어요. "
                            f"우리 학교를 고르세요.")
        for s in self._schools:
            item = QListWidgetItem(
                f"{s.label()}\n{s.office_name}  {s.address}".strip())
            self.list.addItem(item)
        self.list.setCurrentRow(0)
        self.ok_btn.setEnabled(True)

    def _show_error(self, msg: str) -> None:
        self.search_btn.setEnabled(True)
        self.status.setText(msg)

    def _choose(self) -> None:
        idx = self.list.currentRow()
        if not (0 <= idx < len(self._schools)):
            return
        self.picked = self._schools[idx]
        self.accept()


class _EventRow(QFrame):
    """학사일정 한 건 — 체크박스 + 기간 + 행사명. 이미 등록된 건 회색."""

    def __init__(self, ev: neis.NeisEvent, registered: bool, parent=None):
        super().__init__(parent)
        self.ev = ev
        self.registered = registered
        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 6, 10, 6)
        lay.setSpacing(8)

        self.check = QCheckBox()
        self.check.setChecked(not registered)
        self.check.setEnabled(not registered)
        self.check.setToolTip("등록할 일정만 체크하세요")
        lay.addWidget(self.check)

        when = QLabel(ev.when_text())
        when.setFixedWidth(78)
        when.setStyleSheet(
            f"color:{theme.PRIMARY_DARK};font-size:{theme.FONT_SM}px;"
            f"font-weight:bold;background:transparent")
        lay.addWidget(when)

        title = QLabel(ev.title)
        title.setWordWrap(True)
        title.setStyleSheet(
            f"color:{theme.SUBTLE if registered else theme.TEXT};"
            f"font-size:{theme.FONT_MD}px;background:transparent")
        lay.addWidget(title, stretch=1)

        if registered:
            mark = QLabel("✓ 등록됨")
            mark.setStyleSheet(
                f"background:{theme.SUCCESS_FG};color:white;"
                f"border-radius:{theme.RADIUS_SM}px;padding:1px 8px;"
                f"font-size:{theme.FONT_XS}px;font-weight:bold")
            lay.addWidget(mark)
        self.setStyleSheet(
            f"_EventRow{{background:{theme.CARD_TINT if registered else theme.CARD};"
            f"border-radius:{theme.RADIUS_MD}px}}")

    def wanted(self) -> bool:
        return self.check.isChecked() and not self.registered


# 기간 선택지 — (표시 이름, 시작 오프셋(일), 끝 오프셋(일))
RANGES = [
    ("앞으로 3개월", 0, 90),
    ("앞으로 1년", 0, 365),
    ("이번 달", None, None),        # 특별 처리
    ("올해 전체", None, None),      # 특별 처리
]


def range_dates(label: str, today: date | None = None) -> tuple[date, date]:
    """기간 선택지 이름 → (시작일, 종료일). 창 밖에서도 쓰도록 순수 함수로."""
    today = today or date.today()
    if label == "이번 달":
        first = today.replace(day=1)
        nxt = (first + timedelta(days=32)).replace(day=1)
        return first, nxt - timedelta(days=1)
    if label == "올해 전체":
        return date(today.year, 1, 1), date(today.year, 12, 31)
    if label == "앞으로 1년":
        return today, today + timedelta(days=365)
    return today, today + timedelta(days=90)


class NeisScheduleDialog(motion.FadeInMixin, QDialog):
    """학사일정 불러오기 창 — 학교·기간을 정하고 골라서 등록한다."""

    def __init__(self, base_dir: str, config: dict, store: EventStore,
                 parent=None):
        super().__init__(parent)
        self.base_dir, self.config, self.store = base_dir, config, store
        self.rows: list[_EventRow] = []
        self.setWindowTitle("학사일정 가져오기")
        self.setWindowFlags(self.windowFlags()
                            | Qt.WindowType.WindowStaysOnTopHint)
        self.setStyleSheet(theme.BASE_QSS + f"QDialog{{background:{theme.BG}}}")
        self.resize(560, 560)

        lay = QVBoxLayout(self)
        lay.setSpacing(8)
        head = QLabel("🏫 학사일정 가져오기")
        head.setStyleSheet(theme.DIALOG_HEADER)
        lay.addWidget(head)

        tip = QLabel("나이스에 올라온 우리 학교 학사일정을 불러옵니다. "
                     "체크한 것만 등록돼요.")
        tip.setWordWrap(True)
        tip.setStyleSheet(f"color:{theme.SUBTLE};font-size:{theme.FONT_SM}px")
        lay.addWidget(tip)

        bar = QHBoxLayout()
        bar.setSpacing(6)
        self.school_label = QLabel()
        self.school_label.setStyleSheet(
            f"background:{theme.PRIMARY_LIGHT};color:{theme.PRIMARY_DARK};"
            f"border-radius:{theme.RADIUS_MD}px;padding:6px 12px;"
            f"font-size:{theme.FONT_MD}px;font-weight:bold")
        bar.addWidget(self.school_label, stretch=1)
        change = QPushButton("학교 바꾸기")
        change.setStyleSheet(theme.TEXT_BTN)
        change.setCursor(Qt.CursorShape.PointingHandCursor)
        change.clicked.connect(self.pick_school)
        bar.addWidget(change)
        lay.addLayout(bar)

        row2 = QHBoxLayout()
        row2.setSpacing(6)
        self.range_combo = QComboBox()
        for label, _a, _b in RANGES:
            self.range_combo.addItem(label)
        self.range_combo.setToolTip("가져올 기간")
        row2.addWidget(self.range_combo)
        self.holiday_cb = QCheckBox("휴업일·방학도 포함")
        self.holiday_cb.setToolTip(
            "끄면 토요휴업일·공휴일 같은 항목은 목록에서 빼요")
        row2.addWidget(self.holiday_cb)
        row2.addStretch()
        self.load_btn = QPushButton("불러오기")
        self.load_btn.setStyleSheet(theme.PRIMARY_BTN)
        self.load_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.load_btn.clicked.connect(self.load)
        row2.addWidget(self.load_btn)
        lay.addLayout(row2)

        self.status = QLabel("")
        self.status.setWordWrap(True)
        self.status.setStyleSheet(
            f"color:{theme.SUBTLE};font-size:{theme.FONT_SM}px")
        lay.addWidget(self.status)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            f"QScrollArea{{border:1px solid {theme.BORDER};"
            f"border-radius:{theme.RADIUS_LG}px;background:{theme.CARD}}}")
        inner = QWidget()
        inner.setStyleSheet("background:transparent")
        self.rows_lay = QVBoxLayout(inner)
        self.rows_lay.setContentsMargins(6, 6, 6, 6)
        self.rows_lay.setSpacing(4)
        scroll.setWidget(inner)
        lay.addWidget(scroll, stretch=1)

        btns = QHBoxLayout()
        self.all_btn = QPushButton("전체 선택 / 해제")
        self.all_btn.setStyleSheet(theme.TEXT_BTN)
        self.all_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.all_btn.clicked.connect(self._toggle_all)
        btns.addWidget(self.all_btn)
        btns.addStretch()
        close = QPushButton("닫기")
        close.setStyleSheet(theme.TEXT_BTN)
        close.setCursor(Qt.CursorShape.PointingHandCursor)
        close.clicked.connect(self.reject)
        btns.addWidget(close)
        self.save_btn = QPushButton("선택한 일정 등록")
        self.save_btn.setStyleSheet(theme.PRIMARY_BTN)
        self.save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.save_btn.setEnabled(False)
        self.save_btn.clicked.connect(self._register)
        btns.addWidget(self.save_btn)
        lay.addLayout(btns)

        self._sync_school()

    # ── 학교 ────────────────────────────────────────────────
    def school(self) -> neis.School | None:
        return neis.School.from_conf(self.config.get("neis_school"))

    def _sync_school(self) -> None:
        s = self.school()
        self.school_label.setText(s.label() if s else "학교를 먼저 정해 주세요")
        self.load_btn.setEnabled(s is not None)

    def pick_school(self) -> bool:
        dlg = SchoolPickerDialog(self.config, self)
        if not dlg.exec() or dlg.picked is None:
            return False
        self.config["neis_school"] = dlg.picked.to_conf()
        pipeline.save_config(self.base_dir, self.config)
        self._sync_school()
        return True

    # ── 불러오기 ────────────────────────────────────────────
    def load(self) -> None:
        school = self.school()
        if school is None:
            return
        start, end = range_dates(self.range_combo.currentText())
        skip = not self.holiday_cb.isChecked()
        self.load_btn.setEnabled(False)
        self.save_btn.setEnabled(False)
        self.status.setText("나이스에서 불러오는 중이에요…")
        self._clear_rows()
        self._worker = _Worker(
            lambda: neis.fetch_schedule(school, start, end, self.config,
                                        skip_holidays=skip), self)
        self._worker.done.connect(self._show_events)
        self._worker.failed.connect(self._show_error)
        self._worker.start()

    def _clear_rows(self) -> None:
        self.rows = []
        while self.rows_lay.count():
            item = self.rows_lay.takeAt(0)
            w = item.widget()
            if w is not None:
                w.hide()
                w.setParent(None)
                w.deleteLater()

    def _show_events(self, events) -> None:
        self.load_btn.setEnabled(True)
        events = list(events)
        if not events:
            self.status.setText("그 기간에는 올라온 학사일정이 없어요. "
                                "기간을 넓혀 보세요.")
            return
        done_refs = self.store.registered_refs()
        new_count = 0
        for ev in events:
            registered = ev.ref in done_refs
            row = _EventRow(ev, registered, self)
            self.rows.append(row)
            self.rows_lay.addWidget(row)
            new_count += 0 if registered else 1
        self.rows_lay.addStretch()
        self.status.setText(
            f"{len(events)}건을 불러왔어요 — 새 일정 {new_count}건. "
            f"체크한 것만 등록됩니다.")
        self.save_btn.setEnabled(new_count > 0)

    def _show_error(self, msg: str) -> None:
        self.load_btn.setEnabled(True)
        self.status.setText(msg)

    def _toggle_all(self) -> None:
        rows = [r for r in self.rows if not r.registered]
        turn_on = not all(r.check.isChecked() for r in rows) if rows else False
        for r in rows:
            r.check.setChecked(turn_on)

    # ── 등록 ────────────────────────────────────────────────
    def _register(self) -> None:
        wanted = [r.ev for r in self.rows if r.wanted()]
        if not wanted:
            self.status.setText("등록할 일정을 하나 이상 체크해 주세요.")
            return
        for ev in wanted:
            start = datetime.combine(ev.start, datetime.min.time())
            end = (datetime.combine(ev.end, datetime.min.time())
                   .replace(hour=23, minute=59)) if ev.end else None
            self.store.add(title=ev.title, start=start, end=end,
                           all_day=True, memo=ev.memo, source_ref=ev.ref)
        QMessageBox.information(
            self, "등록 완료",
            f"학사일정 {len(wanted)}건을 등록했어요.\n"
            f"캘린더와 바탕화면 위젯에서 바로 보입니다.")
        self.accept()


def open_neis_schedule(owner) -> None:
    """펭귄 메뉴·설정에서 부르는 진입점. 학교가 없으면 먼저 고르게 한다."""
    dlg = NeisScheduleDialog(owner.base_dir, owner.config, owner.store, owner)
    if dlg.school() is None and not dlg.pick_school():
        return                      # 학교 고르기를 취소하면 그냥 닫는다
    dlg.exec()
    owner.on_events_changed()
