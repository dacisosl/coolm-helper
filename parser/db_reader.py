# -*- coding: utf-8 -*-
"""쿨메신저 .udb 리더.

접근 규칙(고정): 원본은 절대 쓰기 모드로 열지 않는다.
udb + -wal + -shm 세 파일을 임시 폴더에 복사한 뒤 복사본을 읽기 전용으로 연다.
"""
from __future__ import annotations

import glob
import os
import shutil
import sqlite3
import tempfile
from dataclasses import dataclass
from datetime import datetime

REQUIRED_RECV_COLS = {"MessageKey", "Sender", "ReceiveDate", "Title", "MessageText"}


class SchemaMismatch(Exception):
    """쿨메신저 DB 구조가 예상과 다를 때 (업데이트로 스키마 변경 등) → Plan B 폴백."""


@dataclass
class Message:
    key: int
    sender: str
    received: datetime
    title: str
    body: str
    is_unread: bool = False   # 쿨메신저의 안읽음 상태 (읽기만 하고 바꾸지 않는다)


def parse_receive_date(s: str) -> datetime:
    """'2026/07/16 17:04:52 (목)' 형식의 문자열 날짜를 파싱한다."""
    return datetime.strptime(str(s)[:19], "%Y/%m/%d %H:%M:%S")


def find_active_udb(memo_dir: str) -> str:
    """폴더 내 가장 최근 수정된 .udb를 고른다 (구버전 파일 공존 대비)."""
    candidates = glob.glob(os.path.join(memo_dir, "*.udb"))
    if not candidates:
        raise FileNotFoundError(f"메시지 DB(.udb)를 찾을 수 없습니다: {memo_dir}")
    return max(candidates, key=os.path.getmtime)


def _copy_shared(src: str, dst: str) -> None:
    """쿨메신저가 잠근 파일도 공유 읽기로 복사한다."""
    with open(src, "rb") as fin, open(dst, "wb") as fout:
        shutil.copyfileobj(fin, fout, 1024 * 1024)


class DbReader:
    """복사본 기반 읽기 전용 리더. with 문으로 사용하면 복사본이 자동 삭제된다."""

    def __init__(self, memo_dir: str):
        self.memo_dir = memo_dir
        self._tmp: str | None = None
        self._con: sqlite3.Connection | None = None

    def __enter__(self) -> "DbReader":
        src = find_active_udb(self.memo_dir)
        self._tmp = tempfile.mkdtemp(prefix="coolm_ro_")
        dst = os.path.join(self._tmp, "copy.udb")
        for ext in ("", "-wal", "-shm"):
            if os.path.exists(src + ext):
                _copy_shared(src + ext, dst + ext)
        self._con = sqlite3.connect(f"file:{dst}?mode=ro", uri=True)
        self._validate()
        return self

    def __exit__(self, *exc) -> None:
        if self._con:
            self._con.close()
        if self._tmp:
            shutil.rmtree(self._tmp, ignore_errors=True)

    def _validate(self) -> None:
        cur = self._con.cursor()
        tables = {r[0] for r in cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        if "tbl_recv" not in tables:
            raise SchemaMismatch("tbl_recv 테이블이 없습니다")
        cols = {r[1] for r in cur.execute("PRAGMA table_info(tbl_recv)")}
        missing = REQUIRED_RECV_COLS - cols
        if missing:
            raise SchemaMismatch(f"tbl_recv에 필수 컬럼이 없습니다: {missing}")

    UNREAD_CAP = 200   # 안읽은 쪽지 안전 상한 (사실상 무제한)

    def latest_messages(self, limit: int = 10) -> list[Message]:
        """안읽은 쪽지는 전부 + 읽은 쪽지 최근 N개 (삭제 제외, 최신순).

        안읽은 쪽지가 15개, 30개 쌓인 날에도 확인 중인 쪽지가 항상 목록에
        있도록, 안읽음은 개수 제한 없이 포함한다. 평소(안읽음 0~2개)에는
        기존의 '최근 N개'와 사실상 동일하게 동작한다.
        """
        cur = self._con.cursor()
        cols = "MessageKey, Sender, ReceiveDate, Title, MessageText, IsUnRead"
        rows = cur.execute(
            f"SELECT {cols} FROM tbl_recv "
            "WHERE DeletedDate IS NULL AND IsUnRead = 1 "
            "ORDER BY ReceiveDate DESC LIMIT ?",
            (self.UNREAD_CAP,),
        ).fetchall()
        rows += cur.execute(
            f"SELECT {cols} FROM tbl_recv "
            "WHERE DeletedDate IS NULL AND (IsUnRead IS NULL OR IsUnRead != 1) "
            "ORDER BY ReceiveDate DESC LIMIT ?",
            (int(limit),),
        ).fetchall()
        out = []
        for key, sender, rdate, title, body, unread in rows:
            try:
                received = parse_receive_date(rdate)
            except (ValueError, TypeError):
                continue
            out.append(Message(key=key, sender=sender or "", received=received,
                               title=title or "", body=body or "",
                               is_unread=bool(unread)))
        out.sort(key=lambda m: m.received, reverse=True)
        return out

    def member_names(self) -> set[str]:
        """교직원 명단(tbl_member) — PII 탐지 사전으로 재활용."""
        cur = self._con.cursor()
        try:
            return {r[0].strip() for r in cur.execute(
                "SELECT MemberName FROM tbl_member") if r[0] and r[0].strip()}
        except sqlite3.OperationalError:
            return set()
