"""Verify 2D and 3D landmarks on the untouched original Tripo GLB.

This script does not create shape keys, alter topology, import Avaturn, or
save a modified GLB.  It raycasts detector output onto the original mesh and
renders only diagnostic marker helpers.
"""
import json
import math
from pathlib import Path

import bpy
import bmesh
import numpy as np
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
# This is the preserved original Tripo surface with its Mixamo rest skeleton.
# The mesh vertices and textures are unchanged; the skeleton supplies the
# coordinate frame used by the existing frontal render and landmark image.
SOURCE = ROOT / 'assets/tripo/vela-photoreal/generated-rigged.glb'
DETECTED = ROOT / 'verification/goal1-tripo-detected-landmarks.json'
OUT = ROOT / 'verification/goal1-tripo-landmark-evidence'
OUT.mkdir(parents=True, exist_ok=True)

W = H = 1024
ORTHO = 0.20
FRONT_CAMERA = Vector((1.0, 0.0, 0.82))
TARGET = Vector((0.0, 0.0, 0.82))

LABELS = {
    'right_eye_outer': 33, 'right_eye_inner': 133,
    'left_eye_outer': 263, 'left_eye_inner': 362,
    'right_eyelid_upper': 159, 'right_eyelid_lower': 145,
    'left_eyelid_upper': 386, 'left_eyelid_lower': 374,
    'right_eyebrow': 107, 'left_eyebrow': 336,
    'nose_bridge': 168, 'nose_tip': 1,
    'nose_wing_right': 98, 'nose_wing_left': 327,
    'mouth_corner_right': 61, 'mouth_corner_left': 291,
    'upper_lip_center': 13, 'lower_lip_center': 14,
    'chin': 152, 'jawline_right': 172, 'jawline_left': 397,
}
CONTOURS = {
    'upper_lip': [61, 146, 91, 181, 84, 17, 314, 405, 321, 291],
    'lower_lip': [291, 409, 270, 269, 267, 0, 37, 39, 40, 185, 61],
    'right_eye_lid': [33, 160, 158, 133, 153, 144],
    'left_eye_lid': [263, 387, 385, 362, 380, 373],
}

# Fixed image-space review regions, specified independently of the detected
# points. They are intentionally broad and are used only to reject obvious
# assignments to hair, cheek, neck, or the wrong facial feature.
REFERENCE_REGIONS = {
    'right_eye': (0.30, 0.08, 0.52, 0.25),
    'left_eye': (0.52, 0.08, 0.74, 0.25),
    'right_eyebrow': (0.30, 0.04, 0.52, 0.17),
    'left_eyebrow': (0.52, 0.04, 0.74, 0.17),
    'nose': (0.40, 0.10, 0.63, 0.32),
    'mouth': (0.34, 0.28, 0.68, 0.43),
    'chin': (0.36, 0.38, 0.68, 0.56),
    'jawline_right': (0.25, 0.28, 0.45, 0.48),
    'jawline_left': (0.59, 0.28, 0.79, 0.48),
}

def camera_basis(camera):
    rotation = (TARGET - camera).to_track_quat('-Z', 'Y')
    return rotation @ Vector((1, 0, 0)), rotation @ Vector((0, 1, 0)), rotation @ Vector((0, 0, -1))

def project(point, camera, right, up):
    relative = point - camera
    return [0.5 + relative.dot(right) / ORTHO,
            0.5 - relative.dot(up) / ORTHO]

def ray_origin(u, v, camera, right, up):
    return camera + right * ((u - 0.5) * ORTHO) + up * ((0.5 - v) * ORTHO)

def region_for_label(label):
    if not label:
        return None
    if 'eyebrow' in label:
        return 'left_eyebrow' if label.startswith('left_') else 'right_eyebrow'
    if 'eye' in label or 'eyelid' in label:
        return 'left_eye' if label.startswith('left_') else 'right_eye'
    if 'nose' in label:
        return 'nose'
    if 'lip' in label or 'mouth' in label:
        return 'mouth'
    if label == 'chin':
        return 'chin'
    if label == 'jawline_left':
        return 'jawline_left'
    if label == 'jawline_right':
        return 'jawline_right'
    return None

