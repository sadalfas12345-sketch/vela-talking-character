"""Forensic topology audit of the exported original-Tripo V12 mouth prototype."""
import json
import os
from pathlib import Path

import bpy
import bmesh
import numpy as np
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
GLB = Path(os.environ.get(
    'VELA_FORENSIC_GLB',
    ROOT / 'verification/vela-original-tripo-local-mouth-v12.glb',
))
REPORT = Path(os.environ.get(
    'VELA_FORENSIC_REPORT',
    ROOT / 'verification/vela-original-tripo-local-mouth-v12-forensic.json',
))

def world_vertices(obj):
    matrix = np.asarray(obj.matrix_world, dtype=np.float64)
    coords = np.empty((len(obj.data.vertices), 3), dtype=np.float64)
    obj.data.vertices.foreach_get('co', coords.ravel())
    return coords @ matrix[:3, :3].T + matrix[:3, 3]

def boundary_components(mesh):
    edge_count = {}
    edge_vertices = {}
    for poly in mesh.polygons:
        ids = list(poly.vertices)
        for index, a in enumerate(ids):
            b = ids[(index + 1) % len(ids)]
            edge = tuple(sorted((int(a), int(b))))
            edge_count[edge] = edge_count.get(edge, 0) + 1
            edge_vertices[edge] = edge
    boundary = [edge for edge, count in edge_count.items() if count == 1]
    nonmanifold = [edge for edge, count in edge_count.items() if count > 2]
    adjacency = {}
    for a, b in boundary:
        adjacency.setdefault(a, set()).add(b)
        adjacency.setdefault(b, set()).add(a)
    remaining = set(boundary)
    components = []
    while remaining:
        first = next(iter(remaining))
        stack = [first[0], first[1]]
        vertices = set(stack)
        while stack:
            vertex = stack.pop()
            for neighbor in adjacency.get(vertex, ()):
                edge = tuple(sorted((vertex, neighbor)))
                if edge in remaining:
                    remaining.remove(edge)
                if neighbor not in vertices:
                    vertices.add(neighbor)
                    stack.append(neighbor)
        edges = [edge for edge in boundary if edge[0] in vertices and edge[1] in vertices]
        degree_histogram = {}
        for vertex in vertices:
            degree = len(adjacency.get(vertex, ()))
            degree_histogram[str(degree)] = degree_histogram.get(str(degree), 0) + 1
        components.append({
            'vertexCount': len(vertices),
            'edgeCount': len(edges),
            'closedCycle': all(len(adjacency.get(vertex, ())) == 2 for vertex in vertices),
            'degreeHistogram': degree_histogram,
            'vertices': sorted(vertices),
        })
    return boundary, nonmanifold, components

def mesh_audit(obj):
    mesh = obj.data
    world = world_vertices(obj)
    boundary, nonmanifold, components = boundary_components(mesh)
    degenerate = []
    for poly in mesh.polygons:
        ids = list(poly.vertices)
        if len(ids) < 3:
            degenerate.append(int(poly.index))
            continue
        a, b, c = world[ids[0]], world[ids[1]], world[ids[2]]
        if np.linalg.norm(np.cross(b - a, c - a)) < 1e-12:
            degenerate.append(int(poly.index))
    winding = {}
    for poly in mesh.polygons:
        winding[str(poly.normal.z >= 0)] = winding.get(str(poly.normal.z >= 0), 0) + 1
    uv_layers = []
    for layer in mesh.uv_layers:
        values = np.empty((len(layer.data), 2), dtype=np.float64)
        for index, loop in enumerate(layer.data):
            values[index] = loop.uv[:]
        uv_layers.append({
            'name': layer.name,
            'loopCount': len(layer.data),
            'finite': bool(np.isfinite(values).all()),
            'min': values.min(axis=0).tolist() if len(values) else [],
            'max': values.max(axis=0).tolist() if len(values) else [],
        })
    return {
        'name': obj.name,
        'vertexCount': len(mesh.vertices),
        'edgeCount': len(mesh.edges),
        'polygonCount': len(mesh.polygons),
        'boundaryEdgeCount': len(boundary),
        'nonmanifoldEdgeCount': len(nonmanifold),
        'degenerateFaceCount': len(degenerate),
        'degenerateFaces': degenerate[:100],
        'boundaryComponents': components,
        'uvLayers': uv_layers,
        'materials': [slot.material.name if slot.material else None for slot in obj.material_slots],
        'shapeKeys': [key.name for key in mesh.shape_keys.key_blocks] if mesh.shape_keys else [],
        'parent': obj.parent.name if obj.parent else None,
        'parentType': obj.parent_type,
        'parentBone': obj.parent_bone,
        'worldBounds': {'min': world.min(axis=0).tolist(), 'max': world.max(axis=0).tolist()},
        'normalSignCounts': winding,
    }

def mouth_boundary_candidates(obj):
    points_file = ROOT / 'verification/avaturn-face-fit-landmark-points.json'
    target = np.asarray(json.loads(points_file.read_text(encoding='utf-8'))['targetPoints'], dtype=np.float64)
    mouth_center = target[[61, 291, 13, 14]].mean(axis=0)
    world = world_vertices(obj)
    _, _, components = boundary_components(obj.data)
    candidates = []
    for component in components:
        ids = np.asarray(component['vertices'], dtype=np.int64)
        center = world[ids].mean(axis=0)
        distance = float(np.linalg.norm(center - mouth_center))
        if distance < 0.04:
            candidates.append({
                'distanceToLandmarkMouthCenter': distance,
                'center': center.tolist(),
                'min': world[ids].min(axis=0).tolist(),
                'max': world[ids].max(axis=0).tolist(),
                'vertexCount': component['vertexCount'],
                'edgeCount': component['edgeCount'],
                'closedCycle': component['closedCycle'],
                'degreeHistogram': component['degreeHistogram'],
                'vertices': component['vertices'],
            })
    candidates.sort(key=lambda item: item['distanceToLandmarkMouthCenter'])
    return {'mouthCenter': mouth_center.tolist(), 'candidates': candidates}

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(GLB))
meshes = [obj for obj in bpy.context.scene.objects if obj.type == 'MESH']
audits = [mesh_audit(obj) for obj in meshes]
report = {
    'glb': str(GLB.relative_to(ROOT)),
    'meshCount': len(meshes),
    'objects': audits,
    'bodyMouthBoundaryCandidates': mouth_boundary_candidates(
        next(obj for obj in meshes if obj.name.startswith('tripo_'))
    ),
    'classification': {
        'A_landmarkCorrespondence': 'not evaluated by topology audit',
        'B_boundarySelection': 'measured in objects and boundary components',
        'C_topologyConnectivity': 'measured boundary and nonmanifold counts',
        'D_deformationConstraints': 'not evaluated by topology audit',
        'E_skinningTransforms': 'measured parent and bone metadata',
        'F_cavityTeethTongue': 'measured as separate exported meshes',
        'G_renderMaterial': 'measured UV and material metadata; render evidence separate',
    },
}
REPORT.parent.mkdir(parents=True, exist_ok=True)
REPORT.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
print(json.dumps(report, indent=2))
