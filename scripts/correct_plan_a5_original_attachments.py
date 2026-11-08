"""Raycast Goal-1 image landmarks onto an original GLB with audited alignment.

This corrects the known female rigged/original vertical-origin mismatch without
changing the donor video landmarks or the original GLB.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy
from mathutils import Vector


def bounds(obj):
    pts = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    return Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts))), Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))


def barycentric(point, a, b, c):
    v0, v1, v2 = b - a, c - a, point - a
    d00, d01, d11 = v0.dot(v0), v0.dot(v1), v1.dot(v1)
    d20, d21 = v2.dot(v0), v2.dot(v1)
    den = d00 * d11 - d01 * d01
    if abs(den) < 1e-18:
        return None
    v = (d11 * d20 - d01 * d21) / den
    w = (d00 * d21 - d01 * d20) / den
    return [float(1 - v - w), float(v), float(w)]


def main():
    argv = sys.argv[sys.argv.index("--") + 1 :]
    def arg(name): return Path(argv[argv.index(name) + 1]).resolve()
    source_report = arg("--source-report")
    target_glb = arg("--target-glb")
    output = arg("--output")
    source = json.loads(source_report.read_text(encoding="utf-8"))
    source_glb = Path(source["sourceGLB"]).resolve()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(source_glb))
    source_mesh = max([o for o in bpy.context.scene.objects if o.type == "MESH"], key=lambda o: len(o.data.vertices))
    src_min, src_max = bounds(source_mesh)
    for obj in list(bpy.context.scene.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    bpy.ops.import_scene.gltf(filepath=str(target_glb))
    target_mesh = max([o for o in bpy.context.scene.objects if o.type == "MESH"], key=lambda o: len(o.data.vertices))
    tgt_min, tgt_max = bounds(target_mesh)
    source_center = (src_min + src_max) * 0.5
    target_center = (tgt_min + tgt_max) * 0.5
    shift = source_center - target_center
    target_mesh.location += shift
    scene = bpy.context.scene
    depsgraph = bpy.context.evaluated_depsgraph_get()
    cam = source["camera"]
    camera_location = Vector(cam["cameraLocation"])
    target = Vector(cam["target"])
    rotation = (target - camera_location).to_track_quat("-Z", "Y")
    right = rotation @ Vector((1, 0, 0))
    up = rotation @ Vector((0, 1, 0))
    forward = rotation @ Vector((0, 0, -1))
    ortho = float(cam["orthoScale"])
    records = []
    for old in source["records"]:
        u, v = float(old["imageXY"][0]) / 640.0, float(old["imageXY"][1]) / 640.0
        origin = camera_location + right * ((u - 0.5) * ortho) + up * ((0.5 - v) * ortho)
        hit, hit_location, normal, face_index, hit_object, _ = scene.ray_cast(depsgraph, origin, forward, distance=100.0)
        row = {"index": int(old["index"]), "imageXY": old["imageXY"], "meshXYZ": None, "triangleIndex": None, "triangleVertexIndices": None, "barycentricCoordinates": None, "surfaceNormal": None, "frontSurface": False, "hitObject": hit_object.name if hit and hit_object else None}
        if hit and hit_object == target_mesh and face_index < len(target_mesh.data.polygons):
            poly = target_mesh.data.polygons[face_index]
            verts = list(poly.vertices)
            if len(verts) >= 3:
                world = [target_mesh.matrix_world @ target_mesh.data.vertices[i].co for i in verts[:3]]
                weights = barycentric(hit_location, *world)
                facing = float(normal.normalized().dot((camera_location - hit_location).normalized()))
                local_hit = target_mesh.matrix_world.inverted() @ hit_location
                visible = bool(facing > 0.05 or old.get("surfaceVisibleFromFrontalCamera", False))
                row.update({"meshXYZ": list(local_hit), "triangleIndex": int(face_index), "triangleVertexIndices": [int(i) for i in verts[:3]], "barycentricCoordinates": weights, "surfaceNormal": list(normal), "frontSurface": visible, "frontNormalFacingDot": facing, "hitObject": target_mesh.name})
        records.append(row)
    out = {"sourceGLB": str(target_glb), "sourceGoal1Report": str(source_report), "alignmentSourceGLB": str(source_glb), "alignmentTranslationApplied": list(shift), "records": records, "validFrontSurfaceHits": sum(bool(r["frontSurface"] and r["meshXYZ"] is not None and r["barycentricCoordinates"] is not None) for r in records), "attachmentMethod": "Goal-1 image landmarks raycast onto original GLB after automatically measured source/target world-bounds alignment", "goal1Unmodified": True}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"validFrontSurfaceHits": out["validFrontSurfaceHits"], "records": len(records), "translation": list(shift)}))


if __name__ == "__main__":
    main()
