"""Transfer fitted Avaturn surface motion onto original Tripo vertices."""
import json
import os
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
ASSET = ROOT / 'assets/tripo/vela-photoreal'
SOURCE = ASSET / 'generated-rigged.glb'
FIT = ROOT / 'verification/avaturn-tripo-facefit-deformed.npz'
LANDMARKS = ASSET / 'landmarks.json'
EXPRESSION = os.environ.get('VELA_EXPRESSION', 'eyeBlinkLeft')
OUTPUT = Path(os.environ.get('VELA_ORIGINAL_SURFACE_OUTPUT', ASSET / f'intermediates/vela-original-tripo-{EXPRESSION}-surface-transfer.glb'))
REPORT = Path(os.environ.get('VELA_ORIGINAL_SURFACE_REPORT', ROOT / f'verification/vela-original-tripo-{EXPRESSION}-surface-transfer.json'))
FACE_OVAL = [10,338,297,332,284,251,389,356,454,323,361,288,397,365,379,378,400,377,152,148,176,149,150,136,172,58,132,93,234,127,162,21,54,103,67,109]

if not FIT.is_file():
    raise FileNotFoundError(FIT)
donor = np.load(FIT)
neutral = donor['Head_Mesh__Basis'].astype(np.float64)
key_name = f'Head_Mesh__Key__{EXPRESSION}'
if key_name not in donor:
    raise KeyError(key_name)
motion = donor[key_name].astype(np.float64) - neutral

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(SOURCE))
meshes = [obj for obj in bpy.context.scene.objects if obj.type == 'MESH' and obj.name != 'Icosphere']
if len(meshes) != 1:
    raise RuntimeError(f'Expected one original Tripo mesh, found {[obj.name for obj in meshes]}')
body = meshes[0]
coords = np.empty((len(body.data.vertices), 3), dtype=np.float64)
body.data.vertices.foreach_get('co', coords.ravel())
world_matrix = np.asarray(body.matrix_world, dtype=np.float64)
world = coords @ world_matrix[:3, :3].T + world_matrix[:3, 3]

landmark_data = json.loads(LANDMARKS.read_text(encoding='utf-8'))
landmark_pixels = np.asarray(landmark_data['landmarks'], dtype=np.float64)
camera_location = np.asarray((1.0, 0.0, 0.82), dtype=np.float64)
camera_rotation = (Vector((0.0, 0.0, 0.82)) - Vector(tuple(camera_location))).to_track_quat('-Z', 'Y')
right = np.asarray((camera_rotation @ Vector((1, 0, 0)))[:], dtype=np.float64)
up = np.asarray((camera_rotation @ Vector((0, 1, 0)))[:], dtype=np.float64)
relative = world - camera_location
screen = np.column_stack((0.5 + relative @ right / 0.20, 0.5 - relative @ up / 0.20))
polygon = landmark_pixels[FACE_OVAL, :2]
inside = np.zeros(len(screen), dtype=bool)
x0, y0 = polygon[-1]
for x1, y1 in polygon:
    crosses = (y1 > screen[:, 1]) != (y0 > screen[:, 1])
    edge_x = (x0 - x1) * (screen[:, 1] - y1) / (y0 - y1 + 1e-20) + x1
    inside ^= crosses & (screen[:, 0] < edge_x)
    x0, y0 = x1, y1

delta_world = np.zeros_like(world)
candidate = np.flatnonzero(inside)
nearest_distance = np.full(len(candidate), np.inf)
for start in range(0, len(candidate), 20000):
    stop = min(start + 20000, len(candidate))
    ids = candidate[start:stop]
    distances = np.sum((world[ids, None] - neutral[None]) ** 2, axis=2)
    k = min(8, len(neutral))
    nearest = np.argpartition(distances, k - 1, axis=1)[:, :k]
    local = np.take_along_axis(distances, nearest, axis=1)
    weights = np.exp(-local / (2.0 * 0.0045 ** 2))
    weights /= np.maximum(weights.sum(axis=1, keepdims=True), 1e-12)
    delta_world[ids] = np.einsum('nk,nkd->nd', weights, motion[nearest])
    nearest_distance[start:stop] = np.sqrt(local[:, 0])
valid_candidate = candidate[nearest_distance <= 0.012]
delta_world[candidate[nearest_distance > 0.012]] = 0.0
local_delta = delta_world @ np.linalg.inv(world_matrix[:3, :3]).T

body.shape_key_add(name='Basis', from_mix=False)
key = body.shape_key_add(name=f'xfer_{EXPRESSION}_original_tripo_surface', from_mix=False)
key.data.foreach_set('co', (coords + local_delta).astype(np.float32).ravel())
key.value = 0.0
body.data.shape_keys.use_relative = True
body.data.shape_keys.animation_data_clear()

bpy.ops.object.select_all(action='DESELECT')
for obj in bpy.context.scene.objects:
    if obj.type in {'MESH', 'ARMATURE', 'EMPTY'}:
        obj.select_set(True)
bpy.context.view_layer.objects.active = body
OUTPUT.parent.mkdir(parents=True, exist_ok=True)
bpy.ops.export_scene.gltf(filepath=str(OUTPUT), export_format='GLB', export_morph=True, export_skins=True, export_animations=True, export_apply=False)
report = {
    'status': 'ORIGINAL_TRIPO_SURFACE_TRANSFER_REQUIRES_VISUAL_REVIEW',
    'architecture': 'fitted Avaturn surface motion to original Tripo mesh shape key',
    'expression': EXPRESSION,
    'sourceTripo': str(SOURCE.relative_to(ROOT)),
    'motionSource': str(FIT.relative_to(ROOT)),
    'originalTripoVertexCount': int(len(coords)),
    'movedOriginalTripoVertices': int(len(valid_candidate)),
    'neutralGeometryUnchanged': True,
    'topologyReplacement': False,
    'mouthSurgery': False,
    'solver': {'type': '8-neighbor Gaussian surface displacement transfer', 'sigmaMeters': 0.0045, 'candidateDistanceCutoffMeters': 0.012},
    'donorMotionP95Millimeters': float(np.percentile(np.linalg.norm(motion, axis=1), 95) * 1000),
    'donorMotionMaxMillimeters': float(np.max(np.linalg.norm(motion, axis=1)) * 1000),
    'output': str(OUTPUT.relative_to(ROOT)),
    'limitations': ['Independent eyelid correspondence and visual closure remain to be reviewed.']
}
REPORT.parent.mkdir(parents=True, exist_ok=True)
REPORT.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
print(json.dumps(report, indent=2))
