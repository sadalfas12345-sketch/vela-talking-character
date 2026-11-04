"""Inspect a Tripo GLB's meshes, skinning, textures, and facial morphs in Blender."""
import bpy
import json
import sys
from pathlib import Path
from mathutils import Vector

args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
if len(args) != 2:
    raise SystemExit("Usage: blender -b --python scripts/inspect_tripo_glb.py -- INPUT.glb REPORT.json")
source = Path(args[0]).resolve()
report_path = Path(args[1]).resolve()
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(source))

def image_record(image):
    try:
        width, height = image.size[:]
    except Exception:
        width, height = 0, 0
    return {"name": image.name, "width": width, "height": height, "channels": image.channels,
            "format": image.file_format, "packed": bool(image.packed_file)}

meshes = []
materials = []
armatures = []
for obj in bpy.context.scene.objects:
    if obj.type == "MESH":
        sk = obj.data.shape_keys
        groups = obj.vertex_groups
        weighted_vertices = sum(1 for v in obj.data.vertices if v.groups)
        key_names = [k.name for k in sk.key_blocks[1:]] if sk else []
        meshes.append({
            "name": obj.name,
            "vertices": len(obj.data.vertices),
            "triangles": sum(max(0, len(poly.vertices) - 2) for poly in obj.data.polygons),
            "uv_layers": [uv.name for uv in obj.data.uv_layers],
            "vertex_groups": len(groups),
            "weighted_vertices": weighted_vertices,
            "shape_key_count": len(key_names),
            "shape_keys": key_names,
            "world_bounds": [list(obj.matrix_world @ Vector(corner)) for corner in obj.bound_box],
            "modifiers": [{"name": m.name, "type": m.type, "target": getattr(getattr(m, "object", None), "name", None)} for m in obj.modifiers],
            "materials": [slot.material.name if slot.material else None for slot in obj.material_slots],
        })
    if obj.type == "ARMATURE":
        armatures.append({"name": obj.name, "bones": [b.name for b in obj.data.bones]})
for mat in bpy.data.materials:
    textures = []
    if mat.use_nodes and mat.node_tree:
        for node in mat.node_tree.nodes:
            if node.type == "TEX_IMAGE" and node.image:
                textures.append({"node": node.name, "image": node.image.name})
    materials.append({"name": mat.name, "use_nodes": mat.use_nodes, "images": textures})

report = {
    "source": str(source),
    "file_bytes": source.stat().st_size,
    "meshes": meshes,
    "materials": materials,
    "images": [image_record(i) for i in bpy.data.images],
    "armatures": armatures,
    "facial_rig": {
        "shape_key_count": sum(m["shape_key_count"] for m in meshes),
        "arkit_names_detected": sorted({n for m in meshes for n in m["shape_keys"] if n in {
            "eyeBlinkLeft", "eyeBlinkRight", "jawOpen", "mouthSmileLeft", "mouthFrownLeft", "browInnerUp", "mouthClose"}}),
        "oculus_visemes_detected": sorted({n for m in meshes for n in m["shape_keys"] if n.startswith("viseme_")}),
        "eye_bones_detected": sorted({b for a in armatures for b in a["bones"] if "eye" in b.lower()}),
    },
}
report_path.parent.mkdir(parents=True, exist_ok=True)
report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
print("TRIPO_INSPECTION_JSON=" + json.dumps(report, separators=(",", ":")))
