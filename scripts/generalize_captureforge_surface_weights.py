"""Connectivity-aware CaptureForge skin weights and landmark-105 regression."""
import heapq, json, sys
from pathlib import Path
import bpy, numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
ROOT=Path(r'C:\Users\USER\talking-character-demo'); sys.path.insert(0,str(ROOT/'scripts'))
import diagnose_captureforge_corrected_setup as base
from captureforge.face import autofit
OUT=ROOT/'verification/captureforge-facial-rig-test/generalized-weights'
CASES={'female':{'glb':ROOT/'assets/tripo/vela-photoreal/generated-original.glb','goal1':ROOT/'verification/goal1-generalization-run/cross-character-accuracy/female/refined/raycast-report.json','markers':ROOT/'verification/goal2-browInnerUp-proof/step4-tripo-transfer/female/landmark_markers.json'},'male':{'glb':ROOT/'assets/tripo/generalization-male-20261105/generated-original.glb','goal1':ROOT/'verification/goal1-generalization-run/cross-character-accuracy/male/refined/raycast-report.json','markers':ROOT/'verification/goal2-browInnerUp-proof/step4-tripo-transfer/male/landmark_markers.json'}}

def geodesic_weights(co,specs,g,polys):
    anchors=[np.asarray(s['anchor'],float) for s in specs if s['anchor'] is not None]
    mask=np.zeros(len(co),bool); nearest=np.full(len(co),1e30)
    for a in anchors:
        d=np.linalg.norm(co-a,axis=1); nearest=np.minimum(nearest,d)
    mask=nearest <= 3.0*float(g['ew'])
    idx=np.flatnonzero(mask); inv=-np.ones(len(co),np.int64); inv[idx]=np.arange(len(idx))
    tri=polys[np.all(mask[polys],axis=1)]
    ed=np.concatenate([tri[:,[0,1]],tri[:,[1,2]],tri[:,[2,0]]],axis=0); ed=np.sort(ed,axis=1); ed=np.unique(ed,axis=0)
    adj=[[] for _ in range(len(idx))]
    for a,b in ed:
        ia,ib=int(inv[a]),int(inv[b]); l=float(np.linalg.norm(co[a]-co[b])); adj[ia].append((ib,l)); adj[ib].append((ia,l))
    out={s['name']:np.zeros(len(co),float) for s in specs}
    for s in specs:
        if s['anchor'] is None: continue
        anchor=np.asarray(s['anchor'],float); seed_count=min(16,len(idx)); order=np.argsort(np.linalg.norm(co[idx]-anchor,axis=1))[:seed_count]; dist=np.full(len(idx),np.inf); heap=[]
        for oi in order: dist[oi]=float(np.linalg.norm(co[idx[oi]]-anchor)); heapq.heappush(heap,(dist[oi],int(oi)))
        while heap:
            d,u=heapq.heappop(heap)
            if d!=dist[u]: continue
            for v,l in adj[u]:
                nd=d+l
                if nd<dist[v]: dist[v]=nd; heapq.heappush(heap,(nd,v))
        support=max(3.0*float(s['radius']),1.5*float(g['ew'])); t=np.clip(1.0-dist/support,0,1); out[s['name']][idx]=(t*t*(3-2*t))**2
    total=np.zeros(len(co),float)
    for v in out.values(): total+=v
    for n in out: out[n]=np.divide(out[n],np.maximum(total,1.0),where=np.ones(len(co),bool))
    out['head']=np.maximum(0.0,1.0-total/np.maximum(total,1.0))
    return out,int(mask.sum()),len(tri),len(ed)

