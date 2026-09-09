# -*- coding: utf-8 -*-
"""쿨메신저 조작 — 포스트잇 '제출'에서 그 쪽지를 **메시지 관리함**에서 찾아 열어 준다.

(2026-09-08 사용자 결정) 지금까지 이 프로그램은 쿨메신저를 읽기만 했다(capture.py).
'제출'을 사용자가 직접 눌렀을 때만 예외로
  ① 관리함이 없으면 열고  ② 받은메시지 목록에서 그 쪽지를 골라(선택) 오른쪽에
  내용이 뜨게 하고  ③ 관리함 창을 앞으로 올린다.
회신 버튼을 누르는 것, 내용을 쓰는 것, 보내는 것은 하지 않는다 — 사용자가 한다.

근거: 사용자 PC의 화면 구조 진단(coolm_ui_dump.txt, v2.7.0):
- 관리함 창 제목 '메시지 관리함', 쪽지 목록 List id 3195(SysListView32).
  ListItem의 Name=보낸사람, 자식 Text 3개=보낸사람/제목/날짜('2026/09/04 09:00:23 (금)').
  패턴 Invoke·SelectionItem·ScrollItem.
- 메인 창 제목 'COOLMESSENGER', 버튼 '메시지관리함 열기 (Ctrl+B)' id 3016.
- 관리함 버튼 '받은메시지' id 4337, '메시지 회신 (Ctrl+R)' id 3314(우리는 안 누른다).
id는 버전마다 바뀔 수 있어 이름으로도 찾는다. DB의 ReceiveDate도 같은
'yyyy/mm/dd HH:MM:SS' 꼴이라 초 단위로 정확히 대조된다.

UIA 호출은 백그라운드 스레드에서 해도 된다 — quick_capture._Loader가 같은 방식.
"""
from __future__ import annotations

import sys
import time
from dataclasses import dataclass
from datetime import datetime

MANAGER_TITLE = "메시지 관리함"
MAIN_TITLE = "COOLMESSENGER"
LIST_ID = "3195"
OPEN_MANAGER_BTN_ID, OPEN_MANAGER_BTN_TEXT = "3016", "메시지관리함"
RECEIVED_TAB_ID, RECEIVED_TAB_TEXT = "4337", "받은메시지"
RECEIVED_HEADER = "보낸사람"

MSG_NOT_WINDOWS = "윈도우에서만 동작합니다."
MSG_NO_COOLM = "쿨메신저가 켜져 있지 않아요."
MSG_NO_MANAGER = "메시지 관리함을 열지 못했어요."
MSG_NOT_FOUND = ("관리함 목록에서 이 쪽지를 찾지 못했어요 "
                 "(오래된 쪽지는 목록에 없을 수 있어요).")
# 사람에게 쪽지 쓰기 (2026-09-08 사용자 재설계 — 쪽지를 찾는 대신 사람을 찾는다)
SEARCH_EDIT_ID = "1708"        # 메인 창의 '이름(아이디) 또는 그룹명 검색' 칸
TREE_ID = "3013"               # 조직도 (SysTreeView32)
MSG_NO_NAME = "보낸 사람 이름을 몰라서 쪽지 쓰기를 열 수 없어요."
MSG_NO_MAIN = "쿨메신저 기본 창을 찾지 못했어요."

