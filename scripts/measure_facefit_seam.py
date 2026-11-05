"""Measure the exported full-face patch against the cut Tripo shell boundary."""
import json
from pathlib import Path

import bpy
import bmesh
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree

ROOT = Path(__file__).resolve().parents[1]
GLB = ROOT / 'assets/tripo/vela-photoreal/vela-photoreal-facefit-prototype.glb'
OUT = ROOT / 'verification/tripo-facefit-seam-measurements.json'
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(GLB))
scene = bpy.context.scene
shell = next(o for o in scene.objects if o.type == 'MESH' and o.name.startswith('tripo_node_'))
patch = next(o for o in scene.objects if o.type == 'MESH' and o.name == 'VelaTripoHead')

def boundary(obj):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    edges = [e for e in bm.edges if e.is_boundary]
    ids = np.unique(np.asarray([[e.verts[0].index, e.verts[1].index] for e in edges], dtype=np.int32))
    points = np.asarray([(obj.matrix_world @ bm.verts[i].co)[:] for i in ids], dtype=np.float64)
    bm.free()
    return points, len(edges)

shell_points, shell_edges = boundary(shell)
patch_points, patch_edges = boundary(patch)
patch_bvh = BVHTree.FromObject(patch, bpy.context.evaluated_depsgraph_get(), epsilon=0.0)
shell_bvh = BVHTree.FromObject(shell, bpy.context.evaluated_depsgraph_get(), epsilon=0.0)

def gaps(points, bvh):
    values = []
    for point in points:
        hit = bvh.find_nearest(point)
        if hit and hit[0] is not None:
            values.append(float(hit[3]))
    return np.asarray(values, dtype=np.float64)

patch_to_shell = gaps(patch_points, shell_bvh)
shell_to_patch = gaps(shell_points, patch_bvh)
patch_tree = KDTree(len(patch_points))
for index, point in enumerate(patch_points):
    patch_tree.insert(point, index)
patch_tree.balance()
shell_tree = KDTree(len(shell_points))
for index, point in enumerate(shell_points):
    shell_tree.insert(point, index)
shell_tree.balance()
patch_boundary_gap = np.asarray([shell_tree.find(point)[2] for point in patch_points], dtype=np.float64)
pad = 0.012
lo, hi = patch_points.min(axis=0) - pad, patch_points.max(axis=0) + pad
near_shell_boundary = shell_points[np.all((shell_points >= lo) & (shell_points <= hi), axis=1)]
near_shell_gap = np.asarray([patch_tree.find(point)[2] for point in near_shell_boundary], dtype=np.float64)
landmarks = json.loads((ROOT / 'assets/tripo/vela-photoreal/landmarks.json').read_text(encoding='utf-8'))
target_points = np.asarray(json.loads((ROOT / 'verification/avaturn-face-fit-landmark-points.json').read_text(encoding='utf-8'))['targetPoints'], dtype=np.float64)
oval = [10,338,297,332,284,251,389,356,454,323,361,288,397,365,379,378,400,377,152,148,176,149,150,136,172,58,132,93,234,127,162,21,54,103,67,109]
landmark_xy = np.asarray(landmarks['landmarks'], dtype=np.float64)
camera_location = Vector((1.0, 0.0, 0.82))
camera_rotation = (Vector((0,0,0.82))-camera_location).to_track_quat('-Z','Y')
right = np.asarray((camera_rotation @ Vector((1,0,0)))[:])
up = np.asarray((camera_rotation @ Vector((0,1,0)))[:])
forward = np.asarray((camera_rotation @ Vector((0,0,-1)))[:])
cam = np.asarray(camera_location[:])
def project(points):
    rel = points - cam
    return np.column_stack((0.5 + rel @ right / 0.20, 0.5 - rel @ up / 0.20, rel @ forward))
def inside_polygon(x, y, polygon):
    inside = False
    x0,y0=polygon[-1]
    for x1,y1 in polygon:
        if (y1>y)!=(y0>y) and x < (x0-x1)*(y-y1)/(y0-y1+1e-20)+x1: inside=not inside
        x0,y0=x1,y1
    return inside
polygon=landmark_xy[oval,:2]
valid=np.isfinite(target_points[:,0])
face_xy=landmark_xy[valid,:2]
face_depth=(target_points[valid]-cam)@forward
ipd=float(np.linalg.norm((landmark_xy[33,:2]-landmark_xy[263,:2])*0.20))
depth_tolerance=max(ipd*0.42,0.003)
shell_screen=project(shell_points)
near_face=np.asarray([inside_polygon(p[0],p[1],polygon) for p in shell_screen])
candidate_ids=np.flatnonzero(near_face)
nearest=np.empty(len(candidate_ids),dtype=np.int32)
for start in range(0,len(candidate_ids),1000):
    ids=candidate_ids[start:start+1000]
    delta=shell_screen[ids,None,:2]-face_xy[None,:,:]
    nearest[start:start+len(ids)]=np.argmin(np.sum(delta*delta,axis=2),axis=1)
