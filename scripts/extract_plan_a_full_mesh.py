"""Fast, read-only extraction of an original GLB's world-space mesh arrays."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import bpy
import numpy as np


def arg(name):
    values = sys.argv[sys.argv.index("--") + 1 :]
    return Path(values[values.index(name) + 1]).resolve()


def main():
    source, output = arg("--source"), arg("--output")
    output.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(source))
    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    body = max(meshes, key=lambda o: len(o.data.vertices))
    raw = np.empty(len(body.data.vertices) * 3, dtype=np.float64)
    body.data.vertices.foreach_get("co", raw)
    matrix = np.asarray(body.matrix_world, dtype=np.float64)
    vertices = raw.reshape(-1, 3) @ matrix[:3, :3].T + matrix[:3, 3]
    body.data.calc_loop_triangles()
    loops = np.empty(len(body.data.loop_triangles) * 3, dtype=np.int64)
    body.data.loop_triangles.foreach_get("vertices", loops)
    faces = loops.reshape(-1, 3)
    np.savez_compressed(output.with_suffix(".npz"), V=vertices, F=faces)
    output.write_text(json.dumps({"source": str(source), "meshObject": body.name, "vertices": len(vertices), "triangles": len(faces)}, indent=2) + "\n")
    print(json.dumps({"output": str(output), "vertices": len(vertices), "triangles": len(faces)}))


if __name__ == "__main__":
    main()
