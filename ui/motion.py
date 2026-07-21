# -*- coding: utf-8 -*-
"""모션 유틸 — 가볍고 절제된 등장/퇴장 애니메이션 (emil-design-eng 기준).

원칙:
- 자주 보는 UI(펭귄 메뉴·⚡ 등록)는 애니메이션을 아예 걸지 않는다(이 모듈을
  호출하지 않으면 됨).
- 등장은 OutCubic 150~220ms, 퇴장은 그보다 빠르게. scale은 Qt QSS로 불가하므로
  "아래서 살짝 올라오며 페이드"(= scale 0.95+opacity의 번역)로 대체.
- config["animations_enabled"](기본 True) 하나로 전체를 끈다. 꺼져 있거나 중복
  호출돼도 최종 opacity는 반드시 1.0을 보장한다(창이 안 보이는 사고 방지).

스프링 물리는 쓰지 않는다 — 이 앱 규모엔 QEasingCurve로 충분.
"""
from __future__ import annotations

from PyQt6.QtCore import (QEasingCurve, QParallelAnimationGroup, QPoint,
                          QPropertyAnimation, QTimer)

_enabled = True


def set_enabled(on: bool) -> None:
    global _enabled
    _enabled = bool(on)


def is_enabled() -> bool:
    return _enabled


def fade_in(win, ms: int = 150) -> None:
    """톱레벨 창 windowOpacity 0→1 (OutCubic). 꺼짐이면 즉시 1.0."""
    if not _enabled:
        win.setWindowOpacity(1.0)
        return
    win.setWindowOpacity(0.0)
    a = QPropertyAnimation(win, b"windowOpacity", win)
    a.setDuration(ms)
    a.setStartValue(0.0)
    a.setEndValue(1.0)
    a.setEasingCurve(QEasingCurve.Type.OutCubic)
    win._motion_anim = a          # GC 방지
    a.start()


def pop_in(win, ms: int = 180, rise: int = 6) -> None:
    """등장: opacity 0→1 + 아래 rise px에서 제자리로 (scale 0.95 대체).

    win이 이미 최종 위치에 놓인 뒤(move 완료 후) 호출할 것.
    """
    if not _enabled:
        win.setWindowOpacity(1.0)
        return
    end = win.pos()
    start = QPoint(end.x(), end.y() + rise)
    win.move(start)
    win.setWindowOpacity(0.0)
    grp = QParallelAnimationGroup(win)
    fa = QPropertyAnimation(win, b"windowOpacity")
    fa.setDuration(ms)
    fa.setStartValue(0.0)
    fa.setEndValue(1.0)
    fa.setEasingCurve(QEasingCurve.Type.OutCubic)
    pa = QPropertyAnimation(win, b"pos")
    pa.setDuration(ms)
    pa.setStartValue(start)
    pa.setEndValue(end)
    pa.setEasingCurve(QEasingCurve.Type.OutCubic)
    grp.addAnimation(fa)
    grp.addAnimation(pa)
    win._motion_anim = grp
    grp.start()


def fade_out_close(win, ms: int = 120) -> None:
    """퇴장: enter보다 빠른 페이드 후 close(). 이중 호출은 무시(재진입 가드)."""
    if getattr(win, "_closing", False):
        return
    win._closing = True
    if not _enabled:
        win.close()
        return
    a = QPropertyAnimation(win, b"windowOpacity", win)
    a.setDuration(ms)
    a.setStartValue(win.windowOpacity())
    a.setEndValue(0.0)
    a.setEasingCurve(QEasingCurve.Type.OutCubic)
    a.finished.connect(win.close)
    win._motion_anim = a
    a.start()


class FadeInMixin:
    """QDialog 등에 섞으면 창이 뜰 때 부드럽게 페이드 인.

    class MyDialog(FadeInMixin, QDialog): ... 처럼 QDialog **앞**에 둘 것.
    자주 뜨지 않는 창에만 사용 (⚡ 등록처럼 빠른 창엔 넣지 않는다).
    """
    _fade_ms = 150

    def showEvent(self, ev):
        super().showEvent(ev)
        fade_in(self, getattr(self, "_fade_ms", 150))


def fade_in_widget(widget, ms: int = 200) -> None:
    """레이아웃 안의 자식 위젯 등장 — opacity 0→1 (pos 이동 없음, 레이아웃 안전).

    끝나면 효과를 제거해 이후 렌더가 정상으로 돌아온다.
    그림자 있는 위젯엔 쓰지 말 것(QGraphicsEffect는 위젯당 1개).
    """
    from PyQt6.QtWidgets import QGraphicsOpacityEffect
    widget.show()
    if not _enabled:
        return
    eff = QGraphicsOpacityEffect(widget)
    widget.setGraphicsEffect(eff)
    a = QPropertyAnimation(eff, b"opacity", widget)
    a.setDuration(ms)
    a.setStartValue(0.0)
    a.setEndValue(1.0)
    a.setEasingCurve(QEasingCurve.Type.OutCubic)
    a.finished.connect(lambda: widget.setGraphicsEffect(None))
    widget._motion_anim = a
    a.start()


def slide_fade_in(child, dy: int = 8, ms: int = 200) -> None:
    """자식 위젯(토스트)용 — QGraphicsOpacityEffect + 아래서 위로.

    주의: 위젯당 QGraphicsEffect는 1개뿐 → 그림자 있는 위젯엔 쓰지 말 것.
    """
    from PyQt6.QtWidgets import QGraphicsOpacityEffect
    if not _enabled:
        return
    end = child.pos()
    start = QPoint(end.x(), end.y() + dy)
    child.move(start)
    eff = QGraphicsOpacityEffect(child)
    child.setGraphicsEffect(eff)
    grp = QParallelAnimationGroup(child)
    fa = QPropertyAnimation(eff, b"opacity")
    fa.setDuration(ms)
    fa.setStartValue(0.0)
    fa.setEndValue(1.0)
    fa.setEasingCurve(QEasingCurve.Type.OutCubic)
    pa = QPropertyAnimation(child, b"pos")
    pa.setDuration(ms)
    pa.setStartValue(start)
    pa.setEndValue(end)
    pa.setEasingCurve(QEasingCurve.Type.OutCubic)
    grp.addAnimation(fa)
    grp.addAnimation(pa)
    child._motion_anim = grp
    grp.start()
