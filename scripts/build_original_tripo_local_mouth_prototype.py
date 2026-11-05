"""Build a localized mouth-surgery prototype on the original Tripo mesh.

Avaturn supplies motion only. The Tripo mesh remains the target everywhere
except the measured lip-region faces removed to expose a recessed cavity.
"""
import json
import os
from pathlib import Path

import bpy
import bmesh
import numpy as np
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
ASSET = ROOT / 'assets/tripo/vela-photoreal'
SOURCE = ASSET / 'generated-rigged.glb'
POINTS = ROOT / 'verification/avaturn-face-fit-landmark-points.json'
FIT_REPORT = ROOT / 'verification/avaturn-tripo-facefit-report.json'
DONOR_MESHES = ROOT / 'verification/avaturn-face-fit-source-meshes.npz'
LANDMARKS = ASSET / 'landmarks.json'
OUTPUT = Path(os.environ.get('VELA_LOCAL_MOUTH_OUTPUT', ASSET / 'intermediates/vela-original-tripo-local-mouth-prototype.glb'))
REPORT = Path(os.environ.get('VELA_LOCAL_MOUTH_REPORT', ROOT / 'verification/vela-original-tripo-local-mouth-prototype.json'))
EXPRESSION = 'jawOpen'

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

def rbf_displacement(points, handles, displacement, sigma):
    output = np.zeros_like(points)
    for start in range(0, len(points), 20000):
        stop = min(start + 20000, len(points))
        distances = np.sum((points[start:stop, None] - handles[None]) ** 2, axis=2)
        k = min(24, len(handles))
        indices = np.argpartition(distances, k - 1, axis=1)[:, :k]
        local = np.take_along_axis(distances, indices, axis=1)
        weights = np.exp(-local / (2.0 * sigma * sigma))
        weights /= np.maximum(weights.sum(axis=1, keepdims=True), 1e-12)
        output[start:stop] = np.einsum('nk,nkd->nd', weights, displacement[indices])
    return output

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
donor_expression = donor_data[f'Head_Mesh__Key__{EXPRESSION}'].astype(np.float64)
handle_faces = donor_triangles[face_ids[rows]]
donor_neutral_landmarks = np.einsum('ni,nij->nj', bary[rows], donor_basis[handle_faces])
donor_expression_landmarks = np.einsum('ni,nij->nj', bary[rows], donor_expression[handle_faces])
landmark_displacements = scale * (donor_expression_landmarks - donor_neutral_landmarks) @ rotation
target_handles = target_points[rows]

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(SOURCE))
meshes = [obj for obj in bpy.context.scene.objects if obj.type == 'MESH' and obj.name != 'Icosphere']
if len(meshes) != 1:
    raise RuntimeError(f'Expected one original Tripo mesh, found {[obj.name for obj in meshes]}')
body = meshes[0]
armature = next((obj for obj in bpy.context.scene.objects if obj.type == 'ARMATURE'), None)
if armature is None:
    raise RuntimeError('Original Tripo armature is missing.')
head_bone = next((bone for bone in armature.data.bones if bone.name.lower().endswith(':head')), None)
if head_bone is None:
    raise RuntimeError('Original Tripo Head bone is missing.')
head_pose = armature.pose.bones[head_bone.name]
bone_world = armature.matrix_world @ head_pose.matrix
bone_inverse = bone_world.inverted()

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
forward = np.asarray((camera_rotation @ Vector((0, 0, -1)))[:], dtype=np.float64)
relative = world - camera_location
screen = np.column_stack((0.5 + relative @ right / 0.20,
                          0.5 - relative @ up / 0.20,
                          relative @ forward))
polygon = landmark_pixels[LIP_OUTER, :2]
inside = point_in_polygon(screen[:, 0], screen[:, 1], polygon)
mouth_indices = np.asarray([61, 291, 13, 14, 78, 308, 95, 324, 82, 312, 87, 317], dtype=np.int32)
mouth_xy = landmark_pixels[mouth_indices, :2]
nearest = np.empty(len(screen), dtype=np.int32)
for start in range(0, len(screen), 20000):
    stop = min(start + 20000, len(screen))
    nearest[start:stop] = np.argmin(np.sum((screen[start:stop, None, :2] - mouth_xy[None, :, :]) ** 2, axis=2), axis=1)
target_depth = np.asarray([screen[np.argmin(np.sum((screen[:, :2] - landmark_pixels[index, :2]) ** 2, axis=1)), 2] for index in mouth_indices])
ipd = float(np.linalg.norm((landmark_pixels[33, :2] - landmark_pixels[263, :2]) * 0.20))
# Restrict surgery to the visible lip shell. The first prototype admitted
# roughly 25 mm of hidden geometry behind the lips and produced jagged cuts.
depth_tolerance = max(ipd * 0.08, 0.0015)
face_mask = inside & (np.abs(screen[:, 2] - target_depth[nearest]) <= depth_tolerance)

