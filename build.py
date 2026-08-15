# -*- coding: utf-8 -*-
"""exe 빌드 스크립트: python build.py

필요: pip install pyinstaller PyQt6 xlrd
결과: dist/CoolmHelper/CoolmHelper.exe + 동봉 문서
설치파일까지 만들려면 Inno Setup으로 installer.iss를 컴파일한다.
"""
import os
import shutil
import subprocess
import sys

BASE = os.path.dirname(os.path.abspath(__file__))


def main() -> int:
    os.chdir(BASE)
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean", "--windowed",
        "--name", "CoolmHelper",
        "--exclude-module", "tkinter",
        # 구글 연동 — 함수 안에서 import되므로 명시 포함 + 정적 discovery JSON
        "--hidden-import", "googleapiclient",
        "--hidden-import", "googleapiclient.discovery",
        "--hidden-import", "google_auth_oauthlib.flow",
        "--hidden-import", "google.auth.transport.requests",
        # discovery JSON 뭉치(수십 MB)는 동봉하지 않는다 —
        # google_sync가 static_discovery=False로 접속 시 받아온다.
        "main.py",
    ]
    ico = os.path.join(BASE, "assets", "app.ico")
    if os.path.exists(ico):
        cmd[-1:-1] = ["--icon", ico]
    print(">", " ".join(cmd))
    if subprocess.call(cmd) != 0:
        print("빌드 실패")
        return 1

    dist = os.path.join(BASE, "dist", "CoolmHelper")
    bundle = [
        ("students.txt.example", "students.txt.example"),
        (os.path.join("docs", "사용설명서.html"), "사용설명서.html"),
        (os.path.join("docs", "설치안내.md"), "설치안내.md"),
        (os.path.join("docs", "개인정보고지.md"), "개인정보고지.md"),
        (os.path.join("calendar_sync", "SETUP.md"), "구글연동설정.md"),
        # 업데이트 직후 쿨비서가 "이번에 바뀐 점"을 읽어 알려준다
        ("release_notes.txt", "release_notes.txt"),
    ]
    for src, dst in bundle:
        shutil.copyfile(os.path.join(BASE, src), os.path.join(dist, dst))
    assets_src = os.path.join(BASE, "assets")
    if os.path.isdir(assets_src):
        shutil.copytree(assets_src, os.path.join(dist, "assets"),
                        dirs_exist_ok=True)

    make_portable_zip(dist)
    print(f"\n빌드 완료: {os.path.join(dist, 'CoolmHelper.exe')}")
    return 0


PORTABLE_README = """\
COOL-비서 무설치판 — 먼저 읽어 주세요

1) 이 폴더(CoolmHelper)를 통째로 원하는 곳에 옮겨 놓으세요.
   예) 문서\\CoolmHelper  또는  바탕화면\\CoolmHelper
   ※ 압축 프로그램 창 안에서 바로 실행하면 안 됩니다.
      일정이 임시 폴더에 저장돼서 컴퓨터를 끄면 사라져요.
      반드시 '압축 풀기'를 먼저 해 주세요.

2) 폴더 안의 CoolmHelper.exe 를 실행하면 펭귄이 나타납니다.
   자주 쓰려면 CoolmHelper.exe 에 오른쪽 클릭 →
   '바로 가기 만들기' 로 바탕화면에 놓아 두세요.

3) 일정·설정은 이 폴더 안에 저장됩니다(store 폴더, config.json).
   폴더를 옮기면 일정도 같이 따라갑니다.

4) 새 버전이 나오면 앱이 알려줍니다. 새 ZIP을 받아 압축을 푼 뒤
   이 폴더에 덮어쓰면 됩니다 — 일정은 그대로 남습니다.

설치판(CoolmHelper-Setup.exe)이 실행되는 컴퓨터라면 설치판을 쓰는 편이
편합니다. 새 버전이 나올 때 자동으로 업데이트되거든요.
"""


def make_portable_zip(dist: str) -> str:
    """설치 없이 압축만 풀어 쓰는 배포본 — 설치파일이 차단되는 PC 대비.

    학교 PC에서 설치파일이 백신·SmartScreen에 막히는 경우가 있어
    보조 배포본으로 함께 낸다 (2026-08-14 사용자 요청).
    """
    with open(os.path.join(dist, "먼저 읽어주세요.txt"), "w",
              encoding="utf-8") as f:
        f.write(PORTABLE_README)
    out = os.path.join(BASE, "dist", "CoolmHelper-Portable")
    path = shutil.make_archive(out, "zip",
                               root_dir=os.path.join(BASE, "dist"),
                               base_dir="CoolmHelper")
    mb = os.path.getsize(path) / 1048576
    print(f"무설치판 압축 완료: {path} ({mb:.1f} MB)")
    return path


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
