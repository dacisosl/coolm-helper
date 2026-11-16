# -*- coding: utf-8 -*-
"""사용설명서 생성기 — 지금 앱 화면을 데모 데이터로 그려 설명서에 넣는다.

앱의 각 창을 화면에 띄우지 않고 렌더링해 캡처(grab)하고, base64로
docs/사용설명서.template.html의 {{SHOT:이름}} 자리에 넣어
docs/사용설명서.html(이미지가 들어 있는 파일 하나)을 만든다. 설치파일에 동봉된다.

⚠ 실제 쪽지는 절대 쓰지 않는다 — 화면 읽기(capture)를 막고 데모(가짜)만 쓴다.

사용:
    python tools/make_screenshots.py                 # docs/사용설명서.html 갱신
    python tools/make_screenshots.py --png 폴더       # 캡처 PNG도 따로 저장(확인용)
    python tools/make_screenshots.py --body 파일.html  # <html> 틀 없는 본문판(웹 게시용)

리눅스(서버)에서는 QT_QPA_PLATFORM=offscreen + 한글 글꼴(Noto Sans CJK)로 돌린다.
윈도우에서는 일반 플랫폼에서 show() 없이 grab()한다(offscreen은 한글이 □로 나온다).
"""
import argparse
import base64
import os
import re
import shutil
import sys
import tempfile
from datetime import date, datetime, timedelta

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
os.environ.setdefault("COOLM_NO_CAPTURE", "1")

ap = argparse.ArgumentParser()
ap.add_argument("--png", help="캡처 PNG를 저장할 폴더(확인용)")
ap.add_argument("--body", help="<html> 틀 없이 본문만 담은 파일도 쓴다")
args = ap.parse_args()

from PyQt6.QtCore import QBuffer, QCoreApplication, QDate, QEvent, QLocale, QSize
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QApplication, QWidget

# 선생님 PC처럼 한국어로 (달력의 '11월'·'월화수…') — 서버 기본 언어는 영어라서
QLocale.setDefault(QLocale(QLocale.Language.Korean, QLocale.Country.SouthKorea))
app = QApplication([])
if sys.platform != "win32":
    f = QFont()
    f.setFamilies(["Noto Sans CJK KR", "DejaVu Sans"])   # ✕·– 같은 기호는 DejaVu로
    f.setPointSize(9)
    app.setFont(f)
from ui import theme
app.setStyleSheet(theme.SYSTEM_QSS)

# 실제 화면 캡처 기능을 차단 — 스크린샷에 진짜 쪽지가 들어가면 안 된다
import capture
capture.read_current_message = lambda: None

from parser import demo_data, pipeline
from store.event_store import EventStore
from store.todo_store import TodoStore

shots: dict[str, str] = {}
if args.png:
    os.makedirs(args.png, exist_ok=True)


def settle() -> None:
    for _ in range(4):
        app.processEvents()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def put(pm, name: str, alt: str, cls: str = "shot") -> None:
    if args.png:
        pm.save(os.path.join(args.png, f"{name}.png"))
    buf = QBuffer()
    buf.open(QBuffer.OpenModeFlag.WriteOnly)
    pm.save(buf, "PNG")
    b64 = base64.b64encode(bytes(buf.data())).decode()
    w, h = pm.width(), pm.height()
    shots[name] = (f'<img class="{cls}" alt="{alt}" width="{w}" height="{h}" '
                   f'src="data:image/png;base64,{b64}">')
    print(f"  캡처: {name} ({w}x{h}, {len(b64) // 1024}KB)")


def grab(widget, name: str, alt: str, cls: str = "shot") -> None:
    """화면에 띄우지 않고 그린다 (offscreen에서는 show해도 화면에 안 나온다)."""
    if sys.platform != "win32":
        widget.show()
    settle()
    put(widget.grab(), name, alt, cls)
    if sys.platform != "win32":
        widget.hide()


# ── 데모 저장소 (가짜 일정·할 일) ───────────────────────────
tmp = tempfile.mkdtemp(prefix="coolm_shot_")
store = EventStore(tmp, "store")
todos = TodoStore.shared(tmp)
now = datetime.now().replace(second=0, microsecond=0)
today = now.date()
week0 = today - timedelta(days=(today.weekday() + 1) % 7)       # 이번 주 일요일


def at(day: date, h=0, m=0):
    return datetime(day.year, day.month, day.day, h, m)


# 설명서 전체가 따라가는 한 통의 데모 쪽지: 더블클릭 → 포스트잇 → 알림 → 제출·회신
from parser.db_reader import Message

