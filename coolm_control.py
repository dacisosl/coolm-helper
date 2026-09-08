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
            if self.cap._gettext(h, 200).strip() == title:
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