face_boundary_mask=np.zeros(len(shell_points),dtype=bool)
face_boundary_mask[candidate_ids]=np.abs(shell_screen[candidate_ids,2]-face_depth[nearest])<=depth_tolerance
face_shell_boundary=shell_points[face_boundary_mask]
face_shell_tree=KDTree(len(face_shell_boundary))
for index,point in enumerate(face_shell_boundary): face_shell_tree.insert(point,index)
face_shell_tree.balance()
face_patch_gap=np.asarray([face_shell_tree.find(point)[2] for point in patch_points],dtype=np.float64) if len(face_shell_boundary) else np.asarray([])
if len(face_shell_boundary):
    patch_screen=project(patch_points)
    boundary_screen=project(face_shell_boundary)
    screen_delta=patch_screen[:,None,:2]-boundary_screen[None,:,:2]
    screen_d2=np.sum(screen_delta*screen_delta,axis=2)
    nearest_screen=np.argmin(screen_d2,axis=1)
    screen_gap_pixels=np.sqrt(screen_d2[np.arange(len(patch_points)),nearest_screen])*2048
    screen_mapped_world_gap=np.linalg.norm(patch_points-face_shell_boundary[nearest_screen],axis=1)
else:
    screen_gap_pixels=np.asarray([])
    screen_mapped_world_gap=np.asarray([])
report = {
    'method': 'Boundary edge vertices from Blender BMesh; nearest-surface distances to the other exported mesh via Blender BVH.',
    'glb': str(GLB.relative_to(ROOT)),
    'TripoShellBoundaryEdges': shell_edges,
    'TripoShellBoundaryVertices': int(len(shell_points)),
    'FittedFaceBoundaryEdges': patch_edges,
    'FittedFaceBoundaryVertices': int(len(patch_points)),
    'patchBoundaryBoundsMeters': [patch_points.min(axis=0).tolist(), patch_points.max(axis=0).tolist()],
    'shellBoundaryBoundsMeters': [shell_points.min(axis=0).tolist(), shell_points.max(axis=0).tolist()],
    'localShellBoundaryVerticesWithin12mmOfPatchBounds': int(len(near_shell_boundary)),
    'registeredFaceShellBoundaryVertices': int(len(face_shell_boundary)),
    'patchBoundaryToRegisteredFaceCutBoundaryMillimeters': {
        'median': float(np.median(face_patch_gap)*1000) if len(face_patch_gap) else None,
        'p95': float(np.percentile(face_patch_gap,95)*1000) if len(face_patch_gap) else None,
        'max': float(np.max(face_patch_gap)*1000) if len(face_patch_gap) else None,
        'within0_5mm': float(np.mean(face_patch_gap<=0.0005)) if len(face_patch_gap) else None,
    },
    'registeredFaceBoundaryNearestInProjectionPixels': {
        'median': float(np.median(screen_gap_pixels)) if len(screen_gap_pixels) else None,
        'p95': float(np.percentile(screen_gap_pixels,95)) if len(screen_gap_pixels) else None,
        'max': float(np.max(screen_gap_pixels)) if len(screen_gap_pixels) else None,
        'worldDistanceMedianMillimeters': float(np.median(screen_mapped_world_gap)*1000) if len(screen_mapped_world_gap) else None,
        'worldDistanceP95Millimeters': float(np.percentile(screen_mapped_world_gap,95)*1000) if len(screen_mapped_world_gap) else None,
    },
    'patchBoundaryToShellBoundaryMillimeters': {
        'median': float(np.median(patch_boundary_gap) * 1000),
        'p95': float(np.percentile(patch_boundary_gap, 95) * 1000),
        'max': float(np.max(patch_boundary_gap) * 1000),
        'within0_5mm': float(np.mean(patch_boundary_gap <= 0.0005)),
    },
    'localShellBoundaryToPatchBoundaryMillimeters': {
        'median': float(np.median(near_shell_gap) * 1000) if len(near_shell_gap) else None,
        'p95': float(np.percentile(near_shell_gap, 95) * 1000) if len(near_shell_gap) else None,
        'max': float(np.max(near_shell_gap) * 1000) if len(near_shell_gap) else None,
        'within0_5mm': float(np.mean(near_shell_gap <= 0.0005)) if len(near_shell_gap) else None,
    },
    'patchBoundaryToShellSurfaceMillimeters': {
        'median': float(np.median(patch_to_shell) * 1000),
        'p95': float(np.percentile(patch_to_shell, 95) * 1000),
        'max': float(np.max(patch_to_shell) * 1000),
        'within0_5mm': float(np.mean(patch_to_shell <= 0.0005)),
    },
    'shellBoundaryToPatchSurfaceMillimeters': {
        'median': float(np.median(shell_to_patch) * 1000),
        'p95': float(np.percentile(shell_to_patch, 95) * 1000),
        'max': float(np.max(shell_to_patch) * 1000),
        'within0_5mm': float(np.mean(shell_to_patch <= 0.0005)),
    },
}
OUT.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
print(json.dumps(report, indent=2))
