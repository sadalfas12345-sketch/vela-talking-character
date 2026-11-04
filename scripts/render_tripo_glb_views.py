"""Render two orthographic views of a Tripo GLB for visual inspection."""
import bpy
import sys
from pathlib import Path
from mathutils import Vector

args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
if len(args) != 2:
    raise SystemExit("Usage: blender -b --python scripts/render_tripo_glb_views.py -- INPUT.glb OUTPUT_DIR")
source, output_dir = Path(args[0]).resolve(), Path(args[1]).resolve()
output_dir.mkdir(parents=True, exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(source))
scene = bpy.context.scene
scene.render.engine = "BLENDER_EEVEE"
scene.render.resolution_x = 768
scene.render.resolution_y = 1024
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"
scene.render.film_transparent = False
scene.view_settings.view_transform = "AgX"
scene.world = bpy.data.worlds.new("InspectionWorld")
scene.world.color = (0.045, 0.055, 0.075)
scene.camera = bpy.data.objects.new("InspectionCamera", bpy.data.cameras.new("InspectionCamera"))
scene.collection.objects.link(scene.camera)
scene.camera.data.type = "ORTHO"
scene.camera.data.ortho_scale = 1.16
target = Vector((0, 0, 0.49))

def aim(obj, point):
    obj.rotation_euler = (Vector(point) - obj.location).to_track_quat("-Z", "Y").to_euler()

def area(name, location, power, color, size):
    light_data = bpy.data.lights.new(name, "AREA")
    light_data.energy = power
    light_data.color = color
    light_data.shape = "DISK"
    light_data.size = size
    obj = bpy.data.objects.new(name, light_data)
    scene.collection.objects.link(obj)
    obj.location = location
    aim(obj, target)

area("Key", (1.1, -1.1, 1.6), 180, (1.0, 0.82, 0.68), 1.1)
area("Fill", (-1.4, -0.7, 0.8), 120, (0.67, 0.79, 1.0), 1.5)
area("Rim", (0.1, 1.2, 1.25), 220, (0.72, 0.84, 1.0), 0.9)

for label, x in [("positive-x", 2.2), ("negative-x", -2.2)]:
    scene.camera.location = (x, 0, 0.53)
    aim(scene.camera, target)
    scene.render.filepath = str(output_dir / f"{label}.png")
    bpy.ops.render.render(write_still=True)

scene.render.resolution_x = 1024
scene.render.resolution_y = 1024
scene.camera.data.ortho_scale = 0.20
face_target = Vector((0, 0, 0.82))
scene.camera.location = (1.0, 0, 0.82)
aim(scene.camera, face_target)
for light in [o for o in scene.objects if o.type == "LIGHT"]:
    light.location.z = 0.95
    aim(light, face_target)
scene.render.filepath = str(output_dir / "face-closeup.png")
bpy.ops.render.render(write_still=True)
