"""Measure the local response of every existing CaptureForge facial control.

This script only operates on temporary copies of the original GLBs. It does not
change CaptureForge source, source meshes, Goal 1 records, or saved weights.
"""
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
from captureforge.face import autofit

OUT = ROOT / "verification/captureforge-facial-rig-test/control-calibration"
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

SMALL_ROT = 0.01
LARGE_ROT = 0.10
SMALL_TRANSLATION_EW = 0.001
LARGE_TRANSLATION_EW = 0.01
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


def reset_pose(rig):
    for b in rig.pose.bones:
        b.rotation_mode = "XYZ"
        b.location = (0.0, 0.0, 0.0)
        b.rotation_euler = (0.0, 0.0, 0.0)


def apply_dof(rig, bone_name, kind, axis, value):
    reset_pose(rig)
    b = rig.pose.bones[bone_name]
    if kind == "translation":
        b.location[axis] = value
    else:
        b.rotation_euler[axis] = value


def transform_record(b):
    return {
        "name": b.name,
        "location": list(map(float, b.location)),
        "rotation_euler": list(map(float, b.rotation_euler)),
        "matrix_translation": list(map(float, b.matrix.translation)),
    }


def response_for_landmarks(coords, attachments, neutral_points):
    out = np.empty((LANDMARK_COUNT, 3), float)
    for i in range(LANDMARK_COUNT):
        tri = attachments[i]["triangleVertexIndices"]
        w = attachments[i]["barycentricCoordinates"]
        out[i] = sum(w[k] * coords[tri[k]] for k in range(3)) - neutral_points[i]
    return out


def strain_measure(coords, neutral, triangles):
    if len(triangles) == 0:
        return {"max_edge_strain": 0.0, "p95_edge_strain": 0.0, "min_area_ratio": 1.0, "collapsed_triangles": 0, "invalid_coordinates": int(np.sum(~np.isfinite(coords)))}
    e0 = np.concatenate([
        np.linalg.norm(neutral[triangles[:, 1]] - neutral[triangles[:, 0]], axis=1),
        np.linalg.norm(neutral[triangles[:, 2]] - neutral[triangles[:, 1]], axis=1),
        np.linalg.norm(neutral[triangles[:, 0]] - neutral[triangles[:, 2]], axis=1),
    ])
    e1 = np.concatenate([
        np.linalg.norm(coords[triangles[:, 1]] - coords[triangles[:, 0]], axis=1),
        np.linalg.norm(coords[triangles[:, 2]] - coords[triangles[:, 1]], axis=1),
        np.linalg.norm(coords[triangles[:, 0]] - coords[triangles[:, 2]], axis=1),
    ])
    a0 = np.linalg.norm(np.cross(neutral[triangles[:, 1]] - neutral[triangles[:, 0]], neutral[triangles[:, 2]] - neutral[triangles[:, 0]]), axis=1)
    a1 = np.linalg.norm(np.cross(coords[triangles[:, 1]] - coords[triangles[:, 0]], coords[triangles[:, 2]] - coords[triangles[:, 0]]), axis=1)
    ratios = a1 / np.maximum(a0, 1e-12)
    strain = np.abs(e1 / np.maximum(e0, 1e-12) - 1.0)
    return {
        "max_edge_strain": float(np.max(strain)),
        "p95_edge_strain": float(np.percentile(strain, 95)),
        "min_area_ratio": float(np.min(ratios)),
        "collapsed_triangles": int(np.sum(ratios <= 0.1)),
        "invalid_coordinates": int(np.sum(~np.isfinite(coords))),
    }


