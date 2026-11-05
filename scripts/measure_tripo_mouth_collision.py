import bpy, json, numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from pathlib import Path
p=Path('assets/tripo/vela-photoreal/vela-photoreal-faced.glb').resolve()
bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=str(p))
objs={o.name:o for o in bpy.data.objects if o.type=='MESH'}
body=next(o for n,o in objs.items() if n.startswith('tripo_node_'))
teeth=objs['VelaTransplantedTeeth']; tongue=objs['VelaTransplantedTongue']
def set_pose(target):
 for o in objs.values():
  if o.data.shape_keys:
   for k in o.data.shape_keys.key_blocks[1:]: k.value=1.0 if k.name==target else 0.0
 bpy.context.view_layer.update()
def evaluated_world(obj):
 ev=obj.evaluated_get(bpy.context.evaluated_depsgraph_get()); me=ev.to_mesh(); me.calc_loop_triangles()
 co=np.empty((len(me.vertices),3),dtype=np.float64)
 for i,v in enumerate(me.vertices): co[i]=ev.matrix_world @ v.co
 tri=np.asarray([t.vertices for t in me.loop_triangles],dtype=np.int32)
 return ev,me,co,tri

def tree(coords,tri):
 return BVHTree.FromPolygons([Vector(x) for x in coords], [tuple(map(int,x)) for x in tri], all_triangles=True)
report={'method':'Blender evaluated geometry at full target influence; BVH triangle overlap between transferred oral meshes and the Tripo shell near the mouth. This is a read-only test.' ,'states':{}}
for state in ['jawOpen','viseme_PP']:
 set_pose(state)
 e_t,m_t,c_t,tr_t=evaluated_world(teeth)
 e_g,m_g,c_g,tr_g=evaluated_world(tongue)
 e_b,m_b,c_b,tr_b=evaluated_world(body)
 lo=np.minimum(c_t.min(0),c_g.min(0)); hi=np.maximum(c_t.max(0),c_g.max(0)); pad=.004
 in_box=np.all((c_b>=lo-pad)&(c_b<=hi+pad),axis=1)
 tri_keep=np.any(in_box[tr_b],axis=1)
 tsel=tr_b[tri_keep]
 used,inv=np.unique(tsel.reshape(-1),return_inverse=True)
 shell_tree=tree(c_b[used],inv.reshape(-1,3))
 tooth_tree=tree(c_t,tr_t); tongue_tree=tree(c_g,tr_g)
 tx=shell_tree.overlap(tooth_tree); gx=shell_tree.overlap(tongue_tree)
 # Report count and minimum sampled vertex-to-shell separation as supporting context.
 report['states'][state]={'shellTrianglesInMouthAABB':int(tri_keep.sum()),'teethTriangles':int(len(tr_t)),'tongueTriangles':int(len(tr_g)),'shellTeethIntersectingTrianglePairs':len(tx),'shellTongueIntersectingTrianglePairs':len(gx),'mouthAABBMinWorld':lo.tolist(),'mouthAABBMaxWorld':hi.tolist(),'bvhExpansionMeters':pad}
 e_t.to_mesh_clear();e_g.to_mesh_clear();e_b.to_mesh_clear()
print(json.dumps(report,indent=2))
Path('verification/tripo-mouth-bvh-overlap.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
