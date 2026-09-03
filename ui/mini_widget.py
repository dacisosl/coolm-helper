# -*- coding: utf-8 -*-
"""미니 위젯 — 바탕화면 어디에나 놓는 펭귄.

펭귄 클릭 → 세로 아이콘 바(📌 고정 / ✉ 쪽지 목록 / ⚙ 설정).
바깥을 클릭하면 자동으로 접힌다.
그 밖의 기능(⚡ 바로 등록·학사일정·문구 보정)은 우클릭 메뉴에 있다
(2026-09-03 사용자 요청 — 아이콘 바는 자주 쓰는 셋만).

이동 규칙 (2026-08-25 사용자 요청):
- 예전엔 오른쪽 벽에 붙은 채 위아래로만 움직였다 → **어디로든 자유롭게** 이동.
- 듀얼 모니터면 **다른 모니터로도** 끌고 갈 수 있다.
- 자꾸 건드려 움직이는 게 싫은 사람을 위해 **📌 위치 고정**을 아이콘 바에 뒀다.
- 놓은 자리는 config의 penguin_pos에 기억돼 다음 실행에도 그대로다.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt, QPoint
from PyQt6.QtWidgets import (
    QApplication, QFrame, QLabel, QPushButton,
    QVBoxLayout, QWidget,
)

from ui import theme
from ui.icons import icon, ICON_SIZE
from ui.penguin_icon import penguin_pixmap
from ui.widget_base import WidgetBase, clamp_to_screens, screen_at


class _IconBar(QWidget):
    """펭귄 옆에 뜨는 세로 아이콘 바. Popup이라 바깥 클릭 시 자동으로 닫힌다."""

    def __init__(self, owner: "MiniWidget"):
        super().__init__(None, Qt.WindowType.Popup
                         | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        card = QFrame()
        card.setObjectName("bar")
        card.setStyleSheet(
            f"#bar{{background:{theme.CARD};border-radius:{theme.RADIUS_LG}px;"
            f"border:none}}")
        card.setGraphicsEffect(theme.make_shadow(self, 2))
        outer.addWidget(card)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(6, 8, 6, 8)
        lay.setSpacing(4)

        # 아이콘은 셋만 — 📌 고정 / ✉ 쪽지 목록 / ⚙ 설정 (2026-09-03 사용자 요청).
        # ⚡ 바로 등록·학사일정·문구 보정은 펭귄 우클릭 메뉴로 옮겼다
        # (⚡는 펭귄 더블클릭이 여전히 가장 빠른 길이다).
        locked = owner.is_locked()
        buttons = [
            ("pin",
             "위치 고정 해제 — 다시 끌어서 옮길 수 있어요" if locked
             else "위치 고정 — 펭귄이 지금 자리에서 움직이지 않아요",
             owner.toggle_lock),
            ("mail", "쪽지 목록 — 최근 쪽지에서 일정 고르기", owner.open_review),
            # 캘린더·할일은 v0.11.0부터 바탕화면 위젯으로 이동 (관리는 설정에서)
            ("gear", "설정", owner.open_settings),
        ]

        # 메뉴 크기: 설정 → 일반 → 펭귄 위젯에서 보통(100)/크게(135) 선택
        from PyQt6.QtCore import QSize
        scale = int(owner.config.get("menu_scale", 100)) / 100
        btn_px = round(40 * scale)
        icon_px = round(22 * scale)
        for name, tip, handler in buttons:
            b = QPushButton()
            b.setIcon(icon(name, icon_px))
            b.setIconSize(QSize(icon_px, icon_px))
            b.setToolTip(tip)
            b.setFixedSize(btn_px, btn_px)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            # 고정 중인 📌는 켜져 있다는 게 한눈에 보이도록 배경을 남긴다
            on = name == "pin" and locked
            b.setStyleSheet(
                f"QPushButton{{background:"
                f"{theme.SIGNATURE_SOFT if on else 'transparent'};border:none;"
                f"border-radius:{theme.RADIUS_MD}px}}"
                f"QPushButton:hover{{background:{theme.PRIMARY_LIGHT}}}"
                f"QPushButton:pressed{{background:{theme.LIGHT_PRESSED}}}")
            b.clicked.connect(lambda _, h=handler: (self.close(), h()))
            lay.addWidget(b)
            if name == "pin":                 # 📌 아래로 얇은 구분선
                line = QFrame()
                line.setFixedHeight(1)
                line.setStyleSheet(f"background:{theme.BORDER_SUBTLE};border:none")
                lay.addWidget(line)


class MiniWidget(WidgetBase):
    WIDTH = 52
    BASE_PX = 46          # 펭귄 기본 크기(보통=100%)
    POS_KEY = "penguin_pos"   # 놓아둔 자리를 기억한다

    def penguin_px(self) -> int:
        """설정 → 일반 → 펭귄 크기(%)를 반영한 실제 픽셀 (2026-07-24)."""
        pct = int(self.config.get("penguin_scale", 140) or 140)
        return max(24, round(self.BASE_PX * max(50, min(300, pct)) / 100))

    def __init__(self, base_dir: str):
        super().__init__(base_dir)
        self.setWindowFlags(self.window_flags())
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(2, 2, 2, 2)
        self.penguin = QLabel()
        self.penguin.setPixmap(penguin_pixmap(self.base_dir, self.penguin_px()))
        self.penguin.setCursor(Qt.CursorShape.PointingHandCursor)
        self._mood = "base"
        lay.addWidget(self.penguin)
        # 데모 모드 표시 뱃지
        self.demo_chip = QLabel("D", self)
        self.demo_chip.setFixedSize(16, 16)
        self.demo_chip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.demo_chip.setStyleSheet(
            f"background:{theme.PRIMARY};color:white;border-radius:8px;"  # 8=16px의 반(원형)
            f"font-size:{theme.FONT_XS}px;font-weight:bold")
        self.demo_chip.setToolTip("데모 모드가 켜져 있습니다 (설정 → 데이터에서 끄기)")
        self.demo_chip.move(0, 0)
        self._resize_to_penguin()
        self._bar: _IconBar | None = None
        self._moved = False
        self._last_bar_open = 0.0
        self.apply_config()
        # 쿨쿠리 무드: 오늘 일정·밀린 일이 없으면 잠든다 (보면 안심)
        self._store_cb = self._update_mood
        self.store.subscribe(self._store_cb)
        self._update_mood()

    def _resize_to_penguin(self) -> None:
        """펭귄 크기에 맞춰 창 크기만 바꾼다 — 놓아둔 자리는 그대로.

        커지다 화면 밖으로 삐져나오는 경우에만 안쪽으로 밀어 넣는다.
        (예전엔 크기가 바뀔 때마다 오른쪽 벽으로 되돌아갔다.)
        """
        px = self.penguin_px()
        self.WIDTH = px + 6
        right = self.geometry().right()      # 커져도 오른쪽 모서리는 그대로
        self.resize(self.WIDTH, px + 8)
        if self.isVisible():
            self.move(clamp_to_screens(
                QPoint(right - self.width() + 1, self.y()), self.size()))

    def closeEvent(self, ev):
        self.store.unsubscribe(self._store_cb)
        super().closeEvent(ev)

    def _update_mood(self) -> None:
        from datetime import date
        mood = "base"
        if self.config.get("character_mode", True):
            overdue, today, _up = self.store.sections(date.today())
            # 완료 체크한 일은 '남은 할 일'이 아니다 — 다 끝내면 자야 한다
            # (예전엔 완료해도 오늘 목록에 남아 계속 깨어 있었음, 2026-07-26)
            todo_left = [e for e in today if not e.done]
            if not overdue and not todo_left:
                mood = "sleep"
        self._mood = mood
        self.penguin.setPixmap(
            penguin_pixmap(self.base_dir, self.penguin_px(), mood))
        self._resize_to_penguin()
        self._sync_tooltip()

    def apply_config(self) -> None:
        super().apply_config()
        if hasattr(self, "demo_chip"):
            self.demo_chip.setVisible(bool(self.config.get("demo_mode")))
        if hasattr(self, "_store_cb"):
            self._update_mood()      # 설정에서 캐릭터 모드 토글 즉시 반영

    def place_default(self) -> None:
        """처음 켤 때 자리 — 지금 있는 화면의 오른쪽 벽 중앙."""
        scr = screen_at(self.frameGeometry().center()) \
            or QApplication.primaryScreen()
        g = scr.availableGeometry()
        self.move(g.right() - self.WIDTH, g.center().y() - 27)

    def _ensure_on_screen(self) -> None:
        """해상도·모니터가 바뀌어도 실종되지 않게 — 있던 화면 안으로만 민다.

        보조 모니터에 둔 펭귄을 주 화면으로 끌고 오지 않는다. 모니터를
        아예 뽑아서 갈 곳이 없을 때만 가까운 화면으로 옮겨진다.
        """
        if not QApplication.instance().screens():
            return
        self.move(clamp_to_screens(self.pos(), self.size()))
        if getattr(self, "_in_tray", False):
            return               # 사용자가 트레이로 보낸 상태는 존중
        if not self.isVisible():
            self.show()
        self.raise_()

    def _open_bar(self) -> None:
        # 빠르게 두 번 열리면(=더블클릭이 팝업에 먹힌 경우) ⚡로 보낸다
        import time
        now = time.monotonic()
        if now - self._last_bar_open < \
                QApplication.doubleClickInterval() / 1000:
            if self._bar is not None and self._bar.isVisible():
                self._bar.close()
            self.open_quick()
            return
        self._last_bar_open = now
        # 메뉴를 여는 순간 ⚡용 데이터를 미리 데워둔다 (클릭 시 즉시 채움)
        import threading
        from parser import pipeline
        threading.Thread(target=pipeline.prefetch_quick,
                         args=(self.base_dir,), daemon=True).start()
        self._bar = _IconBar(self)
        self._bar.adjustSize()
        # 기본은 펭귄 왼쪽. 왼쪽에 자리가 없으면(화면 왼쪽 끝에 뒀을 때)
        # 오른쪽으로 펼친다 — 자유 이동이 되면서 생긴 경우 (2026-08-25)
        scr = screen_at(self.frameGeometry().center())
        g = scr.availableGeometry() if scr else None
        x = self.x() - self._bar.width() + 6
        if g is not None and x < g.left():
            x = self.x() + self.width() - 6
        y = self.y()
        if g is not None:
            y = min(max(g.top(), y), g.bottom() - self._bar.height())
            x = min(max(g.left(), x), g.right() - self._bar.width())
        self._bar.move(QPoint(x, y))
        self._bar.show()

    # ── 위치 고정 (📌) ──────────────────────────────────────
    def is_locked(self) -> bool:
        return bool(self.config.get("penguin_locked"))

    def toggle_lock(self) -> None:
        """📌 — 켜면 그 자리에 붙박이, 끄면 다시 자유롭게 끌 수 있다."""
        from parser import pipeline
        locked = not self.is_locked()
        self.config["penguin_locked"] = locked
        pipeline.save_config(self.base_dir, self.config)
        if locked:
            self.save_position()          # 고정한 자리를 확실히 남긴다
        self._sync_tooltip()
        from ui.quick_capture import _say
        _say(self, "이 자리에 고정했어요 — 📌 다시 누르면 풀려요" if locked
             else "이제 펭귄을 자유롭게 옮길 수 있어요")

    def _sync_tooltip(self) -> None:
        head = ("쿨쿠리가 자고 있어요 — 오늘은 일정이 없어요 💤\n"
                if self._mood == "sleep" else "COOL-비서\n")
        move = "이동: 📌 고정 중 (메뉴에서 해제)" if self.is_locked() \
            else "드래그: 이동 (다른 모니터로도)"
        self.penguin.setToolTip(
            f"{head}클릭: 메뉴(고정·쪽지·설정) / 더블클릭: ⚡ 바로 등록 / "
            f"{move} / 우클릭: 학사일정·옵션")

    # ── 마우스: 클릭=메뉴, 드래그=자유 이동, 우클릭=옵션 ──────
    def mousePressEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton:
            self._drag = ev.globalPosition().toPoint() - self.pos()
            self._moved = False

    def mouseMoveEvent(self, ev):
        # QPoint(0,0)은 거짓이라 'if self._drag'로 쓰면 펭귄 좌상단 모서리를
        # 정확히 집었을 때 드래그가 통째로 무시된다 (2026-08-25 발견)
        if self._drag is None or not (ev.buttons() & Qt.MouseButton.LeftButton):
            return
        if self.is_locked():
            return                       # 📌 고정 중엔 끌어도 꿈쩍 않는다
        # 화면 경계로 자르되 **커서가 있는 모니터**를 기준으로 — 그래야
        # 듀얼 모니터에서 경계에 걸리지 않고 옆 화면으로 넘어간다 (2026-08-25)
        cursor = ev.globalPosition().toPoint()
        self.move(clamp_to_screens(cursor - self._drag, self.size(), cursor))
        self._moved = True
        bubble = getattr(self, "_alert_bubble", None)
        if bubble is not None and bubble.isVisible():
            bubble.reposition()                      # 말풍선도 따라온다

    def mouseReleaseEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton and not self._moved:
            self._open_bar()                  # 딜레이 없이 즉시 메뉴
        elif self._moved:
            self.save_position()              # 놓은 자리를 기억한다
        self._drag = None

    def mouseDoubleClickEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton:
            if self._bar is not None and self._bar.isVisible():
                self._bar.close()
            self.open_quick()                 # 더블클릭 = ⚡ 바로 등록

    # 우클릭 → 투명도 선택지 (2026-07-25 사용자 요청)
    OPACITY_STEPS = ((100, "진하게 (100%)"), (85, "조금 흐리게 (85%)"),
                     (70, "흐리게 (70%)"), (55, "많이 흐리게 (55%)"),
                     (40, "아주 흐리게 (40%)"))

    def _set_opacity(self, pct: int) -> None:
        """펭귄 투명도를 바로 적용하고 저장한다."""
        from parser import pipeline
        self.config["widget_opacity"] = int(pct)
        self.setWindowOpacity(int(pct) / 100)
        pipeline.save_config(self.base_dir, self.config)

    def _show_capture_diagnosis(self) -> None:
        """'보고 있는 쪽지'를 왜 못 읽는지 확인해서 보여준다 (복사 가능)."""
        from PyQt6.QtWidgets import QMessageBox
        try:
            import capture
            text = capture.diagnose()
        except Exception as e:
            text = f"진단을 실행하지 못했습니다: {e}"
        box = QMessageBox(self)
        box.setWindowTitle("쪽지 읽기 진단")
        box.setText("쿨메신저에서 쪽지를 열어 둔 채로 확인한 결과입니다.")
        box.setDetailedText(text)          # 길어서 '자세히'에 — 복사해서 보내기 쉬움
        box.setStyleSheet(theme.BASE_QSS)
        box.exec()

    def contextMenuEvent(self, ev):
        from PyQt6.QtWidgets import QMenu
        menu = QMenu(self)
        menu.setStyleSheet(theme.BASE_QSS)
        # 아이콘 바에서 뺀 기능들이 여기 있다 (2026-09-03)
        act_quick = menu.addAction("⚡ 바로 등록 (펭귄 더블클릭)")
        act_neis = menu.addAction("🏫 학사일정 가져오기") \
            if self.config.get("neis_enabled", True) else None
        act_proof = menu.addAction("✏ 문구 보정 (공개용 글)") \
            if self.config.get("proof_enabled") else None
        menu.addSeparator()
        act_tray = menu.addAction("트레이로 보내기 (펭귄 숨기기)")
        act_detail = menu.addAction("상세 위젯으로 전환")
        # 투명도 — 고르면 바로 반영된다
        cur = int(self.config.get("widget_opacity", 100) or 100)
        sub = menu.addMenu("투명도")
        opacity_acts = {}
        for pct, label in self.OPACITY_STEPS:
            a = sub.addAction(label)
            a.setCheckable(True)
            a.setChecked(pct == cur)
            opacity_acts[a] = pct
        menu.addSeparator()
        act_diag = menu.addAction("쪽지 읽기 진단…")
        act_quit = menu.addAction("종료")
        chosen = menu.exec(ev.globalPos())
        if chosen == act_diag:
            self._show_capture_diagnosis()
            return
        if chosen is not None and chosen == act_quick:
            self.open_quick()
            return
        if act_neis is not None and chosen == act_neis:
            self.open_neis()
            return
        if act_proof is not None and chosen == act_proof:
            self.open_proof()
            return
        if chosen in opacity_acts:
            self._set_opacity(opacity_acts[chosen])
        elif chosen == act_tray:
            self.send_to_tray()
        elif chosen == act_detail:
            from parser import pipeline
            self.config["widget_style"] = "detail"
            pipeline.save_config(self.base_dir, self.config)
            self._swap_style("detail")
        elif chosen == act_quit:
            QApplication.instance().quit()
