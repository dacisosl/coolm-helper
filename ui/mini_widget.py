# -*- coding: utf-8 -*-
"""미니 위젯 — 바탕화면 오른쪽 벽에 붙는 펭귄.

펭귄 클릭 → 세로 아이콘 바(➕ 일정등록 / 🗓 캘린더 / 💬 안내보정(옵션) / ⚙ 설정).
바깥을 클릭하면 자동으로 접힌다. 펭귄은 오른쪽 벽에 붙은 채 위아래로만 이동.
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
from ui.widget_base import WidgetBase


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

        buttons = [("bolt", "바로 등록 — 지금 보고 있는 쪽지를 즉시 등록 "
                    "(펭귄 더블클릭으로도 열려요)", owner.open_quick)]
        buttons.append(("mail", "쪽지 목록 — 최근 쪽지에서 일정 고르기",
                        owner.open_review))
        # 캘린더·할일은 v0.11.0부터 바탕화면 위젯으로 이동 (관리는 설정에서)
        if owner.config.get("proof_enabled"):
            buttons.append(("chat", "문구 보정 (공개용 글)", owner.open_proof))
        buttons.append(("gear", "설정", owner.open_settings))

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
            b.setStyleSheet(
                f"QPushButton{{background:transparent;border:none;"
                f"border-radius:{theme.RADIUS_MD}px}}"
                f"QPushButton:hover{{background:{theme.PRIMARY_LIGHT}}}"
                f"QPushButton:pressed{{background:{theme.LIGHT_PRESSED}}}")
            b.clicked.connect(lambda _, h=handler: (self.close(), h()))
            lay.addWidget(b)


class MiniWidget(WidgetBase):
    WIDTH = 52

    def __init__(self, base_dir: str):
        super().__init__(base_dir)
        self.setWindowFlags(self.window_flags())
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(2, 2, 2, 2)
        self.penguin = QLabel()
        self.penguin.setPixmap(penguin_pixmap(self.base_dir, 46))
        self.penguin.setCursor(Qt.CursorShape.PointingHandCursor)
        self.penguin.setToolTip("COOL-비서\n클릭: 메뉴 / 더블클릭: 바로 등록 / "
                                "드래그: 이동 / 우클릭: 옵션")
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
        self.resize(self.WIDTH, 54)
        self._bar: _IconBar | None = None
        self._moved = False
        self._last_bar_open = 0.0
        self.apply_config()
        # 쿨쿠리 무드: 오늘 일정·밀린 일이 없으면 잠든다 (보면 안심)
        self._store_cb = self._update_mood
        self.store.subscribe(self._store_cb)
        self._update_mood()

    def closeEvent(self, ev):
        self.store.unsubscribe(self._store_cb)
        super().closeEvent(ev)

    def _update_mood(self) -> None:
        from datetime import date
        mood = "base"
        if self.config.get("character_mode", True):
            overdue, today, _up = self.store.sections(date.today())
            if not overdue and not today:
                mood = "sleep"
        self.penguin.setPixmap(penguin_pixmap(self.base_dir, 46, mood))
        self.penguin.setToolTip(
            ("쿨쿠리가 자고 있어요 — 오늘은 일정이 없어요 💤\n" if mood == "sleep"
             else "COOL-비서\n")
            + "클릭: 메뉴 / 더블클릭: 바로 등록 / 드래그: 이동 / 우클릭: 옵션")

    def apply_config(self) -> None:
        super().apply_config()
        if hasattr(self, "demo_chip"):
            self.demo_chip.setVisible(bool(self.config.get("demo_mode")))
        if hasattr(self, "_store_cb"):
            self._update_mood()      # 설정에서 캐릭터 모드 토글 즉시 반영

    def place_default(self) -> None:
        """오른쪽 벽 중앙에 도킹."""
        screen = QApplication.primaryScreen().availableGeometry()
        self.move(screen.right() - self.WIDTH, screen.center().y() - 27)

    def _ensure_on_screen(self) -> None:
        """해상도가 바뀌면 새 화면의 오른쪽 벽에 다시 도킹 (실종 방지)."""
        scr = QApplication.primaryScreen()
        if scr is None:
            return
        g = scr.availableGeometry()
        y = min(max(g.top(), self.y()), g.bottom() - self.height())
        self.move(g.right() - self.WIDTH, y)
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
        x = self.x() - self._bar.width() + 6
        y = min(self.y(), QApplication.primaryScreen().availableGeometry().bottom()
                - self._bar.height())
        self._bar.move(QPoint(x, y))
        self._bar.show()

    # ── 마우스: 클릭=메뉴, 드래그=상하 이동(벽에 고정), 우클릭=스타일 전환 ──
    def mousePressEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton:
            self._drag = ev.globalPosition().toPoint() - self.pos()
            self._moved = False

    def mouseMoveEvent(self, ev):
        if self._drag and ev.buttons() & Qt.MouseButton.LeftButton:
            target = ev.globalPosition().toPoint() - self._drag
            screen = QApplication.primaryScreen().availableGeometry()
            y = max(screen.top(), min(target.y(), screen.bottom() - self.height()))
            self.move(screen.right() - self.WIDTH, y)   # x는 벽에 고정
            self._moved = True
            bubble = getattr(self, "_alert_bubble", None)
            if bubble is not None and bubble.isVisible():
                bubble.reposition()                      # 말풍선도 따라온다

    def mouseReleaseEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton and not self._moved:
            self._open_bar()                  # 딜레이 없이 즉시 메뉴
        self._drag = None

    def mouseDoubleClickEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton:
            if self._bar is not None and self._bar.isVisible():
                self._bar.close()
            self.open_quick()                 # 더블클릭 = ⚡ 바로 등록

    def contextMenuEvent(self, ev):
        from PyQt6.QtWidgets import QMenu
        menu = QMenu(self)
        act_detail = menu.addAction("상세 위젯으로 전환")
        act_quit = menu.addAction("종료")
        chosen = menu.exec(ev.globalPos())
        if chosen == act_detail:
            from parser import pipeline
            self.config["widget_style"] = "detail"
            pipeline.save_config(self.base_dir, self.config)
            self._swap_style("detail")
        elif chosen == act_quit:
            QApplication.instance().quit()
