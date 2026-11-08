"""Audit reference-video coefficients against temporary CaptureForge rigs.

The source GLBs, Goal 1 records, rig implementation, and stored motion data are
not modified. Each character is imported into a fresh Blender scene, copied,
bound with the existing CaptureForge weights, and driven only on the temporary
copy. The coefficient-to-bone table is explicit so the audit can report where
motion is lost rather than silently optimizing the rig.
"""
import csv
import json
import sys
import time
from collections import defaultdict
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
from captureforge.face import autofit

OUT = ROOT / "verification/captureforge-facial-rig-test/video-motion-audit"
COEFF_NPZ = ROOT / "verification/captureforge-facial-rig-test/worried-reference.capture.npz"
MOTION = ROOT / "verification/goal2-browInnerUp-proof/worried-expression-table.json"
CASES = {
    "female": {
        "glb": ROOT / "assets/tripo/vela-photoreal/generated-original.glb",
        "goal1": ROOT / "verification/goal1-generalization-run/cross-character-accuracy/female/refined/raycast-report.json",
    },
    "male": {
        "glb": ROOT / "assets/tripo/generalization-male-20261105/generated-original.glb",
        "goal1": ROOT / "verification/goal1-generalization-run/cross-character-accuracy/male/refined/raycast-report.json",
    },
}

# This is an audit mapping, not a rig correction. 0.25 rad is the same fixed
# command scale used by the earlier controlled CaptureForge test. No character
# or landmark-specific values are used.
COMMAND_SCALE_RAD = 0.25
COMMAND_AXIS = 0

REGIONS = {
    "eyebrows": [70, 63, 105, 336, 293, 334, 107, 300, 65, 52, 53, 46, 285, 295, 282, 283, 276],
    "eyelids": [33, 133, 159, 145, 160, 144, 153, 154, 155, 263, 362, 386, 374, 385, 380, 373, 390, 249],
    "cheeks": [50, 101, 118, 123, 187, 205, 36, 206, 216, 215, 214, 280, 330, 347, 352, 411, 425, 266, 426, 436, 435, 434],
    "lips": [0, 13, 14, 17, 39, 61, 84, 87, 88, 91, 95, 146, 178, 181, 269, 291, 308, 314, 317, 318, 321, 324, 375, 402, 405],
    "mouth_corners": [61, 291, 40, 270, 185, 409],
    "jaw": [152, 148, 176, 149, 150, 136, 365, 377, 400, 378, 379, 394, 172, 132, 361],
}


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
    # Read only the requested evaluated vertices. The original Tripo objects
    # approach one million vertices; pulling the entire evaluated mesh for
    # every video frame needlessly exhausts memory during an audit.
    a = np.asarray([eo.data.vertices[int(i)].co[:] for i in indices], dtype=float)
    M = np.asarray(eo.matrix_world, float)
    return a @ M[:3, :3].T + M[:3, 3]


def add_cmd(cmd, bone, value):
    cmd[bone] += float(value)


