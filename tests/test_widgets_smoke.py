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
