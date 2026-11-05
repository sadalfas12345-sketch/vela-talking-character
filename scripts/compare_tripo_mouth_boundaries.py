"""Compare original and V12 body boundary components near the mouth."""
import json
from pathlib import Path
import bpy
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'assets/tripo/vela-photoreal/generated-rigged.glb'
V12 = ROOT / 'verification/vela-original-tripo-local-mouth-v12.glb'
OUT = ROOT / 'verification/vela-original-tripo-local-mouth-boundary-comparison.json'
TARGET = np.asarray(json.loads((ROOT / 'verification/avaturn-face-fit-landmark-points.json').read_text())['targetPoints'], dtype=np.float64)
MOUTH = TARGET[[61, 291, 13, 14]].mean(axis=0)

def audit(obj):
    matrix = np.asarray(obj.matrix_world, dtype=np.float64)
    verts = np.empty((len(obj.data.vertices), 3), dtype=np.float64)
    obj.data.vertices.foreach_get('co', verts.ravel())
    verts = verts @ matrix[:3, :3].T + matrix[:3, 3]
    counts = {}
    for poly in obj.data.polygons:
        ids = list(poly.vertices)
        for index, a in enumerate(ids):
            b = ids[(index + 1) % len(ids)]
            edge = tuple(sorted((int(a), int(b))))
            counts[edge] = counts.get(edge, 0) + 1
    boundary = [edge for edge, count in counts.items() if count == 1]
    adjacency = {}
    for a, b in boundary:
        adjacency.setdefault(a, set()).add(b)
        adjacency.setdefault(b, set()).add(a)
    remaining = set(boundary)
    components = []
    while remaining:
        edge = next(iter(remaining))
        stack = [edge[0], edge[1]]
        ids = set(stack)
        while stack:
            vertex = stack.pop()
            for neighbor in adjacency.get(vertex, ()):
                pair = tuple(sorted((vertex, neighbor)))
                remaining.discard(pair)
                if neighbor not in ids:
                    ids.add(neighbor)
                    stack.append(neighbor)
        xyz = verts[np.asarray(sorted(ids), dtype=np.int64)]
        center = xyz.mean(axis=0)
        distance = float(np.linalg.norm(center - MOUTH))
        if distance < 0.04:
            components.append({
                'distance': distance,
                'vertexCount': len(ids),
                'edgeCount': sum(1 for a, b in boundary if a in ids and b in ids),
                'closedCycle': all(len(adjacency.get(vertex, ())) == 2 for vertex in ids),
                'center': center.tolist(),
                'min': xyz.min(axis=0).tolist(),
                'max': xyz.max(axis=0).tolist(),
            })
    components.sort(key=lambda item: item['distance'])
    return {'vertexCount': len(verts), 'boundaryEdgeCount': len(boundary), 'components': components}

def load_body(path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(path))
    return next(obj for obj in bpy.context.scene.objects if obj.type == 'MESH' and obj.name.startswith('tripo'))

original = audit(load_body(SOURCE))
v12 = audit(load_body(V12))
report = {'mouthCenter': MOUTH.tolist(), 'original': original, 'v12': v12}
OUT.write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
