"""Non-mutating visual and record audit of existing Goal-1 attachments.

The script does not detect, move, replace, or deform landmarks. It combines the
existing raycast records with the previously selected visual reference set and
produces an honest audit inventory. Unreviewed IDs remain explicitly unreviewed.
"""
from __future__ import annotations

import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "verification" / "goal2-landmark-attachment-audit"
TRIPO_ROOT = ROOT / "verification/goal1-generalization-run/cross-character-accuracy"
SELECTED = ROOT / "verification/goal1-tripo-landmark-evidence/goal1-tripo-deterministic-landmark-manifest.json"
REGIONS = {
    "eyebrows": [46, 53, 52, 65, 55, 70, 63, 105, 276, 283, 282, 295, 285, 336, 293, 334],
    "eyes-eyelids": [33, 133, 159, 145, 386, 374, 263, 362],
    "nose": [168, 6, 1, 98, 327],
    "mouth-lips": [61, 291, 13, 14, 78, 308, 95, 324, 82, 317],
    "jaw-cheeks": [152, 172, 397],
}
BROW_IDS = set(REGIONS["eyebrows"])


def fnt(size):
    p = Path("C:/Windows/Fonts/arial.ttf")
    return ImageFont.truetype(str(p), size) if p.exists() else ImageFont.load_default()


def load_json(p):
    return json.loads(p.read_text(encoding="utf-8"))


