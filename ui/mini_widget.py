# -*- coding: utf-8 -*-
"""미니 위젯 — 바탕화면 오른쪽 벽에 붙는 펭귄.

펭귄 클릭 → 세로 아이콘 바(➕ 일정등록 / 🗓 캘린더 / 💬 안내보정(옵션) / ⚙ 설정).
바깥을 클릭하면 자동으로 접힌다. 펭귄은 오른쪽 벽에 붙은 채 위아래로만 이동.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt, QPoint, QTimer
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QApplication, QFrame, QGraphicsDropShadowEffect, QLabel, QPushButton,
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
            f"#bar{{background:{theme.CARD};border-radius:14px;"
            f"border:1px solid {theme.BORDER}}}")
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(18)
        shadow.setOffset(0, 3)
        shadow.setColor(QColor(30, 136, 229, 70))
        card.setGraphicsEffect(shadow)
        outer.addWidget(card)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(6, 8, 6, 8)
        lay.setSpacing(4)

        buttons = [("bolt", "바로 등록 — 지금 보고 있는 쪽지를 즉시 등록 "
                    "(펭귄 더블클릭으로도 열려요)", owner.open_quick)]
        buttons.append(("inbox", "쪽지 목록 — 최근 쪽지에서 일정 고르기",
                        owner.open_review))
        # 캘린더·할일은 v0.11.0부터 바탕화면 위젯으로 이동 (관리는 설정에서)
        if owner.config.get("proof_enabled"):
            buttons.append(("chat", "문구 보정 (공개용 글)", owner.open_proof))
        buttons.append(("gear", "설정", owner.open_settings))

        for name, tip, handler in buttons:
            b = QPushButton()
            b.setIcon(icon(name))
            b.setIconSize(ICON_SIZE)
            b.setToolTip(tip)
            b.setFixedSize(40, 40)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setStyleSheet(
                f"QPushButton{{background:transparent;border:none;"
                f"border-radius:10px}}"
                f"QPushButton:hover{{background:{theme.PRIMARY_LIGHT}}}")
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
        self.penguin.setToolTip("쿨 일정 도우미\n클릭: 메뉴 / 더블클릭: 바로 등록 / "
                                "드래그: 이동 / 우클릭: 옵션")
        lay.addWidget(self.penguin)
        # 데모 모드 표시 뱃지
        self.demo_chip = QLabel("D", self)
        self.demo_chip.setFixedSize(16, 16)
        self.demo_chip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.demo_chip.setStyleSheet(
            "background:#f5a623;color:white;border-radius:8px;"
            "font-size:10px;font-weight:bold")
        self.demo_chip.setToolTip("데모 모드가 켜져 있습니다 (설정 → 데이터에서 끄기)")
        self.demo_chip.move(0, 0)
        self.resize(self.WIDTH, 54)
        self._bar: _IconBar | None = None
        self._moved = False
        self._click_timer = QTimer(self)
        self._click_timer.setSingleShot(True)
        self._click_timer.timeout.connect(self._open_bar)
        self.apply_config()

    def apply_config(self) -> None:
        super().apply_config()
        if hasattr(self, "demo_chip"):
            self.demo_chip.setVisible(bool(self.config.get("demo_mode")))

    def place_default(self) -> None:
        """오른쪽 벽 중앙에 도킹."""
        screen = QApplication.primaryScreen().availableGeometry()
        self.move(screen.right() - self.WIDTH, screen.center().y() - 27)

    def _open_bar(self) -> None:
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
            # 더블클릭과 구분: 잠깐 기다렸다가 메뉴를 연다
            self._click_timer.start(QApplication.doubleClickInterval())
        self._drag = None

    def mouseDoubleClickEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton:
            self._click_timer.stop()          # 단일클릭 메뉴 취소
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
