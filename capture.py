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

MAIN_WINDOW_CLASS = "CoolMsg50SingleInstance"   # 쿨메신저 고유 창 클래스(5.0)
# 학교마다 쿨메신저 버전이 달라 창 클래스가 CoolMsg51…처럼 바뀐다.
# 정확한 이름이 안 맞으면 접두어·실행파일 이름으로도 찾는다 (2026-07-26).
CLASS_PREFIXES = ("COOLMSG", "COOLMESSENGER")
PROCESS_HINTS = ("COOLMESSENGER", "COOLMSG")
CHROME_CHILD_CLASS = "Chrome_RenderWidgetHostHWND"
MIN_BODY_LEN = 10
WM_GETTEXT, WM_GETTEXTLENGTH = 0x000D, 0x000E
PROCESS_QUERY_LIMITED = 0x1000

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


def _pid_of(hwnd: int) -> int:
    pid = wintypes.DWORD()
    ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value or 0


def _exe_name(pid: int) -> str:
    """프로세스 실행파일 이름 (실패하면 빈 문자열)."""
    try:
        k32 = ctypes.windll.kernel32
        h = k32.OpenProcess(PROCESS_QUERY_LIMITED, False, pid)
        if not h:
            return ""
        try:
            buf = ctypes.create_unicode_buffer(260)
            size = wintypes.DWORD(260)
            if not k32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
                return ""
            return buf.value.rsplit("\\", 1)[-1].upper()
        finally:
            k32.CloseHandle(h)
    except Exception:
        return ""


def _cool_pid() -> int | None:
    """쿨메신저 프로세스를 찾는다 — 버전이 달라도 찾도록 3단계로.

    ① 정확한 창 클래스(가장 빠름) ② 클래스 접두어(CoolMsg…) ③ 실행파일 이름.
    """
    user32 = ctypes.windll.user32
    hwnd = user32.FindWindowW(MAIN_WINDOW_CLASS, None)
    if hwnd:
        return _pid_of(hwnd) or None

    found: list[int] = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    def cb(h, lparam):
        cls = ctypes.create_unicode_buffer(128)
        user32.GetClassNameW(h, cls, 128)
        name = (cls.value or "").upper()
        if any(name.startswith(p) for p in CLASS_PREFIXES):
            pid = _pid_of(h)
            if pid:
                found.append(pid)
                return False           # 찾았으면 그만
        return True

    user32.EnumWindows(cb, 0)
    if found:
        return found[0]

    # ③ 창 클래스가 완전히 달라진 경우: 보이는 창의 실행파일 이름으로 찾기
    cands: list[int] = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    def cb2(h, lparam):
        if not user32.IsWindowVisible(h):
            return True
        pid = _pid_of(h)
        if pid and any(k in _exe_name(pid) for k in PROCESS_HINTS):
            cands.append(pid)
            return False
        return True

    user32.EnumWindows(cb2, 0)
    return cands[0] if cands else None


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


def diagnose() -> str:
    """왜 쪽지를 못 읽는지 사람이 읽을 수 있게 알려준다 (설정 → 데이터에서 실행).

    PC마다 쿨메신저 버전이 달라 실패 지점이 제각각이라, 어디서 막혔는지
    바로 알 수 있게 단계별로 확인한다 (2026-07-26).
    """
    lines: list[str] = []
    try:
        user32 = ctypes.windll.user32
    except Exception as e:
        return f"윈도우에서만 동작합니다 ({e})"

    exact = user32.FindWindowW(MAIN_WINDOW_CLASS, None)
    lines.append(f"① 표준 창 이름({MAIN_WINDOW_CLASS}): "
                 + ("찾음" if exact else "없음"))
    pid = _cool_pid()
    if pid is None:
        lines.append("② 쿨메신저 프로세스: 못 찾음")
        lines.append("→ 쿨메신저가 실행 중인지 확인해 주세요. "
                     "실행 중인데도 이 메시지가 보이면 이 내용을 알려주세요.")
        # 힌트: 지금 떠 있는 창 클래스 몇 개를 보여준다
        seen: list[str] = []

        @ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
        def cb(h, lparam):
            if user32.IsWindowVisible(h) and len(seen) < 12:
                cls = ctypes.create_unicode_buffer(96)
                user32.GetClassNameW(h, cls, 96)
                exe = _exe_name(_pid_of(h))
                if cls.value and exe:
                    seen.append(f"{exe} / {cls.value}")
            return True

        user32.EnumWindows(cb, 0)
        if seen:
            lines.append("지금 열린 창(참고): " + ", ".join(dict.fromkeys(seen)))
        return "\n".join(lines)

    lines.append(f"② 쿨메신저 프로세스: 찾음 (실행파일 {_exe_name(pid)})")
    wins = _cool_windows(pid)
    lines.append(f"③ 쿨메신저 창: {len(wins)}개")
    try:
        warmup()
        lines.append("④ 화면 읽기 준비(UIA): 정상")
    except Exception as e:
        lines.append(f"④ 화면 읽기 준비(UIA) 실패: {e}")
        return "\n".join(lines)

    for i, hwnd in enumerate(wins[:4], 1):
        kids = _children_by_class(hwnd)
        chrome = len(kids.get(CHROME_CHILD_CLASS, []))
        rich = sum(len(v) for k, v in kids.items() if "RICHEDIT" in k.upper())
        best = ""
        for c in kids.get(CHROME_CHILD_CLASS, []):
            try:
                t = _chrome_body(c)
            except Exception:
                continue
            if len(t) > len(best):
                best = t
        lines.append(f"   창{i}: 본문틀 {chrome}개 / 옛본문 {rich}개 / "
                     f"읽은 글자 {len(best)}자")
    got = read_current_message()
    lines.append("⑤ 결과: " + (f"제목 '{got.title[:20]}…' 읽음"
                              if got else "쪽지를 읽지 못함"))
    if not got:
        lines.append("→ 쿨메신저에서 쪽지를 '열어 둔' 상태여야 읽을 수 있어요.")
    return "\n".join(lines)


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
