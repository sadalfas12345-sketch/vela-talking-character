from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(r"C:\Users\USER\talking-character-demo")
OUT = ROOT / "verification/captureforge-facial-rig-test/video-motion-audit"
items = [
    ("Reference neutral\n468 tracked points", ROOT / "verification/goal2-browInnerUp-proof/step1/neutral-468-overlay.png"),
    ("Female neutral\noriginal textured mesh", OUT / "female/neutral.png"),
    ("Male neutral\noriginal textured mesh", OUT / "male/neutral.png"),
    ("Reference peak\n468 tracked points", ROOT / "verification/goal2-browInnerUp-proof/step1/peak-468-overlay.png"),
    ("Female peak\nCaptureForge coefficients", OUT / "female/peak.png"),
    ("Male peak\nCaptureForge coefficients", OUT / "male/peak.png"),
]
tile_w, tile_h, label_h = 768, 810, 42
sheet = Image.new("RGB", (tile_w * 3, tile_h * 2), "#202020")
draw = ImageDraw.Draw(sheet)
font = ImageFont.load_default()
for i, (label, path) in enumerate(items):
    im = Image.open(path).convert("RGB").resize((tile_w, tile_h - label_h))
    x = (i % 3) * tile_w
    y = (i // 3) * tile_h
    sheet.paste(im, (x, y + label_h))
    draw.rectangle((x, y, x + tile_w, y + label_h), fill="#303030")
    draw.multiline_text((x + 12, y + 8), label, fill="white", font=font, spacing=2)
OUT.mkdir(parents=True, exist_ok=True)
sheet.save(OUT / "reference-and-tripo-comparison.png")
print(OUT / "reference-and-tripo-comparison.png")
