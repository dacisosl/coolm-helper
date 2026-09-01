# -*- coding: utf-8 -*-
"""전 위젯 생성 스모크 — import 누락·QSS 파싱 오류 회귀 방지.

v1.3.0에서 alerts.py가 QHBoxLayout를 import 없이 써서 앱이 시작 시 죽는
버그가 있었다(오프스크린 렌더 스모크에 AlertBubble이 빠져 있어 못 잡음).
이 테스트는 오프스크린으로 모든 상위 위젯을 '실제로 생성'해 그 유형의
NameError/AttributeError를 CI에서 잡는다.
"""
import os
import sys
import tempfile
import shutil
import unittest
from datetime import datetime, date

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
# Windows CI에서 pywinauto/UIA 캡처가 멈출 수 있어 테스트에선 차단
os.environ["COOLM_NO_CAPTURE"] = "1"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication

from store.event_store import EventStore
from store.favorites import FavStore
from parser.pipeline import load_config

_app = QApplication.instance() or QApplication(sys.argv)


class TestWidgetSmoke(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.store = EventStore(self.tmp)
        self.fav = FavStore(self.tmp)
        self.conf = load_config(self.tmp)
        self.conf["proof_enabled"] = True
        self.conf["favorites_enabled"] = True
        self.ev = self.store.add(
            "교직원 회의", datetime(2026, 7, 22, 15, 0), all_day=False,
            priority="높음", memo="안건")
        self.store.add("성적 마감", datetime(2026, 7, 23), is_deadline=True)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _show(self, w):
        w.show()
        _app.processEvents()
        w.close()

    def test_alert_bubble(self):
        # 시작 시 뜨는 알림 말풍선 — v1.3.0 크래시 지점
        from ui.mini_widget import MiniWidget
        from ui.alerts import AlertBubble
        anchor = MiniWidget(self.tmp)
        self._show(AlertBubble(["오늘 일정 3건", "성적 마감 1일 전"], anchor))
        anchor.close()

    def test_alert_note(self):
        # 시작 시 뜨는 알림 포스트잇 — 말풍선과 같은 유형의 크래시 방지
        from ui.mini_widget import MiniWidget
        from ui.alert_note import AlertNote
        from ui.alerts import Alert
        anchor = MiniWidget(self.tmp)
        note = AlertNote([Alert("⏰ 마감 3일 전", "성적 입력",
                                key="ev:a1", days_left=3),
                          Alert("🗓 오늘", "교직원 회의",
                                key="ev:a2", days_left=0)],
                         anchor, on_open=lambda: None)
        note.place()
        self._show(note)
        anchor.close()

    def test_alert_note_without_anchor(self):
        # 펭귄이 아직 안 떴을 때도 화면 오른쪽 아래에 자리를 잡아야 한다
        from ui.alert_note import AlertNote
        from ui.alerts import Alert
        note = AlertNote([Alert(f"⏰ 마감 {i}일 전", f"일정 {i}",
                                key=f"ev:{i}", days_left=i)
                          for i in range(1, 10)])
        note.place()
        self._show(note)

    def test_alert_note_drop_item(self):
        """항목별 ✕ — 뗀 것만 사라지고, 다 떼면 메모지가 닫힌다."""
        from ui.alert_note import AlertNote
        from ui.alerts import Alert
        dropped = []
        alerts = [Alert("⏰ 마감 1일 전", "성적", key="ev:a1", days_left=1),
                  Alert("🗓 오늘", "교직원 회의", key="ev:a2", days_left=0)]
        note = AlertNote(alerts, on_dismiss=dropped.append)
        note.place()
        note.show()
        _app.processEvents()
        tall = note.height()
        note.drop_item(alerts[0])
        for _ in range(3):      # 크기 조절은 다음 프레임에 일어난다
            _app.processEvents()
        self.assertEqual(dropped, [alerts[0]])
        # 뗀 줄은 레이아웃에서 빠지고, 메모지도 그만큼 줄어든다
        self.assertEqual([a for a, _r, _l in note._rows], [alerts[1]])
        self.assertLess(note.height(), tall)
        note.drop_item(alerts[0])       # 이미 뗀 줄을 또 눌러도 조용하다
        self.assertEqual(dropped, [alerts[0]])
        note.drop_item(alerts[1])       # 마지막 줄까지 떼면 닫힌다
        self.assertEqual(dropped, alerts)
        _app.processEvents()
        note.close()

    def test_bubble_click_does_not_open_today_widget(self):
        """안내 말풍선을 넘긴다고 '오늘 할 일' 위젯이 켜지면 안 된다.

        시작 알림이 포스트잇으로 바뀌기 전의 잔재였다 (2026-09-01 제거).
        """
        from PyQt6.QtCore import QPoint, QPointF, Qt
        from PyQt6.QtGui import QMouseEvent
        from ui.alerts import AlertBubble
        from ui.mini_widget import MiniWidget
        from parser.pipeline import desk_conf
        anchor = MiniWidget(self.tmp)
        self.assertFalse(desk_conf(anchor.config, "today").get("enabled"))
        bubble = AlertBubble(["안내 1", "안내 2"], anchor)
        bubble.show()
        _app.processEvents()
        for _ in range(2):          # 두 장 다 넘긴다
            bubble.mousePressEvent(QMouseEvent(
                QMouseEvent.Type.MouseButtonPress, QPointF(5, 5),
                Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton,
                Qt.KeyboardModifier.NoModifier))
        _app.processEvents()
        self.assertFalse(desk_conf(anchor.config, "today").get("enabled"))
        anchor.close()

    def test_show_alert_note_end_to_end(self):
        """시작 경로 전체 — 설정을 읽고, 뗀 것을 거르고, 포스트잇을 띄운다."""
        from datetime import timedelta
        from ui import alerts as alerts_mod

        from PyQt6.QtWidgets import QWidget

        class Stub(QWidget):   # WidgetBase 대신 최소한의 것만 (앵커라 위젯이어야)
            pass

        w = Stub()
        w.config = dict(self.conf)
        w.base_dir = self.tmp
        w.store = self.store
        w.open_calendar = lambda: None
        tomorrow = datetime.combine(date.today() + timedelta(days=1),
                                    datetime.min.time())
        ev = self.store.add("내일 마감", tomorrow, is_deadline=True)

        alerts_mod._show_alert_note(w)
        _app.processEvents()
        self.assertEqual(len(w._alert_note._rows), 1)
        self.assertIn("내일 마감", w._alert_note._rows[0][0].title)

        # ✕로 떼면 기록되고, 다음 번에는 뜨지 않는다
        w._alert_note.drop_item(w._alert_note._rows[0][0])
        _app.processEvents()
        self.assertIn(f"ev:{ev.id}", w.config["alert_dismissed"])
        w._alert_note = None
        alerts_mod._show_alert_note(w)
        _app.processEvents()
        self.assertIsNone(w._alert_note)

        # 설정에서 끄면 아무것도 안 뜬다
        w.config["alert_dismissed"] = {}
        w.config["alert_enabled"] = False
        alerts_mod._show_alert_note(w)
        self.assertIsNone(w._alert_note)

    def test_alert_note_calendar_does_not_dismiss(self):
        """'캘린더 열기'는 알림을 뗀 것이 아니다 — 기억하지 않는다."""
        from ui.alert_note import AlertNote
        from ui.alerts import Alert
        dropped, opened = [], []
        alerts = [Alert("⏰ 마감 1일 전", "성적", key="ev:a1", days_left=1)]
        note = AlertNote(alerts, on_open=lambda: opened.append(1),
                         on_dismiss=dropped.append)
        note.show()
        _app.processEvents()
        note._open_calendar()
        self.assertEqual(opened, [1])
        self.assertEqual(dropped, [])
        _app.processEvents()
        note.close()

    def test_alert_note_close_remembers_rest(self):
        """머리글 ✕ — 남아 있던 줄은 전부 '봤다'로 기억한다."""
        from ui.alert_note import AlertNote
        from ui.alerts import Alert
        dropped = []
        alerts = [Alert("⏰ 마감 1일 전", "성적", key="ev:a1", days_left=1),
                  Alert("⏰ 마감 3일 전", "협의록", key="ev:a2", days_left=3)]
        note = AlertNote(alerts, on_dismiss=dropped.append)
        note.show()
        _app.processEvents()
        note.dismiss()
        self.assertEqual(dropped, alerts)
        _app.processEvents()
        note.close()

    def test_all_windows(self):
        from ui.floating_widget import FloatingWidget
        from ui.calendar_view import CalendarWindow, EventItemCard
        from ui.settings_dialog import SettingsDialog
        from ui.quick_dialog import QuickDialog
        from ui.proof_dialog import ProofDialog
        from ui.update_dialog import UpdateDialog
        from ui.desk_widgets import (
            SimpleTodoWidget, WeeklyWidget, PlannerWidget,
            DayDetailDialog, EditPopup, AddEventDialog)
        from ui.favorites_view import FavoritesTab
        from ui.help_dot import HelpDot

        self._show(FloatingWidget(self.tmp))
        self._show(CalendarWindow(self.store, fav_store=self.fav,
                                  favorites_enabled=True))
        self._show(SettingsDialog(self.tmp, self.conf, self.store))
        self._show(QuickDialog(self.tmp, self.store))
        self._show(ProofDialog(self.conf))
        self._show(UpdateDialog({"version": "9.9.9", "url": "x",
                                 "notes": "제목\n\n- 항목"}))
        for cls in (SimpleTodoWidget, WeeklyWidget, PlannerWidget):
            kind = {"SimpleTodoWidget": "simple", "WeeklyWidget": "weekly",
                    "PlannerWidget": "planner"}[cls.__name__]
            self._show(cls(self.store, self.conf, self.tmp,
                           dict(self.conf["desk_widgets"][kind])))
        self._show(DayDetailDialog(self.store, date(2026, 7, 22)))
        self._show(EditPopup(self.ev, self.store))
        self._show(AddEventDialog(self.store))
        self._show(EventItemCard(self.ev, self.store, lambda **k: None,
                                 full=True))
        self._show(FavoritesTab(self.fav))
        self._show(HelpDot("도움말"))


if __name__ == "__main__":
    unittest.main()
