# -*- coding: utf-8 -*-
"""바탕화면 위젯 공통 베이스 + 매니저 (v0.10.0).

위젯 4종(할일 간단판·주간·월간·포스트잇)이 공유하는 동작:
- 드래그 이동(상단 헤더 영역) + 가장자리 8방향 크기 조절
- 위치·크기·투명도·항상 위를 config["desk_widgets"]에 저장/복원
- 우클릭 메뉴(항상 위 / 투명도 / 끄기)
- 기본은 '항상 맨 뒤'(바탕화면 붙박이), 위젯별로 '항상 위' 선택 가능

매니저(ensure_desk_widgets / pin_note)는 설정에 맞춰 위젯들을
켜고 끄는 단일 진입점 — 레지스트리는 app._coolm_desk dict.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt, QRect, QTimer
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QApplication, QMenu, QWidget

from parser import pipeline
from parser.pipeline import DESK_KINDS, clamp_geometry, desk_conf, prune_notes
from store.event_store import EventStore
from ui import theme

_EDGE_L, _EDGE_R, _EDGE_T, _EDGE_B = 1, 2, 4, 8
_MARGIN = 8          # 가장자리 리사이즈 감지 폭 (투명 여백과 동일)
_HEADER_H = 40       # 상단 이동 드래그 영역 높이
_OPACITIES = (60, 75, 90, 100)


class DeskWidgetBase(QWidget):
    """서브클래스는 content 카드 UI와 refresh()만 구성한다.

    conf: config 내부의 위젯 설정 dict (desk_conf(...) 또는 notes 항목).
    수정 후 _save_config()를 부르면 통째로 저장된다.
    """

    MIN_W, MIN_H = 220, 160
    OFF_LABEL = "이 위젯 끄기"

    def __init__(self, store: EventStore, config: dict, base_dir: str,
                 conf: dict):
        super().__init__()
        self.store = store
        self.config = config
        self.base_dir = base_dir
        self.conf = conf
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMouseTracking(True)
        self.setMinimumSize(self.MIN_W, self.MIN_H)
        self._mode: str | None = None      # "move" | "resize"
        self._edges = 0
        self._start_geo: QRect | None = None
        self._start_pos = None
        self.apply_window_conf(first=True)
        self._store_cb = lambda: QTimer.singleShot(0, self.refresh)
        store.subscribe(self._store_cb)

    # ── 설정 반영 ────────────────────────────────────────────
    def window_flags(self) -> Qt.WindowType:
        flags = Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint
        if self.conf.get("always_on_top"):
            flags |= Qt.WindowType.WindowStaysOnTopHint
        else:
            flags |= Qt.WindowType.WindowStaysOnBottomHint
        return flags

    def apply_window_conf(self, first: bool = False) -> None:
        self.setWindowOpacity(max(40, int(self.conf.get("opacity", 90))) / 100)
        flags = self.window_flags()
        if first:
            self.setWindowFlags(flags)
        elif flags != self.windowFlags():
            visible = self.isVisible()
            self.setWindowFlags(flags)
            if visible:
                self.show()

    def show_at_saved(self) -> None:
        """저장된 위치·크기로 표시. 화면 밖(해상도 변경 등)이면 기본 배치."""
        screen = QApplication.primaryScreen().availableGeometry()
        geo = clamp_geometry(self.conf.get("geometry"),
                             [screen.x(), screen.y(),
                              screen.width(), screen.height()])
        if geo:
            self.setGeometry(*geo)
        else:
            self.place_default()
        self.show()

    def place_default(self) -> None:
        """서브클래스에서 재정의 — 기본 크기·위치."""
        screen = QApplication.primaryScreen().availableGeometry()
        self.resize(320, 300)
        self.move(screen.right() - self.width() - 80, screen.top() + 80)

    def refresh(self) -> None:
        """서브클래스에서 재정의 — 일정 변경 시 다시 그림."""

    # ── 저장 ────────────────────────────────────────────────
    def _save_config(self) -> None:
        pipeline.save_config(self.base_dir, self.config)

    def _save_geometry(self) -> None:
        g = self.geometry()
        self.conf["geometry"] = [g.x(), g.y(), g.width(), g.height()]
        self._save_config()

    # ── 이동·리사이즈 ───────────────────────────────────────
    def _hit_edges(self, pos) -> int:
        e = 0
        if pos.x() <= _MARGIN:
            e |= _EDGE_L
        if pos.x() >= self.width() - _MARGIN:
            e |= _EDGE_R
        if pos.y() <= _MARGIN:
            e |= _EDGE_T
        if pos.y() >= self.height() - _MARGIN:
            e |= _EDGE_B
        return e

    @staticmethod
    def _cursor_for(edges: int):
        if edges in (_EDGE_L | _EDGE_T, _EDGE_R | _EDGE_B):
            return Qt.CursorShape.SizeFDiagCursor
        if edges in (_EDGE_R | _EDGE_T, _EDGE_L | _EDGE_B):
            return Qt.CursorShape.SizeBDiagCursor
        if edges & (_EDGE_L | _EDGE_R):
            return Qt.CursorShape.SizeHorCursor
        if edges & (_EDGE_T | _EDGE_B):
            return Qt.CursorShape.SizeVerCursor
        return None

    def mousePressEvent(self, ev):
        if ev.button() != Qt.MouseButton.LeftButton:
            return
        pos = ev.position().toPoint()
        self._start_geo = QRect(self.geometry())
        self._start_pos = ev.globalPosition().toPoint()
        edges = self._hit_edges(pos)
        if edges:
            self._mode, self._edges = "resize", edges
        elif pos.y() <= _HEADER_H:
            self._mode = "move"

    def mouseMoveEvent(self, ev):
        if self._mode == "move":
            delta = ev.globalPosition().toPoint() - self._start_pos
            self.move(self._start_geo.topLeft() + delta)
            return
        if self._mode == "resize":
            delta = ev.globalPosition().toPoint() - self._start_pos
            g = QRect(self._start_geo)
            if self._edges & _EDGE_L:
                g.setLeft(min(g.left() + delta.x(),
                              g.right() - self.MIN_W + 1))
            if self._edges & _EDGE_R:
                g.setRight(max(g.right() + delta.x(),
                               g.left() + self.MIN_W - 1))
            if self._edges & _EDGE_T:
                g.setTop(min(g.top() + delta.y(),
                             g.bottom() - self.MIN_H + 1))
            if self._edges & _EDGE_B:
                g.setBottom(max(g.bottom() + delta.y(),
                                g.top() + self.MIN_H - 1))
            self.setGeometry(g)
            return
        # 드래그 중이 아니면 호버 위치에 맞는 커서만 갱신
        cur = self._cursor_for(self._hit_edges(ev.position().toPoint()))
        if cur:
            self.setCursor(cur)
        else:
            self.unsetCursor()

    def mouseReleaseEvent(self, ev):
        if self._mode:
            self._mode = None
            self._save_geometry()

    def leaveEvent(self, ev):
        self.unsetCursor()
        super().leaveEvent(ev)

    # ── 우클릭 메뉴 ──────────────────────────────────────────
    def contextMenuEvent(self, ev):
        menu = QMenu(self)
        menu.setStyleSheet(theme.BASE_QSS)
        top = QAction("항상 위에 보이기", menu)
        top.setCheckable(True)
        top.setChecked(bool(self.conf.get("always_on_top")))
        top.toggled.connect(self._set_always_on_top)
        menu.addAction(top)
        sub = menu.addMenu("투명도")
        cur_op = int(self.conf.get("opacity", 90))
        for v in _OPACITIES:
            a = QAction(f"{v}%", sub)
            a.setCheckable(True)
            a.setChecked(v == cur_op)
            a.triggered.connect(lambda _, v=v: self._set_opacity(v))
            sub.addAction(a)
        menu.addSeparator()
        off = QAction(self.OFF_LABEL, menu)
        off.triggered.connect(self.turn_off)
        menu.addAction(off)
        menu.exec(ev.globalPos())

    def _set_always_on_top(self, on: bool) -> None:
        self.conf["always_on_top"] = bool(on)
        self._save_config()
        self.apply_window_conf()

    def _set_opacity(self, v: int) -> None:
        self.conf["opacity"] = int(v)
        self._save_config()
        self.apply_window_conf()

    def turn_off(self) -> None:
        """끄기 — 서브클래스(포스트잇)는 notes 항목 제거로 재정의."""
        self.conf["enabled"] = False
        self._save_config()
        self.close()

    def closeEvent(self, ev):
        self.store.unsubscribe(self._store_cb)
        # 레지스트리에서 자신을 지워 다음 켜기 때 새로 만들어지게 한다
        reg = getattr(QApplication.instance(), "_coolm_desk", None)
        if reg:
            for k in DESK_KINDS:
                if reg.get(k) is self:
                    reg[k] = None
        super().closeEvent(ev)


# ── 매니저 ───────────────────────────────────────────────────
def _registry() -> dict:
    app = QApplication.instance()
    reg = getattr(app, "_coolm_desk", None)
    if reg is None:
        reg = {"simple": None, "weekly": None, "monthly": None, "notes": {}}
        app._coolm_desk = reg
    return reg


def _widget_class(kind: str):
    from ui import desk_widgets
    return {"simple": desk_widgets.SimpleTodoWidget,
            "weekly": desk_widgets.WeeklyWidget,
            "monthly": desk_widgets.MonthlyWidget}[kind]


def ensure_desk_widgets(owner) -> None:
    """설정에 맞춰 바탕화면 위젯들을 켜거나 끈다.

    owner: 펭귄/상세 위젯(WidgetBase) — base_dir·config·store를 빌려 쓴다.
    """
    app = QApplication.instance()
    app._coolm_desk_ctx = owner          # pin_note가 쓸 컨텍스트
    reg = _registry()
    config, store = owner.config, owner.store

    # 삭제된 일정을 가리키는 포스트잇 항목 정리
    if prune_notes(config, {e.id for e in store.all()}):
        pipeline.save_config(owner.base_dir, config)

    for kind in DESK_KINDS:
        conf = desk_conf(config, kind)
        cur = reg.get(kind)
        if conf.get("enabled"):
            if cur is None:
                w = _widget_class(kind)(store, config, owner.base_dir, conf)
                w.show_at_saved()
                reg[kind] = w
            else:
                cur.conf = conf          # 설정 창에서 config를 새로 읽었을 수 있음
                cur.config = config
                cur.apply_window_conf()
        elif cur is not None:
            cur.close()
            reg[kind] = None

    # 포스트잇: notes 목록과 떠 있는 위젯을 맞춘다
    from ui.desk_note import PostItWidget
    notes = desk_conf(config, "notes")
    wanted = {n.get("event_id"): n for n in notes if n.get("event_id")}
    for eid in list(reg["notes"]):
        if eid not in wanted:
            reg["notes"].pop(eid).close()
    for eid, conf in wanted.items():
        cur = reg["notes"].get(eid)
        if cur is None:
            ev = next((e for e in store.all() if e.id == eid), None)
            if ev is None:
                continue
            w = PostItWidget(store, config, owner.base_dir, conf, ev)
            w.show_at_saved()
            reg["notes"][eid] = w
        else:
            cur.conf = conf
            cur.config = config
            cur.apply_window_conf()


def pin_note(event_id: str) -> bool:
    """일정 1건을 포스트잇으로 바탕화면에 붙인다. 이미 있으면 앞으로 올린다."""
    app = QApplication.instance()
    owner = getattr(app, "_coolm_desk_ctx", None)
    if owner is None:
        return False
    reg = _registry()
    cur = reg["notes"].get(event_id)
    if cur is not None:
        cur.raise_()
        cur.activateWindow()
        return True
    notes = desk_conf(owner.config, "notes")
    notes.append({"event_id": event_id, "geometry": None,
                  "opacity": 95, "always_on_top": False})
    pipeline.save_config(owner.base_dir, owner.config)
    ensure_desk_widgets(owner)
    return True
