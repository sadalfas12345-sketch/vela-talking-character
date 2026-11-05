"""Test explicit upper- and lower-lip commands without speech or donor weights."""
import json
import os
from pathlib import Path
import bpy
import numpy as np
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
GLB = Path(os.environ.get('VELA_CANDIDATE_GLB', ROOT / 'verification/vela-original-tripo-local-mouth-v15.glb'))
OUT = Path(os.environ.get('VELA_LIP_CONTROL_RENDER_DIR', ROOT / 'verification/vela-original-tripo-local-mouth-v15-independent-lip-controls'))
OUT.mkdir(parents=True, exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(GLB))
scene = bpy.context.scene
rim = next(obj for obj in scene.objects if obj.type == 'MESH' and 'lip boundary' in obj.name.lower())
center = Vector((0.0618627, 0.0031152, 0.8529158))
up = (Vector((0.0, 0.0, 0.82)) - Vector((1.0, 0.0, 0.82))).to_track_quat('-Z', 'Y') @ Vector((0, 0, 1))
world_matrix = rim.matrix_world
inverse = world_matrix.inverted()
coords = np.empty((len(rim.data.vertices), 3), dtype=np.float64)
rim.data.vertices.foreach_get('co', coords.ravel())
world = coords @ np.asarray(world_matrix, dtype=np.float64)[:3, :3].T + np.asarray(world_matrix, dtype=np.float64)[:3, 3]
vertical = np.asarray([(Vector(point.tolist()) - center).dot(up) for point in world])
for name, selector, direction in [
    ('test_upperLip_down', vertical >= 0.0, -1.0),
    ('test_lowerLip_up', vertical < 0.0, 1.0),
]:
    key = rim.shape_key_add(name=name, from_mix=False)
    moved = coords.copy()
    for index in np.flatnonzero(selector):
        point = Vector(world[index].tolist()) + up * (direction * 0.003)
        moved[index] = np.asarray((inverse @ point)[:], dtype=np.float64)
    key.data.foreach_set('co', moved.astype(np.float32).ravel())
    key.value = 0.0

camera_data = bpy.data.cameras.new('Independent lip control camera')
camera = bpy.data.objects.new('Independent lip control camera', camera_data)
scene.collection.objects.link(camera)
camera.location = (1.0, center.y, center.z)
camera.rotation_euler = (center - camera.location).to_track_quat('-Z', 'Y').to_euler()
camera_data.type = 'ORTHO'
camera_data.ortho_scale = 0.06
scene.camera = camera
scene.render.engine = 'BLENDER_EEVEE'
scene.render.resolution_x = 1024
scene.render.resolution_y = 1024
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'PNG'
scene.view_settings.view_transform = 'Standard'
scene.view_settings.look = 'Medium High Contrast'
scene.view_settings.exposure = -1.0
for name, location, power in [('key', (0.4, -0.3, 0.95), 100), ('fill', (0.5, 0.3, 0.85), 60)]:
    data = bpy.data.lights.new(name, 'AREA')
    data.energy, data.shape, data.size = power, 'DISK', 0.2
    light = bpy.data.objects.new(name, data)
    scene.collection.objects.link(light)
    light.location = location
    light.rotation_euler = (center - light.location).to_track_quat('-Z', 'Y').to_euler()
states = [
    ('upperLipDown', {'test_upperLip_down': 1.0}),
    ('lowerLipUp', {'test_lowerLip_up': 1.0}),
    ('upperAndLowerIndependent', {'test_upperLip_down': 1.0, 'test_lowerLip_up': 1.0}),
]
for name, controls in states:
    for key in rim.data.shape_keys.key_blocks:
        key.value = controls.get(key.name, 0.0)
    scene.render.filepath = str(OUT / f'{name}.png')
    bpy.ops.render.render(write_still=True)
report = {'candidate': str(GLB.relative_to(ROOT)), 'controls': [name for name, _ in states], 'upperDisplacementMeters': 0.003, 'lowerDisplacementMeters': 0.003}
(OUT / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