body.data.calc_loop_triangles()
selected_keys = set()
mouth_center_screen = landmark_pixels[[61, 291, 13, 14], :2].mean(axis=0)
mouth_width_screen = float(np.linalg.norm(landmark_pixels[291, :2] - landmark_pixels[61, :2]))
seam_rx = mouth_width_screen * 0.52
seam_ry = max(mouth_width_screen * 0.06, 0.006)
for triangle in body.data.loop_triangles:
    ids = tuple(int(v) for v in triangle.vertices)
    if not face_mask[list(ids)].all():
        continue
    center = world[list(ids)].mean(axis=0)
    center_screen = np.asarray((0.5 + (center - camera_location) @ right / 0.20,
                                0.5 - (center - camera_location) @ up / 0.20))
    seam_distance = ((center_screen[0] - mouth_center_screen[0]) / seam_rx) ** 2 + ((center_screen[1] - mouth_center_screen[1]) / seam_ry) ** 2
    if seam_distance <= 1.0:
        selected_keys.add(tuple(sorted(ids)))
if len(selected_keys) < 100:
    raise RuntimeError(f'Localized mouth selection is too small: {len(selected_keys)} faces')

bm = bmesh.new()
bm.from_mesh(body.data)
bm.faces.ensure_lookup_table()
cut_faces = [face for face in bm.faces if len(face.verts) == 3 and tuple(sorted(v.index for v in face.verts)) in selected_keys]
if len(cut_faces) != len(selected_keys):
    raise RuntimeError(f'BMesh selection mismatch: {len(cut_faces)} vs {len(selected_keys)}')
bmesh.ops.delete(bm, geom=cut_faces, context='FACES_ONLY')
bm.to_mesh(body.data)
bm.free()
body.data.update()

# Transfer donor motion onto the original Tripo vertices before adding the
# separate local cavity. Outside the measured mouth surface this is the same
# original-vertex deformation field as the proof artifact.
sigma = max(ipd * 0.35, 0.012)
delta_world = rbf_displacement(world, target_handles, landmark_displacements, sigma)
# A closed Tripo shell places several upper and lower inner-lip landmarks at
# nearly the same target depth.  A single spatial RBF therefore mixes the two
# anatomical motions.  Keep the measured donor displacements, but add explicit
# upper/lower lip constraints and taper them into the original Tripo surface.
upper_ids = np.asarray([61, 185, 40, 39, 37, 0, 267, 269, 270, 409, 291], dtype=np.int32)
lower_ids = np.asarray([291, 375, 321, 405, 314, 17, 84, 181, 91, 146, 61], dtype=np.int32)
upper_rows = np.isin(rows, upper_ids)
lower_rows = np.isin(rows, lower_ids)
if upper_rows.any() and lower_rows.any():
    upper_field = rbf_displacement(world, target_handles[upper_rows], landmark_displacements[upper_rows], sigma)
    lower_field = rbf_displacement(world, target_handles[lower_rows], landmark_displacements[lower_rows], sigma)
    mouth_cx, mouth_cy = landmark_pixels[[61, 291, 13, 14], :2].mean(axis=0)
    mouth_w = max(float(np.linalg.norm(landmark_pixels[291, :2] - landmark_pixels[61, :2])), 1e-6)
    mouth_region = np.exp(-(((screen[:, 0] - mouth_cx) / (mouth_w * 0.72)) ** 2 + ((screen[:, 1] - mouth_cy) / (mouth_w * 0.52)) ** 2))
    lower_fraction = 1.0 / (1.0 + np.exp(-(screen[:, 1] - mouth_cy) / max(mouth_w * 0.055, 1e-6)))
    constrained = upper_field * (1.0 - lower_fraction[:, None]) + lower_field * lower_fraction[:, None]
    delta_world = delta_world * (1.0 - mouth_region[:, None]) + constrained * mouth_region[:, None]
local_delta = delta_world @ np.linalg.inv(world_matrix[:3, :3]).T
body.shape_key_add(name='Basis', from_mix=False)
body_key = body.shape_key_add(name='xfer_jawOpen_original_tripo', from_mix=False)
body_key.data.foreach_set('co', (coords + local_delta).astype(np.float32).ravel())
body_key.value = 0.0
body.data.shape_keys.use_relative = True
body.data.shape_keys.animation_data_clear()

# Build only a small recessed cavity behind the landmark-derived seam. The
# previous version used the complete lip contour as the cavity rim, which made
# the neutral state read as a black rectangular face patch.
center_world = target_points[[61, 291, 13, 14]].mean(axis=0)
mouth_width_world = float(np.linalg.norm(target_points[291] - target_points[61]))
ring_count = 24
outer_ring = []
inner_ring = []
back_ring = []
for index in range(ring_count):
    angle = 2.0 * np.pi * index / ring_count
    xy = right * (np.cos(angle) * mouth_width_world * 0.31) + up * (np.sin(angle) * mouth_width_world * 0.045)
    outer_ring.append(center_world + xy)
    inner_ring.append(center_world + xy * 0.88 + forward * (ipd * 0.10))
    back_ring.append(center_world + xy * 0.72 + forward * (ipd * 0.20))
