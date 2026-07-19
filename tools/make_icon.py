# -*- coding: utf-8 -*-
"""펭귄 SVG → assets/app.ico 생성 (빌드 도구, 배포물 아님).

사용: python tools/make_icon.py   (요구: pip install pillow)
assets/penguin.png이 있으면 그걸 원본으로 쓴다.
"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

from PyQt6.QtWidgets import QApplication

app = QApplication([])
from ui.penguin_icon import penguin_pixmap

assets = os.path.join(BASE, "assets")
os.makedirs(assets, exist_ok=True)

sizes = [16, 24, 32, 48, 64, 128, 256]
pngs = []
for s in sizes:
    pm = penguin_pixmap(BASE, s)
    path = os.path.join(assets, f"_icon_{s}.png")
    pm.save(path, "PNG")
    pngs.append(path)

from PIL import Image

images = [Image.open(p) for p in pngs]
ico_path = os.path.join(assets, "app.ico")
images[-1].save(ico_path, format="ICO",
                sizes=[(s, s) for s in sizes],
                append_images=images[:-1])
for p in pngs:
    os.remove(p)
print(f"생성 완료: {ico_path}")
