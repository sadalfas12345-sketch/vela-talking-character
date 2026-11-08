"""Replay bounded control fits on temporary original-mesh rigs and measure Blender output."""
import csv
import json
import sys
import time
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

ROOT = Path(r"C:\Users\USER\talking-character-demo")
CAPTUREFORGE = r"C:\Users\USER\captureforge"
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, CAPTUREFORGE)
import diagnose_captureforge_corrected_setup as base
import measure_captureforge_control_response as measured
from captureforge.face import autofit

CAL = ROOT / "verification/captureforge-facial-rig-test/control-calibration"
MOTION = ROOT / "verification/goal2-browInnerUp-proof/worried-expression-table.json"
COEFF = ROOT / "verification/captureforge-facial-rig-test/worried-reference.capture.npz"
REGIONS = {
    "eyebrows": [70, 63, 105, 336, 293, 334, 107, 300, 65, 52, 53, 46, 285, 295, 282, 283, 276],
    "eyelids": [33, 133, 159, 145, 160, 144, 153, 154, 155, 263, 362, 386, 374, 385, 380, 373, 390, 249],
    "cheeks": [50, 101, 118, 123, 187, 205, 36, 206, 216, 215, 214, 280, 330, 347, 352, 411, 425, 266, 426, 436, 435, 434],
    "lips": [0, 13, 14, 17, 39, 61, 84, 87, 88, 91, 95, 146, 178, 181, 269, 291, 308, 314, 317, 318, 321, 324, 375, 402, 405],
    "mouth_corners": [61, 291, 40, 270, 185, 409],
    "jaw": [152, 148, 176, 149, 150, 136, 365, 377, 400, 378, 379, 394, 172, 132, 361],
}
MAX_STRAIN_TRIANGLES = 20000
LANDMARK_COUNT = 478


def records(path):
    d = json.loads(path.read_text(encoding="utf-8"))
    return d, {int(r["index"]): r for r in d["records"] if r.get("meshXYZ")}


def world_vertices(obj):
    M = np.asarray(obj.matrix_world, float)
    a = np.empty(len(obj.data.vertices) * 3, float)
    obj.data.vertices.foreach_get("co", a)
    return a.reshape(-1, 3) @ M[:3, :3].T + M[:3, 3]


def import_main(path):
    bpy.ops.import_scene.gltf(filepath=str(path))
    return max((o for o in bpy.context.scene.objects if o.type == "MESH"), key=lambda o: len(o.data.vertices))


def barycentric(p, a, b, c):
    v0, v1, v2 = b - a, c - a, p - a
    d00, d01, d11 = np.dot(v0, v0), np.dot(v0, v1), np.dot(v1, v1)
    d20, d21 = np.dot(v2, v0), np.dot(v2, v1)
    den = d00 * d11 - d01 * d01
    if abs(den) < 1e-15:
        return np.array([1.0, 0.0, 0.0])
    v, w = (d11 * d20 - d01 * d21) / den, (d00 * d21 - d01 * d20) / den
    return np.array([1.0 - v - w, v, w])


def frame(p):
    center = (p[33] + p[263]) / 2
    right = p[263] - p[33]
    right /= np.linalg.norm(right)
    up = p[10] - p[152]
    up -= right * np.dot(up, right)
    up /= np.linalg.norm(up)
    outward = np.cross(right, up)
    outward /= np.linalg.norm(outward)
    return center, np.stack([right, -outward, up], axis=0)


def canon(x, c, R):
    return (np.asarray(x) - c) @ R.T


def eval_subset(obj, indices):
    deps = bpy.context.evaluated_depsgraph_get()
    deps.update()
    eo = obj.evaluated_get(deps)
    a = np.asarray([eo.data.vertices[int(i)].co[:] for i in indices], dtype=float)
    M = np.asarray(eo.matrix_world, float)
    return a @ M[:3, :3].T + M[:3, 3]


def apply_controls(rig, dofs, values):
    for b in rig.pose.bones:
        b.rotation_mode = "XYZ"
        b.location = (0, 0, 0)
        b.rotation_euler = (0, 0, 0)
    for d, value in zip(dofs, values):
        b = rig.pose.bones[d["bone"]]
        if d["kind"] == "translation":
            b.location[d["axis"]] = float(value)
        else:
            b.rotation_euler[d["axis"]] = float(value)


