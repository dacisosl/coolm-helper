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
        (os.path.join("docs", "설치안내.md"), "설치안내.md"),
        (os.path.join("docs", "개인정보고지.md"), "개인정보고지.md"),
        (os.path.join("calendar_sync", "SETUP.md"), "구글연동설정.md"),
    ]
    for src, dst in bundle:
        shutil.copyfile(os.path.join(BASE, src), os.path.join(dist, dst))
    assets_src = os.path.join(BASE, "assets")
    if os.path.isdir(assets_src):
        shutil.copytree(assets_src, os.path.join(dist, "assets"),
                        dirs_exist_ok=True)

    print(f"\n빌드 완료: {os.path.join(dist, 'CoolmHelper.exe')}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
