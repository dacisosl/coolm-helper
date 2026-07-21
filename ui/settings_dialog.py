# -*- coding: utf-8 -*-
"""설정 모달 — 계정 / 데이터 / 개인정보 / 위젯 4개 섹션."""
from __future__ import annotations

import os
import shutil

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox, QDialog, QHBoxLayout, QLabel, QLineEdit, QMessageBox,
    QPushButton, QRadioButton, QSlider, QSpinBox, QTabWidget, QVBoxLayout,
    QWidget,
)

from parser import pipeline
from parser.pii_detector import load_students
from store.event_store import EventStore
from ui import theme
from version import APP_VERSION


def _section_label(text: str) -> QLabel:
    lab = QLabel(text)
    lab.setStyleSheet(
        f"color:{theme.SUBTLE};font-size:11px;font-weight:bold;margin-top:6px")
    return lab


class SettingsDialog(QDialog):
    def __init__(self, base_dir: str, config: dict, store: EventStore,
                 parent=None):
        super().__init__(parent)
        self.base_dir = base_dir
        self.config = config
        self.store = store
        self.setWindowTitle("설정")
        self.resize(460, 430)
        self.setStyleSheet(theme.BASE_QSS)

        lay = QVBoxLayout(self)
        tabs = QTabWidget()
        tabs.addTab(self._general_tab(), "일반")
        tabs.addTab(self._account_tab(), "계정")
        tabs.addTab(self._data_tab(), "데이터")
        tabs.addTab(self._privacy_tab(), "개인정보")
        lay.addWidget(tabs)

        btns = QHBoxLayout()
        btns.addStretch()
        cancel = QPushButton("취소")
        cancel.clicked.connect(self.reject)
        btns.addWidget(cancel)
        save = QPushButton("저장")
        save.setStyleSheet(theme.PRIMARY_BTN)
        save.clicked.connect(self._save)
        btns.addWidget(save)
        lay.addLayout(btns)

    # ── 계정: 저장 모드 (선택제 저장) ─────────────────────────
    def _account_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.addWidget(_section_label("저장 모드"))

        self.local_radio = QRadioButton("로컬 모드 (기본) — 일정이 이 PC에만 저장됩니다")
        self.google_radio = QRadioButton(
            "구글 연동 모드 — 등록 시 구글 캘린더에도 올릴 수 있습니다\n"
            "     (휴대폰에서 일정을 보고 싶은 분께 추천)")
        if self.config.get("google_sync_enabled"):
            self.google_radio.setChecked(True)
        else:
            self.local_radio.setChecked(True)
        lay.addWidget(self.local_radio)
        lay.addWidget(self.google_radio)

        try:
            from calendar_sync import google_sync
            ready = google_sync.is_available()
            token = os.path.exists(google_sync.TOKEN_PATH)
        except Exception:
            ready, token = False, False
        status = ("연동 준비 완료" if ready else
                  "구글 연동을 쓰려면 최초 1회 설정이 필요합니다 (구글연동설정.md 참고)")
        if token:
            status += " · 구글 계정 연결됨"
        info = QLabel(status)
        info.setWordWrap(True)
        info.setStyleSheet(f"color:{theme.SUBTLE};font-size:12px")
        lay.addWidget(info)

        row = QHBoxLayout()
        guide_btn = QPushButton("설정 안내 열기")
        guide_btn.clicked.connect(self._open_google_guide)
        row.addWidget(guide_btn)
        if token:
            unlink = QPushButton("구글 계정 연결 해제")
            unlink.clicked.connect(self._unlink_google)
            row.addWidget(unlink)
        row.addStretch()
        lay.addLayout(row)

        note = QLabel("어느 모드든 구글로 나가는 정보는 사용자가 확인한 "
                      "일정 제목과 일시뿐입니다. 쪽지 원문은 나가지 않습니다.")
        note.setWordWrap(True)
        note.setStyleSheet(
            f"background:{theme.PRIMARY_LIGHT};color:{theme.PRIMARY_DARK};"
            f"border-radius:8px;padding:8px;font-size:11px")
        lay.addWidget(note)

        lay.addWidget(_section_label("안내문구 보정 — Gemini API 키"))
        self.proof_key_edit = QLineEdit(self.config.get("proof_api_key", ""))
        self.proof_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.proof_key_edit.setPlaceholderText(
            "AIza… 로 시작하는 키를 붙여넣으세요 (이 PC에만 저장됩니다)")
        lay.addWidget(self.proof_key_edit)
        key_row = QHBoxLayout()
        key_guide = QPushButton("무료 키 발급 페이지 열기")
        key_guide.clicked.connect(lambda: __import__("webbrowser").open(
            "https://aistudio.google.com/apikey"))
        key_row.addWidget(key_guide)
        key_row.addStretch()
        lay.addLayout(key_row)
        key_note = QLabel("보정 기능은 입력창에 직접 붙여넣은 글만 전송합니다. "
                          "예전에 쪽지 등으로 공유된 적 있는 키는 쓰지 말고 "
                          "새 키를 발급받으세요.")
        key_note.setWordWrap(True)
        key_note.setStyleSheet(f"color:{theme.SUBTLE};font-size:11px")
        lay.addWidget(key_note)
        lay.addStretch()
        return w

    # ── 데이터: 쪽지 개수·저장 위치·업데이트 ──────────────────
    def _data_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.addWidget(_section_label("쪽지 가져오기"))
        row = QHBoxLayout()
        row.addWidget(QLabel("기본으로 가져올 최근 쪽지 개수"))
        self.count_spin = QSpinBox()
        self.count_spin.setRange(5, 200)
        self.count_spin.setValue(int(self.config.get("recent_count", 10)))
        row.addWidget(self.count_spin)
        row.addStretch()
        lay.addLayout(row)

        lay.addWidget(_section_label("저장된 데이터"))
        n = len(self.store.all())
        lay.addWidget(QLabel(f"등록된 일정: {n}건 (이 PC의 store 폴더)"))
        open_btn = QPushButton("데이터 폴더 열기")
        open_btn.clicked.connect(lambda: os.startfile(
            os.path.join(self.base_dir, self.config.get("store_dir", "store"))))
        lay.addWidget(open_btn, alignment=Qt.AlignmentFlag.AlignLeft)

        lay.addWidget(_section_label("지난 일정 정리"))
        arch_row = QHBoxLayout()
        arch_row.addWidget(QLabel("지난 지"))
        from PyQt6.QtWidgets import QComboBox
        self.archive_combo = QComboBox()
        for label, days in (("보관 안 함", 0), ("30일", 30),
                            ("90일 (기본)", 90), ("180일", 180)):
            self.archive_combo.addItem(label, days)
        cur = int(self.config.get("auto_archive_days", 90))
        idx = {0: 0, 30: 1, 90: 2, 180: 3}.get(cur, 2)
        self.archive_combo.setCurrentIndex(idx)
        arch_row.addWidget(self.archive_combo)
        arch_row.addWidget(QLabel("넘은 일정은 보관함 파일로 이동"))
        arch_row.addStretch()
        lay.addLayout(arch_row)

        lay.addWidget(_section_label("데모 모드 (테스트)"))
        self.demo_cb = QCheckBox("데모 모드 — 내장된 가짜 쪽지로 기능 체험 "
                                 "(쿨메신저가 없어도 동작)")
        self.demo_cb.setChecked(bool(self.config.get("demo_mode", False)))
        lay.addWidget(self.demo_cb)
        self.demo_del_btn = QPushButton(
            f"데모로 등록한 일정 모두 삭제 ({self.store.demo_count()}건)")
        self.demo_del_btn.clicked.connect(self._delete_demo_events)
        self.demo_del_btn.setEnabled(self.store.demo_count() > 0)
        lay.addWidget(self.demo_del_btn, alignment=Qt.AlignmentFlag.AlignLeft)

        lay.addWidget(_section_label("업데이트"))
        lay.addWidget(QLabel(f"현재 버전: v{APP_VERSION}"))
        self.auto_update_cb = QCheckBox("시작할 때 새 버전 자동 확인")
        self.auto_update_cb.setChecked(
            bool(self.config.get("auto_update_check", True)))
        lay.addWidget(self.auto_update_cb)
        check_btn = QPushButton("지금 업데이트 확인")
        check_btn.clicked.connect(self._check_update_now)
        lay.addWidget(check_btn, alignment=Qt.AlignmentFlag.AlignLeft)
        lay.addStretch()
        return w

    # ── 개인정보 ────────────────────────────────────────────
    def _privacy_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.addWidget(_section_label("학생 명단 (이름 탐지용)"))
        path = self.config.get("students_path", "students.txt")
        if not os.path.isabs(path):
            path = os.path.join(self.base_dir, path)
        self._students_path = path
        n = len(load_students(path))
        status = f"등록된 학생 {n}명" if n else "명단 파일이 아직 없습니다"
        self.students_label = QLabel(status)
        lay.addWidget(self.students_label)
        btn = QPushButton("명단 파일 열기(없으면 만들기)")
        btn.clicked.connect(self._open_students)
        lay.addWidget(btn, alignment=Qt.AlignmentFlag.AlignLeft)

        lay.addWidget(_section_label("탐지 정책"))
        policy = QLabel(
            "· 전화번호·주민번호·이름(호칭/명단)을 찾아 빨간 글씨로 표시합니다\n"
            "· 자동으로 지우지 않습니다 — 지울지는 등록 전에 직접 결정합니다\n"
            "· 쪽지 원문과 명단은 이 PC 밖으로 나가지 않습니다")
        policy.setWordWrap(True)
        policy.setStyleSheet(f"color:{theme.TEXT};font-size:12px")
        lay.addWidget(policy)
        lay.addStretch()
        return w

    # ── 일반: 위젯 스타일 + 기능 온오프 ──────────────────────
    def _general_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.addWidget(_section_label("위젯 스타일"))
        self.style_mini = QRadioButton(
            "미니 (기본) — 오른쪽 벽의 펭귄, 클릭하면 메뉴가 나옵니다")
        self.style_detail = QRadioButton("상세 — 버튼이 다 보이는 카드형")
        if self.config.get("widget_style", "mini") == "detail":
            self.style_detail.setChecked(True)
        else:
            self.style_mini.setChecked(True)
        lay.addWidget(self.style_mini)
        lay.addWidget(self.style_detail)

        lay.addWidget(_section_label("시작"))
        import autostart
        self.autostart_cb = QCheckBox("Windows 시작 시 자동 실행")
        self.autostart_cb.setChecked(autostart.is_enabled())
        lay.addWidget(self.autostart_cb)

        lay.addWidget(_section_label("위젯 동작"))
        self.on_top_cb = QCheckBox("항상 다른 창 위에 표시")
        self.on_top_cb.setChecked(
            bool(self.config.get("widget_always_on_top", True)))
        lay.addWidget(self.on_top_cb)
        row = QHBoxLayout()
        row.addWidget(QLabel("투명도"))
        self.opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.opacity_slider.setRange(50, 100)
        self.opacity_slider.setValue(int(self.config.get("widget_opacity", 100)))
        row.addWidget(self.opacity_slider)
        self.opacity_label = QLabel(f"{self.opacity_slider.value()}%")
        self.opacity_slider.valueChanged.connect(
            lambda v: self.opacity_label.setText(f"{v}%"))
        row.addWidget(self.opacity_label)
        lay.addLayout(row)

        lay.addWidget(_section_label("알림 — 마감 며칠 전에 알려드릴까요?"))
        alert_row = QHBoxLayout()
        self.alert_cbs = {}
        current_days = set(self.config.get("alert_days", [3, 1]))
        for d in (7, 3, 1):
            cb = QCheckBox(f"{d}일 전")
            cb.setChecked(d in current_days)
            self.alert_cbs[d] = cb
            alert_row.addWidget(cb)
        alert_row.addStretch()
        lay.addLayout(alert_row)

        lay.addWidget(_section_label("기능"))
        core = QCheckBox("일정 등록 (기본 기능)")
        core.setChecked(True)
        core.setEnabled(False)
        lay.addWidget(core)
        self.fav_cb = QCheckBox("즐겨찾기 보관함 — 일정 등록 창의 ☆ 버튼 + "
                                "캘린더 창의 ★ 탭")
        self.fav_cb.setChecked(bool(self.config.get("favorites_enabled", False)))
        lay.addWidget(self.fav_cb)
        self.proof_cb = QCheckBox("안내문구 보정 — 공개용 글을 AI로 다듬기 "
                                  "(계정 탭에서 API 키 필요)")
        self.proof_cb.setChecked(bool(self.config.get("proof_enabled", False)))
        lay.addWidget(self.proof_cb)

        lay.addWidget(_section_label("바탕화면 위젯"))
        from parser.pipeline import desk_conf
        self.desk_cbs = {}
        for kind, label in (("simple", "할일 간단판 — 밀린 일·오늘·앞으로"),
                            ("weekly", "주간 일정 — 이번 주 한눈에"),
                            ("monthly", "월간 달력 — 한 달 배지 달력")):
            cb = QCheckBox(label)
            cb.setChecked(bool(desk_conf(self.config, kind).get("enabled")))
            lay.addWidget(cb)
            self.desk_cbs[kind] = cb
        desk_hint = QLabel("드래그로 옮기고 모서리를 끌어 크기 조절 · "
                           "우클릭으로 투명도/항상 위 · 포스트잇은 캘린더에서 📌")
        desk_hint.setStyleSheet("color:#78859a;font-size:11px")
        desk_hint.setWordWrap(True)
        lay.addWidget(desk_hint)
        lay.addStretch()
        return w

    # ── 동작 ────────────────────────────────────────────────
    def _open_google_guide(self) -> None:
        for name in ("구글연동설정.md", os.path.join("calendar_sync", "SETUP.md")):
            p = os.path.join(self.base_dir, name)
            if os.path.exists(p):
                os.startfile(p)
                return
        QMessageBox.information(self, "안내", "설정 안내 파일을 찾지 못했습니다.")

    def _unlink_google(self) -> None:
        try:
            from calendar_sync import google_sync
            if os.path.exists(google_sync.TOKEN_PATH):
                os.remove(google_sync.TOKEN_PATH)
            QMessageBox.information(self, "완료", "구글 계정 연결을 해제했습니다.")
        except Exception as e:
            QMessageBox.warning(self, "오류", str(e))

    def _open_students(self) -> None:
        path = self._students_path
        if not os.path.exists(path):
            example = os.path.join(self.base_dir, "students.txt.example")
            if os.path.exists(example):
                shutil.copyfile(example, path)
            else:
                with open(path, "w", encoding="utf-8") as f:
                    f.write("# 한 줄에 학생 이름 하나씩 적으세요.\n")
        os.startfile(path)

    def _delete_demo_events(self) -> None:
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

    def _save(self) -> None:
        self.config["widget_style"] = ("detail" if self.style_detail.isChecked()
                                       else "mini")
        self.config["favorites_enabled"] = self.fav_cb.isChecked()
        self.config["proof_enabled"] = self.proof_cb.isChecked()
        self.config["alert_days"] = sorted(
            (d for d, cb in self.alert_cbs.items() if cb.isChecked()),
            reverse=True) or [3, 1]
        self.config["auto_archive_days"] = self.archive_combo.currentData()
        self.config["proof_api_key"] = self.proof_key_edit.text().strip()
        from parser.pipeline import desk_conf
        for kind, cb in self.desk_cbs.items():
            desk_conf(self.config, kind)["enabled"] = cb.isChecked()
        import autostart
        try:
            if self.autostart_cb.isChecked():
                autostart.enable(self.base_dir)
            else:
                autostart.disable()
        except OSError as e:
            QMessageBox.warning(self, "자동 시작", f"설정하지 못했습니다.\n{e}")
        self.config["google_sync_enabled"] = self.google_radio.isChecked()
        self.config["recent_count"] = self.count_spin.value()
        self.config["demo_mode"] = self.demo_cb.isChecked()
        self.config["auto_update_check"] = self.auto_update_cb.isChecked()
        self.config["widget_always_on_top"] = self.on_top_cb.isChecked()
        self.config["widget_opacity"] = self.opacity_slider.value()
        pipeline.save_config(self.base_dir, self.config)
        self.accept()
