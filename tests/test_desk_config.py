# -*- coding: utf-8 -*-
"""바탕화면 위젯(v0.10.0) config 계층 테스트 — Qt 없이 순수 로직만."""
import sys, os, tempfile, shutil, unittest
from datetime import date, datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from parser.pipeline import (clamp_geometry, desk_conf, drop_monthly,
                             ensure_planner, migrate_desk_config, prune_notes,
                             DEFAULT_CONFIG)
from store.event_store import EventStore

TODAY = date(2026, 7, 20)


class TestMigrateDeskConfig(unittest.TestCase):
    def test_old_widget_on_inherits(self):
        config = {"desktop_widget_enabled": True, "desktop_widget_opacity": 75}
        self.assertTrue(migrate_desk_config(config))
        self.assertTrue(config["desk_widgets"]["weekly"]["enabled"])
        self.assertEqual(config["desk_widgets"]["weekly"]["opacity"], 75)
        self.assertTrue(config["desk_widgets"]["planner"]["enabled"])
        self.assertFalse(config["desk_widgets"]["simple"]["enabled"])
        self.assertNotIn("desktop_widget_enabled", config)
        self.assertNotIn("desktop_widget_opacity", config)
        self.assertFalse(config["desk_migration_notice_done"])   # 안내 예정

    def test_old_widget_off_defaults(self):
        config = {"desktop_widget_enabled": False}
        self.assertTrue(migrate_desk_config(config))
        for kind in ("simple", "weekly"):
            self.assertFalse(config["desk_widgets"][kind]["enabled"])
        self.assertEqual(config["desk_widgets"]["notes"], [])
        self.assertTrue(config["desk_migration_notice_done"])    # 안내 불필요

    def test_already_migrated_untouched(self):
        config = {"desk_widgets": {"weekly": {"enabled": True}}}
        self.assertFalse(migrate_desk_config(config))
        self.assertTrue(config["desk_widgets"]["weekly"]["enabled"])

    def test_planner_on_by_default(self):
        # 캘린더·할일 위젯은 빠른메뉴 아이콘을 대신하므로 항상 켜져야 한다
        config = {"desktop_widget_enabled": False}
        migrate_desk_config(config)
        self.assertTrue(config["desk_widgets"]["planner"]["enabled"])


class TestEnsurePlanner(unittest.TestCase):
    def test_adds_enabled_planner_to_v010_config(self):
        config = {"desk_widgets": {"simple": {"enabled": True}, "notes": []}}
        self.assertTrue(ensure_planner(config))
        self.assertTrue(config["desk_widgets"]["planner"]["enabled"])
        self.assertTrue(config["desk_widgets"]["simple"]["enabled"])  # 보존

    def test_noop_when_planner_present(self):
        config = {"desk_widgets": {"planner": {"enabled": False}}}
        self.assertFalse(ensure_planner(config))
        self.assertFalse(config["desk_widgets"]["planner"]["enabled"])  # 존중

    def test_noop_without_desk_widgets(self):
        self.assertFalse(ensure_planner({}))


class TestDropMonthly(unittest.TestCase):
    def test_monthly_on_moves_to_planner(self):
        config = {"desk_widgets": {
            "planner": {"enabled": False},
            "monthly": {"enabled": True, "geometry": [1, 2, 300, 300]}}}
        self.assertTrue(drop_monthly(config))
        self.assertNotIn("monthly", config["desk_widgets"])
        self.assertTrue(config["desk_widgets"]["planner"]["enabled"])

    def test_monthly_off_just_removed(self):
        config = {"desk_widgets": {"planner": {"enabled": False},
                                   "monthly": {"enabled": False}}}
        self.assertTrue(drop_monthly(config))
        self.assertFalse(config["desk_widgets"]["planner"]["enabled"])

    def test_noop_when_absent(self):
        self.assertFalse(drop_monthly({"desk_widgets": {}}))
        self.assertFalse(drop_monthly({}))


class TestDeskConf(unittest.TestCase):
    def test_fills_missing_keys(self):
        config = {"desk_widgets": {"weekly": {"enabled": True}}}
        cur = desk_conf(config, "weekly")
        self.assertTrue(cur["enabled"])
        self.assertEqual(cur["opacity"], 90)
        self.assertIsNone(cur["geometry"])
        self.assertFalse(cur["always_on_top"])

    def test_missing_desk_widgets_entirely(self):
        config = {}
        cur = desk_conf(config, "simple")
        self.assertFalse(cur["enabled"])
        self.assertEqual(desk_conf(config, "notes"), [])

    def test_returns_live_reference(self):
        config = {}
        desk_conf(config, "weekly")["enabled"] = True
        self.assertTrue(config["desk_widgets"]["weekly"]["enabled"])

    def test_default_config_not_polluted(self):
        # load_config는 깊은 복사를 쓰므로 DEFAULT_CONFIG 원본은 선언값 그대로여야 한다.
        # 기본 바탕화면 위젯 = 주간 하나만 (2026-07-23 사용자 기본값)
        self.assertTrue(DEFAULT_CONFIG["desk_widgets"]["weekly"]["enabled"])
        self.assertFalse(DEFAULT_CONFIG["desk_widgets"]["simple"]["enabled"])
        self.assertFalse(DEFAULT_CONFIG["desk_widgets"]["planner"]["enabled"])


