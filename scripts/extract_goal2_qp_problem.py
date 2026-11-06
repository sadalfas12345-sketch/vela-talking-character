import json,sys
from pathlib import Path
import bpy,numpy as np
ROOT=Path(__file__).resolve().parents[1]; BROW=[70,63,105,336,293,334]; ANCHORS=[159,145,386,374,33,133,263,362,168,6,1,98,327,234,454,152,10,127,356]
def arg(n):
 a=sys.argv[sys.argv.index('--')+1:]; return Path(a[a.index(n)+1]).resolve()
def main():
 source,goal1,camera,out=arg('--source'),arg('--goal1'),arg('--camera'),arg('--problem'); ray=json.loads(goal1.read_text()); rec={int(r['index']):r for r in ray['records'] if r.get('frontSurface') and r.get('meshXYZ')}; cam=json.loads(camera.read_text()); up=np.asarray(cam['cameraBasis']['up'],float); up/=np.linalg.norm(up)
 bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=str(source)); body=max([o for o in bpy.context.scene.objects if o.type=='MESH'],key=lambda o:len(o.data.vertices)); n=len(body.data.vertices); local=np.empty((n,3),float); body.data.vertices.foreach_get('co',local.ravel()); mw=np.asarray(body.matrix_world,float); world=local@mw[:3,:3].T+mw[:3,3]; target={i:np.asarray(rec[i]['meshXYZ'],float) for i in rec}; eye=float(np.linalg.norm(target[33]-target[263])); center=np.mean([target[i] for i in BROW],axis=0); radius=float(np.linalg.norm(center-target[152]))*.5; handles=np.asarray([target[i] for i in BROW+ANCHORS]); ids=np.flatnonzero(np.min(np.linalg.norm(world[:,None]-handles[None],axis=2),axis=1)<=radius); mask=np.zeros(n,bool); mask[ids]=1; tris=np.asarray([[v for v in p.vertices] for p in body.data.polygons],int); edges=np.concatenate([tris[:,[0,1]],tris[:,[1,2]],tris[:,[2,0]]]); edges=edges[mask[edges[:,0]]&mask[edges[:,1]]]; inv={int(v):i for i,v in enumerate(ids)}; edges=np.asarray([[inv[int(x)],inv[int(y)]] for x,y in edges],int)
 cvi=[]; cb=[]
 for i in BROW+ANCHORS:
  r=rec[i]; cvi.append([inv[int(v)] for v in r['triangleVertexIndices']]); cb.append(r['barycentricCoordinates'])
 desired=np.tile(.05*eye*up,(len(BROW),1)); desired=np.vstack([desired,np.zeros((len(ANCHORS),3))]);
 edge_lengths=np.linalg.norm(world[ids][edges[:,0]]-world[ids][edges[:,1]],axis=1)
 np.savez_compressed(out,source=str(source),local_indices=ids,local_coords=local[ids],world_coords=world[ids],edges=edges,edge_lengths=edge_lengths,constraint_vertices=np.asarray(cvi),constraint_bary=np.asarray(cb),desired=desired,eye_width=eye,up=up,matrix_world=mw)
 print(json.dumps({'source':str(source),'localVertices':len(ids),'edges':len(edges),'eyeWidthMillimeters':eye*1000,'requestedMillimeters':.05*eye*1000,'problem':str(out)}))
if __name__=='__main__': main()
