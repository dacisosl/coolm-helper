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
    """'제출' → 쿨메신저에서 열기를 먼저 시도하고, 실패할 때만 대체 창 (2026-09-08)."""

    def setUp(self):
        import time
        from PyQt6.QtWidgets import QWidget
        self.time = time
        self.tmp = tempfile.mkdtemp()
        memo = os.path.join(self.tmp, "memo")
        os.makedirs(memo)
        make_fake_db(memo, unread=1, read=2)
        store = EventStore(os.path.join(self.tmp, "store"))
        ev = store.add("일정", datetime(2026, 7, 20, 9, 0), memo="메모",
                       source_ref="2|2026-07-20T09:00:00")

        class _Note(QWidget):
            pass

        self.note = _Note()
        self.note.base_dir, self.note.event = self.tmp, ev
        self.note.config = {"memo_dir": memo, "desk_widgets": {"notes": []}}

    def tearDown(self):
        self.note.close()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _run(self, result):
        import coolm_control
        import ui.reply_helper as rh
        created = []
        real_open, real_exec = coolm_control.open_message, rh.SourceMessageDialog.exec
        coolm_control.open_message = lambda msg, ui=None: result
        rh.SourceMessageDialog.exec = lambda self: created.append(self) or 0
        try:
            rh.open_source_message(self.note)
            for _ in range(300):                 # 백그라운드 → 시그널 대기
                QApplication.processEvents()
                if self.note._source_result is not None:
                    break
                self.time.sleep(0.01)
        finally:
            coolm_control.open_message = real_open
            rh.SourceMessageDialog.exec = real_exec
        return created

    def test_opens_in_coolm_without_dialog(self):
        created = self._run((True, ""))
        self.assertEqual(self.note._source_result, (True, ""))
        self.assertEqual(created, [])                # 쿨메신저가 열렸으니 창 없음

    def test_fallback_dialog_with_reason(self):
        created = self._run((False, "메시지 관리함을 열지 못했어요."))
        self.assertEqual(len(created), 1)
        self.assertIn("관리함을 열지 못했어요", created[0].status.text())
        self.assertIn("정주은" if False else "발신자", " ".join(
            w.text() for w in created[0].findChildren(QLabel)))  # 원본 보낸 사람


if __name__ == "__main__":
    unittest.main(verbosity=2)