def geometry(coords, neutral, triangles):
    if len(triangles) == 0:
        return {"max_edge_strain": 0.0, "p95_edge_strain": 0.0, "min_area_ratio": 1.0, "collapsed_triangles": 0, "invalid_coordinates": int(np.sum(~np.isfinite(coords)))}
    e0 = np.concatenate([np.linalg.norm(neutral[triangles[:, 1]] - neutral[triangles[:, 0]], axis=1), np.linalg.norm(neutral[triangles[:, 2]] - neutral[triangles[:, 1]], axis=1), np.linalg.norm(neutral[triangles[:, 0]] - neutral[triangles[:, 2]], axis=1)])
    e1 = np.concatenate([np.linalg.norm(coords[triangles[:, 1]] - coords[triangles[:, 0]], axis=1), np.linalg.norm(coords[triangles[:, 2]] - coords[triangles[:, 1]], axis=1), np.linalg.norm(coords[triangles[:, 0]] - coords[triangles[:, 2]], axis=1)])
    a0 = np.linalg.norm(np.cross(neutral[triangles[:, 1]] - neutral[triangles[:, 0]], neutral[triangles[:, 2]] - neutral[triangles[:, 0]]), axis=1)
    a1 = np.linalg.norm(np.cross(coords[triangles[:, 1]] - coords[triangles[:, 0]], coords[triangles[:, 2]] - coords[triangles[:, 0]]), axis=1)
    ratio = a1 / np.maximum(a0, 1e-12)
    strain = np.abs(e1 / np.maximum(e0, 1e-12) - 1)
    return {"max_edge_strain": float(np.max(strain)), "p95_edge_strain": float(np.percentile(strain, 95)), "min_area_ratio": float(np.min(ratio)), "collapsed_triangles": int(np.sum(ratio <= 0.1)), "invalid_coordinates": int(np.sum(~np.isfinite(coords)))}