def coefficient_commands(names, values):
    """Map semantic MediaPipe coefficients to existing FaceForge bones."""
    c = dict(zip(names, map(float, values)))
    cmd = defaultdict(float)
    # Brow controls. CaptureForge's earlier controlled test established local X
    # positive as the common anatomical-up response for these bones.
    inner = c.get("browInnerUp", 0.0)
    add_cmd(cmd, "brow.mid.L", COMMAND_SCALE_RAD * inner)
    add_cmd(cmd, "brow.mid.R", COMMAND_SCALE_RAD * inner)
    add_cmd(cmd, "brow.out.L", COMMAND_SCALE_RAD * c.get("browOuterUpLeft", 0.0))
    add_cmd(cmd, "brow.out.R", COMMAND_SCALE_RAD * c.get("browOuterUpRight", 0.0))
    for side, key in (("L", "browDownLeft"), ("R", "browDownRight")):
        down = c.get(key, 0.0)
        for part in ("in", "mid", "out"):
            add_cmd(cmd, f"brow.{part}.{side}", -COMMAND_SCALE_RAD * down)

    # Eyelids, cheeks, lips, mouth corners, and jaw use the existing named
    # controls. These are direct semantic commands for diagnosis, not fitted
    # coefficients or new weights.
    for side, key in (("L", "eyeBlinkLeft"), ("R", "eyeBlinkRight")):
        blink = c.get(key, 0.0)
        add_cmd(cmd, f"lid.T.{side}", COMMAND_SCALE_RAD * blink)
        add_cmd(cmd, f"lid.B.{side}", -COMMAND_SCALE_RAD * blink)
    for side, key in (("L", "cheekSquintLeft"), ("R", "cheekSquintRight")):
        add_cmd(cmd, f"cheek.{side}", COMMAND_SCALE_RAD * c.get(key, 0.0))
    for side, smile, frown in (("L", "mouthSmileLeft", "mouthFrownLeft"), ("R", "mouthSmileRight", "mouthFrownRight")):
        add_cmd(cmd, f"mouth.corner.{side}", COMMAND_SCALE_RAD * (c.get(smile, 0.0) - c.get(frown, 0.0)))
    add_cmd(cmd, "lip.T", COMMAND_SCALE_RAD * (c.get("mouthUpperUpLeft", 0.0) + c.get("mouthUpperUpRight", 0.0)) / 2)
    add_cmd(cmd, "lip.B", -COMMAND_SCALE_RAD * (c.get("mouthLowerDownLeft", 0.0) + c.get("mouthLowerDownRight", 0.0)) / 2)
    add_cmd(cmd, "jaw", COMMAND_SCALE_RAD * c.get("jawOpen", 0.0))
    return {k: v for k, v in cmd.items() if abs(v) > 1e-12}


def apply_commands(rig, commands):
    for b in rig.pose.bones:
        b.rotation_mode = "XYZ"
        b.rotation_euler = (0.0, 0.0, 0.0)
    for name, angle in commands.items():
        if rig.pose.bones.get(name):
            rig.pose.bones[name].rotation_mode = "XYZ"
            rig.pose.bones[name].rotation_euler[COMMAND_AXIS] = angle


def vertex_group_weights(obj, vertex_ids, bone_names):
    group_by_index = {g.index: g.name for g in obj.vertex_groups if g.name in bone_names}
    result = {}
    for vid in vertex_ids:
        result[str(vid)] = {}
        for g in obj.data.vertices[int(vid)].groups:
            if g.group in group_by_index:
                result[str(vid)][group_by_index[g.group]] = float(g.weight)
    return result


def region_for_ids(points, vertices, ids, radius):
    d = np.full(len(vertices), np.inf, dtype=float)
    for i in ids:
        d = np.minimum(d, np.linalg.norm(vertices - points[i], axis=1))
    return d <= radius


