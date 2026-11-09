"""Render a Plan A5 probe over an untouched original GLB."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector


def main():
    argv = sys.argv[sys.argv.index("--") + 1:]
    def arg(name): return Path(argv[argv.index(name) + 1]).resolve()
    glb, graph_path, positions_path, camera_path, out = arg("--glb"), arg("--graph"), arg("--positions"), arg("--camera"), arg("--output")
    graph = np.load(graph_path); positions = np.load(positions_path)["positions"].astype(float)
    indices = graph["originalIndices"].astype(np.int64)
    V = graph["V"].astype(float)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(glb))
    scene = bpy.context.scene
    body = max([o for o in scene.objects if o.type == "MESH"], key=lambda o: len(o.data.vertices))
    center = Vector(V.mean(axis=0))
    spec = json.loads(camera_path.read_text(encoding="utf-8")); spec = spec.get("camera", spec)
    camera_data = bpy.data.cameras.new("PlanA5ProbeCamera")
    camera = bpy.data.objects.new("PlanA5ProbeCamera", camera_data); scene.collection.objects.link(camera)
    camera.location = center + Vector((10.0, 0.0, 0.0))
    camera.rotation_euler = (center - camera.location).to_track_quat("-Z", "Y").to_euler()
    camera_data.type = "ORTHO"; camera_data.ortho_scale = float(spec["orthoScale"]); scene.camera = camera
    light_data = bpy.data.lights.new("PlanA5ProbeKey", type="AREA"); light_data.energy = 900.0; light_data.size = 4.0
    light = bpy.data.objects.new("PlanA5ProbeKey", light_data); scene.collection.objects.link(light)
    light.location = camera.location + Vector((0.0, 0.0, 2.0)); light.rotation_euler = (center - light.location).to_track_quat("-Z", "Y").to_euler()
    scene.render.engine = "BLENDER_EEVEE"; scene.render.resolution_x = 640; scene.render.resolution_y = 640; scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"; out.parent.mkdir(parents=True, exist_ok=True)
    neutral = np.empty(len(body.data.vertices) * 3, dtype=np.float64); body.data.vertices.foreach_get("co", neutral); neutral = neutral.reshape(-1, 3)
    for name, coords in (("neutral", neutral), ("supported", neutral.copy())):
        if name == "supported": coords[indices] = positions
        for i, co in enumerate(coords): body.data.vertices[i].co = co
        body.data.update(); scene.render.filepath = str(out.parent / f"{out.stem}-{name}.png"); bpy.ops.render.render(write_still=True)
    print(json.dumps({"neutral": str(out.parent / f"{out.stem}-neutral.png"), "supported": str(out.parent / f"{out.stem}-supported.png")}))


if __name__ == "__main__": main()