def run(label, cfg):
    started = time.perf_counter()
    src = CAL / label
    fit = json.loads((src / "fit-controls.json").read_text(encoding="utf-8"))
    motion = json.loads(MOTION.read_text(encoding="utf-8"))["rows"]
    coeff = np.load(COEFF, allow_pickle=True)
    coeff_names = [str(x) for x in coeff["names"].tolist()]
    coeff_values = np.asarray(coeff["scores"], float)
    out = src / "validation"
    out.mkdir(parents=True, exist_ok=True)
    goal, src_ids = records(cfg["goal1"])
    bpy.ops.wm.read_factory_settings(use_empty=True)
    source_path = Path(goal.get("sourceGLB", ""))
    if not source_path.exists():
        source_path = Path(cfg["glb"])
    source_center = np.zeros(3)
    if source_path.resolve() != Path(cfg["glb"]).resolve():
        source_body = import_main(source_path)
        sv = world_vertices(source_body)
        source_center = (sv.min(0) + sv.max(0)) / 2
        bpy.ops.wm.read_factory_settings(use_empty=True)
    body = import_main(cfg["glb"])
    target_world = world_vertices(body)
    target_center = (target_world.min(0) + target_world.max(0)) / 2
    source_translation = target_center - source_center if source_path.resolve() != Path(cfg["glb"]).resolve() else np.zeros(3)
    bvh = BVHTree.FromObject(body, bpy.context.evaluated_depsgraph_get())
    mapped, attachments, distances = {}, {}, []
    for i, r in src_ids.items():
        q = bvh.find_nearest(Vector(np.asarray(r["meshXYZ"], float) + source_translation))
        if q is None:
            continue
        loc, _normal, poly_index, dist = q
        poly = body.data.polygons[int(poly_index)]
        if len(poly.vertices) != 3:
            continue
        tri = [int(v) for v in poly.vertices]
        p = np.asarray(loc, float)
        mapped[i] = p
        attachments[i] = {"triangleVertexIndices": tri, "barycentricCoordinates": barycentric(p, target_world[tri[0]], target_world[tri[1]], target_world[tri[2]])}
        distances.append(float(dist))
    c, R = frame({i: mapped[i] for i in [10, 33, 152, 263]})
    neutral_mesh = canon(target_world, c, R)
    neutral_points = np.asarray([canon(mapped[i], c, R) for i in range(LANDMARK_COUNT)])
    work = body.copy()
    work.data = body.data.copy()
    work.name = f"{label}_CaptureForgeFitValidationCopy"
    body.users_collection[0].objects.link(work)
    for i, v in enumerate(work.data.vertices):
        v.co = Vector(neutral_mesh[i])
    work.location = (0, 0, 0)
    work.rotation_euler = (0, 0, 0)
    work.scale = (1, 1, 1)
    work.parent = None
    P = {name: Vector(canon(mapped[idx], c, R)) for name, idx in autofit.LANDMARKS.items()}
    rig = autofit.build_faceforge_rig(P, work, (), name=f"{label}_CaptureForgeFitValidationRig")
    g = autofit.face_geometry(P, work, ())
    weights = autofit.skin_weights(neutral_mesh, autofit.bone_specs(P, g), g)
    autofit._bind(work, rig, weights)
    dofs = fit["dofs"]
    attach_vertices = sorted(set(v for i in range(LANDMARK_COUNT) for v in attachments[i]["triangleVertexIndices"]))
    polys = np.asarray([[int(v) for v in f.vertices] for f in work.data.polygons if len(f.vertices) == 3], dtype=np.int64)
    ew = float(np.linalg.norm(neutral_points[33] - neutral_points[263]))
    used_ids = sorted(set(i for ids in REGIONS.values() for i in ids))
    region_mask = np.full(len(neutral_mesh), False)
    for i in used_ids:
        region_mask |= np.linalg.norm(neutral_mesh - neutral_points[i], axis=1) <= 1.5 * ew
    region_tri = np.flatnonzero(np.all(region_mask[polys], axis=1))
    if len(region_tri) > MAX_STRAIN_TRIANGLES:
        region_tri = np.linspace(0, len(region_tri) - 1, MAX_STRAIN_TRIANGLES, dtype=np.int64)
    triangles = polys[region_tri]
    region_vertices = np.unique(triangles.reshape(-1)) if len(triangles) else np.array([], dtype=np.int64)
    lookup = {int(v): j for j, v in enumerate(region_vertices)}
    local_triangles = np.asarray([[lookup[int(v)] for v in tri] for tri in triangles], dtype=np.int64)
    neutral_region = neutral_mesh[region_vertices]
    actual_rows = []
    predicted_sequence = np.load(src / "fit-predicted.npz")["predicted"]
    region_data = {name: {"expected": [], "predicted": [], "actual": [], "error_pred": [], "error_actual": []} for name in list(REGIONS) + ["other"]}
    geometry_rows = []
    for f, row in enumerate(motion):
        values = fit["frames"][f]["controls"]
        apply_controls(rig, dofs, values)
        pos = eval_subset(work, attach_vertices)
        by_vertex = {int(v): pos[k] for k, v in enumerate(attach_vertices)}
        actual = np.empty((LANDMARK_COUNT, 3), float)
        for i in range(LANDMARK_COUNT):
            tri = attachments[i]["triangleVertexIndices"]
            w = attachments[i]["barycentricCoordinates"]
            actual[i] = sum(w[k] * by_vertex[tri[k]] for k in range(3)) - neutral_points[i]
        dxdy = np.asarray([[float(x[0]), float(x[1])] for x in row["landmarks"][:LANDMARK_COUNT]], float)
        expected = np.zeros((LANDMARK_COUNT, 3), float)
        expected[:, 0] = dxdy[:, 0] * ew
        expected[:, 2] = dxdy[:, 1] * ew
        predicted = predicted_sequence[f]
        for i in range(LANDMARK_COUNT):
            name = next((n for n, ids in REGIONS.items() if i in ids), "other")
            actual_rows.append({"frame": f, "time": float(row["timeSeconds"]), "landmark_id": i, "region": name, "expected_dx_norm": float(expected[i, 0] / ew), "expected_dy_norm": float(expected[i, 2] / ew), "predicted_dx_norm": float(predicted[i, 0] / ew), "predicted_dy_norm": float(predicted[i, 2] / ew), "actual_dx_norm": float(actual[i, 0] / ew), "actual_dy_norm": float(actual[i, 2] / ew), "predicted_error_norm": float(np.linalg.norm(predicted[i] - expected[i]) / ew), "actual_error_norm": float(np.linalg.norm(actual[i] - expected[i]) / ew)})
            region_data[name]["expected"].append(expected[i]); region_data[name]["predicted"].append(predicted[i]); region_data[name]["actual"].append(actual[i]); region_data[name]["error_pred"].append(np.linalg.norm(predicted[i] - expected[i]) / ew); region_data[name]["error_actual"].append(np.linalg.norm(actual[i] - expected[i]) / ew)
        if f == 0 or f % 10 == 0:
            rv = eval_subset(work, region_vertices)
            geometry_rows.append({"frame": f, **geometry(rv, neutral_region, local_triangles)})
    with (out / "actual-frame-measurements.csv").open("w", newline="", encoding="utf-8") as fh:
        fields = list(actual_rows[0].keys()); writer = csv.DictWriter(fh, fieldnames=fields); writer.writeheader(); writer.writerows(actual_rows)
    summaries = {}
    for name, d in region_data.items():
        if not d["expected"]:
            continue
        expected = np.asarray(d["expected"]); predicted = np.asarray(d["predicted"]); actual = np.asarray(d["actual"])
        summaries[name] = {"landmark_count": int(len(REGIONS.get(name, []))), "mean_expected_magnitude_norm": float(np.mean(np.linalg.norm(expected, axis=1) / ew)), "mean_predicted_magnitude_norm": float(np.mean(np.linalg.norm(predicted, axis=1) / ew)), "mean_actual_magnitude_norm": float(np.mean(np.linalg.norm(actual, axis=1) / ew)), "predicted_mean_error_norm": float(np.mean(d["error_pred"])), "predicted_p95_error_norm": float(np.percentile(d["error_pred"], 95)), "actual_mean_error_norm": float(np.mean(d["error_actual"])), "actual_p95_error_norm": float(np.percentile(d["error_actual"], 95))}
    coeff_peak = {name: int(np.argmax(coeff_values[:, i])) for i, name in enumerate(coeff_names) if name in {"browInnerUp", "eyeBlinkLeft", "jawOpen", "mouthSmileLeft"}}
    render_frames = {"neutral": -1, **{name: frame for name, frame in coeff_peak.items()}}
    fp = neutral_points
    cam_scale = max(float(np.ptp(fp[:, 0])), float(np.ptp(fp[:, 2]))) * 1.6
    cam = {"cx": float((fp[:, 0].min() + fp[:, 0].max()) / 2), "cz": float((fp[:, 2].min() + fp[:, 2].max()) / 2), "scale": cam_scale, "y": float(fp[:, 1].min() - cam_scale), "depth": float(np.ptp(fp[:, 1]))}
    for name, f in render_frames.items():
        if f < 0:
            apply_controls(rig, dofs, np.zeros(len(dofs)))
        else:
            apply_controls(rig, dofs, fit["frames"][f]["controls"])
        autofit.render_front(bpy.context.scene, [work], str(out / f"{name}.png"), cam, size=768, color_type="TEXTURE")
    report = {"character": label, "status": "COMPLETE", "frames": len(motion), "dofs": len(dofs), "mapped_landmarks": len(mapped), "eye_width": ew, "region_metrics": summaries, "geometry_sampled_frames": geometry_rows, "geometry_summary": {"max_edge_strain": float(max(x["max_edge_strain"] for x in geometry_rows)), "p95_edge_strain_max": float(max(x["p95_edge_strain"] for x in geometry_rows)), "min_area_ratio": float(min(x["min_area_ratio"] for x in geometry_rows)), "collapsed_triangles": int(sum(x["collapsed_triangles"] for x in geometry_rows)), "invalid_coordinates": int(sum(x["invalid_coordinates"] for x in geometry_rows))}, "representative_frames": render_frames, "runtime_seconds": time.perf_counter() - started, "visual_expression_pass": False}
    (out / "validation-report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    cases = {
        "female": {"glb": ROOT / "assets/tripo/vela-photoreal/generated-original.glb", "goal1": ROOT / "verification/goal1-generalization-run/cross-character-accuracy/female/refined/raycast-report.json"},
        "male": {"glb": ROOT / "assets/tripo/generalization-male-20261105/generated-original.glb", "goal1": ROOT / "verification/goal1-generalization-run/cross-character-accuracy/male/refined/raycast-report.json"},
    }
    for label, cfg in cases.items():
        run(label, cfg)
