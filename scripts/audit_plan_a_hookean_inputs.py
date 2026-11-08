"""Audit the fixed inputs and topology preconditions for Plan A1."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--video-landmarks", type=Path, required=True)
    p.add_argument("--expression-table", type=Path, required=True)
    p.add_argument("--female-goal1", type=Path, required=True)
    p.add_argument("--male-goal1", type=Path, required=True)
    p.add_argument("--female-patch", type=Path, required=True)
    p.add_argument("--male-patch", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()

    raw = json.loads(a.video_landmarks.read_text(encoding="utf-8"))
    table = json.loads(a.expression_table.read_text(encoding="utf-8"))
    raw_frames = [f for f in raw["frames"] if f.get("valid")]
    table_rows = table["rows"]
    raw_ids = set(raw["landmark_ids"])
    table_count = len(table_rows[0]["landmarks"])
    iris_ids = sorted(set(range(468, table_count)) - raw_ids)
    models = {}
    for name, goal_path, patch_path in (("female", a.female_goal1, a.female_patch), ("male", a.male_goal1, a.male_patch)):
        goal = json.loads(goal_path.read_text(encoding="utf-8"))
        records = {int(r["index"]): r for r in goal["records"] if r.get("meshXYZ") is not None}
        patch = json.loads(patch_path.read_text(encoding="utf-8"))
        p3 = np.asarray([records[i]["meshXYZ"] for i in range(478)], dtype=float)
        eye = float(np.linalg.norm(p3[263] - p3[33]))
        models[name] = {
            "goal1NeutralAttachments": len(records),
            "missingGoal1Ids": [i for i in range(478) if i not in records],
            "interocularWidth": eye,
            "solverVertices": patch["solverVertices"],
            "solverTriangles": patch["solverTriangles"],
            "solverConnectedComponents": len(patch["connectedComponents"]),
            "solverBoundaryVertices": patch["boundaryVertices"],
            "largestComponentVertices": max(x["vertices"] for x in patch["connectedComponents"]),
            "largestComponentTriangles": max(x["triangles"] for x in patch["connectedComponents"]),
        }
    neutral = np.asarray([row["landmarks"] for row in table_rows[:8]], dtype=float)
    neutral_rms = float(np.sqrt(np.mean(np.sum((neutral - neutral.mean(axis=0)) ** 2, axis=2))))
    models["sourceMotion"] = {
        "decodedFrames": raw["decoded_frames"],
        "validFrames": raw["valid_frames"],
        "rawValidatedLandmarkIds": len(raw_ids),
        "rawValidatedIdRange": [min(raw_ids), max(raw_ids)],
        "rawValidatedPerFrameCoordinates": len(raw_frames[0]["landmarks"]) if raw_frames else 0,
        "normalizedExpressionFrames": len(table_rows),
        "normalizedExpressionLandmarksPerFrame": table_count,
        "normalizedExpressionIdRange": [0, table_count - 1],
        "irisIdsInExpressionTable": iris_ids,
        "irisRawValidated": bool(set(iris_ids).issubset(raw_ids)),
        "neutralMotionRmsInTableUnits": neutral_rms,
        "trajectoryDimensionality": "2D head-stabilized; no validated per-frame depth trajectory",
        "fullyMeasured3DTrajectories": 0,
        "embedded3DConstraintsIfDepthSetZero": len(table_rows) * table_count,
    }
    result = {
        "status": "PLAN_A_INPUT_AUDIT_FAILED_PRECONDITION",
        "sourceMotion": models.pop("sourceMotion"),
        "models": models,
        "hardBlockers": [
            "No validated head-stabilized per-frame depth trajectory exists for the 478-landmark expression table.",
            "The original-topology geodesic facial selections are disconnected, so they are not one connected Hookean skin network.",
        ],
        "notRun": [
            "Hookean equilibrium",
            "intermediate substeps",
            "per-frame landmark residuals",
            "deformed renders",
        ],
        "depthPolicy": "No depth values were fabricated. Setting dz=0 would be an unmeasured embedding, not observed 3D motion.",
    }
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
