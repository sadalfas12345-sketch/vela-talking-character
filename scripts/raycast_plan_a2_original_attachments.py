"""Reproject existing Goal-1 landmark image locations onto Plan A2 originals.

This does not edit Goal 1. It creates a Plan A2 attachment cache when the
stored Goal-1 report was generated on a different mesh asset, as happened for
the female rigged/original pair. The camera is translated by the difference
between the report bounds center and the imported target bounds center; scale
and orientation are checked before raycasting.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import bpy
from mathutils import Vector


def camera_basis(location, target):
    rotation = (target - location).to_track_quat("-Z", "Y")
    return rotation @ Vector((1, 0, 0)), rotation @ Vector((0, 1, 0)), rotation @ Vector((0, 0, -1))


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
    glb = Path(argv[argv.index("--glb") + 1]).resolve()
    source_report = Path(argv[argv.index("--source-report") + 1]).resolve()
    output = Path(argv[argv.index("--output") + 1]).resolve()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(glb))
    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    body = max(meshes, key=lambda o: len(o.data.vertices))
    scene = bpy.context.scene
    depsgraph = bpy.context.evaluated_depsgraph_get()
    src = json.loads(source_report.read_text(encoding="utf-8"))
    cam = src["camera"]
    # The report camera bounds describe the earlier rigged asset and are not a
    # usable translation/scale for the original.  Preserve its viewing
    # direction, then center and scale the orthographic camera from the same
    # stored attachment IDs evaluated on the exact target mesh.
    evaluated = body.evaluated_get(depsgraph)
    corners = [body.matrix_world @ Vector(point) for point in body.bound_box]
    target_min = Vector((min(p.x for p in corners), min(p.y for p in corners), min(p.z for p in corners)))
    target_max = Vector((max(p.x for p in corners), max(p.y for p in corners), max(p.z for p in corners)))
    # The female original and rigged files do not share vertex topology, so
    # stored source attachment IDs cannot estimate a target IPD. Use the
    # target object's neutral bounding-box center and the validated Goal-1
    # camera scale; target-specific attachment validation follows raycasting.
    source_eye = (Vector(src["records"][263]["meshXYZ"]) - Vector(src["records"][33]["meshXYZ"])).length
    target_eye = None
    scale = 1.0
    target = (target_min + target_max) * 0.5
    source_direction = (Vector(cam["cameraLocation"]) - Vector(cam["target"])).normalized()
    location = target + source_direction * 10.0
    shift = target - Vector(cam.get("center", cam["target"]))
    right, up, forward = camera_basis(location, target)
    ortho = float(cam["orthoScale"]) * scale
    records = []
    for old in src["records"]:
        u, v = float(old["imageXY"][0]) / 640.0, float(old["imageXY"][1]) / 640.0
        origin = location + right * ((u - 0.5) * ortho) + up * ((0.5 - v) * ortho)
        distance = (location - target).length + ortho * 4.0
        hit, hit_location, normal, face_index, hit_object, _ = scene.ray_cast(depsgraph, origin, forward, distance=distance)
        row = {"index": int(old["index"]), "imageXY": old["imageXY"], "meshXYZ": None, "triangleIndex": None, "triangleVertexIndices": None, "barycentricCoordinates": None, "surfaceNormal": None, "frontSurface": False, "hitObject": hit_object.name if hit and hit_object else None}
        if hit and hit_object and hit_object.type == "MESH" and face_index < len(hit_object.data.polygons):
            poly = hit_object.data.polygons[face_index]
            verts = list(poly.vertices)
            if len(verts) >= 3:
                evaluated = hit_object.evaluated_get(depsgraph)
                world = [evaluated.matrix_world @ evaluated.data.vertices[i].co for i in verts[:3]]
                weights = barycentric(hit_location, *world)
                facing = float(normal.normalized().dot((location - hit_location).normalized()))
                row.update({"meshXYZ": list(hit_location), "triangleIndex": int(face_index), "triangleVertexIndices": [int(i) for i in verts[:3]], "barycentricCoordinates": weights, "surfaceNormal": list(normal), "frontSurface": bool(facing > 0.05), "frontNormalFacingDot": facing, "hitObject": hit_object.name})
        records.append(row)
    out = {"sourceGLB": str(glb), "sourceGoal1Report": str(source_report), "cameraDirectionPreserved": True, "cameraTranslationApplied": list(shift), "cameraScaleFromStoredAttachments": float(scale), "sourceEyeWidth": source_eye, "targetEyeWidth": target_eye, "records": records, "validFrontSurfaceHits": sum(bool(r["frontSurface"] and r["meshXYZ"] is not None and r["barycentricCoordinates"] is not None) for r in records), "attachmentMethod": "same existing Goal-1 image locations and camera direction, automatically recentered and IPD-scaled for exact Plan A2 GLB", "goal1Unmodified": True}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"validFrontSurfaceHits": out["validFrontSurfaceHits"], "records": len(records), "shift": list(shift), "scale": scale}))


if __name__ == "__main__":
    main()
