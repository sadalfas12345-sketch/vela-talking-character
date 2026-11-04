"""Create measured, sparse facial shape keys on the preserved Tripo/Mixamo GLB.

The mesh is a closed image-to-3D shell with no oral cavity or separate eyelids.
This script deforms its existing face surface from registered Face Landmarker
coordinates; it does not claim to synthesize missing anatomy.

Run with Blender 5.x. The source files are read-only.
"""
import json
import math
import os
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
ASSET = ROOT / "assets" / "tripo" / "vela-photoreal"
SOURCE = ASSET / "generated-rigged.glb"
LANDMARKS = ASSET / "landmarks.json"
OUTPUT = ASSET / "vela-photoreal-faced.glb"
CALIBRATION = ASSET / "face-calibration.json"
REPORT = ASSET / "facial-rig-report.json"

# Face Landmarker's stable 478-point face oval.
FACE_OVAL = [10, 338, 297, 332, 284, 251, 389, 356, 454, 323, 361, 288,
             397, 365, 379, 378, 400, 377, 152, 148, 176, 149, 150, 136,
             172, 58, 132, 93, 234, 127, 162, 21, 54, 103, 67, 109]


def point_in_polygon(x, y, polygon):
    inside = np.zeros(x.shape, dtype=bool)
    x0, y0 = polygon[-1]
    for x1, y1 in polygon:
        crosses = (y1 > y) != (y0 > y)
        edge_x = (x0 - x1) * (y - y1) / (y0 - y1 + 1e-20) + x1
        inside ^= crosses & (x < edge_x)
        x0, y0 = x1, y1
    return inside


def smooth(value):
    value = np.clip(value, 0.0, 1.0)
    return value * value * (3.0 - 2.0 * value)


def gaussian(x, y, cx, cy, rx, ry):
    q = ((x - cx) / max(rx, 1e-8)) ** 2 + ((y - cy) / max(ry, 1e-8)) ** 2
    return smooth(1.0 - q)


