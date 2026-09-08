# -*- coding: utf-8 -*-
"""포스트잇 '제출' → 원본 쪽지 되찾기·보여주기 (2026-09-04)."""
import os
import shutil
import sys
import tempfile
import unittest
from datetime import datetime

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication, QLabel, QTextEdit

from store.event_store import EventStore
from test_db_reader import make_fake_db

_app = QApplication.instance() or QApplication([])


class TestParseKey(unittest.TestCase):
    def test_cases(self):
        from ui.reply_helper import parse_source_key, sender_name
        self.assertEqual(parse_source_key("3841|2026-08-05T15:00:00"), 3841)
        self.assertIsNone(parse_source_key(""))
        self.assertIsNone(parse_source_key("-1|2026-08-05T15:00:00"))   # 화면 등록
        self.assertIsNone(parse_source_key("neis:7010|x"))              # 나이스 표식
        self.assertEqual(sender_name("정주은(정주은)"), "정주은")
        self.assertEqual(sender_name("교무기획부"), "교무기획부")


class TestFindSource(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.memo = os.path.join(self.tmp, "memo")
        os.makedirs(self.memo)
        make_fake_db(self.memo, unread=1, read=2)      # key 1,2(읽음) 3(안읽음)
        self.store = EventStore(os.path.join(self.tmp, "store"))
        self.config = {"memo_dir": self.memo, "desk_widgets": {"notes": []}}

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _event(self, ref):
        return self.store.add("일정", datetime(2026, 7, 20, 9, 0),
                              memo="등록 때 메모", source_ref=ref)

    def test_finds_original(self):
        from ui.reply_helper import find_source_message
        msg, spans = find_source_message(self.tmp, self.config,
                                         self._event("2|2026-07-20T09:00:00"))
        self.assertIsNotNone(msg)
        self.assertEqual(msg.key, 2)
        self.assertEqual(msg.sender, "발신자")
        self.assertEqual(msg.title, "읽은쪽지2")
        self.assertIsInstance(spans, list)

    def test_missing_key_returns_none(self):
        from ui.reply_helper import find_source_message
        msg, _ = find_source_message(self.tmp, self.config,
                                     self._event("999|2026-07-20T09:00:00"))
        self.assertIsNone(msg)

    def test_no_ref_returns_none_without_touching_db(self):
        from ui.reply_helper import find_source_message
        self.assertEqual(find_source_message(self.tmp, self.config,
                                             self._event("")), (None, []))
        self.assertEqual(find_source_message(self.tmp, {}, self._event("2|x")),
                         (None, []))


class TestDialog(unittest.TestCase):
    def setUp(self):
        from parser.db_reader import Message
        self.store = EventStore(tempfile.mkdtemp())
        self.ev = self.store.add("일정", datetime(2026, 7, 20, 9, 0),
                                 memo="등록 때 저장한 본문", source_ref="")
        self.msg = Message(7, "정주은(정주은)", datetime(2026, 7, 18, 14, 30),
                           "출제 안내", "빈칸 작성하셔서 화요일까지 보내주세요")

    def _labels(self, dlg):
        return " ".join(w.text() for w in dlg.findChildren(QLabel))

    def test_shows_sender_and_body(self):
        from ui.reply_helper import SourceMessageDialog
        dlg = SourceMessageDialog(self.ev, self.msg, [])
        self.assertIn("정주은 선생님이 보낸 쪽지", self._labels(dlg))
        self.assertIn("7/18", self._labels(dlg))
        self.assertIn("출제 안내", self._labels(dlg))
        self.assertIn("화요일까지", dlg.body_view.toPlainText())
        self.assertTrue(dlg.copy_btn.isEnabled())

    def test_copy_puts_name_on_clipboard(self):
        from ui.reply_helper import SourceMessageDialog
        dlg = SourceMessageDialog(self.ev, self.msg, [])
        dlg.copy_name()
        self.assertEqual(QApplication.clipboard().text(), "정주은")
        self.assertIn("복사했어요", dlg.status.text())

    def test_fallback_shows_memo(self):
        from ui.reply_helper import SourceMessageDialog
        dlg = SourceMessageDialog(self.ev, None, [])
        self.assertIn("찾지 못했어요", self._labels(dlg))
        self.assertIn("등록 때 저장한 본문", dlg.body_view.toPlainText())
        self.assertFalse(dlg.copy_btn.isEnabled())

    def test_pii_marked_red_not_masked(self):
        from parser import pii_detector
        from ui.reply_helper import SourceMessageDialog
        body = "홍길동 학생 보호자 010-1234-5678로 연락 바랍니다."
        msg = type(self.msg)(8, "담임", datetime(2026, 7, 18, 9, 0), "연락", body)
        spans = pii_detector.detect(body, {"홍길동"})
        dlg = SourceMessageDialog(self.ev, msg, spans)
        self.assertIn("010-1234-5678", dlg.body_view.toPlainText())   # 가리지 않고
        self.assertIn("color:", dlg.body_view.toHtml())                # 표시만

    def test_bring_to_front_quiet_off_windows(self):
        try:
            import capture
        except Exception as e:                       # 리눅스에서 import 자체가 안 되면
            self.skipTest(f"capture import 불가: {e}")
        self.assertFalse(capture.bring_to_front())
        # 화면 구조 진단도 죽지 않고 안내 문구를 돌려준다. 문구는 환경에 따라
        # 다르다 — 리눅스는 "윈도우에서만", 쿨메신저 없는 윈도우(빌드 서버)는
        # "쿨메신저 프로세스를 찾지 못했어요". 둘 중 하나면 정상이다.
        text = capture.dump_ui_tree()
        self.assertTrue(
            "윈도우에서만" in text or "쿨메신저 프로세스를 찾지 못했어요" in text,
            f"예상 못한 진단 결과: {text[:120]}")


class TestOpenFlow(unittest.TestCase):
    """'제출' → 보낸 사람에게 쪽지 쓰기 (2026-09-08 재설계)."""

    def setUp(self):
        import time
        from PyQt6.QtWidgets import QWidget
        self.time = time
        self.tmp = tempfile.mkdtemp()
        self.memo = os.path.join(self.tmp, "memo")
        os.makedirs(self.memo)
        make_fake_db(self.memo, unread=1, read=2)      # key 2 = 발신자
        self.store = EventStore(os.path.join(self.tmp, "store"))

        class _Note(QWidget):
            pass

        self.note = _Note()
        self.note.base_dir = self.tmp
        self.note.store = self.store
        self.note.config = {"memo_dir": self.memo, "desk_widgets": {"notes": []}}

    def tearDown(self):
        self.note.close()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _event(self, sender="", ref="2|2026-07-20T09:00:00"):
        ev = self.store.add("일정", datetime(2026, 7, 20, 9, 0), memo="메모",
                            source_ref=ref, sender=sender)
        self.note.event = ev
        return ev

    def _run(self, result, typed=None):
        """compose_to를 가짜로 바꿔 흐름만 확인. typed면 이름 모달에 그 이름을 적는다."""
        import coolm_control
        import ui.reply_helper as rh
        asked, composed, fallbacks, infos = [], [], [], []
        real = (coolm_control.compose_to, rh.SourceMessageDialog.exec,
                rh.NameAskDialog.exec, rh.InfoDialog.exec)

        def _compose(name, ui=None):
            composed.append(name)
            return result

        def _ask(dlg):
            asked.append(dlg)
            if typed is None:
                return 0                       # 취소
            dlg.edit.setText(typed)
            return 1                           # Accepted

        coolm_control.compose_to = _compose
        rh.SourceMessageDialog.exec = lambda self: fallbacks.append(self) or 0
        rh.NameAskDialog.exec = _ask
        rh.InfoDialog.exec = lambda self: infos.append(self) or 0
        try:
            rh.open_source_message(self.note)
            for _ in range(300):
                QApplication.processEvents()
                if self.note._source_result is not None:
                    break
                self.time.sleep(0.01)
        finally:
            (coolm_control.compose_to, rh.SourceMessageDialog.exec,
             rh.NameAskDialog.exec, rh.InfoDialog.exec) = real
        return {"asked": asked, "composed": composed,
                "fallbacks": fallbacks, "infos": infos}

    def test_uses_saved_sender_without_touching_db(self):
        import ui.reply_helper as rh
        self._event(sender="정주은(정주은)")
        real = rh.find_source_message
        rh.find_source_message = lambda *a, **k: (_ for _ in ()).throw(
            AssertionError("저장된 이름이 있으면 DB를 보지 않아야 한다"))
        try:
            out = self._run(("opened", ""))
        finally:
            rh.find_source_message = real
        self.assertEqual(out["composed"], ["정주은(정주은)"])
        self.assertEqual(out["asked"], [])
        self.assertEqual(out["fallbacks"], [])

    def test_backfills_sender_from_db_and_remembers(self):
        ev = self._event(sender="")
        out = self._run(("opened", ""))
        self.assertEqual(out["composed"], ["발신자"])      # 가짜 DB의 보낸 사람
        self.assertEqual(out["asked"], [])
        # 일정에 기억됐다 — 다음부터 DB를 안 본다
        saved = [e for e in EventStore(
            os.path.join(self.tmp, "store")).all() if e.id == ev.id][0]
        self.assertEqual(saved.sender, "발신자")

    def test_asks_name_when_unknown_and_remembers(self):
        ev = self._event(sender="", ref="")               # DB로도 못 찾음
        out = self._run(("opened", ""), typed="정주은")
        self.assertEqual(len(out["asked"]), 1)
        self.assertEqual(out["composed"], ["정주은"])
        saved = [e for e in EventStore(
            os.path.join(self.tmp, "store")).all() if e.id == ev.id][0]
        self.assertEqual(saved.sender, "정주은")

    def test_cancelling_name_does_nothing(self):
        self._event(sender="", ref="")
        out = self._run(("opened", ""), typed=None)
        self.assertEqual(out["composed"], [])
        self.assertEqual(self.note._source_result, ("cancelled", ""))

    def test_selected_shows_info(self):
        self._event(sender="정주은")
        out = self._run(("selected", "더블클릭하면 열려요"))
        self.assertEqual(len(out["infos"]), 1)
        self.assertEqual(out["fallbacks"], [])

    def test_failed_shows_fallback_with_reason(self):
        self._event(sender="정주은")
        out = self._run(("failed", "조직도에서 못 찾았어요"))
        self.assertEqual(len(out["fallbacks"]), 1)
        self.assertIn("못 찾았어요", out["fallbacks"][0].status.text())


if __name__ == "__main__":
    unittest.main(verbosity=2)
