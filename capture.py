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


_warmed_hwnds: set[int] = set()   # 이미 깨워둔 창 — 빠른 감시가 건너뛴다


def prewarm(force: bool = False) -> bool:
    """쿨메신저 웹뷰의 접근성 트리를 미리 깨운다 — 첫 ⚡ 지연의 주범 제거.

    쿨메신저 본문을 그리는 내장 크롬(CEF)은 누군가 처음 UIA로 읽으려 할
    때에야 접근성 트리를 만들기 시작한다. 그 첫 준비가 몇 초 걸리고,
    한 번 만들어지면 프로세스가 살아 있는 동안 수십 ms로 빨라진다
    (2026-08-04 사용자 보고: "맨 처음 간편등록만 오래 걸린다").
    그래서 미리 한 번 읽어 두고 결과는 버린다. 읽기 전용 UIA 조회라
    쿨메신저 상태는 바꾸지 않는다.

    force=False: 아직 안 깨운 창만 깨운다 (몇 초 간격 빠른 감시용 — 이미
    깨운 창은 창 목록 조회(수 ms)만 하고 끝나 부담이 없다).
    force=True : 모든 창을 다시 깨운다 (웹뷰 재시작 대비, 느슨한 주기용).
    무언가를 깨웠으면 True를 반환한다.
    """
    woke = False
    try:
        pid = _cool_pid()
        if pid is None:
            _warmed_hwnds.clear()      # 쿨메신저가 꺼졌다 켜지면 처음부터
            return False
        wins = _cool_windows(pid)
        targets = [h for h in wins if force or h not in _warmed_hwnds]
        if not targets:
            return False
        warmup()
        for hwnd in targets:
            try:
                _window_body(hwnd)     # 결과는 버림 — 깨우는 것이 목적
                _warmed_hwnds.add(hwnd)
                woke = True
            except Exception:
                continue
        # 사라진 창의 흔적 정리 (hwnd 재사용 대비)
        _warmed_hwnds.intersection_update(wins)
    except Exception:
        pass                           # 프리워밍 실패는 기능에 영향 없음
    return woke


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


def _uia_text_from_hwnd(hwnd: int) -> str:
    """hwnd 안의 본문을 UIA TextPattern으로 읽는다.

    Document 컨트롤을 먼저 찾고, 없으면 TextPattern을 가진 아무 요소나
    찾는다 (쿨메신저 버전에 따라 본문 컨트롤 종류가 달라서, 2026-08-02).
    """
    import comtypes.gen.UIAutomationClient as UIAC
    elem = _uia.iuia.ElementFromHandle(hwnd)
    cond = _uia.iuia.CreatePropertyCondition(
        _uia.UIA_dll.UIA_ControlTypePropertyId,
        _uia.UIA_dll.UIA_DocumentControlTypeId)
    doc = elem.FindFirst(_uia.tree_scope["descendants"], cond)
    if doc is None:
        cond2 = _uia.iuia.CreatePropertyCondition(
            _uia.UIA_dll.UIA_IsTextPatternAvailablePropertyId, True)
        doc = elem.FindFirst(_uia.tree_scope["descendants"], cond2)
    if doc is None:
        return ""
    try:
        pat = doc.GetCurrentPattern(_uia.UIA_dll.UIA_TextPatternId)
        tp = pat.QueryInterface(UIAC.IUIAutomationTextPattern)
        return (tp.DocumentRange.GetText(-1) or "").strip()
    except Exception:
        return ""


def _chrome_body(chrome_hwnd: int) -> str:
    """(구 이름 유지) 내장 브라우저 자식 창의 본문 읽기."""
    return _uia_text_from_hwnd(chrome_hwnd)


IE_CHILD_CLASS = "Internet Explorer_Server"   # 옛 방식 내장 브라우저
PLAIN_TEXT_CLASSES = ("EDIT", "STATIC")       # WM_GETTEXT로 읽히는 표준 컨트롤


def _window_body(hwnd: int) -> tuple[str, str]:
    """창 하나에서 본문을 3단계로 읽는다. (본문, 읽은 방법) 반환.

    ① 내장 브라우저(크롬/IE) 자식 → UIA
    ② RichEdit/Edit/Static 표준 컨트롤 → WM_GETTEXT
    ③ 마지막 수단: 창 전체를 UIA로 탐색 (느릴 수 있어 최후에만)
    """
    kids = _children_by_class(hwnd)
    best, how = "", ""
    for h in (kids.get(CHROME_CHILD_CLASS, [])
              + kids.get(IE_CHILD_CLASS, [])):
        try:
            t = _uia_text_from_hwnd(h)
        except Exception:
            continue
        if len(t) > len(best):
            best, how = t, "웹뷰"
    if len(best) < MIN_BODY_LEN:
        for cls, hwnds in kids.items():
            u = cls.upper()
            if "RICHEDIT" in u or u in PLAIN_TEXT_CLASSES:
                for h in hwnds:
                    t = _gettext(h).strip()
                    if len(t) > len(best):
                        best, how = t, "텍스트칸"
    if len(best) < MIN_BODY_LEN:
        try:
            t = _uia_text_from_hwnd(hwnd)
            if len(t) > len(best):
                best, how = t, "전체탐색"
        except Exception:
            pass
    return best, how


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
        # 어떤 부품으로 이뤄진 창인지 — 못 읽을 때 원인 파악의 핵심 정보
        summary = ", ".join(
            f"{cls}×{len(hs)}" for cls, hs in
            sorted(kids.items(), key=lambda kv: -len(kv[1]))[:8])
        body, how = _window_body(hwnd)
        lines.append(f"   창{i}: 읽은 글자 {len(body)}자"
                     + (f" ({how})" if how else "")
                     + f" | 부품: {summary or '없음'}")
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
        body, _how = _window_body(hwnd)
        if len(body) < MIN_BODY_LEN:
            continue
        title = ""
        for h in _children_by_class(hwnd).get("Edit", []):
            t = _gettext(h, 500).strip()
            if 2 <= len(t) <= 120:
                title = t
                break
        if not title:
            title = body.splitlines()[0][:40]
        return CapturedMessage(title=title, body=body)
    return None
