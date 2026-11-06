import json,sys
from pathlib import Path
import bpy,numpy as np
ROOT=Path(__file__).resolve().parents[1]; BROW=[70,63,105,336,293,334]; ANCHORS=[159,145,386,374,33,133,263,362,168,6,1,98,327,234,454,152,10,127,356]
def arg(n):
 a=sys.argv[sys.argv.index('--')+1:]; return Path(a[a.index(n)+1]).resolve()
def main():
 source,goal1,camera,out=arg('--source'),arg('--goal1'),arg('--camera'),arg('--problem'); ray=json.loads(goal1.read_text()); rec={int(r['index']):r for r in ray['records'] if r.get('frontSurface') and r.get('meshXYZ')}; cam=json.loads(camera.read_text()); up=np.asarray(cam['cameraBasis']['up'],float); up/=np.linalg.norm(up)
 desired_path = Path(sys.argv[sys.argv.index('--')+1:][sys.argv[sys.argv.index('--')+1:].index('--desired')+1]).resolve() if '--desired' in sys.argv[sys.argv.index('--')+1:] else None
 bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=str(source)); body=max([o for o in bpy.context.scene.objects if o.type=='MESH'],key=lambda o:len(o.data.vertices)); n=len(body.data.vertices); local=np.empty((n,3),float); body.data.vertices.foreach_get('co',local.ravel()); mw=np.asarray(body.matrix_world,float); world=local@mw[:3,:3].T+mw[:3,3]; target={i:np.asarray(rec[i]['meshXYZ'],float) for i in rec}; eye=float(np.linalg.norm(target[33]-target[263])); center=np.mean([target[i] for i in BROW],axis=0); radius=float(np.linalg.norm(center-target[152]))*.5; handles=np.asarray([target[i] for i in BROW+ANCHORS]); ids=np.flatnonzero(np.min(np.linalg.norm(world[:,None]-handles[None],axis=2),axis=1)<=radius); mask=np.zeros(n,bool); mask[ids]=1; tris=np.asarray([[v for v in p.vertices] for p in body.data.polygons],int); edges=np.concatenate([tris[:,[0,1]],tris[:,[1,2]],tris[:,[2,0]]]); edges=edges[mask[edges[:,0]]&mask[edges[:,1]]]; inv={int(v):i for i,v in enumerate(ids)}; edges=np.asarray([[inv[int(x)],inv[int(y)]] for x,y in edges],int)
 cvi=[]; cb=[]
 for i in BROW+ANCHORS:
  r=rec[i]; cvi.append([inv[int(v)] for v in r['triangleVertexIndices']]); cb.append(r['barycentricCoordinates'])
 if desired_path:
  desired_brow=np.asarray(json.loads(desired_path.read_text())['desiredTargetWorldDisplacements'],float)
 else:
  desired_brow=np.tile(.05*eye*up,(len(BROW),1))
 desired=np.vstack([desired_brow,np.zeros((len(ANCHORS),3))]);
 edge_lengths=np.linalg.norm(world[ids][edges[:,0]]-world[ids][edges[:,1]],axis=1)
 # Select a scale-derived local ring around the brow anchors. These are
 # linearized signed-area inequalities, solved inside the QP active set.
 local_tris=[]; ori_q=[]; ori_n=[]
 brow_world=np.asarray([target[i] for i in BROW])
 for tri in tris:
  if not (mask[tri[0]] and mask[tri[1]] and mask[tri[2]]): continue
  c=world[tri].mean(axis=0)
  c=world[tri].mean(axis=0)
  if np.min(np.linalg.norm(c[None]-brow_world,axis=1)) > .05*eye: continue
  p=world[tri]; n=np.cross(p[1]-p[0],p[2]-p[0]); ln=np.linalg.norm(n)
  if ln < 1e-12: continue
  local_tris.append([inv[int(v)] for v in tri]); ori_q.append(float(np.dot(n/ln,n))); ori_n.append(n/ln)
 local_world=world[ids]; e0=local_world[edges[:,0]]; e1=local_world[edges[:,1]]
 d0=np.min(np.linalg.norm(e0[:,None]-brow_world[None],axis=2),axis=1); d1=np.min(np.linalg.norm(e1[:,None]-brow_world[None],axis=2),axis=1)
 quality_edges=edges[(d0<=.012*eye)&(d1<=.012*eye)]
 quality_lengths=np.linalg.norm(world[ids][quality_edges[:,0]]-world[ids][quality_edges[:,1]],axis=1)
 np.savez_compressed(out,source=str(source),local_indices=ids,local_coords=local[ids],world_coords=world[ids],edges=edges,edge_lengths=edge_lengths,quality_edges=quality_edges,quality_edge_lengths=quality_lengths,constraint_vertices=np.asarray(cvi),constraint_bary=np.asarray(cb),desired=desired,eye_width=eye,up=up,matrix_world=mw,orientation_triangles=np.asarray(local_tris),orientation_normals=np.asarray(ori_n),orientation_q0=np.asarray(ori_q))
 print(json.dumps({'source':str(source),'localVertices':len(ids),'edges':len(edges),'orientationTriangles':len(local_tris),'eyeWidthMillimeters':eye*1000,'requestedBrowMillimeters':(np.linalg.norm(desired_brow,axis=1)*1000).tolist(),'problem':str(out)}))
if __name__=='__main__': main()
