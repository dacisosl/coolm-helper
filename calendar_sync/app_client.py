# -*- coding: utf-8 -*-
"""COOL-비서 공용 OAuth 클라이언트 (2026-07-22, 제작자 발급).

이 '앱 명함' 덕분에 사용자는 열쇠 파일을 만들 필요 없이
[연동하기] → 자기 구글 계정으로 로그인 → 바로 연동된다.

- 여기 담긴 값은 '앱'의 신분증이지 누군가의 계정 비밀번호가 아니다.
  로그인은 각자 자기 구글 계정으로 하며, 토큰은 각자 PC에만 저장된다.
- 데스크톱 앱의 client_secret은 구글 정책상 기밀로 취급되지 않는다
  (배포되는 모든 데스크톱 앱에 포함됨 — gcloud CLI 등과 같은 방식).
- 자기만의 클라이언트를 쓰고 싶으면 calendar_sync/credentials.json을
  두면 그쪽이 우선한다 (google_sync.credentials_path 참고).
"""

CLIENT_CONFIG = {
    "installed": {
        "client_id": ("616804457354-2b64l1fs3mp0osv7qe150u5rrm2im4rv"
                      ".apps.googleusercontent.com"),
        "project_id": "cool-503203",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "auth_provider_x509_cert_url":
            "https://www.googleapis.com/oauth2/v1/certs",
        "client_secret": "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",
        "redirect_uris": ["http://localhost"],
    }
}
