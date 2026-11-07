"""Build visual-only landmark annotation plates for Goal 2.

This script reads existing renders and landmark records. It does not recalculate,
move, or deform any mesh or landmark. It writes PNG annotations and an HTML index.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageDraw, ImageFont, ImageOps


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "verification" / "goal2-visual-landmark-annotation"
VIDEO_JSON = ROOT / "verification/goal2-browInnerUp-proof/step1/video_landmarks.json"
VIDEO_DIR = ROOT / "verification/goal2-browInnerUp-proof/worried-frames"
TRIPO_ROOT = ROOT / "verification/goal1-generalization-run/cross-character-accuracy"
MARKER_ROOT = ROOT / "verification/goal2-browInnerUp-proof/step4-tripo-transfer"

REGIONS = {
    "eyebrows": ([46, 53, 52, 65, 55, 70, 63, 105, 276, 283, 282, 295, 285, 336, 293, 334], (255, 190, 0)),
    "eyes-eyelids": ([33, 133, 159, 145, 386, 374, 263, 362, 155, 154, 384, 385], (0, 220, 255)),
    "nose": ([1, 2, 4, 5, 6, 19, 94, 168, 195, 197, 236, 3, 51, 281, 275, 45], (80, 230, 100)),
    "mouth-lips": ([61, 291, 13, 14, 78, 308, 95, 324, 82, 312, 87, 317], (255, 70, 190)),
    "jaw-cheeks": ([10, 152, 234, 454, 127, 356, 93, 132, 361, 323], (80, 130, 255)),
}
REGION_BY_ID = {i: (name, color) for name, (ids, color) in REGIONS.items() for i in ids}


def font(size: int):
    for p in (Path("C:/Windows/Fonts/arial.ttf"), Path("C:/Windows/Fonts/segoeui.ttf")):
        if p.exists():
            return ImageFont.truetype(str(p), size)
    return ImageFont.load_default()


FONT = font(18)
SMALL = font(14)
TITLE = font(24)


def load(path: Path) -> Image.Image:
    return Image.open(path).convert("RGB")


def point_xy(p, w, h):
    if isinstance(p, dict):
        x, y = p["x"], p["y"]
    else:
        x, y = p[0], p[1]
    return (float(x) * w, float(y) * h)


def draw_dot(draw, xy, color, radius=3, label=None):
    x, y = xy
    draw.ellipse((x-radius, y-radius, x+radius, y+radius), fill=color, outline=(20, 20, 20), width=1)
    if label is not None:
        tx, ty = x + radius + 2, y - radius - 2
        draw.text((tx+1, ty+1), str(label), fill=(0, 0, 0), font=SMALL)
        draw.text((tx, ty), str(label), fill=(255, 255, 255), font=SMALL)


def annotate(img, points, labels=False, title=None, selected=None, arrows=None):
    out = img.copy()
    d = ImageDraw.Draw(out)
    w, h = out.size
    selected = set(selected) if selected is not None else None
    for i, p in enumerate(points):
        if selected is not None and i not in selected:
            continue
        xy = point_xy(p, w, h)
        color = REGION_BY_ID.get(i, (190, 190, 190))[1]
        draw_dot(d, xy, color, radius=max(2, round(w / 320)), label=i if labels else None)
    if arrows:
        for i, a, b in arrows:
            d.line((a[0], a[1], b[0], b[1]), fill=(255, 255, 255), width=max(1, round(w / 700)))
            dx, dy = b[0] - a[0], b[1] - a[1]
            mag = max((dx*dx + dy*dy) ** 0.5, 1.0)
            ux, uy = dx / mag, dy / mag
            px, py = -uy, ux
            tip = b
            left = (b[0] - ux*8 + px*4, b[1] - uy*8 + py*4)
            right = (b[0] - ux*8 - px*4, b[1] - uy*8 - py*4)
            d.polygon((tip, left, right), fill=(255, 255, 255))
    if title:
        d.rectangle((0, 0, w, 34), fill=(0, 0, 0))
        d.text((10, 5), title, fill=(255, 255, 255), font=TITLE)
    return out


def bbox(points, size, margin=45):
    w, h = size
    xs, ys = zip(*points)
    return (max(0, int(min(xs)-margin)), max(0, int(min(ys)-margin)), min(w, int(max(xs)+margin)), min(h, int(max(ys)+margin)))


def crop_region(img, points, ids, title):
    xy = [point_xy(points[i], *img.size) for i in ids]
    box = bbox(xy, img.size, margin=max(35, img.size[0] // 18))
    crop = img.crop(box)
    shifted = [(x-box[0], y-box[1]) for x, y in xy]
    # Rebuild a compact regional plate from the already annotated crop.
    d = ImageDraw.Draw(crop)
    color = REGIONS[title][1]
    for i, (x, y) in zip(ids, shifted):
        draw_dot(d, (x, y), color, radius=max(3, crop.size[0] // 180), label=i)
    d.rectangle((0, 0, crop.size[0], 30), fill=(0, 0, 0))
    d.text((8, 4), title, fill=(255, 255, 255), font=TITLE)
    return crop


def side_by_side(images, titles, path, width=480):
    scaled = []
    for im, title in zip(images, titles):
        h = int(im.height * width / im.width)
        x = im.resize((width, h), Image.Resampling.LANCZOS)
        canvas = Image.new("RGB", (width, h + 36), "black")
        canvas.paste(x, (0, 36))
        ImageDraw.Draw(canvas).text((8, 7), title, fill="white", font=TITLE)
        scaled.append(canvas)
    out = Image.new("RGB", (width * len(scaled), max(x.height for x in scaled)), "black")
    x = 0
    for im in scaled:
        out.paste(im, (x, 0)); x += width
    out.save(path)


def video_points(data, frame_index):
    frame = next(f for f in data["frames"] if f["frame"] == frame_index)
    return frame["landmarks"]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    video = json.loads(VIDEO_JSON.read_text(encoding="utf-8"))
    outputs = []

    # Existing clean reference frames, with existing tracked coordinates.
    ref_specs = [("neutral", 0, "start.png"), ("peak", 99, "end.png")]
    reference = {}
    for name, fi, img_name in ref_specs:
        im = load(VIDEO_DIR / img_name)
        pts = video_points(video, fi)
        p = OUT / f"reference-{name}-all468.png"
        annotate(im, pts, title=f"Reference {name} - existing MediaPipe IDs 0-467").save(p)
        outputs.append(p); reference[name] = (im, pts)
        for region, (ids, _) in REGIONS.items():
            q = OUT / f"reference-{name}-{region}.png"
            crop_region(im, pts, ids, region).save(q); outputs.append(q)

    models = {}
    for model in ("female", "male"):
        base = TRIPO_ROOT / model
        im = load(base / "refined-neutral.png")
        det = json.loads((base / "refined/detected-landmarks.json").read_text(encoding="utf-8"))["landmarks"]
        allp = OUT / f"{model}-neutral-all468.png"
        annotate(im, det, title=f"Tripo {model} - existing Goal 1 surface landmarks").save(allp); outputs.append(allp)
        models[model] = (im, det)
        for region, (ids, _) in REGIONS.items():
            q = OUT / f"{model}-neutral-{region}.png"
            crop_region(im, det, ids, region).save(q); outputs.append(q)
        # Preserve the existing oblique attachment evidence as a referenced, copied plate.
        oblique = base / "oblique-3d-attachments.png"
        if oblique.exists():
            q = OUT / f"{model}-oblique-3d-attachments.png"
            shutil.copy2(oblique, q); outputs.append(q)

        markers = json.loads((MARKER_ROOT / model / "landmark_markers.json").read_text(encoding="utf-8"))
        neutral = markers["neutral"]
        peak = markers["samples"]["100"]
        cam = json.loads((base / "refined-camera.json").read_text(encoding="utf-8"))
        loc = cam["cameraLocation"]; right = cam["cameraBasis"]["right"]; up = cam["cameraBasis"]["up"]
        scale = cam["orthoScale"]; w, h = im.size
        def project(p):
            v = [p[i] - loc[i] for i in range(3)]
            return (w/2 + sum(v[i]*right[i] for i in range(3))/scale*w,
                    h/2 - sum(v[i]*up[i] for i in range(3))/scale*h)
        np = [project(p) for p in neutral]; pp = [project(p) for p in peak]
        arrows = [(i, np[i], pp[i]) for i in range(468)]
        arrow_img = annotate(im, [], title=f"Tripo {model} - neutral to existing 100% target", arrows=arrows)
        q = OUT / f"{model}-neutral-to-peak-arrows-all468.png"; arrow_img.save(q); outputs.append(q)
        brow = annotate(im, [], title=f"Tripo {model} - eyebrow target arrows", arrows=[a for a in arrows if a[0] in REGIONS["eyebrows"][0]])
        # Add labels and neutral/peak dots for brow IDs.
        d = ImageDraw.Draw(brow)
        for i in REGIONS["eyebrows"][0]:
            draw_dot(d, np[i], (80, 180, 255), radius=5, label=i)
            draw_dot(d, pp[i], (255, 90, 90), radius=5, label=None)
        q = OUT / f"{model}-eyebrow-target-arrows.png"; brow.save(q); outputs.append(q)
        models[model] = (im, det, {"neutral": np, "peak": pp})

    # Comparison plates, using the same source images and regional crops.
    side_by_side([reference["neutral"][0], models["female"][0], models["male"][0]], ["Reference neutral", "Female Tripo", "Male Tripo"], OUT / "comparison-neutral-reference-female-male.png")
    outputs.append(OUT / "comparison-neutral-reference-female-male.png")
    for region, (ids, _) in REGIONS.items():
        imgs = [crop_region(reference["neutral"][0], reference["neutral"][1], ids, region), crop_region(models["female"][0], models["female"][1], ids, region), crop_region(models["male"][0], models["male"][1], ids, region)]
        q = OUT / f"comparison-{region}.png"; side_by_side(imgs, ["Reference neutral", "Female Tripo", "Male Tripo"], q, width=420); outputs.append(q)

    manifest = {
        "purpose": "visual annotation only",
        "coordinates_modified": False,
        "geometry_modified": False,
        "source_video_landmarks": str(VIDEO_JSON.relative_to(ROOT)),
        "source_goal1_render_root": str(TRIPO_ROOT.relative_to(ROOT)),
        "source_transferred_markers": str(MARKER_ROOT.relative_to(ROOT)),
        "outputs": [str(p.relative_to(ROOT)) for p in outputs],
        "regions": {k: v[0] for k, v in REGIONS.items()},
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    html = ["<!doctype html><meta charset='utf-8'><title>Goal 2 Visual Landmark Annotation</title>", "<h1>Goal 2 Visual Landmark Annotation</h1><p>Existing coordinates only. No scoring or deformation.</p>"]
    for p in outputs:
        rel = p.name
        html.append(f"<figure><a href='{rel}'><img src='{rel}' style='max-width:640px'></a><figcaption>{rel}</figcaption></figure>")
    (OUT / "index.html").write_text("\n".join(html), encoding="utf-8")
    print(f"Wrote {len(outputs)} images to {OUT}")


if __name__ == "__main__":
    main()
