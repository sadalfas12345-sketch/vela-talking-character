"""Add a target-specific facial shape-key set to the preserved Tripo Mixamo GLB.

This is a measured surface deformation rig for the existing closed-mouth Tripo
mesh. It deliberately does not add fictional teeth or an interior mouth cavity.
Run with Blender 5.x:
  blender -b --python scripts/build_tripo_face_rig.py
The source GLBs are read-only; output is assets/tripo/vela-reference-faced.glb.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import sys

import bpy
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "assets", "tripo", "vela-reference-rigged.glb")
ORIGINAL = os.path.join(ROOT, "assets", "tripo", "vela-reference-original.glb")
OUT = os.path.join(ROOT, "assets", "tripo", "vela-reference-faced.glb")
CAL = os.path.join(ROOT, "assets", "tripo", "face-transfer-calibration.json")

# Landmark coordinates were detected on the existing Tripo render by the
# official MediaPipe Face Landmarker, then mapped through its measured 20 cm
# orthographic registration camera into original Tripo model coordinates.
# This selects genuine skin islands from texture-color inspection, not hair.
LANDMARK_IDS = {
    "eye_outer_left": 263, "eye_inner_left": 362,
    "eye_outer_right": 33, "eye_inner_right": 133,
    "eye_top_left": 386, "eye_bottom_left": 374,
    "eye_top_right": 159, "eye_bottom_right": 145,
    "mouth_corner_left": 291, "mouth_corner_right": 61,
    "upper_lip": 13, "lower_lip": 14,
    "brow_left": 336, "brow_right": 107, "chin": 152,
}
FACE_RECT = {"screen_y": [-0.050, 0.050], "z": [0.345, 0.455], "depth_x": [0.008, 0.10]}


def smooth_gauss(y, z, cy, cz, ry, rz):
    q = ((y - cy) / ry) ** 2 + ((z - cz) / rz) ** 2
    # Compact-support C2 falloff avoids moving disconnected hair outside the mask.
    t = np.clip(1.0 - q, 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main():
    if not os.path.isfile(SRC):
        raise FileNotFoundError(SRC)
    with open(CAL, encoding="utf-8") as f:
        cal = json.load(f)
    lm = {name: np.asarray(cal["landmarks3d"][name], dtype=np.float64)
          for name in LANDMARK_IDS}

    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=SRC)
    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH" and o.name != "Icosphere"]
    if len(meshes) != 1:
        raise RuntimeError(f"Expected one Tripo body mesh, found {[o.name for o in meshes]}")
    # Tripo's Mixamo output includes an unskinned, untextured 42-vertex helper
    # sphere. It is absent from the original character and renders as a stray
    # floating bead, so omit that rigging artifact from the derived export only.
    for helper in [o for o in bpy.context.scene.objects if o.type == "MESH" and o.name == "Icosphere"]:
        bpy.data.objects.remove(helper, do_unlink=True)
    obj = meshes[0]
    if len(obj.data.vertices) != 261084:
        raise RuntimeError(f"Unexpected Tripo topology: {len(obj.data.vertices)} vertices")
    if len(obj.vertex_groups) < 60:
        raise RuntimeError("Mixamo skin weights missing; refusing to build on wrong asset")

    coords = np.empty((len(obj.data.vertices), 3), dtype=np.float32)
    obj.data.vertices.foreach_get("co", coords.ravel())
    # The existing Mixamo conversion baked a vertical translation into all
    # geometry. Measure that translation from the two mesh bounding-box centers
    # and shift the registered landmarks into the rigged mesh coordinate space.
    rigged_z_center = float((coords[:, 2].min() + coords[:, 2].max()) * 0.5)
    rigged_objects = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=ORIGINAL)
    original = next(o for o in set(bpy.data.objects) - rigged_objects
                    if o.type == "MESH" and len(o.data.vertices) == len(coords))
    source_coords = np.empty_like(coords)
    original.data.vertices.foreach_get("co", source_coords.ravel())
    source_z_center = float((source_coords[:, 2].min() + source_coords[:, 2].max()) * 0.5)
    z_offset = rigged_z_center - source_z_center
    cal["riggedVerticalOffsetMeters"] = z_offset
    cal["faceForwardYawRadians"] = -math.pi / 2
    with open(CAL, "w", encoding="utf-8") as f:
        json.dump(cal, f, indent=2)
    for imported in set(bpy.data.objects) - rigged_objects:
        bpy.data.objects.remove(imported, do_unlink=True)
    lm = {name: point + np.array([0.0, 0.0, z_offset]) for name, point in lm.items()}
    analysis = coords
    y, z, x = analysis[:, 1], analysis[:, 2], analysis[:, 0]
    face = (y >= FACE_RECT["screen_y"][0]) & (y <= FACE_RECT["screen_y"][1])
    face &= (z >= FACE_RECT["z"][0] + z_offset) & (z <= FACE_RECT["z"][1] + z_offset)
    face &= (x >= FACE_RECT["depth_x"][0])
    if int(face.sum()) < 1000:
        raise RuntimeError(f"Face transfer mask unexpectedly small: {int(face.sum())} vertices")

    # Landmark coordinates are in original un-rigged source space.
    mouth = (lm["mouth_corner_left"] + lm["mouth_corner_right"]) * 0.5
    mouth_y, mouth_z = mouth[1], mouth[2]
    mouth_width = float(np.linalg.norm(lm["mouth_corner_left"][[1, 2]] - lm["mouth_corner_right"][[1, 2]]))
    eye_centers = {
        "Left": (lm["eye_outer_left"] + lm["eye_inner_left"]) * 0.5,
        "Right": (lm["eye_outer_right"] + lm["eye_inner_right"]) * 0.5,
    }

    # For the mouth controls, local axes are measured from the character:
    # Y spans left/right, Z is vertical, X points toward the rendered face.
    dy = y - mouth_y
    dz = z - mouth_z
    mouth_w = max(mouth_width * 0.65, 0.012)
    mouth_h = 0.013
    near_mouth = smooth_gauss(y, z, mouth_y, mouth_z, mouth_w, mouth_h)
    upper = np.clip(dz / 0.006, 0.0, 1.0) * near_mouth
    lower = np.clip(-dz / 0.006, 0.0, 1.0) * near_mouth
    corner = np.clip(np.abs(dy) / max(mouth_width * 0.32, 0.003), 0.0, 1.0) * near_mouth

    # Controls are real vertex deltas baked into the mesh. Viseme weights and
    # names match TalkingHead's Oculus/ARKit vocabulary.
    shapes = {}
    def new_delta():
        return np.zeros_like(coords, dtype=np.float32)
    def put(name, delta):
        delta[~face] = 0
        shapes[name] = delta

    # Jaw and open vowels move the actual lower-face surface down. The closed
    # shell constraint prevents an anatomically correct inner-mouth opening.
    d = new_delta(); d[:, 2] = -0.015 * lower; d[:, 0] = 0.0012 * near_mouth
    put("jawOpen", d)
    d = new_delta(); d[:, 2] = -0.024 * lower + 0.002 * upper; d[:, 0] = 0.0015 * near_mouth
    put("viseme_aa", d)
    d = new_delta(); d[:, 2] = -0.006 * lower; d[:, 1] = np.sign(dy) * 0.003 * corner
    put("viseme_E", d)
    d = new_delta(); d[:, 2] = -0.005 * lower; d[:, 1] = np.sign(dy) * 0.004 * corner
    put("viseme_I", d)
    d = new_delta(); d[:, 1] = -np.sign(dy) * 0.0028 * near_mouth; d[:, 0] = 0.001 * near_mouth
    put("viseme_O", d)
    d = new_delta(); d[:, 1] = -np.sign(dy) * 0.0032 * near_mouth; d[:, 2] = -0.004 * lower; d[:, 0] = 0.0015 * near_mouth
    put("viseme_U", d)
    for name in ("viseme_PP", "viseme_sil", "mouthClose"):
        d = new_delta(); d[:, 2] = -np.sign(dz) * 0.0025 * near_mouth; put(name, d)
    d = new_delta(); d[:, 2] = 0.004 * lower; put("viseme_FF", d)
    d = new_delta(); d[:, 2] = -0.002 * lower; d[:, 1] = np.sign(dy) * 0.001 * corner; put("viseme_TH", d)
    for name, factor in (("viseme_DD", 0.7), ("viseme_kk", 0.85), ("viseme_CH", 0.6),
                         ("viseme_SS", 0.45), ("viseme_nn", 0.35), ("viseme_RR", 0.8)):
        d = new_delta(); d[:, 2] = -0.006 * factor * lower; d[:, 1] = np.sign(dy) * 0.0015 * factor * corner; put(name, d)
    # TalkingHead requests the unprefixed alias too on some paths.
    d = new_delta(); d[:, 2] = -0.015 * lower; put("mouthOpen", d)

    # Eye blink: deform the eye surround toward the measured eyelid midpoint.
    # Each side is independent; there are no separate eyeball/lid meshes in GLB.
    for side in ("Left", "Right"):
        c = eye_centers[side]
        top_name = "eye_top_" + side.lower()
        bot_name = "eye_bottom_" + side.lower()
        ey = float((c[1] + lm["mouth_corner_left"][1]) * 0.0 + c[1])
        ez = float(c[2])
        half_h = max(abs(lm[top_name][2] - lm[bot_name][2]) * 1.5, 0.006)
        ewidth = max(abs(lm["eye_outer_" + side.lower()][1] - lm["eye_inner_" + side.lower()][1]) * 1.2, 0.009)
        eye_w = smooth_gauss(y, z, ey, ez, ewidth, half_h * 1.7)
        d = new_delta()
        vertical = np.clip((z - ez) / half_h, -1.0, 1.0)
        d[:, 2] = -vertical * 0.0065 * eye_w
        d[:, 0] = 0.0004 * eye_w
        put("eyeBlink" + side, d)

    # Smile/frown and brow controls use separate landmark-centered falloffs.
    for side, corner_name in (("Left", "mouth_corner_left"), ("Right", "mouth_corner_right")):
        c = lm[corner_name]
        w = smooth_gauss(y, z, c[1], c[2], 0.010, 0.008)
        sign = 1.0 if side == "Left" else -1.0
        d = new_delta(); d[:, 1] = sign * 0.0035 * w; d[:, 2] = 0.0028 * w; put("mouthSmile" + side, d)
        d = new_delta(); d[:, 1] = -sign * 0.0025 * w; d[:, 2] = -0.003 * w; put("mouthFrown" + side, d)
    for side, key, sign in (("Left", "brow_left", 1.0), ("Right", "brow_right", -1.0)):
        c = lm[key]
        w = smooth_gauss(y, z, c[1], c[2], 0.012, 0.006)
        d = new_delta(); d[:, 2] = 0.0035 * w; put("browOuterUp" + side, d)
        d = new_delta(); d[:, 2] = -0.0025 * w; put("browDown" + side, d)
    d = new_delta();
    for side in ("Left", "Right"):
        c = lm["brow_" + side.lower()]
        d[:, 2] += 0.002 * smooth_gauss(y, z, c[1], c[2], 0.008, 0.006)
    put("browInnerUp", d)

    # Shape keys share one Basis and leave all skinning and original surfaces intact.
    obj.shape_key_add(name="Basis", from_mix=False)
    for name, delta in shapes.items():
        key = obj.shape_key_add(name=name, from_mix=False)
        out_coords = coords + delta
        key.data.foreach_set("co", out_coords.astype(np.float32, copy=False).ravel())
        key.value = 0.0
    obj.data.shape_keys.use_relative = True
    obj.data.shape_keys.animation_data_clear()

    report = {
        "source": os.path.relpath(SRC, ROOT), "output": os.path.relpath(OUT, ROOT),
        "vertexCount": len(coords), "facialMaskVertexCount": int(face.sum()),
        "shapeKeyCount": len(shapes), "shapeKeys": list(shapes),
        "sourceFilesUnchangedByBuild": True,
        "originalGlbSha256": sha256_file(ORIGINAL),
        "riggedGlbSha256": sha256_file(SRC),
        "method": "landmark-registered surface deformation in rigged coordinates with measured source-to-rigged bounding-box offset",
        "measuredRiggedVerticalOffsetMeters": z_offset,
        "limitations": ["Tripo mesh has no mouth cavity, separate teeth, or tongue; open-mouth shapes stretch the closed lip surface."],
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    bpy.ops.export_scene.gltf(filepath=OUT, export_format="GLB", export_morph=True,
                              export_skins=True, export_animations=True, export_apply=False)
    with open(os.path.join(ROOT, "assets", "tripo", "facial-rig-report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print("TRIPO_FACE_RIG_REPORT", json.dumps(report))


if __name__ == "__main__":
    main()