class TestPruneNotes(unittest.TestCase):
    def test_removes_orphans_keeps_valid(self):
        config = {"desk_widgets": {"notes": [
            {"event_id": "aaa", "geometry": [0, 0, 200, 150]},
            {"event_id": "gone", "geometry": [10, 10, 200, 150]},
        ]}}
        self.assertTrue(prune_notes(config, {"aaa", "bbb"}))
        ids = [n["event_id"] for n in config["desk_widgets"]["notes"]]
        self.assertEqual(ids, ["aaa"])

    def test_no_change(self):
        config = {"desk_widgets": {"notes": [{"event_id": "aaa"}]}}
        self.assertFalse(prune_notes(config, {"aaa"}))


class TestClampGeometry(unittest.TestCase):
    SCREEN = [0, 0, 1920, 1080]

    def test_normal_rect_unchanged(self):
        self.assertEqual(clamp_geometry([100, 100, 300, 200], self.SCREEN),
                         [100, 100, 300, 200])

    def test_offscreen_returns_none(self):
        # 예: 교실 듀얼 모니터에 두었다가 노트북만 들고 온 경우
        self.assertIsNone(clamp_geometry([2500, 100, 300, 200], self.SCREEN))
        self.assertIsNone(clamp_geometry([-400, 100, 300, 200], self.SCREEN))

    def test_partial_overlap_pulled_in(self):
        self.assertEqual(clamp_geometry([1800, -50, 300, 200], self.SCREEN),
                         [1620, 0, 300, 200])

    def test_bigger_than_screen_shrunk(self):
        self.assertEqual(clamp_geometry([0, 0, 4000, 3000], self.SCREEN),
                         [0, 0, 1920, 1080])

    def test_garbage_returns_none(self):
        self.assertIsNone(clamp_geometry(None, self.SCREEN))
        self.assertIsNone(clamp_geometry([1, 2, 3], self.SCREEN))
        self.assertIsNone(clamp_geometry(["a", 0, 10, 10], self.SCREEN))


class TestSections(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.store = EventStore(self.tmp, "store")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_overdue_only_open_deadlines(self):
        self.store.add("밀린 제출", datetime(2026, 7, 18), is_deadline=True)
        done = self.store.add("끝낸 제출", datetime(2026, 7, 17), is_deadline=True)
        self.store.set_done(done.id, True)
        self.store.add("지나간 행사", datetime(2026, 7, 15))   # 마감형 아님
        overdue, _, _ = self.store.sections(TODAY)
        self.assertEqual([e.title for e in overdue], ["밀린 제출"])

    def test_today_includes_spanning(self):
        self.store.add("오늘 회의", datetime(2026, 7, 20, 14), all_day=False)
        self.store.add("긴 행사", datetime(2026, 7, 19),
                       end=datetime(2026, 7, 22))
        _, today, _ = self.store.sections(TODAY)
        self.assertEqual({e.title for e in today}, {"오늘 회의", "긴 행사"})

    def test_upcoming_within_14_days_sorted(self):
        self.store.add("먼 미래", datetime(2026, 8, 10))       # 21일 뒤 — 제외
        self.store.add("모레", datetime(2026, 7, 22))
        self.store.add("내일", datetime(2026, 7, 21))
        done = self.store.add("끝낸 미래 마감", datetime(2026, 7, 23),
                              is_deadline=True)
        self.store.set_done(done.id, True)
        _, _, upcoming = self.store.sections(TODAY)
        self.assertEqual([e.title for e in upcoming], ["내일", "모레"])

    def test_upcoming_capped_at_10(self):
        for i in range(12):
            self.store.add(f"일정{i}", datetime(2026, 7, 21 + (i % 10)))
        _, _, upcoming = self.store.sections(TODAY)
        self.assertEqual(len(upcoming), 10)


if __name__ == "__main__":
    unittest.main()


class TestAutoFontFactor(unittest.TestCase):
    """크기 연동 글씨 자동 배율 — 계단식 스냅 (v1.5.4)."""

    def test_snap_steps(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from ui.desk_base import auto_font_factor
        self.assertEqual(auto_font_factor(175, 250), 0.85)   # 0.7배 → 최소단계
        self.assertEqual(auto_font_factor(250, 250), 1.0)
        self.assertEqual(auto_font_factor(305, 250), 1.15)   # 1.22배 → 1.15
        self.assertEqual(auto_font_factor(500, 250), 1.3)    # 2배 → 최대단계
        self.assertEqual(auto_font_factor(300, 0), 1.0)      # 방어
