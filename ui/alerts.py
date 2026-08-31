# -*- coding: utf-8 -*-
"""시작 알림 — 켤 때 마감이 다가온 일정을 포스트잇(ui/alert_note.py)에 붙인다.

프로그램을 켤 때 딱 한 번만 뜬다 (앱 수준 플래그로 보장).
설정 → 일반 → '알림'에서 끄고 켜며, 며칠 전부터 알릴지도 거기서 고른다.
말풍선(AlertBubble)은 첫 실행 기능 안내와 ⚡ 간편 등록 안내에 계속 쓰인다.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget,
)

from store.event_store import EventStore
from ui import theme
from version import APP_VERSION


@dataclass
class Alert:
    """알림 한 줄. key가 있으면 ✕로 뗀 사실을 config에 기억한다.

    days_left: 마감까지 남은 날 (마감 알림만, 0=오늘 마감). 마감 알림이
    아니면 None — '오늘 일정 N건'이나 안내 문구가 그렇다.
    """
    text: str
    key: str = ""              # "" = 기억하지 않는다 (안내 문구 등)
    days_left: int | None = None


def build_alerts(store: EventStore, today: date | None = None,
                 days_before: int = 3) -> list[Alert]:
    """마감 알림(N일 전부터 당일까지) → 오늘 할일 순서로 알림을 만든다.

    days_before는 사용자가 설정에서 고른다(기본 3). 예전에는 딱 3일 전·1일 전
    이틀만 알려서 그 사이에 프로그램을 안 켜면 알림을 통째로 놓쳤다.
    급한 것(마감이 가까운 것)부터 위로 온다.
    """
    today = today or date.today()
    days_before = max(0, int(days_before))
    items: list[Alert] = []
    for e in store.all():
        if e.is_deadline and not e.done:
            days_left = (e.start_dt.date() - today).days
            if 0 <= days_left <= days_before:
                label = "오늘 마감" if days_left == 0 else f"마감 {days_left}일 전"
                items.append(Alert(f"⏰ {label}\n{e.title}",
                                   key=f"ev:{e.id}", days_left=days_left))
    items.sort(key=lambda a: a.days_left)
    n = len(store.on_date(today))
    if n:
        items.append(Alert(f"📋 오늘 일정 {n}건",
                           key=f"today:{today.isoformat()}"))
    return items


# ── ✕로 뗀 알림 기억하기 ────────────────────────────────────
# config["alert_dismissed"] = {열쇠: 뗄 때 남아 있던 날수}
# 값이 필요한 이유: 미리 떼어 두었어도 '마감 당일'에는 한 번 더 알리기 위해
# (2026-08-31 사용자 결정). 당일에 뗀 것(값 0)은 다시 뜨지 않는다.
DISMISS_KEY = "alert_dismissed"


def _dismissed(config: dict) -> dict:
    d = config.get(DISMISS_KEY)
    return d if isinstance(d, dict) else {}


def is_dismissed(alert: Alert, config: dict) -> bool:
    """이미 ✕로 뗀 알림인지. 단, 마감 당일 알림은 한 번 더 통과시킨다."""
    if not alert.key:
        return False
    marks = _dismissed(config)
    if alert.key not in marks:
        return False
    try:
        when = int(marks[alert.key])
    except (TypeError, ValueError):
        when = 0
    return not (alert.days_left == 0 and when > 0)


def mark_dismissed(alert: Alert, config: dict) -> bool:
    """✕로 뗀 사실을 config에 적는다. 바뀌었으면 True (저장은 호출한 쪽에서)."""
    if not alert.key:
        return False
    marks = dict(_dismissed(config))
    value = alert.days_left if alert.days_left is not None else 0
    if marks.get(alert.key) == value:
        return False
    marks[alert.key] = value
    config[DISMISS_KEY] = marks
    return True


def prune_dismissed(config: dict, store: EventStore,
                    today: date | None = None) -> bool:
    """사라진 일정·지난 날짜의 기록을 지운다. 변경 시 True.

    안 지우면 config가 뗀 알림 기록으로 계속 불어난다.
    """
    marks = _dismissed(config)
    if not marks:
        return False
    today = today or date.today()
    alive = {f"ev:{e.id}" for e in store.all()}
    today_key = f"today:{today.isoformat()}"
    keep = {k: v for k, v in marks.items()
            if (k in alive) or k == today_key}
    if len(keep) == len(marks):
        return False
    config[DISMISS_KEY] = keep
    return True


def highlight_urgency(text: str) -> str:
    """'N건'·'N일 전'·'오늘 마감'을 빨간 배경+흰 글씨로 강조한 HTML로 바꾼다.

    '오늘 마감'에는 숫자가 없어서 예전 규칙으로는 가장 급한 알림이 오히려
    밋밋하게 보였다 — 그래서 낱말째로 함께 잡는다.
    """
    import html
    import re
    esc = html.escape(text).replace("\n", "<br>")
    return re.sub(
        r"(\d+건|\d+일 전|오늘 마감)",
        rf'<span style="background-color:{theme.DANGER};color:white;'
        r'font-weight:bold;">&nbsp;\1&nbsp;</span>', esc)


class AlertBubble(QWidget):
    """앵커 위젯 위에 뜨는 말풍선. 클릭하면 다음 알림, 끝나면 사라진다."""

    def __init__(self, alerts: list[str], anchor: QWidget, on_done=None):
        super().__init__(None, Qt.WindowType.Tool
                         | Qt.WindowType.FramelessWindowHint
                         | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.alerts = alerts
        self.anchor = anchor
        self.on_done = on_done
        self._popped = False
        self.idx = 0
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 10)
        card = QFrame()
        card.setObjectName("bubble")
        card.setStyleSheet(
            f"#bubble{{background:{theme.CARD};border:none;"
            f"border-radius:{theme.RADIUS_LG}px}}")
        card.setGraphicsEffect(theme.make_shadow(self, 2))
        outer.addWidget(card)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(12, 9, 12, 9)
        lay.setSpacing(3)
        body = QHBoxLayout()
        body.setSpacing(8)
        # 놀란 쿨쿠리 — 알림이 있다는 걸 캐릭터가 대신 말해준다
        if getattr(anchor, "config", {}).get("character_mode", True):
            from ui.penguin_icon import penguin_pixmap
            base_dir = getattr(anchor, "base_dir", "")
            kookuri = QLabel()
            kookuri.setPixmap(penguin_pixmap(base_dir, 38, "surprise"))
            kookuri.setStyleSheet("background:transparent")
            body.addWidget(kookuri, alignment=Qt.AlignmentFlag.AlignTop)
        self.text = QLabel()
        self.text.setWordWrap(True)
        self.text.setStyleSheet(
            f"color:{theme.TEXT};font-size:12px;font-weight:bold;"
            f"background:transparent")
        body.addWidget(self.text, stretch=1)
        lay.addLayout(body)
        self.hint = QLabel()
        self.hint.setStyleSheet(
            f"color:{theme.SUBTLE};font-size:10px;background:transparent")
        lay.addWidget(self.hint)
        self._sync()

    def _sync(self) -> None:
        self.text.setTextFormat(Qt.TextFormat.RichText)
        self.text.setText(highlight_urgency(self.alerts[self.idx]))
        remain = len(self.alerts) - self.idx - 1
        self.hint.setText(f"클릭하면 {'다음 알림' if remain else '닫기'} "
                          f"({self.idx + 1}/{len(self.alerts)})")
        self.adjustSize()
        self.reposition()

    def reposition(self) -> None:
        """앵커 위에 오른쪽 정렬로 배치 (펭귄 머리 위 / 위젯 위).

        화면 밖으로 나가면 앵커가 놓인 화면 안으로 민다. 예전엔 0으로 잘라
        보조 모니터(좌표가 음수일 수 있다)에서 말풍선이 주 화면으로 튀었다.
        """
        if self.anchor is None or not self.anchor.isVisible():
            return
        from PyQt6.QtCore import QPoint
        from ui.widget_base import clamp_to_screens
        x = self.anchor.x() + self.anchor.width() - self.width()
        y = self.anchor.y() - self.height() - 2
        self.move(clamp_to_screens(QPoint(x, y), self.size()))

    def showEvent(self, ev):
        super().showEvent(ev)
        if not self._popped:          # 첫 등장만 살짝 올라오며 페이드
            self._popped = True
            from ui import motion
            motion.pop_in(self, ms=200, rise=6)

    def mousePressEvent(self, ev) -> None:
        # 일정 말풍선을 누르면 '오늘 할 일' 위젯을 바로 보여준다 (1회)
        self._open_today_widget()
        self.idx += 1
        if self.idx >= len(self.alerts):
            self.close()
            if self.on_done:
                self.on_done()
        else:
            self._sync()

    def _open_today_widget(self) -> None:
        """말풍선 클릭 → 오늘 할 일 위젯 켜기 (설정에도 저장)."""
        if getattr(self, "_today_opened", False):
            return
        self._today_opened = True
        anchor = self.anchor
        try:
            if hasattr(anchor, "apply_desk_widget"):
                from parser.pipeline import desk_conf
                if not desk_conf(anchor.config, "today").get("enabled"):
                    anchor.apply_desk_widget("today", True)
        except Exception:
            pass                      # 위젯 표시 실패가 알림을 막지 않게


INTRO_STEPS = [
    "👋 반가워요! 쿨메신저에서 쪽지를 보다가\n"
    "⚡(바로 등록)를 누르면 그 쪽지가 일정이 돼요.\n"
    "펭귄을 더블클릭해도 열립니다.",
    "🗓 등록한 일정은 캘린더에서\n확인하고 수정할 수 있어요.\n"
    "중요도가 '높음'인 날은 빨간 배지로 표시돼요.",
    "⚙ 설정에서 즐겨찾기·알림·자동 시작 같은\n기능을 켜고 끌 수 있어요.\n"
    "그럼, 시작해 볼까요?",
]


def _is_new_version(widget) -> bool:
    """지난 실행 이후 버전이 올라갔는지 (업데이트 직후 첫 실행인지).

    호출 시점에는 이미 '첫 실행(intro_done False)'을 걸러낸 뒤이므로,
    기록(last_seen_version)이 아예 없으면 = 이 기능이 없던 옛 버전에서
    막 올라온 사용자 → 업데이트로 본다. (v1.7.2에서 기록이 없어 인사가
    안 뜨던 버그 수정, 2026-07-25)
    """
    return widget.config.get("last_seen_version") != APP_VERSION


def _bundled_notes(base_dir: str) -> str:
    """앱과 함께 설치된 release_notes.txt의 본문(첫 줄=제목 제외)."""
    import os
    try:
        with open(os.path.join(base_dir, "release_notes.txt"),
                  encoding="utf-8") as f:
            lines = f.read().strip().splitlines()
        return "\n".join(lines[1:]).strip()
    except Exception:
        return ""


def _mark_version_seen(widget) -> None:
    if widget.config.get("last_seen_version") == APP_VERSION:
        return
    from parser import pipeline
    widget.config["last_seen_version"] = APP_VERSION
    widget.config.pop("pending_update_notes", None)
    try:
        pipeline.save_config(widget.base_dir, widget.config)
    except Exception:
        pass


def show_startup_alerts(widget) -> None:
    """앱 세션당 한 번만 알림 포스트잇을 띄운다. widget = WidgetBase 인스턴스.

    첫 실행이면 알림 대신 기능 안내(인트로) 3장을 말풍선으로 먼저 보여준다.
    설정에서 알림을 꺼 두었으면 아무것도 띄우지 않는다.
    """
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance()
    if getattr(app, "_coolm_alerts_shown", False):
        return
    app._coolm_alerts_shown = True

    if not widget.config.get("intro_done"):
        def finish_intro():
            from parser import pipeline
            widget.config["intro_done"] = True
            pipeline.save_config(widget.base_dir, widget.config)

        def show_bubble():
            bubble = AlertBubble(INTRO_STEPS, widget, on_done=finish_intro)
            widget._alert_bubble = bubble
            bubble.show()

        # 설치 후 첫 실행: 가운데 등장 → 오른쪽 벽으로 날아가는 인트로 먼저
        from ui.intro import play_intro
        _mark_version_seen(widget)
        if not play_intro(widget.base_dir, on_done=show_bubble):
            show_bubble()
        return

    # 업데이트 직후 첫 실행: 새 소식 + 응원 멘트를 쿨비서가 전한다
    if _is_new_version(widget):
        # 옛 버전에서 올라온 경우 저장된 변경점이 없으므로 앱에 동봉된
        # release_notes.txt를 대신 읽는다.
        notes = (widget.config.pop("pending_update_notes", "")
                 or _bundled_notes(widget.base_dir))
        _mark_version_seen(widget)      # 못 띄우더라도 기록은 남긴다
        from ui.intro import play_update_intro
        if play_update_intro(widget.base_dir, APP_VERSION, notes):
            return
    else:
        _mark_version_seen(widget)

    # 설정에서 알림을 끈 사용자에게는 아무것도 띄우지 않는다
    if not widget.config.get("alert_enabled", True):
        return

    from parser import pipeline
    today = date.today()
    days_before = widget.config.get("alert_before_days", 3)
    alerts = build_alerts(widget.store, today, days_before=days_before)

    # ✕로 뗀 알림은 거른다. 전부 뗀 상태면 아무것도 띄우지 않는다 —
    # "다 봤다"고 표시한 사람에게 '새 알림 없어요'를 다시 들이밀지 않게.
    if prune_dismissed(widget.config, widget.store, today):
        pipeline.save_config(widget.base_dir, widget.config)
    had_any = bool(alerts)
    alerts = [a for a in alerts if not is_dismissed(a, widget.config)]

    # 구 '반절 캘린더' 사용자에게 위젯 개편을 최초 1회만 안내
    notice = None
    if not widget.config.get("desk_migration_notice_done", True):
        notice = Alert(
            "🔄 바탕화면 캘린더가 주간·월간 위젯 2개로 바뀌었어요.\n"
            "이제 드래그로 옮기고 모서리를 끌어 크기를 조절할 수 있어요.\n"
            "펭귄 → 위젯 메뉴에서 켜고 끕니다.")
        alerts.insert(0, notice)
        widget.config["desk_migration_notice_done"] = True
        pipeline.save_config(widget.base_dir, widget.config)

    if not alerts:
        if had_any:
            return          # 있던 알림을 전부 뗐다 — 조용히 넘어간다
        # 알림이 없어도 '켜졌다'는 것은 보이게 — 창이 없는 앱이라
        # 실행됐는지 몰라 헤매는 문제 방지 (2026-07-22 사용자 피드백)
        alerts = [Alert("COOL-비서가 켜졌어요 — 오늘은 새 알림이 없어요.\n"
                        "펭귄을 누르면 메뉴가 열립니다.")]

    def remember(alert: Alert) -> None:
        if mark_dismissed(alert, widget.config):
            try:
                pipeline.save_config(widget.base_dir, widget.config)
            except OSError:
                pass        # 기록에 실패해도 알림을 떼는 동작은 막지 않는다

    from ui.alert_note import AlertNote
    note = AlertNote(alerts, widget, today=today, on_dismiss=remember,
                     on_open=getattr(widget, "open_calendar", None))
    widget._alert_note = note              # GC 방지
    note.place()
    note.show()
