# -*- coding: utf-8 -*-
"""상세 위젯 — 카드형 플로팅 런처 (쿨메신저 블루 테마)."""
from __future__ import annotations

from datetime import date

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QApplication, QFrame, QGraphicsDropShadowEffect, QHBoxLayout, QLabel,
    QPushButton, QVBoxLayout,
)

from ui import theme
from ui.icons import icon, ICON_SIZE
from ui.widget_base import WidgetBase


class FloatingWidget(WidgetBase):
    def __init__(self, base_dir: str):
        super().__init__(base_dir)
        self.setWindowFlags(self.window_flags())
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        card = QFrame()
        card.setObjectName("card")
        card.setStyleSheet(
            f"#card{{background:{theme.CARD};border-radius:16px;"
            f"border:1px solid {theme.BORDER}}}"
            f"QLabel{{background:transparent;font-family:'Malgun Gothic'}}")
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(24)
        shadow.setOffset(0, 4)
        shadow.setColor(QColor(30, 136, 229, 60))
        card.setGraphicsEffect(shadow)
        outer.addWidget(card)

        lay = QVBoxLayout(card)
        lay.setContentsMargins(14, 14, 14, 12)
        lay.setSpacing(8)

        title_row = QHBoxLayout()
        demo_suffix = " · 데모" if self.config.get("demo_mode") else ""
        title = QLabel("쿨 일정 도우미" + demo_suffix)
        title.setStyleSheet(
            f"color:{theme.PRIMARY_DARK};font-weight:bold;font-size:14px")
        title_row.addWidget(title, stretch=1)
        gear = QPushButton()
        gear.setIcon(icon("gear", 18))
        gear.setFixedSize(26, 26)
        gear.setStyleSheet(
            "QPushButton{background:transparent;border:none;border-radius:6px}"
            f"QPushButton:hover{{background:{theme.PRIMARY_LIGHT}}}")
        gear.setCursor(Qt.CursorShape.PointingHandCursor)
        gear.setToolTip("설정")
        gear.clicked.connect(self.open_settings)
        title_row.addWidget(gear)
        lay.addLayout(title_row)

        self.today_label = QLabel()
        self.today_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.today_label.setStyleSheet(
            f"background:{theme.PRIMARY_LIGHT};color:{theme.PRIMARY_DARK};"
            f"border-radius:9px;padding:5px;font-size:12px;font-weight:bold")
        lay.addWidget(self.today_label)

        secondary = (
            f"QPushButton{{background:{theme.CARD};color:{theme.PRIMARY_DARK};"
            f"border:1.5px solid {theme.PRIMARY};border-radius:8px;"
            f"padding:8px;font-weight:bold;font-size:13px;text-align:left}}"
            f"QPushButton:hover{{background:{theme.PRIMARY_LIGHT}}}")

        quick_btn = QPushButton(" 바로 등록")
        quick_btn.setIcon(icon("bolt"))
        quick_btn.setIconSize(ICON_SIZE)
        quick_btn.setStyleSheet(theme.PRIMARY_BTN + "QPushButton{font-size:13px}")
        quick_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        quick_btn.setToolTip("쿨메신저에서 지금 보고 있는 쪽지를 즉시 등록")
        quick_btn.clicked.connect(self.open_quick)
        lay.addWidget(quick_btn)

        add_btn = QPushButton(" 쪽지 목록")
        add_btn.setIcon(icon("inbox"))
        add_btn.setIconSize(ICON_SIZE)
        add_btn.setStyleSheet(secondary)
        add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_btn.setToolTip("최근 쪽지에서 일정 고르기")
        add_btn.clicked.connect(self.open_review)
        lay.addWidget(add_btn)

        cal_btn = QPushButton(" 캘린더 · 할일")
        cal_btn.setIcon(icon("calendar"))
        cal_btn.setIconSize(ICON_SIZE)
        cal_btn.setStyleSheet(secondary)
        cal_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cal_btn.clicked.connect(self.open_calendar)
        lay.addWidget(cal_btn)

        if self.config.get("proof_enabled"):
            proof_btn = QPushButton(" 문구 보정")
            proof_btn.setIcon(icon("chat"))
            proof_btn.setIconSize(ICON_SIZE)
            proof_btn.setStyleSheet(secondary.replace(theme.PRIMARY, theme.BORDER, 1))
            proof_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            proof_btn.clicked.connect(self.open_proof)
            lay.addWidget(proof_btn)

        quit_btn = QPushButton("종료")
        quit_btn.setStyleSheet(
            f"QPushButton{{background:transparent;color:{theme.SUBTLE};"
            f"border:none;padding:4px;font-size:11px}}"
            f"QPushButton:hover{{color:{theme.DANGER}}}")
        quit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        quit_btn.clicked.connect(QApplication.instance().quit)
        lay.addWidget(quit_btn)

        self.refresh_badge()
        self.resize(190, 205)
        self.apply_config()
        self.store.subscribe(self.refresh_badge)

    def refresh_badge(self) -> None:
        n = len(self.store.on_date(date.today()))
        self.today_label.setText(f"오늘 일정 {n}건")

    def on_events_changed(self) -> None:
        self.refresh_badge()

    def contextMenuEvent(self, ev):
        from PyQt6.QtWidgets import QMenu
        menu = QMenu(self)
        act_mini = menu.addAction("미니 위젯으로 전환")
        chosen = menu.exec(ev.globalPos())
        if chosen == act_mini:
            from parser import pipeline
            self.config["widget_style"] = "mini"
            pipeline.save_config(self.base_dir, self.config)
            self._swap_style("mini")
