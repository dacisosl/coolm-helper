# -*- coding: utf-8 -*-
"""알림 포스트잇 — 시작할 때 뜨는 알림을 메모지 한 장에 모아 붙인다.

말풍선(AlertBubble)은 클릭할 때마다 한 줄씩 넘어가서, 급한 마감을 보기 전에
실수로 다 넘겨 버리기 쉬웠다. 포스트잇은 알림을 한눈에 펼쳐 두고
사용자가 ✕로 뗄 때까지 화면에 붙어 있는다.

설정 → 일반 → '알림'에서 끄고 켜며, 마감 며칠 전부터 알릴지도 거기서 고른다.
바탕화면 포스트잇(desk_note.py)과 달리 이 메모지는 저장되지 않는다 —
알림용이라 닫으면 그걸로 끝이고, 위치도 기억하지 않는다.
"""
from __future__ import annotations

from datetime import date

from PyQt6.QtCore import QPoint, Qt, QTimer
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget,
)

from ui import theme
from ui.alerts import highlight_urgency
from ui.calendar_view import WEEKDAY_KO
from ui.screens import clamp_to_screens

MAX_ITEMS = 6           # 이보다 많으면 메모지가 화면을 덮는다 — 나머지는 한 줄로
MARGIN = 24             # 앵커가 없을 때 화면 가장자리에서 띄울 여백


