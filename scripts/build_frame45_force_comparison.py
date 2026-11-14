"""Build a compact textured comparison for the GPU-consistent frame-45 run."""

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "verification" / "reference-expression-replay" / "frame045-force-comparison.png"

PANELS = [
    ("Reference video, frame 45", ROOT / "verification/reference-expression-replay/reference-frame045.png"),
    ("Female, neutral", ROOT / "verification/reference-expression-replay/female-frame045-gpu-consistent-rerun-render-neutral.png"),
    ("Female, GPU-consistent force result", ROOT / "verification/reference-expression-replay/female-frame045-gpu-consistent-rerun-render-supported.png"),
    ("Male, neutral", ROOT / "verification/reference-expression-replay/male-frame045-gpu-consistent-rerun-render-neutral.png"),
    ("Male, GPU-consistent force result", ROOT / "verification/reference-expression-replay/male-frame045-gpu-consistent-rerun-render-supported.png"),
]


def load_font(size: int):
    for candidate in (
        Path("C:/Windows/Fonts/arial.ttf"),
        Path("C:/Windows/Fonts/segoeui.ttf"),
    ):
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size)
    return ImageFont.load_default()


def main() -> None:
    missing = [str(path) for _, path in PANELS if not path.exists()]
    if missing:
        raise SystemExit("Missing comparison inputs:\n" + "\n".join(missing))

    tile_w, tile_h = 640, 700
    canvas = Image.new("RGB", (tile_w * 3, tile_h * 2), (24, 24, 28))
    draw = ImageDraw.Draw(canvas)
    title_font = load_font(24)
    label_font = load_font(20)

    for index, (label, path) in enumerate(PANELS):
        row, col = divmod(index, 3)
        image = Image.open(path).convert("RGB")
        image.thumbnail((tile_w - 20, tile_h - 72), Image.Resampling.LANCZOS)
        x = col * tile_w + (tile_w - image.width) // 2
        y = row * tile_h + 54 + (tile_h - 54 - image.height) // 2
        draw.rectangle((col * tile_w, row * tile_h, (col + 1) * tile_w - 1, (row + 1) * tile_h - 1), outline=(90, 90, 100), width=2)
        draw.text((col * tile_w + 14, row * tile_h + 14), label, fill=(240, 240, 245), font=title_font)
        canvas.paste(image, (x, y))

    draw.text((tile_w * 2 + 14, tile_h + 14), "GPU result panels are the frame-45 force solve", fill=(210, 210, 220), font=label_font)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(OUT)
    print(OUT)


if __name__ == "__main__":
    main()
