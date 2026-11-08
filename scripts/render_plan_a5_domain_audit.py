"""Render the A5 candidate domain over the original textured character."""
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
    glb, graph_path, camera_path, out = arg("--glb"), arg("--graph"), arg("--camera"), arg("--output")
    g = np.load(graph_path)
    V = g["V"].astype(float)
    F = g["F"].astype(np.int64)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(glb))
    scene = bpy.context.scene
    body = max([o for o in scene.objects if o.type == "MESH"], key=lambda o: len(o.data.vertices))
    corners = [body.matrix_world @ Vector(point) for point in body.bound_box]
    mn = Vector((min(p.x for p in corners), min(p.y for p in corners), min(p.z for p in corners)))
    mx = Vector((max(p.x for p in corners), max(p.y for p in corners), max(p.z for p in corners)))
    center = Vector(V.mean(axis=0))
    camera_spec = json.loads(camera_path.read_text(encoding="utf-8"))
    camera_spec = camera_spec.get("camera", camera_spec)
    camera_data = bpy.data.cameras.new("PlanA5AuditCamera")
    camera = bpy.data.objects.new("PlanA5AuditCamera", camera_data)
    scene.collection.objects.link(camera)
    camera.location = center + Vector((10.0, 0.0, 0.0))
    camera.rotation_euler = (center - camera.location).to_track_quat("-Z", "Y").to_euler()
    camera_data.type = "ORTHO"
    camera_data.ortho_scale = min(float(camera_spec["orthoScale"]), max(float((V.max(axis=1) - V.min(axis=1)).max() * 2.0), 0.1))
    scene.camera = camera
    light_data = bpy.data.lights.new("PlanA5AuditKey", type="AREA")
    light_data.energy = 900.0
    light_data.size = 4.0
    light = bpy.data.objects.new("PlanA5AuditKey", light_data)
    scene.collection.objects.link(light)
    light.location = camera.location + Vector((0.0, 0.0, 2.0))
    light.rotation_euler = (center - light.location).to_track_quat("-Z", "Y").to_euler()
    overlay_mesh = bpy.data.meshes.new("A5CandidateDomain")
    overlay_mesh.from_pydata(V.tolist(), [], F.tolist())
    overlay_mesh.update()
    overlay = bpy.data.objects.new("A5CandidateDomain", overlay_mesh)
    scene.collection.objects.link(overlay)
    material = bpy.data.materials.new("A5CandidateDomainRed")
    material.diffuse_color = (0.9, 0.02, 0.01, 0.95)
    material.use_nodes = True
    bsdf = material.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (0.9, 0.01, 0.005, 1.0)
        bsdf.inputs["Emission Color"].default_value = (0.4, 0.0, 0.0, 1.0)
        bsdf.inputs["Emission Strength"].default_value = 2.0
    material.metallic = 0.0
    material.roughness = 0.35
    overlay.data.materials.append(material)
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = 640
    scene.render.resolution_y = 640
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = str(out)
    bpy.ops.render.render(write_still=True)
    print(json.dumps({"output": str(out), "vertices": len(V), "triangles": len(F)}))


if __name__ == "__main__":
    main()
