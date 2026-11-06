"""Build a separate coarse anatomy-aware physics surface and render embedding."""
import json,sys
from pathlib import Path
import bpy,numpy as np
from mathutils.bvhtree import BVHTree

REGIONS={'brow':[70,63,105,336,293,334],'eyelid':[159,145,386,374],'eye':[33,133,263,362],'nose':[168,6,1,98,327],'mouth':[61,291,13,14],'jaw':[152,234,454]}
def arg(n):
    a=sys.argv[sys.argv.index('--')+1:]; return Path(a[a.index(n)+1]).resolve()
def bary(p,a,b,c):
    v0=b-a; v1=c-a; v2=p-a; d00=np.dot(v0,v0); d01=np.dot(v0,v1); d11=np.dot(v1,v1); d20=np.dot(v2,v0); d21=np.dot(v2,v1); den=d00*d11-d01*d01
    if abs(den)<1e-15: return np.array([1.,0.,0.])
    v=(d11*d20-d01*d21)/den; w=(d00*d21-d01*d20)/den; return np.array([1-v-w,v,w])
def main():
    glb,goal1,out=arg('--glb'),arg('--goal1'),arg('--output'); target_nodes=int(next((sys.argv[i+1] for i,x in enumerate(sys.argv) if x=='--nodes'),'5000'))
    ray=json.loads(goal1.read_text()); rec={int(r['index']):r for r in ray['records'] if r.get('meshXYZ')}; target={i:np.asarray(rec[i]['meshXYZ'],float) for i in rec}; cam=json.loads(arg('--camera').read_text()); eye=float(np.linalg.norm(target[33]-target[263])); centers={k:np.mean([target[i] for i in ids if i in target],axis=0) for k,ids in REGIONS.items()}
    bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=str(glb)); render=max([o for o in bpy.context.scene.objects if o.type=='MESH'],key=lambda o:len(o.data.vertices)); n=len(render.data.vertices); local=np.empty((n,3),float); render.data.vertices.foreach_get('co',local.ravel()); mw=np.asarray(render.matrix_world,float); world=local@mw[:3,:3].T+mw[:3,3]
    phy=render.copy(); phy.data=render.data.copy(); phy.name='Goal2 anatomy physics surface'; bpy.context.collection.objects.link(phy); bpy.context.view_layer.objects.active=phy; phy.select_set(True); mod=phy.modifiers.new('automatic physics decimation','DECIMATE'); mod.ratio=min(.95,max(1.0*target_nodes/n,.001)); bpy.ops.object.modifier_apply(modifier=mod.name); pv=np.empty((len(phy.data.vertices),3),float); phy.data.vertices.foreach_get('co',pv.ravel()); pm=np.asarray(phy.matrix_world,float); pv=pv@pm[:3,:3].T+pm[:3,3]; faces=np.asarray([[int(v) for v in p.vertices] for p in phy.data.polygons],int); faces=faces[:, :3];
    edges=np.unique(np.sort(np.vstack([faces[:,[0,1]],faces[:,[1,2]],faces[:,[2,0]]]),axis=1),axis=0); rest=np.linalg.norm(pv[edges[:,0]]-pv[edges[:,1]],axis=1)
    edge_faces={}
    for fi,t in enumerate(faces):
        for u,v in ((t[0],t[1]),(t[1],t[2]),(t[2],t[0])): edge_faces.setdefault(tuple(sorted((int(u),int(v)))),[]).append(fi)
    normals=np.cross(pv[faces[:,1]]-pv[faces[:,0]],pv[faces[:,2]]-pv[faces[:,0]]); normals/=np.maximum(np.linalg.norm(normals,axis=1,keepdims=True),1e-12); bends=[]; theta=[]
    for e,fs in edge_faces.items():
        if len(fs)==2:
            bends.append(e); theta.append(float(np.arccos(np.clip(np.dot(normals[fs[0]],normals[fs[1]]),-1,1))))
    def region(p):
        ds={k:np.linalg.norm(p-c)/eye for k,c in centers.items()}; return min(ds,key=ds.get),min(ds.values())
    labels=np.asarray([region(p)[0] for p in pv],dtype='<U8'); anchor=np.asarray([1.0 if region(p)[0] in {'nose','jaw'} or region(p)[1]>2.0 else 0.0 for p in pv]); brow=np.flatnonzero(labels=='brow'); forehead=np.flatnonzero((labels=='brow') & (np.linalg.norm(pv-centers['brow'],axis=1)>0.35*eye)); fibers=[]
    for b in brow:
        if len(forehead): fibers.append((int(b),int(forehead[np.argmin(np.linalg.norm(pv[forehead]-pv[b],axis=1))])))
    bvht=BVHTree.FromPolygons(pv.tolist(),faces.tolist(),all_triangles=True); tri=np.zeros((n,3),int); weights=np.zeros((n,3),float); offsets=np.zeros((n,3),float); dist=np.zeros(n,float)
    for i,p in enumerate(world):
        hit,norm,fi,d=bvht.find_nearest(tuple(p)); fi=0 if fi is None else int(fi); t=faces[fi]; w=bary(p,pv[t[0]],pv[t[1]],pv[t[2]]); tri[i]=t; weights[i]=w; offsets[i]=p-(pv[t]*w[:,None]).sum(axis=0); dist[i]=0 if d is None else float(d)
    recon=(pv[tri]*weights[:,:,None]).sum(axis=1)+offsets; neutral=np.linalg.norm(recon-world,axis=1)
    out.parent.mkdir(parents=True,exist_ok=True); np.savez_compressed(out.with_suffix('.npz'),physics_vertices=pv,physics_faces=faces,physics_edges=edges,rest_lengths=rest,bend_edges=np.asarray(bends),rest_dihedral=np.asarray(theta),labels=labels,anchor_weights=anchor,muscle_fibers=np.asarray(fibers),embedding_triangles=tri,embedding_weights=weights,embedding_offsets=offsets,render_world=world,neutral_error=neutral)
    out.write_text(json.dumps({'glb':str(glb),'physicsNodes':len(pv),'physicsTriangles':len(faces),'stretchSprings':len(edges),'bendEdges':len(bends),'anchors':int(anchor.sum()),'frontalisFibers':len(fibers),'renderVertices':n,'embeddingCoverage':float(np.mean(dist<.002*eye)),'neutralErrorMax':float(neutral.max()),'neutralErrorP95':float(np.percentile(neutral,95)),'neutralErrorMedian':float(np.median(neutral)),'regionCounts':{k:int(np.sum(labels==k)) for k in sorted(set(labels))}},indent=2)+'\n')
if __name__=='__main__': main()
