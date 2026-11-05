import json
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector

root = Path(__file__).resolve().parents[1]
source = root / 'TalkingHead' / 'avatars' / 'avaturn.glb'
arrays = np.load(root / 'verification' / 'avaturn-tripo-facefit-deformed.npz')
out_dir = root / 'verification' / 'avaturn-tripo-facefit-preview'
out_dir.mkdir(parents=True, exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(source))
parts = {'Head_Mesh', 'Eye_Mesh', 'EyeAO_Mesh', 'Eyelash_Mesh', 'Teeth_Mesh', 'Tongue_Mesh'}
objects = {o.name: o for o in bpy.context.scene.objects if o.type == 'MESH'}
for obj in objects.values():
    obj.hide_render = obj.name not in parts
    if obj.name not in parts:
        continue
    prefix = obj.name.replace('.', '_')
    inv = obj.matrix_world.inverted()
    basis = arrays[prefix + '__Basis']
    if len(basis) != len(obj.data.vertices):
        raise RuntimeError(f'{obj.name} vertex count changed: {len(basis)} vs {len(obj.data.vertices)}')
    for i, point in enumerate(basis):
        obj.data.vertices[i].co = inv @ Vector(point.tolist())
    keys = obj.data.shape_keys.key_blocks if obj.data.shape_keys else []
    for key in keys:
        key.value = 0.0
        if key.name == 'Basis':
            for i, point in enumerate(basis):
                key.data[i].co = inv @ Vector(point.tolist())
            continue
        array_key = prefix + '__Key__' + key.name
        if array_key not in arrays:
            continue
        coords = arrays[array_key]
        for i, point in enumerate(coords):
            key.data[i].co = inv @ Vector(point.tolist())
    obj.data.update()

scene = bpy.context.scene
scene.render.engine = 'BLENDER_EEVEE'
scene.render.resolution_x = 1024
scene.render.resolution_y = 1024
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'PNG'
scene.view_settings.view_transform = 'Standard'
scene.view_settings.look = 'Medium High Contrast'
scene.view_settings.exposure = -1.0
cam_data = bpy.data.cameras.new('Tripo Face Fit Preview Camera')
camera = bpy.data.objects.new('Tripo Face Fit Preview Camera', cam_data)
scene.collection.objects.link(camera)
camera.location = (1, 0, 0.82)
camera.rotation_euler = (Vector((0, 0, 0.82)) - camera.location).to_track_quat('-Z', 'Y').to_euler()
cam_data.type = 'ORTHO'
cam_data.ortho_scale = 0.20
scene.camera = camera
for name, location, power, size in [
    ('Key', (0.4, -0.35, 1.1), 70, 0.6),
    ('Fill', (0.25, 0.42, 0.85), 30, 0.8),
    ('Rim', (-0.25, 0.1, 1.05), 45, 0.5),
]:
    data = bpy.data.lights.new(name, 'AREA')
    data.energy = power
    data.shape = 'DISK'
    data.size = size
    light = bpy.data.objects.new(name, data)
    scene.collection.objects.link(light)
    light.location = location
    light.rotation_euler = (Vector((0, 0, 0.88)) - light.location).to_track_quat('-Z', 'Y').to_euler()
scene.world = bpy.data.worlds.new('Preview World') if scene.world is None else scene.world
scene.world.color = (0.05, 0.05, 0.05)
captures = []
states = [
    ('neutral', {}),
    ('jaw-open', {'Head_Mesh': {'jawOpen': 1.0}, 'Teeth_Mesh': {'jawOpen': 1.0}, 'Tongue_Mesh': {'jawOpen': 1.0}}),
    ('blink-left', {'Head_Mesh': {'eyeBlinkLeft': 1.0}, 'EyeAO_Mesh': {'eyeBlinkLeft': 1.0}, 'Eyelash_Mesh': {'eyeBlinkLeft': 1.0}}),
    ('smile-left', {'Head_Mesh': {'mouthSmileLeft': 1.0}, 'EyeAO_Mesh': {'mouthSmileLeft': 1.0}, 'Eyelash_Mesh': {'mouthSmileLeft': 1.0}}),
]
for name, activations in states:
    for obj in objects.values():
        if obj.type != 'MESH' or not obj.data.shape_keys:
            continue
        for key in obj.data.shape_keys.key_blocks:
            key.value = activations.get(obj.name, {}).get(key.name, 0.0)
    scene.render.filepath = str(out_dir / f'{name}.png')
    bpy.ops.render.render(write_still=True)
    captures.append(str((out_dir / f'{name}.png').relative_to(root)))
(out_dir / 'preview.json').write_text(json.dumps({'captures': captures, 'states': [x[0] for x in states]}, indent=2) + '\n')
print(json.dumps({'captures': captures}, indent=2))
