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


def _data_dir() -> str:
    """열쇠·토큰을 두는 폴더 — exe(또는 프로젝트) 옆 calendar_sync.

    frozen exe에서는 __file__이 _internal 안을 가리켜 업데이트 때 지워진다.
    exe 옆 폴더는 [InstallDelete] 대상이 아니라 로그인이 유지된다.
    """
    import sys
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(_DIR)
    d = os.path.join(base, "calendar_sync")
    os.makedirs(d, exist_ok=True)
    return d


def credentials_path() -> str | None:
    """열쇠 파일을 여러 위치에서 찾는다 — 데이터 폴더 → 소스 폴더."""
    for p in (os.path.join(_data_dir(), "credentials.json"),
              os.path.join(_DIR, "credentials.json")):
        if os.path.exists(p):
            return p
    return None


def token_path() -> str:
    return os.path.join(_data_dir(), "token.json")


# 이전 버전 호환용 별칭 (settings 등에서 TOKEN_PATH를 직접 참조)
TOKEN_PATH = token_path()
CREDENTIALS_PATH = os.path.join(_data_dir(), "credentials.json")


def libs_available() -> bool:
    """구글 라이브러리가 이 빌드에 들어 있는가."""
    try:
        import googleapiclient  # noqa: F401
        import google_auth_oauthlib  # noqa: F401
        return True
    except ImportError:
        return False


def is_available(base_dir: str | None = None) -> bool:
    """구글 연동을 켤 수 있는 상태인가 (라이브러리 + 열쇠 파일)."""
    return credentials_path() is not None and libs_available()


def install_credentials(src_path: str) -> None:
    """사용자가 고른 열쇠 파일(JSON)을 검사해 제자리에 복사한다.

    잘못된 파일이면 ValueError — 설정 창이 쉬운 말로 안내한다.
    """
    import json
    import shutil
    try:
        with open(src_path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        raise ValueError("JSON 파일이 아니거나 열 수 없습니다.")
    if "installed" not in data and "web" not in data:
        raise ValueError("구글 OAuth 클라이언트 파일이 아닙니다.\n"
                         "(구글 클라우드에서 받은 client_secret JSON을 골라주세요)")
    dst = os.path.join(_data_dir(), "credentials.json")
    shutil.copyfile(src_path, dst)


def _service():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    creds = None
    tok = token_path()
    if os.path.exists(tok):
        creds = Credentials.from_authorized_user_file(tok, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            cred = credentials_path()
            if not cred:
                raise RuntimeError("구글 열쇠 파일(credentials.json)이 없습니다.")
            flow = InstalledAppFlow.from_client_secrets_file(cred, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(tok, "w", encoding="utf-8") as f:
            f.write(creds.to_json())
    # static_discovery=False: 무거운 API 문서 뭉치를 동봉하지 않고
    # 접속할 때 받아온다 (로그인 자체가 온라인이라 추가 제약 없음)
    return build("calendar", "v3", credentials=creds,
                 static_discovery=False)


def ensure_login() -> None:
    """OAuth 로그인만 미리 수행해 토큰을 만든다 (설정 창 연동 칩용).

    이벤트는 만들지 않는다 — 로그인 성공 여부만 확인.
    """
    _service()


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


def delete_event(event_id: str) -> None:
    """등록 취소·삭제 시 구글 캘린더의 사본도 삭제한다 (이벤트 ID만 사용)."""
    _service().events().delete(calendarId="primary", eventId=event_id).execute()


def update_event(event_id: str, title: str, start: datetime,
                 end: datetime | None, all_day: bool) -> None:
    """일정 수정 시 구글 사본도 갱신한다 — 제목·시작·종료만."""
    if all_day:
        end_date = (end or start).date() + timedelta(days=1)
        body = {"summary": title,
                "start": {"date": start.date().isoformat()},
                "end": {"date": end_date.isoformat()}}
    else:
        tz = "Asia/Seoul"
        body = {"summary": title,
                "start": {"dateTime": start.isoformat(), "timeZone": tz},
                "end": {"dateTime": (end or start + timedelta(hours=1)).isoformat(),
                        "timeZone": tz}}
    _service().events().patch(calendarId="primary", eventId=event_id,
                              body=body).execute()