# 활성화 방법 — 조직도 항목엔 Invoke 패턴이 없고(진단 확인) 메인 창에 '쪽지 보내기'
# 버튼도 없어, 사람이 하는 동작인 **이름 더블클릭**이 유일한 길이다.
# (2026-09-09 사용자: "첫 번째도 빠르게") 시험 순서가 첫 번째를 느리게 했다 —
# 예전엔 기본동작 → Enter → 더블클릭 순서라 앞의 둘이 안 통하는 PC는 2초+2초를 그냥
# 기다렸다. 이제 더블클릭을 맨 앞에 둔다. 메시지로 보내는 더블클릭(post_double_click)이
# 첫 방법: 우리 포스트잇·펭귄이 그 자리를 가려도 트리로 직접 들어가고, 창이 앞에
# 없어도 되고, 쪽지 창이 모달로 열려도 우리 스레드가 멈추지 않는다(PostMessage).
STEPS = ("post_double_click", "double_click", "press_enter", "do_default_action")
# (2026-09-09 사용자: "잘 되는데 너무 느려") 안 통하는 방법마다 4초씩 기다리던 것이
# 느림의 주범. 통한 방법은 기억해 다음부터 맨 먼저 쓰고(넉넉히 기다림),
# 아직 모르는 방법을 탐색할 때만 짧게 기다린다 — 쪽지 쓰기 창은 보통 0.5초 안에
# 뜨므로 2초면 안전하고, 창이 뜬 뒤 다음 방법을 또 눌러 창이 둘 뜨는 일도 없다.
KNOWN_TIMEOUT = 4.0
PROBE_TIMEOUT = 2.0
MEMORY_KEY = "compose_method"


def step_order(remembered: str = "") -> list[str]:
    """기억된 방법을 맨 앞에, 나머지는 기본 순서로. 모르는 값은 무시."""
    rest = [s for s in STEPS if s != remembered]
    return ([remembered] if remembered in STEPS else []) + rest


def msg_no_person(name: str) -> str:
    return (f"쿨메신저 조직도에서 '{name}' 님을 찾지 못했어요 "
            "(이름이 조직도와 다르거나 전근하셨을 수 있어요).")


def msg_selected(name: str) -> str:
    return (f"쿨메신저에서 '{name}' 님을 찾아 선택해 뒀어요 — "
            "이름을 더블클릭하면 쪽지 쓰기가 열려요.")


def date_key(received: datetime) -> str:
    """목록의 날짜 칸과 대조할 열쇠 — '2026/09/04 09:00:23' (요일 꼬리는 무시)."""
    return received.strftime("%Y/%m/%d %H:%M:%S")


def name_only(s: str) -> str:
    """'정주은(정주은)' → '정주은'. DB Sender도 같은 꼴이지만 안전하게 이름만."""
    s = (s or "").strip()
    return s.split("(", 1)[0].strip() or s


def row_matches(sender_text: str, date_text: str, msg) -> bool:
    if not (date_text or "").strip().startswith(date_key(msg.received)):
        return False
    return name_only(sender_text) == name_only(getattr(msg, "sender", ""))


@dataclass
class Row:
    sender: str
    handle: object            # UIA 요소 (테스트에서는 아무 값)
    _date: str = ""           # 가짜 어댑터용


