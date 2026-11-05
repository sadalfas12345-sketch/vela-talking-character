import json
from pathlib import Path

import bpy
from mathutils import Vector

root = Path(__file__).resolve().parents[1]
source = root / 'TalkingHead' / 'avatars' / 'avaturn.glb'
out = root / 'verification' / 'avaturn-face-fit-source.json'
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(source))
rows = []
for obj in (o for o in bpy.context.scene.objects if o.type == 'MESH'):
    world = [obj.matrix_world @ v.co for v in obj.data.vertices]
    mins = [min(p[i] for p in world) for i in range(3)]
    maxs = [max(p[i] for p in world) for i in range(3)]
    keys = obj.data.shape_keys.key_blocks if obj.data.shape_keys else []
    rows.append({
        'name': obj.name, 'vertices': len(obj.data.vertices),
        'triangles': sum(max(0, len(p.vertices) - 2) for p in obj.data.polygons),
        'boundsWorld': {'min': mins, 'max': maxs},
        'shapeKeys': [k.name for k in keys],
        'materials': [m.name if m else None for m in obj.data.materials],
        'uvLayers': [uv.name for uv in obj.data.uv_layers],
        'vertexGroups': len(obj.vertex_groups),
        'modifiers': [m.type for m in obj.modifiers],
    })
images = []
for image in bpy.data.images:
    if image.source == 'FILE' or image.packed_file:
        images.append({'name': image.name, 'size': list(image.size), 'packed': bool(image.packed_file)})
for obj in bpy.context.scene.objects:
    if obj.type == 'MESH' and obj.name in {'Body_Mesh', 'avaturn_shoes_0', 'avaturn_look_0', 'Icosphere'}:
        obj.hide_render = True
scene = bpy.context.scene
scene.render.engine = 'BLENDER_EEVEE'
scene.render.resolution_x = 1024
scene.render.resolution_y = 1024
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'PNG'
scene.render.film_transparent = False
scene.view_settings.view_transform = 'Standard'
scene.view_settings.look = 'Medium High Contrast'
camera_data = bpy.data.cameras.new('FaceFitReferenceCamera')
camera = bpy.data.objects.new('FaceFitReferenceCamera', camera_data)
scene.collection.objects.link(camera)
camera.location = (0, -1, 1.71)
target = Vector((0, 0, 1.71))
camera.rotation_euler = (target - camera.location).to_track_quat('-Z', 'Y').to_euler()
camera_data.type = 'ORTHO'
camera_data.ortho_scale = 0.42
scene.camera = camera
for name, location, power, size in [
    ('Key', (-0.35, -0.55, 2.05), 70, 0.6),
    ('Fill', (0.42, -0.4, 1.7), 30, 0.8),
    ('Rim', (0.1, 0.35, 1.95), 45, 0.5),
]:
    light_data = bpy.data.lights.new(name, 'AREA')
    light_data.energy = power
    light_data.shape = 'DISK'
    light_data.size = size
    light = bpy.data.objects.new(name, light_data)
    scene.collection.objects.link(light)
    light.location = location
    light.rotation_euler = (target - light.location).to_track_quat('-Z', 'Y').to_euler()
if scene.world:
    scene.world.color = (0.05, 0.05, 0.05)
render = root / 'verification' / 'avaturn-face-fit-reference.png'
scene.render.filepath = str(render)
bpy.ops.render.render(write_still=True)
result = {'source': str(source.relative_to(root)), 'meshes': rows, 'images': images, 'referenceRender': str(render.relative_to(root))}
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
print(json.dumps(result, indent=2))
