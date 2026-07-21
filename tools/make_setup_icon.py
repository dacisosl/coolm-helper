# -*- coding: utf-8 -*-
"""assets/app.ico → assets/setup.ico 생성 (빌드 도구, 배포물 아님).

설치파일(CoolmHelper-Setup.exe)과 실행파일 아이콘이 똑같아 헷갈린다는
피드백(2026-07-21) — 펭귄 오른쪽 아래에 초록 원 + 흰 ↓ 화살표 배지를
얹어 '내려받아 설치하는 파일'임을 한눈에 구분되게 한다.

사용법: pip install Pillow 후  python tools/make_setup_icon.py
"""
import os

from PIL import Image, ImageDraw

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(BASE, "assets", "app.ico")
DST = os.path.join(BASE, "assets", "setup.ico")

BADGE = (46, 160, 67)        # 초록 (설치·다운로드 관례색)
BADGE_RING = (255, 255, 255)


def _badged(size: int) -> Image.Image:
    src = Image.open(SRC)
    # ico 안에서 요청 크기와 같은 프레임을 고른다 (없으면 256에서 축소)
    try:
        src.size = (size, size)
        base = src.convert("RGBA")
    except Exception:
        base = Image.open(SRC).convert("RGBA").resize((size, size),
                                                      Image.LANCZOS)
    if base.size != (size, size):
        base = base.resize((size, size), Image.LANCZOS)

    # 작은 크기일수록 배지를 크게 (16px에서도 보이도록)
    frac = 0.62 if size <= 24 else 0.52 if size <= 48 else 0.44
    d = int(size * frac)
    x0, y0 = size - d, size - d
    ring = max(1, d // 12)

    over = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    dr = ImageDraw.Draw(over)
    dr.ellipse([x0 - ring, y0 - ring, size - 1, size - 1], fill=BADGE_RING)
    dr.ellipse([x0, y0, size - 1 - ring, size - 1 - ring], fill=BADGE)

    # 흰 ↓ 화살표 (막대 + 삼각형)
    cx = (x0 + size - 1 - ring) / 2
    cy = (y0 + size - 1 - ring) / 2
    r = d / 2 - ring
    bar_w = max(1, int(r * 0.36))
    top = cy - r * 0.55
    mid = cy + r * 0.05
    bot = cy + r * 0.62
    dr.rectangle([cx - bar_w / 2, top, cx + bar_w / 2, mid], fill="white")
    dr.polygon([(cx - r * 0.5, mid), (cx + r * 0.5, mid), (cx, bot)],
               fill="white")
    return Image.alpha_composite(base, over)


def main() -> None:
    sizes = [256, 128, 64, 48, 32, 24, 16]
    imgs = {s: _badged(s) for s in sizes}
    imgs[256].save(DST, format="ICO",
                   sizes=[(s, s) for s in sizes],
                   append_images=[imgs[s] for s in sizes[1:]])
    print("생성:", DST, os.path.getsize(DST), "bytes")


if __name__ == "__main__":
    main()
