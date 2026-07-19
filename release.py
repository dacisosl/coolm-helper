# -*- coding: utf-8 -*-
"""릴리스 자동화: python release.py <버전> <제목> <노트>

예) python release.py 0.9.0 "종합 개선" "여러 항목 개선"
순서: 버전 갱신 → 테스트 → 빌드 → 설치파일 → GitHub 릴리스 → version.json → push
사용자 데이터(dist의 store)는 자동으로 백업·복원한다.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

BASE = os.path.dirname(os.path.abspath(__file__))
GH = r"C:\Program Files\GitHub CLI\gh.exe"
ISCC = os.path.expandvars(
    r"%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe")
REPO = "dacisosl/coolm-helper"


def run(cmd, **kw):
    print(">", " ".join(map(str, cmd)))
    subprocess.run(cmd, check=True, cwd=BASE, **kw)


def set_version(ver: str) -> None:
    vp = os.path.join(BASE, "version.py")
    text = open(vp, encoding="utf-8").read()
    open(vp, "w", encoding="utf-8").write(
        re.sub(r'APP_VERSION = "[^"]+"', f'APP_VERSION = "{ver}"', text))
    ip = os.path.join(BASE, "installer.iss")
    text = open(ip, encoding="utf-8").read()
    open(ip, "w", encoding="utf-8").write(
        re.sub(r'#define AppVersion "[^"]+"', f'#define AppVersion "{ver}"', text))


def main() -> int:
    if len(sys.argv) < 4:
        print(__doc__)
        return 1
    ver, title, notes = sys.argv[1], sys.argv[2], sys.argv[3]

    set_version(ver)
    run([sys.executable, "-m", "unittest", "discover", "-s", "tests"])

    # 사용자 데이터 백업
    dist_store = os.path.join(BASE, "dist", "CoolmHelper", "store")
    backup = None
    if os.path.isdir(dist_store):
        backup = tempfile.mkdtemp(prefix="coolm_store_bak_")
        shutil.copytree(dist_store, os.path.join(backup, "store"),
                        dirs_exist_ok=True)

    subprocess.run(["taskkill", "/f", "/im", "CoolmHelper.exe"],
                   capture_output=True)
    run([sys.executable, os.path.join(BASE, "build.py")])

    if backup:
        shutil.copytree(os.path.join(backup, "store"), dist_store,
                        dirs_exist_ok=True)

    run([ISCC, os.path.join(BASE, "installer.iss")])
    setup = os.path.join(BASE, "Output", "CoolmHelper-Setup.exe")
    run([GH, "release", "create", f"v{ver}", setup, "--repo", REPO,
         "--title", f"v{ver} — {title}", "--notes", notes])

    vj = {"version": ver,
          "url": (f"https://github.com/{REPO}/releases/download/"
                  f"v{ver}/CoolmHelper-Setup.exe"),
          "notes": notes}
    with open(os.path.join(BASE, "version.json"), "w", encoding="utf-8") as f:
        json.dump(vj, f, ensure_ascii=False, indent=2)

    run(["git", "add", "-A"])
    run(["git", "commit", "-m",
         f"v{ver}: {title}\n\nCo-Authored-By: Claude Fable 5 <noreply@anthropic.com>"])
    run(["git", "push"])
    print(f"\n✅ v{ver} 릴리스 완료")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
