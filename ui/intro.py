# -*- coding: utf-8 -*-
"""설치 후 첫 실행 인트로 — 화면 가운데에서 쿨비서가 등장해 오른쪽 벽으로 날아간다.

three.js/웹엔진 없이 Qt 애니메이션만 사용한다(용량 0, 시작 빠름).
- 1단계: 화면 중앙에 펭귄이 통통 튀며 등장 (OutBack) + 말풍선 인사
- 2단계: 말풍선 문구가 바뀌며 살짝 흔들림
- 3단계: 오른쪽 벽(도킹 위치)으로 작아지며 날아가 사라짐
아무 곳이나 클릭하거나 [건너뛰기]를 누르면 즉시 끝난다.
애니메이션이 꺼져 있으면(motion.is_enabled False) 아예 재생하지 않는다.
"""
from __future__ import annotations

from PyQt6.QtCore import (
    QEasingCurve, QParallelAnimationGroup, QPoint, QPropertyAnimation, QRect,
    QSequentialAnimationGroup, Qt, QTimer,
)
from PyQt6.QtWidgets import (
    QApplication, QGraphicsOpacityEffect, QLabel, QPushButton, QWidget,
)

from ui import motion, theme
from ui.penguin_icon import penguin_pixmap

BIG = 300          # 가운데 등장 크기(px)
DOCK = 70          # 오른쪽 벽에 붙을 때 크기(px)
LINE1 = "안녕하세요, 저는 <b>쿨비서</b>예요"
LINE2 = "쪽지를 <b>일정</b>으로 만들어 드릴게요"
LINE3 = "여기 오른쪽에 있을게요!"
FIRST_LINES = (LINE1, LINE2, LINE3)

# 업데이트 후 마무리 응원 멘트 (버전마다 하나씩 골라 쓴다)
CHEERS = (
    "오늘도 힘내세요, 제가 도울게요!",
    "오늘 하루도 순조롭길 바라요!",
    "바쁜 하루, 일정은 제게 맡기세요!",
    "언제나 여기서 기다릴게요!",
)


def update_lines(version: str, notes: str = "") -> list[str]:
    """업데이트 인트로 문구: 버전 알림 → 변경점 1~2줄 → 응원."""
    lines = [f"<b>v{version}</b>로 업데이트했어요!"]
    for raw in (notes or "").splitlines():
        item = raw.strip().lstrip("-•").strip()
        if item:
            lines.append(item if len(item) <= 42 else item[:41] + "…")
        if len(lines) >= 3:          # 너무 길지 않게 최대 2줄만
            break
    if len(lines) == 1:
        lines.append("자잘한 개선이 담겨 있어요")
    lines.append(CHEERS[sum(ord(c) for c in version) % len(CHEERS)])
    return lines


