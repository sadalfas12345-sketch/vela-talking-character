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
LANDMARKS = CALIBRATION["landmarks3d"]


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
    world_up = Vector((0.0, 0.0, 1.0))
    torso_front = norm(world_up.cross(lateral))
    front = SOURCE_FRONT.copy()
    if apply_adapter_yaw:
        front.rotate(armature.matrix_world.to_quaternion())
        front = norm(front)
    # Anatomical face-forward comes from independently registered facial
    # landmarks. A Mixamo Head bone's local axes encode its bind frame, not
    # necessarily the visible face normal.
    def landmark(name):
        p = LANDMARKS[name]
        return armature.matrix_world @ Vector((p[0], p[1], p[2]))
    # Eye outer corners lie on different depths along the curved face. Use
    # centers of the upper/lower eyelid landmarks to estimate the eye line.
    left_eye_center = (landmark("eye_top_left") + landmark("eye_bottom_left")) * 0.5
    right_eye_center = (landmark("eye_top_right") + landmark("eye_bottom_right")) * 0.5
    eye_lateral = norm(right_eye_center - left_eye_center)
    face_up = norm((landmark("brow_left") + landmark("brow_right")) * 0.5 - landmark("chin"))
    face_forward = norm(face_up.cross(eye_lateral))
    if face_forward.dot(front) < 0:
        face_forward.negate()
    # Anatomical hip facing is recovered from the pelvis-to-shoulder axis and
    # the left/right hip-joint line, not a guessed Mixamo local bone axis.
    left_hip, right_hip = get("LeftUpLeg"), get("RightUpLeg")
    hip_lateral = norm(point(right_hip, "head") - point(left_hip, "head"))
    hip_forward = norm(world_up.cross(hip_lateral))
    if hip_forward.dot(front) < 0:
        hip_forward.negate()
    shoulder_width = (point(right, "head") - point(left, "head")).length
    shoulder_height_delta = abs(point(right, "head").z - point(left, "head").z)
    # Compare actual anatomical cross-sections of pelvis and shoulders. This
    # detects a twisted trunk without assuming that bone local X means left.
    shoulder_lateral = norm(point(right, "head") - point(left, "head"))
    pelvis_projected = norm(hip_lateral - world_up * hip_lateral.dot(world_up))
    shoulder_projected = norm(shoulder_lateral - world_up * shoulder_lateral.dot(world_up))
    trunk_twist = math.degrees(math.atan2(world_up.dot(pelvis_projected.cross(shoulder_projected)), pelvis_projected.dot(shoulder_projected)))
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
        "headForwardMethod": "registered brow/chin vertical crossed with left/right eye line",
        "headAnatomicalForwardWorld": list(face_forward), "hipAnatomicalForwardWorld": list(hip_forward),
        "headToHipForwardDisagreementDegrees": angle(face_forward, hip_forward),
        "headToTorsoForwardDisagreementDegrees": angle(face_forward, torso_front),
        "shoulderToHipFacingDisagreementDegrees": angle(torso_front, hip_forward),
        "spineRollMethod": "signed angle between pelvis and shoulder anatomical lateral axes around torso-up",
        "spineRollDegrees": {"pelvisToShoulders": trunk_twist},
        "maxAbsoluteSpineRollDegrees": abs(trunk_twist),
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
    result = {"measurements": records}
    output = ROOT / "verification" / "tripo-gate2-orientation.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
