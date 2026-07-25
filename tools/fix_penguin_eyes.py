# -*- coding: utf-8 -*-
"""펭귄 이미지의 '안경 렌즈 구멍' 메우기 (빌드 도구, 배포물 아님).

3D 렌더 원본은 안경 렌즈 안쪽이 투명(alpha=0)이라, 바탕화면 위에 올리면
눈 위쪽으로 배경이 비쳐 보였다(2026-07-25 사용자 제보). 바깥 배경과 이어지지
않은 '갇힌 투명 영역'만 찾아 머리색으로 메우고 불투명하게 만든다.
안경테처럼 반투명(alpha 128~249)인 픽셀은 색을 살린 채 불투명화만 한다.

사용: pip install pillow numpy scipy 후  python tools/fix_penguin_eyes.py
"""
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from scipy import ndimage

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGETS = ("penguin.png", "penguin_sleep.png",
           "penguin_work.png", "penguin_surprise.png")


def fix_image(path: str) -> int:
    """구멍을 메운다. 채운 픽셀 수를 돌려준다(0이면 손댈 것 없음)."""
    im = Image.open(path).convert("RGBA")
    arr = np.array(im)
    alpha = arr[:, :, 3]

    # 바깥(0,0)에서 이어지지 않는 투명 영역 = 렌즈 안쪽 구멍
    mask = Image.fromarray((alpha < 250).astype(np.uint8) * 255, "L").copy()
    ImageDraw.floodfill(mask, (0, 0), 128)      # copy() 필수 — 배열 기반은 실패
    region = np.array(mask) == 255
    if not region.any():
        return 0

    hole = region & (alpha < 128)               # 완전히 빈 곳 → 새로 칠한다
    lum = arr[:, :, :3].astype(np.float32) @ np.array([0.299, 0.587, 0.114])
    src = (alpha >= 250) & (lum < 110)          # 머리(어두운) 픽셀에서 색을 가져옴
    idx = ndimage.distance_transform_edt(
        ~src, return_distances=False, return_indices=True)

    out = arr.copy()
    for c in range(3):
        out[:, :, c][hole] = arr[:, :, c][idx[0][hole], idx[1][hole]]
    out[:, :, 3][region] = 255                  # 안경테 포함 전부 불투명하게

    # 거리 변환 특유의 방사형 줄무늬를 채운 안쪽에서만 부드럽게
    soft = np.array(Image.fromarray(out).filter(ImageFilter.GaussianBlur(2.5)))
    inner = ndimage.binary_erosion(hole, iterations=2)
    for c in range(3):
        out[:, :, c][inner] = soft[:, :, c][inner]

    Image.fromarray(out).save(path)
    return int(hole.sum())


def main() -> int:
    for name in TARGETS:
        path = os.path.join(BASE, "assets", name)
        if not os.path.exists(path):
            print(f"건너뜀(없음): {name}")
            continue
        print(f"{name}: {fix_image(path)}px 메움")
    print("완료 — tools/make_icon.py, make_setup_icon.py도 다시 실행하세요.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
