# -*- coding: utf-8 -*-
"""화면 캡처(읽기 전용, 고속) — 쿨메신저에서 '지금 보고 있는 쪽지'를 읽는다.

속도 설계 (실측: 워밍업 후 총 30~60ms):
- 제목: 창의 Edit 컨트롤에 WM_GETTEXT (클래식 win32, ~1ms)
- 본문: 쿨메신저가 본문을 내장 크롬(CEF)에 그리므로, 크롬 자식 창만 콕 집어
  UIA TextPattern으로 읽는다 (~30ms). 창 전체를 UIA로 순회하면 3초가
  걸리므로 절대 전체 순회하지 않는다.
키 입력 시뮬레이션·클립보드 조작 없음. 이 모듈은 쿨메신저 상태를 바꾸지 않는다.
상태를 바꾸는 동작은 coolm_control.py에만 있고, 사용자가 포스트잇 '제출'을
직접 눌렀을 때만 실행된다(관리함 열기·쪽지 선택·창 앞으로, 2026-09-08 결정).
조직도 검색칸에 이름을 넣고 그 사람을 골라 쪽지 쓰기 창을 여는 것까지가 예외다.
회신 내용 작성·전송은 어디서도 하지 않는다. bring_to_front는 포커스만 준다.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes
from dataclasses import dataclass

MAIN_WINDOW_CLASS = "CoolMsg50SingleInstance"   # 쿨메신저 고유 창 클래스(5.0)
# 학교마다 쿨메신저 버전이 달라 창 클래스가 CoolMsg51…처럼 바뀐다.
# 정확한 이름이 안 맞으면 접두어·실행파일 이름으로도 찾는다 (2026-07-26).
# 창 종류·실행파일 이름에서 찾는 조각 — **접두어가 아니라 포함** 검사.
# 경기도교육청 메신저는 클래스가 '@Messenger7_MainWnd'(앞에 @가 붙어 접두어
# 검사가 실패했다), 실행파일이 'ATMESSENGERMOBILEEDITION.EXE'다. 제품 이름이
# 아니라 **공통 성질(MESSENGER)**로 잡아야 지역마다 다른 메신저를 다 잡는다.
CLASS_PREFIXES = ("COOLMSG", "COOLMESSENGER", "MESSENGER")   # 이름 유지(진단이 쓴다)
PROCESS_HINTS = ("COOLMESSENGER", "COOLMSG", "MESSENGER")
# 지역에 따라 메신저 프로그램 이름이 아예 다르다 (2026-09-08 경기도 사례:
# SSAMBOARD.EXE / Chrome_WidgetWin_1 — 이름·창클래스 어느 힌트에도 안 걸렸다).
# 그래서 **창 제목**으로도 찾는다. 제목은 그 프로그램의 우리말 화면 글자라
# 회사·버전이 달라도 같다.
WINDOW_TITLE_HINTS = ("쪽지 읽기", "쪽지 보내기", "쪽지 쓰기",
                      "메시지 관리함", "쪽지함", "메시지관리함")
# 제목이 딱 이 단어인 창 — GOE메신저의 쪽지 창 제목이 '쪽지' 한 단어였다
TITLE_EXACT = ("쪽지", "쪽지함", "메시지", "메신저")
# 브라우저 제목은 '보고 있는 웹페이지' 이름이라 메신저 판단에 쓰면 안 된다
# (그 선생님 목록에도 제목에 '쿨메신저'가 든 크롬 창이 있었다)
BROWSER_HINTS = ("CHROME", "MSEDGE", "EDGE", "WHALE", "FIREFOX", "IEXPLORE",
                 "OPERA", "BRAVE")
SELF_EXE_HINT = "COOLMHELPER"      # 우리 앱 — 우리 창을 메신저로 착각하면 안 된다
_learned_exes: set[str] = set()    # 제목으로 찾아낸 프로그램 이름 (이 실행 동안 기억)
_extra_exes: set[str] = set()      # 설정(messenger_exe)으로 직접 지정한 이름
_cached_pid: int | None = None     # 직전에 찾은 프로세스 (몇 초마다 다시 찾지 않게)


def set_extra_hints(exe: str = "") -> None:
    """설정에서 직접 지정한 쪽지 프로그램 이름을 알려 준다 (main.py가 부른다).

    자동으로 못 찾는 학교는 config.json의 messenger_exe에 한 줄
    (예: "ATMESSENGERMOBILEEDITION.EXE") 적어 두면 그걸로 찾는다.
    """
    name = (exe or "").strip().upper()
    if name:
        _extra_exes.add(name)
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


def looks_like_messenger_title(title: str) -> bool:
    """창 제목이 메신저의 쪽지 창처럼 보이는가 (프로그램 이름과 무관하게)."""
    t = (title or "").strip()
    return bool(t) and any(h in t for h in WINDOW_TITLE_HINTS)


def _window_title(hwnd: int) -> str:
    """최상위 창의 제목 — GetWindowTextW로 읽는다.

    _gettext(WM_GETTEXT)는 다른 프로세스에 메시지를 보내 응답을 기다리므로,
    멈춘 프로그램이 하나라도 있으면 창 목록을 훑다가 같이 멈춘다.
    GetWindowTextW는 다른 프로세스의 최상위 창 제목을 기다림 없이 준다.
    """
    try:
        buf = ctypes.create_unicode_buffer(256)
        ctypes.windll.user32.GetWindowTextW(hwnd, buf, 256)
        return buf.value or ""
    except Exception:
        return ""


def _is_self(exe: str) -> bool:
    return SELF_EXE_HINT in (exe or "")


def _is_browser(exe: str) -> bool:
    return any(b in (exe or "") for b in BROWSER_HINTS)


def messenger_score(exe: str, cls: str, title: str) -> int:
    """이 창이 쪽지 프로그램의 것일 가능성 (0=아님, 클수록 확실).

    3 = 창 종류나 실행파일 이름에 MESSENGER/COOLMSG… 가 있다 (가장 확실)
    2 = 제목이 쪽지 창 같다 (브라우저는 제외 — 제목이 웹페이지 이름이다)
    """
    if _is_self(exe):
        return 0                      # 우리 앱 창 (제목에 '쪽지'가 들어간다)
    e, c = (exe or "").upper(), (cls or "").upper()
    hints = tuple(PROCESS_HINTS) + tuple(_learned_exes) + tuple(_extra_exes)
    if any(k in c for k in CLASS_PREFIXES) or any(k in e for k in hints):
        return 3
    if _is_browser(e):
        return 0
    t = (title or "").strip()
    if t in TITLE_EXACT or looks_like_messenger_title(t):
        return 2
    return 0


def pick_messenger(rows):
    """(실행파일, 창종류, 제목, pid) 목록에서 쪽지 프로그램 창을 고른다.

    점수가 가장 높은 것, 같으면 제목이 있는 것을 먼저. 없으면 None.
    """
    best, best_key = None, (0, 0)
    for row in rows:
        exe, cls, title = row[0], row[1], row[2]
        score = messenger_score(exe, cls, title)
        if not score:
            continue
        key = (score, 1 if (title or "").strip() else 0)
        if key > best_key:
            best, best_key = row, key
    return best


def dedupe_windows(rows: list[tuple[str, str, str]], limit: int = 25) -> list[str]:
    """(실행파일, 창클래스, 제목) 목록을 사람이 읽을 줄로 — 중복은 합친다.

    예전 진단은 **중복을 지우기 전에 12개에서 잘라서**, 탐색기 창 몇 개가
    자리를 다 먹고 정작 메신저가 목록에 안 나왔다(2026-09-08 경기도 사례).
    제목도 안 보여줘서 어느 프로그램이 쪽지 창인지 알 수 없었다.
    이제 중복을 먼저 합치고, **제목이 있는 창을 앞으로** 놓는다.
    """
    seen: dict[tuple[str, str], str] = {}
    for exe, cls, title in rows:
        if not exe and not cls:
            continue
        key = (exe, cls)
        if seen.get(key):
            continue                      # 이미 제목까지 있는 줄은 그대로
        seen[key] = (title or "").strip()
    out = [(exe, cls, title) for (exe, cls), title in seen.items()]
    out.sort(key=lambda r: (not r[2], r[0]))      # 제목 있는 것 먼저
    return [f"{exe} / {cls}" + (f" / '{title[:40]}'" if title else "")
            for exe, cls, title in out[:limit]]


# 쪽지 프로그램일 수 있는 이름 조각 — 진단에서 후보를 좁히는 데만 쓴다
CANDIDATE_KEYS = ("COOL", "MSG", "MESSENGER", "SSAM", "쪽지", "메신저")


def visible_windows(include_hidden: bool = False,
                    with_self: bool = False) -> list[tuple[str, str, str]]:
    """최상위 창들의 (실행파일, 창클래스, 제목).

    include_hidden=True면 숨은 창도 — 트레이로 내려간 메신저를 찾을 때 필요하다.
    실행파일 이름을 못 읽으면(권한 등) 빈 문자열로 남는다.
    """
    rows: list[tuple[str, str, str]] = []
    try:
        user32 = ctypes.windll.user32
    except Exception:
        return rows

    @ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    def cb(h, lparam):
        if not include_hidden and not user32.IsWindowVisible(h):
            return True
        exe = _exe_name(_pid_of(h))
        if _is_self(exe) and not with_self:
            return True
        cls = ctypes.create_unicode_buffer(96)
        user32.GetClassNameW(h, cls, 96)
        rows.append((exe, cls.value or "", _window_title(h)))
        return True

    user32.EnumWindows(cb, 0)
    return rows


def candidate_rows(rows: list[tuple[str, str, str]]) -> list[tuple[str, str, str]]:
    """쪽지 프로그램일 수 있는 창만 — 이름·창종류·제목에 단서가 있는 것."""
    out = []
    for exe, cls, title in rows:
        blob = f"{exe} {cls} {title}".upper()
        if any(k.upper() in blob for k in CANDIDATE_KEYS):
            out.append((exe, cls, title))
    return out


def _pid_by_title() -> int | None:
    """④ 창 제목으로 찾기 — 프로그램 이름이 아예 다른 지역 대응."""
    try:
        user32 = ctypes.windll.user32
    except Exception:
        return None
    found: list[int] = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    def cb(h, lparam):
        if not user32.IsWindowVisible(h):
            return True
        if not looks_like_messenger_title(_window_title(h)):
            return True
        pid = _pid_of(h)
        exe = _exe_name(pid)
        if pid and not _is_self(exe):
            if exe:
                _learned_exes.add(exe)     # 다음부터는 이름으로 바로 찾는다
            found.append(pid)
            return False
        return True

    user32.EnumWindows(cb, 0)
    return found[0] if found else None


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
    """쪽지 프로그램(쿨메신저·GOE메신저 등)의 프로세스를 찾는다.

    ① 정확한 창 클래스(가장 빠름) ② 직전에 찾은 프로세스가 아직 살아 있으면 그대로
    ③ 숨은 창까지 한 번 훑어 messenger_score가 가장 높은 창의 프로세스.

    ③을 매번 하면 창마다 OpenProcess를 해서 부담이다(prewarm이 몇 초마다 부른다).
    그래서 ②로 캐시를 둔다. 학교마다 프로그램이 달라 이름·클래스·제목을 모두
    본다 (2026-09-09 경기도 GOE메신저 확인).
    """
    global _cached_pid
    user32 = ctypes.windll.user32
    hwnd = user32.FindWindowW(MAIN_WINDOW_CLASS, None)
    if hwnd:
        pid = _pid_of(hwnd) or None
        if pid:
            _cached_pid = pid
            return pid

    if _cached_pid and _exe_name(_cached_pid):      # ② 아직 살아 있나 (한 번만 확인)
        return _cached_pid

    rows: list[tuple[str, str, str, int]] = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    def cb(h, lparam):
        pid = _pid_of(h)
        if not pid:
            return True
        cls = ctypes.create_unicode_buffer(128)
        user32.GetClassNameW(h, cls, 128)
        rows.append((_exe_name(pid), cls.value or "", _window_title(h), pid))
        return True

    user32.EnumWindows(cb, 0)
    best = pick_messenger(rows)
    if best is None:
        _cached_pid = None
        return None
    exe = best[0]
    if exe:
        _learned_exes.add(exe)      # 다음부터는 이름으로 바로 걸린다
    _cached_pid = best[3]
    return _cached_pid


def bring_to_front() -> bool:
    """쿨메신저 창을 앞으로 올린다(포커스만). 없거나 실패하면 False.

    포스트잇 '제출' → 원본 쪽지 창의 [쿨메신저 창 앞으로]에서만 부른다.
    최소화돼 있으면 복원한다. 비Windows·쿨메신저 미실행은 조용히 False.
    """
    try:
        pid = _cool_pid()
        if not pid:
            return False
        wins = _cool_windows(pid)
        if not wins:
            return False
        user32 = ctypes.windll.user32
        hwnd = wins[0]
        if user32.IsIconic(hwnd):
            user32.ShowWindow(hwnd, 9)          # SW_RESTORE
        return bool(user32.SetForegroundWindow(hwnd))
    except Exception:
        return False


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
        lines.append("→ 쿨메신저(또는 학교에서 쓰는 쪽지 프로그램)를 켜고 "
                     "쪽지 하나를 열어 둔 채 다시 시도해 주세요.")
        lines.append("→ 그래도 안 되면 아래 '지금 열린 창' 목록을 그대로 "
                     "알려주세요. 지역마다 프로그램 이름이 달라서 "
                     "(예: 경기도) 목록을 보면 무엇을 찾아야 할지 알 수 있어요.")
        # 어느 단계에서 막혔는지 하나씩 — 이게 없으면 원인을 알 수 없다
        # (2026-09-08 경기도 제보: 쿨메신저를 쓰는데 '실행 중 아님'이 떴다)
        allw = visible_windows(include_hidden=True, with_self=True)
        vis = visible_windows()
        cls_hits = [r for r in allw
                    if any(p in r[1].upper() for p in CLASS_PREFIXES)]
        exe_hits = [r for r in vis
                    if any(k in r[0] for k in PROCESS_HINTS)]
        titled = [r for r in vis if looks_like_messenger_title(r[2])]
        unknown = sum(1 for r in allw if not r[0])
        lines.append(f"   ② 창 종류에 Messenger/CoolMsg가 든 창: {len(cls_hits)}개"
                     + (" → " + ", ".join(dedupe_windows(cls_hits, 3))
                        if cls_hits else ""))
        lines.append(f"   ③ 실행파일 이름에 COOLMESSENGER/COOLMSG가 있는 창: "
                     f"{len(exe_hits)}개"
                     + (" → " + ", ".join(dedupe_windows(exe_hits, 3))
                        if exe_hits else ""))
        lines.append(f"   ④ 제목이 쪽지 창 같은 창: {len(titled)}개"
                     + (" → " + ", ".join(dedupe_windows(titled, 3))
                        if titled else ""))
        if unknown:
            lines.append(f"   ※ 프로그램 이름을 읽지 못한 창 {unknown}개 — "
                         "관리자 권한으로 실행된 프로그램이면 이름을 못 읽어요.")
        cands = candidate_rows(allw)
        if cands:
            lines.append("쪽지 프로그램으로 보이는 것 (숨은 창까지):")
            for row in dedupe_windows(cands, 12):
                lines.append(f"   - {row}")
        else:
            lines.append("→ 쪽지 프로그램 후보가 하나도 없어요. "
                         "지금 쿨메신저가 정말 켜져 있는지, 트레이 아이콘만 "
                         "있는 상태가 아닌지 확인해 주세요.")
        lines.append("지금 열린 창 전체 (실행파일 / 창종류 / 제목):")
        for row in dedupe_windows(vis):
            lines.append(f"   - {row}")
        return "\n".join(lines)

    lines.append(f"② 쿨메신저 프로세스: 찾음 (실행파일 {_exe_name(pid)})")
    if _learned_exes:
        lines.append(f"   (창 제목으로 알아낸 프로그램: {', '.join(sorted(_learned_exes))})")
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


# 요소마다 "누를 수 있나(Invoke)·고를 수 있나(SelectionItem)…"를 보는 속성들.
# 쪽지 목록 항목이 어떤 패턴을 지원하는지가 '실제 쪽지 열기' 자동화의 열쇠다.
_PATTERN_PROPS = (
    ("Invoke", "UIA_IsInvokePatternAvailablePropertyId"),
    ("SelectionItem", "UIA_IsSelectionItemPatternAvailablePropertyId"),
    ("ExpandCollapse", "UIA_IsExpandCollapsePatternAvailablePropertyId"),
    ("Toggle", "UIA_IsTogglePatternAvailablePropertyId"),
    ("Value", "UIA_IsValuePatternAvailablePropertyId"),
    ("Text", "UIA_IsTextPatternAvailablePropertyId"),
    ("ScrollItem", "UIA_IsScrollItemPatternAvailablePropertyId"),
    ("Legacy", "UIA_IsLegacyIAccessiblePatternAvailablePropertyId"),
)


def _describe_element(el, type_names: dict) -> str:
    """UIA 요소 한 개를 한 줄로: 종류 이름 id 클래스 위치 [패턴]."""
    def prop(name):
        try:
            return getattr(el, name)
        except Exception:
            return None

    ct = prop("CurrentControlType")
    kind = type_names.get(ct, str(ct))
    name = str(prop("CurrentName") or "").replace("\n", " ")[:60]
    aid = str(prop("CurrentAutomationId") or "")[:40]
    cls = str(prop("CurrentClassName") or "")[:30]
    pats = []
    for label, pname in _PATTERN_PROPS:
        pid_ = getattr(_uia.UIA_dll, pname, None)
        if pid_ is None:
            continue
        try:
            if el.GetCurrentPropertyValue(pid_):
                pats.append(label)
        except Exception:
            pass
    rect = ""
    try:
        r = el.CurrentBoundingRectangle
        rect = f" ({r.left},{r.top},{r.right},{r.bottom})"
    except Exception:
        pass
    hidden = " [화면밖]" if prop("CurrentIsOffscreen") else ""
    parts = [kind]
    if name:
        parts.append(f"이름='{name}'")
    if aid:
        parts.append(f"id='{aid}'")
    if cls:
        parts.append(f"class='{cls}'")
    return " ".join(parts) + rect + (f" [{','.join(pats)}]" if pats else "") + hidden


LVM_GETITEMCOUNT = 0x1004      # SysListView32 항목 수 (포인터 없이 안전)
HDM_GETITEMCOUNT = 0x1200      # SysHeader32 열 수


def _classic_controls(kids: dict[str, list[int]]) -> list[str]:
    """표준 부품의 글자·크기를 WM_GETTEXT/LVM 메시지로 읽어 요약한다 (읽기 전용)."""
    out: list[str] = []
    user32 = ctypes.windll.user32
    for cls, hs in kids.items():
        up = cls.upper()
        if up in ("BUTTON", "STATIC", "EDIT") or up.startswith("RICHEDIT"):
            texts = []
            for h in hs[:60]:
                t = _gettext(h, 120).replace("\n", " ").strip()
                vis = user32.IsWindowVisible(h)
                if t:
                    texts.append(f"'{t}'" + ("" if vis else "(숨김)"))
            if texts:
                out.append(f"  {cls} 글자: " + ", ".join(texts))
        elif up == "SYSLISTVIEW32":
            for h in hs:
                n = user32.SendMessageW(h, LVM_GETITEMCOUNT, 0, 0)
                r = wintypes.RECT()
                user32.GetWindowRect(h, ctypes.byref(r))
                out.append(f"  목록(SysListView32) hwnd={h}: 항목 {n}개, "
                           f"위치 ({r.left},{r.top},{r.right},{r.bottom}), "
                           f"{'보임' if user32.IsWindowVisible(h) else '숨김'}")
        elif up == "SYSHEADER32":
            for h in hs:
                n = user32.SendMessageW(h, HDM_GETITEMCOUNT, 0, 0)
                out.append(f"  목록 머리(SysHeader32) hwnd={h}: 열 {n}개")
    return out


def dump_ui_tree(max_depth: int = 40, max_nodes: int = 6000) -> str:
    """쿨메신저 창들의 UI 자동화(접근성) 트리를 글로 뽑는다 — 읽기 전용.

    '제출' 버튼이 **실제 쿨메신저 쪽지 창**을 열게 하려면(2026-09-04 사용자
    결정) 쪽지 목록·버튼이 접근성 트리에서 어떤 이름·종류로 보이는지 알아야
    한다. 사용자 PC에서 한 번 뽑아 보고 자동화가 가능한지 판단한다.
    쪽지 제목·사람 이름이 섞여 있을 수 있어 화면에 뿌리지 않고 파일로 준다.
    쿨메신저 상태는 바꾸지 않는다(조회만).
    """
    lines: list[str] = []
    try:
        user32 = ctypes.windll.user32
    except Exception as e:
        return f"윈도우에서만 동작합니다 ({e})"
    pid = _cool_pid()
    if pid is None:
        head = ("쿨메신저 프로세스를 찾지 못했어요 — 쪽지 프로그램을 켜고 "
                "쪽지 하나를 열어 둔 채 다시 시도해 주세요.\n"
                "아래 목록을 알려주시면 어떤 프로그램인지 찾을 수 있어요.\n"
                "지금 열린 창 (실행파일 / 창종류 / 제목):")
        allw = visible_windows(include_hidden=True, with_self=True)
        cands = candidate_rows(allw)
        out = [head]
        if cands:
            out.append("쪽지 프로그램으로 보이는 것 (숨은 창까지):")
            out += [f"   - {row}" for row in dedupe_windows(cands, 12)]
        out.append("지금 열린 창 전체:")
        out += [f"   - {row}" for row in dedupe_windows(visible_windows())]
        return "\n".join(out)
    wins = _cool_windows(pid)
    lines.append(f"쿨메신저 실행파일: {_exe_name(pid)} / 보이는 창 {len(wins)}개")
    lines.append("표기: 종류 이름 id class (좌,상,우,하) [지원 패턴]  — 앞에 있던 창부터")
    try:
        warmup()
    except Exception as e:
        lines.append(f"UIA 준비 실패: {e}")
        return "\n".join(lines)
    type_names = {v: k for k, v in
                  getattr(_uia, "known_control_types", {}).items()}
    walker = _uia.iuia.ControlViewWalker
    total = 0
    for i, hwnd in enumerate(wins, 1):
        cls = ctypes.create_unicode_buffer(128)
        user32.GetClassNameW(hwnd, cls, 128)
        title = _gettext(hwnd, 200)
        lines.append("")
        lines.append(f"===== 창{i}: class={cls.value} 제목='{title[:60]}' hwnd={hwnd} =====")
        kids = _children_by_class(hwnd)
        lines.append("자식 창 클래스: " + (", ".join(
            f"{c}×{len(h)}" for c, h in kids.items()) or "없음"))
        # 표준 윈도우 부품(버튼·글상자·목록)은 UIA 없이도 글자를 읽을 수 있다.
        # 2026-09-04 사용자 진단에서 쿨메신저 쪽지 창이 Button×35·SysListView32×2
        # 같은 표준 부품으로 돼 있음을 확인 — '회신' 버튼 이름과 목록 크기를
        # 여기서 바로 본다 (UIA가 놓치는 경우의 보험).
        lines.extend(_classic_controls(kids))
        try:
            root = _uia.iuia.ElementFromHandle(hwnd)
        except Exception as e:
            lines.append(f"(UIA 루트를 못 얻음: {e})")
            continue
        stack = [(root, 0)]
        count = 0
        while stack and total < max_nodes:
            el, depth = stack.pop()
            count += 1
            total += 1
            try:
                lines.append("  " * depth + _describe_element(el, type_names))
            except Exception as e:
                lines.append("  " * depth + f"(요소 설명 실패: {e})")
            if depth >= max_depth:
                continue
            # 자식들을 원래 순서대로 보이게 — 스택이라 뒤집어 넣는다
            children = []
            try:
                child = walker.GetFirstChildElement(el)
                while child is not None and len(children) < 500:
                    children.append(child)
                    child = walker.GetNextSiblingElement(child)
            except Exception:
                pass
            for c in reversed(children):
                stack.append((c, depth + 1))
        lines.append(f"(창{i} 요소 {count}개)")
        if total >= max_nodes:
            lines.append(f"(요소가 너무 많아 {max_nodes}개에서 멈췄어요)")
            break
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