def in_reference_region(x, y, region):
    if region is None:
        return None
    left, top, right, bottom = REFERENCE_REGIONS[region]
    return left <= x <= right and top <= y <= bottom

def marker_mesh(name, points, material, radius=0.0012):
    vertices = []
    faces = []
    for point in points:
        base = len(vertices)
        x, y, z = point
        vertices.extend([(x + radius, y, z), (x - radius, y, z),
                         (x, y + radius, z), (x, y - radius, z),
                         (x, y, z + radius), (x, y, z - radius)])
        faces.extend([(base, base + 2, base + 4), (base + 2, base + 1, base + 4),
                      (base + 1, base + 3, base + 4), (base + 3, base, base + 4),
                      (base + 2, base, base + 5), (base + 1, base + 2, base + 5),
                      (base + 3, base + 1, base + 5), (base, base + 3, base + 5)])
    mesh = bpy.data.meshes.new(name + ' mesh')
    mesh.from_pydata(vertices, [], faces)
    mesh.materials.append(material)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    return obj

def make_material(name, color):
    material = bpy.data.materials.new(name)
    material.diffuse_color = (*color, 1.0)
    material.use_nodes = True
    shader = material.node_tree.nodes.get('Principled BSDF')
    if shader:
        shader.inputs['Base Color'].default_value = (*color, 1.0)
        if 'Emission Color' in shader.inputs:
            shader.inputs['Emission Color'].default_value = (*color, 1.0)
            shader.inputs['Emission Strength'].default_value = 0.5
    return material

def add_label(text, point, camera, right, up, material):
    body = bpy.data.curves.new(text + ' curve', 'FONT')
    body.body = text
    body.align_x = 'CENTER'
    body.size = 0.006
    body.extrude = 0.0001
    obj = bpy.data.objects.new(text, body)
    bpy.context.scene.collection.objects.link(obj)
    obj.data.materials.append(material)
    obj.location = point + (camera - point).normalized() * 0.001
    obj.rotation_euler = (TARGET - camera).to_track_quat('Z', 'Y').to_euler()
    return obj

def render(path, camera, ortho_scale=ORTHO):
    scene = bpy.context.scene
    camera_obj = scene.camera
    camera_obj.location = camera
    camera_obj.rotation_euler = (TARGET - camera).to_track_quat('-Z', 'Y').to_euler()
    camera_obj.data.type = 'ORTHO'
    camera_obj.data.ortho_scale = ortho_scale
    scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)

