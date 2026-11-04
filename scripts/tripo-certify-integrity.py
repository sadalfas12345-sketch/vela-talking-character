"""Measure GLB structure and skin integrity for Vela's Tripo certification.

This parser reads the binary GLB directly, independently of the cached Blender
inspection reports. It emits measured values only; policy thresholds live in
tripo-certify.mjs.
"""
import hashlib
import json
import math
import re
import struct
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
ASSET = ROOT / "assets" / "tripo" / "vela-photoreal"
FILES = ["generated-original.glb", "generated-rigged.glb", "vela-photoreal-faced.glb"]
COMPONENTS = {5120: ("b", 1), 5121: ("B", 1), 5122: ("h", 2), 5123: ("H", 2), 5125: ("I", 4), 5126: ("f", 4)}
TYPE_WIDTH = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT2": 4, "MAT3": 9, "MAT4": 16}
REQUIRED = ["Hips", "Spine", "Spine1", "Spine2", "Neck", "Head", "LeftShoulder", "RightShoulder",
            "LeftArm", "RightArm", "LeftForeArm", "RightForeArm", "LeftHand", "RightHand",
            "LeftUpLeg", "RightUpLeg", "LeftLeg", "RightLeg", "LeftFoot", "RightFoot", "LeftToeBase", "RightToeBase"]
for side in ("Left", "Right"):
    for digit in ("Thumb", "Index", "Middle", "Ring", "Pinky"):
        REQUIRED += [f"{side}Hand{digit}{i}" for i in (1, 2, 3)]
REQUIRED_MORPHS = ["jawOpen", "mouthOpen", "viseme_sil", "viseme_PP", "viseme_FF", "viseme_TH", "viseme_DD",
                   "viseme_kk", "viseme_CH", "viseme_SS", "viseme_nn", "viseme_RR", "viseme_aa", "viseme_E",
                   "viseme_I", "viseme_O", "viseme_U", "eyeBlinkLeft", "eyeBlinkRight", "mouthSmileLeft",
                   "mouthSmileRight", "mouthFrownLeft", "mouthFrownRight", "browInnerUp", "browDownLeft",
                   "browDownRight", "browOuterUpLeft", "browOuterUpRight"]


def read_glb(path):
    data = path.read_bytes()
    if len(data) < 20:
        raise ValueError("file shorter than GLB header")
    magic, version, declared = struct.unpack_from("<4sII", data, 0)
    if magic != b"glTF" or version != 2 or declared != len(data):
        raise ValueError(f"invalid GLB header magic={magic!r}, version={version}, declared={declared}, actual={len(data)}")
    offset, doc, binary = 12, None, None
    while offset < len(data):
        length, kind = struct.unpack_from("<I4s", data, offset)
        offset += 8
        chunk = data[offset:offset + length]
        if len(chunk) != length:
            raise ValueError("truncated GLB chunk")
        if kind == b"JSON":
            doc = json.loads(chunk.decode("utf-8").rstrip(" \t\r\n\0"))
        elif kind == b"BIN\0":
            binary = chunk
        offset += length
    if doc is None or binary is None:
        raise ValueError("GLB must have JSON and binary chunks")
    return data, doc, binary


def accessor_array(doc, binary, index):
    accessor = doc["accessors"][index]
    fmt, size = COMPONENTS[accessor["componentType"]]
    width = TYPE_WIDTH[accessor["type"]]
    view = doc["bufferViews"][accessor["bufferView"]]
    stride = view.get("byteStride", size * width)
    start = view.get("byteOffset", 0) + accessor.get("byteOffset", 0)
    count = accessor["count"]
    if stride == size * width:
        values = np.frombuffer(binary, dtype=np.dtype("<" + fmt), count=count * width, offset=start).reshape(count, width)
    else:
        values = np.empty((count, width), dtype=np.dtype("<" + fmt))
        for row in range(count):
            values[row] = struct.unpack_from("<" + fmt * width, binary, start + row * stride)
    return values, accessor


def normalize_bone(name):
    value = re.sub(r"^mixamorig[:_]?", "", name, flags=re.I)
    return re.sub(r"[^a-z0-9]", "", value).lower()


