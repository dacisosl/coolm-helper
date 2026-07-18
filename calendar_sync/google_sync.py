# -*- coding: utf-8 -*-
"""구글 캘린더 연동 (온라인 존 — 옵트인 선택 기능).

⚠ 개인정보 경계: 이 모듈의 공개 함수는 제목(title)·시작(start)·종료(end)만
받는다. Message/Candidate 객체 자체를 받는 함수는 의도적으로 만들지 않는다 —
원문·발신자·본문이 이 모듈로 흘러들어올 통로를 구조적으로 차단하기 위해서다.

사용 조건 (SETUP.md 참고):
1. config.json 에서 "google_sync_enabled": true
2. calendar_sync/credentials.json (구글 OAuth 클라이언트 파일) 존재
3. pip install google-api-python-client google-auth-oauthlib
첫 등록 시 브라우저가 열려 구글 로그인 → 토큰은 로컬(token.json)에만 저장.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta

SCOPES = ["https://www.googleapis.com/auth/calendar.events"]
_DIR = os.path.dirname(os.path.abspath(__file__))
CREDENTIALS_PATH = os.path.join(_DIR, "credentials.json")
TOKEN_PATH = os.path.join(_DIR, "token.json")


def is_available(base_dir: str | None = None) -> bool:
    """구글 연동을 켤 수 있는 상태인가 (라이브러리 + 클라이언트 파일)."""
    if not os.path.exists(CREDENTIALS_PATH):
        return False
    try:
        import googleapiclient  # noqa: F401
        import google_auth_oauthlib  # noqa: F401
        return True
    except ImportError:
        return False


def _service():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    creds = None
    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                CREDENTIALS_PATH, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_PATH, "w", encoding="utf-8") as f:
            f.write(creds.to_json())
    return build("calendar", "v3", credentials=creds)


def register_event(title: str, start: datetime, end: datetime | None,
                   all_day: bool) -> str:
    """마스킹·확인된 제목과 일시만으로 구글 캘린더 이벤트를 만든다.

    반환: 구글 이벤트 ID. 실패 시 예외 (호출부에서 로컬 저장은 계속된다).
    """
    if all_day:
        end_date = (end or start).date() + timedelta(days=1)  # 구글 종일은 배타적 종료
        body = {
            "summary": title,
            "start": {"date": start.date().isoformat()},
            "end": {"date": end_date.isoformat()},
        }
    else:
        tz = "Asia/Seoul"
        body = {
            "summary": title,
            "start": {"dateTime": start.isoformat(), "timeZone": tz},
            "end": {"dateTime": (end or start + timedelta(hours=1)).isoformat(),
                    "timeZone": tz},
        }
    created = _service().events().insert(calendarId="primary", body=body).execute()
    return created["id"]
