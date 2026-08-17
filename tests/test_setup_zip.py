# -*- coding: utf-8 -*-
"""설치파일 ZIP 감싸기 + 복사본 판별 (2026-08-16 사용자 정리).

ZIP은 무설치판이 아니라 **설치파일을 압축만 한 것** — 다운로드 차단을 피하는
용도이고, 압축을 풀어 설치하면 자동 업데이트까지 평소와 똑같이 동작한다.
설치를 거치지 않은 복사본으로 실행 중일 때만 '설치파일 받기'로 안내한다.
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


class TestCopyDetection(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        open(os.path.join(self.dir, "CoolmHelper.exe"), "w").close()

    def test_copied_folder_detected(self):
        with _Frozen():
            self.assertTrue(updater.is_portable(self.dir))

    def test_installed_build_is_not(self):
        open(os.path.join(self.dir, "unins000.exe"), "w").close()
        with _Frozen():
            self.assertFalse(updater.is_portable(self.dir))

    def test_source_run_is_not_flagged(self):
        # 개발 중(소스 실행)에는 무설치판으로 보지 않는다
        self.assertFalse(updater.is_portable(self.dir))

    def test_missing_folder_is_safe(self):
        with _Frozen():
            self.assertFalse(updater.is_portable(os.path.join(self.dir, "없음")))


class TestDownloadUrl(unittest.TestCase):
    BASE = "https://example.com/releases/download/v2.0.0/"

    def test_uses_zip_url_when_given(self):
        info = {"url": self.BASE + "CoolmHelper-Setup.exe",
                "zip_url": self.BASE + "CoolmHelper-Setup.zip"}
        self.assertEqual(updater.portable_zip_url(info), info["zip_url"])

    def test_falls_back_to_setup_exe(self):
        # 옛 version.json(zip_url 없음)에서는 설치파일 주소를 그대로 쓴다
        info = {"url": self.BASE + "CoolmHelper-Setup.exe"}
        self.assertEqual(updater.portable_zip_url(info), info["url"])

    def test_empty_info(self):
        self.assertEqual(updater.portable_zip_url({}), "")


class TestSetupZip(unittest.TestCase):
    """build.make_setup_zip — 설치파일 + 안내문만 담긴 ZIP."""

    def _make(self):
        import build
        tmp = tempfile.mkdtemp()
        exe = os.path.join(tmp, "CoolmHelper-Setup.exe")
        with open(exe, "wb") as f:
            f.write(b"MZ" + b"0" * 1000)
        return build.make_setup_zip(exe)

    def test_contains_installer_and_readme(self):
        import zipfile
        names = zipfile.ZipFile(self._make()).namelist()
        self.assertIn("CoolmHelper-Setup.exe", names)
        self.assertTrue(any("먼저 읽어주세요" in n for n in names), names)

    def test_no_app_folder_inside(self):
        # ZIP은 무설치판이 아니다 — 프로그램 폴더가 들어가면 안 된다
        import zipfile
        names = zipfile.ZipFile(self._make()).namelist()
        self.assertFalse(any(n.startswith("CoolmHelper/") for n in names), names)

    def test_readme_tells_to_run_installer(self):
        import build
        self.assertIn("CoolmHelper-Setup.exe", build.SETUP_ZIP_README)
        self.assertIn("압축을 풀", build.SETUP_ZIP_README)
        self.assertIn("자동으로 업데이트", build.SETUP_ZIP_README)


if __name__ == "__main__":
    unittest.main()
