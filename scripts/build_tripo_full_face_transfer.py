"""Build a Tripo-textured, animation-ready facial patch from Vela's Avaturn rig.

The source Tripo and donor GLBs are read-only. The derivative replaces the
front facial shell region, transfers the Tripo albedo by Cycles bake, and keeps
TalkingHead's existing Mixamo body armature and morph channel names.
"""
import json
import math
import os
from pathlib import Path

import bpy
import bmesh
import numpy as np
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

ROOT = Path(__file__).resolve().parents[1]
ASSET = ROOT / 'assets' / 'tripo' / 'vela-photoreal'
SOURCE = ASSET / 'generated-rigged.glb'
DONOR = ROOT / 'TalkingHead' / 'avatars' / 'avaturn.glb'
LANDMARKS = ASSET / 'landmarks.json'
POINTS = ROOT / 'verification' / 'avaturn-face-fit-landmark-points.json'
FIT = ROOT / 'verification' / 'avaturn-tripo-facefit-deformed.npz'
OUTPUT = Path(os.environ.get('VELA_FACEFIT_OUTPUT', ASSET / 'vela-photoreal-facefit-prototype.glb'))
REPORT = Path(os.environ.get('VELA_FACEFIT_REPORT', ASSET / 'facial-facefit-prototype-report.json'))
COLOR_SOURCE_MODE = os.environ.get('VELA_FACE_COLOR_SOURCE', 'face').lower()
FACE_PATCH_SCOPE = os.environ.get('VELA_FACE_PATCH_SCOPE', 'oval').lower()
SURFACE_CONFORM = os.environ.get('VELA_FACE_SURFACE_CONFORM', 'true').lower() != 'false'
FACE_OVAL_EXPANSION = float(os.environ.get('VELA_FACE_OVAL_EXPANSION', '1.0'))
FACE_DEPTH_TOLERANCE_IPD = float(os.environ.get('VELA_FACE_DEPTH_TOLERANCE_IPD', '0.42'))
TEXTURE_DIR = ASSET / 'intermediates'
TEXTURE = TEXTURE_DIR / 'tripo-facefit-skin-2k.png'
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


def screen_project(world, camera_location, right, up, forward, scale):
    rel = world - camera_location
    return np.column_stack((0.5 + rel @ right / scale, 0.5 - rel @ up / scale, rel @ forward))


def reset_pose_keys(obj):
    if obj.data.shape_keys:
        for key in obj.data.shape_keys.key_blocks:
            key.value = 0.0


def create_part(source_obj, fitted, triangles, name, armature, head_bone, bone_inverse, selected=None, correction=None):
    if selected is None:
        selected = np.ones(len(triangles), dtype=bool)
    chosen_faces = np.flatnonzero(selected)
    if len(chosen_faces) < 4:
        raise RuntimeError(f'{name} retained too few triangles: {len(chosen_faces)}')
    kept_triangles = triangles[chosen_faces]
    used = np.unique(kept_triangles.ravel())
    remap = np.full(len(fitted), -1, dtype=np.int32)
    remap[used] = np.arange(len(used), dtype=np.int32)
    local_faces = remap[kept_triangles]
    world_basis = fitted[used]
    local_basis = np.asarray([(bone_inverse @ Vector(p.tolist()))[:] for p in world_basis], dtype=np.float32)
    mesh = bpy.data.meshes.new(name + ' geometry')
    mesh.from_pydata(local_basis.tolist(), [], local_faces.tolist())
    mesh.update()
    for poly in mesh.polygons:
        poly.use_smooth = True

    # Preserve the donor's authored UVs and material slots before replacing the
    # face skin material with the Tripo projection.
    for material in source_obj.data.materials:
        mesh.materials.append(material)
    source_uv = source_obj.data.uv_layers.active
    target_uv = mesh.uv_layers.new(name=source_uv.name if source_uv else 'UVMap')
    source_polygons = source_obj.data.polygons
    for out_poly_index, face_index in enumerate(chosen_faces):
        source_poly = source_polygons[int(face_index)]
        out_poly = mesh.polygons[out_poly_index]
        out_poly.material_index = source_poly.material_index
        if source_uv and len(source_poly.loop_indices) == 3:
            for src_loop, dst_loop in zip(source_poly.loop_indices, out_poly.loop_indices):
                target_uv.data[dst_loop].uv = source_uv.data[src_loop].uv

    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    obj.parent = armature
    obj.parent_type = 'BONE'
    obj.parent_bone = head_bone.name
    obj.matrix_world = armature.matrix_world @ armature.pose.bones[head_bone.name].matrix
    obj.shape_key_add(name='Basis', from_mix=False)
    basis_key = mesh.shape_keys.key_blocks['Basis']
    for index, point in enumerate(world_basis):
        basis_key.data[index].co = bone_inverse @ Vector(point.tolist())
    mesh.shape_keys.use_relative = True

    prefix = source_obj.name.replace('.', '_')
    for source_key in source_obj.data.shape_keys.key_blocks[1:]:
        key_name = prefix + '__Key__' + source_key.name
        if key_name not in fitted_arrays:
            continue
        key_world = fitted_arrays[key_name][used]
        if correction is not None:
            key_world = key_world + correction[used]
        key = obj.shape_key_add(name=source_key.name, from_mix=False)
        for index, point in enumerate(key_world):
            key.data[index].co = bone_inverse @ Vector(point.tolist())
        key.value = 0.0
    mesh.shape_keys.animation_data_clear()
    reset_pose_keys(obj)
    return obj, used, chosen_faces