back_center = center_world + forward * (ipd * 0.20)
ring_world = np.vstack([np.asarray(outer_ring), np.asarray(inner_ring), np.asarray(back_ring), back_center[None]])
ring_delta = rbf_displacement(ring_world, target_handles, landmark_displacements, sigma)
ring_local = np.asarray([(bone_inverse @ Vector(point.tolist()))[:] for point in ring_world], dtype=np.float32)
ring_moved_local = np.asarray([(bone_inverse @ Vector((point + delta).tolist()))[:] for point, delta in zip(ring_world, ring_delta)], dtype=np.float32)
cavity_vertices = ring_local.tolist()
cavity_faces = []
for index in range(ring_count):
    nxt = (index + 1) % ring_count
    cavity_faces.append((index, nxt, ring_count + nxt, ring_count + index))
    cavity_faces.append((ring_count + index, ring_count + nxt, ring_count * 2 + nxt, ring_count * 2 + index))
    cavity_faces.append((ring_count * 2 + index, ring_count * 2 + nxt, ring_count * 3))
cavity_mesh = bpy.data.meshes.new('Original Tripo localized mouth cavity geometry')
cavity_mesh.from_pydata(cavity_vertices, [], cavity_faces)
cavity_mesh.update()
cavity_obj = bpy.data.objects.new('Original Tripo localized mouth cavity', cavity_mesh)
bpy.context.scene.collection.objects.link(cavity_obj)
cavity_obj.parent = armature
cavity_obj.parent_type = 'BONE'
cavity_obj.parent_bone = head_bone.name
cavity_obj.matrix_world = bone_world
material = bpy.data.materials.new('Localized original Tripo oral cavity')
material.diffuse_color = (0.035, 0.004, 0.008, 1.0)
material.use_nodes = True
bsdf = material.node_tree.nodes.get('Principled BSDF')
if bsdf:
    bsdf.inputs['Base Color'].default_value = (0.035, 0.004, 0.008, 1.0)
    bsdf.inputs['Roughness'].default_value = 0.92
    if 'Emission Color' in bsdf.inputs:
        bsdf.inputs['Emission Color'].default_value = (0.012, 0.001, 0.002, 1.0)
        bsdf.inputs['Emission Strength'].default_value = 0.2
cavity_mesh.materials.append(material)
cavity_obj.shape_key_add(name='Basis', from_mix=False)
cavity_key = cavity_obj.shape_key_add(name='xfer_jawOpen_original_tripo', from_mix=False)
cavity_key.data.foreach_set('co', ring_moved_local.ravel())
cavity_key.value = 0.0
cavity_mesh.shape_keys.use_relative = True
cavity_mesh.shape_keys.animation_data_clear()

bpy.ops.object.select_all(action='DESELECT')
for obj in bpy.context.scene.objects:
    if obj.type in {'MESH', 'ARMATURE', 'EMPTY'}:
        obj.select_set(True)
bpy.context.view_layer.objects.active = body
OUTPUT.parent.mkdir(parents=True, exist_ok=True)
bpy.ops.export_scene.gltf(filepath=str(OUTPUT), export_format='GLB', export_morph=True,
                          export_skins=True, export_animations=True, export_apply=False)
report = {
    'status': 'LOCAL_MOUTH_SURGERY_PROTOTYPE_REQUIRES_RENDER_REVIEW',
    'sourceTripo': str(SOURCE.relative_to(ROOT)),
    'originalTripoVertexCount': int(len(coords)),
    'localizedCutFaces': int(len(selected_keys)),
    'localizedCutVerticesEstimated': int(face_mask.sum()),
    'preservesOutsideMouth': True,
    'donorGeometryImported': False,
    'topologyReplacement': False,
    'mouthSurgery': True,
    'cavityVertices': int(len(cavity_vertices)),
    'cavityFaces': int(len(cavity_faces)),
    'motionSource': 'Avaturn landmark displacement only',
    'solver': {
        'type': 'localized Gaussian RBF interpolation with constrained upper/lower lip fields',
        'handleCount': int(len(rows)),
        'neighbors': 24,
        'sigmaMeters': sigma,
        'depthToleranceMeters': depth_tolerance,
    },
    'output': str(OUTPUT.relative_to(ROOT)),
    'limitations': ['Only jawOpen is wired in this prototype.', 'Upper/lower lip boundary quality, cavity occlusion, self-intersections, and runtime behavior remain to be reviewed.'],
}
REPORT.parent.mkdir(parents=True, exist_ok=True)
REPORT.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
print(json.dumps(report, indent=2))
