# -*- coding: utf-8 -*-
"""화면 캡처(읽기 전용, 고속) — 쿨메신저에서 '지금 보고 있는 쪽지'를 읽는다.

속도 설계 (실측: 워밍업 후 총 30~60ms):
- 제목: 창의 Edit 컨트롤에 WM_GETTEXT (클래식 win32, ~1ms)
- 본문: 쿨메신저가 본문을 내장 크롬(CEF)에 그리므로, 크롬 자식 창만 콕 집어
  UIA TextPattern으로 읽는다 (~30ms). 창 전체를 UIA로 순회하면 3초가
  걸리므로 절대 전체 순회하지 않는다.
키 입력 시뮬레이션·클립보드 조작 없음. 쿨메신저 상태를 바꾸지 않는다.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes
from dataclasses import dataclass

MAIN_WINDOW_CLASS = "CoolMsg50SingleInstance"   # 쿨메신저 고유 창 클래스
CHROME_CHILD_CLASS = "Chrome_RenderWidgetHostHWND"
MIN_BODY_LEN = 10
WM_GETTEXT, WM_GETTEXTLENGTH = 0x000D, 0x000E

_uia = None   # UIA COM 싱글턴 (warmup()으로 미리 초기화)


@dataclass
class CapturedMessage:
    title: str
    body: str


def warmup() -> None:
    """UIA COM 초기화 — 앱 시작 시 백그라운드에서 불러 첫 클릭을 빠르게 한다."""
    global _uia
    if _uia is None:
        from pywinauto.uia_defines import IUIA
        _uia = IUIA()


def _cool_pid() -> int | None:
    user32 = ctypes.windll.user32
    hwnd = user32.FindWindowW(MAIN_WINDOW_CLASS, None)
    if not hwnd:
        return None
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value or None


def _cool_windows(pid: int) -> list[int]:
    """쿨메신저의 보이는 최상위 창 — 포커스된 창을 맨 앞으로."""
    user32 = ctypes.windll.user32
    result: list[int] = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    def cb(hwnd, lparam):
        wpid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(wpid))
        if wpid.value == pid and user32.IsWindowVisible(hwnd):
            result.append(hwnd)
        return True

    user32.EnumWindows(cb, 0)
    fg = user32.GetForegroundWindow()
    result.sort(key=lambda h: 0 if h == fg else 1)
    return result


def _children_by_class(parent: int) -> dict[str, list[int]]:
    user32 = ctypes.windll.user32
    out: dict[str, list[int]] = {}

    @ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    def cb(hwnd, lparam):
        cls = ctypes.create_unicode_buffer(64)
        user32.GetClassNameW(hwnd, cls, 64)
        out.setdefault(cls.value, []).append(hwnd)
        return True

    user32.EnumChildWindows(parent, cb, 0)
    return out


def _gettext(hwnd: int, max_len: int = 65536) -> str:
    user32 = ctypes.windll.user32
    n = user32.SendMessageW(hwnd, WM_GETTEXTLENGTH, 0, 0)
    if n <= 0:
        return ""
    n = min(n, max_len)
    buf = ctypes.create_unicode_buffer(n + 1)
    user32.SendMessageW(hwnd, WM_GETTEXT, n + 1, buf)
    return buf.value or ""


def _chrome_body(chrome_hwnd: int) -> str:
    """크롬 자식 창의 문서 본문을 UIA TextPattern으로 읽는다 (~30ms)."""
    import comtypes.gen.UIAutomationClient as UIAC
    elem = _uia.iuia.ElementFromHandle(chrome_hwnd)
    cond = _uia.iuia.CreatePropertyCondition(
        _uia.UIA_dll.UIA_ControlTypePropertyId,
        _uia.UIA_dll.UIA_DocumentControlTypeId)
    doc = elem.FindFirst(_uia.tree_scope["descendants"], cond)
    if doc is None:
        return ""
    pat = doc.GetCurrentPattern(_uia.UIA_dll.UIA_TextPatternId)
    tp = pat.QueryInterface(UIAC.IUIAutomationTextPattern)
    return (tp.DocumentRange.GetText(-1) or "").strip()


def read_current_message() -> CapturedMessage | None:
    """지금 쿨메신저 화면에 떠 있는 쪽지를 읽는다. 없으면 None."""
    pid = _cool_pid()
    if pid is None:
        return None
    warmup()
    for hwnd in _cool_windows(pid):
        kids = _children_by_class(hwnd)
        body = ""
        for chrome in kids.get(CHROME_CHILD_CLASS, []):
            try:
                t = _chrome_body(chrome)
            except Exception:
                continue
            if len(t) > len(body):
                body = t
        if not body:                       # 구버전 대비: RichEdit 폴백
            for cls, hwnds in kids.items():
                if "RICHEDIT" in cls.upper():
                    for h in hwnds:
                        t = _gettext(h).strip()
                        if len(t) > len(body):
                            body = t
        if len(body) < MIN_BODY_LEN:
            continue
        title = ""
        for h in kids.get("Edit", []):
            t = _gettext(h, 500).strip()
            if 2 <= len(t) <= 120:
                title = t
                break
        if not title:
            title = body.splitlines()[0][:40]
        return CapturedMessage(title=title, body=body)
    return None
