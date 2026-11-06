import json,sys,os
from pathlib import Path
import bpy,numpy as np
def main():
 a=sys.argv[sys.argv.index('--')+1:]; glb=Path(a[a.index('--glb')+1]).resolve(); out=Path(a[a.index('--report')+1]).resolve(); keyname=os.environ.get('VELA_GOAL2_BROW_KEY','real_browInnerUp_qp')
 bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=str(glb)); body=max([o for o in bpy.context.scene.objects if o.type=='MESH'],key=lambda o:len(o.data.vertices)); mesh=body.data
 base=np.empty((len(mesh.vertices),3),float); posed=np.empty_like(base); mesh.vertices.foreach_get('co',base.ravel()); mesh.shape_keys.key_blocks[keyname].data.foreach_get('co',posed.ravel()); delta=np.linalg.norm(posed-base,axis=1)
 faces=np.asarray([[v for v in p.vertices] for p in mesh.polygons],int); b=base[faces]; p=posed[faces]
 nb=np.cross(b[:,1]-b[:,0],b[:,2]-b[:,0]); npv=np.cross(p[:,1]-p[:,0],p[:,2]-p[:,0]); nbm=np.linalg.norm(nb,axis=1); npm=np.linalg.norm(npv,axis=1); dots=np.sum(nb*npv,axis=1)/np.maximum(nbm*npm,1e-20); angles=np.degrees(np.arccos(np.clip(dots,-1,1)))
 tri_move=np.max(delta[faces],axis=1); order=np.argsort(-tri_move)[:100]
 rows=[]
 for j in order[:30]: rows.append({'triangle':int(j),'vertices':faces[j].tolist(),'maxVertexMotionMillimeters':float(tri_move[j]*1000),'normalChangeDegrees':float(angles[j]),'material':mesh.polygons[int(j)].material_index,'centroid':b[j].mean(axis=0).tolist()})
 out.parent.mkdir(parents=True,exist_ok=True); out.write_text(json.dumps({'glb':str(glb),'shapeKey':keyname,'maxVertexMotionMillimeters':float(delta.max()*1000),'maxNormalChangeDegrees':float(angles.max()),'topTriangles':rows},indent=2)+'\n')
if __name__=='__main__': main()
