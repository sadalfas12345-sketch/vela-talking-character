"""Measure topology and projected mouth aperture for a localized Tripo prototype."""
import json
import os
from pathlib import Path

import bpy
import bmesh
import numpy as np
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
GLB = Path(os.environ.get('VELA_LOCAL_MOUTH_GLB', ROOT / 'assets/tripo/vela-photoreal/intermediates/vela-original-tripo-local-mouth-v3.glb'))
OUT = Path(os.environ.get('VELA_LOCAL_MOUTH_MEASUREMENTS', ROOT / 'verification/vela-original-tripo-local-mouth-v3-measurements.json'))
KEY = 'xfer_jawOpen_original_tripo'

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(GLB))
meshes = [obj for obj in bpy.context.scene.objects if obj.type == 'MESH']
body = next(obj for obj in meshes if 'cavity' not in obj.name.lower())
cavity = next((obj for obj in meshes if 'cavity' in obj.name.lower()), None)

def topology(obj):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    boundary = sum(1 for edge in bm.edges if not edge.is_manifold)
    nonmanifold = sum(1 for edge in bm.edges if edge.is_manifold is False and not edge.is_boundary)
    bm.free()
    return {'vertices': len(obj.data.vertices), 'polygons': len(obj.data.polygons), 'boundaryEdges': boundary, 'nonmanifoldEdges': nonmanifold}

def bounds(obj):
    points = np.asarray([(obj.matrix_world @ v.co)[:] for v in obj.data.vertices], dtype=np.float64)
    return {'min': points.min(axis=0).tolist(), 'max': points.max(axis=0).tolist()}

result = {'glb': str(GLB.relative_to(ROOT)), 'body': topology(body), 'bodyWorldBounds': bounds(body), 'cavity': topology(cavity) if cavity else None}
states = {}
for state, value in [('neutral', 0.0), ('jawOpen', 1.0)]:
    for obj in meshes:
        if obj.data.shape_keys:
            for key in obj.data.shape_keys.key_blocks:
                key.value = value if key.name == KEY else 0.0
    bpy.context.view_layer.update()
    states[state] = {
        'bodyWorldBounds': bounds(body),
        'cavityWorldBounds': bounds(cavity) if cavity else None,
    }
result['states'] = states
result['status'] = 'MEASURED_REQUIRES_GATE4_REVIEW'
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
print(json.dumps(result, indent=2))