d1, d2 = today + timedelta(days=3), today + timedelta(days=9)
PICK_SENDER = "교무부(데모)"
pick_received = (now - timedelta(hours=1)).replace(second=5)
m_pick = Message(key=-2000, sender=PICK_SENDER, received=pick_received,
                 title="2학기 공개수업 안내",
                 body=(f"2학기 공개수업 안내드립니다.\n"
                       f"공개수업 신청서를 {d1.month}월 {d1.day}일까지 교무부로 제출해 주세요.\n"
                       f"사전 협의회는 {d2.month}월 {d2.day}일 오후 3시 시청각실에서 열립니다.\n"
                       f"참석 부탁드립니다."))
e_pick = store.add("공개수업 신청서 제출", at(d1), is_deadline=True,
                   memo=m_pick.body, sender=PICK_SENDER,
                   **pipeline.msg_fingerprint(Message(1, PICK_SENDER, pick_received,
                                                      m_pick.title, m_pick.body)))

e_meet = store.add("교직원 회의", at(today + timedelta(days=1), 15, 30), all_day=False,
                   sender="교무부장(데모)")
e_hak = store.add("학폭위 심의", at(today + timedelta(days=4), 14, 0), all_day=False)
store.update(e_hak.id, priority="높음")
e_grade = store.add("성적 입력 마감", at(today + timedelta(days=2)), is_deadline=True,
                    memo="1학기 성적 입력을 기한 내에 제출 바랍니다.",
                    sender="연구부(데모)")
store.add("개교기념일 휴업", at(today + timedelta(days=5)))
store.add("수학여행", at(today + timedelta(days=7)), end=at(today + timedelta(days=9)))
store.add("오늘 수업 공개", at(today, 10, 0), all_day=False)
# 보드 위젯 — 이번 주 일요일 기준으로 고정 배치(요일이 바뀌어도 그림이 비슷하게)
b1 = store.add("면접자료 제출 마감", at(week0 + timedelta(days=1)), is_deadline=True)
b2 = store.add("1학년 수행평가 실시", at(week0 + timedelta(days=4)))
b3 = store.add("글로벌연수 발표", at(week0 + timedelta(days=6)))
todos.add("수행평가 준비", event_id=b2.id)
todos.add("글로벌연수 발표 준비", event_id=b3.id)
todos.add("시험문제 만들기")
t_done = todos.add("수업준비 (8·9차시, 모고풀이)")
todos.toggle(t_done.id, True)
todos.add("1학년 수업준비 (모고풀이)")

roster = demo_data.demo_roster()
msgs = demo_data.demo_messages(now)
config = dict(pipeline.DEFAULT_CONFIG)
config["desk_widgets"] = {}
config["character_mode"] = True


def conf(**kw):
    c = {"enabled": True, "geometry": None, "opacity": 100,
         "always_on_top": False, "font_scale": 100}
    c.update(kw)
    return c


print("사용설명서 캡처 시작 (데모 데이터)")

# ── 펭귄과 아이콘 ────────────────────────────────────────────
from ui.icons import icon
from ui.penguin_icon import penguin_pixmap

put(penguin_pixmap(BASE, 120, "base"), "penguin", "쿨비서 펭귄", "peng")
put(penguin_pixmap(BASE, 120, "sleep"), "penguin_sleep", "잠든 펭귄", "peng")
for name in ("pin", "mail", "gear"):
    put(icon(name, 22).pixmap(QSize(22, 22)), f"icon_{name}", name, "ico")

# ── ⚡ 날짜 선택 창 ──────────────────────────────────────────
from ui.quick_capture import DatePickDialog, date_options

opts = date_options(pipeline.candidates_from_message(m_pick, roster))
dp = DatePickDialog(opts, m_pick.body)
dp.resize(720, 430)
grab(dp, "datepick", "날짜 선택 창")

# ── 쪽지 목록 ────────────────────────────────────────────────
from ui.review_dialog import ReviewDialog

cands = [c for m in msgs for c in pipeline.candidates_from_message(m, roster)]
rd = ReviewDialog(cands, store, source="demo")
rd.list.setCurrentRow(2)            # 학폭위 쪽지 — 이름·전화번호가 빨갛게 표시되는 예
rd.rows[0].set_registered(True)
rd.resize(880, 540)
grab(rd, "review", "쪽지 목록 창")

# ── 포스트잇 ────────────────────────────────────────────────
from ui.desk_note import PostItWidget

pn = PostItWidget(store, config, tmp, conf(event_id=e_pick.id, color="yellow"), e_pick)
pn._save_config = lambda: None
pn.resize(240, 220)
grab(pn, "postit", "바탕화면 포스트잇")

# ── 회신 실패 시 안내 창 (원본 쪽지) ─────────────────────────
from ui.reply_helper import SourceMessageDialog

sdlg = SourceMessageDialog(e_meet, msgs[0], [],
                           reason="쪽지는 찾았지만 회신 창이 뜨지 않았어요.\n"
                                  "어디까지 됐나: 관리함 ✓ → 쪽지 ✓(목록) → 회신 창 안 뜸(command)")
sdlg.resize(560, 470)
grab(sdlg, "source", "원본 쪽지 안내 창")