def bake_skin_color(source, target, texture_path, resolution):
    TEXTURE_DIR.mkdir(parents=True, exist_ok=True)
    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'
    scene.cycles.samples = 1
    scene.cycles.device = 'CPU'
    scene.render.bake.use_selected_to_active = True
    scene.render.bake.max_ray_distance = 0.080
    scene.render.bake.cage_extrusion = 0.0
    scene.render.bake.margin = 16
    scene.render.bake.use_clear = True
    scene.render.bake.use_pass_color = True
    scene.render.bake.use_pass_direct = False
    scene.render.bake.use_pass_indirect = False
    image = bpy.data.images.new(f'TripoFaceSkin_{resolution}', width=resolution, height=resolution, alpha=False)
    image.file_format = 'PNG'
    image.colorspace_settings.name = 'sRGB'
    material = bpy.data.materials.new('Tripo projected face skin')
    material.use_nodes = True
    nodes = material.node_tree.nodes
    nodes.clear()
    output = nodes.new('ShaderNodeOutputMaterial')
    shader = nodes.new('ShaderNodeBsdfPrincipled')
    shader.inputs['Roughness'].default_value = 0.52
    image_node = nodes.new('ShaderNodeTexImage')
    image_node.image = image
    material.node_tree.links.new(shader.outputs['BSDF'], output.inputs['Surface'])
    nodes.active = image_node
    target.data.materials.clear()
    target.data.materials.append(material)
    bpy.ops.object.select_all(action='DESELECT')
    source.select_set(True)
    target.select_set(True)
    bpy.context.view_layer.objects.active = target
    bpy.ops.object.bake(type='DIFFUSE')
    image.filepath_raw = str(texture_path)
    image.save()
    image.pack()
    material.node_tree.links.new(image_node.outputs['Color'], shader.inputs['Base Color'])
    return {'resolution': [resolution, resolution], 'filepath': str(texture_path.relative_to(ROOT)), 'baked': True}


