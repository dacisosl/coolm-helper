# -*- coding: utf-8 -*-
"""사용설명서 스크린샷 생성기.

앱의 각 창을 (화면에 띄우지 않고) 데모 데이터로 렌더링해 캡처하고,
base64로 docs/사용설명서.template.html의 {{SHOT:이름}} 자리에 삽입해
docs/사용설명서.html(이미지 포함 단일 파일)을 만든다.

⚠ 실제 쪽지는 절대 사용하지 않는다 — 캡처 데이터는 전부 데모(가짜).
사용: python tools/make_screenshots.py
"""
import base64
import io
import os
import shutil
import sys
import tempfile
from datetime import datetime, timedelta

# offscreen 플랫폼은 한글 폰트를 못 찾아 □로 렌더링된다.
# 일반 플랫폼에서 show() 없이 grab()하면 화면에 안 뜨면서 폰트가 제대로 나온다.
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

from PyQt6.QtCore import QBuffer
from PyQt6.QtWidgets import QApplication

app = QApplication([])

# 실제 화면 캡처 기능을 차단 — 스크린샷에 진짜 쪽지가 들어가면 안 된다
import capture
capture.read_current_message = lambda: None

from parser import demo_data, pipeline
from store.event_store import EventStore

shots: dict[str, str] = {}


def grab(widget, name: str) -> None:
    # deleteLater로 예약된 옛 위젯(유령 잔상)까지 정리한 뒤 캡처
    from PyQt6.QtCore import QCoreApplication, QEvent
    for _ in range(3):
        app.processEvents()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    pm = widget.grab()
    buf = QBuffer()
    buf.open(QBuffer.OpenModeFlag.WriteOnly)
    pm.save(buf, "PNG")
    b64 = base64.b64encode(bytes(buf.data())).decode()
    shots[name] = f'<img class="shot" alt="{name} 화면" src="data:image/png;base64,{b64}">'
    print(f"  캡처: {name} ({pm.width()}x{pm.height()}, {len(b64)//1024}KB)")


# ── 데모 저장소 (가짜 일정) ─────────────────────────────────
tmp = tempfile.mkdtemp(prefix="coolm_shot_")
store = EventStore(tmp, "store")
now = datetime.now()


def d(days, h=0, m=0):
    t = now + timedelta(days=days)
    return t.replace(hour=h, minute=m)


ev1 = store.add("교직원 회의", d(1, 15, 30), all_day=False)
ev2 = store.add("학폭위 심의", d(4, 14, 0), all_day=False)
store.update(ev2.id, priority="높음")
store.add("성적 입력 마감", d(2), is_deadline=True)
store.add("개교기념일 휴업", d(5))
store.add("수학여행", d(7), end=d(9), all_day=True)
# 캘린더 캡처용 — 같은 날 일정 여러 건
store.add("학년부장 협의회", d(4, 10, 0), all_day=False)
ev3 = store.add("상담실 운영 회의", d(4, 16, 30), all_day=False)
store.update(ev3.id, priority="낮음")

roster = demo_data.demo_roster()
msgs = demo_data.demo_messages(now)
cands = [c for m in msgs for c in pipeline.candidates_from_message(m, roster)]

# ── 1. 바로 등록 (QuickDialog, 데모 텍스트 채움) ─────────────
from ui.quick_dialog import QuickDialog

qd = QuickDialog(BASE, store, google_enabled=False)
qd._fill_from_text(msgs[1].title, msgs[1].body, origin="화면")
qd.resize(520, 500)
grab(qd, "quick")

# ── 2. 쪽지 목록 (ReviewDialog, 데모 후보) ───────────────────
from ui.review_dialog import ReviewDialog

rd = ReviewDialog(cands, store, source="demo")
rd.list.setCurrentRow(1)
# 한 건은 등록된 모습으로 (연두 배경 시연)
rd.rows[0].set_registered(True)
rd.resize(860, 540)
grab(rd, "review")

# ── 3. 캘린더 ────────────────────────────────────────────────
from PyQt6.QtCore import QDate
from ui.calendar_view import CalendarWindow

cw = CalendarWindow(store)
qd2 = ev2.start_dt
cw.cal.setSelectedDate(QDate(qd2.year, qd2.month, qd2.day))  # 선택 시 자동 갱신
cw.resize(800, 520)
grab(cw, "calendar")

# ── 4. 알림 말풍선 ───────────────────────────────────────────
from PyQt6.QtWidgets import QWidget
from ui.alerts import AlertBubble

anchor = QWidget()
anchor.resize(50, 50)
bub = AlertBubble(["⏰ 마감 1일 전\n성적 입력 마감",
                   "📋 오늘 일정이 3건 있습니다"], anchor)
bub.adjustSize()
grab(bub, "bubble")

# ── 5. 설정 (일반 탭) ────────────────────────────────────────
from ui.settings_dialog import SettingsDialog

cfg = dict(pipeline.DEFAULT_CONFIG)
sd = SettingsDialog(BASE, cfg, store)
sd.resize(470, 460)
grab(sd, "settings")

# ── 템플릿에 삽입 ───────────────────────────────────────────
tpl_path = os.path.join(BASE, "docs", "사용설명서.template.html")
out_path = os.path.join(BASE, "docs", "사용설명서.html")
html = open(tpl_path, encoding="utf-8").read()
for name, tag in shots.items():
    html = html.replace("{{SHOT:" + name + "}}", tag)
# 안 채워진 토큰은 제거
import re
html = re.sub(r"\{\{SHOT:[a-z_]+\}\}", "", html)
open(out_path, "w", encoding="utf-8").write(html)
size_kb = os.path.getsize(out_path) // 1024
print(f"\n생성 완료: {out_path} ({size_kb}KB, 캡처 {len(shots)}장)")

shutil.rmtree(tmp, ignore_errors=True)
