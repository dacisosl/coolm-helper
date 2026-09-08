# -*- coding: utf-8 -*-
"""⚡ 간편 등록(포스트잇 직행)과 자는 무드 조건 회귀 테스트."""
import os
import sys
import tempfile
import time
import unittest
from datetime import date, datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from parser.pipeline import Message, candidates_from_message
from store.event_store import EventStore


class _Owner:
    """WidgetBase 대역 — 등록·핀만 확인한다."""

    def __init__(self, tmp):
        self.base_dir = tmp
        self.store = EventStore(tmp)
        self.config = {"desk_widgets": {"notes": []}}
        self.changed = 0

    def on_events_changed(self):
        self.changed += 1


class TestQuickRegister(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.owner = _Owner(self.tmp)

    def _run(self, title, body, cands=None, matched=False):
        from ui import quick_capture
        msg = Message(-1, "교무기획부", datetime(2026, 7, 26, 9, 0), title, body)
        if cands is None:
            cands = candidates_from_message(msg, set())
        # pin_note는 실행 중인 앱 컨텍스트가 필요하므로 호출만 확인
        called = []
        orig = quick_capture._register_and_pin.__globals__
        import ui.desk_base as desk_base
        real = desk_base.pin_note
        desk_base.pin_note = lambda eid: called.append(eid) or True
        try:
            ok = quick_capture._register_and_pin(self.owner, cands, msg, matched)
        finally:
            desk_base.pin_note = real
        return ok, called

    def test_registers_and_pins(self):
        ok, pinned = self._run("7월 30일 교직원 연수",
                               "7월 30일 오후 3시에 연수가 있습니다.")
        self.assertTrue(ok)
        events = self.owner.store.all()
        self.assertEqual(len(events), 1)
        self.assertEqual(pinned, [events[0].id])          # 포스트잇으로 붙었나

    def test_body_saved_as_memo(self):
        self._run("연수 안내", "7월 30일 오후 3시 연수. 준비물은 노트북입니다.")
        self.assertIn("노트북", self.owner.store.all()[0].memo)

    def test_no_date_still_registers(self):
        ok, pinned = self._run("제목만 있는 쪽지", "날짜가 없는 본문", cands=[])
        self.assertTrue(ok)
        self.assertEqual(len(self.owner.store.all()), 1)
        self.assertEqual(len(pinned), 1)

    def test_empty_title_rejected(self):
        ok, pinned = self._run("", "", cands=[])
        self.assertFalse(ok)
        self.assertEqual(self.owner.store.all(), [])
        self.assertEqual(pinned, [])


class TestClipboardConfirm(unittest.TestCase):
    """클립보드에서 가져올 때만 '이 내용 등록할까요?'를 묻는다 (2026-08-02)."""

    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PyQt6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        from PyQt6.QtWidgets import QWidget

        class _QOwner(QWidget):              # quick_pin은 QObject 부모를 쓴다
            def __init__(self, tmp):
                super().__init__()
                self.base_dir = tmp
                self.store = EventStore(tmp)
                self.config = {"desk_widgets": {"notes": []}}
                self.changed = 0

            def on_events_changed(self):
                self.changed += 1

        self.tmp = tempfile.mkdtemp()
        self.owner = _QOwner(self.tmp)
        from ui import quick_capture
        self.qc = quick_capture

    def _run_fallback(self, clip_text, answer):
        """quick_pin의 클립보드 경로만 흉내 — 물음에 answer로 답한다.

        answer=False는 '취소'. 날짜를 찾은 쪽지는 날짜 선택 모달이 확인까지
        겸하므로(창이 두 번 뜨지 않게), 두 물음을 모두 가로채 어느 쪽이
        떴는지 기록한다.
        """
        from PyQt6.QtWidgets import QApplication
        QApplication.clipboard().setText(clip_text)
        asked, via = [], []
        real_confirm = self.qc.confirm_clipboard
        real_ask = self.qc.ask_dates
        import ui.desk_base as desk_base
        real_pin, desk_base.pin_note = desk_base.pin_note, lambda eid: True

        def _fake_confirm(owner, cands, msg):
            asked.append(msg)
            via.append("content")
            return answer

        def _fake_ask(owner, cands, msg, body=""):
            asked.append(msg)
            via.append("dates")
            # 취소는 None, 수락은 '첫 날짜 하나' (모달 기본값과 같다)
            return None if not answer else self.qc.date_options(cands)[:1]

        self.qc.confirm_clipboard = _fake_confirm
        self.qc.ask_dates = _fake_ask
        try:
            self.qc.quick_pin(self.owner)
            for _ in range(200):            # 백그라운드 → 시그널 전달 대기
                QApplication.processEvents()
                if asked:
                    break
                time.sleep(0.01)
            QApplication.processEvents()
        finally:
            self.qc.confirm_clipboard = real_confirm
            self.qc.ask_dates = real_ask
            desk_base.pin_note = real_pin
        return asked, via

    def test_asks_before_registering(self):
        asked, via = self._run_fallback(
            "8월 7일 오후 2시 30분 강당에서 방학식이 있습니다.", True)
        self.assertEqual(len(asked), 1)             # 딱 한 번만 묻는다
        self.assertEqual(via, ["dates"])            # 날짜가 있으니 날짜 모달로
        self.assertEqual(len(self.owner.store.all()), 1)

    def test_cancel_registers_nothing(self):
        asked, _ = self._run_fallback(
            "8월 7일 오후 2시 30분 강당에서 방학식이 있습니다.", False)
        self.assertEqual(len(asked), 1)
        self.assertEqual(self.owner.store.all(), [])

    def test_no_date_uses_content_confirm(self):
        # 날짜가 없으면 예전처럼 '이 내용 등록할까요?' 확인만 뜬다
        asked, via = self._run_fallback(
            "특별한 날짜 없이 안내드리는 사항입니다. 참고해 주세요.", True)
        self.assertEqual(len(asked), 1)
        self.assertEqual(via, ["content"])

    def test_content_confirm_is_clipboard_only(self):
        # '이 내용 맞나요?' 확인은 클립보드 경로에만 — 화면에서 읽은 쪽지는
        # '지금 보고 있는 것'이라 내용을 되묻지 않는다.
        # (날짜 선택은 별개다 — 두 경로 모두 묻는다. 아래 TestDatePick 참고)
        src = open(os.path.join(os.path.dirname(__file__), "..", "ui",
                                "quick_capture.py"), encoding="utf-8").read()
        head, _, tail = src.partition("def _fallback")
        body, _, rest = tail.partition("def _finish")
        self.assertIn("confirm_clipboard", body)      # 클립보드 경로엔 있고
        self.assertNotIn("confirm_clipboard", rest)   # 화면 경로엔 없다

    def test_dialog_shows_content(self):
        dlg = self.qc.ClipboardConfirmDialog(
            "방학식", "8/7(금) 14:30", "강당에서 방학식이 있습니다.")
        texts = [w.text() for w in dlg.findChildren(
            __import__("PyQt6.QtWidgets", fromlist=["QLabel"]).QLabel)]
        self.assertTrue(any("등록하시겠습니까" in t for t in texts))
        self.assertTrue(any("8/7(금) 14:30" in t for t in texts))

    def test_long_body_truncated(self):
        long = "가" * 2000
        dlg = self.qc.ClipboardConfirmDialog("긴 쪽지", "8/7(금)", long)
        from PyQt6.QtWidgets import QTextEdit
        view = dlg.findChild(QTextEdit)
        self.assertLess(len(view.toPlainText()),
                        dlg.PREVIEW_CHARS + 10)


class TestDatePick(unittest.TestCase):
    """본문에서 날짜를 찾았을 때 어느 날짜로 넣을지 묻는다 (2026-09-03 요청).

    - 여러 개 체크 → 날짜마다 하나씩 등록
    - 아무것도 체크 안 함 → 오늘 날짜로 등록
    - 취소 → 아무것도 등록되지 않음
    """

    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PyQt6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.owner = _Owner(self.tmp)
        from ui import quick_capture
        self.qc = quick_capture
        self.msg = Message(-1, "교무기획부", datetime(2026, 7, 26, 9, 0),
                           "연수 안내",
                           "7월 30일 오후 3시 연수, 8월 5일 오후 2시 워크숍이 있습니다.")
        self.cands = candidates_from_message(self.msg, set())

    def _register(self, chosen):
        import ui.desk_base as desk_base
        pinned = []
        real, desk_base.pin_note = desk_base.pin_note, lambda eid: pinned.append(eid)
        try:
            n = self.qc._register_and_pin(self.owner, self.cands, self.msg,
                                          False, chosen)
        finally:
            desk_base.pin_note = real
        return n, pinned

    def test_two_dates_offered(self):
        opts = self.qc.date_options(self.cands)
        days = {c.start.date() for c in opts}
        self.assertIn(date(2026, 7, 30), days)
        self.assertIn(date(2026, 8, 5), days)

    def test_duplicate_dates_collapsed(self):
        doubled = self.cands + self.cands
        self.assertEqual(len(self.qc.date_options(doubled)),
                         len(self.qc.date_options(self.cands)))

    def test_option_cap(self):
        many = self.cands * 20
        self.assertLessEqual(len(self.qc.date_options(many)),
                             self.qc.MAX_DATE_OPTIONS)

    def test_registers_every_checked_date(self):
        opts = self.qc.date_options(self.cands)[:2]
        n, pinned = self._register(opts)
        self.assertEqual(n, 2)
        self.assertEqual(len(self.owner.store.all()), 2)
        self.assertEqual(len(pinned), 2)          # 각각 포스트잇으로 붙는다
        days = {e.start_dt.date() for e in self.owner.store.all()}
        self.assertEqual(days, {c.start.date() for c in opts})

    def test_nothing_checked_falls_back_to_today(self):
        n, _ = self._register([])
        self.assertEqual(n, 1)
        self.assertEqual(self.owner.store.all()[0].start_dt.date(),
                         date.today())

    def test_dialog_prechecks_first_only(self):
        opts = self.qc.date_options(self.cands)
        dlg = self.qc.DatePickDialog(opts)
        self.assertEqual([cb.isChecked() for cb in dlg.checks],
                         [True] + [False] * (len(opts) - 1))
        # 기본값 그대로면 예전과 같은 날짜 하나가 등록된다
        self.assertEqual(dlg.chosen(), [opts[0]])

    def test_dialog_lists_all_dates(self):
        opts = self.qc.date_options(self.cands)
        dlg = self.qc.DatePickDialog(opts)
        self.assertEqual(len(dlg.checks), len(opts))
        labels = " ".join(cb.text() for cb in dlg.checks)
        self.assertIn("7/30", labels)
        self.assertIn("8/5", labels)

    def test_dialog_question_and_hint(self):
        from PyQt6.QtWidgets import QLabel
        dlg = self.qc.DatePickDialog(self.qc.date_options(self.cands))
        texts = " ".join(w.text() for w in dlg.findChildren(QLabel))
        self.assertIn("어떤 날짜에 일정을 등록하시겠습니까?", texts)
        self.assertIn("오늘 날짜로 등록", texts)      # 안 고르면 어떻게 되는지

    def test_cancel_returns_none(self):
        from PyQt6.QtWidgets import QDialog

        class _Rejected(self.qc.DatePickDialog):
            def exec(self):
                return QDialog.DialogCode.Rejected

        real, self.qc.DatePickDialog = self.qc.DatePickDialog, _Rejected
        try:
            self.assertIsNone(self.qc.ask_dates(None, self.cands, self.msg))
        finally:
            self.qc.DatePickDialog = real

    def test_no_dates_asks_nothing(self):
        # 날짜를 못 찾았으면 모달 없이 예전처럼 오늘로 등록한다
        self.assertEqual(self.qc.ask_dates(None, [], self.msg), [])

    def test_screen_path_asks_when_dates_found(self):
        src = open(os.path.join(os.path.dirname(__file__), "..", "ui",
                                "quick_capture.py"), encoding="utf-8").read()
        _, _, screen = src.partition("def _on_screen")
        self.assertIn("ask_dates", screen)
        self.assertIn("loader.done.connect", src)
        self.assertIn("_on_screen(*r)", src)      # 화면 경로가 실제로 연결됐나

    def test_option_label_readable(self):
        opts = self.qc.date_options(self.cands)
        label = self.qc.option_label(opts[0])
        self.assertIn("7/30", label)
        self.assertIn("오후 3:00", label)


class TestDatePickLayout(unittest.TestCase):
    """날짜 선택 모달 2차 개선 (2026-09-03): 날짜순 · 본문 · 화면 가운데.

    본문에 늦은 날짜가 먼저 나오는 쪽지로, 정렬이 실제로 일어나는지 본다.
    """

    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PyQt6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        from ui import quick_capture
        self.qc = quick_capture
        self.msg = Message(
            -1, "교무기획부", datetime(2026, 9, 1, 9, 0),
            "2학기 1회 정기시험 출제 안내",
            "안녕하세요. 출제 원고는 9월 16일까지 제출해 주세요.\n"
            "9월 9일 출제 협의회를 진행합니다.\n"
            "9월 11일 문항 검토가 있습니다.")
        self.cands = candidates_from_message(self.msg, set())

    def test_options_sorted_by_date(self):
        opts = self.qc.date_options(self.cands)
        days = [c.start.date() for c in opts]
        self.assertEqual(days, sorted(days))
        # 본문 순서(16→9→11)와 다르게 정렬됐는지 = 정렬이 실제로 일어났나
        self.assertNotEqual(days, [c.start.date() for c in self.cands])
        self.assertEqual(days[0], date(2026, 9, 9))

    def test_auto_pick_stays_checked_after_sorting(self):
        """정렬로 자리가 밀려도 '예전에 자동 등록되던 날짜'가 체크된다."""
        opts = self.qc.date_options(self.cands)
        dlg = self.qc.DatePickDialog(opts, default=self.cands[0])
        self.assertEqual(dlg.chosen(), [self.cands[0]])
        # 그 후보는 첫 줄이 아니다 (첫 줄만 체크하는 옛 방식이면 실패한다)
        self.assertNotEqual(opts[0].start, self.cands[0].start)

    def test_context_shows_where_the_date_came_from(self):
        opts = self.qc.date_options(self.cands)
        by_day = {c.start.date(): c for c in opts}
        self.assertIn("협의회", self.qc.source_context(by_day[date(2026, 9, 9)]))
        self.assertIn("제출", self.qc.source_context(by_day[date(2026, 9, 16)]))

    def test_body_pane_has_full_message(self):
        from PyQt6.QtWidgets import QTextEdit
        opts = self.qc.date_options(self.cands)
        dlg = self.qc.DatePickDialog(opts)
        views = dlg.findChildren(QTextEdit)
        self.assertTrue(views)
        text = views[0].toPlainText()
        self.assertIn("출제 협의회", text)        # 본문이 그대로 보인다
        self.assertIn("정기시험 출제 안내", text)  # 제목도 함께

    def test_clicking_date_highlights_it_in_body(self):
        opts = self.qc.date_options(self.cands)
        dlg = self.qc.DatePickDialog(opts)
        self.assertTrue(dlg.show_in_body(0))
        self.assertIn("9월 9일", dlg.body_view.textCursor().selectedText())

    def test_row_click_toggles_check(self):
        opts = self.qc.date_options(self.cands)
        dlg = self.qc.DatePickDialog(opts, default=opts[0])
        dlg._on_row_clicked(1)
        self.assertEqual(len(dlg.chosen()), 2)     # 첫 줄 + 방금 누른 줄
        dlg._on_row_clicked(1)
        self.assertEqual(dlg.chosen(), [opts[0]])

    def _duplicate_title_msg(self):
        """제목이 본문 줄과 똑같은 쪽지 — 부재중 쪽지가 이렇게 온다 (2026-09-04)."""
        line = "빈칸 작성하셔서 다음주 화요일까지 보내주세요~!"
        msg = Message(-1, "교무기획부", datetime(2026, 9, 4, 9, 0), line,
                      "\n" + line)
        return msg, candidates_from_message(msg, set())

    def test_display_text_drops_duplicated_title(self):
        msg, cands = self._duplicate_title_msg()
        text, to_body = self.qc.display_text(cands[0])
        self.assertEqual(text.count("빈칸 작성하셔서"), 1)      # 한 번만
        # 제목에 있던 위치가 본문의 같은 문장으로 옮겨진다
        title_pos = msg.title.index("다음주")
        self.assertEqual(text[to_body(title_pos):to_body(title_pos) + 3], "다음주")

    def test_display_text_keeps_distinct_title(self):
        text, to_body = self.qc.display_text(self.cands[0])
        self.assertIn("정기시험 출제 안내", text)                 # 제목 그대로
        self.assertEqual(to_body(7), 7)                           # 위치도 그대로

    def test_body_pane_shows_duplicated_line_once(self):
        from PyQt6.QtWidgets import QTextEdit
        msg, cands = self._duplicate_title_msg()
        dlg = self.qc.DatePickDialog(self.qc.date_options(cands))
        text = dlg.findChildren(QTextEdit)[0].toPlainText()
        self.assertEqual(text.count("빈칸 작성하셔서"), 1)
        # 제목에서 찾은 날짜라도 본문 쪽에 하이라이트가 남아야 한다
        self.assertTrue(dlg.show_in_body(0))
        self.assertIn("화요일", dlg.body_view.textCursor().selectedText())

    def test_opens_at_screen_center(self):
        from PyQt6.QtWidgets import QApplication
        opts = self.qc.date_options(self.cands)
        dlg = self.qc.DatePickDialog(opts)
        dlg.show()
        try:
            g = QApplication.primaryScreen().availableGeometry()
            center = dlg.geometry().center()
            # 정확히 한가운데(창 테두리 오차 정도만 허용)
            self.assertAlmostEqual(center.x(), g.center().x(), delta=40)
            self.assertAlmostEqual(center.y(), g.center().y(), delta=40)
        finally:
            dlg.close()


class TestSleepMood(unittest.TestCase):
    """완료한 일은 '남은 할 일'이 아니다 — 다 끝내면 자야 한다."""

    def setUp(self):
        self.store = EventStore(tempfile.mkdtemp())

    def _left(self):
        overdue, today, _ = self.store.sections(date.today())
        return overdue, [e for e in today if not e.done]

    def test_sleeps_when_empty(self):
        overdue, left = self._left()
        self.assertFalse(overdue or left)

    def test_awake_with_open_task(self):
        self.store.add("할 일", datetime.now(), is_deadline=True)
        _, left = self._left()
        self.assertTrue(left)

    def test_sleeps_after_completing_today(self):
        ev = self.store.add("할 일", datetime.now(), is_deadline=True)
        self.store.set_done(ev.id, True)
        overdue, left = self._left()
        self.assertFalse(overdue or left)      # 예전엔 여기서 깨어 있었다

    def test_awake_with_overdue(self):
        self.store.add("지난 마감", datetime.now() - timedelta(days=2),
                       is_deadline=True)
        overdue, _ = self._left()
        self.assertTrue(overdue)



class TestOldMessageDates(unittest.TestCase):
    """오랜 시간이 지난 뒤 쪽지를 열어도 날짜가 제대로 잡혀야 한다.

    (2026-08-02 사용자 지적: 6월 쪽지를 8월에 열면 2027년으로 밀렸다)
    """

    def setUp(self):
        from parser import pipeline
        self.pipeline = pipeline
        self.now = datetime(2026, 8, 2, 10, 0)
        self.msg = Message(-1, "(화면에서 가져옴)", self.now,
                           "6월 5일 회의 안내",
                           "지난 번에 안내드렸듯이 6월 5일에 회의가 있습니다.")

    def test_past_date_kept_when_allowed(self):
        # 기본(allow_past=False)은 수신일 이후만 남긴다
        normal = self.pipeline.candidates_from_message(self.msg, set())
        loose = self.pipeline.candidates_from_message(self.msg, set(),
                                                      allow_past=True)
        self.assertGreaterEqual(len(loose), len(normal))

    def test_year_pulled_back_to_this_year(self):
        cands = self.pipeline.candidates_from_message(self.msg, set(),
                                                      allow_past=True)
        fixed = [self.pipeline._pull_back_year(c, self.now) for c in cands]
        self.assertTrue(any(c.start.date() == date(2026, 6, 5) for c in fixed))

    def test_future_date_untouched(self):
        msg = Message(-1, "(화면)", self.now, "9월 3일 연수", "9월 3일 오후 2시 연수")
        cands = self.pipeline.candidates_from_message(msg, set(), allow_past=True)
        fixed = [self.pipeline._pull_back_year(c, self.now) for c in cands]
        self.assertTrue(all(c.start.year == 2026 for c in fixed))


if __name__ == "__main__":
    unittest.main()


class TestPrewarm(unittest.TestCase):
    """첫 ⚡ 지연 해소 — 프리워밍이 조용히, 안전하게 돌아야 한다."""

    def test_prewarm_never_raises(self):
        # 리눅스(CI)에는 Windows API가 없다 — 예외 없이 조용히 넘어가야 한다
        import capture
        capture.prewarm()

    def test_warmup_loop_wired(self):
        # 시작 워밍업이 prewarm + prefetch를 부르고 주기 루프를 갖는지
        src = open(os.path.join(os.path.dirname(__file__), "..", "ui",
                                "widget_base.py"), encoding="utf-8").read()
        self.assertIn("capture.prewarm(", src)
        self.assertIn("prefetch_quick", src)
        self.assertIn("PREWARM_SCAN_SEC", src)
        self.assertIn("PREWARM_FULL_SEC", src)

    def test_waiting_bubble_wired(self):
        # 읽기가 길어지면 '읽는 중' 안내가 뜨도록 연결됐는지
        src = open(os.path.join(os.path.dirname(__file__), "..", "ui",
                                "quick_capture.py"), encoding="utf-8").read()
        self.assertIn("읽는 중", src)
        self.assertIn("waiting.stop()", src)
