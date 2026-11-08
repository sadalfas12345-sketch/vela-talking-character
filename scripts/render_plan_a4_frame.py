"""Render one A4 solved patch over the untouched original GLB."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector


def main():
    argv = sys.argv[sys.argv.index("--") + 1 :]
    def arg(name): return Path(argv[argv.index(name) + 1]).resolve()
    glb, graph_path, positions_path, camera_path, out = arg("--glb"), arg("--graph"), arg("--positions"), arg("--camera"), arg("--output")
    graph = np.load(graph_path)
    positions = np.load(positions_path)["positions"].astype(float)
    original_indices = graph["originalIndices"].astype(np.int64)
    camera_spec = json.loads(camera_path.read_text(encoding="utf-8"))
    camera_spec = camera_spec.get("camera", camera_spec)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(glb))
    scene = bpy.context.scene
    body = max([o for o in scene.objects if o.type == "MESH"], key=lambda o: len(o.data.vertices))
    corners = [body.matrix_world @ Vector(point) for point in body.bound_box]
    mn = Vector((min(p.x for p in corners), min(p.y for p in corners), min(p.z for p in corners)))
    mx = Vector((max(p.x for p in corners), max(p.y for p in corners), max(p.z for p in corners)))
    full_center = (mn + mx) * 0.5
    center = Vector((full_center.x, full_center.y, mn.z + 0.72 * (mx.z - mn.z)))
    source_camera = Vector(camera_spec["cameraLocation"])
    source_target = Vector(camera_spec["target"])
    # The original Tripo meshes use +X as the facial viewing direction.  The
    # old Goal-1 camera was fitted to a different rigged asset, so reuse only
    # its scale and render the original from its anatomical frontal axis.
    direction = Vector((1.0, 0.0, 0.0))
    camera_location = center + direction * 10.0
    camera_data = bpy.data.cameras.new("PlanA4Camera")
    camera = bpy.data.objects.new("PlanA4Camera", camera_data)
    scene.collection.objects.link(camera)
    camera.location = camera_location
    camera.rotation_euler = (center - camera.location).to_track_quat("-Z", "Y").to_euler()
    camera_data.type = "ORTHO"
    camera_data.ortho_scale = float(camera_spec["orthoScale"])
    scene.camera = camera
    light_data = bpy.data.lights.new("PlanA4Key", type="AREA")
    light_data.energy = 900.0
    light_data.size = 4.0
    light = bpy.data.objects.new("PlanA4Key", light_data)
    scene.collection.objects.link(light)
    light.location = camera.location + Vector((0.0, 0.0, 2.0))
    light.rotation_euler = (center - light.location).to_track_quat("-Z", "Y").to_euler()
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = 640
    scene.render.resolution_y = 640
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False
    out.mkdir(parents=True, exist_ok=True)
    neutral = np.empty(len(body.data.vertices) * 3, dtype=np.float64)
    body.data.vertices.foreach_get("co", neutral)
    neutral = neutral.reshape(-1, 3)
    for label, coords in (("neutral", neutral), ("a4-partial", neutral.copy())):
        if label != "neutral":
            coords[original_indices] = positions
        for i, co in enumerate(coords):
            body.data.vertices[i].co = co
        body.data.update()
        scene.render.filepath = str(out / f"{label}.png")
        bpy.ops.render.render(write_still=True)
    print(json.dumps({"output": str(out), "neutral": str(out / "neutral.png"), "deformed": str(out / "a4-partial.png")}))


if __name__ == "__main__":
    main()
