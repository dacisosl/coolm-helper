# -*- coding: utf-8 -*-
"""무설치판(ZIP) 배포본 — 판별과 업데이트 안내 (2026-08-14 사용자 요청).

설치파일이 백신·SmartScreen에 막히는 PC를 위해 ZIP 배포본을 함께 낸다.
ZIP으로 실행 중이면 '조용한 설치'가 통하지 않으므로 새 ZIP을 받게 안내한다.
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import updater


class _Frozen:
    """sys.frozen을 잠깐 켜서 배포본처럼 보이게 하는 컨텍스트."""

    def __enter__(self):
        self._had = hasattr(sys, "frozen")
        sys.frozen = True
        return self

    def __exit__(self, *exc):
        if not self._had:
            del sys.frozen


class TestPortableDetection(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        open(os.path.join(self.dir, "CoolmHelper.exe"), "w").close()

    def test_zip_build_is_portable(self):
        with _Frozen():
            self.assertTrue(updater.is_portable(self.dir))

    def test_installed_build_is_not(self):
        open(os.path.join(self.dir, "unins000.exe"), "w").close()
        with _Frozen():
            self.assertFalse(updater.is_portable(self.dir))

    def test_source_run_is_not_portable(self):
        # 개발 중(소스 실행)에는 무설치판으로 보지 않는다
        self.assertFalse(updater.is_portable(self.dir))

    def test_missing_folder_is_safe(self):
        with _Frozen():
            self.assertFalse(updater.is_portable(os.path.join(self.dir, "없음")))


class TestPortableZipUrl(unittest.TestCase):
    BASE = "https://example.com/releases/download/v2.0.0/"

    def test_uses_zip_url_when_given(self):
        info = {"url": self.BASE + "CoolmHelper-Setup.exe",
                "zip_url": self.BASE + "CoolmHelper-Portable.zip"}
        self.assertEqual(updater.portable_zip_url(info), info["zip_url"])

    def test_falls_back_to_setup_url(self):
        # 옛 version.json(zip_url 없음)에서도 같은 폴더의 ZIP을 가리킨다
        info = {"url": self.BASE + "CoolmHelper-Setup.exe"}
        self.assertEqual(updater.portable_zip_url(info),
                         self.BASE + "CoolmHelper-Portable.zip")

    def test_empty_info(self):
        self.assertEqual(updater.portable_zip_url({}), "")


class TestBuildPacking(unittest.TestCase):
    """build.py가 ZIP과 안내문을 만드는지 (PyInstaller 없이 압축 단계만)."""

    def test_zip_contains_folder_and_readme(self):
        import zipfile

        import build
        tmp = tempfile.mkdtemp()
        dist = os.path.join(tmp, "dist", "CoolmHelper")
        os.makedirs(dist)
        open(os.path.join(dist, "CoolmHelper.exe"), "w").close()
        real_base, build.BASE = build.BASE, tmp
        try:
            path = build.make_portable_zip(dist)
            names = zipfile.ZipFile(path).namelist()
        finally:
            build.BASE = real_base
        # 압축을 풀면 CoolmHelper 폴더가 통째로 나와야 한다 (파일이 흩어지지 않게)
        self.assertTrue(all(n.startswith("CoolmHelper/") for n in names), names)
        self.assertTrue(any("먼저 읽어주세요" in n for n in names), names)

    def test_readme_warns_about_running_inside_zip(self):
        import build
        self.assertIn("압축 풀기", build.PORTABLE_README)

    def test_installer_excludes_portable_readme(self):
        # 설치판에는 무설치판 안내문이 들어가면 안 된다
        iss = open(os.path.join(os.path.dirname(__file__), "..",
                                "installer.iss"), encoding="utf-8").read()
        self.assertIn("Excludes:", iss)
        self.assertIn("먼저 읽어주세요.txt", iss)


if __name__ == "__main__":
    unittest.main()
