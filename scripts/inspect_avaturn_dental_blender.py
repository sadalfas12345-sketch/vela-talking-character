import bpy, json
from pathlib import Path
p=Path('TalkingHead/avatars/avaturn.glb').resolve()
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(p))
out=[]
for o in bpy.data.objects:
 if o.type!='MESH' or not any(k in o.name.lower() for k in ['teeth','tongue']): continue
 bpy.context.view_layer.update(); ev=o.evaluated_get(bpy.context.evaluated_depsgraph_get()); m=ev.to_mesh(); m.calc_loop_triangles()
 coords=[]
 for v in m.vertices: coords.append((ev.matrix_world@v.co)[:])
 mins=[min(v[i] for v in coords) for i in range(3)]; maxs=[max(v[i] for v in coords) for i in range(3)]
 out.append({'name':o.name,'verts':len(coords),'bounds':{'min':mins,'max':maxs},'shapeKeys':[k.name for k in o.data.shape_keys.key_blocks] if o.data.shape_keys else [],'matrix':[[float(x) for x in row] for row in o.matrix_world]})
 ev.to_mesh_clear()
print(json.dumps(out,indent=2))
