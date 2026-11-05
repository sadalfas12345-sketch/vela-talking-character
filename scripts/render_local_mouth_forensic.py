"""Render a close forensic view of the exported V12 local mouth objects."""
import json
import os
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
GLB = Path(os.environ.get('VELA_FORENSIC_GLB', ROOT / 'verification/vela-original-tripo-local-mouth-v12.glb'))
OUT = Path(os.environ.get('VELA_FORENSIC_RENDER_DIR', ROOT / 'verification/vela-original-tripo-local-mouth-v12-forensic-render'))
OUT.mkdir(parents=True, exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(GLB))
scene = bpy.context.scene
target = Vector((0.0618627, 0.0031152, 0.8529158))
camera_data = bpy.data.cameras.new('V12 forensic mouth camera')
camera = bpy.data.objects.new('V12 forensic mouth camera', camera_data)
scene.collection.objects.link(camera)
camera.location = (1.0, target.y, target.z)
camera.rotation_euler = (target - camera.location).to_track_quat('-Z', 'Y').to_euler()
camera_data.type = 'ORTHO'
camera_data.ortho_scale = 0.060
scene.camera = camera
scene.render.engine = 'BLENDER_EEVEE'
scene.render.resolution_x = 1024
scene.render.resolution_y = 1024
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'PNG'
scene.view_settings.view_transform = 'Standard'
scene.view_settings.look = 'Medium High Contrast'
scene.view_settings.exposure = -1.0
world = bpy.data.worlds.new('V12 forensic world')
scene.world = world
world.color = (0.015, 0.015, 0.015)
for name, location, power, size in [
    ('Forensic key', (0.4, -0.3, 0.95), 120, 0.2),
    ('Forensic fill', (0.5, 0.3, 0.85), 80, 0.2),
]:
    data = bpy.data.lights.new(name, 'AREA')
    data.energy, data.shape, data.size = power, 'DISK', size
    obj = bpy.data.objects.new(name, data)
    scene.collection.objects.link(obj)
    obj.location = location
    obj.rotation_euler = (target - obj.location).to_track_quat('-Z', 'Y').to_euler()

def diagnostic_material(name, color):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (*color, 1.0)
    mat.use_nodes = True
    shader = mat.node_tree.nodes.get('Principled BSDF')
    if shader:
        shader.inputs['Base Color'].default_value = (*color, 1.0)
        shader.inputs['Roughness'].default_value = 0.35
        if 'Emission Color' in shader.inputs:
            shader.inputs['Emission Color'].default_value = (*color, 1.0)
            shader.inputs['Emission Strength'].default_value = 0.25
    return mat

colors = {
    'lip boundary': (1.0, 0.8, 0.02),
    'mouth cavity': (0.05, 0.45, 1.0),
    'upper teeth': (1.0, 1.0, 1.0),
    'lower tongue': (1.0, 0.05, 0.2),
}
meshes = [obj for obj in scene.objects if obj.type == 'MESH']
for obj in meshes:
    lower = obj.name.lower()
    match = next((key for key in colors if key in lower), None)
    if match:
        obj.data.materials.clear()
        obj.data.materials.append(diagnostic_material('Forensic ' + match, colors[match]))
        for poly in obj.data.polygons:
            poly.use_smooth = False
    elif lower.startswith('tripo_'):
        if os.environ.get('VELA_FORENSIC_HIDE_BODY') == '1':
            obj.hide_render = True
            continue
        obj.data.materials.clear()
        obj.data.materials.append(diagnostic_material('Forensic original Tripo body', (0.25, 0.25, 0.25)))
    else:
        obj.hide_render = True

for value, filename in [(0.0, 'neutral.png'), (0.5, 'jawOpen_50.png'), (1.0, 'jawOpen_100.png')]:
    for obj in meshes:
        if not obj.data.shape_keys:
            continue
        for key in obj.data.shape_keys.key_blocks:
            key.value = value if key.name == 'xfer_jawOpen_original_tripo' else 0.0
    scene.render.filepath = str(OUT / filename)
    bpy.ops.render.render(write_still=True)

report = {'glb': str(GLB.relative_to(ROOT)), 'renders': [str((OUT / name).relative_to(ROOT)) for name in ['neutral.png', 'jawOpen_50.png', 'jawOpen_100.png']]}
(OUT / 'render-report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
print(json.dumps(report, indent=2))
