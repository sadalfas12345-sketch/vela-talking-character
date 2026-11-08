from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(r"C:\Users\USER\talking-character-demo")
OUT = ROOT / "verification/captureforge-facial-rig-test/control-calibration"
labels = ["neutral", "browInnerUp", "eyeBlinkLeft", "jawOpen", "mouthSmileLeft"]
rows = ["female", "male"]
tw, th, lh = 512, 550, 34
sheet = Image.new("RGB", (tw * len(labels), th * len(rows)), "#202020")
draw = ImageDraw.Draw(sheet)
font = ImageFont.load_default()
for r, character in enumerate(rows):
    for c, label in enumerate(labels):
        path = OUT / character / "validation" / f"{label}.png"
        im = Image.open(path).convert("RGB").resize((tw, th - lh))
        x, y = c * tw, r * th
        sheet.paste(im, (x, y + lh))
        draw.rectangle((x, y, x + tw, y + lh), fill="#303030")
        draw.text((x + 8, y + 9), f"{character} {label}", fill="white", font=font)
sheet.save(OUT / "calibration-expression-comparison.png")
print(OUT / "calibration-expression-comparison.png")