def transfer_projected_tripo_uv(source, target, skin_material, camera_location, camera_right,
                                camera_up, camera_forward, screen_scale):
    """Project target vertices through the matching view onto Tripo UV space."""
    source_world = np.asarray([(source.matrix_world @ vertex.co)[:] for vertex in source.data.vertices], dtype=np.float64)
    polygons = [list(poly.vertices) for poly in source.data.polygons]
    if any(len(face) != 3 for face in polygons):
        raise RuntimeError('The decimated Tripo face source must contain triangles for UV projection.')
    tree = BVHTree.FromPolygons(source_world.tolist(), polygons, all_triangles=True)
    source_uv = source.data.uv_layers.active
    if source_uv is None:
        raise RuntimeError('The Tripo face projection source has no UV map.')
    face_uvs = np.asarray([[tuple(source_uv.data[loop].uv) for loop in poly.loop_indices]
                           for poly in source.data.polygons], dtype=np.float64)
    face_vertices = np.asarray(polygons, dtype=np.int32)
    world = np.asarray([(target.matrix_world @ vertex.co)[:] for vertex in target.data.vertices], dtype=np.float64)
    pixels = screen_project(world, np.asarray(camera_location[:]),
                            np.asarray(camera_right[:]), np.asarray(camera_up[:]),
                            np.asarray(camera_forward[:]), screen_scale)
    uv = np.full((len(world), 2), np.nan, dtype=np.float64)
    origin_camera = Vector(camera_location)
    right_v, up_v, forward_v = Vector(camera_right), Vector(camera_up), Vector(camera_forward)
    for i, (sx, sy, _depth) in enumerate(pixels):
        origin = origin_camera + right_v * ((sx - 0.5) * screen_scale) + up_v * ((0.5 - sy) * screen_scale)
        location, _normal, face_index, _distance = tree.ray_cast(origin, forward_v, 3.0)
        if location is None or face_index is None or face_index >= len(face_vertices):
            continue
        ids = face_vertices[face_index]
        tri = source_world[ids]
        a, b, c = tri
        v0, v1, v2 = b - a, c - a, np.asarray(location[:]) - a
        d00, d01, d11 = v0 @ v0, v0 @ v1, v1 @ v1
        d20, d21 = v2 @ v0, v2 @ v1
        denominator = d00 * d11 - d01 * d01
        if abs(denominator) < 1e-16:
            continue
        w1 = (d11 * d20 - d01 * d21) / denominator
        w2 = (d00 * d21 - d01 * d20) / denominator
        weights = np.asarray([1.0 - w1 - w2, w1, w2])
        uv[i] = weights @ face_uvs[face_index]
    valid = np.isfinite(uv[:, 0])
    valid_count = int(valid.sum())
    if valid_count < len(world) * 0.90:
        raise RuntimeError(f'Tripo UV projection hit only {valid_count}/{len(world)} vertices on {target.name}')
    if valid_count < len(world):
        valid_screen = pixels[valid, :2]
        valid_uv = uv[valid]
        missing = np.flatnonzero(~valid)
        for start in range(0, len(missing), 512):
            ids = missing[start:start + 512]
            delta = pixels[ids, None, :2] - valid_screen[None, :, :]
            nearest = np.argmin(np.sum(delta * delta, axis=2), axis=1)
            uv[ids] = valid_uv[nearest]
    layer = target.data.uv_layers.active
    if layer is None:
        layer = target.data.uv_layers.new(name='UVMap')
    for poly in target.data.polygons:
        for loop_index in poly.loop_indices:
            layer.data[loop_index].uv = uv[target.data.loops[loop_index].vertex_index]
    target.data.materials.clear()
    target.data.materials.append(skin_material)
    return {'vertices': int(len(world)), 'rayHits': valid_count, 'rayHitFraction': valid_count / len(world)}


def render_face_color_projection(source, original_material, camera_location, camera_target, ortho_scale):
    """Render unlit Tripo face color in the registered landmark camera."""
    color_image = next((image for image in bpy.data.images if image.name.startswith('Color_')), None)
    if color_image is None:
        raise RuntimeError('The original Tripo base-color image is missing.')
    material = bpy.data.materials.new('Temporary Tripo face albedo projection')
    material.use_nodes = True
    nodes = material.node_tree.nodes
    nodes.clear()
    output = nodes.new('ShaderNodeOutputMaterial')
    emission = nodes.new('ShaderNodeEmission')
    uv = nodes.new('ShaderNodeTexCoord')
    texture = nodes.new('ShaderNodeTexImage')
    texture.image = color_image
    material.node_tree.links.new(uv.outputs['UV'], texture.inputs['Vector'])
    material.node_tree.links.new(texture.outputs['Color'], emission.inputs['Color'])
    material.node_tree.links.new(emission.outputs['Emission'], output.inputs['Surface'])
    source.data.materials.clear()
    source.data.materials.append(material)
    for obj in bpy.context.scene.objects:
        if obj.type == 'MESH':
            obj.hide_render = obj != source
    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_EEVEE'
    scene.render.resolution_x = 2048
    scene.render.resolution_y = 2048
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = True
    scene.render.image_settings.file_format = 'OPEN_EXR'
    scene.render.image_settings.color_mode = 'RGBA'
    scene.render.image_settings.color_depth = '32'
    scene.view_settings.view_transform = 'Standard'
    scene.view_settings.look = 'None'
    scene.view_settings.exposure = 0.0
    camera_data = bpy.data.cameras.new('Tripo face-color projection camera')
    camera = bpy.data.objects.new('Tripo face-color projection camera', camera_data)
    scene.collection.objects.link(camera)
    camera.location = camera_location
    camera.rotation_euler = (Vector(camera_target) - camera.location).to_track_quat('-Z', 'Y').to_euler()
    camera_data.type = 'ORTHO'
    camera_data.ortho_scale = ortho_scale
    scene.camera = camera
    projection_path = TEXTURE_DIR / 'tripo-face-screen-color.exr'
    TEXTURE_DIR.mkdir(parents=True, exist_ok=True)
    scene.render.filepath = str(projection_path)
    bpy.ops.render.render(write_still=True)
    image = bpy.data.images.load(str(projection_path), check_existing=False)
    pixels = np.empty(len(image.pixels), dtype=np.float32)
    image.pixels.foreach_get(pixels)
    return pixels.reshape((image.size[1], image.size[0], 4)), color_image, str(projection_path.relative_to(ROOT))


