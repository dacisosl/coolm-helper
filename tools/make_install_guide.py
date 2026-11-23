# -*- coding: utf-8 -*-
"""설치 안내 페이지 생성기 — docs/설치안내.template.html → docs/설치안내.html.

버전과 펭귄 그림(assets/penguin.png)을 채워 이미지가 들어 있는 파일 하나로 만든다.
경고창·설치 마법사는 캡처할 수 없어 템플릿 안에 HTML로 그린 '예시 화면'이다.

사용:
    python tools/make_install_guide.py                  # docs/설치안내.html
    python tools/make_install_guide.py --body 파일.html  # <html> 틀 없는 본문판(웹 게시용)
"""
import argparse
import base64
import os
import re
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
from version import APP_VERSION  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--body", help="<html> 틀 없이 본문만 담은 파일도 쓴다")
args = ap.parse_args()

with open(os.path.join(BASE, "assets", "penguin.png"), "rb") as f:
    b64 = base64.b64encode(f.read()).decode()
src = f"data:image/png;base64,{b64}"

body = open(os.path.join(BASE, "docs", "설치안내.template.html"), encoding="utf-8").read()
for k, v in {
    "VERSION": APP_VERSION,
    "PENGUIN": f'<img src="{src}" alt="COOL-비서 펭귄 쿨쿠리" width="96" height="96">',
    "PENGUIN_DESK": f'<img src="{src}" alt="">',
}.items():
    body = body.replace("{{" + k + "}}", v)
left = sorted(set(re.findall(r"\{\{([A-Z_]+)\}\}", body)))
if left:
    sys.exit("안 채운 자리: " + ", ".join(left))

out = os.path.join(BASE, "docs", "설치안내.html")
with open(out, "w", encoding="utf-8") as f:
    f.write('<!doctype html>\n<html lang="ko">\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
            + body + "\n</html>\n")
print(f"생성 완료: {out} ({os.path.getsize(out) // 1024}KB)")
if args.body:
    with open(args.body, "w", encoding="utf-8") as f:
        f.write(body)
    print(f"본문판: {args.body}")
