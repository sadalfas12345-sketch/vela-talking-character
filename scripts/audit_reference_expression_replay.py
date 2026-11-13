"""Audit the existing reference-video targets before Plan A replay.

This script only reads the existing capture, stabilized expression table,
character-specific target arrays, and spring graph. It does not alter meshes,
attachments, trajectories, or solver parameters.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np


REGIONS = {
    "eyebrows": [70, 63, 105, 336, 293, 334, 107, 300, 65, 52, 53, 46, 285, 295, 282, 283, 276],
    "eyelids": [33, 133, 159, 145, 160, 144, 153, 154, 155, 263, 362, 386, 374, 385, 380, 373, 390, 249],
    "cheeks": [50, 101, 118, 123, 187, 205, 36, 206, 216, 215, 214, 280, 330, 347, 352, 411, 425, 266, 426, 436, 435, 434],
    "lips": [0, 13, 14, 17, 39, 61, 84, 87, 88, 91, 95, 146, 178, 181, 269, 291, 308, 314, 317, 318, 321, 324, 375, 402, 405],
    "jaw": [152, 148, 176, 149, 150, 136, 365, 377, 400, 378, 379, 394, 172, 132, 361],
}


def finite_stats(array: np.ndarray) -> dict:
    values = np.asarray(array, dtype=float)
    return {"finite": bool(np.isfinite(values).all()), "nanOrInf": int(np.size(values) - np.isfinite(values).sum())}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True, choices=["female", "male"])
    parser.add_argument("--capture", type=Path, required=True)
    parser.add_argument("--table", type=Path, required=True)
    parser.add_argument("--graph", type=Path, required=True)
    parser.add_argument("--targets", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--selected-frames", type=int, nargs="+", default=[0, 45, 97, 99])
    args = parser.parse_args()

    capture = np.load(args.capture, allow_pickle=True)
    table = json.loads(args.table.read_text(encoding="utf-8"))
    graph = np.load(args.graph, allow_pickle=True)
    targets = np.load(args.targets, allow_pickle=True)

    capture_landmarks = np.asarray(capture["landmarks"], dtype=float)
    capture_valid = np.asarray(capture["valid"], dtype=bool)
    table_rows = table.get("rows", [])
    table_landmarks = np.asarray([row["landmarks"] for row in table_rows], dtype=float)
    target_array = np.asarray(targets["targets"], dtype=float)
    neutral = np.asarray(graph["V"], dtype=float)
    triangles = np.asarray(graph["constraintTriangles"], dtype=np.int64)
    bary = np.asarray(graph["constraintBary"], dtype=float)
    neutral_landmarks = np.asarray(graph["neutralLandmarks"], dtype=float)

    valid_triangles = bool(np.all((triangles >= 0) & (triangles < len(neutral))))
    bary_sums = bary.sum(axis=1)
    reconstructed_neutral = np.einsum("ij,ijk->ik", bary, neutral[triangles])
    neutral_error = np.linalg.norm(reconstructed_neutral - neutral_landmarks, axis=1)
    selected = {}
    baseline = target_array[0]
    for frame in args.selected_frames:
        if frame < 0 or frame >= len(target_array):
            continue
        delta = target_array[frame] - baseline
        region = {}
        for name, ids in REGIONS.items():
            values = np.linalg.norm(delta[ids], axis=1)
            region[name] = {
                "landmarks": len(ids),
                "maxDisplacement": float(values.max()),
                "rmsDisplacement": float(np.sqrt(np.mean(values * values))),
                "meanDisplacement": float(values.mean()),
            }
        selected[str(frame)] = {
            "timeSeconds": float(capture["times"][frame]) if frame < len(capture["times"]) else float(frame / 24.0),
            "maxDisplacement": float(np.linalg.norm(delta, axis=1).max()),
            "rmsDisplacement": float(np.sqrt(np.mean(np.sum(delta * delta, axis=1)))),
            "regions": region,
        }

    negative = np.argwhere(bary < 0)
    output = {
        "schema": "vela-reference-expression-replay-audit-v1",
        "model": args.model,
        "source": {
            "capture": str(args.capture),
            "table": str(args.table),
            "graph": str(args.graph),
            "targets": str(args.targets),
            "videoProvenance": table.get("video"),
            "headStabilization": table.get("rows", [{}])[0].get("headAlignment") if table_rows else None,
        },
        "tracking": {
            "captureFrames": int(len(capture_landmarks)),
            "captureLandmarkColumns": int(capture_landmarks.shape[1]) if capture_landmarks.ndim >= 2 else 0,
            "captureValidFrames": int(capture_valid.sum()),
            "captureTransformationMatrices": int(len(capture.get("mats", []))),
            "blendshapeCoefficientNames": int(len(capture.get("names", []))),
            "tableFrames": int(len(table_rows)),
            "tableLandmarkColumns": int(table_landmarks.shape[1]) if table_landmarks.ndim >= 2 else 0,
            "tableDerivedTrajectoryIds": "468-477",
            "rawValidatedTrajectoryIds": "0-467",
            "direct3DDepthMeasurementAvailable": False,
        },
        "targets": {
            "frames": int(target_array.shape[0]),
            "landmarks": int(target_array.shape[1]),
            "coordinates": int(target_array.shape[2]),
            "finite": bool(np.isfinite(target_array).all()),
            "neutralMatchesGraph": bool(np.allclose(target_array[0], neutral_landmarks, atol=1e-12, rtol=0.0)),
            "selectedFrames": selected,
        },
        "correspondence": {
            "simulationVertices": int(len(neutral)),
            "simulationTriangles": int(len(graph["F"])),
            "constraintCount": int(len(triangles)),
            "validTriangleIndices": valid_triangles,
            "finiteBarycentricWeights": bool(np.isfinite(bary).all()),
            "maxWeightSumError": float(np.max(np.abs(bary_sums - 1.0))),
            "negativeWeightCount": int(len(negative)),
            "negativeWeightRows": sorted(set(int(row) for row in negative[:, 0])) if len(negative) else [],
            "neutralReconstructionMaxError": float(neutral_error.max()),
            "neutralReconstructionRmsError": float(np.sqrt(np.mean(neutral_error * neutral_error))),
            "virtualSprings": int(len(graph.get("virtualSprings", []))),
            "sourceComponents": int(json.loads(args.graph.with_suffix(".json").read_text(encoding="utf-8")).get("sourceComponents", -1)) if args.graph.with_suffix(".json").exists() else None,
            "simulationComponentsAfterVirtualSprings": int(json.loads(args.graph.with_suffix(".json").read_text(encoding="utf-8")).get("simulationComponentsAfterVirtualSprings", -1)) if args.graph.with_suffix(".json").exists() else None,
        },
        "inputAuditPass": bool(
            len(capture_landmarks) == 121
            and capture_landmarks.shape[1:] == (478, 3)
            and int(capture_valid.sum()) == 121
            and len(table_rows) == 121
            and table_landmarks.shape[1:] == (478, 2)
            and target_array.shape == (121, 478, 3)
            and len(triangles) == 478
            and valid_triangles
            and np.isfinite(bary).all()
            and np.max(np.abs(bary_sums - 1.0)) <= 1e-10
            and np.isfinite(neutral_error).all()
            and neutral_error.max() <= 1e-10
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"model": args.model, "inputAuditPass": output["inputAuditPass"], "frames": output["targets"]["frames"], "landmarks": output["targets"]["landmarks"], "neutralMaxError": output["correspondence"]["neutralReconstructionMaxError"]}))


if __name__ == "__main__":
    main()