def bleed_rgba(rgb, valid, iterations):
    """Extend valid edge colors into transparent/unused pixels without wraparound."""
    colors = rgb.copy()
    mask = valid.copy()
    height, width = mask.shape
    shifts = [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1)]
    for _ in range(iterations):
        changed = False
        next_mask = mask.copy()
        for dy, dx in shifts:
            sy0, sy1 = max(0, -dy), min(height, height - dy)
            sx0, sx1 = max(0, -dx), min(width, width - dx)
            ty0, ty1 = max(0, dy), min(height, height + dy)
            tx0, tx1 = max(0, dx), min(width, width + dx)
            source_mask = mask[sy0:sy1, sx0:sx1]
            take = (~next_mask[ty0:ty1, tx0:tx1]) & source_mask
            if not np.any(take):
                continue
            target_view = colors[ty0:ty1, tx0:tx1]
            source_view = colors[sy0:sy1, sx0:sx1]
            target_view[take] = source_view[take]
            next_mask[ty0:ty1, tx0:tx1][take] = True
            changed = True
        mask = next_mask
        if not changed:
            break
    return colors, mask


def sample_bilinear(image, x, y):
    height, width = image.shape[:2]
    x = np.clip(x, 0.0, width - 1.001)
    y = np.clip(y, 0.0, height - 1.001)
    x0, y0 = np.floor(x).astype(np.int32), np.floor(y).astype(np.int32)
    x1, y1 = x0 + 1, y0 + 1
    fx, fy = (x - x0)[:, None], (y - y0)[:, None]
    return (image[y0, x0] * (1 - fx) * (1 - fy) + image[y0, x1] * fx * (1 - fy)
            + image[y1, x0] * (1 - fx) * fy + image[y1, x1] * fx * fy)


