"""Render the original-Tripo deformation-transfer proof at neutral and full influence."""
import json
import os
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
GLB = Path(os.environ.get('VELA_ORIGINAL_TRANSFER_GLB', ROOT / 'assets/tripo/vela-photoreal/intermediates/vela-original-tripo-jawOpen-transfer-proof.glb'))
OUT = Path(os.environ.get('VELA_ORIGINAL_TRANSFER_RENDER_DIR', ROOT / 'verification/vela-original-tripo-jawOpen-transfer-proof-render'))
OUT.mkdir(parents=True, exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(GLB))
scene = bpy.context.scene
camera_data = bpy.data.cameras.new('Original Tripo Transfer Proof Camera')
camera = bpy.data.objects.new('Original Tripo Transfer Proof Camera', camera_data)
scene.collection.objects.link(camera)
camera.location = (1, 0, 0.87)
camera.rotation_euler = (Vector((0, 0, 0.87)) - camera.location).to_track_quat('-Z', 'Y').to_euler()
camera_data.type = 'ORTHO'
camera_data.ortho_scale = 0.25
scene.camera = camera
scene.render.engine = 'BLENDER_EEVEE'
scene.render.resolution_x = 1024
scene.render.resolution_y = 1024
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'PNG'
scene.view_settings.view_transform = 'Standard'
scene.view_settings.look = 'Medium High Contrast'
scene.view_settings.exposure = -2.0
for name, location, power, size in [
    ('Key', (0.4, -0.35, 1.1), 70, 0.6),
    ('Fill', (0.25, 0.42, 0.85), 30, 0.8),
    ('Rim', (-0.25, 0.1, 1.05), 45, 0.5),
]:
    data = bpy.data.lights.new(name, 'AREA')
    data.energy, data.shape, data.size = power, 'DISK', size
    obj = bpy.data.objects.new(name, data)
    scene.collection.objects.link(obj)
    obj.location = location
    obj.rotation_euler = (Vector((0, 0, 0.88)) - obj.location).to_track_quat('-Z', 'Y').to_euler()
if scene.world is None:
    scene.world = bpy.data.worlds.new('Original Tripo Transfer Proof World')
scene.world.color = (0.05, 0.05, 0.05)
meshes = [obj for obj in scene.objects if obj.type == 'MESH']
if os.environ.get('VELA_HIDE_CAVITY') == '1':
    for obj in meshes:
        if 'cavity' in obj.name.lower():
            obj.hide_render = True
key_name = os.environ.get('VELA_ORIGINAL_TRANSFER_KEY', 'xfer_jawOpen_original_tripo')
captures = []
for state, value in [('neutral', 0.0), ('jawOpenTransfer', 1.0)]:
    for obj in meshes:
        if not obj.data.shape_keys:
            continue
        for key in obj.data.shape_keys.key_blocks:
            key.value = value if key.name == key_name else 0.0
    path = OUT / f'{state}.png'
    scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    captures.append(str(path.relative_to(ROOT)))
(OUT / 'render-report.json').write_text(json.dumps({'glb': str(GLB.relative_to(ROOT)), 'key': key_name, 'captures': captures}, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'glb': str(GLB.relative_to(ROOT)), 'key': key_name, 'captures': captures}, indent=2))