def annotate(model, status_by_id):
    base = Image.open(TRIPO_ROOT / model / "refined-neutral.png").convert("RGB")
    detected = load_json(TRIPO_ROOT / model / "refined/detected-landmarks.json")["landmarks"]
    d = ImageDraw.Draw(base)
    w, h = base.size
    for i in sorted(BROW_IDS):
        x, y = detected[i][0] * w, detected[i][1] * h
        status = status_by_id.get(i, "UNCERTAIN")
        color = {"CORRECT": (50, 220, 80), "MISPLACED": (255, 50, 50), "UNCERTAIN": (255, 210, 20)}.get(status, (255, 210, 20))
        r = 7
        d.ellipse((x-r, y-r, x+r, y+r), outline=color, width=3)
        d.text((x+9, y-10), str(i), fill=color, font=fnt(16))
    d.rectangle((0, 0, w, 34), fill=(0, 0, 0))
    d.text((10, 6), f"{model.title()} Tripo brow attachment audit: yellow = uncertain", fill="white", font=fnt(20))
    return base


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    selected = load_json(SELECTED)
    selected_ids = [int(x["mediapipeIndex"]) for x in selected["attachments"]]
    selected_names = {int(x["mediapipeIndex"]): x["name"] for x in selected["attachments"]}

    # The 30-point set is the existing selected visual reference set. Its
    # classifications are limited to what the supplied frontal and oblique
    # evidence supports. Jawline 397 remains unresolved in the source evidence.
    selected_status = {i: ("UNCERTAIN" if i == 397 else "CORRECT") for i in selected_ids}
    brow_status = {i: "UNCERTAIN" for i in BROW_IDS}

    inventory = []
    rows = []
    for model in ("female", "male"):
        report = load_json(TRIPO_ROOT / model / "refined/raycast-report.json")
        records = {int(r["index"]): r for r in report["records"]}
        for i in range(468):
            r = records.get(i)
            if r is None:
                inventory.append({"model": model, "landmarkId": i, "auditStatus": "MISSING_RECORD"})
                continue
            if i in selected_status:
                status = selected_status[i]
                basis = "existing 30-point frontal and oblique evidence"
            elif i in brow_status:
                status = "UNCERTAIN"
                basis = "brow close-up visual evidence; boundary between brow, eyelid, and forehead is not independently resolved"
            else:
                status = "NOT_VISUALLY_AUDITED"
                basis = "preserved Goal-1 raycast record only; no visual classification claimed"
            inventory.append({
                "model": model,
                "landmarkId": i,
                "auditStatus": status,
                "auditBasis": basis,
                "meshObject": r.get("hitObject"),
                "triangleIndex": r.get("triangleIndex"),
                "triangleVertexIndices": r.get("triangleVertexIndices"),
                "barycentricCoordinates": r.get("barycentricCoordinates"),
                "meshXYZ": r.get("meshXYZ"),
                "frontSurface": r.get("frontSurface"),
                "surfaceVisibleFromFrontalCamera": r.get("surfaceVisibleFromFrontalCamera"),
                "frontNormalFacingDot": r.get("frontNormalFacingDot"),
                "region": next((name for name, ids in REGIONS.items() if i in ids), None),
            })
        counts = {s: sum(1 for x in inventory if x["model"] == model and x["auditStatus"] == s) for s in ["CORRECT", "MISPLACED", "UNCERTAIN", "NOT_VISUALLY_AUDITED", "MISSING_RECORD"]}
        rows.append((model, counts))
        audit_img = annotate(model, brow_status)
        audit_img.save(OUT / f"{model}-brow-questionable-attachments.png")

    report_md = [
        "# Goal 2: Existing Goal-1 Landmark Attachment Audit",
        "",
        "This is a non-mutating visual and record audit. No landmark coordinates, mesh geometry, attachments, or trajectories were changed.",
        "",
        "## Scope and evidence",
        "",
        f"The existing 30-point reference set contains {len(selected_ids)} IDs. The eyebrow close-up was additionally inspected for {len(BROW_IDS)} IDs. The remaining IDs are retained in the inventory but are not visually classified.",
        "",
        "The 30-point classifications use the existing frontal and oblique evidence. They are not a new independent reference annotation. Eyebrow points are marked UNCERTAIN because the supplied textured close-ups do not independently resolve whether every point is on brow hair, brow skin, eyelid, or forehead skin.",
        "",
        "## Counts",
        "",
        "| Model | CORRECT | MISPLACED | UNCERTAIN | NOT_VISUALLY_AUDITED | Missing record |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for model, c in rows:
        report_md.append(f"| {model} | {c['CORRECT']} | {c['MISPLACED']} | {c['UNCERTAIN']} | {c['NOT_VISUALLY_AUDITED']} | {c['MISSING_RECORD']} |")
    report_md += [
        "",
        "## Findings requiring attention",
        "",
        "- **Female brow IDs 46, 53, 52, 65, 55, 70, 63, 105, 276, 283, 282, 295, 285, 336, 293, 334: UNCERTAIN.** The points are visible in the brow close-up, but the image does not establish a correct 3D anatomical attachment for each point. No point is declared MISPLACED from this evidence alone.",
        "- **Male brow IDs 46, 53, 52, 65, 55, 70, 63, 105, 276, 283, 282, 295, 285, 336, 293, 334: UNCERTAIN** for the same reason. The male close-up appears visually more aligned, but that is not enough to certify every surface attachment.",
        "- **Landmark 397: UNCERTAIN** in the existing selected set because the earlier Goal-1 evidence identifies the left jawline point as unresolved.",
        "- **No confirmed MISPLACED attachment was established.** A successful raycast or barycentric reconstruction was not treated as anatomical proof.",
        "",
        "## Exact attachment records",
        "",
        "The machine-readable inventory preserves, for every model and ID, the hit mesh object, triangle index, triangle vertex indices, barycentric coordinates, mesh position, visibility flags, and audit status.",
        "",
        "## Visual evidence",
        "",
        "- `female-brow-questionable-attachments.png` and `male-brow-questionable-attachments.png` highlight the brow IDs in yellow because they remain uncertain.",
        "- The original annotation plates remain unchanged in `verification/goal2-visual-landmark-annotation/`.",
        "- Existing oblique attachment images were used as evidence and were not regenerated or altered.",
        "",
        "## Decision",
        "",
        "This audit does not authorize correction. The current evidence supports preserving the existing attachments and treating the brow set plus landmark 397 as unresolved pending a geometry-aware close-up review of the exact hit triangles.",
    ]
    (OUT / "landmark-attachment-audit.md").write_text("\n".join(report_md), encoding="utf-8")
    (OUT / "landmark-attachment-audit.json").write_text(json.dumps({"scope": "visual and record audit only", "coordinatesModified": False, "geometryModified": False, "inventory": inventory}, indent=2), encoding="utf-8")
    html = "<h1>Goal 2 Landmark Attachment Audit</h1><p>No coordinates or geometry changed.</p>"
    for p in sorted(OUT.glob("*.png")):
        html += f"<figure><img src='{p.name}' style='max-width:900px'><figcaption>{p.name}</figcaption></figure>"
    (OUT / "index.html").write_text("<!doctype html><meta charset='utf-8'>" + html, encoding="utf-8")
    print(f"Wrote audit to {OUT}")


if __name__ == "__main__":
    main()
