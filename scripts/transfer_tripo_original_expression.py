"""Transfer one Avaturn expression onto the original Tripo mesh vertices.

This proof deliberately imports no donor geometry and cuts no Tripo faces. It
uses Avaturn only as a source of neutral-to-expression landmark displacement.
"""
import json
import os
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
ASSET = ROOT / 'assets/tripo/vela-photoreal'
SOURCE = ASSET / 'generated-rigged.glb'
POINTS = ROOT / 'verification/avaturn-face-fit-landmark-points.json'
FIT_REPORT = ROOT / 'verification/avaturn-tripo-facefit-report.json'
DONOR_MESHES = ROOT / 'verification/avaturn-face-fit-source-meshes.npz'
LANDMARKS = ASSET / 'landmarks.json'
EXPRESSION = os.environ.get('VELA_EXPRESSION', 'jawOpen')
OUTPUT = Path(os.environ.get(
    'VELA_ORIGINAL_TRANSFER_OUTPUT',
    ASSET / f'intermediates/vela-original-tripo-{EXPRESSION}-transfer-proof.glb'))
REPORT = Path(os.environ.get(
    'VELA_ORIGINAL_TRANSFER_REPORT',
    ROOT / f'verification/vela-original-tripo-{EXPRESSION}-transfer-proof.json'))

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

if not all(path.is_file() for path in (SOURCE, POINTS, FIT_REPORT, DONOR_MESHES, LANDMARKS)):
    raise FileNotFoundError('Original Tripo, donor calibration, and landmark files are required.')

points = json.loads(POINTS.read_text(encoding='utf-8'))
donor_points = np.asarray(points['donorPoints'], dtype=np.float64)
target_points = np.asarray(points['targetPoints'], dtype=np.float64)
face_ids = np.asarray(points['donorFaceIds'], dtype=np.int32)
bary = np.asarray(points['donorBarycentric'], dtype=np.float64)
valid = np.isfinite(donor_points[:, 0]) & np.isfinite(target_points[:, 0]) & (face_ids >= 0)
rows = np.flatnonzero(valid)

fit_report = json.loads(FIT_REPORT.read_text(encoding='utf-8'))
scale = float(fit_report['similarity']['scale'])
rotation = np.asarray(fit_report['similarity']['rotation'], dtype=np.float64)
donor_data = np.load(DONOR_MESHES)
donor_basis = donor_data['Head_Mesh__Basis'].astype(np.float64)
donor_triangles = donor_data['Head_Mesh__Triangles'].astype(np.int32)
donor_shape_key = f'Head_Mesh__Key__{EXPRESSION}'
if donor_shape_key not in donor_data:
    raise KeyError(f'Avaturn source expression is unavailable: {EXPRESSION}')
donor_expression = donor_data[donor_shape_key].astype(np.float64)

handle_faces = donor_triangles[face_ids[rows]]
donor_neutral_landmarks = np.einsum('ni,nij->nj', bary[rows], donor_basis[handle_faces])
donor_expression_landmarks = np.einsum('ni,nij->nj', bary[rows], donor_expression[handle_faces])
landmark_displacements = scale * (donor_expression_landmarks - donor_neutral_landmarks) @ rotation
target_handles = target_points[rows]

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(SOURCE))
meshes = [obj for obj in bpy.context.scene.objects if obj.type == 'MESH' and obj.name != 'Icosphere']
if len(meshes) != 1:
    raise RuntimeError(f'Expected one original Tripo character mesh, found {[obj.name for obj in meshes]}')
body = meshes[0]
coords = np.empty((len(body.data.vertices), 3), dtype=np.float64)
body.data.vertices.foreach_get('co', coords.ravel())
world_matrix = np.asarray(body.matrix_world, dtype=np.float64)
world = coords @ world_matrix[:3, :3].T + world_matrix[:3, 3]

landmark_data = json.loads(LANDMARKS.read_text(encoding='utf-8'))
landmark_pixels = np.asarray(landmark_data['landmarks'], dtype=np.float64)
camera_location = np.asarray((1.0, 0.0, 0.82), dtype=np.float64)
camera_target = np.asarray((0.0, 0.0, 0.82), dtype=np.float64)
camera_rotation = (Vector(tuple(camera_target)) - Vector(tuple(camera_location))).to_track_quat('-Z', 'Y')
right = np.asarray((camera_rotation @ Vector((1, 0, 0)))[:], dtype=np.float64)
up = np.asarray((camera_rotation @ Vector((0, 1, 0)))[:], dtype=np.float64)
forward = np.asarray((camera_rotation @ Vector((0, 0, -1)))[:], dtype=np.float64)
polygon = landmark_pixels[FACE_OVAL, :2]
screen_rel = world - camera_location
screen = np.column_stack((0.5 + screen_rel @ right / 0.20,
                          0.5 - screen_rel @ up / 0.20,
                          screen_rel @ forward))
