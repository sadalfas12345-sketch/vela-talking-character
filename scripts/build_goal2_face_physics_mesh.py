"""Build a face-only coarse physics surface and full render embedding."""
import json,sys
from pathlib import Path
import bpy,numpy as np
from mathutils.bvhtree import BVHTree
REGIONS={'brow':[70,63,105,336,293,334],'eyelid':[159,145,386,374],'eye':[33,133,263,362],'nose':[168,6,1,98,327],'mouth':[61,291,13,14],'jaw':[152,234,454]}
def arg(n):
 a=sys.argv[sys.argv.index('--')+1:]; return Path(a[a.index(n)+1]).resolve()
def bary(p,a,b,c):
 v0=b-a;v1=c-a;v2=p-a;d00=v0@v0;d01=v0@v1;d11=v1@v1;d20=v2@v0;d21=v2@v1;den=d00*d11-d01*d01
 if abs(den)<1e-15:return np.array([1.,0.,0.])
 v=(d11*d20-d01*d21)/den;w=(d00*d21-d01*d20)/den;return np.array([1-v-w,v,w])
def main():
 glb,goal1,camj,out=arg('--glb'),arg('--goal1'),arg('--camera'),arg('--output'); target_nodes=int(sys.argv[sys.argv.index('--nodes')+1]); ray=json.loads(goal1.read_text()); rec={int(r['index']):r for r in ray['records'] if r.get('meshXYZ')}; target={i:np.asarray(rec[i]['meshXYZ'],float) for i in rec}; cam=json.loads(camj.read_text()); eye=np.linalg.norm(target[33]-target[263]); centers={k:np.mean([target[i] for i in ids if i in target],axis=0) for k,ids in REGIONS.items()}; center=np.mean(list(centers.values()),axis=0); forward=np.asarray(cam['cameraBasis']['forward'],float); forward/=np.linalg.norm(forward); up=np.asarray(cam['cameraBasis']['up'],float); up/=np.linalg.norm(up)
 bpy.ops.wm.read_factory_settings(use_empty=True);bpy.ops.import_scene.gltf(filepath=str(glb));render=max([o for o in bpy.context.scene.objects if o.type=='MESH'],key=lambda o:len(o.data.vertices));n=len(render.data.vertices);local=np.empty((n,3),float);render.data.vertices.foreach_get('co',local.ravel());mw=np.asarray(render.matrix_world,float);world=local@mw[:3,:3].T+mw[:3,3];rad=2.6*eye;depth=np.sum((world-center)*forward,axis=1);face_mask=(np.linalg.norm(world-center,axis=1)<=rad)&(depth>=-.8*eye)
 tris=np.asarray([[int(v) for v in p.vertices] for p in render.data.polygons],int);sub=tris[np.all(face_mask[tris],axis=1)];used=np.unique(sub.ravel());imap=-np.ones(n,int);imap[used]=np.arange(len(used));sub=imap[sub];mesh=bpy.data.meshes.new('Goal2 face physics source');mesh.from_pydata(world[used].tolist(),[],sub.tolist());obj=bpy.data.objects.new('Goal2 face physics source',mesh);bpy.context.collection.objects.link(obj);bpy.context.view_layer.objects.active=obj;obj.select_set(True);mod=obj.modifiers.new('face physics decimation','DECIMATE');mod.ratio=min(.95,max(target_nodes/max(len(used),1),.001));bpy.ops.object.modifier_apply(modifier=mod.name);pv=np.empty((len(obj.data.vertices),3),float);obj.data.vertices.foreach_get('co',pv.ravel());faces=np.asarray([[int(v) for v in p.vertices] for p in obj.data.polygons],int);faces=faces[:,:3];edges=np.unique(np.sort(np.vstack([faces[:,[0,1]],faces[:,[1,2]],faces[:,[2,0]]]),axis=1),axis=0);rest=np.linalg.norm(pv[edges[:,0]]-pv[edges[:,1]],axis=1);edgefaces={}
 for fi,t in enumerate(faces):
  for u,v in ((t[0],t[1]),(t[1],t[2]),(t[2],t[0])):edgefaces.setdefault(tuple(sorted((int(u),int(v)))),[]).append(fi)
 normals=np.cross(pv[faces[:,1]]-pv[faces[:,0]],pv[faces[:,2]]-pv[faces[:,0]]);normals/=np.maximum(np.linalg.norm(normals,axis=1,keepdims=True),1e-12);be=[];th=[]
 for e,fs in edgefaces.items():
  if len(fs)==2:be.append(e);th.append(float(np.arccos(np.clip(normals[fs[0]]@normals[fs[1]],-1,1))))
 def reg(p):
  ds={k:np.linalg.norm(p-c)/eye for k,c in centers.items()};return min(ds,key=ds.get),min(ds.values())
 labels=np.asarray([reg(p)[0] for p in pv],dtype='<U8');anchors=np.asarray([1. if r[0] in {'nose','jaw'} or r[1]>1.8 else 0. for r in [reg(p) for p in pv]]);brow=np.flatnonzero(labels=='brow');fore=np.flatnonzero((np.sum((pv-centers['brow'])*up,axis=1)>0.25*eye)&(np.linalg.norm(pv-centers['brow'],axis=1)<1.6*eye));fib=[]
 for b in brow:
  if len(fore):fib.append((int(b),int(fore[np.argmin(np.linalg.norm(pv[fore]-pv[b],axis=1))])))
 bvh=BVHTree.FromPolygons(pv.tolist(),faces.tolist(),all_triangles=True);et=np.full((n,3),-1,int);ew=np.zeros((n,3));eo=world.copy();valid=np.flatnonzero(face_mask);dist=[]
 for i in valid:
  hit,norm,fi,d=bvh.find_nearest(tuple(world[i]));fi=int(fi);t=faces[fi];w=bary(world[i],pv[t[0]],pv[t[1]],pv[t[2]]);et[i]=t;ew[i]=w;eo[i]=world[i]-(pv[t]*w[:,None]).sum(axis=0);dist.append(float(d))
 recon=(pv[np.maximum(et,0)]*ew[:,:,None]).sum(axis=1)+eo;err=np.linalg.norm(recon-world,axis=1);out.parent.mkdir(parents=True,exist_ok=True);np.savez_compressed(out.with_suffix('.npz'),physics_vertices=pv,physics_faces=faces,physics_edges=edges,rest_lengths=rest,bend_edges=np.asarray(be),rest_dihedral=np.asarray(th),labels=labels,anchor_weights=anchors,muscle_fibers=np.asarray(fib),embedding_triangles=et,embedding_weights=ew,embedding_offsets=eo,render_world=world,embedding_valid=face_mask,neutral_error=err)
 out.write_text(json.dumps({'glb':str(glb),'faceRenderVertices':int(face_mask.sum()),'renderVertices':n,'physicsNodes':len(pv),'physicsTriangles':len(faces),'stretchSprings':len(edges),'bendEdges':len(be),'anchors':int(anchors.sum()),'frontalisFibers':len(fib),'embeddingCoverageOnFace':float(np.mean(np.asarray(dist)<.01*eye)) if dist else 0.,'neutralErrorMaxOnFace':float(err[face_mask].max()) if np.any(face_mask) else None,'neutralErrorP95OnFace':float(np.percentile(err[face_mask],95)) if np.any(face_mask) else None,'regionCounts':{k:int(np.sum(labels==k)) for k in sorted(set(labels))}},indent=2)+'\n')
if __name__=='__main__':main()
