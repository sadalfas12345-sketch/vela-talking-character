"""Prototype Tripo albedo projection onto the fitted Avaturn head, without GLB edits."""
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector

root = Path(__file__).resolve().parents[1]
avatar_path = root / 'TalkingHead' / 'avatars' / 'avaturn.glb'
tripo_path = root / 'assets' / 'tripo' / 'vela-photoreal' / 'generated-rigged.glb'
fit_path = root / 'verification' / 'avaturn-tripo-facefit-deformed.npz'
out_dir = root / 'verification' / 'tripo-facefit-texture-test'
out_dir.mkdir(parents=True, exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(tripo_path))
tripo_objects = [o for o in bpy.context.scene.objects if o.type == 'MESH' and o.name != 'Icosphere']
if len(tripo_objects) != 1:
    raise RuntimeError(f'Expected one Tripo source mesh, got {len(tripo_objects)}')
source = tripo_objects[0]
source.name = 'TripoTextureProjectionSource'
bpy.ops.import_scene.gltf(filepath=str(avatar_path))
donor_objects = {o.name: o for o in bpy.context.scene.objects if o.type == 'MESH'}
head = donor_objects['Head_Mesh']
fit = np.load(fit_path)
fit_head = fit['Head_Mesh__Basis']
if len(fit_head) != len(head.data.vertices):
    raise RuntimeError('Fitted head vertex count differs from the donor')
inverse = head.matrix_world.inverted()
for i, point in enumerate(fit_head):
    head.data.vertices[i].co = inverse @ Vector(point.tolist())
if head.data.shape_keys:
    basis = head.data.shape_keys.key_blocks['Basis']
    for i, point in enumerate(fit_head):
        basis.data[i].co = inverse @ Vector(point.tolist())
head.data.update()

scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.samples = 1
scene.cycles.device = 'CPU'
scene.render.resolution_percentage = 100
scene.render.bake.use_selected_to_active = True
scene.render.bake.max_ray_distance = 0.035
scene.render.bake.cage_extrusion = 0.01
scene.render.bake.use_pass_color = True
scene.render.bake.use_pass_direct = False
scene.render.bake.use_pass_indirect = False
image = bpy.data.images.new('TripoFaceProjectionTest', width=2048, height=2048, alpha=False)
image.file_format = 'PNG'
material = bpy.data.materials.new('Tripo face texture bake test')
material.use_nodes = True
nodes = material.node_tree.nodes
nodes.clear()
output = nodes.new('ShaderNodeOutputMaterial')
shader = nodes.new('ShaderNodeBsdfPrincipled')
texture = nodes.new('ShaderNodeTexImage')
texture.image = image
material.node_tree.links.new(texture.outputs['Color'], shader.inputs['Base Color'])
material.node_tree.links.new(shader.outputs['BSDF'], output.inputs['Surface'])
nodes.active = texture
head.data.materials.clear()
head.data.materials.append(material)

# Keep the proxy target and high-poly source selected; the target is active.
bpy.ops.object.select_all(action='DESELECT')
source.select_set(True)
head.select_set(True)
bpy.context.view_layer.objects.active = head
bpy.ops.object.bake(type='DIFFUSE')
image.filepath_raw = str(out_dir / 'face-albedo-2k.png')
image.save()

# Render the baked head in the target camera to check projection coverage.
source.hide_render = True
for obj in donor_objects.values():
    obj.hide_render = obj != head
scene.render.engine = 'BLENDER_EEVEE'
scene.render.resolution_x = 1024
scene.render.resolution_y = 1024
scene.render.image_settings.file_format = 'PNG'
scene.view_settings.view_transform = 'Standard'
scene.view_settings.look = 'Medium High Contrast'
scene.view_settings.exposure = -1.0
camera_data = bpy.data.cameras.new('Projection Check Camera')
camera = bpy.data.objects.new('Projection Check Camera', camera_data)
scene.collection.objects.link(camera)
camera.location = (1, 0, 0.82)
camera.rotation_euler = (Vector((0, 0, 0.82)) - camera.location).to_track_quat('-Z', 'Y').to_euler()
camera_data.type = 'ORTHO'
camera_data.ortho_scale = 0.20
scene.camera = camera
for name, location, power, size in [
    ('Key', (0.4, -0.35, 1.1), 70, 0.6),
    ('Fill', (0.25, 0.42, 0.85), 30, 0.8),
    ('Rim', (-0.25, 0.1, 1.05), 45, 0.5),
]:
    data = bpy.data.lights.new(name, 'AREA')
    data.energy, data.shape, data.size = power, 'DISK', size
    light = bpy.data.objects.new(name, data)
    scene.collection.objects.link(light)
    light.location = location
    light.rotation_euler = (Vector((0, 0, 0.88)) - light.location).to_track_quat('-Z', 'Y').to_euler()
if scene.world is None:
    scene.world = bpy.data.worlds.new('Projection Preview World')
scene.world.color = (0.05, 0.05, 0.05)
scene.render.filepath = str(out_dir / 'face-albedo-preview.png')
bpy.ops.render.render(write_still=True)
print(f'Baked {image.size[0]}x{image.size[1]} Tripo albedo to {image.filepath_raw}')
