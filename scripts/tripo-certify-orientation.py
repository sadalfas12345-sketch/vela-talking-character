"""Measure neutral rest-pose orientation in the preserved Tripo GLBs.

Axes are measured in Blender world coordinates. The character's forward axis
is taken from the documented matched face-registration camera, then compared
to the hip, head, spine and shoulder geometry. Stage D applies the exact
adapter yaw after converting the GLB Y-up rotation into Blender's Z-up axis.
"""
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
ASSET = ROOT / "assets" / "tripo" / "vela-photoreal"
CALIBRATION = json.loads((ASSET / "face-calibration.json").read_text(encoding="utf-8"))
SOURCE_FRONT = Vector(CALIBRATION["renderCamera"]["position"]) - Vector(CALIBRATION["renderCamera"]["target"])
SOURCE_FRONT.normalize()
YAW = float(CALIBRATION["faceForwardYawRadians"])


def angle(a, b):
    if a.length < 1e-9 or b.length < 1e-9:
        return None
    return math.degrees(math.acos(max(-1.0, min(1.0, a.normalized().dot(b.normalized())))))


def norm(v):
    return v.normalized() if v.length > 1e-9 else Vector((0.0, 0.0, 0.0))


def measure(path, stage, apply_adapter_yaw=False, rename_bones=False):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(path))
    armature = next((o for o in bpy.context.scene.objects if o.type == "ARMATURE"), None)
    if not armature:
        return {"stage": stage, "path": str(path.relative_to(ROOT)).replace("\\", "/"), "armature": False,
                "missingBones": ["Armature"], "diagnosis": "No armature exists at this pipeline stage."}
    if apply_adapter_yaw:
        # GLTF's armature root is a Y-up object. Blender imports it Z-up with
        # quaternion rotation mode, so explicitly switch before applying the
        # adapter's equivalent world yaw.
        armature.rotation_mode = "XYZ"
        armature.rotation_euler.z += YAW
        bpy.context.view_layer.update()
    prefix = "mixamorig:"
    def get(name):
        candidates = (name, prefix + name)
        for candidate in candidates:
            bone = armature.data.bones.get(candidate)
            if bone:
                return bone
        return None
    if rename_bones:
        for bone in armature.data.bones:
            if bone.name.lower().startswith(prefix.lower()):
                bone.name = bone.name[len(prefix):]
    missing = [name for name in ("Hips", "Spine", "Spine1", "Spine2", "Neck", "Head", "LeftShoulder", "RightShoulder") if get(name) is None]
    if missing:
        return {"stage": stage, "path": str(path.relative_to(ROOT)).replace("\\", "/"), "armature": True,
                "missingBones": missing, "diagnosis": "Required landmarks cannot be measured from this skeleton."}
    def point(bone, which):
        co = bone.head_local if which == "head" else bone.tail_local
        return armature.matrix_world @ co
    def axis(bone, index):
        return norm(armature.matrix_world.to_3x3() @ bone.matrix_local.to_3x3().col[index])
    hips, spine, spine1, spine2, neck, head = [get(n) for n in ("Hips", "Spine", "Spine1", "Spine2", "Neck", "Head")]
    left, right = get("LeftShoulder"), get("RightShoulder")
    up = norm(point(neck, "head") - point(hips, "head"))
    lateral = norm(point(right, "head") - point(left, "head"))
    torso_front = norm(up.cross(lateral))
    front = SOURCE_FRONT.copy()
    if apply_adapter_yaw:
        front.rotate(armature.matrix_world.to_quaternion())
        front = norm(front)
    hip_axes = [axis(hips, i) for i in range(3)]
    head_axes = [axis(head, i) for i in range(3)]
    hip_axis_i = max(range(3), key=lambda i: abs(hip_axes[i].dot(front)))
    head_axis_i = max(range(3), key=lambda i: abs(head_axes[i].dot(front)))
    hip_forward = hip_axes[hip_axis_i]
    head_forward = head_axes[head_axis_i]
    if hip_forward.dot(front) < 0:
        hip_forward.negate()
    if head_forward.dot(front) < 0:
        head_forward.negate()
    shoulder_width = (point(right, "head") - point(left, "head")).length
    shoulder_height_delta = abs(point(right, "head").z - point(left, "head").z)
    # Compare projected bone-roll axes around the local trunk-up axis.
    base_x = axis(hips, 0)
    rolls = {}
    for name, bone in (("Spine", spine), ("Spine1", spine1), ("Spine2", spine2), ("Neck", neck), ("Head", head)):
        current_x = axis(bone, 0)
        base_projected = norm(base_x - up * base_x.dot(up))
        current_projected = norm(current_x - up * current_x.dot(up))
        signed = math.degrees(math.atan2(up.dot(base_projected.cross(current_projected)), base_projected.dot(current_projected)))
        rolls[name] = signed
    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH" and o.data.vertices and o.name != "Icosphere"]
    boxes = []
    for obj in meshes:
        boxes.extend(obj.matrix_world @ Vector(c) for c in obj.bound_box)
    if boxes:
        minimum = [min(p[i] for p in boxes) for i in range(3)]
        maximum = [max(p[i] for p in boxes) for i in range(3)]
        height = maximum[2] - minimum[2]
    else:
        minimum = maximum = [0.0, 0.0, 0.0]
        height = 0.0
    return {
        "stage": stage, "path": str(path.relative_to(ROOT)).replace("\\", "/"), "armature": True,
        "appliedAdapterYawDegrees": math.degrees(YAW) if apply_adapter_yaw else 0.0,
        "boneNamesRenamedOnly": rename_bones,
        "sourceFaceForwardWorld": list(front), "torsoForwardWorld": list(torso_front),
        "hipLocalForwardAxisIndex": hip_axis_i, "headLocalForwardAxisIndex": head_axis_i,
        "headToHipForwardDisagreementDegrees": angle(head_forward, hip_forward),
        "headToTorsoForwardDisagreementDegrees": angle(head_forward, torso_front),
        "shoulderToHipFacingDisagreementDegrees": angle(torso_front, hip_forward),
        "spineRollDegrees": rolls,
        "maxAbsoluteSpineRollDegrees": max(abs(v) for v in rolls.values()),
        "shoulderHeightDeltaMeters": shoulder_height_delta, "shoulderWidthMeters": shoulder_width,
        "shoulderHeightDeltaRatio": shoulder_height_delta / shoulder_width if shoulder_width else None,
        "worldBoundsMeters": {"min": minimum, "max": maximum, "height": height},
        "meshArmatureRelationships": [{"mesh": o.name, "parent": o.parent.name if o.parent else None,
                                        "armatureModifiers": [m.object.name for m in o.modifiers if m.type == "ARMATURE" and m.object]}
                                       for o in meshes],
        "neutralPoseDeviationDegrees": {name: math.degrees(math.sqrt(sum(v*v for v in pose_bone.rotation_euler)))
                                        if (pose_bone := bpy.context.scene.objects.get("Armature").pose.bones.get(prefix+name)
                                            or bpy.context.scene.objects.get("Armature").pose.bones.get(name))
                                        else None for name in ("Hips", "Spine", "Spine1", "Spine2", "Neck", "Head")},
        "missingBones": missing
    }


def main():
    stages = [
        ("A_mixamo_rigged_source", ASSET / "generated-rigged.glb", False, False),
        ("B_facial_converted_before_preprocess", ASSET / "vela-photoreal-faced.glb", False, False),
        ("C_bone_renaming_only", ASSET / "vela-photoreal-faced.glb", False, True),
        ("D_adapter_minus_90_yaw", ASSET / "vela-photoreal-faced.glb", True, True),
    ]
    records = [measure(path, stage, yaw, rename) for stage, path, yaw, rename in stages]
    print(json.dumps({"measurements": records}, indent=2))


if __name__ == "__main__":
    main()
