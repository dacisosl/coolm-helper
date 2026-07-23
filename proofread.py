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

import base64
import json
import os
import sys
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


# 값싼 Flash 기본 모델 — 막히면(없어짐 등) 아래 후보로 폴백.
OPENROUTER_MODEL = "google/gemini-2.0-flash-001"
OPENROUTER_FALLBACKS = ["google/gemini-flash-1.5", "openai/gpt-4o-mini"]
OPENROUTER_HEADERS = {
    "Content-Type": "application/json",
    # OpenRouter 권장 헤더 (일부 모델은 없으면 거부하기도 함)
    "HTTP-Referer": "https://github.com/dacisosl/coolm-helper",
    "X-Title": "COOL-비서",
}


def _app_root() -> str:
    """assets/가 놓이는 앱 루트 (main.py의 BASE_DIR과 동일 규칙)."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def embedded_openrouter_key() -> str:
    """빌드 때 심어둔 공용 OpenRouter 키 (assets/proof.key, base64).

    소스/깃에는 없고 릴리스 빌드에서만 주입된다. 없으면 빈 문자열.
    """
    path = os.path.join(_app_root(), "assets", "proof.key")
    try:
        with open(path, "rb") as f:
            return base64.b64decode(f.read().strip()).decode("utf-8").strip()
    except Exception:
        return ""


class _ModelUnavailable(Exception):
    """모델을 못 찾음(400/404) — 다음 후보로 넘어가도 되는 오류."""


def _openrouter_call(prompt: str, key: str, model: str) -> str:
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
    }).encode("utf-8")
    headers = dict(OPENROUTER_HEADERS, Authorization=f"Bearer {key}")
    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=body, method="POST", headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            data = json.load(r)
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = json.load(e).get("error", {}).get("message", "")
        except Exception:
            pass
        if e.code in (400, 404):                 # 모델 문제 → 폴백 가능
            raise _ModelUnavailable(detail or model)
        if e.code in (401, 403):
            raise RuntimeError(f"API 키가 올바르지 않거나 권한이 없습니다. ({detail})")
        if e.code == 402:
            raise RuntimeError(
                "AI 사용 크레딧이 부족합니다. 잠시 후 다시 시도하거나, "
                "설정에서 직접 발급한 키를 넣어 주세요.")
        if e.code == 429:
            raise RuntimeError("요청이 너무 많습니다. 잠시 후 다시 시도해 주세요.")
        raise RuntimeError(f"OpenRouter 오류 {e.code}: {detail}")
    try:
        return data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError):
        emsg = ""
        try:
            emsg = (data.get("error") or {}).get("message", "")
        except Exception:
            pass
        if emsg:
            raise RuntimeError(f"OpenRouter: {emsg}")
        raise RuntimeError("응답을 해석하지 못했습니다. 잠시 후 다시 시도해 주세요.")


def _openrouter(text: str, config: dict, key: str | None = None) -> str:
    """OpenRouter — 여러 AI를 한 키로 쓰는 중계(OpenAI 호환). 모델 폴백 지원.

    key: 명시하면 그 키를 사용(내장 공용 키 경로). 없으면 config의 사용자 키.
    """
    if key is None:
        key = (config.get("proof_api_key") or "").strip()
    if not key:
        raise RuntimeError("OpenRouter API 키가 설정되지 않았습니다. "
                           "설정 → 일반에서 입력해 주세요.")
    model = (config.get("proof_model_openrouter") or "").strip() or OPENROUTER_MODEL
    # 사용자가 모델을 직접 지정하면 그것만, 기본값이면 후보들을 차례로 시도.
    candidates = [model]
    if model == OPENROUTER_MODEL:
        candidates += [m for m in OPENROUTER_FALLBACKS if m != model]
    last = None
    for m in candidates:
        try:
            return _openrouter_call(text, key, m)
        except _ModelUnavailable as e:
            last = str(e)
            continue
    raise RuntimeError(
        f"모델을 찾지 못했어요 ({last or model}). 설정 → 일반에서 'AI 모델' 이름을 "
        "바꿔보세요 (예: google/gemini-2.0-flash-001).")


_PROVIDERS = {"gemini": _gemini, "openrouter": _openrouter}


def proofread(text: str, config: dict, tone: str = "formal") -> str:
    """입력 텍스트를 다듬어 돌려준다. 실패 시 RuntimeError(사용자용 메시지).

    tone: TONES의 키 — 다듬는 말투(정중/친근/격식/간결).
    """
    text = text.strip()
    if not text:
        raise RuntimeError("보정할 글을 입력해 주세요.")
    prompt = PROMPT.format(style=TONES.get(tone, TONES["formal"]), text=text)
    # ① 사용자가 직접 넣은 키가 있으면 그 공급자로 (본인 키 우선)
    user_key = (config.get("proof_api_key") or "").strip()
    if user_key:
        provider = config.get("proof_provider", "gemini")
        fn = _PROVIDERS.get(provider)
        if fn is None:
            raise RuntimeError(f"알 수 없는 공급자: {provider}")
        return fn(prompt, config)
    # ② 없으면 앱에 내장된 공용 OpenRouter 키로 바로 동작
    ekey = embedded_openrouter_key()
    if ekey:
        return _openrouter(prompt, config, key=ekey)
    # ③ 아무 키도 없음 → 기존 공급자 함수가 "키 없음"을 안내
    fn = _PROVIDERS.get(config.get("proof_provider", "gemini"), _gemini)
    return fn(prompt, config)
