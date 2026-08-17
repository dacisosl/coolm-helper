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

    print(f"\n빌드 완료: {os.path.join(dist, 'CoolmHelper.exe')}")
    return 0


SETUP_ZIP_README = """\
COOL-비서 설치 방법 — 압축을 풀고 CoolmHelper-Setup.exe 를 실행하세요

학교 컴퓨터에서는 설치파일(.exe)을 인터넷에서 바로 받으면 백신이나
Windows SmartScreen이 실행을 막는 경우가 있습니다. 그래서 같은 설치파일을
압축(ZIP) 형태로도 함께 올립니다. 압축을 풀어서 실행하면 대부분 그냥 됩니다.

1) 이 ZIP의 압축을 풀어 주세요. (반디집·알집·탐색기 아무거나 괜찮습니다)
2) 나온 CoolmHelper-Setup.exe 를 실행하고 안내를 따르세요.
   관리자 권한은 필요 없습니다.
3) "Windows가 PC를 보호했습니다" 창이 뜨면
   [추가 정보] → [실행] 을 눌러 주세요.
   서명 인증서가 없는 개인 제작 프로그램이라 나타나는 정상적인 안내입니다.

설치가 끝나면 바탕화면에 펭귄 아이콘이 생깁니다.
이후 새 버전은 앱이 알려주고, [예]만 누르면 자동으로 업데이트됩니다.
"""


def make_setup_zip(setup_exe: str, out_dir: str | None = None) -> str:
    """설치파일을 ZIP으로 감싼 배포본 — 다운로드 차단을 피하기 위한 것.

    ZIP은 '무설치판'이 아니다. 안에 설치파일이 그대로 들어 있고, 압축을
    풀어 설치하면 평소와 똑같은 설치판이 된다(자동 업데이트도 그대로).
    exe를 그냥 받으면 '인터넷에서 받음' 표시가 붙어 SmartScreen이 막지만,
    압축을 풀어 나온 파일에는 그 표시가 안 붙는 경우가 많다 (2026-08-16).
    """
    import zipfile
    out_dir = out_dir or os.path.dirname(setup_exe)
    path = os.path.join(out_dir, "CoolmHelper-Setup.zip")
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(setup_exe, "CoolmHelper-Setup.exe")
        z.writestr("먼저 읽어주세요.txt",
                   SETUP_ZIP_README.encode("utf-8-sig"))
    mb = os.path.getsize(path) / 1048576
    print(f"설치파일 압축 완료: {path} ({mb:.1f} MB)")
    return path


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