def screen_color_to_target_uv(target, screen_rgba, screen_scale, texture_resolution, texture_path):
    """Rasterize the registered screen-space color into the target UV atlas."""
    scene = bpy.context.scene
    scene.view_layers[0].update()
    camera_location = np.asarray(camera_location_global[:], dtype=np.float64)
    camera_right = np.asarray(camera_right_global[:], dtype=np.float64)
    camera_up = np.asarray(camera_up_global[:], dtype=np.float64)
    camera_forward = np.asarray(camera_forward_global[:], dtype=np.float64)
    world = np.asarray([(target.matrix_world @ vertex.co)[:] for vertex in target.data.vertices], dtype=np.float64)
    screen = screen_project(world, camera_location, camera_right, camera_up, camera_forward, screen_scale)
    uv_layer = target.data.uv_layers.active
    if uv_layer is None:
        raise RuntimeError(f'{target.name} has no UV layer to receive the color projection.')
    tex = np.zeros((texture_resolution, texture_resolution, 4), dtype=np.float32)
    mask = np.zeros((texture_resolution, texture_resolution), dtype=bool)
    source_valid = screen_rgba[:, :, 3] > 0.5
    screen_rgb, screen_valid = bleed_rgba(screen_rgba[:, :, :3], source_valid, 32)
    screen_image = np.concatenate((screen_rgb, screen_valid[:, :, None].astype(np.float32)), axis=2)
    screen_height, screen_width = screen_image.shape[:2]
    margin = 6.0
    for poly in target.data.polygons:
        if len(poly.loop_indices) != 3:
            continue
        loop_indices = list(poly.loop_indices)
        vertex_indices = [target.data.loops[index].vertex_index for index in loop_indices]
        tri_uv = np.asarray([tuple(uv_layer.data[index].uv) for index in loop_indices], dtype=np.float64)
        tri_screen = screen[vertex_indices, :2]
        x_min = max(0, int(np.floor(tri_uv[:, 0].min() * texture_resolution - margin)))
        x_max = min(texture_resolution, int(np.ceil(tri_uv[:, 0].max() * texture_resolution + margin)))
        y_min = max(0, int(np.floor(tri_uv[:, 1].min() * texture_resolution - margin)))
        y_max = min(texture_resolution, int(np.ceil(tri_uv[:, 1].max() * texture_resolution + margin)))
        if x_max <= x_min or y_max <= y_min:
            continue
        xs = (np.arange(x_min, x_max, dtype=np.float64) + 0.5) / texture_resolution
        ys = (np.arange(y_min, y_max, dtype=np.float64) + 0.5) / texture_resolution
        grid_u, grid_v = np.meshgrid(xs, ys)
        p0, p1, p2 = tri_uv
        denominator = (p1[1] - p2[1]) * (p0[0] - p2[0]) + (p2[0] - p1[0]) * (p0[1] - p2[1])
        if abs(denominator) < 1e-12:
            continue
        w0 = ((p1[1] - p2[1]) * (grid_u - p2[0]) + (p2[0] - p1[0]) * (grid_v - p2[1])) / denominator
        w1 = ((p2[1] - p0[1]) * (grid_u - p2[0]) + (p0[0] - p2[0]) * (grid_v - p2[1])) / denominator
        w2 = 1.0 - w0 - w1
        area_pixels = abs(denominator) * texture_resolution * texture_resolution
        edge_lengths = np.asarray([np.linalg.norm((tri_uv[1] - tri_uv[2]) * texture_resolution),
                                  np.linalg.norm((tri_uv[2] - tri_uv[0]) * texture_resolution),
                                  np.linalg.norm((tri_uv[0] - tri_uv[1]) * texture_resolution)])
        altitudes = np.maximum(area_pixels / np.maximum(edge_lengths, 1e-5), 1.0)
        inside = ((w0 >= -margin / altitudes[0]) & (w1 >= -margin / altitudes[1]) & (w2 >= -margin / altitudes[2]))
        if not np.any(inside):
            continue
        weights = np.stack((w0[inside], w1[inside], w2[inside]), axis=1)
        screen_points = weights @ tri_screen
        source_x = screen_points[:, 0] * screen_width - 0.5
        source_y = (1.0 - screen_points[:, 1]) * screen_height - 0.5
        sampled = sample_bilinear(screen_image, source_x, source_y)
        good = sampled[:, 3] > 0.5
        if not np.any(good):
            continue
        yy, xx = np.nonzero(inside)
        yy, xx = yy[good] + y_min, xx[good] + x_min
        tex[yy, xx, :3] = sampled[good, :3]
        tex[yy, xx, 3] = 1.0
        mask[yy, xx] = True
    tex[:, :, :3], padded = bleed_rgba(tex[:, :, :3], mask, 12)
    tex[:, :, 3] = padded.astype(np.float32)
    image = bpy.data.images.new(f'TripoScreenFace_{texture_resolution}', width=texture_resolution,
                                height=texture_resolution, alpha=True, float_buffer=False)
    image.colorspace_settings.name = 'sRGB'
    image.pixels.foreach_set(tex.ravel())
    image.update()
    image.filepath_raw = str(texture_path)
    image.file_format = 'PNG'
    image.save()
    image.pack()
    material = bpy.data.materials.new(target.name + ' Tripo-projected skin')
    material.use_nodes = True
    nodes = material.node_tree.nodes
    nodes.clear()
    output = nodes.new('ShaderNodeOutputMaterial')
    shader = nodes.new('ShaderNodeBsdfPrincipled')
    shader.inputs['Roughness'].default_value = 0.58
    texture = nodes.new('ShaderNodeTexImage')
    texture.image = image
    material.node_tree.links.new(texture.outputs['Color'], shader.inputs['Base Color'])
    material.node_tree.links.new(shader.outputs['BSDF'], output.inputs['Surface'])
    nodes.active = texture
    target.data.materials.clear()
    target.data.materials.append(material)
    return {'resolution': [texture_resolution, texture_resolution],
            'uvTexelsCoveredBeforeBleed': int(mask.sum()),
            'screenColorValidFraction': float(np.mean(screen_valid)),
            'texturePath': str(texture_path.relative_to(ROOT))}


if not all(path.is_file() for path in (SOURCE, DONOR, LANDMARKS, POINTS, FIT)):
    raise FileNotFoundError('The source GLBs, registration, and fitted-mesh data must exist before building.')
fitted_arrays = np.load(FIT)
lm_data = json.loads(LANDMARKS.read_text(encoding='utf-8'))
landmark_pixels = np.asarray(lm_data['landmarks'], dtype=np.float64)
point_data = json.loads(POINTS.read_text(encoding='utf-8'))
target_points = np.asarray(point_data['targetPoints'], dtype=np.float64)

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(SOURCE))
scene = bpy.context.scene
tripo_meshes = [o for o in scene.objects if o.type == 'MESH' and o.name != 'Icosphere']
if len(tripo_meshes) != 1:
    raise RuntimeError(f'Expected one Tripo character mesh: {[o.name for o in tripo_meshes]}')