def run(label, cfg, coeff_names, coeff_values, times, motion_rows):
    started = time.perf_counter()
    out = OUT / label
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
    deps = bpy.context.evaluated_depsgraph_get()
    bvh = BVHTree.FromObject(body, deps)
    mapped, attachments, distances = {}, {}, []
    for i, r in src_ids.items():
        q = bvh.find_nearest(Vector(np.asarray(r["meshXYZ"], float) + source_translation))
        if q is None:
            continue
        loc, _normal, poly_index, dist = q
        poly = body.data.polygons[int(poly_index)]
        if len(poly.vertices) != 3:
            continue
        tri = [int(x) for x in poly.vertices]
        p = np.asarray(loc, float)
        mapped[i] = p
        attachments[i] = {"triangleVertexIndices": tri, "barycentricCoordinates": barycentric(p, target_world[tri[0]], target_world[tri[1]], target_world[tri[2]])}
        distances.append(float(dist))
    if len(mapped) < 468:
        raise RuntimeError(f"{label}: expected at least 468 mapped landmarks, got {len(mapped)}")

    c, R = frame({i: mapped[i] for i in [10, 33, 152, 263]})
    neutral_mesh = canon(target_world, c, R)
    work = body.copy()
    work.data = body.data.copy()
    work.name = f"{label}_CaptureForgeVideoAuditCopy"
    body.users_collection[0].objects.link(work)
    for i, v in enumerate(work.data.vertices):
        v.co = Vector(neutral_mesh[i])
    work.location = (0, 0, 0)
    work.rotation_euler = (0, 0, 0)
    work.scale = (1, 1, 1)
    work.parent = None
    P = {name: Vector(canon(mapped[idx], c, R)) for name, idx in autofit.LANDMARKS.items()}
    rig = autofit.build_faceforge_rig(P, work, (), name=f"{label}_CaptureForgeVideoAuditRig")
    g = autofit.face_geometry(P, work, ())
    specs = autofit.bone_specs(P, g)
    weights = autofit.skin_weights(neutral_mesh, specs, g)
    autofit._bind(work, rig, weights)
    attach_vertex_ids = sorted(set(v for i in range(468) for v in attachments[i]["triangleVertexIndices"]))
    neutral_check_ids = sorted(set(attach_vertex_ids))
    neutral_eval = eval_subset(work, neutral_check_ids)
    # The temporary copy is canonicalized, so this verifies the neutral rig path.
    neutral_error = float(np.max(np.linalg.norm(neutral_eval - neutral_mesh[neutral_check_ids], axis=1)))
    ew = float(np.linalg.norm(canon(mapped[33], c, R) - canon(mapped[263], c, R)))

    used_ids = sorted(set(i for ids in REGIONS.values() for i in ids))
    landmark_neutral = {i: canon(mapped[i], c, R) for i in range(468)}
    region_mask = region_for_ids(landmark_neutral, neutral_mesh, used_ids, 1.5 * ew)
    region_triangles = np.asarray([[int(v) for v in f.vertices] for f in work.data.polygons if len(f.vertices) == 3 and region_mask[[int(v) for v in f.vertices]].all()], dtype=np.int64)
    region_vertices = np.unique(region_triangles.reshape(-1)) if len(region_triangles) else np.array([], dtype=np.int64)
    region_lookup = {int(v): j for j, v in enumerate(region_vertices)}
    local_triangles = np.asarray([[region_lookup[int(v)] for v in tri] for tri in region_triangles], dtype=np.int64)
    neutral_region = neutral_mesh[region_vertices]
    e0 = np.concatenate([np.linalg.norm(neutral_region[local_triangles[:, 1]] - neutral_region[local_triangles[:, 0]], axis=1), np.linalg.norm(neutral_region[local_triangles[:, 2]] - neutral_region[local_triangles[:, 1]], axis=1), np.linalg.norm(neutral_region[local_triangles[:, 0]] - neutral_region[local_triangles[:, 2]], axis=1)]) if len(local_triangles) else np.array([])
    a0 = np.linalg.norm(np.cross(neutral_region[local_triangles[:, 1]] - neutral_region[local_triangles[:, 0]], neutral_region[local_triangles[:, 2]] - neutral_region[local_triangles[:, 0]]), axis=1) if len(local_triangles) else np.array([])

    bone_names = [b.name for b in rig.data.bones]
    brow_bones = [n for n in bone_names if n.startswith("brow.")]
    weight_audit = {
        "bone_group_counts": {n: int(np.sum(weights.get(n, np.zeros(len(neutral_mesh))) > 1e-6)) for n in bone_names},
        "landmark_attachment_weights": vertex_group_weights(work, attach_vertex_ids, bone_names),
    }
    (out / "skin-weights.json").write_text(json.dumps(weight_audit, indent=2), encoding="utf-8")

    expected_base = {i: landmark_neutral[i].copy() for i in range(468)}
    rows = []
    region_summary = defaultdict(lambda: {"errors": [], "expected_norm": [], "actual_norm": [], "frames": 0})
    geometry_rows = []
    command_rows = []
    peak_frame = int(json.loads(MOTION.read_text(encoding="utf-8"))["peakByBrowMotion"])
    peak_actual = None
    peak_expected = None
    peak_commands = None
    peak_transforms = None
    for frame_index, (coeff_row, motion_row) in enumerate(zip(coeff_values, motion_rows)):
        commands = coefficient_commands(coeff_names, coeff_row)
        apply_commands(rig, commands)
        actual_subset = eval_subset(work, attach_vertex_ids)
        actual_by_vertex = {int(v): actual_subset[j] for j, v in enumerate(attach_vertex_ids)}
        actual_landmarks = {}
        expected_landmarks = {}
        for i in range(468):
            tri = attachments[i]["triangleVertexIndices"]
            w = np.asarray(attachments[i]["barycentricCoordinates"], float)
            actual_landmarks[i] = sum(w[k] * actual_by_vertex[tri[k]] for k in range(3))
            dx, dy = map(float, motion_row["landmarks"][i][:2])
            expected_landmarks[i] = expected_base[i] + np.array([dx * ew, 0.0, dy * ew])
            actual_move = actual_landmarks[i] - expected_base[i]
            expected_move = expected_landmarks[i] - expected_base[i]
            error = float(np.linalg.norm(actual_move - expected_move) / max(ew, 1e-12))
            record = {"frame": frame_index, "time": float(times[frame_index]), "landmark_id": i, "region": next((n for n, ids in REGIONS.items() if i in ids), "other"), "expected_dx_norm": dx, "expected_dy_norm": dy, "actual_dx_norm": float(actual_move[0] / ew), "actual_dy_norm": float(actual_move[2] / ew), "expected_position": expected_landmarks[i].tolist(), "actual_position": actual_landmarks[i].tolist(), "error_norm": error, "actual_magnitude_norm": float(np.linalg.norm(actual_move) / ew), "expected_magnitude_norm": float(np.linalg.norm(expected_move) / ew)}
            rows.append(record)
            region = record["region"]
            region_summary[region]["errors"].append(error)
            region_summary[region]["expected_norm"].append(record["expected_magnitude_norm"])
            region_summary[region]["actual_norm"].append(record["actual_magnitude_norm"])
            region_summary[region]["frames"] += 1
        command_rows.append({"frame": frame_index, "time": float(times[frame_index]), "commands_rad": commands, "coefficients": {n: float(v) for n, v in zip(coeff_names, coeff_row)}})
        # Geometry checks are sampled through the sequence, while landmark
        # positions are measured on all 121 frames.
        if len(region_vertices) and (frame_index in (0, peak_frame) or frame_index % 10 == 0):
            rv = eval_subset(work, region_vertices)
            e1 = np.concatenate([np.linalg.norm(rv[local_triangles[:, 1]] - rv[local_triangles[:, 0]], axis=1), np.linalg.norm(rv[local_triangles[:, 2]] - rv[local_triangles[:, 1]], axis=1), np.linalg.norm(rv[local_triangles[:, 0]] - rv[local_triangles[:, 2]], axis=1)])
            a1 = np.linalg.norm(np.cross(rv[local_triangles[:, 1]] - rv[local_triangles[:, 0]], rv[local_triangles[:, 2]] - rv[local_triangles[:, 0]]), axis=1)
            strain = np.abs(e1 / np.maximum(e0, 1e-12) - 1.0)
            geometry_rows.append({"frame": frame_index, "max_edge_strain": float(np.max(strain)), "p95_edge_strain": float(np.percentile(strain, 95)), "min_area_ratio": float(np.min(a1 / np.maximum(a0, 1e-12))), "collapsed_triangles": int(np.sum(a1 <= 0.1 * np.maximum(a0, 1e-12))), "invalid_coordinates": int(np.sum(~np.isfinite(rv)))})
        if frame_index == peak_frame:
            peak_actual, peak_expected, peak_commands = actual_landmarks, expected_landmarks, commands
            peak_transforms = [{"name": b.name, "rotation_euler": list(map(float, b.rotation_euler)), "matrix_translation": list(map(float, b.matrix.translation))} for b in rig.pose.bones]

    with (out / "landmark-frame-measurements.csv").open("w", newline="", encoding="utf-8") as f:
        fields = list(rows[0].keys())
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in rows:
            w.writerow(row)
    (out / "bone-commands.json").write_text(json.dumps(command_rows, indent=2), encoding="utf-8")
    (out / "peak-bone-transforms.json").write_text(json.dumps(peak_transforms, indent=2), encoding="utf-8")

    for region, value in region_summary.items():
        errors = value.pop("errors")
        expected_values = value.pop("expected_norm")
        actual_values = value.pop("actual_norm")
        value["mean_error_norm"] = float(np.mean(errors))
        value["p95_error_norm"] = float(np.percentile(errors, 95))
        value["mean_expected_magnitude_norm"] = float(np.mean(expected_values))
        value["mean_actual_magnitude_norm"] = float(np.mean(actual_values))
    geometry_peak = next((x for x in geometry_rows if x["frame"] == peak_frame), {})
    fp = np.asarray([landmark_neutral[i] for i in range(468)])
    scale = max(float(np.ptp(fp[:, 0])), float(np.ptp(fp[:, 2]))) * 1.6
    cam = {"cx": float((fp[:, 0].min() + fp[:, 0].max()) / 2), "cz": float((fp[:, 2].min() + fp[:, 2].max()) / 2), "scale": scale, "y": float(fp[:, 1].min() - scale), "depth": float(np.ptp(fp[:, 1]))}
    apply_commands(rig, {})
    autofit.render_front(bpy.context.scene, [work], str(out / "neutral.png"), cam, size=768, color_type="TEXTURE")
    apply_commands(rig, command_rows[peak_frame]["commands_rad"])
    autofit.render_front(bpy.context.scene, [work], str(out / "peak.png"), cam, size=768, color_type="TEXTURE")

    summary = {
        "status": "COMPLETE",
        "character": label,
        "source_glb": str(cfg["glb"]),
        "goal1_source": goal.get("sourceGLB"),
        "coefficient_source": str(COEFF_NPZ),
        "coefficient_count": len(coeff_names),
        "frame_count": len(coeff_values),
        "mapped_landmarks": len(mapped),
        "surface_distance_median": float(np.median(distances)),
        "source_translation": source_translation.tolist(),
        "eye_width": ew,
        "rig_bones": len(rig.data.bones),
        "command_axis": "pose-bone local Euler X",
        "command_scale_radians": COMMAND_SCALE_RAD,
        "neutral_reconstruction_max_error": neutral_error,
        "attachment_vertex_count": len(attach_vertex_ids),
        "audit_region_vertex_count": len(region_vertices),
        "audit_region_triangle_count": len(region_triangles),
        "peak_frame": peak_frame,
        "peak_commands_rad": peak_commands,
        "peak_bone_transforms": peak_transforms,
        "regions": REGIONS,
        "region_metrics": dict(region_summary),
        "geometry_at_peak": geometry_peak,
        "geometry_over_sequence": {"max_edge_strain": float(max(x["max_edge_strain"] for x in geometry_rows)), "min_area_ratio": float(min(x["min_area_ratio"] for x in geometry_rows)), "collapsed_triangles_total_frames": int(sum(x["collapsed_triangles"] for x in geometry_rows)), "invalid_coordinate_total_frames": int(sum(x["invalid_coordinates"] for x in geometry_rows))} if geometry_rows else {},
        "neutral_render": str(out / "neutral.png"),
        "peak_render": str(out / "peak.png"),
        "runtime_seconds": time.perf_counter() - started,
        "visual_expression_pass": False,
    }
    (out / "result.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    z = np.load(COEFF_NPZ, allow_pickle=True)
    coeff_names = [str(x) for x in z["names"].tolist()]
    coeff_values = np.asarray(z["scores"], float)
    times = np.asarray(z["times"], float)
    motion_rows = json.loads(MOTION.read_text(encoding="utf-8"))["rows"]
    if len(coeff_values) != len(motion_rows):
        raise RuntimeError(f"Coefficient frames {len(coeff_values)} != motion frames {len(motion_rows)}")
    for label, cfg in CASES.items():
        run(label, cfg, coeff_names, coeff_values, times, motion_rows)