class UiaAdapter:
    """실제 쿨메신저를 UIA로 다룬다. 테스트에서는 같은 메서드를 가진 가짜로 바꿔 끼운다."""

    def __init__(self):
        import capture
        import comtypes.gen.UIAutomationClient as UIAC
        capture.warmup()
        self.cap, self.uia, self.UIAC = capture, capture._uia, UIAC
        self.d = self.uia.UIA_dll
        self.desc = self.uia.tree_scope["descendants"]
        self.kids = self.uia.tree_scope["children"]

    # ── 창 ──────────────────────────────────────────────────
    def _windows(self) -> list[int]:
        pid = self.cap._cool_pid()
        return self.cap._cool_windows(pid) if pid else []

    def _window_titled(self, title: str):
        for h in self._windows():
            if self.cap._window_title(h).strip() == title:
                return h
        return None

    def coolm_running(self) -> bool:
        return self.cap._cool_pid() is not None

    def manager_hwnd(self):
        return self._window_titled(MANAGER_TITLE)

    def open_manager(self, timeout: float = 6.0):
        """메인 창의 '메시지관리함 열기'를 눌러 관리함이 뜰 때까지 기다린다."""
        main = self._window_titled(MAIN_TITLE)
        btn = None
        if main is not None:
            btn = self._find_button(self._root(main), OPEN_MANAGER_BTN_ID,
                                    OPEN_MANAGER_BTN_TEXT)
        if btn is None:                    # 제목이 다른 버전: 버튼이 있는 창을 찾는다
            for h in self._windows():
                btn = self._find_button(self._root(h), OPEN_MANAGER_BTN_ID,
                                        OPEN_MANAGER_BTN_TEXT)
                if btn is not None:
                    break
        if btn is None:
            return None
        self._invoke(btn)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            h = self.manager_hwnd()
            if h:
                time.sleep(0.5)            # 목록이 채워질 시간
                return h
            time.sleep(0.2)
        return None

    # ── UIA 도우미 ──────────────────────────────────────────
    def _root(self, hwnd):
        return self.uia.iuia.ElementFromHandle(hwnd)

    def _cond(self, prop, value):
        return self.uia.iuia.CreatePropertyCondition(prop, value)

    def _find_button(self, root, auto_id: str, text: str):
        el = root.FindFirst(self.desc, self._cond(self.d.UIA_AutomationIdPropertyId, auto_id))
        if el is not None:
            return el
        arr = root.FindAll(self.desc, self._cond(self.d.UIA_ControlTypePropertyId,
                                                 self.d.UIA_ButtonControlTypeId))
        for i in range(arr.Length):
            b = arr.GetElement(i)
            try:
                if text in (b.CurrentName or ""):
                    return b
            except Exception:
                continue
        return None

    def _pattern(self, el, pattern_id, iface):
        return el.GetCurrentPattern(pattern_id).QueryInterface(iface)

    def _invoke(self, el) -> None:
        self._pattern(el, self.d.UIA_InvokePatternId,
                      self.UIAC.IUIAutomationInvokePattern).Invoke()

    def _has_received_header(self, lst) -> bool:
        arr = lst.FindAll(self.desc, self._cond(self.d.UIA_ControlTypePropertyId,
                                                self.d.UIA_HeaderItemControlTypeId))
        for i in range(arr.Length):
            try:
                if RECEIVED_HEADER in (arr.GetElement(i).CurrentName or ""):
                    return True
            except Exception:
                pass
        return False

    def _list(self, root):
        el = root.FindFirst(self.desc, self._cond(self.d.UIA_AutomationIdPropertyId, LIST_ID))
        if el is not None:
            return el
        arr = root.FindAll(self.desc, self._cond(self.d.UIA_ControlTypePropertyId,
                                                 self.d.UIA_ListControlTypeId))
        for i in range(arr.Length):
            if self._has_received_header(arr.GetElement(i)):
                return arr.GetElement(i)
        return arr.GetElement(0) if arr.Length else None

    def ensure_received(self, hwnd) -> None:
        """'보낸메시지' 탭이면 '받은메시지'로 바꾼다 (헤더에 '보낸사람'이 있는지로 판단)."""
        root = self._root(hwnd)
        lst = self._list(root)
        if lst is not None and self._has_received_header(lst):
            return
        btn = self._find_button(root, RECEIVED_TAB_ID, RECEIVED_TAB_TEXT)
        if btn is not None:
            self._invoke(btn)
            time.sleep(0.5)

    def rows(self, hwnd):
        """목록의 행들 — 보낸사람(Name)만 먼저 읽는다 (450개라도 빠르게)."""
        lst = self._list(self._root(hwnd))
        if lst is None:
            return
        arr = lst.FindAll(self.kids, self._cond(self.d.UIA_ControlTypePropertyId,
                                                self.d.UIA_ListItemControlTypeId))
        for i in range(arr.Length):
            el = arr.GetElement(i)
            try:
                yield Row(sender=el.CurrentName or "", handle=el)
            except Exception:
                continue

    def row_date(self, row: Row) -> str:
        """보낸사람이 맞는 행에서만 부른다 — 자식 Text 가운데 날짜 꼴(yyyy/mm/dd …)."""
        arr = row.handle.FindAll(self.kids, self._cond(self.d.UIA_ControlTypePropertyId,
                                                       self.d.UIA_TextControlTypeId))
        texts = []
        for i in range(arr.Length):
            try:
                texts.append(arr.GetElement(i).CurrentName or "")
            except Exception:
                texts.append("")
        for t in reversed(texts):                     # 날짜는 마지막 칸
            if len(t) >= 19 and t[4] == "/" and t[7] == "/":
                return t
        return texts[-1] if texts else ""

    def select(self, row: Row) -> None:
        try:
            self._pattern(row.handle, self.d.UIA_ScrollItemPatternId,
                          self.UIAC.IUIAutomationScrollItemPattern).ScrollIntoView()
        except Exception:
            pass
        self._pattern(row.handle, self.d.UIA_SelectionItemPatternId,
                      self.UIAC.IUIAutomationSelectionItemPattern).Select()

    # ── 사람에게 쪽지 쓰기 ──────────────────────────────────
    def main_hwnd(self):
        """쿨메신저 기본 창 — 제목이 다른 버전은 검색칸이 있는 창으로 찾는다."""
        h = self._window_titled(MAIN_TITLE)
        if h is not None:
            return h
        for cand in self._windows():
            try:
                if self._search_edit(self._root(cand), cand) is not None:
                    return cand
            except Exception:
                continue
        return None

    def windows(self) -> list[int]:
        return self._windows()

    def _control(self, hwnd, cls: str, ctrl_id: str):
        """메인 창의 Win32 자식 컨트롤을 hwnd로 바로 잡는다 (UIA 트리 훑기 없이).

        Win32 컨트롤의 UIA AutomationId는 곧 컨트롤 ID(GetDlgCtrlID)다. 조직도
        항목 수백 개를 프로세스 밖에서 하나씩 세는 FindFirst(descendants)보다
        수백 배 빠르다. 같은 클래스가 하나뿐이면 ID가 달라도 그것을 쓴다.
        """
        if not hwnd:
            return None
        import ctypes
        kids = self.cap._children_by_class(hwnd).get(cls, [])
        pick = None
        for h in kids:
            if str(ctypes.windll.user32.GetDlgCtrlID(h)) == ctrl_id:
                pick = h
                break
        if pick is None and len(kids) == 1:
            pick = kids[0]
        return self._root(pick) if pick else None

    def _search_edit(self, root, hwnd=None):
        try:
            el = self._control(hwnd, "Edit", SEARCH_EDIT_ID)
        except Exception:
            el = None
        if el is not None:
            return el
        el = root.FindFirst(self.desc,
                            self._cond(self.d.UIA_AutomationIdPropertyId,
                                       SEARCH_EDIT_ID))
        if el is not None:
            return el
        arr = root.FindAll(self.desc, self._cond(self.d.UIA_ControlTypePropertyId,
                                                 self.d.UIA_EditControlTypeId))
        for i in range(arr.Length):
            e = arr.GetElement(i)
            try:
                if e.GetCurrentPropertyValue(self.d.UIA_IsValuePatternAvailablePropertyId):
                    return e
            except Exception:
                continue
        return None

    def search_person(self, hwnd, name: str) -> None:
        """조직도 검색칸에 이름을 넣어 목록을 좁힌다 (사람이 하는 것과 같은 동작).

        필터가 안 걸리는 버전이어도 다음 단계가 트리 전체를 훑으므로 문제없다.
        """
        edit = self._search_edit(self._root(hwnd), hwnd)
        if edit is None:
            return
        self._pattern(edit, self.d.UIA_ValuePatternId,
                      self.UIAC.IUIAutomationValuePattern).SetValue(name)
        # 고정 sleep 없음 — find_person이 필터 결과가 보일 때까지만 기다린다

    def _tree(self, root, hwnd=None):
        try:
            el = self._control(hwnd, "SysTreeView32", TREE_ID)
        except Exception:
            el = None
        if el is not None:
            return el
        el = root.FindFirst(self.desc,
                            self._cond(self.d.UIA_AutomationIdPropertyId, TREE_ID))
        if el is not None:
            return el
        arr = root.FindAll(self.desc, self._cond(self.d.UIA_ControlTypePropertyId,
                                                 self.d.UIA_TreeControlTypeId))
        return arr.GetElement(0) if arr.Length else None

    def _tree_items(self, tree) -> list[tuple[object, str, bool]]:
        """(요소, 이름, 화면밖) 목록 — CacheRequest로 한 번의 왕복에 읽는다.

        항목마다 CurrentName·CurrentIsOffscreen을 따로 부르면 수백×2 회 프로세스
        왕복이다. 캐시가 안 되는 환경이면 예전 방식으로 폴백.
        """
        cond = self._cond(self.d.UIA_ControlTypePropertyId,
                          self.d.UIA_TreeItemControlTypeId)
        out = []
        try:
            cache = self.uia.iuia.CreateCacheRequest()
            cache.AddProperty(self.d.UIA_NamePropertyId)
            cache.AddProperty(self.d.UIA_IsOffscreenPropertyId)
            arr = tree.FindAllBuildCache(self.desc, cond, cache)
            for i in range(arr.Length):
                el = arr.GetElement(i)
                try:
                    out.append((el, el.CachedName or "", bool(el.CachedIsOffscreen)))
                except Exception:
                    continue
            return out
        except Exception:
            out = []
        arr = tree.FindAll(self.desc, cond)
        for i in range(arr.Length):
            el = arr.GetElement(i)
            try:
                out.append((el, el.CurrentName or "", bool(el.CurrentIsOffscreen)))
            except Exception:
                continue
        return out

    def find_person(self, hwnd, name: str, wait: float = 0.8):
        """조직도에서 그 사람의 항목. 항목 이름은 '(정주은)3-1/수학/8531' 꼴.

        '(이름)' 정확 일치를 먼저, 없으면 이름 포함으로 완화한다. 화면에
        보이는 항목을 우선하고, 접혀 있는 항목이면 부모를 펼쳐서 꺼낸다.
        검색 필터가 걸리는 데 시간이 조금 걸리므로 화면에 보이는 정확 일치가
        나올 때까지 짧게(0.05초 간격, 최대 wait초) 다시 읽는다 — 고정 0.4초
        sleep 대신 필요한 만큼만 기다린다.
        """
        tree = self._tree(self._root(hwnd), hwnd)
        if tree is None:
            return None
        exact, loose = f"({name})", name
        deadline = time.monotonic() + wait
        best = {}
        while True:
            best = {}
            for el, label, off in self._tree_items(tree):
                if exact in label:
                    rank = 0 if not off else 1
                elif loose in label:
                    rank = 2 if not off else 3
                else:
                    continue
                best.setdefault(rank, el)
                if rank == 0:
                    break
            if 0 in best or time.monotonic() >= deadline:
                break
            time.sleep(0.05)
        for rank in (0, 1, 2, 3):
            el = best.get(rank)
            if el is None:
                continue
            if rank in (1, 3):
                self._expand_ancestors(el)
            return el
        return None

    def _expand_ancestors(self, el) -> None:
        """접힌 상위 조직을 위에서부터 펼쳐 항목이 화면에 나오게 한다."""
        walker = self.uia.iuia.ControlViewWalker
        chain, cur = [], el
        for _ in range(12):
            try:
                cur = walker.GetParentElement(cur)
            except Exception:
                break
            if cur is None:
                break
            chain.append(cur)
        for parent in reversed(chain):
            try:
                self._pattern(parent, self.d.UIA_ExpandCollapsePatternId,
                              self.UIAC.IUIAutomationExpandCollapsePattern).Expand()
            except Exception:
                continue
        time.sleep(0.05)

    def select_person(self, el) -> None:
        try:
            self._pattern(el, self.d.UIA_ScrollItemPatternId,
                          self.UIAC.IUIAutomationScrollItemPattern).ScrollIntoView()
        except Exception:
            pass
        self._pattern(el, self.d.UIA_SelectionItemPatternId,
                      self.UIAC.IUIAutomationSelectionItemPattern).Select()

    # 활성화 방법들 — STEPS 순서로 시도한다 (통한 것은 compose_method로 기억).
    def _tree_hwnd(self, hwnd) -> int:
        """조직도(SysTreeView32) 창 핸들 — 컨트롤 ID 3013 우선, 없으면 첫 트리."""
        import ctypes
        trees = self.cap._children_by_class(hwnd).get("SysTreeView32", [])
        if not trees:
            raise RuntimeError("조직도 창을 찾지 못함")
        for t in trees:
            if str(ctypes.windll.user32.GetDlgCtrlID(t)) == TREE_ID:
                return t
        return trees[0]

    @staticmethod
    def _center(el) -> tuple[int, int]:
        r = el.CurrentBoundingRectangle
        if r.right <= r.left or r.bottom <= r.top:
            raise RuntimeError("항목이 화면에 없음")
        return (r.left + r.right) // 2, (r.top + r.bottom) // 2

    def post_double_click(self, el, hwnd) -> None:
        """항목 가운데에 더블클릭 **메시지**를 조직도 창으로 직접 보낸다.

        WM_LBUTTONDOWN → UP → DBLCLK → UP을 PostMessage로 (pywinauto double_click과
        같은 방식). 실제 마우스 입력과 달리 위를 덮은 다른 창(항상 위 포스트잇 등)에
        가로막히지 않고, 쿨메신저가 앞에 없어도 된다. 앱이 GetCursorPos로 위치를 읽는
        경우를 대비해 보내는 동안만 커서를 항목 위로 옮기고 되돌린다.
        """
        import ctypes
        from ctypes import wintypes
        tree = self._tree_hwnd(hwnd)
        x, y = self._center(el)
        user32 = ctypes.windll.user32
        pt = wintypes.POINT(x, y)
        user32.ScreenToClient(tree, ctypes.byref(pt))
        lparam = (pt.y & 0xFFFF) << 16 | (pt.x & 0xFFFF)
        old = wintypes.POINT()
        user32.GetCursorPos(ctypes.byref(old))
        try:
            user32.SetCursorPos(x, y)
            for msg, wparam in ((0x0201, 1), (0x0202, 0),     # LBUTTONDOWN(MK_LBUTTON)/UP
                                (0x0203, 1), (0x0202, 0)):    # LBUTTONDBLCLK/UP
                user32.PostMessageW(tree, msg, wparam, lparam)
            time.sleep(0.15)         # 앱이 메시지를 처리한 뒤 커서를 되돌린다
        finally:
            user32.SetCursorPos(old.x, old.y)

    def do_default_action(self, el, hwnd) -> None:
        self._pattern(el, self.d.UIA_LegacyIAccessiblePatternId,
                      self.UIAC.IUIAutomationLegacyIAccessiblePattern).DoDefaultAction()

    def press_enter(self, el, hwnd) -> None:
        import ctypes
        t = self._tree_hwnd(hwnd)
        user32 = ctypes.windll.user32
        user32.SendMessageW(t, 0x0100, 0x0D, 0)         # WM_KEYDOWN VK_RETURN
        user32.SendMessageW(t, 0x0101, 0x0D, 0)         # WM_KEYUP
        # 기다림은 new_window_after가 한다

    def double_click(self, el, hwnd) -> None:
        """항목 가운데를 실제로 더블클릭한다 — 커서는 원래 자리로 되돌린다."""
        import ctypes
        from ctypes import wintypes
        x, y = self._center(el)
        user32 = ctypes.windll.user32
        old = wintypes.POINT()
        user32.GetCursorPos(ctypes.byref(old))
        try:
            user32.SetCursorPos(x, y)
            for _ in range(2):
                user32.mouse_event(0x0002, 0, 0, 0, 0)   # LEFTDOWN
                user32.mouse_event(0x0004, 0, 0, 0, 0)   # LEFTUP
            time.sleep(0.1)          # 클릭이 큐에 들어간 뒤 커서를 되돌린다
        finally:
            user32.SetCursorPos(old.x, old.y)

    def new_window_after(self, before, timeout: float = 4.0):
        """쿨메신저 창이 하나 늘어나면 그 hwnd (쪽지 쓰기 창이 떴다는 뜻)."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            for h in self._windows():
                if h not in before:
                    return h
            time.sleep(0.05)
        return None

    def front(self, hwnd) -> bool:
        import ctypes
        user32 = ctypes.windll.user32
        if user32.IsIconic(hwnd):
            user32.ShowWindow(hwnd, 9)                # SW_RESTORE
        return bool(user32.SetForegroundWindow(hwnd))


def open_message(msg, ui=None) -> tuple[bool, str]:
    """관리함에서 msg를 찾아 선택하고 창을 앞으로. (성공 여부, 실패 이유)."""
    try:
        if ui is None:
            if sys.platform != "win32":
                return False, MSG_NOT_WINDOWS
            ui = UiaAdapter()
        if not ui.coolm_running():
            return False, MSG_NO_COOLM
        hwnd = ui.manager_hwnd() or ui.open_manager()
        if not hwnd:
            return False, MSG_NO_MANAGER
        ui.ensure_received(hwnd)
        target = name_only(getattr(msg, "sender", ""))
        for row in ui.rows(hwnd):
            if name_only(row.sender) != target:
                continue                           # 다른 사람 행은 자식을 읽지 않는다
            if row_matches(row.sender, ui.row_date(row), msg):
                ui.select(row)
                ui.front(hwnd)
                return True, ""
        return False, MSG_NOT_FOUND
    except Exception as e:                         # 어디서 깨져도 대체 경로로
        return False, f"쿨메신저를 다루는 중 문제가 생겼어요: {e}"


def compose_to(name: str, ui=None, memory: dict | None = None) -> tuple[str, str]:
    """그 사람에게 **새 쪽지 쓰기** 창을 열어 준다 (2026-09-08 사용자 재설계).

    관리함에서 옛 쪽지를 찾는 방식은 목록에 없는 쪽지가 많아 자주 실패했다.
    이제는 조직도에서 사람을 찾아 쪽지 쓰기를 연다 — 쪽지가 아무리 오래돼도
    보낸 사람 이름만 알면 된다. 내용 작성·전송은 하지 않는다.

    memory: {"compose_method": …} 꼴 dict. 통한 활성화 방법을 여기에 기록하고,
    다음 호출에서는 그 방법을 맨 먼저 쓴다 (호출부가 config에 저장해 준다).

    반환 (상태, 안내문):
      "opened"   — 쪽지 쓰기 창이 떴다 (할 일 없음)
      "selected" — 사람은 찾아 선택했지만 창이 안 떴다 (더블클릭 안내)
      "failed"   — 못 했다 (이유를 안내문에)
    """
    person = name_only(name)
    if not person:
        return "failed", MSG_NO_NAME
    remembered = (memory or {}).get(MEMORY_KEY, "") or ""
    try:
        if ui is None:
            if sys.platform != "win32":
                return "failed", MSG_NOT_WINDOWS
            ui = UiaAdapter()
        if not ui.coolm_running():
            return "failed", MSG_NO_COOLM
        hwnd = ui.main_hwnd()
        if not hwnd:
            return "failed", MSG_NO_MAIN
        ui.front(hwnd)
        ui.search_person(hwnd, person)
        item = ui.find_person(hwnd, person)
        if item is None:
            return "failed", msg_no_person(person)
        ui.select_person(item)
        before = set(ui.windows())
        for step in step_order(remembered):
            try:
                getattr(ui, step)(item, hwnd)
            except Exception:
                continue          # 이 버전에서 안 통하는 방법 → 다음 방법으로
            wait = KNOWN_TIMEOUT if step == remembered else PROBE_TIMEOUT
            if ui.new_window_after(before, timeout=wait):
                if memory is not None:
                    memory[MEMORY_KEY] = step
                return "opened", ""
        return "selected", msg_selected(person)
    except Exception as e:
        return "failed", f"쿨메신저를 다루는 중 문제가 생겼어요: {e}"
