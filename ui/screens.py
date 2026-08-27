# -*- coding: utf-8 -*-
"""여러 모니터 다루기 — "그 지점이 속한 화면"을 찾아 쓰는 도우미들.

예전에는 곳곳에서 primaryScreen()만 봤다. 듀얼 모니터에서 보조 화면은
좌표가 음수이거나 주 화면 밖이라, 그 기준으로 자르면 펭귄·위젯이 주
화면으로 튕겨 돌아왔다 (2026-08-25).

펭귄(widget_base)과 바탕화면 위젯(desk_base)이 함께 쓴다. 두 모듈이
서로를 import하지 않도록 여기 따로 뒀다.
"""
from __future__ import annotations

from PyQt6.QtCore import QPoint, QRect
from PyQt6.QtWidgets import QApplication


def screen_at(point: QPoint):
    """그 점이 놓인 화면. 화면 사이 틈이면 가장 가까운 화면."""
    app = QApplication.instance()
    scr = app.screenAt(point) if app else None
    if scr is not None:
        return scr
    best, best_d = None, None
    for s in (app.screens() if app else []):
        c = s.availableGeometry().center()
        d = (c.x() - point.x()) ** 2 + (c.y() - point.y()) ** 2
        if best_d is None or d < best_d:
            best, best_d = s, d
    return best or (app.primaryScreen() if app else None)


def clamp_to_screens(pos: QPoint, size, anchor: QPoint | None = None) -> QPoint:
    """창이 화면 밖으로 나가지 않게 자른다.

    기준 화면은 기본적으로 '창 한가운데가 놓인 화면'. 드래그 중에는
    anchor로 **커서 위치**를 넘긴다 — 그래야 듀얼 모니터 경계에서 창이
    반쯤 걸린 채 끈적이지 않고 커서를 따라 옆 화면으로 넘어간다.
    """
    center = anchor if anchor is not None else QPoint(
        pos.x() + size.width() // 2, pos.y() + size.height() // 2)
    scr = screen_at(center)
    if scr is None:
        return pos
    g = scr.availableGeometry()
    x = min(max(pos.x(), g.left()), max(g.left(), g.right() - size.width() + 1))
    y = min(max(pos.y(), g.top()), max(g.top(), g.bottom() - size.height() + 1))
    return QPoint(x, y)


def on_any_screen(rect) -> bool:
    """어느 화면에든 걸쳐 있으면 True (보조 모니터도 화면이다)."""
    app = QApplication.instance()
    return any(s.availableGeometry().intersects(rect)
               for s in (app.screens() if app else []))


def best_screen_rect(geo) -> list[int] | None:
    """저장된 [x, y, w, h]와 가장 많이 겹치는 화면의 영역 [x, y, w, h].

    저장된 위치가 보조 모니터의 것이면 그 모니터를 돌려준다 — 주 화면
    기준으로 자르면 위젯이 매번 주 화면으로 끌려온다.
    """
    if not geo or len(geo) != 4:
        return None
    try:
        rect = QRect(int(geo[0]), int(geo[1]), int(geo[2]), int(geo[3]))
    except (TypeError, ValueError):
        return None
    app = QApplication.instance()
    best, best_area = None, -1
    for s in (app.screens() if app else []):
        inter = s.availableGeometry().intersected(rect)
        area = max(0, inter.width()) * max(0, inter.height())
        if area > best_area:
            best, best_area = s, area
    if best is None:
        return None
    g = best.availableGeometry()
    return [g.x(), g.y(), g.width(), g.height()]
