# -*- coding: utf-8 -*-
"""설정 모달 — 사이드바형(일반 / 구글 연동 / 데이터 / 업데이트).

디자인 원칙 (2026-07-21 리마스터):
- 왼쪽 사이드바 + 오른쪽 카드 섹션 (트렌디한 설정 창 레이아웃)
- 제목 옆 긴 설명 금지 — 제목 + ? 아이콘(툴팁)으로 통일
- 바탕화면 위젯 토글은 체크 즉시 실시간 반영
"""
from __future__ import annotations

import os
import threading

from PyQt6.QtCore import Qt, QObject, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QMessageBox, QPushButton, QRadioButton, QSpinBox,
    QStackedWidget, QVBoxLayout, QWidget,
)

from parser import pipeline
from store.event_store import EventStore
from ui import motion, theme
from version import APP_VERSION

_SETTINGS_QSS = f"""
QListWidget#side {{
    background:{theme.BG}; border:none; border-radius:{theme.RADIUS_LG}px;
    padding:6px; font-size:{theme.FONT_MD}px; outline:0; }}
QListWidget#side::item {{
    padding:10px 12px; border-radius:{theme.RADIUS_MD}px; margin:2px 0;
    color:{theme.TEXT}; }}
QListWidget#side::item:hover {{ background:{theme.PRIMARY_LIGHT}; }}
QListWidget#side::item:selected {{
    background:{theme.PRIMARY}; color:white; font-weight:bold; }}
QFrame[scard="true"] {{
    background:{theme.CARD}; border:1px solid {theme.BORDER_SUBTLE};
    border-radius:{theme.RADIUS_LG}px; }}
"""


def _help_dot(tip: str):
    """제목 옆 ? 아이콘 — 누르면 설명 말풍선 (호버 툴팁 겸용)."""
    from ui.help_dot import HelpDot
    return HelpDot(tip)


class _GoogleLoginWorker(QObject):
    """구글 OAuth 로그인을 백그라운드에서 — 브라우저 로그인 동안 창이 안 굳게."""
    done = pyqtSignal()
    failed = pyqtSignal(str)

    def start(self) -> None:
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self) -> None:
        try:
            from calendar_sync import google_sync
            google_sync.ensure_login()
            self.done.emit()
        except Exception as e:
            self.failed.emit(str(e))


def _card(title: str, tip: str = "") -> tuple[QFrame, QVBoxLayout]:
    """섹션 카드: 제목(+? 아이콘) 아래에 내용을 쌓는다."""
    frame = QFrame()
    frame.setProperty("scard", True)
    lay = QVBoxLayout(frame)
    lay.setContentsMargins(14, 10, 14, 12)
    lay.setSpacing(8)
    head = QHBoxLayout()
    lab = QLabel(title)
    lab.setStyleSheet(
        f"font-size:13px;font-weight:bold;color:{theme.TEXT};border:none")
    head.addWidget(lab)
    if tip:
        head.addWidget(_help_dot(tip))
    head.addStretch()
    lay.addLayout(head)
    return frame, lay


def _check(text: str, checked: bool, tip: str = "") -> tuple[QCheckBox, QWidget]:
    """짧은 라벨 체크박스 + ? 아이콘 한 줄."""
    row = QWidget()
    row.setStyleSheet("background:transparent;border:none")
    h = QHBoxLayout(row)
    h.setContentsMargins(0, 0, 0, 0)
    h.setSpacing(6)
    cb = QCheckBox(text)
    cb.setChecked(checked)
    h.addWidget(cb)
    if tip:
        cb.setToolTip(tip)
        h.addWidget(_help_dot(tip))
    h.addStretch()
    return cb, row