body = tripo_meshes[0]
armature = next((o for o in scene.objects if o.type == 'ARMATURE'), None)
if armature is None:
    raise RuntimeError('The Mixamo armature is missing from the Tripo source.')
head_bone = next((bone for bone in armature.data.bones if bone.name.lower().endswith(':head')), None)
if head_bone is None:
    raise RuntimeError('The Mixamo Head bone is missing.')
head_pose = armature.pose.bones[head_bone.name]
bone_world = armature.matrix_world @ head_pose.matrix
bone_inverse = bone_world.inverted()

# The source is reduced only in this derivative. Move its decimator ahead of
# the armature modifier so rest-pose skin weights remain associated correctly.
armature_indices = [i for i, mod in enumerate(body.modifiers) if mod.type == 'ARMATURE']
decimate = body.modifiers.new('Face-transfer derivative optimization', 'DECIMATE')
decimate.ratio = 0.30
if armature_indices:
    body.modifiers.move(len(body.modifiers) - 1, 0)
bpy.context.view_layer.objects.active = body
body.select_set(True)
bpy.ops.object.modifier_apply(modifier=decimate.name)

# Registration camera and visible Tripo face mask.
camera_location = Vector((1.0, 0.0, 0.82))
camera_target = Vector((0.0, 0.0, 0.82))
camera_rotation = (camera_target - camera_location).to_track_quat('-Z', 'Y')
camera_right = camera_rotation @ Vector((1, 0, 0))
camera_up = camera_rotation @ Vector((0, 1, 0))
camera_forward = camera_rotation @ Vector((0, 0, -1))
camera_location_global = camera_location.copy()
camera_right_global = camera_right.copy()
camera_up_global = camera_up.copy()
camera_forward_global = camera_forward.copy()
right = np.asarray(camera_right[:], dtype=np.float64)
up = np.asarray(camera_up[:], dtype=np.float64)
forward = np.asarray(camera_forward[:], dtype=np.float64)
cam = np.asarray(camera_location[:], dtype=np.float64)
face_polygon = landmark_pixels[FACE_OVAL, :2]
if FACE_OVAL_EXPANSION != 1.0:
    face_polygon = face_polygon.mean(axis=0) + (face_polygon - face_polygon.mean(axis=0)) * FACE_OVAL_EXPANSION
valid = np.isfinite(target_points[:, 0])
target_xy = landmark_pixels[valid, :2]
target_depth = (target_points[valid] - cam) @ forward
ipd = float(np.linalg.norm((landmark_pixels[33, :2] - landmark_pixels[263, :2]) * 0.20))
depth_tolerance = max(ipd * FACE_DEPTH_TOLERANCE_IPD, 0.003)
coords = np.empty((len(body.data.vertices), 3), dtype=np.float64)
body.data.vertices.foreach_get('co', coords.ravel())
world_matrix = np.asarray(body.matrix_world, dtype=np.float64)
world = coords @ world_matrix[:3, :3].T + world_matrix[:3, 3]
screen = screen_project(world, cam, right, up, forward, 0.20)
inside = point_in_polygon(screen[:, 0], screen[:, 1], face_polygon)
candidate = np.flatnonzero(inside)
nearest_landmark = np.empty(len(candidate), dtype=np.int32)
for start in range(0, len(candidate), 4000):
    ids = candidate[start:start + 4000]
    dx = screen[ids, 0, None] - target_xy[None, :, 0]
    dy = screen[ids, 1, None] - target_xy[None, :, 1]
    nearest_landmark[start:start + len(ids)] = np.argmin(dx * dx + dy * dy, axis=1)
face_mask = np.zeros(len(world), dtype=bool)
face_mask[candidate] = np.abs(screen[candidate, 2] - target_depth[nearest_landmark]) <= depth_tolerance

# Remove the Tripo front-face triangles within its registered face oval. This
# avoids a second face surface covering the fitted lip, eye, and eyelid meshes.
bm = bmesh.new()
bm.from_mesh(body.data)
bm.verts.ensure_lookup_table()
bm.verts.index_update()
bm.faces.ensure_lookup_table()
bm.faces.index_update()
remove_faces = []
for face in bm.faces:
    if len(face.verts) != 3:
        continue
    ids = np.asarray([v.index for v in face.verts], dtype=np.int32)
    if not np.all(face_mask[ids]):
        continue
    center = world[ids].mean(axis=0)
    pixel = screen_project(center[None], cam, right, up, forward, 0.20)[0]
    if point_in_polygon(np.asarray([pixel[0]]), np.asarray([pixel[1]]), face_polygon)[0]:
        remove_faces.append(face)
