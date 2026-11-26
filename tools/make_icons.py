"""assets/icon.png (1024x1024 투명 PNG 권장) → assets/icon.ico (윈도우) + assets/icon.icns (맥) 생성.
사용: pip install pillow  →  python tools/make_icons.py"""
import os
from PIL import Image
a = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")
img = Image.open(os.path.join(a, "icon.png")).convert("RGBA")
side = max(img.size); sq = Image.new("RGBA", (side, side), (0, 0, 0, 0)); sq.paste(img, ((side - img.width) // 2, (side - img.height) // 2))
sq.save(os.path.join(a, "icon.ico"), sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
sq.resize((1024, 1024)).save(os.path.join(a, "icon.icns"))
print("assets/icon.ico, assets/icon.icns 생성 완료")
