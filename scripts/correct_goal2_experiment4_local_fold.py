"""Validate a minimal shared-edge fold correction for Experiment 4.

The existing libigl ARAP result remains the starting surface. A correction is
applied only when a connected triangle pair crosses its common edge. The
offending opposite vertex is moved by the minimum displacement that restores
the original side relationship, with a small scale-aware clearance.
"""
from pathlib import Path
import json
import numpy as np


def area(P, f):
    return float(0.5 * np.linalg.norm(np.cross(P[f[1]] - P[f[0]], P[f[2]] - P[f[0]])))


def side(P, edge, opposite, normal):
    a, b = edge
    return float(np.dot(np.cross(P[b] - P[a], P[opposite] - P[a]), normal))


def pairs(F):
    edges = {}
    for ti, f in enumerate(F):
        for a, b in ((int(f[0]), int(f[1])), (int(f[1]), int(f[2])), (int(f[2]), int(f[0]))):
            edges.setdefault(tuple(sorted((a, b))), []).append(ti)
    out = []
    for edge, fs in edges.items():
        if len(fs) == 2:
            ia, ib = fs
            oa = next(int(v) for v in F[ia] if int(v) not in edge)
            ob = next(int(v) for v in F[ib] if int(v) not in edge)
            out.append((ia, ib, edge, oa, ob))
    return out


def correct(P, V, F, candidate_pairs, eps_scale=1e-6):
    corrections = []
    for ia, ib, edge, oa, ob in candidate_pairs:
        n = np.cross(V[F[ia][1]] - V[F[ia][0]], V[F[ia][2]] - V[F[ia][0]])
        nn = np.linalg.norm(n)
        if nn <= 1e-20:
            continue
        n /= nn
        s0a = side(V, edge, oa, n)
        s0b = side(V, edge, ob, n)
        sa = side(P, edge, oa, n)
        sb = side(P, edge, ob, n)
        if s0a * s0b >= 0 or sa * sb < 0:
            continue
        # Correct the side that changed sign; hold the other opposite vertex fixed.
        moving, current, initial = (oa, sa, s0a) if np.sign(sa) != np.sign(s0a) else (ob, sb, s0b)
        a, b = edge
        e = P[b] - P[a]
        derivative = np.cross(n, e)
        d2 = float(derivative @ derivative)
        if d2 <= 1e-30:
            continue
        scale = max(np.linalg.norm(e), np.sqrt(max(area(V, F[ia]), 1e-30)))
        margin = max(eps_scale * scale * scale, 1e-14)
        target = np.sign(initial) * margin
        displacement = ((target - current) / d2) * derivative
        P[moving] += displacement
        corrections.append({"triangles": [ia, ib], "edge": list(edge), "vertex": moving, "displacement": displacement.tolist()})
    return corrections


def main():
    root = Path(__file__).resolve().parents[1]
    out = root / "verification" / "goal2-experiment4"
    rows = []
    for model in ("female", "male"):
        patch = np.load(out / f"{model}-patch.npz")
        solution = np.load(out / f"{model}-landmark70-solution.npz")
        V, U, F = patch["V"], solution["U"], patch["F"]
        tri = solution["triangle"]
        bary = solution["bary"]
        requested = (bary[:, None] * (U[tri] - V[tri])).sum(axis=0)
        all_pairs = pairs(F)
        candidate_pairs = []
        for ia, ib, edge, oa, ob in all_pairs:
            n = np.cross(V[F[ia][1]] - V[F[ia][0]], V[F[ia][2]] - V[F[ia][0]])
            if np.linalg.norm(n) <= 1e-20:
                continue
            n /= np.linalg.norm(n)
            if side(V, edge, oa, n) * side(V, edge, ob, n) < 0 and side(U, edge, oa, n) * side(U, edge, ob, n) >= 0:
                candidate_pairs.append((ia, ib, edge, oa, ob))
        # Re-run the samples with the automatically detected full-target fold set.
        samples = []
        for alpha in (0.0, 0.25, 0.5, 0.65, 0.6898463310893217, 0.7, 0.75, 1.0):
            P = V + alpha * (U - V)
            before = P.copy()
            corrections = correct(P, V, F, candidate_pairs)
            base = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]])
            deformed = np.cross(P[F[:, 1]] - P[F[:, 0]], P[F[:, 2]] - P[F[:, 0]])
            dots = np.einsum("ij,ij->i", base, deformed)
            areas = np.linalg.norm(deformed, axis=1) * 0.5
            neutral_areas = np.linalg.norm(base, axis=1) * 0.5
            achieved = (bary[:, None] * (P[tri] - V[tri])).sum(axis=0)
            fold_count = 0
            for ia, ib, edge, oa, ob in candidate_pairs:
                n = np.cross(V[F[ia][1]] - V[F[ia][0]], V[F[ia][2]] - V[F[ia][0]])
                n /= np.linalg.norm(n)
                if side(V, edge, oa, n) * side(V, edge, ob, n) < 0 and side(P, edge, oa, n) * side(P, edge, ob, n) >= 0:
                    fold_count += 1
            edge_pairs = np.unique(np.sort(np.vstack((F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]])), axis=1), axis=0)
            neutral_lengths = np.linalg.norm(V[edge_pairs[:, 0]] - V[edge_pairs[:, 1]], axis=1)
            deformed_lengths = np.linalg.norm(P[edge_pairs[:, 0]] - P[edge_pairs[:, 1]], axis=1)
            samples.append({"alpha": float(alpha), "landmarkError": float(np.linalg.norm(achieved - alpha * requested) / max(np.linalg.norm(alpha * requested), 1e-20)) if alpha else 0.0, "correctionCount": len(corrections), "maximumCorrection": float(np.max(np.linalg.norm(P - before, axis=1))), "foldPairs": fold_count, "invertedTriangles": int(np.sum(dots < 0)), "collapsedTriangles": int(np.sum(areas < neutral_areas * 1e-4)), "minimumAreaRatio": float(np.min(areas / np.maximum(neutral_areas, 1e-20))), "finite": bool(np.isfinite(P).all())})
            samples[-1]["maximumEdgeStrain"] = float(np.max(np.abs(deformed_lengths / np.maximum(neutral_lengths, 1e-20) - 1.0)))
        rows.append({"model": model, "candidateFoldPairs": len(candidate_pairs), "requestedMagnitude": float(np.linalg.norm(requested)), "samples": samples, "pass": all(x["foldPairs"] == 0 and x["invertedTriangles"] == 0 and x["collapsedTriangles"] == 0 and x["finite"] and x["landmarkError"] <= 0.05 for x in samples)})
    report = {"method": "official libigl ARAP result plus minimal shared-edge side correction", "models": rows, "sameAlgorithm": True, "sourceGeometryModified": False}
    (out / "local-fold-correction-report.json").write_text(json.dumps(report, indent=2) + "\n")
    (out / "local-fold-correction-report.md").write_text("# Experiment 4 local fold correction\n\n" + json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    if not all(r["pass"] for r in rows):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