def run(label, cfg):
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
    if len(mapped) < LANDMARK_COUNT:
        raise RuntimeError(f"{label}: only {len(mapped)} mapped Goal 1 points")
    c, R = frame({i: mapped[i] for i in [10, 33, 152, 263]})
    neutral_mesh = canon(target_world, c, R)
    neutral_points = np.asarray([canon(mapped[i], c, R) for i in range(LANDMARK_COUNT)])
    work = body.copy()
    work.data = body.data.copy()
    work.name = f"{label}_CaptureForgeControlCalibrationCopy"
    body.users_collection[0].objects.link(work)
    for i, v in enumerate(work.data.vertices):
        v.co = Vector(neutral_mesh[i])
    work.location = (0, 0, 0)
    work.rotation_euler = (0, 0, 0)
    work.scale = (1, 1, 1)
    work.parent = None
    P = {name: Vector(canon(mapped[idx], c, R)) for name, idx in autofit.LANDMARKS.items()}
    rig = autofit.build_faceforge_rig(P, work, (), name=f"{label}_CaptureForgeControlCalibrationRig")
    g = autofit.face_geometry(P, work, ())
    specs = autofit.bone_specs(P, g)
    weights = autofit.skin_weights(neutral_mesh, specs, g)
    autofit._bind(work, rig, weights)
    ew = float(np.linalg.norm(neutral_points[33] - neutral_points[263]))
    attachment_vertices = sorted(set(v for i in range(LANDMARK_COUNT) for v in attachments[i]["triangleVertexIndices"]))
    polys = np.asarray([[int(v) for v in f.vertices] for f in work.data.polygons if len(f.vertices) == 3], dtype=np.int64)
    face_mask = np.full(len(neutral_mesh), False)
    for i in autofit.LANDMARKS.values():
        if i < 468:
            face_mask |= np.linalg.norm(neutral_mesh - neutral_points[i], axis=1) <= 1.5 * ew
    bone_names = [b.name for b in rig.data.bones]
    dofs = []
    for bone in bone_names:
        for kind in ("translation", "rotation"):
            for axis in range(3):
                dofs.append({"name": f"{bone}.{kind[0]}{axis}", "bone": bone, "kind": kind, "axis": axis, "small": SMALL_TRANSLATION_EW * ew if kind == "translation" else SMALL_ROT, "large": LARGE_TRANSLATION_EW * ew if kind == "translation" else LARGE_ROT})
    response_small_plus = np.zeros((len(dofs), LANDMARK_COUNT, 3), float)
    response_small_minus = np.zeros_like(response_small_plus)
    response_large_plus = np.zeros_like(response_small_plus)
    tests = []
    for j, d in enumerate(dofs):
        for sign, arr in ((1, response_small_plus), (-1, response_small_minus)):
            apply_dof(rig, d["bone"], d["kind"], d["axis"], sign * d["small"])
            landmark_coords = eval_subset(work, attachment_vertices)
            by_vertex = {int(v): landmark_coords[k] for k, v in enumerate(attachment_vertices)}
            all_coords = np.asarray([by_vertex[int(v)] for v in attachment_vertices])
            # Reconstruct using a compact lookup for the attachment vertices.
            positions = np.empty((LANDMARK_COUNT, 3), float)
            for i in range(LANDMARK_COUNT):
                tri = attachments[i]["triangleVertexIndices"]
                w = attachments[i]["barycentricCoordinates"]
                positions[i] = sum(w[k] * by_vertex[tri[k]] for k in range(3))
            arr[j] = positions - neutral_points
            rec = transform_record(rig.pose.bones[d["bone"]])
            tests.append({"dof": d["name"], "bone": d["bone"], "kind": d["kind"], "axis": d["axis"], "sign": sign, "command": sign * d["small"], "evaluated_transform": rec, "max_landmark_motion": float(np.max(np.linalg.norm(arr[j], axis=1))), "rms_landmark_motion": float(np.sqrt(np.mean(np.sum(arr[j] ** 2, axis=1))))})
        apply_dof(rig, d["bone"], d["kind"], d["axis"], d["large"])
        landmark_coords = eval_subset(work, attachment_vertices)
        by_vertex = {int(v): landmark_coords[k] for k, v in enumerate(attachment_vertices)}
        positions = np.empty((LANDMARK_COUNT, 3), float)
        for i in range(LANDMARK_COUNT):
            tri = attachments[i]["triangleVertexIndices"]
            w = attachments[i]["barycentricCoordinates"]
            positions[i] = sum(w[k] * by_vertex[tri[k]] for k in range(3))
        response_large_plus[j] = positions - neutral_points
        rec = transform_record(rig.pose.bones[d["bone"]])
        bone_weight = weights.get(d["bone"], np.zeros(len(neutral_mesh), dtype=float))
        tri_mask = np.any(bone_weight[polys] > 0.05, axis=1) & np.all(face_mask[polys], axis=1)
        tri_ids = np.flatnonzero(tri_mask)
        if len(tri_ids) > MAX_STRAIN_TRIANGLES:
            tri_ids = np.linspace(0, len(tri_ids) - 1, MAX_STRAIN_TRIANGLES, dtype=np.int64)
            sampled = True
        else:
            sampled = False
        triangles = polys[tri_ids]
        strain_vertices = np.unique(triangles.reshape(-1)) if len(triangles) else np.array([], dtype=np.int64)
        if len(strain_vertices):
            dv = eval_subset(work, strain_vertices)
            lookup = {int(v): k for k, v in enumerate(strain_vertices)}
            local_triangles = np.asarray([[lookup[int(v)] for v in tri] for tri in triangles], dtype=np.int64)
            strain = strain_measure(dv, neutral_mesh[strain_vertices], local_triangles)
        else:
            strain = strain_measure(np.empty((0, 3)), np.empty((0, 3)), np.empty((0, 3), dtype=np.int64))
        tests.append({"dof": d["name"], "bone": d["bone"], "kind": d["kind"], "axis": d["axis"], "sign": 1, "command": d["large"], "magnitude": "large", "evaluated_transform": rec, "max_landmark_motion": float(np.max(np.linalg.norm(response_large_plus[j], axis=1))), "rms_landmark_motion": float(np.sqrt(np.mean(np.sum(response_large_plus[j] ** 2, axis=1)))), "strain": strain, "strain_triangles": len(triangles), "strain_sampled": sampled})
    np.savez_compressed(out / "response-map.npz", response_small_plus=response_small_plus, response_small_minus=response_small_minus, response_large_plus=response_large_plus, neutral_points=neutral_points, dof_names=np.asarray([d["name"] for d in dofs]), small_values=np.asarray([d["small"] for d in dofs]), large_values=np.asarray([d["large"] for d in dofs]), eye_width=np.asarray([ew]))
    (out / "control-tests.json").write_text(json.dumps(tests, indent=2), encoding="utf-8")
    (out / "control-definition.json").write_text(json.dumps({"bones": bone_names, "dofs": dofs, "small_rotation_rad": SMALL_ROT, "large_rotation_rad": LARGE_ROT, "small_translation_fraction_eye_width": SMALL_TRANSLATION_EW, "large_translation_fraction_eye_width": LARGE_TRANSLATION_EW, "mapped_landmarks": len(mapped), "surface_distance_median": float(np.median(distances)), "eye_width": ew, "source_translation": source_translation.tolist(), "neutral_reconstruction_max_error": float(np.max(np.linalg.norm(eval_subset(work, attachment_vertices) - neutral_mesh[attachment_vertices], axis=1))), "weight_group_counts": {n: int(np.sum(weights.get(n, np.zeros(len(neutral_mesh))) > 1e-6)) for n in bone_names}, "runtime_seconds": time.perf_counter() - started}, indent=2), encoding="utf-8")
    print(json.dumps({"character": label, "dofs": len(dofs), "tests": len(tests), "runtime_seconds": time.perf_counter() - started, "output": str(out)}, indent=2))


if __name__ == "__main__":
    for label, cfg in CASES.items():
        run(label, cfg)
