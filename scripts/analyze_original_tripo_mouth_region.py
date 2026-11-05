"""Measure a localized lip-region candidate on the original Tripo mesh."""
import json
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'assets/tripo/vela-photoreal/generated-rigged.glb'
LANDMARKS = ROOT / 'assets/tripo/vela-photoreal/landmarks.json'
OUT = ROOT / 'verification/original-tripo-mouth-region-analysis.json'

LIP_OUTER = [61, 146, 91, 181, 84, 17, 314, 405, 321, 291,
             409, 270, 269, 267, 0, 37, 39, 40, 185]

def point_in_polygon(x, y, polygon):
    inside = np.zeros(x.shape, dtype=bool)
    x0, y0 = polygon[-1]
    for x1, y1 in polygon:
        crosses = (y1 > y) != (y0 > y)
        edge_x = (x0 - x1) * (y - y1) / (y0 - y1 + 1e-20) + x1
        inside ^= crosses & (x < edge_x)
        x0, y0 = x1, y1
    return inside

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
landmarks = np.asarray(json.loads(LANDMARKS.read_text(encoding='utf-8'))['landmarks'], dtype=np.float64)
camera_location = np.asarray((1.0, 0.0, 0.82), dtype=np.float64)
camera_rotation = (Vector((0.0, 0.0, 0.82)) - Vector(tuple(camera_location))).to_track_quat('-Z', 'Y')
right = np.asarray((camera_rotation @ Vector((1, 0, 0)))[:], dtype=np.float64)
up = np.asarray((camera_rotation @ Vector((0, 1, 0)))[:], dtype=np.float64)
forward = np.asarray((camera_rotation @ Vector((0, 0, -1)))[:], dtype=np.float64)
relative = world - camera_location
screen = np.column_stack((0.5 + relative @ right / 0.20,
                          0.5 - relative @ up / 0.20,
                          relative @ forward))
polygon = landmarks[LIP_OUTER, :2]
inside = point_in_polygon(screen[:, 0], screen[:, 1], polygon)
mouth_landmark_indices = np.asarray([61, 291, 13, 14, 78, 308, 95, 324, 82, 312, 87, 317], dtype=np.int32)
mouth_xy = landmarks[mouth_landmark_indices, :2]
nearest = np.empty(len(screen), dtype=np.int32)
for start in range(0, len(screen), 20000):
    stop = min(start + 20000, len(screen))
    distance_sq = np.sum((screen[start:stop, None, :2] - mouth_xy[None, :, :]) ** 2, axis=2)
    nearest[start:stop] = np.argmin(distance_sq, axis=1)
target_depth = np.full(len(mouth_landmark_indices), np.nan)
for i, landmark_index in enumerate(mouth_landmark_indices):
    pixel = landmarks[landmark_index, :2]
    distances = np.sum((screen[:, :2] - pixel[None, :]) ** 2, axis=1)
    target_depth[i] = screen[np.argmin(distances), 2]
ipd = float(np.linalg.norm((landmarks[33, :2] - landmarks[263, :2]) * 0.20))
depth_tolerance = max(ipd * 0.45, 0.004)
face_mask = inside & (np.abs(screen[:, 2] - target_depth[nearest]) <= depth_tolerance)

body.data.calc_loop_triangles()
selected_faces = []
edge_counts = {}
for triangle in body.data.loop_triangles:
    vertex_ids = tuple(int(v) for v in triangle.vertices)
    if not face_mask[list(vertex_ids)].all():
        continue
    center = world[list(vertex_ids)].mean(axis=0)
    center_screen = np.asarray((0.5 + (center - camera_location) @ right / 0.20,
                                0.5 - (center - camera_location) @ up / 0.20,
                                (center - camera_location) @ forward))
    if not point_in_polygon(np.asarray([center_screen[0]]), np.asarray([center_screen[1]]), polygon)[0]:
        continue
    selected_faces.append(vertex_ids)
    for a, b in ((vertex_ids[0], vertex_ids[1]), (vertex_ids[1], vertex_ids[2]), (vertex_ids[2], vertex_ids[0])):
        edge = tuple(sorted((a, b)))
        edge_counts[edge] = edge_counts.get(edge, 0) + 1
boundary_edges = [edge for edge, count in edge_counts.items() if count == 1]
boundary_vertices = np.unique(np.asarray(boundary_edges, dtype=np.int32).ravel()) if boundary_edges else np.empty(0, dtype=np.int32)
boundary_points = world[boundary_vertices] if len(boundary_vertices) else np.empty((0, 3))
report = {
    'status': 'LOCAL_MOUTH_REGION_MEASURED_REQUIRES_SURGERY_REVIEW',
    'source': str(SOURCE.relative_to(ROOT)),
    'originalVertexCount': int(len(world)),
    'lipLandmarkIndices': LIP_OUTER,
    'mouthLandmarkIndices': mouth_landmark_indices.tolist(),
    'ipdMeters': ipd,
    'depthToleranceMeters': depth_tolerance,
    'candidateVertices': int(face_mask.sum()),
    'candidateFaces': int(len(selected_faces)),
    'boundaryEdges': int(len(boundary_edges)),
    'boundaryVertices': int(len(boundary_vertices)),
    'boundaryBoundsMeters': [boundary_points.min(axis=0).tolist(), boundary_points.max(axis=0).tolist()] if len(boundary_points) else None,
    'boundaryScreenBounds': [screen[boundary_vertices, :2].min(axis=0).tolist(), screen[boundary_vertices, :2].max(axis=0).tolist()] if len(boundary_vertices) else None,
    'preservesOutsideMouth': True,
    'topologyChanged': False,
    'limitations': ['This is a geometric selection measurement only. No faces or vertices were modified.', 'The candidate follows a reviewed landmark lip contour; independent visual contour review and surgery quality remain outstanding.'],
}
OUT.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
print(json.dumps(report, indent=2))
