# -*- coding: utf-8 -*-
"""Windows 시작 시 자동 실행 — 사용자 레지스트리 Run 키 사용 (표준 방식).

관리자 권한 불필요(HKCU). 설정 → 일반에서 켜고 끈다.

"체크는 켜져 있는데 부팅 때 안 뜬다" 버그(2026-09-02)의 두 가지 함정:
1. Run 키의 명령이 옛 경로(옮기기 전 dist 폴더, 개발용 pythonw 등)를
   가리키면 부팅 때 아무것도 실행되지 않는다. 값의 존재만 보면 안 되고
   현재 실행 파일과 비교해야 한다.
2. 작업 관리자 '시작 앱'에서 '사용 안 함'으로 끄면(백신·정리 프로그램이
   끄기도 한다) Windows는 Run 값을 지우지 않고 StartupApproved 키에
   차단 표시만 남긴다. Run 값만 봐서는 켜진 것처럼 보인다.
둘 다 is_enabled()가 걸러내고, 앱 시작 때 repair()가 바로잡는다.
"""
from __future__ import annotations

import os
import sys
import winreg

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
# 작업 관리자 '시작 앱'의 사용/사용 안 함 상태가 저장되는 곳
APPROVED_KEY = (r"Software\Microsoft\Windows\CurrentVersion"
                r"\Explorer\StartupApproved\Run")
VALUE_NAME = "CoolmHelper"


def _command(base_dir: str) -> str:
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    pyw = sys.executable.replace("python.exe", "pythonw.exe")
    return f'"{pyw}" "{os.path.join(base_dir, "main.py")}"'


def registered_command() -> str | None:
    """Run 키에 등록된 명령. 등록이 없으면 None."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            value, _ = winreg.QueryValueEx(key, VALUE_NAME)
        return str(value)
    except OSError:
        return None


def _blocked() -> bool:
    """작업 관리자 '시작 앱'에서 '사용 안 함' 상태인가?

    StartupApproved 값의 첫 바이트가 홀수면 차단(보통 0x03),
    짝수(보통 0x02)거나 값 자체가 없으면 허용이다.
    """
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, APPROVED_KEY) as key:
            data, _ = winreg.QueryValueEx(key, VALUE_NAME)
        return bool(data) and data[0] % 2 == 1
    except OSError:
        return False


def _unblock() -> None:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, APPROVED_KEY, 0,
                            winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, VALUE_NAME)
    except OSError:
        pass


def _stale(base_dir: str) -> bool:
    """등록은 있는데 지금 실행 파일이 아닌 옛 경로를 가리키는가?

    exe(frozen)일 때만 판단한다 — 개발용 python으로 열었을 때 설치판
    등록을 어긋난 것으로 착각해 덮어쓰지 않기 위해서다.
    """
    if not getattr(sys, "frozen", False):
        return False
    current = registered_command()
    return current is not None and \
        os.path.normcase(current) != os.path.normcase(_command(base_dir))


def is_enabled(base_dir: str | None = None) -> bool:
    """부팅 때 실제로 실행될 상태인가? (등록됨 + 차단 아님 + 경로 일치)"""
    if registered_command() is None:
        return False
    if _blocked():
        return False
    if base_dir is not None and _stale(base_dir):
        return False
    return True


def enable(base_dir: str) -> None:
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0,
                        winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, _command(base_dir))
    _unblock()          # 작업 관리자에서 꺼져 있던 것도 다시 켠다


def disable() -> None:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0,
                            winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, VALUE_NAME)
    except OSError:
        pass
    _unblock()          # 차단 흔적도 정리 — 다음 enable 때 헷갈리지 않게


def repair(base_dir: str) -> None:
    """앱 시작 때 호출 — 등록이 옛 경로거나 차단돼 있으면 되살린다.

    등록 자체가 없는 경우(사용자가 자동 실행을 끈 상태)는 건드리지 않는다.
    exe(frozen)로 실행됐을 때만 동작한다.
    """
    if not getattr(sys, "frozen", False):
        return
    if registered_command() is None:
        return
    if _stale(base_dir) or _blocked():
        enable(base_dir)
