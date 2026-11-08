import bpy, numpy as np
from pathlib import Path
def load(path):
    bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=str(path)); o=max((x for x in bpy.context.scene.objects if x.type=='MESH'),key=lambda x:len(x.data.vertices)); M=np.asarray(o.matrix_world,float); a=np.empty(len(o.data.vertices)*3,float); o.data.vertices.foreach_get('co',a); v=a.reshape(-1,3)@M[:3,:3].T+M[:3,3]; print(path, 'verts',len(v),'polys',len(o.data.polygons),'min',v.min(0).tolist(),'max',v.max(0).tolist(),'center',v.mean(0).tolist())
load(Path(r'C:\Users\USER\talking-character-demo\assets\tripo\vela-photoreal\generated-original.glb'))
load(Path(r'C:\Users\USER\talking-character-demo\assets\tripo\vela-photoreal\generated-rigged.glb'))
