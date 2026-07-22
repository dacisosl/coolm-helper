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
from PyQt6.QtGui import QAction, QColor, QPainter
from PyQt6.QtWidgets import (
    QApplication, QHBoxLayout, QLabel, QMenu, QPushButton, QSlider, QWidget,
)

from parser import pipeline
from parser.pipeline import DESK_KINDS, clamp_geometry, desk_conf, prune_notes
from store.event_store import EventStore
from ui import theme

_EDGE_L, _EDGE_R, _EDGE_T, _EDGE_B = 1, 2, 4, 8
_MARGIN = 8          # 가장자리 리사이즈 감지 폭 (투명 여백과 동일)
_HEADER_H = 40       # 상단 이동 드래그 영역 높이
_OPACITIES = (60, 75, 90, 100)


class _GripHint(QWidget):
    """카드 우하단에 항상 보이는 대각선 점점 — 잡고 끌면 크기 조절.

    카드(자식 위젯) 위에 얹히는 오버레이라 어느 위젯·배경에서도 보인다.
    아래 깔린 목록이 클릭을 삼키지 않도록 마우스를 직접 받아
    부모(DeskWidgetBase)의 우하단 코너 리사이즈로 넘긴다.
    """

    def __init__(self, parent):
        super().__init__(parent)
        self.setFixedSize(18, 18)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        self.setToolTip("잡고 끌면 크기 조절")

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        c = QColor(theme.SUBTLE)
        c.setAlpha(150)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(c)
        for i in range(3):
            for j in range(3 - i):
                p.drawEllipse(15 - j * 4, 15 - i * 4, 2, 2)
        p.end()

    # 부모의 리사이즈 로직에 위임 — move/release는 global 좌표만 쓴다
    def mousePressEvent(self, ev):
        if ev.button() != Qt.MouseButton.LeftButton:
            return
        w = self.parentWidget()
        w._mode = "resize"
        w._edges = _EDGE_R | _EDGE_B
        w._start_geo = w.geometry()
        w._start_pos = ev.globalPosition().toPoint()

    def mouseMoveEvent(self, ev):
        self.parentWidget().mouseMoveEvent(ev)

    def mouseReleaseEvent(self, ev):
        self.parentWidget().mouseReleaseEvent(ev)


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
        self.edit_mode = False             # 🔧 편집 모드 (잡기 포인트·도구줄)
        self._edit_bar: QWidget | None = None
        self._font_label: QLabel | None = None
        self.apply_window_conf(first=True)
        self._grip_hint = _GripHint(self)   # 우하단 크기조절 점점 (전 위젯)
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

    # ── 🔧 편집 모드 (잡기 포인트 표시 + 도구줄) ─────────────
    def font_scale(self) -> int:
        return int(self.conf.get("font_scale", 100))

    def font_px(self, base: int) -> int:
        """위젯별 글씨 크기 설정(%)을 적용한 픽셀 크기."""
        return max(7, round(base * self.font_scale() / 100))

    def build_edit_bar(self) -> QWidget:
        """편집 모드에서만 보이는 도구줄: 투명도 슬라이더 + 글씨 크기."""
        bar = QWidget()
        bar.setStyleSheet("background:transparent")
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(0, 0, 0, 2)
        lay.setSpacing(6)
        op_label = QLabel("투명도")
        op_label.setStyleSheet(
            f"color:{theme.SUBTLE};font-size:10px;background:transparent")
        lay.addWidget(op_label)
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(40, 100)
        slider.setValue(max(40, int(self.conf.get("opacity", 90))))
        slider.setFixedSize(110, 18)   # 위젯 폭을 다 차지하지 않게 고정 폭
        slider.setToolTip("위젯 투명도")
        slider.valueChanged.connect(
            lambda v: self.setWindowOpacity(v / 100))          # 즉시 미리보기
        slider.sliderReleased.connect(
            lambda s=slider: self._set_opacity(s.value()))     # 놓으면 저장
        lay.addWidget(slider)
        # 글씨 크기 — 'A−'/'A＋' 글자는 PC에 따라 안 보여서 SVG로 그린다
        from PyQt6.QtCore import QSize as _QSize
        from ui.icons import icon as _icon
        for name, delta, tip in (("font_minus", -10, "글씨 작게"),
                                 ("font_plus", 10, "글씨 크게")):
            b = QPushButton()
            b.setIcon(_icon(name, 14))
            b.setIconSize(_QSize(14, 14))
            b.setFixedSize(30, 20)
            b.setToolTip(tip)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setStyleSheet(
                f"QPushButton{{background:{theme.CARD};border:1px solid "
                f"{theme.BORDER};border-radius:5px}}"
                f"QPushButton:hover{{background:{theme.PRIMARY_LIGHT}}}"
                f"QPushButton:pressed{{background:{theme.LIGHT_PRESSED}}}")
            b.clicked.connect(lambda _, d=delta: self._bump_font(d))
            lay.addWidget(b)
        self._font_label = QLabel(f"{self.font_scale()}%")
        self._font_label.setStyleSheet(
            f"color:{theme.SUBTLE};font-size:10px;background:transparent")
        lay.addWidget(self._font_label)
        lay.addStretch()               # ✕는 오른쪽 끝으로
        # ✕ 위젯 끄기 (📌 고정은 v1.4부터 헤더의 make_pin_button으로 이동)
        from PyQt6.QtCore import QSize
        from ui.icons import icon
        off = QPushButton()
        off.setIcon(icon("close", 12))
        off.setIconSize(QSize(12, 12))
        off.setToolTip(self.OFF_LABEL)
        off.setFixedSize(26, 20)
        off.setCursor(Qt.CursorShape.PointingHandCursor)
        off.setStyleSheet(
            f"QPushButton{{background:{theme.CARD};border:1px solid "
            f"{theme.BORDER};border-radius:5px}}"
            f"QPushButton:hover{{background:{theme.DANGER_BG};border-color:{theme.DANGER}}}"
            f"QPushButton:pressed{{background:{theme.DANGER_PRESSED}}}")
        off.clicked.connect(self.turn_off)
        lay.addWidget(off)
        bar.setVisible(False)
        self._edit_bar = bar
        return bar

    def make_header_toggle(self, icon_name: str, tip: str,
                           checked: bool = False) -> QPushButton:
        """헤더용 작은 토글 버튼 (편집 버튼과 같은 결)."""
        from PyQt6.QtCore import QSize
        from ui.icons import icon
        b = QPushButton()
        b.setIcon(icon(icon_name, 14))
        b.setIconSize(QSize(14, 14))
        b.setCheckable(True)
        b.setChecked(checked)
        b.setToolTip(tip)
        b.setFixedSize(26, 22)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.setStyleSheet(
            f"QPushButton{{background:transparent;border:1px solid "
            f"{theme.BORDER};border-radius:{theme.RADIUS_SM}px}}"
            f"QPushButton:checked{{background:{theme.PRIMARY_LIGHT};"
            f"border-color:{theme.PRIMARY}}}"
            f"QPushButton:hover{{background:{theme.PRIMARY_LIGHT}}}"
            f"QPushButton:pressed{{background:{theme.LIGHT_PRESSED}}}")
        return b

    def make_edit_button(self) -> QPushButton:
        """헤더에 놓는 🔧(렌치) 버튼 — 누르면 편집 모드 켜고 끄기.

        이모지가 아니라 내장 SVG 아이콘이라 어느 PC에서나 보인다.
        """
        from PyQt6.QtCore import QSize
        from ui.icons import icon
        b = QPushButton()
        b.setIcon(icon("tools", 14))
        b.setIconSize(QSize(14, 14))
        b.setToolTip("편집 모드 — 크기 조절점·투명도·글씨 크기·내용 수정")
        b.setFixedSize(26, 22)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.setStyleSheet(
            f"QPushButton{{background:transparent;border:1px solid "
            f"{theme.BORDER};border-radius:6px}}"
            f"QPushButton:hover{{background:{theme.PRIMARY_LIGHT}}}"
            f"QPushButton:pressed{{background:{theme.LIGHT_PRESSED}}}")
        b.clicked.connect(self.toggle_edit_mode)
        return b

    _edit_hint_shown = False   # 편집 모드 안내 토스트 — 세션당 1회(전 위젯 공유)

    def toggle_edit_mode(self) -> None:
        self.edit_mode = not self.edit_mode
        if self._edit_bar is not None:
            self._edit_bar.setVisible(self.edit_mode)
        self.update()          # 잡기 포인트 다시 그리기
        self.refresh()         # 편집 모드용 내용(인라인 입력칸 등) 반영
        if self.edit_mode and not DeskWidgetBase._edit_hint_shown:
            DeskWidgetBase._edit_hint_shown = True
            from ui.toast import show_toast
            show_toast(self, "파란 점을 끌면 크기, 제목을 누르면 바로 수정",
                       msec=6000)

    def _bump_font(self, delta: int) -> None:
        self.conf["font_scale"] = max(70, min(150,
                                              self.font_scale() + delta))
        self._save_config()
        if self._font_label is not None:
            self._font_label.setText(f"{self.font_scale()}%")
        self.refresh()

    def paintEvent(self, ev):
        super().paintEvent(ev)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        if self.edit_mode:
            # 4개 변 중앙 + 4개 꼭지점에 잡기 포인트(캐칭 포인트)를 그린다
            p.setPen(QColor("white"))
            p.setBrush(QColor(theme.PRIMARY))
            s = 8
            for x in (0, (w - s) // 2, w - s):
                for y in (0, (h - s) // 2, h - s):
                    if (x, y) == ((w - s) // 2, (h - s) // 2):
                        continue       # 중앙은 제외
                    p.drawRoundedRect(x, y, s, s, 2, 2)
        p.end()
        # 평상시 그립 힌트는 _GripHint 오버레이가 카드 위에 그린다
        # (여기 paintEvent는 자식 카드 아래에 깔려 카드 안에선 안 보임)

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        # 그립 점점을 카드 우하단 안쪽에 붙인다 (카드 여백 8px 감안)
        if getattr(self, "_grip_hint", None) is not None:
            self._grip_hint.move(self.width() - 28, self.height() - 28)
            self._grip_hint.raise_()

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
        # 우하단 점점(그립 힌트) 부근 24×24는 카드 위라도 코너 리사이즈
        if (pos.x() >= self.width() - 24
                and pos.y() >= self.height() - 24):
            e = _EDGE_R | _EDGE_B
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
        edit = QAction("편집 모드 — 크기 조절점·투명도·글씨", menu)
        edit.setCheckable(True)
        edit.setChecked(self.edit_mode)
        edit.triggered.connect(self.toggle_edit_mode)
        menu.addAction(edit)
        menu.addSeparator()
        top = QAction("항상 위에 보이기", menu)
        top.setCheckable(True)
        top.setChecked(bool(self.conf.get("always_on_top")))
        top.toggled.connect(self._set_always_on_top)
        menu.addAction(top)
        # 투명도는 편집 모드의 슬라이더로 일원화 (메뉴 중복 제거)
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
        reg = {k: None for k in DESK_KINDS}
        reg["notes"] = {}
        app._coolm_desk = reg
    reg.setdefault("planner", None)      # 구버전 세션 레지스트리 호환
    return reg


def _widget_class(kind: str):
    from ui import desk_widgets
    return {"planner": desk_widgets.PlannerWidget,
            "simple": desk_widgets.SimpleTodoWidget,
            "weekly": desk_widgets.WeeklyWidget,
            "today": desk_widgets.TodayTodoWidget}[kind]


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
                  "opacity": 95, "always_on_top": False, "font_scale": 100})
    pipeline.save_config(owner.base_dir, owner.config)
    ensure_desk_widgets(owner)
    return True
