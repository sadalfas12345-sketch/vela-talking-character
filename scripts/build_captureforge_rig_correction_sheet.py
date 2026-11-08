from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(r"C:\Users\USER\talking-character-demo")
BASE = ROOT / "verification/captureforge-facial-rig-test/control-calibration"
CORR = ROOT / "verification/captureforge-facial-rig-test/rig-construction-correction"
OUT = CORR / "baseline-versus-corrected.png"
labels = ["neutral", "browInnerUp", "eyeBlinkLeft", "jawOpen", "mouthSmileLeft"]
rows = ["female", "male"]
tw, th, lh = 512, 560, 34
sheet = Image.new("RGB", (tw * len(labels), th * len(rows) * 2), "#202020")
draw = ImageDraw.Draw(sheet)
font = ImageFont.load_default()
for r, character in enumerate(rows):
    for variant, root in (("baseline", BASE), ("corrected", CORR)):
        rr = r * 2 + (0 if variant == "baseline" else 1)
        for c, label in enumerate(labels):
            path = root / character / "validation" / f"{label}.png"
            im = Image.open(path).convert("RGB").resize((tw, th - lh))
            x, y = c * tw, rr * th
            sheet.paste(im, (x, y + lh))
            draw.rectangle((x, y, x + tw, y + lh), fill="#303030")
            draw.text((x + 8, y + 9), f"{character} {variant} {label}", fill="white", font=font)
sheet.save(OUT)
print(OUT)
