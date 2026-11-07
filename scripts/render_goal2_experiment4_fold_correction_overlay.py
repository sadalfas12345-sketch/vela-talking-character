"""Render a review overlay for the Experiment 4 local fold correction."""
from pathlib import Path
import json
import numpy as np
from PIL import Image, ImageDraw
from correct_goal2_experiment4_local_fold import pairs, side, correct


def main():
    root = Path(__file__).resolve().parents[1]
    out = root / "verification" / "goal2-experiment4"
    configs = {
        "female": (root / "verification/goal1-generalization-run/cross-character-accuracy/female/refined-neutral.png", root / "verification/goal1-generalization-run/cross-character-accuracy/female/refined-camera.json"),
        "male": (root / "verification/goal1-generalization-run/cross-character-accuracy/male/refined-neutral.png", root / "verification/goal1-generalization-run/cross-character-accuracy/male/refined-camera.json"),
    }
    for model, (render_path, camera_path) in configs.items():
        patch = np.load(out / f"{model}-patch.npz")
        solution = np.load(out / f"{model}-landmark70-solution.npz")
        V, U, F = patch["V"], solution["U"], patch["F"]
        candidates = []
        for ia, ib, edge, oa, ob in pairs(F):
            n = np.cross(V[F[ia][1]] - V[F[ia][0]], V[F[ia][2]] - V[F[ia][0]])
            if np.linalg.norm(n) <= 1e-20:
                continue
            n /= np.linalg.norm(n)
            if side(V, edge, oa, n) * side(V, edge, ob, n) < 0 and side(U, edge, oa, n) * side(U, edge, ob, n) >= 0:
                candidates.append((ia, ib, edge, oa, ob))
        corrected = U.copy()
        corrections = correct(corrected, V, F, candidates)
        cam = json.loads(camera_path.read_text())
        image = Image.open(render_path).convert("RGB")
        location = np.asarray(cam["cameraLocation"])
        right = np.asarray(cam["cameraBasis"]["right"])
        up = np.asarray(cam["cameraBasis"]["up"])
        scale = float(cam["orthoScale"])
        w, h = image.size
        def project(P):
            q = P - location
            return np.c_[w / 2 + (q @ right) / scale * w, h / 2 - (q @ up) / scale * h]
        p0, p1, p2 = project(V), project(U), project(corrected)
        draw = ImageDraw.Draw(image)
        for ia, ib, edge, oa, ob in candidates:
            for pts, color, width in ((p0, (80, 160, 255), 3), (p1, (255, 40, 40), 3), (p2, (40, 255, 100), 3)):
                face = F[ia]
                draw.line([tuple(pts[int(v)]) for v in (face[0], face[1], face[2], face[0])], fill=color, width=width)
        draw.rectangle((0, 0, w, 38), fill=(0, 0, 0))
        draw.text((8, 10), f"{model}: blue neutral, red ARAP, green corrected; fold pairs={len(candidates)}", fill="white")
        image.save(out / f"{model}-triangle-fold-correction-overlay.png")
        print(model, "candidates", len(candidates), "corrections", len(corrections))


if __name__ == "__main__":
    main()
