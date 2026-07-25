# -*- coding: utf-8 -*-
"""설치 후 첫 실행 인트로 — 화면 가운데에서 쿨비서가 등장해 오른쪽 벽으로 날아간다.

three.js/웹엔진 없이 Qt 애니메이션만 사용한다(용량 0, 시작 빠름).
- 1단계: 화면 중앙에 펭귄이 통통 튀며 등장 (OutBack) + 첫 인사
- 2단계: **사용자가 클릭할 때마다** 다음 말 (깡충 뛰며 전환)
  — 저 혼자 말하고 넘어가지 않도록 자동 진행을 없앰 (2026-07-25 사용자 요청)
- 3단계: 마지막 말에서 한 번 더 클릭하면 오른쪽 벽으로 날아가 사라짐
[건너뛰기]·Esc는 즉시 종료, 스페이스/엔터로도 넘길 수 있다.
애니메이션이 꺼져 있으면(motion.is_enabled False) 아예 재생하지 않는다.
"""
from __future__ import annotations

import math

from PyQt6.QtCore import (
    QEasingCurve, QParallelAnimationGroup, QPropertyAnimation, QRect,
    QSequentialAnimationGroup, Qt, QVariantAnimation,
)
from PyQt6.QtGui import QPainter, QPixmap, QTransform
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
        self._idx = 0            # 지금 보여주는 말의 순번
        self._flying = False     # 날아가는 중이면 클릭 무시
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

        # 클릭 안내 — 사용자가 눌러야 다음 말로 넘어간다.
        # 처음 보는 사람도 놓치지 않게 또렷한 알약 자막 + 은은한 깜빡임 (2026-07-25)
        self.hint = QLabel("👆  화면을 클릭하면 다음 말로 넘어가요", self)
        self.hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hint.setStyleSheet(
            f"background:{theme.CARD};color:{theme.PRIMARY_DARK};"
            f"border:1px solid {theme.BORDER};"
            f"border-radius:{theme.RADIUS_LG}px;padding:9px 18px;"
            f"font-size:{theme.FONT_MD}px;font-weight:bold")
        self.hint.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._hint_fx = QGraphicsOpacityEffect(self.hint)
        self.hint.setGraphicsEffect(self._hint_fx)
        self._hint_pulse = QPropertyAnimation(self._hint_fx, b"opacity", self)
        self._hint_pulse.setDuration(1100)
        self._hint_pulse.setStartValue(1.0)
        self._hint_pulse.setKeyValueAt(0.5, 0.45)
        self._hint_pulse.setEndValue(1.0)
        self._hint_pulse.setLoopCount(-1)      # 계속 깜빡 — 클릭 유도
        self._hint_pulse.start()

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
        self.hint.adjustSize()
        self.hint.move(self.width() // 2 - self.hint.width() // 2,
                       big.bottom() + 16)

    def _set_line(self, html: str) -> None:
        self.bubble.setText(html)
        self.bubble.adjustSize()
        self.bubble.move(self.width() // 2 - self.bubble.width() // 2,
                         self.bubble.y())

    # ── 재생 ────────────────────────────────────────────────
    def build(self) -> QSequentialAnimationGroup:
        """등장 모션만 — 이후 진행은 사용자의 클릭으로 (2026-07-25)."""
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
        return seq

    def _hop(self) -> None:
        """다음 말을 할 때 한 번 깡충 — 말이 바뀐 걸 눈으로 알린다."""
        big = self._center_rect(BIG)
        seq = QSequentialAnimationGroup(self)
        up = QPropertyAnimation(self.peng, b"geometry", self)
        up.setDuration(150); up.setEndValue(big.translated(0, -14))
        up.setEasingCurve(QEasingCurve.Type.OutQuad)
        seq.addAnimation(up)
        down = QPropertyAnimation(self.peng, b"geometry", self)
        down.setDuration(180); down.setEndValue(big)
        down.setEasingCurve(QEasingCurve.Type.OutBounce)
        seq.addAnimation(down)
        self._hop_anim = seq          # GC 방지
        seq.start()

    def _walk_away(self) -> None:
        """마지막 말이 끝나면 뒤돌아서 뒤뚱뒤뚱 걸어 오른쪽 자리로 돌아간다.

        뒷모습 그림은 없으므로 좌우 반전으로 '돌아선' 느낌을 주고,
        발끝을 축으로 좌우 갸우뚱 + 통통 튀는 리듬으로 펭귄 걸음을 흉내낸다.
        """
        self.skip.hide()
        self.hint.hide()
        self._hint_pulse.stop()
        # 뒤돌아선 느낌 — 좌우 반전한 그림으로 교체
        src = penguin_pixmap(self.base_dir, 512, "base")
        self._walk_src = src.transformed(QTransform().scale(-1, 1))
        self.peng.setScaledContents(False)
        bub = QPropertyAnimation(self._bub_fx, b"opacity", self)
        bub.setDuration(300); bub.setEndValue(0.0); bub.start()
        self._bub_anim = bub                    # GC 방지
        start = self._center_rect(BIG)
        end = self._dock_rect()
        walk = QVariantAnimation(self)
        walk.setDuration(2400)
        walk.setStartValue(0.0); walk.setEndValue(1.0)
        walk.setEasingCurve(QEasingCurve.Type.InOutSine)
        walk.valueChanged.connect(
            lambda t: self._walk_tick(float(t), start, end))

        def _arrive():
            out = QPropertyAnimation(self._peng_fx, b"opacity", self)
            out.setDuration(260); out.setEndValue(0.0)
            out.finished.connect(self.finish)
            out.start()
            self._out_anim = out                # GC 방지

        walk.finished.connect(_arrive)
        self._anim = walk
        walk.start()

    _WADDLE_STEPS = 7      # 걸음 수
    _WADDLE_ANGLE = 9      # 갸우뚱 각도(°)

    def _walk_tick(self, t: float, start: QRect, end: QRect) -> None:
        """걷기 한 프레임: 위치 이동 + 발끝 축 갸우뚱 + 통통."""
        x = start.x() + (end.x() - start.x()) * t
        y = start.y() + (end.y() - start.y()) * t
        size = max(24, round(start.width() + (end.width() - start.width()) * t))
        phase = t * math.pi * self._WADDLE_STEPS * 2
        ang = math.sin(phase) * self._WADDLE_ANGLE
        bob = abs(math.sin(phase)) * size * 0.05
        pad = int(size * 0.18)                  # 회전해도 안 잘리게 여유
        box = size + pad * 2
        self.peng.setGeometry(int(x) - pad, int(y - bob) - pad, box, box)
        frame = QPixmap(box, box)
        frame.fill(Qt.GlobalColor.transparent)
        p = QPainter(frame)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        p.translate(box / 2, box - pad)         # 발끝을 회전축으로
        p.rotate(ang)
        scaled = self._walk_src.scaled(
            size, size, Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation)
        p.drawPixmap(-scaled.width() // 2, -scaled.height(), scaled)
        p.end()
        self.peng.setPixmap(frame)

    def advance(self) -> None:
        """화면을 클릭할 때마다 다음 말 → 마지막이면 날아간다."""
        if self._done or self._flying:
            return
        if self._anim is not None and \
                self._anim.state() == QSequentialAnimationGroup.State.Running:
            self._anim.setCurrentTime(self._anim.totalDuration())  # 등장 건너뛰기
            return
        if self._idx < len(self._lines) - 1:
            self._idx += 1
            self._set_line(self._lines[self._idx])
            self._hop()
            if self._idx == len(self._lines) - 1:
                self.hint.setText("👆  한 번 더 누르면 시작해요!")
                self.hint.adjustSize()
                self.hint.move(self.width() // 2 - self.hint.width() // 2,
                               self.hint.y())
        else:
            self._flying = True
            self._walk_away()

    def start(self) -> None:
        self.show()
        self.raise_()
        self._anim = self.build()
        self._anim.start()
        self._anim.start()

    def mousePressEvent(self, ev):     # 아무 데나 클릭 = 다음 말 (건너뛰기는 버튼)
        self.advance()

    def keyPressEvent(self, ev):       # 스페이스·엔터로도 넘길 수 있게
        if ev.key() in (Qt.Key.Key_Space, Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.advance()
        elif ev.key() == Qt.Key.Key_Escape:
            self.finish()
        else:
            super().keyPressEvent(ev)

    def finish(self) -> None:
        if self._done:
            return
        self._done = True
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
