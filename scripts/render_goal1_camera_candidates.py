"""Render model-agnostic spherical camera candidates for Goal 1."""
import json
import math
import os
import sys
from pathlib import Path

import bpy
from mathutils import Vector


def fibonacci_directions(count=32):
    golden = math.pi * (3.0 - math.sqrt(5.0))
    directions = []
    for i in range(count):
        y = 1.0 - (2.0 * (i + 0.5) / count)
        radius = math.sqrt(max(0.0, 1.0 - y * y))
        theta = golden * i
        directions.append(Vector((math.cos(theta) * radius, y, math.sin(theta) * radius)).normalized())
    return directions


def bounds(objects):
    corners = []
    for obj in objects:
        if obj.type != 'MESH':
            continue
        corners.extend([obj.matrix_world @ Vector(corner) for corner in obj.bound_box])
    if not corners:
        raise RuntimeError('The GLB contains no renderable mesh objects.')
    low = Vector((min(p.x for p in corners), min(p.y for p in corners), min(p.z for p in corners)))
    high = Vector((max(p.x for p in corners), max(p.y for p in corners), max(p.z for p in corners)))
    return low, high


def focus_from_head_metadata(scene, low, high, diagonal):
    armatures = [obj for obj in scene.objects if obj.type == 'ARMATURE']
    candidates = []
    for armature in armatures:
        for bone in armature.data.bones:
            name = bone.name.lower()
            if 'head' in name and 'top' not in name and 'end' not in name:
                head = armature.matrix_world @ bone.head_local
                tail = armature.matrix_world @ bone.tail_local
                candidates.append((head, max((tail - head).length * 3.0, diagonal * 0.08), bone.name))
    if candidates:
        head, scale, name = max(candidates, key=lambda item: item[1])
        return head, scale, {'method': 'head-bone-metadata', 'bone': name}
    return (low + high) * 0.5, max(low.x - high.x, low.y - high.y, low.z - high.z) * 1.18, {'method': 'full-mesh-bounds'}


def main():
    if len(sys.argv) < 3:
        raise SystemExit('Usage: blender -b --python render_goal1_camera_candidates.py -- input.glb output_dir [count]')
    glb = Path(sys.argv[-3]).resolve()
    output = Path(sys.argv[-2]).resolve()
    count = int(sys.argv[-1]) if sys.argv[-1].isdigit() else 32
    output.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(glb))
    scene = bpy.context.scene
    meshes = [obj for obj in scene.objects if obj.type == 'MESH']
    low, high = bounds(meshes)
    center = (low + high) * 0.5
    extent = high - low
    diagonal = extent.length
    focus_center, focus_scale, focus_metadata = focus_from_head_metadata(scene, low, high, diagonal)
    camera_data = bpy.data.cameras.new('Goal 1 discovered candidate camera')
    camera = bpy.data.objects.new('Goal 1 discovered candidate camera', camera_data)
    scene.collection.objects.link(camera)
    scene.camera = camera
    camera.data.type = 'ORTHO'
    camera.data.ortho_scale = focus_scale
    scene.render.engine = 'BLENDER_EEVEE'
    scene.render.resolution_x = 640
    scene.render.resolution_y = 640
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.render.film_transparent = False
    scene.view_settings.view_transform = 'Standard'
    scene.view_settings.look = 'Medium High Contrast'
    scene.view_settings.exposure = 0.0
    world = bpy.data.worlds.new('Goal 1 discovery world')
    world.use_nodes = True
    world.node_tree.nodes['Background'].inputs['Color'].default_value = (0.008, 0.008, 0.008, 1.0)
    world.node_tree.nodes['Background'].inputs['Strength'].default_value = 0.25
    scene.world = world
    for name, location, energy, size in [
        ('Discovery key', focus_center + Vector((diagonal, -diagonal, diagonal)), 900, diagonal * 0.8),
        ('Discovery fill', focus_center + Vector((-diagonal, -diagonal * 0.5, diagonal * 0.5)), 500, diagonal),
        ('Discovery rim', focus_center + Vector((0, diagonal, diagonal)), 700, diagonal * 0.7),
    ]:
        data = bpy.data.lights.new(name, 'AREA')
        data.energy = energy
        data.shape = 'DISK'
        data.size = size
        light = bpy.data.objects.new(name, data)
        scene.collection.objects.link(light)
        light.location = location
        light.rotation_euler = (focus_center - location).to_track_quat('-Z', 'Y').to_euler()
    records = []
    distance = diagonal * 3.0 + 1e-3
    for i, direction in enumerate(fibonacci_directions(count)):
        location = focus_center + direction * distance
        camera.location = location
        camera.rotation_euler = (focus_center - location).to_track_quat('-Z', 'Y').to_euler()
        path = output / f'candidate_{i:03d}.png'
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        records.append({
            'index': i,
            'image': path.name,
            'cameraLocation': list(location),
            'target': list(focus_center),
            'orthoScale': camera.data.ortho_scale,
            'resolution': [scene.render.resolution_x, scene.render.resolution_y],
            'projection': 'ORTHOGRAPHIC',
        })
    (output / 'candidate-cameras.json').write_text(json.dumps({
        'sourceGLB': str(glb), 'center': list(focus_center), 'boundsMin': list(low), 'boundsMax': list(high),
        'extent': list(extent), 'diagonal': diagonal, 'focus': focus_metadata, 'focusScale': focus_scale, 'candidates': records,
    }, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'candidateCount': len(records), 'center': list(center), 'extent': list(extent), 'diagonal': diagonal}))


if __name__ == '__main__':
    main()