def main():
    if not SOURCE.is_file() or not LANDMARKS.is_file():
        raise FileNotFoundError("Expected generated-rigged.glb and landmarks.json")
    landmark_data = json.loads(LANDMARKS.read_text(encoding="utf-8"))
    lm = np.asarray(landmark_data["landmarks"], dtype=np.float64)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(SOURCE))
    scene = bpy.context.scene
    meshes = [obj for obj in scene.objects if obj.type == "MESH" and obj.name != "Icosphere"]
    if len(meshes) != 1:
        raise RuntimeError(f"Expected one skinned character mesh, got {[o.name for o in meshes]}")
    obj = meshes[0]
    if len(obj.data.vertices) != 999787 or len(obj.vertex_groups) < 60:
        raise RuntimeError("The preserved Tripo/Mixamo source does not match the inspected asset")
    for helper in [o for o in scene.objects if o.type == "MESH" and o.name == "Icosphere"]:
        bpy.data.objects.remove(helper, do_unlink=True)

    # The source is far denser than a 1080p portrait needs and exceeds Blender's
    # available export memory with dense morphs. Decimate only this derived copy;
    # Blender interpolates UVs and skin weights, while all 4K source maps remain.
    armature_modifiers = [i for i, modifier in enumerate(obj.modifiers) if modifier.type == "ARMATURE"]
    decimate = obj.modifiers.new("Vela derived portrait optimization", "DECIMATE")
    decimate.ratio = 0.30
    decimate.use_collapse_triangulate = False
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    if armature_modifiers:
        obj.modifiers.move(len(obj.modifiers) - 1, 0)
    bpy.ops.object.modifier_apply(modifier=decimate.name)
    if len(obj.data.vertices) > 500000:
        raise RuntimeError(f"Derived mesh optimization did not reduce enough: {len(obj.data.vertices)} vertices")

    # Match the exact orthographic Blender camera used to produce the landmark image.
    cam_data = bpy.data.cameras.new("LandmarkRegistrationCamera")
    camera = bpy.data.objects.new("LandmarkRegistrationCamera", cam_data)
    scene.collection.objects.link(camera)
    camera.location = (1.0, 0.0, 0.82)
    camera.rotation_euler = (Vector((0.0, 0.0, 0.82)) - camera.location).to_track_quat("-Z", "Y").to_euler()
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = 0.20
    scene.camera = camera
    rotation = camera.rotation_euler.to_quaternion()
    camera_right = rotation @ Vector((1, 0, 0))
    camera_up = rotation @ Vector((0, 1, 0))
    camera_toward = rotation @ Vector((0, 0, 1))
    ray_direction = rotation @ Vector((0, 0, -1))
    depsgraph = bpy.context.evaluated_depsgraph_get()

    # Back-project all 478 image landmarks onto the actual Tripo surface.
    hit_points = np.full((len(lm), 3), np.nan, dtype=np.float64)
    hit_depths = np.full(len(lm), np.nan, dtype=np.float64)
    for i, (u, v, _z) in enumerate(lm):
        origin = camera.location + camera_right * ((u - 0.5) * 0.20) + camera_up * ((0.5 - v) * 0.20)
        hit, location, _normal, _index, _obj, _matrix = scene.ray_cast(depsgraph, origin, ray_direction, distance=2.0)
        if hit:
            hit_points[i] = location[:]
            hit_depths[i] = float((location - origin).length)
    valid_lm = np.isfinite(hit_depths)
    if valid_lm.sum() < 350:
        raise RuntimeError(f"Only {valid_lm.sum()} of {len(lm)} facial landmarks hit the GLB surface")

    # Compute camera-space coordinates for each original mesh vertex.
    local = np.empty((len(obj.data.vertices), 3), dtype=np.float32)
    obj.data.vertices.foreach_get("co", local.ravel())
    world_matrix = np.asarray(obj.matrix_world, dtype=np.float64)
    world = local.astype(np.float64) @ world_matrix[:3, :3].T + world_matrix[:3, 3]
    cam_inv = np.asarray(camera.matrix_world.inverted(), dtype=np.float64)
    camera_pos = np.asarray(camera.location[:], dtype=np.float64)
    camera_local = (world - camera_pos) @ cam_inv[:3, :3].T
    sx = 0.5 + camera_local[:, 0] / 0.20
    sy_up = 0.5 + camera_local[:, 1] / 0.20
    depth = -camera_local[:, 2]
    xy = np.column_stack((sx, 1.0 - sy_up))

    outline = lm[FACE_OVAL, :2]
    inside = point_in_polygon(xy[:, 0], xy[:, 1], outline)
    inside &= (xy[:, 0] >= 0) & (xy[:, 0] <= 1) & (xy[:, 1] >= 0) & (xy[:, 1] <= 1)
    candidate = np.flatnonzero(inside)
    valid_indices = np.flatnonzero(valid_lm)
    landmark_xy = lm[valid_indices, :2]
    landmark_depth = hit_depths[valid_indices]
    nearest_depth = np.empty(len(candidate), dtype=np.float64)
    # Nearest measured landmark depth separates the face surface from foreground hair.
    for start in range(0, len(candidate), 12000):
        ids = candidate[start:start + 12000]
        dx = xy[ids, 0, None] - landmark_xy[None, :, 0]
        dy = xy[ids, 1, None] - landmark_xy[None, :, 1]
        nearest = np.argmin(dx * dx + dy * dy, axis=1)
        nearest_depth[start:start + len(ids)] = landmark_depth[nearest]
    interocular = np.linalg.norm((lm[33, :2] - lm[263, :2]) * 0.20)
    depth_tolerance = max(interocular * 0.42, 0.003)
    face_mask = np.zeros(len(local), dtype=bool)
    face_mask[candidate] = np.abs(depth[candidate] - nearest_depth) <= depth_tolerance
    if face_mask.sum() < 2500:
        raise RuntimeError(f"Registered face surface too small: {int(face_mask.sum())} vertices")

    # Preserve a complete provenance map for the adapter's measured eye anchors.
    named = {
        "eye_outer_left": 263, "eye_inner_left": 362,
        "eye_outer_right": 33, "eye_inner_right": 133,
        "eye_top_left": 386, "eye_bottom_left": 374,
        "eye_top_right": 159, "eye_bottom_right": 145,
        "mouth_corner_left": 291, "mouth_corner_right": 61,
        "upper_lip": 13, "lower_lip": 14,
        "brow_left": 336, "brow_right": 107, "chin": 152,
    }
    calibration = {
        "method": "MediaPipe 478-point landmarks back-projected through a matched orthographic camera onto the preserved Tripo surface",
        "renderCamera": {"position": [1, 0, 0.82], "target": [0, 0, 0.82], "orthographicScaleMeters": 0.20},
        "sourceRootLiftMeters": 0.0,
        "faceForwardYawRadians": -math.pi / 2,
        "landmarks3d": {key: hit_points[index].tolist() for key, index in named.items()},
        "landmarksHit": int(valid_lm.sum()),
        "registeredFaceVertices": int(face_mask.sum()),
        "depthToleranceMeters": float(depth_tolerance),
        "interocularDistanceMeters": float(interocular),
    }
    CALIBRATION.write_text(json.dumps(calibration, indent=2) + "\n", encoding="utf-8")

    # Camera-plane coordinates in meters follow measured facial anatomy.
    screen_x = (sx - 0.5) * 0.20
    screen_y = (sy_up - 0.5) * 0.20
    def p(i): return np.array([(lm[i, 0] - 0.5) * 0.20, (0.5 - lm[i, 1]) * 0.20])
    mouth_left, mouth_right = p(291), p(61)
    mouth_center = (mouth_left + mouth_right) * 0.5
    mouth_width = float(np.linalg.norm(mouth_right - mouth_left))
    upper = p(13); lower = p(14); chin = p(152)
    mouth_height = max(float(np.linalg.norm(upper - lower)), mouth_width * 0.12)
    jaw_length = max(float(np.linalg.norm(lower - chin)), mouth_width * 0.48)
    eye_data = {}
    for side, outer, inner, top, bottom in [
        ("Left", 263, 362, 386, 374), ("Right", 33, 133, 159, 145)
    ]:
        a, b, t, d = p(outer), p(inner), p(top), p(bottom)
        center = (a + b + t + d) / 4
        eye_data[side] = {"center": center, "width": float(np.linalg.norm(a - b)), "height": max(float(abs(t[1] - d[1])), mouth_width * 0.08)}

    # Convert camera-plane deformation vectors back to the original local mesh axes.
    basis = np.column_stack((np.asarray(camera_right[:]), np.asarray(camera_up[:]), np.asarray(camera_toward[:])))
    local_inverse = np.linalg.inv(world_matrix[:3, :3])
    def to_local(delta_x, delta_y, delta_depth):
        delta_world = np.column_stack((delta_x, delta_y, delta_depth)) @ basis.T
        return (delta_world @ local_inverse.T).astype(np.float32)

    delta_x = screen_x - mouth_center[0]
    delta_y = screen_y - mouth_center[1]
    mouth_region = gaussian(screen_x, screen_y, mouth_center[0], mouth_center[1], mouth_width * 0.72, max(mouth_width * 0.42, mouth_height * 2.2))
    side = np.clip(np.abs(delta_x) / max(mouth_width * 0.50, 1e-6), 0, 1)
    lip_lower_start = lower[1] + mouth_height * 0.20
    lower_t = np.clip((lip_lower_start - screen_y) / jaw_length, 0, 1)
    upper_weight = gaussian(screen_x, screen_y, upper[0], upper[1], mouth_width * 0.72, max(mouth_height * 0.85, 0.001))
    lower_lip_weight = gaussian(screen_x, screen_y, lower[0], lower[1], mouth_width * 0.70, max(mouth_height * 1.1, 0.001))
    jaw_weight = np.maximum(smooth(lower_t), lower_lip_weight * 0.82) * np.clip(1 - (delta_x / (mouth_width * 0.70)) ** 4, 0, 1)

    shapes = {}
    def store(name, dx, dy, dd=None):
        dx = np.asarray(dx, dtype=np.float32).copy()
        dy = np.asarray(dy, dtype=np.float32).copy()
        dd = np.zeros(len(dx), dtype=np.float32) if dd is None else np.asarray(dd, dtype=np.float32).copy()
        dx[~face_mask] = 0; dy[~face_mask] = 0; dd[~face_mask] = 0
        shapes[name] = to_local(dx, dy, dd)

    # Jaw/viseme deltas scale from each character's registered mouth dimensions.
    store("jawOpen", np.zeros(len(local)), -jaw_weight * mouth_width * 0.20, mouth_region * mouth_width * 0.025)
    store("mouthOpen", np.zeros(len(local)), -jaw_weight * mouth_width * 0.20, mouth_region * mouth_width * 0.025)
    store("viseme_aa", np.zeros(len(local)), -jaw_weight * mouth_width * 0.31 + upper_weight * mouth_width * 0.035,
          mouth_region * mouth_width * 0.035)
    store("viseme_E", np.sign(delta_x) * side * mouth_width * 0.10,
          -jaw_weight * mouth_width * 0.12 + upper_weight * mouth_width * 0.015)
    store("viseme_I", np.sign(delta_x) * side * mouth_width * 0.06,
          -jaw_weight * mouth_width * 0.09)
    store("viseme_O", -np.sign(delta_x) * mouth_region * mouth_width * 0.10,
          -jaw_weight * mouth_width * 0.11, mouth_region * mouth_width * 0.035)
    store("viseme_U", -np.sign(delta_x) * mouth_region * mouth_width * 0.14,
          -jaw_weight * mouth_width * 0.08, mouth_region * mouth_width * 0.045)
    store("viseme_PP", np.zeros(len(local)), np.sign(delta_y) * mouth_region * mouth_height * 0.12)
    store("viseme_sil", np.zeros(len(local)), np.sign(delta_y) * mouth_region * mouth_height * 0.035)
    store("mouthClose", np.zeros(len(local)), np.sign(delta_y) * mouth_region * mouth_height * 0.10)
    store("viseme_FF", np.zeros(len(local)), lower_lip_weight * mouth_width * 0.035)
    for name, factor in [("viseme_TH", 0.8), ("viseme_DD", 0.9), ("viseme_kk", 0.75),
                         ("viseme_CH", 0.7), ("viseme_SS", 0.55), ("viseme_nn", 0.45), ("viseme_RR", 0.7)]:
        store(name, np.sign(delta_x) * side * mouth_width * 0.035 * factor,
              -jaw_weight * mouth_width * 0.10 * factor)

    # Independent eyelid closure: measured upper/lower lid gap converges to zero.
    for side_name, data in eye_data.items():
        ex, ey = data["center"]
        ew, eh = data["width"], data["height"]
        eye_weight = gaussian(screen_x, screen_y, ex, ey, ew * 0.72, eh * 1.55)
        rel_y = screen_y - ey
        closing = np.clip(rel_y / max(eh * 0.65, 1e-6), -1, 1)
        store("eyeBlink" + side_name, np.zeros(len(local)), -closing * eh * 0.54 * eye_weight,
              eye_weight * ew * 0.035)

    # Landmark-centered smiles/frowns and brow actions, each independently controllable.
    for side_name, lm_index in [("Left", 291), ("Right", 61)]:
        cx, cy = p(lm_index)
        w = gaussian(screen_x, screen_y, cx, cy, mouth_width * 0.34, mouth_width * 0.30)
        sign = 1 if side_name == "Left" else -1
        store("mouthSmile" + side_name, sign * w * mouth_width * 0.11, w * mouth_width * 0.10)
        store("mouthFrown" + side_name, -sign * w * mouth_width * 0.07, -w * mouth_width * 0.09)
    brow_centers = {"Left": p(336), "Right": p(107)}
    brow_up = np.zeros(len(local), dtype=np.float32)
    for side_name, (bx, by) in brow_centers.items():
        w = gaussian(screen_x, screen_y, bx, by, mouth_width * 0.40, mouth_width * 0.20)
        store("browOuterUp" + side_name, np.zeros(len(local)), w * mouth_width * 0.11)
        store("browDown" + side_name, np.zeros(len(local)), -w * mouth_width * 0.08)
        brow_up += w
    store("browInnerUp", np.zeros(len(local)), np.clip(brow_up, 0, 1) * mouth_width * 0.08)

    # The source is a closed textured shell with no oral cavity. Add a small
    # dark, shape-keyed inner-mouth surface behind the lips. It remains a thin
    # seam at rest and opens with the same TalkingHead speech morphs. No teeth
    # or tongue are fabricated.
    mouth_point = np.nanmean(hit_points[[13, 14, 61, 291]], axis=0)
    inverse_world = obj.matrix_world.inverted()
    center_local = inverse_world @ Vector(mouth_point.tolist())
    right_local = inverse_world.to_3x3() @ camera_right
    up_local = inverse_world.to_3x3() @ camera_up
    toward_local = inverse_world.to_3x3() @ camera_toward
    right_local.normalize(); up_local.normalize(); toward_local.normalize()
    cavity_width = mouth_width * 0.72
    ring_count = 24
    basis_height = mouth_width * 0.012
    cavity_vertices = [center_local[:]]
    for i in range(ring_count):
        angle = 2 * math.pi * i / ring_count
        point = center_local + right_local * (math.cos(angle) * cavity_width * 0.5) \
                + up_local * (math.sin(angle) * basis_height * 0.5) \
                + toward_local * (mouth_width * 0.018)
        cavity_vertices.append(point[:])
    cavity_faces = [(0, i + 1, ((i + 1) % ring_count) + 1) for i in range(ring_count)]
    cavity_mesh = bpy.data.meshes.new("Generated inner mouth proxy geometry")
    cavity_mesh.from_pydata(cavity_vertices, [], cavity_faces)
    cavity_mesh.update()
    cavity_obj = bpy.data.objects.new("Generated inner mouth surface", cavity_mesh)
    scene.collection.objects.link(cavity_obj)
    cavity_obj.matrix_world = obj.matrix_world.copy()
    cavity_material = bpy.data.materials.new("Inner mouth · procedural dark cavity")
    cavity_material.diffuse_color = (0.012, 0.004, 0.006, 1)
    cavity_material.use_nodes = True
    bsdf = cavity_material.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (0.008, 0.002, 0.003, 1)
        bsdf.inputs["Roughness"].default_value = 0.94
        if "Metallic" in bsdf.inputs:
            bsdf.inputs["Metallic"].default_value = 0.0
    cavity_mesh.materials.append(cavity_material)
    armature = bpy.data.objects.get("Armature")
    head_bone = next((bone for bone in armature.data.bones if bone.name.lower().endswith(":head")), None) if armature else None
    if not head_bone:
        raise RuntimeError("Mixamo Head bone not found for generated inner-mouth surface")
    cavity_world = cavity_obj.matrix_world.copy()
    cavity_obj.parent = armature
    cavity_obj.matrix_parent_inverse = armature.matrix_world.inverted()
    cavity_obj.matrix_world = cavity_world
    head_group = cavity_obj.vertex_groups.new(name=head_bone.name)
    head_group.add(list(range(len(cavity_vertices))), 1.0, "REPLACE")
    cavity_armature = cavity_obj.modifiers.new("Mixamo Head follow", "ARMATURE")
    cavity_armature.object = armature
    cavity_obj.shape_key_add(name="Basis", from_mix=False)
    opening = {
        "jawOpen": (0.68, 0.18), "mouthOpen": (0.68, 0.18), "viseme_aa": (0.74, 0.27),
        "viseme_E": (0.82, 0.13), "viseme_I": (0.72, 0.10), "viseme_O": (0.53, 0.23),
        "viseme_U": (0.48, 0.17), "viseme_PP": (0.48, 0.025), "viseme_sil": (0.70, 0.015),
        "mouthClose": (0.70, 0.01), "viseme_FF": (0.70, 0.065), "viseme_TH": (0.72, 0.11),
        "viseme_DD": (0.72, 0.12), "viseme_kk": (0.70, 0.14), "viseme_CH": (0.78, 0.15),
        "viseme_SS": (0.84, 0.08), "viseme_nn": (0.69, 0.075), "viseme_RR": (0.67, 0.16),
    }
    for name in shapes:
        key = cavity_obj.shape_key_add(name=name, from_mix=False)
        width_ratio, height_ratio = opening.get(name, (0.72, 0.04))
        for i in range(ring_count):
            angle = 2 * math.pi * i / ring_count
            point = center_local + right_local * (math.cos(angle) * cavity_width * width_ratio * 0.5) \
                    + up_local * (math.sin(angle) * mouth_width * height_ratio * 0.5) \
                    + toward_local * (mouth_width * 0.018)
            key.data[i + 1].co = point
        key.value = 0.0
    cavity_obj.data.shape_keys.use_relative = True

    # Shape keys are genuine vertex deltas. Zero-delta body vertices are later
    # represented by sparse glTF accessors to keep the 1M-vertex character usable.
    obj.shape_key_add(name="Basis", from_mix=False)
    for name, delta in shapes.items():
        key = obj.shape_key_add(name=name, from_mix=False)
        output_coords = local + delta
        key.data.foreach_set("co", output_coords.ravel())
        key.value = 0.0
    obj.data.shape_keys.use_relative = True
    obj.data.shape_keys.animation_data_clear()

    bpy.ops.export_scene.gltf(filepath=str(OUTPUT), export_format="GLB", export_morph=True,
                              export_skins=True, export_animations=True, export_apply=False)
    report = {
        "source": str(SOURCE.relative_to(ROOT)), "output": str(OUTPUT.relative_to(ROOT)),
        "sourcePreserved": True, "derivedMeshDecimationRatio": 0.30, "vertices": len(local),
        "triangles": sum(len(poly.vertices) - 2 for poly in obj.data.polygons),
        "landmarksHit": int(valid_lm.sum()), "registeredFaceVertices": int(face_mask.sum()),
        "depthToleranceMeters": float(depth_tolerance), "mouthWidthMeters": mouth_width,
        "eyeWidthMeters": {side: data["width"] for side, data in eye_data.items()},
        "shapeKeys": list(shapes), "shapeKeyCount": len(shapes), "generatedMouthSurface": {
            "geometry": "24-sided shape-keyed inner-mouth surface weighted to Mixamo Head",
            "visemeDriven": True, "restState": "thin closed-lip seam", "includesTeethOrTongue": False,
        },
        "geometryMethod": "measured landmark-space face selection and actual per-vertex surface deltas; Mixamo weights and PBR textures retained",
        "limitations": ["The generated Tripo head is one closed shell with no original oral anatomy or separate eyelids. A small shape-keyed dark inner-mouth surface makes opening visible, but does not provide teeth or tongue; lip motion is still surface deformation.",
                        "Blinking is a measured skin-surface deformation. Eye gaze has no separate eyeball geometry or eye bones in the source GLB."],
    }
    REPORT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("TRIPO_PHOTOREAL_FACE_RIG=" + json.dumps(report))


if __name__ == "__main__":
    main()