removed_tripo_faces = len(remove_faces)
if removed_tripo_faces < 1000:
    bm.free()
    raise RuntimeError(f'Face cut removed too few registered Tripo triangles: {removed_tripo_faces}')

# Use the exact registered Tripo skin triangles as a target surface for the
# fitted donor face. This closes the source/patch depth mismatch while keeping
# the donor's actual speech and eyelid deformation deltas.
target_face_triangles = np.asarray([[v.index for v in face.verts] for face in remove_faces], dtype=np.int32)
target_face_bvh = BVHTree.FromPolygons(world.tolist(), target_face_triangles.tolist(), all_triangles=True)

# Preserve a face-only source by default. Full-source mode also projects the
# original Tripo pixels under the fitted patch boundary to prevent empty atlas
# pixels where the fitted surface extends beyond the removed face triangles.
bake_source = body.copy()
bake_source.data = body.data.copy()
scene.collection.objects.link(bake_source)
bake_source.name = 'TripoFaceOnlyTextureSource'
keep_face_indices = {face.index for face in remove_faces}
if COLOR_SOURCE_MODE != 'full':
    bake_bm = bmesh.new()
    bake_bm.from_mesh(bake_source.data)
    bake_bm.faces.ensure_lookup_table()
    discard_bake_faces = [face for index, face in enumerate(bake_bm.faces) if index not in keep_face_indices]
    bmesh.ops.delete(bake_bm, geom=discard_bake_faces, context='FACES_ONLY')
    bake_bm.to_mesh(bake_source.data)
    bake_bm.free()
    bake_source.data.update()

bmesh.ops.delete(bm, geom=remove_faces, context='FACES_ONLY')
bm.to_mesh(body.data)
bm.free()
body.data.update()

# Import donor mesh topology and apply the precomputed non-rigid face fit.
bpy_objects_before_donor = set(scene.objects)
bpy.ops.import_scene.gltf(filepath=str(DONOR))
donor_objects = set(scene.objects) - bpy_objects_before_donor
donors = {o.name: o for o in donor_objects if o.type == 'MESH'}
required_parts = {'Head_Mesh', 'Eye_Mesh', 'EyeAO_Mesh', 'Eyelash_Mesh', 'Teeth_Mesh', 'Tongue_Mesh'}
if not required_parts.issubset(donors):
    raise RuntimeError(f'Facial donor parts missing: {sorted(required_parts - set(donors))}')

created = []
for part in ['Head_Mesh', 'Eye_Mesh', 'EyeAO_Mesh', 'Eyelash_Mesh', 'Teeth_Mesh', 'Tongue_Mesh']:
    source_obj = donors[part]
    prefix = part.replace('.', '_')
    fitted = fitted_arrays[prefix + '__Basis'].astype(np.float64)
    triangles = fitted_arrays[prefix + '__Triangles'].astype(np.int32)
    if part == 'Head_Mesh':
        face_world = fitted[triangles]
        centers = face_world.mean(axis=1)
        projected = screen_project(centers, cam, right, up, forward, 0.20)
        inside_face = point_in_polygon(projected[:, 0], projected[:, 1], face_polygon)
        normals = np.cross(face_world[:, 1] - face_world[:, 0], face_world[:, 2] - face_world[:, 0])
        toward_camera = normals @ -forward
        selected = (np.ones(len(triangles), dtype=bool) if FACE_PATCH_SCOPE == 'full-head'
                    else inside_face & (toward_camera > 0.0))
        chosen = np.flatnonzero(selected)
        used = np.unique(triangles[chosen].ravel())
        correction = np.zeros_like(fitted)
        snapped = fitted[used].copy()
        snap_distances = np.zeros(len(used), dtype=np.float64)
        if SURFACE_CONFORM:
            for vertex_index, point in enumerate(snapped):
                nearest = target_face_bvh.find_nearest(point)
                if nearest and nearest[0] is not None:
                    snapped[vertex_index] = np.asarray(nearest[0][:], dtype=np.float64)
                    snap_distances[vertex_index] = nearest[3]
        correction[used] = snapped - fitted[used]
        fitted = fitted.copy()
        fitted[used] = snapped
        fitted_arrays_for_head = True
        face_surface_fit = {
            'method': ('Nearest point projection of fitted animation-ready face vertices onto the exact Tripo facial triangles removed for the replacement patch.' if SURFACE_CONFORM else 'Surface projection disabled for this geometry-coverage experiment; donor ARAP fit retained.'),
            'vertexCount': int(len(used)),
            'displacementMillimeters': {
                'median': float(np.median(snap_distances) * 1000),
                'p95': float(np.percentile(snap_distances, 95) * 1000),
                'max': float(np.max(snap_distances) * 1000),
                'over10mm': int(np.sum(snap_distances > 0.010)),
            },
        }
    else:
        selected = None
        correction = None
    obj, used_vertices, used_faces = create_part(
        source_obj, fitted, triangles, 'VelaTripo' + part.replace('_Mesh', ''),
        armature, head_bone, bone_inverse, selected, correction)
    created.append(obj)
    if part == 'Head_Mesh':
        head_patch = obj
        head_source_for_uv = source_obj
        head_selected_faces = used_faces
        head_used_vertices = used_vertices

