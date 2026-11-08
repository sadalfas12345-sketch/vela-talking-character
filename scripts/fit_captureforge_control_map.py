"""Fit the existing measured CaptureForge response map to video landmarks.

This is a bounded ridge least-squares calibration only. It predicts controls
from measured responses; Blender replay and actual surface measurements happen
in the separate validation script.
"""
import json
from pathlib import Path

import numpy as np
from scipy.optimize import lsq_linear

ROOT = Path(r"C:\Users\USER\talking-character-demo")
OUT = ROOT / "verification/captureforge-facial-rig-test/control-calibration"
MOTION = ROOT / "verification/goal2-browInnerUp-proof/worried-expression-table.json"
REGIONS = {
    "eyebrows": [70, 63, 105, 336, 293, 334, 107, 300, 65, 52, 53, 46, 285, 295, 282, 283, 276],
    "eyelids": [33, 133, 159, 145, 160, 144, 153, 154, 155, 263, 362, 386, 374, 385, 380, 373, 390, 249],
    "cheeks": [50, 101, 118, 123, 187, 205, 36, 206, 216, 215, 214, 280, 330, 347, 352, 411, 425, 266, 426, 436, 435, 434],
    "lips": [0, 13, 14, 17, 39, 61, 84, 87, 88, 91, 95, 146, 178, 181, 269, 291, 308, 314, 317, 318, 321, 324, 375, 402, 405],
    "mouth_corners": [61, 291, 40, 270, 185, 409],
    "jaw": [152, 148, 176, 149, 150, 136, 365, 377, 400, 378, 379, 394, 172, 132, 361],
}
LANDMARK_COUNT = 478


def fit_one(label):
    src = OUT / label
    z = np.load(src / "response-map.npz", allow_pickle=True)
    definition = json.loads((src / "control-definition.json").read_text(encoding="utf-8"))
    motion = json.loads(MOTION.read_text(encoding="utf-8"))["rows"]
    plus = z["response_small_plus"]
    minus = z["response_small_minus"]
    large = z["response_large_plus"]
    dof_names = [str(x) for x in z["dof_names"].tolist()]
    neutral = np.asarray(z["neutral_points"], float)
    ew = float(z["eye_width"][0])
    n_dof = len(dof_names)
    small = np.asarray(z["small_values"], float)
    limits = np.asarray([0.05 * ew if ".t" in name else 0.25 for name in dof_names], float)
    # The names use .t0/.r0 suffixes, so explicit metadata is safer than a
    # string heuristic when constructing transform limits.
    limits = np.asarray([0.05 * ew if d["kind"] == "translation" else 0.25 for d in definition["dofs"]], float)
    A = (plus - minus) / (2.0 * small[:, None, None])
    A = A.reshape(n_dof, -1).T
    B = A * limits[None, :]
    regularization = 1e-3
    augmented = np.vstack([B, np.sqrt(regularization) * np.eye(n_dof)])
    fit_rows = []
    predicted = np.zeros((len(motion), LANDMARK_COUNT, 3), float)
    for frame, row in enumerate(motion):
        dxdy = np.asarray([[float(v[0]), float(v[1])] for v in row["landmarks"][:LANDMARK_COUNT]], float)
        target = np.zeros((LANDMARK_COUNT, 3), float)
        target[:, 0] = dxdy[:, 0] * ew
        target[:, 2] = dxdy[:, 1] * ew
        b = target.reshape(-1)
        rhs = np.r_[b, np.zeros(n_dof)]
        result = lsq_linear(augmented, rhs, bounds=(-np.ones(n_dof), np.ones(n_dof)), method="trf", lsmr_tol="auto", verbose=0)
        controls = result.x * limits
        pred = (A @ controls).reshape(LANDMARK_COUNT, 3)
        predicted[frame] = pred
        fit_rows.append({"frame": frame, "time": float(row["timeSeconds"]), "controls": controls.tolist(), "normalized_controls": result.x.tolist(), "cost": float(result.cost), "optimality": float(result.optimality), "status": int(result.status), "message": result.message, "active_bounds": int(np.sum(np.isclose(np.abs(result.x), 1.0, atol=1e-5))), "linear_prediction_rms": float(np.sqrt(np.mean((pred - target) ** 2))), "linear_prediction_max": float(np.max(np.linalg.norm(pred - target, axis=1)))})
    np.savez_compressed(src / "fit-predicted.npz", predicted=predicted, target=predicted * 0.0, neutral=neutral, eye_width=np.asarray([ew]))
    (src / "fit-controls.json").write_text(json.dumps({"character": label, "dof_names": dof_names, "dofs": definition["dofs"], "limits": limits.tolist(), "regularization": regularization, "frames": fit_rows}, indent=2), encoding="utf-8")
    # Summaries of the measured response map and the linear prediction.
    linearity = []
    for j, name in enumerate(dof_names):
        small_response = A[:, j] * limits[j]
        large_response = large[j].reshape(-1)
        denominator = max(float(np.linalg.norm(small_response)), 1e-12)
        linearity.append({"dof": name, "large_command": float(definition["dofs"][j]["large"]), "small_linear_prediction_norm": float(np.linalg.norm(small_response)), "large_actual_norm": float(np.linalg.norm(large_response)), "gain_ratio": float(np.linalg.norm(large_response) / denominator), "cosine_to_linear": float(np.dot(large_response, small_response) / max(np.linalg.norm(large_response) * denominator, 1e-12))})
    (src / "control-linearity.json").write_text(json.dumps(linearity, indent=2), encoding="utf-8")
    region_summary = {}
    for name, ids in REGIONS.items():
        ids = np.asarray(ids, dtype=int)
        expected = np.zeros((len(motion), len(ids), 3), float)
        for f, row in enumerate(motion):
            v = np.asarray([[float(x[0]), 0.0, float(x[1])] for x in row["landmarks"][:LANDMARK_COUNT]], float)
            expected[f] = v[ids] * ew
        pred = predicted[:, ids]
        err = np.linalg.norm(pred - expected, axis=2) / ew
        region_summary[name] = {"landmark_count": int(len(ids)), "mean_error_norm": float(np.mean(err)), "p95_error_norm": float(np.percentile(err, 95)), "mean_expected_magnitude_norm": float(np.mean(np.linalg.norm(expected, axis=2) / ew)), "mean_predicted_magnitude_norm": float(np.mean(np.linalg.norm(pred, axis=2) / ew))}
    report = {"character": label, "frames": len(motion), "dofs": n_dof, "regularization": regularization, "limits": {"translation_eye_width_fraction": 0.05, "rotation_radians": 0.25}, "region_prediction_metrics": region_summary, "fit_rms_mean": float(np.mean([r["linear_prediction_rms"] for r in fit_rows])), "fit_max_error_norm_mean": float(np.mean([r["linear_prediction_max"] / ew for r in fit_rows])), "bounded_frames": int(sum(r["active_bounds"] > 0 for r in fit_rows))}
    (src / "fit-report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    for label in ("female", "male"):
        fit_one(label)