def run(label,cfg):
    out=OUT/label; out.mkdir(parents=True,exist_ok=True); goal,src=base.records(cfg['goal1']); marker=json.loads(cfg['markers'].read_text(encoding='utf-8')); bpy.ops.wm.read_factory_settings(use_empty=True)
    source=Path(goal.get('sourceGLB','')); source=source if source.exists() else cfg['glb']; shift=np.zeros(3)
    if source.resolve()!=cfg['glb'].resolve():
        s=base.import_main(source); sv=base.world_vertices(s); sc=(sv.min(0)+sv.max(0))/2; bpy.ops.wm.read_factory_settings(use_empty=True)
    else: sc=np.zeros(3)
    body=base.import_main(cfg['glb']); scene=bpy.context.scene; tv=base.world_vertices(body); tc=(tv.min(0)+tv.max(0))/2; shift=tc-sc if source.resolve()!=cfg['glb'].resolve() else shift
    deps=bpy.context.evaluated_depsgraph_get(); bvh=BVHTree.FromObject(body,deps); M=np.asarray(body.matrix_world,float); l=np.empty(len(body.data.vertices)*3,float); body.data.vertices.foreach_get('co',l); l=l.reshape(-1,3); world=l@M[:3,:3].T+M[:3,3]
    mapped={}; att={}; dd=[]
    for i,r in src.items():
        q=bvh.find_nearest(Vector(np.asarray(r['meshXYZ'])+shift)); loc,n,pi,dist=q; poly=body.data.polygons[int(pi)]; tri=[int(x) for x in poly.vertices]; p=np.asarray(loc,float); mapped[i]=p; att[i]={'triangleVertexIndices':tri,'barycentricCoordinates':base.barycentric(p,world[tri[0]],world[tri[1]],world[tri[2]])}; dd.append(float(dist))
    c,R=base.frame({i:mapped[i] for i in [10,33,152,263]}); can=base.canon(world,c,R); work=body.copy(); work.data=body.data.copy(); work.name=label+'_GeneralizedWeightsCopy'; body.users_collection[0].objects.link(work)
    for i,v in enumerate(work.data.vertices): v.co=Vector(can[i])
    work.location=(0,0,0); work.rotation_euler=(0,0,0); work.scale=(1,1,1); work.parent=None; P={n:Vector(base.canon(mapped[idx],c,R)) for n,idx in autofit.LANDMARKS.items()}; rig=autofit.build_faceforge_rig(P,work,(),name=label+'_GeneralizedFaceRig'); g=autofit.face_geometry(P,work,()); specs=autofit.bone_specs(P,g); polys=np.asarray([[int(x) for x in f.vertices] for f in work.data.polygons if len(f.vertices)==3],np.int64); weights,nv,nt,ne=geodesic_weights(can,specs,g,polys)
    for vg in list(work.vertex_groups): work.vertex_groups.remove(vg)
    autofit._bind(work,rig,weights); neutral=base.eval_world(work); ew=float(np.linalg.norm(base.canon(mapped[33],c,R)-base.canon(mapped[263],c,R))); delta=base.canon(np.asarray(marker['samples']['100'][105])-np.asarray(marker['neutral'][105]),np.zeros(3),R); pb=rig.pose.bones['brow.mid.R']; m=pb.matrix.copy(); m.translation=m.translation+Vector(delta); pb.matrix=m; expressed=base.eval_world(work); a=att[105]['triangleVertexIndices']; w=np.asarray(att[105]['barycentricCoordinates']); p0=(w[:,None]*neutral[a]).sum(0); p1=(w[:,None]*expressed[a]).sum(0); err=float(np.linalg.norm((p1-p0)-delta)); tri=polys; x=neutral[tri[:,1]]-neutral[tri[:,0]]; y=neutral[tri[:,2]]-neutral[tri[:,0]]; xx=expressed[tri[:,1]]-expressed[tri[:,0]]; yy=expressed[tri[:,2]]-expressed[tri[:,0]]; ar0=np.linalg.norm(np.cross(x,y),axis=1); ar1=np.linalg.norm(np.cross(xx,yy),axis=1); e0=np.concatenate([np.linalg.norm(neutral[tri[:,1]]-neutral[tri[:,0]],axis=1),np.linalg.norm(neutral[tri[:,2]]-neutral[tri[:,1]],axis=1),np.linalg.norm(neutral[tri[:,0]]-neutral[tri[:,2]],axis=1)]); e1=np.concatenate([np.linalg.norm(expressed[tri[:,1]]-expressed[tri[:,0]],axis=1),np.linalg.norm(expressed[tri[:,2]]-expressed[tri[:,1]],axis=1),np.linalg.norm(expressed[tri[:,0]]-expressed[tri[:,2]],axis=1)]); strain=np.abs(e1/(e0+1e-12)-1)
    fp=np.array([base.canon(mapped[i],c,R) for i in range(468)]); scale=max(float(np.ptp(fp[:,0])),float(np.ptp(fp[:,2])))*1.6; cam={'cx':float((fp[:,0].min()+fp[:,0].max())/2),'cz':float((fp[:,2].min()+fp[:,2].max())/2),'scale':scale,'y':float(fp[:,1].min()-scale),'depth':float(np.ptp(fp[:,1]))}; [setattr(o,'hide_render',o!=work) for o in scene.objects]; [setattr(o,'show_wire',False) for o in scene.objects if o.type=='MESH']; pb.matrix=pb.bone.matrix_local; autofit.render_front(scene,[work],str(out/'neutral.png'),cam,size=768,color_type='TEXTURE'); m=pb.matrix.copy(); m.translation=m.translation+Vector(delta); pb.matrix=m; autofit.render_front(scene,[work],str(out/'full-target.png'),cam,size=768,color_type='TEXTURE'); [setattr(o,'show_wire',True) for o in scene.objects if o.type=='MESH']; pb.matrix=pb.bone.matrix_local; autofit.render_front(scene,[work],str(out/'neutral-wireframe.png'),cam,size=768,color_type='TEXTURE'); pb.matrix=m; autofit.render_front(scene,[work],str(out/'full-target-wireframe.png'),cam,size=768,color_type='TEXTURE')
    res={'character':label,'algorithm':'CaptureForge bone architecture plus surface-geodesic diffusion weights','source_translation':shift.tolist(),'mapped_landmarks':len(mapped),'surface_distance_median':float(np.median(dd)),'eye_width':ew,'region_vertices':nv,'region_triangles':nt,'region_edges':ne,'weights_nonzero':{n:int(np.sum(v>1e-4)) for n,v in weights.items() if n.startswith('brow.')},'landmark105_requested':delta.tolist(),'landmark105_achieved':(p1-p0).tolist(),'landmark105_error_percent':100*err/max(float(np.linalg.norm(delta)),1e-12),'min_area_ratio':float(np.min(ar1/(ar0+1e-12))),'collapsed_triangles':int(np.sum(ar1<=0.1*ar0)),'max_edge_strain':float(np.max(strain)),'p95_edge_strain':float(np.percentile(strain,95)),'neutral_render':str(out/'neutral.png'),'full_target_render':str(out/'full-target.png'),'visual_pass':False}
    (out/'result.json').write_text(json.dumps(res,indent=2),encoding='utf-8'); print(json.dumps(res,indent=2))

if __name__=='__main__':
    for label,cfg in CASES.items(): run(label,cfg)