class AlertNote(QWidget):
    """노란 메모지 한 장. 끌어서 옮기고 ✕로 뗀다."""

    WIDTH = 272

    def __init__(self, alerts: list, anchor: QWidget | None = None,
                 on_open=None, on_dismiss=None, today: date | None = None):
        super().__init__(None, Qt.WindowType.Tool
                         | Qt.WindowType.FramelessWindowHint
                         | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.anchor = anchor
        self.on_open = on_open
        self.on_dismiss = on_dismiss
        self._drag: QPoint | None = None
        self._popped = False
        bg, border, fg = theme.postit_colors("yellow")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 10, 10, 12)    # 그림자 자리
        card = QFrame()
        self.card = card
        card.setObjectName("alertnote")
        card.setStyleSheet(
            theme.BASE_QSS
            + f"#alertnote{{background:{bg};"
              f"border:1px solid {border};"
              f"border-radius:{theme.RADIUS_LG}px}}")
        card.setGraphicsEffect(theme.make_shadow(self, 2))
        outer.addWidget(card)

        root = QVBoxLayout(card)
        self.root = root
        root.setContentsMargins(14, 10, 10, 12)
        root.setSpacing(8)

        # ── 머리글: 오늘 날짜 + 닫기 ─────────────────────────
        head = QHBoxLayout()
        head.setSpacing(6)
        d = today or date.today()
        when = QLabel(f"🐧 {d.month}월 {d.day}일 ({WEEKDAY_KO[d.weekday()]}) 알림")
        when.setStyleSheet(
            f"color:{fg};font-size:11px;font-weight:bold;background:transparent")
        head.addWidget(when)
        head.addStretch()
        close_btn = QPushButton("✕")
        close_btn.setToolTip("남은 알림 모두 떼기")
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet(
            f"QPushButton{{background:transparent;border:none;"
            f"color:{fg};font-size:12px;padding:0 4px}}"
            f"QPushButton:hover{{color:{theme.DANGER}}}")
        # 람다로 감싼다 — clicked는 checked(bool)를 넘겨서 그냥 연결하면
        # dismiss(remember=False)로 불려 기억을 안 하고 닫힌다
        close_btn.clicked.connect(lambda: self.dismiss())
        head.addWidget(close_btn)
        root.addLayout(head)

        # ── 알림 목록 (한 줄씩 따로 뗄 수 있다) ──────────────
        self._rows: list[tuple] = []        # [(alert, 줄 위젯, 구분선)]
        for i, alert in enumerate(alerts[:MAX_ITEMS]):
            line = QFrame()
            line.setFixedHeight(1)
            line.setStyleSheet(f"background:{border};border:none")
            line.setVisible(bool(i))        # 첫 줄 위에는 선을 긋지 않는다
            root.addWidget(line)

            row = QWidget()
            row.setObjectName("alertrow")
            row.setStyleSheet("#alertrow{background:transparent;border:none}")
            rl = QHBoxLayout(row)
            rl.setContentsMargins(0, 0, 0, 0)
            rl.setSpacing(6)
            item = QLabel()
            item.setTextFormat(Qt.TextFormat.RichText)
            item.setText(highlight_urgency(alert.text))
            item.setWordWrap(True)
            item.setStyleSheet(
                f"color:{theme.TEXT};font-size:12px;font-weight:bold;"
                f"background:transparent")
            rl.addWidget(item, stretch=1)
            drop = QPushButton("✕")
            drop.setToolTip("이 알림만 떼기")
            drop.setCursor(Qt.CursorShape.PointingHandCursor)
            drop.setFixedWidth(20)
            drop.setStyleSheet(
                f"QPushButton{{background:transparent;border:none;"
                f"color:{border};font-size:11px;padding:0}}"
                f"QPushButton:hover{{color:{theme.DANGER}}}")
            drop.clicked.connect(lambda _, a=alert: self.drop_item(a))
            rl.addWidget(drop, alignment=Qt.AlignmentFlag.AlignTop)
            root.addWidget(row)
            self._rows.append((alert, row, line))
        if len(alerts) > MAX_ITEMS:
            more = QLabel(f"… 그리고 {len(alerts) - MAX_ITEMS}건 더")
            more.setStyleSheet(
                f"color:{fg};font-size:11px;background:transparent")
            root.addWidget(more)

        # ── 바닥: 캘린더 바로가기 + 안내 ─────────────────────
        foot = QHBoxLayout()
        foot.setSpacing(6)
        if on_open is not None:
            cal = QPushButton("🗓 캘린더 열기")
            cal.setCursor(Qt.CursorShape.PointingHandCursor)
            cal.setStyleSheet(
                f"QPushButton{{background:transparent;border:1px solid {border};"
                f"border-radius:{theme.RADIUS_MD}px;color:{fg};"
                f"font-size:11px;padding:4px 10px}}"
                f"QPushButton:hover{{border-color:{theme.SIGNATURE};"
                f"color:{theme.SIGNATURE_DARK}}}")
            cal.clicked.connect(self._open_calendar)
            foot.addWidget(cal)
        foot.addStretch()
        hint = QLabel("끌어서 옮기기")
        hint.setStyleSheet(
            f"color:{theme.SUBTLE};font-size:10px;background:transparent")
        foot.addWidget(hint)
        root.addLayout(foot)

        self.setFixedWidth(self.WIDTH)
        self.adjustSize()

    # ── 자리잡기 ────────────────────────────────────────────
    def place(self) -> None:
        """펭귄 위쪽에 붙인다. 펭귄이 없으면 화면 오른쪽 아래."""
        anchor = self.anchor
        if anchor is not None and anchor.isVisible():
            x = anchor.x() + anchor.width() - self.width()
            y = anchor.y() - self.height() - 6
        else:
            from PyQt6.QtWidgets import QApplication
            app = QApplication.instance()
            scr = app.primaryScreen() if app else None
            if scr is None:
                return
            g = scr.availableGeometry()
            x = g.right() - self.width() - MARGIN
            y = g.bottom() - self.height() - MARGIN
        self.move(clamp_to_screens(QPoint(x, y), self.size()))

    # ── 동작 ────────────────────────────────────────────────
    def _open_calendar(self) -> None:
        if self.on_open is not None:
            try:
                self.on_open()
            except Exception:
                pass            # 캘린더가 안 열려도 알림은 조용히 닫힌다
        self.dismiss()

    def drop_item(self, alert) -> None:
        """줄 하나만 뗀다. 마지막 줄까지 떼면 메모지도 사라진다.

        숨기기(hide)가 아니라 레이아웃에서 **빼고 지운다**. 숨기기만 하면
        반투명 창 + 그림자 조합에서 옛 크기의 그림이 남아 글자가 겹쳐 보였다
        (2026-09-01 사용자 제보).
        """
        found = next(((a, r, l) for a, r, l in self._rows if a is alert), None)
        if found is None:
            return                          # 이미 뗀 줄 (중복 클릭)
        self._remember(alert)
        self._rows.remove(found)
        for w in found[1:]:                 # 줄 위젯 + 그 위 구분선
            self.root.removeWidget(w)
            w.hide()
            w.setParent(None)
            w.deleteLater()                 # 지금 이 클릭의 발신자가 이 안에 있다
        if not self._rows:
            self.dismiss(remember=False)    # 이미 한 줄씩 기억해 두었다
            return
        self._rows[0][2].hide()             # 맨 위로 올라온 줄의 구분선은 지운다
        self._resize_to_content()

    def _resize_to_content(self) -> None:
        """줄을 뺀 뒤 메모지를 다시 재고 그린다.

        아래 모서리를 고정한다 — 펭귄 위에 붙여 둔 메모지가 위로 달아나지
        않고, 끌어다 놓은 자리도 흐트러지지 않는다.
        """
        self._keep_bottom = self.y() + self.height()
        self.update()                   # 옛 그림을 남기지 않게 한 번 지운다
        # 크기 조절은 **다음 프레임으로 미룬다**. 줄을 빼자마자 재면 창의
        # sizeHint가 아직 옛 값이고, 억지로 줄여 놔도 레이아웃이 한 프레임 뒤에
        # 도로 늘린다. 그 어긋난 한 프레임에 옛 크기의 그림이 남아 글자가
        # 겹쳐 보였다 (2026-09-01 사용자 제보).
        QTimer.singleShot(0, self._apply_size)

    def _apply_size(self) -> None:
        """레이아웃이 정리된 뒤 실제 크기·위치를 맞춘다."""
        if getattr(self, "_closing", False) or not self._rows:
            return
        left = self.x()
        bottom = getattr(self, "_keep_bottom", self.y() + self.height())
        self.setMinimumHeight(0)        # 레이아웃이 걸어 둔 옛 최소 높이 풀기
        self.layout().activate()
        height = self.sizeHint().height()
        self.resize(self.width(), height)
        # 아래 모서리를 고정한다 — 펭귄 위에 붙여 둔 메모지가 위로 달아나지
        # 않고, 끌어다 놓은 자리도 흐트러지지 않는다
        self.move(clamp_to_screens(QPoint(left, bottom - height), self.size()))
        # 그림자(QGraphicsEffect)는 그린 결과를 캐시해서, 창이 줄어도 옛 크기의
        # 그림이 남는다. 새로 달아 캐시를 버리게 한다.
        self.card.setGraphicsEffect(theme.make_shadow(self, 2))
        self.card.update()
        self.update()

    def dismiss(self, remember: bool = True) -> None:
        """메모지를 뗀다. 남아 있던 줄은 '봤다'로 기억한다."""
        if remember:
            for alert, _row, _line in self._rows:
                self._remember(alert)
        from ui import motion
        motion.fade_out_close(self, ms=120)

    def _remember(self, alert) -> None:
        if self.on_dismiss is None:
            return
        try:
            self.on_dismiss(alert)
        except Exception:
            pass                # 기록 실패가 알림을 못 떼게 만들지 않는다

    # ── 드래그 이동 ─────────────────────────────────────────
    def mousePressEvent(self, ev) -> None:
        if ev.button() == Qt.MouseButton.LeftButton:
            self._drag = ev.globalPosition().toPoint() - self.pos()

    def mouseMoveEvent(self, ev) -> None:
        if self._drag is None:
            return
        cursor = ev.globalPosition().toPoint()
        self.move(clamp_to_screens(cursor - self._drag, self.size(), cursor))

    def mouseReleaseEvent(self, ev) -> None:
        self._drag = None

    def showEvent(self, ev):
        super().showEvent(ev)
        if not self._popped:            # 첫 등장만 살짝 올라오며 페이드
            self._popped = True
            from ui import motion
            motion.pop_in(self, ms=200, rise=8)