class SettingsDialog(motion.FadeInMixin, QDialog):
    def __init__(self, base_dir: str, config: dict, store: EventStore,
                 parent=None):
        super().__init__(parent)
        self.base_dir = base_dir
        self.config = config
        self.store = store
        self.setWindowTitle("설정")
        self.resize(600, 520)
        self.setStyleSheet(theme.BASE_QSS + _SETTINGS_QSS
                           + f"QDialog{{background:{theme.CARD}}}")

        outer = QVBoxLayout(self)
        body = QHBoxLayout()
        body.setSpacing(12)
        self.side = QListWidget()
        self.side.setObjectName("side")
        self.side.setFixedWidth(128)
        self.stack = QStackedWidget()
        for name, page in (("일반", self._general_page()),
                           ("구글 연동", self._google_page()),
                           ("데이터", self._data_page()),
                           ("업데이트", self._update_page())):
            self.side.addItem(name)
            self.stack.addWidget(page)
        self.side.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.side.setCurrentRow(0)
        body.addWidget(self.side)
        body.addWidget(self.stack, stretch=1)
        outer.addLayout(body)

        btns = QHBoxLayout()
        btns.addStretch()
        cancel = QPushButton("취소")
        cancel.clicked.connect(self.reject)
        btns.addWidget(cancel)
        save = QPushButton("저장")
        save.setStyleSheet(theme.PRIMARY_BTN)
        save.clicked.connect(self._save)
        btns.addWidget(save)
        outer.addLayout(btns)

    @staticmethod
    def _page() -> tuple[QWidget, QVBoxLayout]:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)
        return w, lay

    # ── 일반 ────────────────────────────────────────────────
    def _general_page(self) -> QWidget:
        w, lay = self._page()

        card, c = _card("펭귄 위젯",
                        "화면에 떠 있는 작은 도우미의 모양을 고릅니다.")
        # 미니/상세 — 라디오 대신 칩 두 개 중 하나를 고르는 방식
        chip_row = QHBoxLayout()
        chip_row.setSpacing(8)
        self.style_chips = {}
        self._style_pick = self.config.get("widget_style", "mini")

        def _style_chip(key: str, label: str, tip: str) -> QPushButton:
            b = QPushButton(label)
            b.setCheckable(True)
            b.setToolTip(tip)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setStyleSheet(
                f"QPushButton{{background:{theme.CARD_TINT};color:{theme.SUBTLE};"
                f"border:1px solid {theme.BORDER};border-radius:{theme.RADIUS_LG}px;"
                f"padding:6px 16px;font-weight:bold}}"
                f"QPushButton:hover{{border-color:{theme.PRIMARY}}}"
                f"QPushButton:checked{{background:{theme.PRIMARY};color:white;"
                f"border-color:{theme.PRIMARY}}}")
            b.clicked.connect(lambda _, k=key: self._pick_style(k))
            self.style_chips[key] = b
            return b

        chip_row.addWidget(_style_chip(
            "mini", "🐧 미니", "오른쪽 벽의 작은 펭귄 — 클릭하면 메뉴 (기본)"))
        chip_row.addWidget(_style_chip(
            "detail", "🗂 상세", "버튼이 다 보이는 카드형"))
        chip_row.addStretch()
        c.addLayout(chip_row)
        self._pick_style(self._style_pick)
        lay.addWidget(card)

        card, c = _card("기능")
        try:
            import autostart
            auto_on = autostart.is_enabled()
        except Exception:       # Windows 밖(테스트 환경 등)
            auto_on = False
        self.autostart_cb, row = _check(
            "Windows 시작 시 자동 실행", auto_on,
            "컴퓨터를 켜면 프로그램이 자동으로 시작됩니다.")
        c.addWidget(row)
        self.char_cb, row = _check(
            "캐릭터 변환 모드 (쿨쿠리)",
            bool(self.config.get("character_mode", True)),
            "상황에 따라 펭귄 '쿨쿠리'의 모습이 바뀝니다.\n"
            "오늘 일정이 없으면 잠들고(안심!), 간편 등록에서는 받아 적고,\n"
            "밀린 일 알림에서는 깜짝 놀라요.")
        c.addWidget(row)
        self.fav_cb, row = _check(
            "즐겨찾기 보관함", bool(self.config.get("favorites_enabled")),
            "자주 쓰는 문구를 저장해 두는 보관함.\n"
            "일정 등록 창의 ☆ 버튼과 캘린더 창의 ★ 탭이 생깁니다.")
        c.addWidget(row)
        self.proof_cb, row = _check(
            "안내문구 보정 (AI)", bool(self.config.get("proof_enabled")),
            "가정통신문 등 공개할 글을 AI로 다듬는 기능.\n"
            "아래에 API 키를 넣어야 동작합니다.")
        c.addWidget(row)
        # 보정 켜면 나타나는 API 키 영역 (Gemini 또는 OpenRouter)
        self.proof_area = QWidget()
        self.proof_area.setStyleSheet("background:transparent;border:none")
        pa = QVBoxLayout(self.proof_area)
        pa.setContentsMargins(22, 0, 0, 0)
        pa.setSpacing(6)
        prow = QHBoxLayout()
        self.prov_gemini = QRadioButton("Gemini 키")
        self.prov_gemini.setToolTip("구글 AI 스튜디오에서 무료 발급 (AIza…)")
        self.prov_openrouter = QRadioButton("OpenRouter 키")
        self.prov_openrouter.setToolTip(
            "여러 AI를 한 키로 쓰는 서비스 (sk-or-…)")
        if self.config.get("proof_provider", "gemini") == "openrouter":
            self.prov_openrouter.setChecked(True)
        else:
            self.prov_gemini.setChecked(True)
        prow.addWidget(self.prov_gemini)
        prow.addWidget(self.prov_openrouter)
        prow.addStretch()
        pa.addLayout(prow)
        self.proof_key_edit = QLineEdit(self.config.get("proof_api_key", ""))
        self.proof_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.proof_key_edit.setToolTip(
            "키는 이 PC의 config.json에만 저장됩니다.\n"
            "예전에 쪽지 등으로 공유된 적 있는 키는 쓰지 말고 새로 발급받으세요.")
        pa.addWidget(self.proof_key_edit)
        key_btn = QPushButton("무료 키 발급 페이지 열기")
        key_btn.setStyleSheet(theme.TEXT_BTN)
        key_btn.clicked.connect(self._open_key_page)
        pa.addWidget(key_btn, alignment=Qt.AlignmentFlag.AlignLeft)
        c.addWidget(self.proof_area)
        self.proof_cb.toggled.connect(self._sync_proof_area)
        self.prov_gemini.toggled.connect(self._sync_proof_area)
        self._sync_proof_area()
        lay.addWidget(card)

        card, c = _card("바탕화면 위젯",
                        "체크하면 바로 화면에 나타납니다.\n"
                        "위젯의 🔧으로 크기·투명도·글씨를 조절하고,\n"
                        "포스트잇은 캘린더에서 일정을 열고 📌를 누르세요.")
        from parser.pipeline import desk_conf
        for kind, label, tip in (
                ("planner", "캘린더 · 할 일",
                 "달력과 그날 일정 목록이 한 몸인 위젯"),
                ("simple", "할 일 보드",
                 "지난 일 | 오늘 | 앞으로 — 3열 투두리스트"),
                ("today", "오늘 할 일 목록",
                 "오늘 것만 한 줄씩 체크하는 심플 투두"),
                ("weekly", "주간 일정", "이번 주를 한눈에")):
            cb, row = _check(label,
                             bool(desk_conf(self.config, kind).get("enabled")),
                             tip)
            # 체크하는 순간 실시간 적용 — 저장 버튼을 기다리지 않는다
            cb.toggled.connect(lambda on, k=kind: self._apply_desk_widget(k, on))
            c.addWidget(row)
        lay.addWidget(card)
        lay.addStretch()
        return w

    def _sync_proof_area(self) -> None:
        self.proof_area.setVisible(self.proof_cb.isChecked())
        if self.prov_gemini.isChecked():
            self.proof_key_edit.setPlaceholderText(
                "AIza… 로 시작하는 Gemini 키를 붙여넣으세요")
        else:
            self.proof_key_edit.setPlaceholderText(
                "sk-or-… 로 시작하는 OpenRouter 키를 붙여넣으세요")

    def _open_key_page(self) -> None:
        import webbrowser
        webbrowser.open("https://aistudio.google.com/apikey"
                        if self.prov_gemini.isChecked()
                        else "https://openrouter.ai/settings/keys")

    # ── 구글 연동 ───────────────────────────────────────────
    def _google_state(self) -> tuple[bool, bool]:
        """(연동 준비됨 = 열쇠 파일·라이브러리, 구글 계정 로그인됨)"""
        try:
            from calendar_sync import google_sync
            return (google_sync.is_available(),
                    os.path.exists(google_sync.token_path()))
        except Exception:
            return False, False

    def _google_page(self) -> QWidget:
        w, lay = self._page()
        card, c = _card("구글 캘린더 연동",
                        "연동하면 일정 등록 때 '구글에도 등록'을 고를 수 있어\n"
                        "휴대폰에서도 일정이 보입니다. 구글로 나가는 정보는\n"
                        "확인한 일정 제목과 일시뿐 — 쪽지 원문은 나가지 않아요.")
        self._google_on = bool(self.config.get("google_sync_enabled"))

        # 칩 버튼 하나로 연동/해제 — 누르면 구글 로그인 창이 바로 뜬다
        self.google_chip = QPushButton()
        self.google_chip.setCursor(Qt.CursorShape.PointingHandCursor)
        self.google_chip.clicked.connect(self._google_chip_clicked)
        c.addWidget(self.google_chip, alignment=Qt.AlignmentFlag.AlignLeft)

        self.google_status = QLabel()
        self.google_status.setWordWrap(True)
        self.google_status.setStyleSheet(
            f"color:{theme.SUBTLE};font-size:12px;border:none")
        c.addWidget(self.google_status)

        lay.addWidget(card)
        lay.addStretch()
        self._refresh_google_chip()
        return w

    def _refresh_google_chip(self) -> None:
        ready, token = self._google_state()
        chip = self.google_chip
        chip.setEnabled(True)
        if self._google_on and token:
            chip.setText("✓  구글 캘린더 연동됨")
            chip.setStyleSheet(
                f"QPushButton{{background:{theme.SUCCESS_BG};"
                f"color:{theme.SUCCESS_FG};border:1.5px solid "
                f"{theme.SUCCESS_BORDER};border-radius:{theme.RADIUS_LG}px;"
                f"padding:7px 16px;font-weight:bold}}"
                f"QPushButton:hover{{border-color:{theme.SUCCESS_FG}}}")
            self.google_status.setText("칩을 누르면 연동이 해제됩니다.")
        else:
            chip.setText("🔗  구글 캘린더 연동하기")
            chip.setStyleSheet(
                f"QPushButton{{background:{theme.PRIMARY_LIGHT};"
                f"color:{theme.PRIMARY_DARK};border:1.5px solid "
                f"{theme.PRIMARY};border-radius:{theme.RADIUS_LG}px;"
                f"padding:7px 16px;font-weight:bold}}"
                f"QPushButton:hover{{background:{theme.PRIMARY};color:white}}"
                f"QPushButton:pressed{{background:{theme.PRIMARY_DARK};"
                f"color:white}}")
            self.google_status.setText(
                "누르면 구글 로그인 창이 열리고, 로그인하면 바로 연동됩니다."
                if ready else
                "앱을 최신 버전으로 업데이트하면 쓸 수 있어요.")

    def _google_chip_clicked(self) -> None:
        from parser import pipeline as _pl
        ready, token = self._google_state()
        if self._google_on and token:                     # 연동 해제
            if QMessageBox.question(self, "확인",
                                    "구글 캘린더 연동을 해제할까요?") \
                    != QMessageBox.StandardButton.Yes:
                return
            self._unlink_google(quiet=True)
            self._google_on = False
            self.config["google_sync_enabled"] = False
            _pl.save_config(self.base_dir, self.config)
            self._refresh_google_chip()
            return
        if not ready:      # 구글 부품이 없는 옛 빌드 (v1.4 미만)
            QMessageBox.information(
                self, "업데이트가 필요해요",
                "이 버전에는 구글 연동 부품이 없습니다.\n"
                "앱을 최신 버전으로 업데이트한 뒤 다시 눌러주세요.")
            return
        if token:                                         # 이미 로그인됨 → 켜기만
            self._google_on = True
            self.config["google_sync_enabled"] = True
            _pl.save_config(self.base_dir, self.config)
            self._refresh_google_chip()
            return
        # 로그인 필요 → 브라우저 열고 백그라운드 대기
        self.google_chip.setEnabled(False)
        self.google_chip.setText("브라우저에서 구글 로그인 중…")
        self.google_status.setText(
            "브라우저 창에서 로그인해 주세요. 로그인하면 자동으로 이어집니다.")
        self._login_worker = _GoogleLoginWorker(self)
        self._login_worker.done.connect(self._google_login_done)
        self._login_worker.failed.connect(self._google_login_failed)
        self._login_worker.start()

    def _google_login_done(self) -> None:
        from parser import pipeline as _pl
        self._google_on = True
        self.config["google_sync_enabled"] = True
        _pl.save_config(self.base_dir, self.config)
        self._refresh_google_chip()
        from ui.toast import show_toast
        show_toast(self, "구글 캘린더와 연동됐어요")

    def _google_login_failed(self, err: str) -> None:
        self._refresh_google_chip()
        QMessageBox.warning(
            self, "연동 실패",
            f"구글 로그인이 완료되지 않았습니다.\n{err}")

    # ── 데이터 ──────────────────────────────────────────────
    def _data_page(self) -> QWidget:
        w, lay = self._page()

        card, c = _card("쪽지 가져오기",
                        "일정 등록 창을 열 때 기본으로 불러올 최근 쪽지 개수.")
        row = QHBoxLayout()
        row.addWidget(QLabel("최근 쪽지"))
        self.count_spin = QSpinBox()
        self.count_spin.setRange(5, 200)
        self.count_spin.setValue(int(self.config.get("recent_count", 10)))
        row.addWidget(self.count_spin)
        row.addWidget(QLabel("개"))
        row.addStretch()
        c.addLayout(row)
        lay.addWidget(card)

        card, c = _card("저장된 데이터",
                        "일정은 전부 이 PC의 store 폴더에 저장됩니다.")
        c.addWidget(QLabel(f"등록된 일정: {len(self.store.all())}건"))
        open_btn = QPushButton("데이터 폴더 열기")
        open_btn.clicked.connect(lambda: os.startfile(
            os.path.join(self.base_dir, self.config.get("store_dir", "store"))))
        c.addWidget(open_btn, alignment=Qt.AlignmentFlag.AlignLeft)
        arch_row = QHBoxLayout()
        arch_row.addWidget(QLabel("지난 일정 정리"))
        arch_row.addWidget(_help_dot(
            "지난 지 오래된 일정을 보관함 파일로 옮겨 목록을 가볍게 유지합니다."))
        self.archive_combo = QComboBox()
        for label, days in (("보관 안 함", 0), ("30일 뒤", 30),
                            ("90일 뒤 (기본)", 90), ("180일 뒤", 180)):
            self.archive_combo.addItem(label, days)
        cur = int(self.config.get("auto_archive_days", 90))
        self.archive_combo.setCurrentIndex({0: 0, 30: 1, 90: 2, 180: 3}.get(cur, 2))
        arch_row.addWidget(self.archive_combo)
        arch_row.addStretch()
        c.addLayout(arch_row)
        lay.addWidget(card)

        card, c = _card("데모 모드",
                        "내장된 가짜 쪽지로 기능을 체험합니다.\n"
                        "쿨메신저가 없어도 동작해요.")
        self.demo_cb, row = _check("데모 모드 켜기",
                                   bool(self.config.get("demo_mode", False)))
        c.addWidget(row)
        self.demo_del_btn = QPushButton(
            f"데모로 등록한 일정 모두 삭제 ({self.store.demo_count()}건)")
        self.demo_del_btn.clicked.connect(self._delete_demo_events)
        self.demo_del_btn.setEnabled(self.store.demo_count() > 0)
        c.addWidget(self.demo_del_btn, alignment=Qt.AlignmentFlag.AlignLeft)
        lay.addWidget(card)
        lay.addStretch()
        return w

    # ── 업데이트 ────────────────────────────────────────────
    def _update_page(self) -> QWidget:
        w, lay = self._page()
        card, c = _card("업데이트",
                        "새 버전이 나오면 프로그램을 켤 때 안내가 뜨고,\n"
                        "'예'를 누르면 자동으로 설치됩니다.")
        ver = QLabel(f"현재 버전  v{APP_VERSION}")
        ver.setStyleSheet(
            f"font-size:15px;font-weight:bold;color:{theme.PRIMARY_DARK};"
            f"border:none")
        c.addWidget(ver)
        self.auto_update_cb, row = _check(
            "시작할 때 새 버전 자동 확인",
            bool(self.config.get("auto_update_check", True)),
            "확인만 하고, 설치 여부는 항상 사용자가 결정합니다.")
        c.addWidget(row)
        check_btn = QPushButton("지금 업데이트 확인")
        check_btn.setStyleSheet(theme.PRIMARY_BTN)
        check_btn.clicked.connect(self._check_update_now)
        c.addWidget(check_btn, alignment=Qt.AlignmentFlag.AlignLeft)
        lay.addWidget(card)
        lay.addStretch()
        return w

    # ── 동작 ────────────────────────────────────────────────
    def _apply_desk_widget(self, kind: str, on: bool) -> None:
        parent = self.parent()
        if parent is not None and hasattr(parent, "apply_desk_widget"):
            parent.apply_desk_widget(kind, on)

    def _unlink_google(self, quiet: bool = False) -> None:
        try:
            from calendar_sync import google_sync
            tok = google_sync.token_path()
            if os.path.exists(tok):
                os.remove(tok)
            if not quiet:
                QMessageBox.information(self, "완료",
                                        "구글 계정 연결을 해제했습니다.")
        except Exception as e:
            QMessageBox.warning(self, "오류", str(e))

    def _delete_demo_events(self) -> None:
        n = self.store.demo_count()
        if QMessageBox.question(
                self, "확인",
                f"데모로 등록한 일정 {n}건을 모두 삭제할까요?") \
                != QMessageBox.StandardButton.Yes:
            return
        n = self.store.remove_demo()
        self.demo_del_btn.setText("데모로 등록한 일정 모두 삭제 (0건)")
        self.demo_del_btn.setEnabled(False)
        QMessageBox.information(self, "완료", f"데모 일정 {n}건을 삭제했습니다.")
        parent = self.parent()
        if parent is not None:
            parent.refresh_badge()
            if getattr(parent, "cal_win", None):
                parent.cal_win.refresh()

    def _check_update_now(self) -> None:
        import updater
        url = self.config.get("update_url", "")
        if not url:
            QMessageBox.information(
                self, "업데이트", "업데이트 서버가 아직 설정되지 않았습니다.\n"
                "(배포자가 update_url을 설정하면 활성화됩니다)")
            return
        info = updater.check_for_update(url)
        if not info:
            QMessageBox.information(self, "업데이트",
                                    f"현재 최신 버전입니다. (v{APP_VERSION})")
            return
        self.parent()._offer_update(info)   # 플로팅 위젯의 공용 업데이트 안내 사용

    def _pick_style(self, key: str) -> None:
        """펭귄 위젯 스타일 칩 — 둘 중 하나만 눌린 상태로 유지."""
        self._style_pick = key
        for k, b in self.style_chips.items():
            b.setChecked(k == key)

    def _save(self) -> None:
        self.config["widget_style"] = self._style_pick
        self.config["character_mode"] = self.char_cb.isChecked()
        self.config["favorites_enabled"] = self.fav_cb.isChecked()
        self.config["proof_enabled"] = self.proof_cb.isChecked()
        self.config["proof_provider"] = ("openrouter"
                                         if self.prov_openrouter.isChecked()
                                         else "gemini")
        self.config["proof_api_key"] = self.proof_key_edit.text().strip()
        self.config["alert_days"] = [3, 1]   # 알림은 기본값 고정
        self.config["auto_archive_days"] = self.archive_combo.currentData()
        # 바탕화면 위젯은 체크 즉시 반영·저장되므로 여기서는 건드리지 않는다
        try:
            import autostart
            if self.autostart_cb.isChecked():
                autostart.enable(self.base_dir)
            else:
                autostart.disable()
        except ImportError:
            pass                # Windows 밖(테스트 환경 등)
        except OSError as e:
            QMessageBox.warning(self, "자동 시작", f"설정하지 못했습니다.\n{e}")
        self.config["google_sync_enabled"] = self._google_on
        self.config["recent_count"] = self.count_spin.value()
        self.config["demo_mode"] = self.demo_cb.isChecked()
        self.config["auto_update_check"] = self.auto_update_cb.isChecked()
        # 화면 전환 애니메이션은 설정 항목에서 제외 — 항상 기본값(켬)
        self.config["animations_enabled"] = True
        from ui import motion
        motion.set_enabled(True)
        pipeline.save_config(self.base_dir, self.config)
        self.accept()
