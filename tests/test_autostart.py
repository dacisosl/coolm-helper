# -*- coding: utf-8 -*-
"""autostart 점검 — 가짜 winreg로 레지스트리 동작을 흉내 낸다.

실제 버그 재현 (2026-09-02 "체크는 켜져 있는데 부팅 때 안 뜸"):
- Run 값이 옛 경로를 가리키면 is_enabled가 False여야 하고 repair가 고쳐야 한다.
- 작업 관리자 '시작 앱'에서 '사용 안 함'(StartupApproved 차단)이면
  is_enabled가 False여야 하고 enable/repair가 차단을 푼다.
"""
import importlib
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class FakeKey:
    def __init__(self, store: dict):
        self.store = store

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class FakeWinreg:
    """(키경로, 값이름) → 값 사전 하나로 레지스트리를 흉내 낸다."""
    HKEY_CURRENT_USER = object()
    KEY_SET_VALUE = 2
    REG_SZ = 1

    def __init__(self):
        self.values: dict[tuple[str, str], object] = {}

    def OpenKey(self, root, path, reserved=0, access=0):
        key = FakeKey(self.values)
        key.path = path
        return key

    def QueryValueEx(self, key, name):
        try:
            return self.values[(key.path, name)], self.REG_SZ
        except KeyError:
            raise OSError(2, "값 없음")

    def SetValueEx(self, key, name, reserved, vtype, value):
        self.values[(key.path, name)] = value

    def DeleteValue(self, key, name):
        try:
            del self.values[(key.path, name)]
        except KeyError:
            raise OSError(2, "값 없음")


def _load(fake: FakeWinreg):
    sys.modules["winreg"] = fake
    if "autostart" in sys.modules:
        return importlib.reload(sys.modules["autostart"])
    return importlib.import_module("autostart")


def tearDownModule():
    sys.modules.pop("winreg", None)
    sys.modules.pop("autostart", None)


class AutostartTest(unittest.TestCase):
    def setUp(self):
        self.fake = FakeWinreg()
        self.mod = _load(self.fake)
        self.run = (self.mod.RUN_KEY, self.mod.VALUE_NAME)
        self.approved = (self.mod.APPROVED_KEY, self.mod.VALUE_NAME)

    def test_enable_disable_roundtrip(self):
        self.assertFalse(self.mod.is_enabled())
        self.mod.enable("/base")
        self.assertTrue(self.mod.is_enabled())
        self.mod.disable()
        self.assertFalse(self.mod.is_enabled())
        # 두 번 꺼도 오류 없어야 한다
        self.mod.disable()

    def test_blocked_by_task_manager(self):
        """작업 관리자 '사용 안 함' = StartupApproved 첫 바이트 홀수."""
        self.mod.enable("/base")
        self.fake.values[self.approved] = b"\x03" + b"\x00" * 11
        self.assertFalse(self.mod.is_enabled())
        # 짝수(0x02)는 허용 상태
        self.fake.values[self.approved] = b"\x02" + b"\x00" * 11
        self.assertTrue(self.mod.is_enabled())
        # enable이 차단 표시를 지워 되살린다
        self.fake.values[self.approved] = b"\x03" + b"\x00" * 11
        self.mod.enable("/base")
        self.assertNotIn(self.approved, self.fake.values)
        self.assertTrue(self.mod.is_enabled())

    def test_stale_path_detected_and_repaired(self):
        """옛 경로 등록 = frozen exe 기준으로 어긋남 → repair가 고친다."""
        self.fake.values[self.run] = r'"C:\old\dist\CoolmHelper.exe"'
        with mock.patch.object(sys, "frozen", True, create=True), \
             mock.patch.object(sys, "executable",
                               r"C:\new\CoolmHelper\CoolmHelper.exe"):
            self.assertFalse(self.mod.is_enabled(r"C:\new\CoolmHelper"))
            self.mod.repair(r"C:\new\CoolmHelper")
            self.assertEqual(self.fake.values[self.run],
                             r'"C:\new\CoolmHelper\CoolmHelper.exe"')
            self.assertTrue(self.mod.is_enabled(r"C:\new\CoolmHelper"))

    def test_repair_respects_user_off(self):
        """등록 자체가 없으면(사용자가 끔) repair가 켜지 않는다."""
        with mock.patch.object(sys, "frozen", True, create=True), \
             mock.patch.object(sys, "executable",
                               r"C:\new\CoolmHelper\CoolmHelper.exe"):
            self.mod.repair(r"C:\new\CoolmHelper")
        self.assertNotIn(self.run, self.fake.values)

    def test_repair_unblocks(self):
        """등록은 있는데 차단만 된 경우 repair가 차단을 푼다."""
        with mock.patch.object(sys, "frozen", True, create=True), \
             mock.patch.object(sys, "executable",
                               r"C:\app\CoolmHelper.exe"):
            self.mod.enable(r"C:\app")
            self.fake.values[self.approved] = b"\x03" + b"\x00" * 11
            self.mod.repair(r"C:\app")
            self.assertTrue(self.mod.is_enabled(r"C:\app"))

    def test_dev_python_not_treated_as_stale(self):
        """개발용 python 실행 중에는 설치판 등록을 어긋남으로 보지 않는다."""
        self.fake.values[self.run] = r'"C:\app\CoolmHelper.exe"'
        self.assertTrue(self.mod.is_enabled("/base"))
        self.mod.repair("/base")   # frozen 아님 → 아무것도 안 함
        self.assertEqual(self.fake.values[self.run],
                         r'"C:\app\CoolmHelper.exe"')


if __name__ == "__main__":
    unittest.main()
