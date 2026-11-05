"""Measure topology and aperture for one exported local-mouth candidate."""
import json
import os
from pathlib import Path
import bpy
import numpy as np
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
GLB = Path(os.environ.get('VELA_CANDIDATE_GLB', ROOT / 'verification/vela-original-tripo-local-mouth-v15.glb'))
REPORT = Path(os.environ.get('VELA_CANDIDATE_REPORT', ROOT / 'verification/vela-original-tripo-local-mouth-v15-measurements.json'))
POINTS = json.loads((ROOT / 'verification/avaturn-face-fit-landmark-points.json').read_text())
TARGET = np.asarray(POINTS['targetPoints'], dtype=np.float64)
center = TARGET[[61, 291, 13, 14]].mean(axis=0)
width = float(np.linalg.norm(TARGET[291] - TARGET[61]))
camera_location = np.asarray((1.0, 0.0, 0.82), dtype=np.float64)
camera_rotation = (Vector((0.0, 0.0, 0.82)) - Vector(tuple(camera_location))).to_track_quat('-Z', 'Y')
# The Tripo source uses Y as the horizontal facial axis and Z as anatomical
# up. Use these world axes for the independent metric so camera roll cannot
# hide a malformed loop.
right = np.asarray((0.0, 1.0, 0.0), dtype=np.float64)
up = np.asarray((0.0, 0.0, 1.0), dtype=np.float64)

def world_coords(obj, evaluated=False):
    source = obj.evaluated_get(bpy.context.evaluated_depsgraph_get()) if evaluated else obj
    mesh = source.to_mesh() if evaluated else source.data
    coords = np.empty((len(mesh.vertices), 3), dtype=np.float64)
    mesh.vertices.foreach_get('co', coords.ravel())
    matrix = np.asarray(source.matrix_world, dtype=np.float64)
    result = coords @ matrix[:3, :3].T + matrix[:3, 3]
    if evaluated:
        source.to_mesh_clear()
    return result

def topology(obj):
    edge_counts = {}
    for poly in obj.data.polygons:
        ids = list(poly.vertices)
        for index, a in enumerate(ids):
            b = ids[(index + 1) % len(ids)]
            edge = tuple(sorted((int(a), int(b))))
            edge_counts[edge] = edge_counts.get(edge, 0) + 1
    boundary = sum(count == 1 for count in edge_counts.values())
    nonmanifold = sum(count > 2 for count in edge_counts.values())
    return {'vertices': len(obj.data.vertices), 'edges': len(obj.data.edges), 'faces': len(obj.data.polygons), 'boundaryEdges': boundary, 'nonmanifoldEdges': nonmanifold}

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(GLB))
objects = {obj.name.lower(): obj for obj in bpy.context.scene.objects if obj.type == 'MESH'}
rim = next(obj for name, obj in objects.items() if 'lip boundary' in name)
local = [obj for name, obj in objects.items() if any(token in name for token in ['lip boundary', 'mouth cavity', 'upper teeth', 'lower tongue'])]
baseline = {obj.name: world_coords(obj, evaluated=False) for obj in local}
report = {'glb': str(GLB.relative_to(ROOT)), 'mouthWidthMeters': width, 'objects': {obj.name: topology(obj) for obj in local}, 'states': []}
for value in [0.0, 0.5, 1.0]:
    for obj in objects.values():
        if not obj.data.shape_keys:
            continue
        for key in obj.data.shape_keys.key_blocks:
            key.value = value if key.name == 'xfer_jawOpen_original_tripo' else 0.0
    points = world_coords(rim, evaluated=True)
    relative = points - center
    horizontal = relative @ right
    vertical = relative @ up
    roi = (np.abs(horizontal) <= width * 0.8) & (np.abs(vertical) <= width * 0.8)
    upper = vertical[roi & (vertical >= 0.0)]
    lower = vertical[roi & (vertical < 0.0)]
    upper_edge = float(upper.min()) if len(upper) else None
    lower_edge = float(lower.max()) if len(lower) else None
    aperture = lower_edge - upper_edge if upper_edge is not None and lower_edge is not None else None
    inversions = 0
    for obj in local:
        neutral = baseline[obj.name]
        moved = world_coords(obj, evaluated=True)
        for poly in obj.data.polygons:
            ids = list(poly.vertices)
            if len(ids) < 3:
                continue
            a, b, c = neutral[ids[0]], neutral[ids[1]], neutral[ids[2]]
            d, e, f = moved[ids[0]], moved[ids[1]], moved[ids[2]]
            if np.dot(np.cross(b - a, c - a), np.cross(e - d, f - d)) < 0:
                inversions += 1
    report['states'].append({'jawOpen': value, 'upperEdge': upper_edge, 'lowerEdge': lower_edge, 'apertureMeters': aperture, 'apertureOverWidth': aperture / width if aperture is not None else None, 'triangleNormalFlips': inversions})
REPORT.write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
