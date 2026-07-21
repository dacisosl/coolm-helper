# -*- coding: utf-8 -*-
"""자동 업데이트 (선택 기능).

동작 방식:
1. config.json의 update_url에서 버전 정보(JSON)를 받아온다.
   {"version": "0.3.0", "url": "https://.../CoolmHelper-Setup.exe", "notes": "변경사항"}
2. 현재 버전보다 새 버전이면 "업데이트 후 재시작하시겠습니까?" 안내.
3. 예 → 설치파일을 임시 폴더에 다운로드 → 조용히 실행(/SILENT) → 앱 종료.
   설치가 끝나면 새 버전이 자동 실행된다 (installer.iss의 [Run] 참고).

개인정보: 이 기능이 서버에 보내는 것은 버전 정보 요청뿐이다.
update_url이 비어 있으면 아무 통신도 하지 않는다.

배포자 안내(구글 드라이브 말고 고정 URL이 필요):
- GitHub 저장소를 만들고 Releases에 CoolmHelper-Setup.exe를 올린 뒤,
  저장소에 version.json(위 형식)을 두고 그 raw URL을 update_url에 넣으면 된다.
"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
import urllib.request

from version import APP_VERSION

TIMEOUT = 6


def _parse(v: str) -> tuple:
    try:
        return tuple(int(x) for x in str(v).strip().lstrip("v").split(".")[:3])
    except ValueError:
        return (0,)


def check_for_update(update_url: str) -> dict | None:
    """새 버전이 있으면 {"version","url","notes"} 반환, 없거나 실패하면 None."""
    if not update_url:
        return None
    try:
        req = urllib.request.Request(
            update_url, headers={"User-Agent": f"CoolmHelper/{APP_VERSION}"})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            info = json.load(r)
        if _parse(info.get("version", "0")) > _parse(APP_VERSION):
            return info
    except Exception:
        pass   # 오프라인·서버 문제는 조용히 무시 (다음 실행 때 다시 확인)
    return None


def download_installer(url: str, progress=None) -> str:
    """설치파일을 임시 폴더에 내려받고 경로를 돌려준다.

    progress(받은 바이트, 전체 바이트)를 주면 덩어리마다 불러준다
    (전체를 모르면 전체=0) — 업데이트 진행 창의 게이지용.
    """
    fd, path = tempfile.mkstemp(suffix=".exe", prefix="CoolmHelper-Update-")
    os.close(fd)
    req = urllib.request.Request(
        url, headers={"User-Agent": f"CoolmHelper/{APP_VERSION}"})
    with urllib.request.urlopen(req, timeout=60) as r, open(path, "wb") as f:
        total = int(r.headers.get("Content-Length") or 0)
        done = 0
        while chunk := r.read(1024 * 256):
            f.write(chunk)
            done += len(chunk)
            if progress is not None:
                progress(done, total)
    return path


def run_installer_and_quit(installer_path: str) -> None:
    """설치파일을 조용히 실행하고 앱을 종료한다."""
    subprocess.Popen([installer_path, "/SILENT", "/NORESTART"], close_fds=True)
    from PyQt6.QtWidgets import QApplication
    QApplication.instance().quit()
