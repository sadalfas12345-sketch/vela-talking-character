"""Render a target facial morph for visual QA in Blender."""
import bpy
import sys
from pathlib import Path
from mathutils import Vector

args = sys.argv[sys.argv.index("--") + 1:]
if len(args) != 3:
    raise SystemExit("Usage: blender -b --python scripts/render_tripo_photoreal_shape.py -- INPUT.glb SHAPE OUTPUT.png")
source, shape, output = Path(args[0]).resolve(), args[1], Path(args[2]).resolve()
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(source))
scene = bpy.context.scene
scene.render.engine = "BLENDER_EEVEE"
scene.render.resolution_x = scene.render.resolution_y = 1024
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"
scene.view_settings.view_transform = "Standard"
scene.view_settings.look = "Medium High Contrast"
scene.world = bpy.data.worlds.new("ShapeQAWorld")
scene.world.use_nodes = True
scene.world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.06, 0.06, 0.06, 1)
scene.world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.3
target = Vector((0, 0, 0.82))
for name, location, power, size in [("Key", (1, -2, 1), 130, 1.1), ("Fill", (0, 2, .6), 70, 1.6), ("Top", (-.6, 0, 2), 120, 1.2)]:
    data = bpy.data.lights.new(name, "AREA")
    data.energy = power; data.shape = "DISK"; data.size = size
    light = bpy.data.objects.new(name, data); scene.collection.objects.link(light); light.location = location
    light.rotation_euler = (target - light.location).to_track_quat("-Z", "Y").to_euler()
camera_data = bpy.data.cameras.new("Camera"); camera = bpy.data.objects.new("Camera", camera_data); scene.collection.objects.link(camera)
camera.location = (1, 0, .82); camera.rotation_euler = (target - camera.location).to_track_quat("-Z", "Y").to_euler()
camera_data.type = "ORTHO"; camera_data.ortho_scale = .20; scene.camera = camera
found = []
for obj in scene.objects:
    if obj.type == "MESH" and obj.data.shape_keys:
        key = obj.data.shape_keys.key_blocks.get(shape)
        if key:
            key.value = 1.0; found.append((obj.name, len(obj.data.vertices), len(key.data)))
if not found: raise RuntimeError(f"Shape {shape} not present")
print("QA_SHAPE", shape, found)
output.parent.mkdir(parents=True, exist_ok=True)
scene.render.filepath = str(output)
bpy.ops.render.render(write_still=True)
