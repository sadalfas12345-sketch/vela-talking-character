"""Generalized CaptureForge rig construction for the correction experiment."""
import numpy as np
from mathutils import Vector
from captureforge.face import autofit

_ORIG_FACE_GEOMETRY = autofit.face_geometry
_ORIG_BONE_SPECS = autofit.bone_specs


def _component_ids(mesh):
    n = len(mesh.vertices)
    parent = np.arange(n, dtype=np.int32)
    size = np.ones(n, dtype=np.int32)

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = int(parent[x])
        return x

    for edge in mesh.edges:
        a, b = int(edge.vertices[0]), int(edge.vertices[1])
        ra, rb = find(a), find(b)
        if ra == rb:
            continue
        if size[ra] < size[rb]:
            ra, rb = rb, ra
        parent[rb] = ra
        size[ra] += size[rb]
    roots = np.asarray([find(i) for i in range(n)], dtype=np.int32)
    _, labels = np.unique(roots, return_inverse=True)
    return labels.astype(np.int32)


def _axes(P):
    eye_l = (P["eye_out.L"] + P["eye_in.L"]) * 0.5
    eye_r = (P["eye_out.R"] + P["eye_in.R"]) * 0.5
    right = np.asarray(eye_l - eye_r, dtype=float)
    right /= max(np.linalg.norm(right), 1.0e-12)
    up = np.asarray(P["top"] - P["chin"], dtype=float)
    up -= right * np.dot(up, right)
    up /= max(np.linalg.norm(up), 1.0e-12)
    front = np.cross(right, up)
    front /= max(np.linalg.norm(front), 1.0e-12)
    return np.stack([right, front, up], axis=0)


def face_geometry(P, head, extras=()):
    g = _ORIG_FACE_GEOMETRY(P, head, extras)
    g["anatomical_axes"] = _axes(P)
    g["component_ids"] = _component_ids(head.data)
    return g


def bone_specs(P, g):
    specs = _ORIG_BONE_SPECS(P, g)
    up = Vector(g["anatomical_axes"][2])
    for spec in specs:
        if spec["name"].startswith("brow."):
            spec["tail"] = spec["head"] + up * (0.25 * g["ew"])
    return specs


def _smooth(t):
    t = np.clip(t, 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def skin_weights(co, specs, g):
    axes = np.asarray(g["anatomical_axes"], dtype=float)
    components = np.asarray(g["component_ids"], dtype=np.int32)
    ew = float(g["ew"])
    mw = float(g["mw"])
    w = {}
    for spec in specs:
        anchor = spec["anchor"]
        if anchor is None:
            continue
        anchor = np.asarray(anchor, dtype=float)
        local = (co - anchor) @ axes.T
        radius = float(spec["radius"])
        if spec["name"].startswith("brow."):
            radius = max(radius, 0.65 * ew)
        elif spec["name"].startswith("lid."):
            radius = max(radius, 0.45 * ew)
        seed = int(np.argmin(np.linalg.norm(co - anchor, axis=1)))
        same_surface = components == components[seed]
        depth_radius = max(0.70 * radius, 1.0e-8)
        q = np.sqrt((local[:, 0] / max(radius, 1.0e-8)) ** 2 +
                    (local[:, 1] / depth_radius) ** 2 +
                    (local[:, 2] / max(radius, 1.0e-8)) ** 2)
        values = _smooth(1.0 - q) ** 2
        values[~same_surface] = 0.0
        w[spec["name"]] = values
        if float(values.max(initial=0.0)) <= 1.0e-6:
            nearest = np.flatnonzero(same_surface)
            if len(nearest):
                nearest = nearest[np.argsort(q[nearest])[: min(32, len(nearest))]]
                local_q = q[nearest]
                span = max(float(local_q[-1] - local_q[0]), 1.0e-6)
                fallback = np.zeros_like(q)
                fallback[nearest] = _smooth(1.0 - (local_q - local_q[0]) / span) ** 2
                w[spec["name"]] = fallback

    jaw = next(s for s in specs if s["name"] == "jaw")
    line = np.asarray(g["line"], dtype=float)
    z_split = line[2] + 0.1 * mw
    jaw_w = _smooth((z_split - co[:, 2]) / max(0.25 * mw, 1.0e-8))
    jaw_w *= _smooth((np.asarray(jaw["head"], dtype=float)[1] - co[:, 1]) /
                     max(0.30 * mw, 1.0e-8) + 0.5)
    x_half = max(0.14, 4.0 * mw)
    y_half = max(0.08, 3.0 * mw)
    face_window = _smooth(1.0 - np.abs(co[:, 0] - float(g["cx"])) / x_half)
    face_window *= _smooth(1.0 - np.abs(co[:, 1] - line[1]) / y_half)
    chin_dist = np.linalg.norm(co - np.asarray(g["chin"], dtype=float), axis=1)
    face_window = np.maximum(face_window, _smooth(1.0 - chin_dist / max(0.25, 1.5 * mw)))
    w["jaw"] = jaw_w * face_window
    total = np.maximum(sum(w.values()), 1.0)
    w = {name: values / total for name, values in w.items()}
    w["head"] = np.maximum(0.0, 1.0 - sum(w.values()))
    return w


def build_faceforge_rig(P, head, extras=(), name="FaceRig"):
    g = face_geometry(P, head, extras)
    specs = bone_specs(P, g)
    arm = autofit.create_armature(name, specs, head.users_collection[0])
    co = np.empty(len(head.data.vertices) * 3, dtype=float)
    head.data.vertices.foreach_get("co", co)
    m = np.asarray(head.matrix_world, dtype=float)
    world = co.reshape(-1, 3) @ m[:3, :3].T + m[:3, 3]
    autofit._bind(head, arm, skin_weights(world, specs, g))
    for extra in extras:
        autofit._bind(extra, arm, {autofit.rigid_bone(extra, specs, g): np.ones(len(extra.data.vertices))})
    return arm
