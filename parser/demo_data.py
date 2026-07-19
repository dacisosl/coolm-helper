# -*- coding: utf-8 -*-
"""데모 모드용 가짜 쪽지 데이터.

쿨메신저가 설치되지 않은 PC에서도 전체 기능을 체험할 수 있게 한다.
모든 인물·연락처·일정은 허구이며, 날짜는 실행 시점 기준으로 생성되어
언제 실행해도 파싱 결과가 미래 일정으로 나온다.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from .db_reader import Message

# 데모용 가상 명단 (PII 빨간 표시 체험용)
DEMO_STUDENTS = {"김민준", "이서연", "박지호"}
DEMO_TEACHERS = {"최수정", "정하늘"}

_WD = "월화수목금토일"


def _fmt(dt: datetime) -> str:
    return f"{dt.month}월 {dt.day}일({_WD[dt.weekday()]})"


def demo_messages(now: datetime | None = None) -> list[Message]:
    now = now or datetime.now()

    def d(days: int) -> datetime:
        return now + timedelta(days=days)

    raw = [
        # (분 전, 발신자, 제목, 본문)
        (30, "교무부장(데모)",
         f"[{_fmt(d(1))} 교직원 회의 안내]",
         f"안녕하세요. 내일 오후 3시 30분 시청각실에서 교직원 회의가 있습니다.\n"
         f"안건: 2학기 학사일정 협의\n참석 부탁드립니다."),
        (95, "학생부(데모)",
         "[긴급] 학교폭력대책심의위원회 개최",
         f"3학년 김민준 학생 관련 학폭위 심의가 {_fmt(d(4))} 14:00 회의실에서 "
         f"열립니다.\n담당: 최수정 선생님(010-1234-5678)\n관련 서류는 회의 전까지 "
         f"학생부로 제출해 주세요."),
        (140, "연구부(데모)",
         "성적 입력 마감 안내",
         f"1학기 성적 입력을 {_fmt(d(2))}까지 제출 바랍니다.\n"
         f"기한 엄수 부탁드립니다. 문의: 정하늘 선생님"),
        (200, "3학년부(데모)",
         "수학여행 일정 확정",
         f"수학여행 일정이 확정되었습니다.\n기간: {_fmt(d(7))}~{_fmt(d(9))} (2박 3일)\n"
         f"장소: 제주도\n인솔: 정하늘 외 4명 (명단 추후 안내)"),
        (260, "상담실(데모)",
         "학부모 상담 일정",
         f"이서연 학생 학부모님 상담이 다음 주 화요일 10시 상담실에서 예정되어 "
         f"있습니다.\n담임 선생님께서는 참고 부탁드립니다."),
        (320, "교감(데모)",
         "개교기념일 휴업 안내",
         f"{_fmt(d(5))}은 개교기념일로 휴업합니다.\n착오 없으시기 바랍니다."),
        (380, "정보부(데모)",
         "정보화 연수 안내",
         f"{_fmt(d(3))} 오후 1시 30분 컴퓨터실에서 AI 활용 연수가 진행됩니다.\n"
         f"신청자: 박지호 학생 외 교직원 12명"),
        (440, "행정실(데모)",
         "감사 인사",
         "지난 행사 준비에 애써주신 모든 선생님께 감사드립니다.\n"
         "덕분에 잘 마무리되었습니다."),
    ]
    out = []
    for i, (mins_ago, sender, title, body) in enumerate(raw, 1):
        out.append(Message(
            key=-1000 - i, sender=sender,
            received=now - timedelta(minutes=mins_ago),
            title=title, body=body))
    return out


def demo_roster() -> set[str]:
    return set(DEMO_STUDENTS) | set(DEMO_TEACHERS)
