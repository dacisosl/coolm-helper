# -*- coding: utf-8 -*-
"""Plan B 폴백: 쿨메신저 엑셀 내보내기(coolmsg_*.xls) 파서.

DB 스키마가 바뀌어 Plan A가 실패할 때만 사용한다.
시트 [받은메시지], 열 [보낸사람 | 제목 | 날짜/시간 | 내용 | 첨부파일].
xlrd 필요 (requirements.txt 참고).
"""
from __future__ import annotations

import glob
import os
from datetime import datetime

from .db_reader import Message

EXPORT_GUIDE = (
    "쿨메신저 메시지 관리함 → 우측 상단 다운로드 아이콘 → "
    "기간 지정 → 다운로드로 coolmsg_*.xls 파일을 먼저 만들어 주세요."
)


def find_latest_export(export_dir: str, pattern: str = "coolmsg_*.xls*") -> str | None:
    files = glob.glob(os.path.join(export_dir, pattern))
    return max(files, key=os.path.getmtime) if files else None


def read_messages(xls_path: str) -> list[Message]:
    import xlrd  # 지연 임포트 — Plan A만 쓸 때는 불필요

    wb = xlrd.open_workbook(xls_path)
    try:
        sheet = wb.sheet_by_name("받은메시지")
    except xlrd.XLRDError:
        sheet = wb.sheet_by_index(0)

    out: list[Message] = []
    for i in range(1, sheet.nrows):  # 0행은 헤더
        sender, title, dt_str, body = (str(sheet.cell_value(i, c)) for c in range(4))
        try:
            received = datetime.strptime(dt_str.strip()[:19], "%Y/%m/%d %H:%M:%S")
        except ValueError:
            continue
        out.append(Message(key=-i, sender=sender, received=received,
                           title=title, body=body))
    out.sort(key=lambda m: m.received, reverse=True)
    return out
