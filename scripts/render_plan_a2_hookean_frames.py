"""Bake selected Plan A2 patch frames onto original GLBs for inspection."""
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
    glb, graph_path, run_path, camera_path, out = arg("--glb"), arg("--graph"), arg("--run"), arg("--camera"), arg("--output")
    frames = [int(x) for x in argv[argv.index("--frames") + 1].split(",")]
    graph = np.load(graph_path)
    pos = np.load(run_path.with_name(run_path.stem + "-positions.npz"))["positions"].astype(float)
    original_indices = graph["originalIndices"].astype(np.int64)
    cam_source = json.loads(camera_path.read_text(encoding="utf-8"))["camera"]
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(glb))
    scene = bpy.context.scene
    body = max([o for o in scene.objects if o.type == "MESH"], key=lambda o: len(o.data.vertices))
    corners = [body.matrix_world @ Vector(point) for point in body.bound_box]
    mn = Vector((min(p.x for p in corners), min(p.y for p in corners), min(p.z for p in corners)))
    mx = Vector((max(p.x for p in corners), max(p.y for p in corners), max(p.z for p in corners)))
    center = (mn + mx) * 0.5
    direction = (Vector(cam_source["cameraLocation"]) - Vector(cam_source["target"])).normalized()
    camera_data = bpy.data.cameras.new("PlanA2InspectionCamera")
    camera = bpy.data.objects.new("PlanA2InspectionCamera", camera_data)
    scene.collection.objects.link(camera)
    camera.location = center + direction * 10.0
    camera.rotation_euler = (center - camera.location).to_track_quat("-Z", "Y").to_euler()
    camera_data.type = "ORTHO"
    camera_data.ortho_scale = float(cam_source["orthoScale"])
    scene.camera = camera
    light_data = bpy.data.lights.new("PlanA2Key", type="AREA")
    light_data.energy = 900.0
    light_data.shape = "DISK"
    light_data.size = 4.0
    light = bpy.data.objects.new("PlanA2Key", light_data)
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
    neutral_coords = np.empty(len(body.data.vertices) * 3, dtype=np.float64)
    body.data.vertices.foreach_get("co", neutral_coords)
    neutral_coords = neutral_coords.reshape(-1, 3)
    for frame in frames:
        coords = neutral_coords.copy()
        if frame != 0:
            coords[original_indices] = pos[frame]
        for i, co in enumerate(coords):
            body.data.vertices[i].co = co
        body.data.update()
        scene.render.filepath = str(out / f"frame-{frame:03d}.png")
        bpy.ops.render.render(write_still=True)
    print(json.dumps({"frames": frames, "output": str(out)}))


if __name__ == "__main__":
    main()
