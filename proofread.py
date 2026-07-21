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

DEFAULT_MODEL = "gemini-3.5-flash"
# 구글이 내려버린 옛 모델들 — config에 남아 있으면 기본 모델로 대체
_RETIRED_MODELS = {"gemini-1.5-flash", "gemini-2.0-flash", "gemini-2.5-flash"}
TIMEOUT = 30

# 톤(분위기) 선택지 — UI 칩과 1:1 대응
TONES = {
    "polite":   "정중하고 세련된 문장으로",
    "friendly": "부드럽고 친근한 말투로",
    "formal":   "격식 있고 명확한 문장으로",
    "short":    "핵심만 남겨 짧고 간결하게",
}

PROMPT = (
    "다음은 학교에서 학부모·학생에게 공개적으로 안내하는 글입니다. "
    "맞춤법과 띄어쓰기를 바로잡고, {style} 다듬어 주세요. "
    "내용·날짜·숫자는 바꾸지 말고, 다듬어진 글만 출력하세요.\n\n"
    "--- 원문 ---\n{text}")


def _gemini(text: str, config: dict) -> str:
    key = (config.get("proof_api_key") or "").strip()
    if not key:
        raise RuntimeError("Gemini API 키가 설정되지 않았습니다. "
                           "설정 → 일반에서 입력해 주세요.")
    model = config.get("proof_model", DEFAULT_MODEL)
    if model in _RETIRED_MODELS:          # 옛 설정 파일 호환 (404 방지)
        model = DEFAULT_MODEL
    url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
           f"{model}:generateContent")
    body = json.dumps({
        "contents": [{"parts": [{"text": text}]}],   # text = 완성된 프롬프트
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


OPENROUTER_MODEL = "google/gemini-3.5-flash"


def _openrouter(text: str, config: dict) -> str:
    """OpenRouter — 여러 AI를 한 키로 쓰는 중계 서비스 (OpenAI 호환 API)."""
    key = (config.get("proof_api_key") or "").strip()
    if not key:
        raise RuntimeError("OpenRouter API 키가 설정되지 않았습니다. "
                           "설정 → 일반에서 입력해 주세요.")
    model = config.get("proof_model_openrouter", OPENROUTER_MODEL)
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": text}],   # text = 완성된 프롬프트
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions", data=body,
        method="POST",
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {key}"})
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
        raise RuntimeError(f"OpenRouter 오류 {e.code}: {detail}")
    try:
        return data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError):
        raise RuntimeError("응답을 해석하지 못했습니다. 잠시 후 다시 시도해 주세요.")


_PROVIDERS = {"gemini": _gemini, "openrouter": _openrouter}


def proofread(text: str, config: dict, tone: str = "formal") -> str:
    """입력 텍스트를 다듬어 돌려준다. 실패 시 RuntimeError(사용자용 메시지).

    tone: TONES의 키 — 다듬는 말투(정중/친근/격식/간결).
    """
    text = text.strip()
    if not text:
        raise RuntimeError("보정할 글을 입력해 주세요.")
    provider = config.get("proof_provider", "gemini")
    fn = _PROVIDERS.get(provider)
    if fn is None:
        raise RuntimeError(f"알 수 없는 공급자: {provider}")
    style = TONES.get(tone, TONES["formal"])
    return fn(PROMPT.format(style=style, text=text), config)
