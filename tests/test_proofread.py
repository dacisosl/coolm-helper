# -*- coding: utf-8 -*-
"""proofread.py — 내장 키/본인 키 우선, 모델 폴백, 오류 처리 (실제 호출 없음)."""
import base64
import io
import json
import os
import sys
import tempfile
import unittest
import urllib.error
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import proofread

OK = {"choices": [{"message": {"content": " 다듬은 글 "}}]}


def _resp(obj):
    return io.BytesIO(json.dumps(obj).encode("utf-8"))


def _http_error(code, msg="err"):
    fp = io.BytesIO(json.dumps({"error": {"message": msg}}).encode("utf-8"))
    return urllib.error.HTTPError("http://x", code, "e", {}, fp)


class TestProofread(unittest.TestCase):
    def test_user_key_beats_embedded(self):
        seen = {}

        def fake(req, timeout=None):
            seen["auth"] = req.get_header("Authorization")
            seen["model"] = json.loads(req.data)["model"]
            return _resp(OK)

        with mock.patch.object(proofread, "embedded_openrouter_key",
                               return_value="EMB"), \
                mock.patch("urllib.request.urlopen", fake):
            out = proofread.proofread(
                "안녕", {"proof_api_key": "USERKEY",
                        "proof_provider": "openrouter"})
        self.assertEqual(out, "다듬은 글")
        self.assertEqual(seen["auth"], "Bearer USERKEY")

    def test_embedded_key_when_no_user_key(self):
        seen = {}

        def fake(req, timeout=None):
            seen["auth"] = req.get_header("Authorization")
            seen["model"] = json.loads(req.data)["model"]
            return _resp(OK)

        with mock.patch.object(proofread, "embedded_openrouter_key",
                               return_value="EMB"), \
                mock.patch("urllib.request.urlopen", fake):
            out = proofread.proofread("안녕", {})
        self.assertEqual(out, "다듬은 글")
        self.assertEqual(seen["auth"], "Bearer EMB")
        self.assertEqual(seen["model"], proofread.OPENROUTER_MODEL)

    def test_fallback_on_model_400(self):
        calls = []

        def fake(req, timeout=None):
            m = json.loads(req.data)["model"]
            calls.append(m)
            if m == proofread.OPENROUTER_MODEL:
                raise _http_error(400, "no such model")
            return _resp(OK)

        with mock.patch.object(proofread, "embedded_openrouter_key",
                               return_value="EMB"), \
                mock.patch("urllib.request.urlopen", fake):
            out = proofread.proofread("안녕", {})
        self.assertEqual(out, "다듬은 글")
        self.assertEqual(calls[0], proofread.OPENROUTER_MODEL)
        self.assertEqual(calls[1], proofread.OPENROUTER_FALLBACKS[0])

    def test_402_credit_message_no_fallback(self):
        calls = []

        def fake(req, timeout=None):
            calls.append(json.loads(req.data)["model"])
            raise _http_error(402, "insufficient credits")

        with mock.patch.object(proofread, "embedded_openrouter_key",
                               return_value="EMB"), \
                mock.patch("urllib.request.urlopen", fake):
            with self.assertRaises(RuntimeError) as cm:
                proofread.proofread("안녕", {})
        self.assertIn("크레딧", str(cm.exception))
        self.assertEqual(len(calls), 1)     # 402는 폴백 안 함

    def test_user_openrouter_model_used_as_is(self):
        seen = {}

        def fake(req, timeout=None):
            seen["model"] = json.loads(req.data)["model"]
            return _resp(OK)

        with mock.patch("urllib.request.urlopen", fake):
            proofread.proofread("안녕", {
                "proof_api_key": "K", "proof_provider": "openrouter",
                "proof_model_openrouter": "openai/gpt-4o-mini"})
        self.assertEqual(seen["model"], "openai/gpt-4o-mini")

    def test_embedded_key_decode_and_absent(self):
        d = tempfile.mkdtemp()
        os.makedirs(os.path.join(d, "assets"))
        with open(os.path.join(d, "assets", "proof.key"), "wb") as f:
            f.write(base64.b64encode("SECRET-키".encode("utf-8")))
        with mock.patch.object(proofread, "_app_root", return_value=d):
            self.assertEqual(proofread.embedded_openrouter_key(), "SECRET-키")
        with mock.patch.object(proofread, "_app_root",
                               return_value=tempfile.mkdtemp()):
            self.assertEqual(proofread.embedded_openrouter_key(), "")

    def test_empty_text_rejected(self):
        with self.assertRaises(RuntimeError):
            proofread.proofread("   ", {"proof_api_key": "K"})

    def test_headers_are_latin1_safe(self):
        # HTTP 헤더 값은 latin-1만 허용 — 한글 등이 들어가면 요청이 깨진다.
        for k, v in proofread.OPENROUTER_HEADERS.items():
            v.encode("latin-1")   # 실패하면 UnicodeEncodeError로 테스트 실패

    def test_korean_body_ok_with_headers(self):
        seen = {}

        def fake(req, timeout=None):
            # 실제 urllib처럼 헤더가 latin-1로 인코딩 가능한지 확인
            for k, v in req.header_items():
                v.encode("latin-1")
            seen["ok"] = True
            return _resp(OK)

        with mock.patch("urllib.request.urlopen", fake):
            out = proofread.proofread(
                "내일 학부모 상담 있어요", {"proof_api_key": "K",
                                        "proof_provider": "openrouter"})
        self.assertEqual(out, "다듬은 글")
        self.assertTrue(seen.get("ok"))


if __name__ == "__main__":
    unittest.main()