class IntroOverlay(QWidget):
    """전체 화면 투명 오버레이 위에서 펭귄이 움직인다."""

    def __init__(self, base_dir: str, on_done=None, parent=None,
                 lines=FIRST_LINES):
        super().__init__(parent)
        self.base_dir = base_dir
        self._on_done = on_done
        self._done = False
        self._lines = list(lines) or list(FIRST_LINES)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint
                            | Qt.WindowType.Tool
                            | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        scr = QApplication.primaryScreen()
        self._geo = scr.availableGeometry() if scr else QRect(0, 0, 1280, 800)
        self.setGeometry(self._geo)

        # 펭귄 — 원본을 크게 받아 두고 라벨 크기에 맞춰 늘린다(계단현상 방지)
        self.peng = QLabel(self)
        self.peng.setPixmap(penguin_pixmap(base_dir, 512, "base"))
        self.peng.setScaledContents(True)
        self.peng.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._peng_fx = QGraphicsOpacityEffect(self.peng)
        self.peng.setGraphicsEffect(self._peng_fx)
        self._peng_fx.setOpacity(0.0)

        # 말풍선
        self.bubble = QLabel(self._lines[0], self)
        self.bubble.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.bubble.setTextFormat(Qt.TextFormat.RichText)
        self.bubble.setStyleSheet(
            f"background:{theme.CARD};color:{theme.TEXT};"
            f"border-radius:{theme.RADIUS_LG}px;padding:14px 22px;"
            f"font-size:{theme.FONT_LG}px;font-weight:bold")
        self.bubble.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._bub_fx = QGraphicsOpacityEffect(self.bubble)
        self.bubble.setGraphicsEffect(self._bub_fx)
        self._bub_fx.setOpacity(0.0)

        self.skip = QPushButton("건너뛰기 ✕", self)
        self.skip.setCursor(Qt.CursorShape.PointingHandCursor)
        self.skip.setStyleSheet(
            f"QPushButton{{background:{theme.CARD};color:{theme.SUBTLE};"
            f"border:1px solid {theme.BORDER};border-radius:{theme.RADIUS_LG}px;"
            f"padding:6px 14px;font-size:{theme.FONT_SM}px}}"
            f"QPushButton:hover{{border-color:{theme.PRIMARY};"
            f"color:{theme.PRIMARY_DARK}}}")
        self.skip.adjustSize()
        self.skip.clicked.connect(self.finish)
        self._layout_pieces()
        self._anim: QSequentialAnimationGroup | None = None
        self._timers: list[QTimer] = []

    # ── 배치 ────────────────────────────────────────────────
    def _center_rect(self, size: int) -> QRect:
        """오버레이 좌표계 기준, 화면 가운데 정사각형."""
        return QRect((self.width() - size) // 2,
                     (self.height() - size) // 2 - 30, size, size)

    def _dock_rect(self) -> QRect:
        """오른쪽 벽 도킹 위치(미니 위젯이 앉을 자리)."""
        return QRect(self.width() - DOCK - 2,
                     self.height() // 2 - DOCK // 2, DOCK, DOCK)

    def _layout_pieces(self) -> None:
        start = self._center_rect(int(BIG * 0.55))
        self.peng.setGeometry(start)
        big = self._center_rect(BIG)
        self.bubble.adjustSize()
        self.bubble.move(self.width() // 2 - self.bubble.width() // 2,
                         big.top() - self.bubble.height() - 12)
        self.skip.move(self.width() - self.skip.width() - 28,
                       self.height() - self.skip.height() - 28)

    def _set_line(self, html: str) -> None:
        self.bubble.setText(html)
        self.bubble.adjustSize()
        self.bubble.move(self.width() // 2 - self.bubble.width() // 2,
                         self.bubble.y())

    # ── 재생 ────────────────────────────────────────────────
    def build(self) -> QSequentialAnimationGroup:
        big = self._center_rect(BIG)
        seq = QSequentialAnimationGroup(self)

        # 1) 뿅 등장 (커지며 페이드인)
        pop = QParallelAnimationGroup(self)
        g = QPropertyAnimation(self.peng, b"geometry", self)
        g.setDuration(620)
        g.setStartValue(self._center_rect(int(BIG * 0.55)))
        g.setEndValue(big)
        g.setEasingCurve(QEasingCurve.Type.OutBack)
        pop.addAnimation(g)
        o = QPropertyAnimation(self._peng_fx, b"opacity", self)
        o.setDuration(420); o.setStartValue(0.0); o.setEndValue(1.0)
        pop.addAnimation(o)
        b = QPropertyAnimation(self._bub_fx, b"opacity", self)
        b.setDuration(500); b.setStartValue(0.0); b.setEndValue(1.0)
        pop.addAnimation(b)
        seq.addAnimation(pop)

        # 2) 살짝 통통 (인사하듯)
        for dy in (-16, 0, -9, 0):
            hop = QPropertyAnimation(self.peng, b"geometry", self)
            hop.setDuration(190)
            hop.setEndValue(big.translated(0, dy))
            hop.setEasingCurve(QEasingCurve.Type.InOutQuad)
            seq.addAnimation(hop)
        # 남은 문구를 다 읽고 나서 날아가도록 (문구 하나당 900ms)
        seq.addPause(max(700, 900 * (len(self._lines) - 1) - 100))

        # 3) 오른쪽 벽으로 슝 (작아지며) + 말풍선 사라짐
        fly = QParallelAnimationGroup(self)
        fg = QPropertyAnimation(self.peng, b"geometry", self)
        fg.setDuration(950)
        fg.setEndValue(self._dock_rect())
        fg.setEasingCurve(QEasingCurve.Type.InOutCubic)
        fly.addAnimation(fg)
        fb = QPropertyAnimation(self._bub_fx, b"opacity", self)
        fb.setDuration(420); fb.setEndValue(0.0)
        fly.addAnimation(fb)
        seq.addAnimation(fly)

        # 4) 도착 후 사라짐 (미니 위젯이 이 자리에 나타난다)
        out = QPropertyAnimation(self._peng_fx, b"opacity", self)
        out.setDuration(260); out.setEndValue(0.0)
        seq.addAnimation(out)
        return seq

    def start(self) -> None:
        self.show()
        self.raise_()
        self._anim = self.build()
        self._anim.finished.connect(self.finish)
        # 말풍선 문구 전환 — 등장(0.62s)+통통(0.76s)=1.38s 뒤부터 900ms 간격.
        # 위 addPause와 맞물려 마지막 문구까지 보이고 나서 날아간다.
        steps = [(1450 + 900 * i, t)
                 for i, t in enumerate(self._lines[1:])]
        for ms, text in steps:
            t = QTimer(self)
            t.setSingleShot(True)
            t.timeout.connect(lambda h=text: self._set_line(h))
            t.start(ms)
            self._timers.append(t)
        self._anim.start()

    def mousePressEvent(self, ev):     # 아무 데나 클릭하면 건너뛰기
        self.finish()

    def finish(self) -> None:
        if self._done:
            return
        self._done = True
        for t in self._timers:
            t.stop()
        if self._anim is not None:
            self._anim.stop()
        self.hide()
        cb, self._on_done = self._on_done, None
        if cb:
            cb()
        self.deleteLater()


def play_intro(base_dir: str, on_done=None, lines=FIRST_LINES) -> bool:
    """인트로를 재생한다. 재생하지 않으면 False(호출자가 바로 진행)."""
    if not motion.is_enabled():
        return False
    app = QApplication.instance()
    if app is None:
        return False
    overlay = IntroOverlay(base_dir, on_done=on_done, lines=lines)
    app._coolm_intro = overlay          # GC 방지
    overlay.start()
    return True


def play_update_intro(base_dir: str, version: str, notes: str = "",
                      on_done=None) -> bool:
    """업데이트 직후 인사 — 새 버전 소식 + 변경점 + 응원 멘트."""
    return play_intro(base_dir, on_done=on_done,
                      lines=update_lines(version, notes))