handle_screen = np.column_stack((0.5 + (target_handles - camera_location) @ right / 0.20,
                                 0.5 - (target_handles - camera_location) @ up / 0.20,
                                 (target_handles - camera_location) @ forward))
inside = point_in_polygon(screen[:, 0], screen[:, 1], polygon)
target_depth = handle_screen[:, 2]
nearest = np.empty(len(screen), dtype=np.int32)
for start in range(0, len(screen), 20000):
    ids = slice(start, min(start + 20000, len(screen)))
    distance_sq = np.sum((screen[ids, None, :2] - handle_screen[None, :, :2]) ** 2, axis=2)
    nearest[start:ids.stop] = np.argmin(distance_sq, axis=1)
depth_tolerance = max(float(np.linalg.norm((landmark_pixels[33, :2] - landmark_pixels[263, :2]) * 0.20)) * 0.48, 0.004)
face_vertices = np.flatnonzero(inside & (np.abs(screen[:, 2] - target_depth[nearest]) <= depth_tolerance))

# Local RBF field over the original Tripo vertices. Handles are anatomical
# target points; only the measured Tripo face surface is allowed to move.
delta_world = np.zeros_like(world)
sigma = max(float(np.linalg.norm((landmark_pixels[33, :2] - landmark_pixels[263, :2]) * 0.20)) * 0.35, 0.012)
for start in range(0, len(face_vertices), 20000):
    ids = face_vertices[start:start + 20000]
    distance_sq = np.sum((world[ids, None] - target_handles[None]) ** 2, axis=2)
    k = min(24, len(rows))
    nearest_k = np.argpartition(distance_sq, k - 1, axis=1)[:, :k]
    local_distance = np.take_along_axis(distance_sq, nearest_k, axis=1)
    weights = np.exp(-local_distance / (2.0 * sigma * sigma))
    weights /= np.maximum(weights.sum(axis=1, keepdims=True), 1e-12)
    delta_world[ids] = np.einsum('nk,nkd->nd', weights, landmark_displacements[nearest_k])

local_delta = delta_world @ np.linalg.inv(world_matrix[:3, :3]).T
body.shape_key_add(name='Basis', from_mix=False)
key = body.shape_key_add(name=f'xfer_{EXPRESSION}_original_tripo', from_mix=False)
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
bpy.ops.export_scene.gltf(filepath=str(OUTPUT), export_format='GLB', export_morph=True,
                          export_skins=True, export_animations=True, export_apply=False)

report = {
    'status': 'ORIGINAL_TRIPO_VERTEX_TRANSFER_PROOF_REQUIRES_REVIEW',
    'architecture': 'Avaturn motion source -> RBF displacement field -> original Tripo mesh shape key',
    'sourceTripo': str(SOURCE.relative_to(ROOT)),
    'sourceDonorMotion': str(DONOR_MESHES.relative_to(ROOT)),
    'expression': EXPRESSION,
    'originalTripoVertexCount': int(len(coords)),
    'movedOriginalTripoVertices': int(len(face_vertices)),
    'neutralGeometryUnchanged': True,
    'topologyReplacement': False,
    'mouthSurgery': False,
    'solver': {'type': 'localized Gaussian RBF interpolation', 'handleCount': int(len(rows)), 'neighbors': 24, 'sigmaMeters': sigma},
    'donorLandmarkDisplacementMillimeters': {
        'median': float(np.median(np.linalg.norm(landmark_displacements, axis=1)) * 1000),
        'p95': float(np.percentile(np.linalg.norm(landmark_displacements, axis=1), 95) * 1000),
        'max': float(np.max(np.linalg.norm(landmark_displacements, axis=1)) * 1000),
    },
    'output': str(OUTPUT.relative_to(ROOT)),
    'limitations': ['This is the first original-Tripo deformation proof; independent held-out correspondence, articulation quality, and runtime gates remain unverified.'],
}
REPORT.parent.mkdir(parents=True, exist_ok=True)
REPORT.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
print(json.dumps(report, indent=2))
