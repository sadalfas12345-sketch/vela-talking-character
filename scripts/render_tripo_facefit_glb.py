"""Render neutral and full-influence faces from the exported prototype GLB."""
import json
import os
from pathlib import Path

import bpy
from mathutils import Vector

root = Path(__file__).resolve().parents[1]
glb = Path(os.environ.get('VELA_FACEFIT_GLB', str(root / 'assets' / 'tripo' / 'vela-photoreal' / 'vela-photoreal-facefit-prototype.glb')))
out_dir = Path(os.environ.get('VELA_FACEFIT_RENDER_DIR', str(root / 'assets' / 'tripo' / 'vela-photoreal' / 'verification' / 'facefit-prototype')))
out_dir.mkdir(parents=True, exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(glb))
scene = bpy.context.scene
meshes = [obj for obj in scene.objects if obj.type == 'MESH']
camera_data = bpy.data.cameras.new('Tripo Face Fit GLB Review Camera')
camera = bpy.data.objects.new('Tripo Face Fit GLB Review Camera', camera_data)
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
    scene.world = bpy.data.worlds.new('Face Fit Review World')
scene.world.color = (0.05, 0.05, 0.05)
states = {
    'neutral': {},
    'jawOpen': {'jawOpen': 1.0},
    'viseme_PP': {'viseme_PP': 1.0},
    'viseme_O': {'viseme_O': 1.0},
    'viseme_E': {'viseme_E': 1.0},
    'eyeBlinkLeft': {'eyeBlinkLeft': 1.0},
    'eyeBlinkRight': {'eyeBlinkRight': 1.0},
    'mouthSmileLeft': {'mouthSmileLeft': 1.0},
    'browInnerUp': {'browInnerUp': 1.0},
}
captures = []
for state, values in states.items():
    for obj in meshes:
        if not obj.data.shape_keys:
            continue
        for key in obj.data.shape_keys.key_blocks:
            key.value = values.get(key.name, 0.0)
    scene.render.filepath = str(out_dir / f'{state}.png')
    bpy.ops.render.render(write_still=True)
    captures.append(str((out_dir / f'{state}.png').relative_to(root)))
report = {'glb': str(glb.relative_to(root)), 'captures': captures, 'states': list(states)}
(out_dir / 'render-report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
print(json.dumps(report, indent=2))
