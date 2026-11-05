"""Raycast MediaPipe points through a discovered orthographic camera in Blender."""
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector


def camera_basis(location, target):
    rotation = (target - location).to_track_quat('-Z', 'Y')
    return rotation @ Vector((1, 0, 0)), rotation @ Vector((0, 1, 0)), rotation @ Vector((0, 0, -1))


def barycentric(point, a, b, c):
    v0, v1, v2 = b - a, c - a, point - a
    d00, d01, d11 = v0.dot(v0), v0.dot(v1), v1.dot(v1)
    d20, d21 = v2.dot(v0), v2.dot(v1)
    den = d00 * d11 - d01 * d01
    if abs(den) < 1e-15:
        return None
    v = (d11 * d20 - d01 * d21) / den
    w = (d00 * d21 - d01 * d20) / den
    return [float(1.0 - v - w), float(v), float(w)]


def main():
    if len(sys.argv) < 4:
        raise SystemExit('Usage: blender -b --python raycast_goal1_discovered_camera.py -- model.glb camera.json output.json')
    glb = Path(sys.argv[-3]).resolve()
    camera_path = Path(sys.argv[-2]).resolve()
    output = Path(sys.argv[-1]).resolve()
    camera_data = json.loads(camera_path.read_text(encoding='utf-8'))
    landmarks_data = json.loads((camera_path.parent / 'detected-landmarks.json').read_text(encoding='utf-8'))
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(glb))
    scene = bpy.context.scene
    depsgraph = bpy.context.evaluated_depsgraph_get()
    location = Vector(camera_data['cameraLocation'])
    target = Vector(camera_data['target'])
    right, up, forward = camera_basis(location, target)
    ortho = float(camera_data['orthoScale'])
    records = []
    for index, point in enumerate(landmarks_data['landmarks']):
        u, v = float(point[0]), float(point[1])
        origin = location + right * ((u - 0.5) * ortho) + up * ((0.5 - v) * ortho)
        # The camera may be far from a tightly cropped head focus, especially
        # when a full-body rig provides the bounds.  Scale-only ray lengths can
        # terminate before reaching the mesh.  Use the actual calibrated
        # camera-to-target distance plus a crop-relative margin instead.
        ray_distance = (location - target).length + ortho * 2.0
        hit, hit_location, normal, face_index, hit_object, _ = scene.ray_cast(depsgraph, origin, forward, distance=ray_distance)
        record = {
            'index': index, 'imageXY': [u * 640.0, v * 640.0], 'meshXYZ': None,
            'triangleIndex': None, 'triangleVertexIndices': None, 'barycentricCoordinates': None,
            'surfaceNormal': None, 'frontSurface': False, 'surfaceVisibleFromFrontalCamera': bool(hit),
            'hitObject': hit_object.name if hit and hit_object else None,
        }
        if hit and hit_object and hit_object.type == 'MESH' and face_index < len(hit_object.data.polygons):
            polygon = hit_object.data.polygons[face_index]
            vertices = list(polygon.vertices)
            if len(vertices) >= 3:
                evaluated = hit_object.evaluated_get(depsgraph)
                world_vertices = [evaluated.matrix_world @ evaluated.data.vertices[v].co for v in vertices[:3]]
                weights = barycentric(hit_location, *world_vertices)
                to_camera = (location - hit_location).normalized()
                facing = float(normal.normalized().dot(to_camera))
                record.update({
                    'meshXYZ': list(hit_location), 'triangleIndex': int(face_index),
                    'triangleVertexIndices': [int(v) for v in vertices[:3]],
                    'barycentricCoordinates': weights, 'surfaceNormal': list(normal),
                    'frontNormalFacingDot': facing, 'frontSurface': bool(facing > 0.05),
                })
        records.append(record)
    report = {
        'sourceGLB': str(glb), 'camera': camera_data, 'detectedLandmarks': len(records),
        'frontalSurfaceHits': sum(r['surfaceVisibleFromFrontalCamera'] for r in records),
        'validFrontSurfaceHits': sum(r['frontSurface'] for r in records),
        'backOrAmbiguousHits': sum(r['surfaceVisibleFromFrontalCamera'] and not r['frontSurface'] for r in records),
        'unresolvedLandmarks': sum(not r['surfaceVisibleFromFrontalCamera'] for r in records),
        'records': records,
    }
    output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: report[k] for k in ('detectedLandmarks', 'frontalSurfaceHits', 'validFrontSurfaceHits', 'backOrAmbiguousHits', 'unresolvedLandmarks')}))


if __name__ == '__main__':
    main()