if len(head_selected_faces) < 1000:
    raise RuntimeError(f'Fitted face patch retained too few triangles: {len(head_selected_faces)}')

# Render the original face albedo in the registration camera, then rasterize
# that screen color into each fitted facial mesh's own continuous UV atlas.
screen_rgba, _source_color_image, screen_projection_path = render_face_color_projection(
    bake_source, body.data.materials[0], camera_location, camera_target, 0.20)
bake = {'method': f'registered screen-space Tripo {COLOR_SOURCE_MODE}-source color transfer rasterized into the fitted facial UV atlases',
        'sourceMaterial': body.data.materials[0].name,
        'sourceScreenProjection': screen_projection_path,
        'sourceTexture': next((image.name for image in bpy.data.images if image.name.startswith('Color_')), None),
        'targets': {}}
for obj, filename, resolution in zip(created[:4], [
    'tripo-facefit-head-projected-2k.png',
    'tripo-facefit-eyes-projected-1k.png',
    'tripo-facefit-eyeao-projected-1k.png',
    'tripo-facefit-lashes-projected-1k.png',
], [2048, 1024, 1024, 1024]):
    bake['targets'][obj.name] = screen_color_to_target_uv(
        obj, screen_rgba, 0.20, resolution, TEXTURE_DIR / filename)

# Remove imported donor scene objects and its unused armature; new facial parts
# follow only the preserved Mixamo Head bone.
for donor in donor_objects:
    bpy.data.objects.remove(donor, do_unlink=True)
bpy.data.objects.remove(bake_source, do_unlink=True)
for obj in list(scene.objects):
    if obj.type == 'MESH' and obj.name == 'Icosphere':
        bpy.data.objects.remove(obj, do_unlink=True)

# Export a reproducible prototype, leaving the currently served facial GLB in place.
scene.render.engine = 'BLENDER_EEVEE'
scene.render.image_settings.file_format = 'PNG'
bpy.ops.object.select_all(action='DESELECT')
for obj in scene.objects:
    if obj.type in {'MESH', 'ARMATURE', 'EMPTY'}:
        obj.select_set(True)
bpy.context.view_layer.objects.active = body
bpy.ops.export_scene.gltf(filepath=str(OUTPUT), export_format='GLB', export_morph=True,
                          export_skins=True, export_animations=True, export_apply=False)

report = {
    'status': 'PROTOTYPE_BUILT_REQUIRES_RENDER_REVIEW',
    'sourceTripoPreserved': True, 'sourceMixamoPreserved': True,
    'source': str(SOURCE.relative_to(ROOT)), 'donor': str(DONOR.relative_to(ROOT)),
    'output': str(OUTPUT.relative_to(ROOT)),
    'removedTripoFaceTriangles': removed_tripo_faces,
    'retainedFittedFaceTriangles': int(len(head_selected_faces)),
    'retainedFittedFaceVertices': int(len(head_used_vertices)),
    'facePatchScope': FACE_PATCH_SCOPE,
    'faceCutCoverage': {'ovalExpansion': FACE_OVAL_EXPANSION, 'depthToleranceIPD': FACE_DEPTH_TOLERANCE_IPD},
    'faceSurfaceFit': face_surface_fit,
    'textureTransfer': bake,
    'facialParts': [obj.name for obj in created],
    'facialMorphs': {obj.name: [key.name for key in (obj.data.shape_keys.key_blocks if obj.data.shape_keys else [])] for obj in created},
    'limitations': ['No morph-frame image review or Vela runtime test has been run yet.', 'The topology fit still has unresolved face-oval outliers and visible jaw/blink quality issues in the donor preview.'],
}
REPORT.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
print(json.dumps(report, indent=2))