def main():
    detector = json.loads(DETECTED.read_text(encoding='utf-8'))
    landmarks = np.asarray(detector['landmarks'], dtype=np.float64)
    if len(landmarks) != 478:
        raise RuntimeError(f'Expected 478 MediaPipe points, got {len(landmarks)}')

    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(SOURCE))
    body = max((obj for obj in bpy.context.scene.objects if obj.type == 'MESH' and obj.name != 'Icosphere'),
               key=lambda obj: len(obj.data.vertices))
    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_EEVEE'
    scene.render.resolution_x = W
    scene.render.resolution_y = H
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.view_settings.view_transform = 'Standard'
    scene.view_settings.look = 'Medium High Contrast'
    scene.view_settings.exposure = -2.0
    world = bpy.data.worlds.new('Goal 1 world')
    scene.world = world
    world.color = (0.015, 0.015, 0.015)
    for name, location, power in [('Key', (0.5, -0.35, 1.05), 35), ('Fill', (0.35, 0.35, 0.85), 15)]:
        light_data = bpy.data.lights.new(name, 'AREA')
        light_data.energy = power
        light_data.shape = 'DISK'
        light_data.size = 0.4
        light = bpy.data.objects.new(name, light_data)
        scene.collection.objects.link(light)
        light.location = location
        light.rotation_euler = (TARGET - light.location).to_track_quat('-Z', 'Y').to_euler()
    camera_data = bpy.data.cameras.new('Goal 1 camera')
    camera_obj = bpy.data.objects.new('Goal 1 camera', camera_data)
    scene.collection.objects.link(camera_obj)
    scene.camera = camera_obj

    right, up, forward = camera_basis(FRONT_CAMERA)
    depsgraph = bpy.context.evaluated_depsgraph_get()
    region_by_index = {}
    for region, indices in CONTOURS.items():
        for point_index in indices:
            region_by_index.setdefault(point_index, region)
    for region, point_index in LABELS.items():
        region_by_index[point_index] = region
    records = []
    front_surface_hits = 0
    back_surface_hits = 0
    ambiguous_surface_hits = 0
    unresolved = 0
    incorrect_region = 0
    oblique_camera = Vector((0.88, -0.42, 0.88))
    oblique_right, oblique_up, oblique_forward = camera_basis(oblique_camera)
    hit_points = []
    for index, (u, v, z) in enumerate(landmarks):
        origin = ray_origin(float(u), float(v), FRONT_CAMERA, right, up)
        hit, location, normal, triangle, hit_object, _ = scene.ray_cast(depsgraph, origin, forward, distance=2.0)
        projected = project(location, FRONT_CAMERA, right, up) if hit else [None, None]
        residual_px = (math.hypot(projected[0] - u, projected[1] - v) * W) if hit else None
        label = next((name for name, point_index in LABELS.items() if point_index == index), None)
        region = region_for_label(label)
        region_valid = in_reference_region(float(u), float(v), region)
        camera_facing_dot = None
        front_surface = False
        oblique_visible = None
        oblique_gap = None
        if hit:
            to_camera = (FRONT_CAMERA - location).normalized()
            camera_facing_dot = float(normal.normalized().dot(to_camera))
            front_surface = camera_facing_dot > 0.05
            if front_surface:
                front_surface_hits += 1
            elif camera_facing_dot >= 0.0:
                ambiguous_surface_hits += 1
            else:
                back_surface_hits += 1
            if region_valid is False:
                incorrect_region += 1
            oblique_origin = ray_origin(float(project(location, oblique_camera, oblique_right, oblique_up)[0]),
                                        float(project(location, oblique_camera, oblique_right, oblique_up)[1]),
                                        oblique_camera, oblique_right, oblique_up)
            to_point = location - oblique_origin
            distance = float(to_point.length)
            if distance > 1e-8:
                oblique_hit, oblique_location, _, _, oblique_object, _ = scene.ray_cast(
                    depsgraph, oblique_origin, to_point.normalized(), distance=distance + 0.01)
                oblique_gap = float((oblique_location - location).length) if oblique_hit else None
                oblique_visible = bool(oblique_hit and oblique_gap <= 0.0005 and oblique_object == hit_object)
        else:
            unresolved += 1
        record = {
            'index': index,
            'imageXY': [float(u * W), float(v * H)],
            'imageNormalized': [float(u), float(v)],
            'meshXYZ': [float(value) for value in location] if hit else None,
            'triangleIndex': int(triangle) if hit else None,
            'projectionResidualPixels': float(residual_px) if residual_px is not None else None,
            'surfaceVisibleFromFrontalCamera': bool(hit),
            'hitObject': hit_object.name if hit and hit_object else None,
            'surfaceNormal': [float(value) for value in normal] if hit else None,
            'anatomicalRegion': region_by_index.get(index),
            'referenceRegion': region,
            'referenceRegionContains2DPoint': region_valid,
            'frontSurface': front_surface,
            'frontNormalFacingDot': camera_facing_dot,
            'obliqueVisibleFirstSurface': oblique_visible,
            'obliqueSurfaceGapMeters': oblique_gap,
        }
        records.append(record)
        if hit:
            hit_points.append(location.copy())

    marker_material = make_material('Detected Tripo landmarks', (0.0, 1.0, 0.1))
    marker_obj = marker_mesh('Detected Tripo 3D landmarks', hit_points, marker_material, 0.0010)
    marker_obj.hide_render = True
    render(OUT / 'A_original_tripo_without_landmarks.png', FRONT_CAMERA)
    marker_obj.hide_render = False
    render(OUT / 'C_original_tripo_projected_3d_landmarks.png', FRONT_CAMERA)

    # Oblique visibility evidence uses the same fixed 3D hit points.
    oblique = Vector((0.88, -0.42, 0.88))
    render(OUT / 'E_original_tripo_projected_landmarks_oblique.png', oblique, 0.20)
    render(OUT / 'F_original_tripo_projected_landmarks_side.png', Vector((0.72, -0.68, 0.84)), 0.20)

    # Save compact evidence only; full point records remain in JSON.
    repeat_path = ROOT / 'assets/tripo/vela-photoreal/landmarks.json'
    repeat_comparison = None
    if repeat_path.is_file():
        repeat = np.asarray(json.loads(repeat_path.read_text(encoding='utf-8'))['landmarks'], dtype=np.float64)
        if repeat.shape == landmarks.shape:
            repeat_errors = np.linalg.norm((repeat[:, :2] - landmarks[:, :2]) * np.asarray([W, H]), axis=1)
            repeat_comparison = {
                'reference': str(repeat_path.relative_to(ROOT)),
                'meanPixels': float(np.mean(repeat_errors)),
                'p95Pixels': float(np.percentile(repeat_errors, 95)),
                'maxPixels': float(np.max(repeat_errors)),
                'interpretation': 'repeat-detector stability only; not independent anatomical ground truth',
            }
    projection_residuals = [item['projectionResidualPixels'] for item in records if item['projectionResidualPixels'] is not None]
    report = {
        'status': 'UNVERIFIED_PENDING_INDEPENDENT_ANATOMICAL_REVIEW',
        'sourceGLB': str(SOURCE.relative_to(ROOT)),
        'detector': 'MediaPipe Face Landmarker, official face_landmarker.task, 478 points',
        'detectorInput': str(Path(detector['image']).relative_to(ROOT)),
        'detectedLandmarks': len(records),
        'frontalSurfaceHits': sum(1 for item in records if item['surfaceVisibleFromFrontalCamera']),
        'validFrontSurfaceHits': front_surface_hits,
        'incorrectRegionHits': incorrect_region,
        'backSurfaceHits': back_surface_hits,
        'ambiguousSurfaceHits': ambiguous_surface_hits,
        'unresolvedLandmarks': unresolved,
        'secondView': {
            'camera': [float(v) for v in oblique_camera],
            'visibleFirstSurfaceCount': sum(1 for item in records if item['obliqueVisibleFirstSurface']),
            'occludedOrAmbiguousCount': sum(1 for item in records if item['obliqueVisibleFirstSurface'] is False),
        },
        'meanProjectionResidualPixels': float(np.mean(projection_residuals)),
        'p95ProjectionResidualPixels': float(np.percentile(projection_residuals, 95)),
        'repeatDetectorComparison': repeat_comparison,
        'independentReferenceValidated': 0,
        'independentValidation': 'UNVERIFIED: no separately annotated ground-truth set was supplied; projection residual is self-consistency only.',
        'landmarkDefinitions': LABELS,
        'records': records,
        'evidence': {
            'A': str((OUT / 'A_original_tripo_without_landmarks.png').relative_to(ROOT)),
            'B': str((OUT / 'B_original_tripo_detected_2d_landmarks.png').relative_to(ROOT)),
            'C': str((OUT / 'C_original_tripo_projected_3d_landmarks.png').relative_to(ROOT)),
            'D': str((OUT / 'D_original_tripo_anatomical_labels.png').relative_to(ROOT)),
            'E': str((OUT / 'E_original_tripo_projected_landmarks_oblique.png').relative_to(ROOT)),
            'F': str((OUT / 'F_original_tripo_projected_landmarks_side.png').relative_to(ROOT)),
        },
        'referenceRegions': REFERENCE_REGIONS,
        'limits': ['2D detector output is not independent anatomical ground truth.', 'Fixed image ROIs are rejection checks, not ground truth.', 'Human review of labeled eyes, nose, lips, chin, and oblique surface placement is still required.'],
    }
    (OUT / 'goal1-tripo-landmark-report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({key: report[key] for key in ['status', 'detectedLandmarks', 'frontalSurfaceHits', 'meanProjectionResidualPixels', 'p95ProjectionResidualPixels', 'independentReferenceValidated']}, indent=2))

if __name__ == '__main__':
    main()