def measure(path):
    data, doc, binary = read_glb(path)
    nodes = doc.get("nodes", [])
    skins = doc.get("skins", [])
    nodes_by_skin = []
    for skin in skins:
        nodes_by_skin.extend(nodes[i].get("name", f"node_{i}") for i in skin.get("joints", []))
    bone_names = sorted(set(nodes_by_skin))
    normalized_bones = {normalize_bone(n) for n in bone_names}
    missing_bones = [name for name in REQUIRED if normalize_bone(name) not in normalized_bones]
    all_morphs, mesh_rows = [], []
    pos_finite = pos_total = 0
    weighted_total = weighted_valid = weight_sum_fail = weight_nonfinite = index_invalid = 0
    bind_total = bind_finite = bind_invertible = 0
    neutral_values = []
    for node_i, node in enumerate(nodes):
        mesh_i = node.get("mesh")
        if mesh_i is None:
            if "weights" in node:
                neutral_values.extend(node["weights"])
            continue
        mesh = doc["meshes"][mesh_i]
        if "weights" in mesh:
            neutral_values.extend(mesh["weights"])
        target_names = mesh.get("extras", {}).get("targetNames", [])
        all_morphs.extend(target_names)
        for prim_i, prim in enumerate(mesh.get("primitives", [])):
            attrs = prim.get("attributes", {})
            row = {"node": node.get("name", f"node_{node_i}"), "mesh": mesh.get("name", f"mesh_{mesh_i}"),
                   "primitive": prim_i, "vertices": 0, "skinned": "JOINTS_0" in attrs,
                   "targets": len(prim.get("targets", [])), "targetNames": target_names}
            if "POSITION" in attrs:
                positions, pa = accessor_array(doc, binary, attrs["POSITION"])
                row["vertices"] = len(positions)
                finite = np.isfinite(positions).all(axis=1)
                pos_total += len(positions); pos_finite += int(finite.sum())
                row["positionFinite"] = int(finite.sum())
            if "JOINTS_0" in attrs and "WEIGHTS_0" in attrs:
                joints, _ = accessor_array(doc, binary, attrs["JOINTS_0"])
                weights, _ = accessor_array(doc, binary, attrs["WEIGHTS_0"])
                combined = weights.astype(np.float64)
                finite = np.isfinite(weights).all(axis=1)
                valid = finite & (weights >= 0).all(axis=1) & (joints < max(1, len(skins[0].get("joints", [])) if skins else 1)).all(axis=1)
                sets = 1
                while f"JOINTS_{sets}" in attrs and f"WEIGHTS_{sets}" in attrs:
                    extra_j, _ = accessor_array(doc, binary, attrs[f"JOINTS_{sets}"])
                    extra_w, _ = accessor_array(doc, binary, attrs[f"WEIGHTS_{sets}"])
                    valid &= np.isfinite(extra_w).all(axis=1) & (extra_w >= 0).all(axis=1)
                    valid &= (extra_j < max(1, len(skins[0].get("joints", [])) if skins else 1)).all(axis=1)
                    combined = np.column_stack([combined, extra_w])
                    sets += 1
                sums = combined.sum(axis=1)
                weighted_total += len(weights); weighted_valid += int(valid.sum())
                weight_sum_fail += int((np.abs(sums - 1.0) > 0.01).sum())
                weight_nonfinite += int((~np.isfinite(combined).all(axis=1)).sum())
                index_invalid += int((~valid).sum())
                row.update({"weightedVertices": len(weights), "weightFiniteVertices": int(finite.sum()),
                            "weightSumFailureVertices": int((np.abs(sums - 1.0) > 0.01).sum()),
                            "influenceSets": sets})
            mesh_rows.append(row)
    for skin in skins:
        accessor_i = skin.get("inverseBindMatrices")
        if accessor_i is None:
            continue
        matrices, _ = accessor_array(doc, binary, accessor_i)
        bind_total += len(matrices)
        for flat in matrices:
            if not np.isfinite(flat).all():
                continue
            bind_finite += 1
            try:
                matrix = flat.reshape((4, 4), order="F").astype(np.float64)
                if abs(float(np.linalg.det(matrix))) > 1e-12:
                    bind_invertible += 1
            except np.linalg.LinAlgError:
                pass
    texture_missing = []
    image_count = len(doc.get("images", []))
    for i, image in enumerate(doc.get("images", [])):
        if "bufferView" in image:
            view = doc["bufferViews"][image["bufferView"]]
            if view.get("byteLength", 0) <= 0:
                texture_missing.append(f"image[{i}]:empty bufferView")
        elif "uri" in image and image["uri"].startswith("data:"):
            continue
        elif "uri" in image:
            texture_missing.append(f"image[{i}]:external URI in GLB: {image['uri']}")
        else:
            texture_missing.append(f"image[{i}]:missing source")
    for i, texture in enumerate(doc.get("textures", [])):
        source_i = texture.get("source")
        if source_i is None or source_i >= image_count:
            texture_missing.append(f"texture[{i}]:invalid image source")
    required_morphs = sorted(set(REQUIRED_MORPHS))
    missing_morphs = [name for name in required_morphs if name not in set(all_morphs)]
    neutral_nonzero = [float(v) for v in neutral_values if not math.isfinite(float(v)) or abs(float(v)) > 1e-8]
    try:
        git_clean = subprocess.run(["git", "diff", "--quiet", "HEAD", "--", str(path.relative_to(ROOT))], cwd=ROOT).returncode == 0
    except Exception:
        git_clean = None
    return {
        "path": str(path.relative_to(ROOT)).replace("\\", "/"), "bytes": len(data),
        "glbLoads": True, "glbVersion": 2, "meshPrimitiveCount": len(mesh_rows), "meshes": mesh_rows,
        "vertexCoordinates": {"finite": pos_finite, "total": pos_total, "finiteFraction": pos_finite / pos_total if pos_total else None},
        "skeleton": {"skinCount": len(skins), "boneCount": len(bone_names), "bones": bone_names,
                     "missingRequired": missing_bones, "requiredCount": len(REQUIRED),
                     "requiredPresent": len(REQUIRED) - len(missing_bones)},
        "skinWeights": {"weightedVertices": weighted_total, "validVertices": weighted_valid,
                        "coverage": weighted_valid / weighted_total if weighted_total else None,
                        "sumFailures": weight_sum_fail, "nonfiniteVertices": weight_nonfinite,
                        "invalidJointIndexVertices": index_invalid},
        "inverseBindMatrices": {"finite": bind_finite, "invertible": bind_invertible, "total": bind_total},
        "textures": {"imageCount": image_count, "textureCount": len(doc.get("textures", [])), "missingReferences": texture_missing},
        "morphTargets": sorted(set(all_morphs)), "missingRequiredMorphs": missing_morphs,
        "neutralMorphInfluenceCount": len(neutral_values), "neutralMorphNonzero": neutral_nonzero,
        "sourceGitClean": git_clean, "sha256": hashlib.sha256(data).hexdigest()
    }


def main():
    result = {"files": [], "errors": []}
    for name in FILES:
        path = ASSET / name
        try:
            result["files"].append(measure(path))
        except Exception as error:
            result["errors"].append({"file": name, "error": f"{type(error).__name__}: {error}"})
    print(json.dumps(result, indent=2))
    if result["errors"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
