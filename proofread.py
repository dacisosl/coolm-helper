# -*- coding: utf-8 -*-
"""안내문구 보정 — 클라우드 AI 호출 (온라인 존, 공개용 글 전용).

⚠ 개인정보 경계:
- 이 모듈은 parser/ 를 import하지 않는다. 쪽지를 자동으로 불러올 수 없다.
- 전송되는 것은 사용자가 입력창에 직접 붙여넣은 텍스트뿐이다.
- API 키는 로컬 config.json에만 저장된다 (gitignore 대상).

공급자 교체(예: Groq)는 _PROVIDERS에 함수 하나 추가 + config의
proof_provider 변경으로 끝나도록 격리해 두었다.
"""
from __future__ import annotations

import json
import urllib.request

DEFAULT_MODEL = "gemini-2.0-flash"
TIMEOUT = 30

PROMPT = (
    "다음은 학교에서 학부모·학생에게 공개적으로 안내하는 글입니다. "
    "맞춤법과 띄어쓰기를 바로잡고, 문장을 정중하고 자연스럽게 다듬어 주세요. "
    "내용·날짜·숫자는 바꾸지 말고, 다듬어진 글만 출력하세요.\n\n"
    "--- 원문 ---\n{text}")


def _gemini(text: str, config: dict) -> str:
    key = (config.get("proof_api_key") or "").strip()
    if not key:
        raise RuntimeError("Gemini API 키가 설정되지 않았습니다. "
                           "설정 → 계정에서 입력해 주세요.")
    model = config.get("proof_model", DEFAULT_MODEL)
    url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
           f"{model}:generateContent")
    body = json.dumps({
        "contents": [{"parts": [{"text": PROMPT.format(text=text)}]}],
    }).encode("utf-8")
    req = urllib.request.Request(
        url, data=body, method="POST",
        headers={"Content-Type": "application/json", "x-goog-api-key": key})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            data = json.load(r)
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = json.load(e).get("error", {}).get("message", "")
        except Exception:
            pass
        if e.code in (401, 403):
            raise RuntimeError(f"API 키가 올바르지 않거나 권한이 없습니다. ({detail})")
        if e.code == 429:
            raise RuntimeError("요청이 너무 많습니다. 잠시 후 다시 시도해 주세요.")
        raise RuntimeError(f"Gemini 오류 {e.code}: {detail}")
    try:
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except (KeyError, IndexError):
        raise RuntimeError("응답을 해석하지 못했습니다. 잠시 후 다시 시도해 주세요.")


_PROVIDERS = {"gemini": _gemini}


def proofread(text: str, config: dict) -> str:
    """입력 텍스트를 다듬어 돌려준다. 실패 시 RuntimeError(사용자용 메시지)."""
    text = text.strip()
    if not text:
        raise RuntimeError("보정할 글을 입력해 주세요.")
    provider = config.get("proof_provider", "gemini")
    fn = _PROVIDERS.get(provider)
    if fn is None:
        raise RuntimeError(f"알 수 없는 공급자: {provider}")
    return fn(text, config)