# ── 캘린더 창 ───────────────────────────────────────────────
from ui.calendar_view import CalendarWindow

cw = CalendarWindow(store)
hd = e_hak.start_dt
cw.cal.setSelectedDate(QDate(hd.year, hd.month, hd.day))
cw.resize(820, 540)
grab(cw, "calendar", "캘린더 창")

# ── 바탕화면 위젯 ────────────────────────────────────────────
from ui.desk_board import BoardWidget
from ui.desk_widgets import PlannerWidget, SimpleTodoWidget, TodayTodoWidget, WeeklyWidget

for name, cls_, size, kw, alt in (
        ("board", BoardWidget, (400, 460), {"view": "table"}, "일정 · 할 일 보드 (표)"),
        ("board_days", BoardWidget, (400, 520), {"view": "days"}, "일정 · 할 일 보드 (날짜)"),
        ("weekly", WeeklyWidget, (720, 300), {}, "주간 일정 위젯"),
        ("planner", PlannerWidget, (380, 540), {"show_detail": True}, "캘린더 · 할 일 위젯"),
        ("simple", SimpleTodoWidget, (560, 260), {}, "할 일 보드 위젯"),
        ("today", TodayTodoWidget, (260, 300), {}, "오늘 할 일 위젯")):
    w = cls_(store, config, tmp, conf(**kw))
    w._save_config = lambda: None
    w.resize(*size)
    settle()
    w.refresh()
    grab(w, name, alt)
    w.close()

# ── 시작 알림 포스트잇 ──────────────────────────────────────
from ui.alert_note import AlertNote
from ui.alerts import build_alerts

an = AlertNote(build_alerts(store, today, 3), None, today=today)
an.adjustSize()
grab(an, "alert", "시작 알림 포스트잇")

# ── 설정 ────────────────────────────────────────────────────
from ui.settings_dialog import SettingsDialog

scfg = dict(config)
scfg["desk_widgets"] = {k: conf(enabled=k in ("board", "weekly"))
                        for k in pipeline.DESK_KINDS}
sd = SettingsDialog(tmp, scfg, store)
sd.resize(560, 620)
grab(sd, "settings", "설정 창")

# ── 템플릿에 넣기 ───────────────────────────────────────────
tpl_path = os.path.join(BASE, "docs", "사용설명서.template.html")
out_path = os.path.join(BASE, "docs", "사용설명서.html")
body = open(tpl_path, encoding="utf-8").read()
from version import APP_VERSION
body = body.replace("{{VERSION}}", APP_VERSION)
import html as _html
WD = "월화수목금토일"


def mdate(dt, sec=True):
    return dt.strftime("%Y/%m/%d %H:%M" + (":%S" if sec else "")) + f" ({WD[dt.weekday()]})"


body_esc = _html.escape(m_pick.body)
body_mark = body_esc
for dd in (d1, d2):
    frag = f"{dd.month}월 {dd.day}일"
    body_mark = body_mark.replace(frag, f"<mark>{frag}</mark>", 1)
fills = {
    "PICK_SENDER": PICK_SENDER, "PICK_SENDER_NAME": PICK_SENDER.split("(")[0],
    "PICK_TITLE": m_pick.title, "PICK_RECEIVED": mdate(pick_received),
    "PICK_RECEIVED_SHORT": mdate(pick_received, sec=False),
    "PICK_BODY": body_mark, "PICK_BODY_PLAIN": body_esc,
    "OLD1": mdate(pick_received - timedelta(days=13, hours=2), sec=False),
    "OLD2": mdate(pick_received - timedelta(days=34, hours=5), sec=False),
}
for k, v in fills.items():
    body = body.replace("{{" + k + "}}", v)
left = sorted(set(re.findall(r"\{\{([A-Z_]+)\}\}", body)))
if left:
    print("  ⚠ 안 채운 글자 자리:", ", ".join(left))
for name, tag in shots.items():
    body = body.replace("{{SHOT:" + name + "}}", tag)
missing = re.findall(r"\{\{SHOT:([a-z_]+)\}\}", body)
if missing:
    print("  ⚠ 캡처 없는 자리:", ", ".join(sorted(set(missing))))
body = re.sub(r"\{\{SHOT:[a-z_]+\}\}", "", body)

# 설치 폴더에서 바로 여는 판: 문서 틀을 붙인다 (웹 게시판은 틀 없이)
full = ('<!doctype html>\n<html lang="ko">\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
        + body + "\n</html>\n")
open(out_path, "w", encoding="utf-8").write(full)
print(f"\n생성 완료: {out_path} ({os.path.getsize(out_path) // 1024}KB, 캡처 {len(shots)}장)")
if args.body:
    open(args.body, "w", encoding="utf-8").write(body)
    print(f"본문판: {args.body}")

shutil.rmtree(tmp, ignore_errors=True)
