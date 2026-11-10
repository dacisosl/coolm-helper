# -*- coding: utf-8 -*-
"""내 할 일 저장소 (store/todos.json) — '일정 · 할 일 보드'용 (2026-11-10)."""
import json
import os
import shutil
import sys
import tempfile
import unittest
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from store.todo_store import TodoStore


class TestTodoStore(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.st = TodoStore(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _again(self):
        return TodoStore(self.tmp)

    def test_add_and_reload(self):
        t = self.st.add("  수행평가 준비 ", event_id="ev1", day=date(2026, 11, 12))
        self.assertEqual(t.title, "수행평가 준비")
        again = self._again().all()
        self.assertEqual([(x.title, x.event_id, x.day) for x in again],
                         [("수행평가 준비", "ev1", "2026-11-12")])

    def test_empty_title_ignored(self):
        self.assertIsNone(self.st.add("   "))
        self.assertEqual(self.st.all(), [])

    def test_toggle_sets_done_at(self):
        t = self.st.add("시험문제 만들기")
        self.st.toggle(t.id)
        got = self._again().get(t.id)
        self.assertTrue(got.done)
        self.assertIsNotNone(got.done_date)
        self.st.toggle(t.id, False)
        self.assertEqual(self._again().get(t.id).done_at, "")

    def test_update_and_remove(self):
        t = self.st.add("수업준비")
        self.st.update(t.id, title="수업준비 (8·9차시)", event_id="")
        self.assertEqual(self._again().get(t.id).title, "수업준비 (8·9차시)")
        self.st.remove(t.id)
        self.assertEqual(self._again().all(), [])

    def test_order_follows_adding(self):
        a, b = self.st.add("첫째"), self.st.add("둘째")
        self.assertEqual([t.id for t in self.st.all()], [a.id, b.id])

    def test_for_event_and_day(self):
        self.st.add("A", event_id="ev1")
        self.st.add("B", day=date(2026, 11, 10))
        self.st.add("C")
        self.assertEqual([t.title for t in self.st.for_event("ev1")], ["A"])
        self.assertEqual([t.title for t in self.st.for_day(date(2026, 11, 10))], ["B"])
        self.assertEqual(self.st.for_event(""), [])

    def test_missing_or_broken_file(self):
        path = os.path.join(self.tmp, "store", "todos.json")
        with open(path, "w", encoding="utf-8") as f:
            f.write("{broken")
        self.assertEqual(self._again().all(), [])

    def test_unknown_keys_from_newer_file_are_ignored(self):
        path = os.path.join(self.tmp, "store", "todos.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump([{"title": "새 버전 할 일", "future_field": 1, "id": "x1"}], f)
        self.assertEqual([t.title for t in self._again().all()], ["새 버전 할 일"])

    def test_subscribe_notifies(self):
        calls = []
        self.st.subscribe(lambda: calls.append(1))
        self.st.add("알림")
        self.assertEqual(calls, [1])

    def test_shared_instance_per_folder(self):
        self.assertIs(TodoStore.shared(self.tmp), TodoStore.shared(self.tmp))


if __name__ == "__main__":
    unittest.main(verbosity=2)
