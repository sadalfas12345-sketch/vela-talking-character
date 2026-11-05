import json
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector

root = Path(__file__).resolve().parents[1]
avatar = root / 'TalkingHead' / 'avatars' / 'avaturn.glb'
tripo = root / 'assets' / 'tripo' / 'vela-photoreal' / 'generated-rigged.glb'
avatar_lm = json.loads((root / 'verification' / 'avaturn-face-fit-landmarks.json').read_text())['landmarks']
target_lm = json.loads((root / 'assets' / 'tripo' / 'vela-photoreal' / 'landmarks.json').read_text())['landmarks']
out = root / 'verification' / 'avaturn-face-fit-landmark-points.json'

def clear():
    bpy.ops.wm.read_factory_settings(use_empty=True)

def ray_points(path, landmarks, camera_location, camera_target, ortho_scale, only_name=None):
    global donor_face_ids, donor_barycentric, donor_triangles
    clear()
    bpy.ops.import_scene.gltf(filepath=str(path))
    scene = bpy.context.scene
    meshes = [o for o in scene.objects if o.type == 'MESH']
    if only_name:
        target_obj = next((o for o in meshes if o.name == only_name), None)
        if target_obj is None:
            raise RuntimeError(f'Mesh {only_name} not found in {path.name}')
        for obj in scene.objects:
            if obj != target_obj:
                obj.hide_set(True)
    else:
        main = next(o for o in meshes if o.name != 'Icosphere')
        for obj in scene.objects:
            if obj.type == 'MESH' and obj != main:
                obj.hide_set(True)
    cam_data = bpy.data.cameras.new('fit camera')
    camera = bpy.data.objects.new('fit camera', cam_data)
    scene.collection.objects.link(camera)
    camera.location = camera_location
    camera.rotation_euler = (Vector(camera_target) - camera.location).to_track_quat('-Z', 'Y').to_euler()
    cam_data.type = 'ORTHO'
    cam_data.ortho_scale = ortho_scale
    scene.camera = camera
    rotation = camera.rotation_euler.to_quaternion()
    right = rotation @ Vector((1, 0, 0))
    up = rotation @ Vector((0, 1, 0))
    toward = rotation @ Vector((0, 0, 1))
    ray = rotation @ Vector((0, 0, -1))
    depsgraph = bpy.context.evaluated_depsgraph_get()
    result = np.full((len(landmarks), 3), np.nan, dtype=np.float64)
    face_ids = np.full(len(landmarks), -1, dtype=np.int32)
    barycentric = np.full((len(landmarks), 3), np.nan, dtype=np.float64)
    for i, (u, v, _z) in enumerate(landmarks):
        origin = camera.location + right * ((u - 0.5) * ortho_scale) + up * ((0.5 - v) * ortho_scale)
        hit, location, _normal, face_index, hit_obj, _matrix = scene.ray_cast(depsgraph, origin, ray, distance=5.0)
        if hit:
            result[i] = location[:]
            if only_name and hit_obj.name == only_name:
                polygon = hit_obj.data.polygons[face_index]
                if len(polygon.vertices) != 3:
                    raise RuntimeError(f'Expected triangulated donor facial mesh; polygon {face_index} has {len(polygon.vertices)} vertices')
                ids = list(polygon.vertices)
                tri = np.asarray([(hit_obj.matrix_world @ hit_obj.data.vertices[j].co)[:] for j in ids], dtype=np.float64)
                a, b, c = tri
                v0, v1, v2 = b - a, c - a, np.asarray(location[:]) - a
                d00, d01, d11 = v0 @ v0, v0 @ v1, v1 @ v1
                d20, d21 = v2 @ v0, v2 @ v1
                denom = d00 * d11 - d01 * d01
                w1 = (d11 * d20 - d01 * d21) / denom
                w2 = (d00 * d21 - d01 * d20) / denom
                barycentric[i] = (1 - w1 - w2, w1, w2)
                face_ids[i] = face_index
    if only_name == 'Head_Mesh':
        export = {}
        wanted = {'Head_Mesh', 'Eye_Mesh', 'EyeAO_Mesh', 'Eyelash_Mesh', 'Teeth_Mesh', 'Tongue_Mesh'}
        for obj in meshes:
            if obj.name not in wanted:
                continue
            prefix = obj.name.replace('.', '_')
            base = np.asarray([(obj.matrix_world @ v.co)[:] for v in obj.data.vertices], dtype=np.float32)
            export[prefix + '__Basis'] = base
            tris = []
            for poly in obj.data.polygons:
                ids = list(poly.vertices)
                for j in range(1, len(ids) - 1):
                    tris.append((ids[0], ids[j], ids[j + 1]))
            export[prefix + '__Triangles'] = np.asarray(tris, dtype=np.int32)
            if obj.name == 'Head_Mesh':
                donor_triangles = np.asarray(tris, dtype=np.int32)
            keys = obj.data.shape_keys.key_blocks if obj.data.shape_keys else []
            export[prefix + '__KeyNames'] = np.asarray([k.name for k in keys], dtype='U64')
            for key in keys[1:]:
                coords = np.asarray([(obj.matrix_world @ v.co)[:] for v in key.data], dtype=np.float32)
                export[prefix + '__Key__' + key.name] = coords
        np.savez_compressed(root / 'verification' / 'avaturn-face-fit-source-meshes.npz', **export)
        if only_name == 'Head_Mesh':
            donor_face_ids, donor_barycentric = face_ids, barycentric
    return result

donor = ray_points(avatar, avatar_lm, (0, -1, 1.71), (0, 0, 1.71), 0.42, 'Head_Mesh')
target = ray_points(tripo, target_lm, (1, 0, 0.82), (0, 0, 0.82), 0.20)
payload = {
    'method': 'Independent MediaPipe landmark rays against the donor Head_Mesh and original Tripo GLB in Blender world space.',
    'donorValid': int(np.isfinite(donor[:, 0]).sum()),
    'targetValid': int(np.isfinite(target[:, 0]).sum()),
    'donorPoints': donor.tolist(), 'targetPoints': target.tolist(),
    'donorFaceIds': donor_face_ids.tolist(), 'donorBarycentric': donor_barycentric.tolist(),
    'donorTrianglesAtLandmarks': donor_triangles[donor_face_ids].tolist(),
}
def json_safe(value):
    if isinstance(value, dict):
        return {key: json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_safe(item) for item in value]
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value

payload = json_safe(payload)
out.write_text(json.dumps(payload, separators=(',', ':'), allow_nan=False) + '\n', encoding='utf-8')
print(json.dumps({'donorValid': payload['donorValid'], 'targetValid': payload['targetValid'], 'landmarkTriangleMappings': len(payload['donorTrianglesAtLandmarks'])}, indent=2))
