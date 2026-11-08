"""Isolate and correct CaptureForge eyebrow control on the exact original GLBs."""
import json, sys
from pathlib import Path
import bpy, numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

ROOT=Path(r'C:\Users\USER\talking-character-demo')
sys.path.insert(0,str(ROOT/'scripts'))
import diagnose_captureforge_corrected_setup as base
from captureforge.face import autofit

OUT=ROOT/'verification/captureforge-facial-rig-test/eyebrow-control'
CASES={
 'female': {'glb':ROOT/'assets/tripo/vela-photoreal/generated-original.glb','goal1':ROOT/'verification/goal1-generalization-run/cross-character-accuracy/female/refined/raycast-report.json','markers':ROOT/'verification/goal2-browInnerUp-proof/step4-tripo-transfer/female/landmark_markers.json'},
 'male': {'glb':ROOT/'assets/tripo/generalization-male-20261105/generated-original.glb','goal1':ROOT/'verification/goal1-generalization-run/cross-character-accuracy/male/refined/raycast-report.json','markers':ROOT/'verification/goal2-browInnerUp-proof/step4-tripo-transfer/male/landmark_markers.json'},
}
BROW={'brow.in.L':336,'brow.mid.L':334,'brow.out.L':300,'brow.in.R':107,'brow.mid.R':105,'brow.out.R':70}

def evalv(o): return base.eval_world(o)
def ptri(v,att):
    t=att['triangleVertexIndices']; w=np.asarray(att['barycentricCoordinates']); return (w[:,None]*v[t]).sum(0)
def reset(rig):
    for b in rig.pose.bones:
        b.rotation_mode='XYZ'; b.rotation_euler=(0,0,0); b.location=(0,0,0)
def translate_bone_armature_space(pb,delta):
    m=pb.matrix.copy(); m.translation=m.translation+Vector(delta); pb.matrix=m
def build(label,cfg):
    out=OUT/label; out.mkdir(parents=True,exist_ok=True)
    goal,src=base.records(cfg['goal1']); marker=json.loads(cfg['markers'].read_text(encoding='utf-8'))
    bpy.ops.wm.read_factory_settings(use_empty=True)
    source_path=Path(goal.get('sourceGLB',''))
    if not source_path.exists(): source_path=cfg['glb']
    src_center=np.zeros(3)
    if source_path.resolve()!=cfg['glb'].resolve():
        s=base.import_main(source_path); sv=base.world_vertices(s); src_center=(sv.min(0)+sv.max(0))/2; bpy.ops.wm.read_factory_settings(use_empty=True)
    body=base.import_main(cfg['glb']); scene=bpy.context.scene; tv=base.world_vertices(body); tgt_center=(tv.min(0)+tv.max(0))/2; shift=tgt_center-src_center if source_path.resolve()!=cfg['glb'].resolve() else np.zeros(3)
    deps=bpy.context.evaluated_depsgraph_get(); bvh=BVHTree.FromObject(body,deps); M=np.asarray(body.matrix_world,float); local=np.empty(len(body.data.vertices)*3,float); body.data.vertices.foreach_get('co',local); local=local.reshape(-1,3); world=local@M[:3,:3].T+M[:3,3]
    mapped={}; attachments={}; distances=[]
    for i,r in src.items():
        q=bvh.find_nearest(Vector(np.asarray(r['meshXYZ'])+shift))
        if not q: continue
        loc,n,pi,dist=q; poly=body.data.polygons[int(pi)]
        if len(poly.vertices)!=3: continue
        tri=[int(x) for x in poly.vertices]; p=np.asarray(loc,float); mapped[i]=p; attachments[i]={'triangleVertexIndices':tri,'barycentricCoordinates':base.barycentric(p,world[tri[0]],world[tri[1]],world[tri[2]])}; distances.append(float(dist))
    if len(mapped)!=len(src): raise RuntimeError(f'{label}: only {len(mapped)} of {len(src)} surface attachments mapped')
    c,R=base.frame({i:mapped[i] for i in [10,33,152,263]}); can=base.canon(world,c,R)
    work=body.copy(); work.data=body.data.copy(); work.name=label+'_CaptureForgeEyebrowControlCopy'; body.users_collection[0].objects.link(work)
    for i,v in enumerate(work.data.vertices): v.co=Vector(can[i])
    work.location=(0,0,0); work.rotation_euler=(0,0,0); work.scale=(1,1,1); work.parent=None
    P={n:Vector(base.canon(mapped[idx],c,R)) for n,idx in autofit.LANDMARKS.items()}
    rig=autofit.build_faceforge_rig(P,work,(),name=label+'_CaptureForgeEyebrowRig')
    neutral=evalv(work); ew=float(np.linalg.norm(base.canon(mapped[33],c,R)-base.canon(mapped[263],c,R)))
    brow_tri=attachments[105]['triangleVertexIndices']; weights=[]
    group_names={g.index:g.name for g in work.vertex_groups}
    for vi in brow_tri:
        weights.append({'vertex':vi,'groups':{group_names[g.group]:float(g.weight) for g in work.data.vertices[vi].groups if group_names.get(g.group,'').startswith('brow.')}})
    bone_audit=[]
    for name in ['brow.mid.R','brow.in.R','brow.mid.L']:
        b=rig.pose.bones[name]; bone_audit.append({'name':name,'head':list(map(float,b.bone.head_local)),'tail':list(map(float,b.bone.tail_local)),'length':float(b.bone.length),'rotation_mode':b.rotation_mode,'parent':b.parent.name if b.parent else None})
    pb=rig.pose.bones['brow.mid.R']; reset(rig); rot0=evalv(work); pb.rotation_euler[0]=0.25; rotated=evalv(work); rot_land=ptri(rotated,attachments[105])-ptri(rot0,attachments[105]); rot_max=float(np.max(np.linalg.norm(rotated-rot0,axis=1))); reset(rig); direct_delta=np.array([0,0,0.01*ew]); translate_bone_armature_space(pb,direct_delta); translated=evalv(work); trans_land=ptri(translated,attachments[105])-ptri(rot0,attachments[105]); trans_max=float(np.max(np.linalg.norm(translated-rot0,axis=1)))
    # Apply full existing landmark-105 motion through a translation control. The
    # displacement is read from the stored normalized transfer, never invented.
    reset(rig); neutral2=evalv(work); marker_delta={i:base.canon(np.asarray(marker['samples']['100'][i])-np.asarray(marker['neutral'][i]),np.zeros(3),R) for i in range(468)}
    # Isolate the requested Experiment 5 control: landmark 105 only.
    translate_bone_armature_space(rig.pose.bones['brow.mid.R'],marker_delta[105])
    expressed=evalv(work); full_rows=[]
    for lid in [70,105,334,336,293,63]:
        actual=ptri(expressed,attachments[lid])-ptri(neutral2,attachments[lid]); requested=marker_delta[lid]; err=float(np.linalg.norm(actual-requested)); full_rows.append({'id':lid,'requested':requested.tolist(),'achieved':actual.tolist(),'error':err,'requested_magnitude':float(np.linalg.norm(requested)),'error_percent':float(100*err/max(np.linalg.norm(requested),1e-12))})
    tri=np.asarray([[int(x) for x in f.vertices] for f in work.data.polygons if len(f.vertices)==3],int); a=neutral2[tri[:,1]]-neutral2[tri[:,0]]; b=neutral2[tri[:,2]]-neutral2[tri[:,0]]; c1=expressed[tri[:,1]]-expressed[tri[:,0]]; d=expressed[tri[:,2]]-expressed[tri[:,0]]; ar0=np.linalg.norm(np.cross(a,b),axis=1); ar1=np.linalg.norm(np.cross(c1,d),axis=1); edge0=np.concatenate([np.linalg.norm(neutral2[tri[:,1]]-neutral2[tri[:,0]],axis=1),np.linalg.norm(neutral2[tri[:,2]]-neutral2[tri[:,1]],axis=1),np.linalg.norm(neutral2[tri[:,0]]-neutral2[tri[:,2]],axis=1)]); edge1=np.concatenate([np.linalg.norm(expressed[tri[:,1]]-expressed[tri[:,0]],axis=1),np.linalg.norm(expressed[tri[:,2]]-expressed[tri[:,1]],axis=1),np.linalg.norm(expressed[tri[:,0]]-expressed[tri[:,2]],axis=1)]); strain=np.abs(edge1/(edge0+1e-12)-1)
    fp=np.array([base.canon(mapped[i],c,R) for i in range(468)]); scale=max(float(np.ptp(fp[:,0])),float(np.ptp(fp[:,2])))*1.6; cam={'cx':float((fp[:,0].min()+fp[:,0].max())/2),'cz':float((fp[:,2].min()+fp[:,2].max())/2),'scale':scale,'y':float(fp[:,1].min()-scale),'depth':float(np.ptp(fp[:,1]))}; reset(rig); autofit.render_front(scene,[work],str(out/'neutral.png'),cam,size=768,color_type='TEXTURE'); translate_bone_armature_space(rig.pose.bones['brow.mid.R'],marker_delta[105]); autofit.render_front(scene,[work],str(out/'full-target.png'),cam,size=768,color_type='TEXTURE'); [setattr(o,'show_wire',True) for o in scene.objects if o.type=='MESH']; [setattr(o,'show_all_edges',True) for o in scene.objects if o.type=='MESH']; reset(rig); autofit.render_front(scene,[work],str(out/'neutral-wireframe.png'),cam,size=768,color_type='SINGLE'); translate_bone_armature_space(rig.pose.bones['brow.mid.R'],marker_delta[105]); autofit.render_front(scene,[work],str(out/'full-target-wireframe.png'),cam,size=768,color_type='SINGLE'); [setattr(o,'show_wire',False) for o in scene.objects if o.type=='MESH']
    res={'character':label,'source_translation':shift.tolist(),'mapped_landmarks':len(mapped),'surface_distance':{'median':float(np.median(distances)),'p95':float(np.percentile(distances,95)),'max':float(max(distances))},'eye_width':ew,'landmark105_neutral':ptri(neutral2,attachments[105]).tolist(),'landmark105_triangle':brow_tri,'landmark105_vertex_brow_weights':weights,'bone_audit':bone_audit,'armature_modifiers':[{'name':m.name,'object':m.object.name if m.object else None} for m in work.modifiers if m.type=='ARMATURE'],'rotation_025':{'landmark105_delta':rot_land.tolist(),'landmark105_magnitude':float(np.linalg.norm(rot_land)),'max_vertex_displacement':rot_max},'translation_1pct_eye_width':{'requested':direct_delta.tolist(),'landmark105_delta':trans_land.tolist(),'landmark105_magnitude':float(np.linalg.norm(trans_land)),'max_vertex_displacement':trans_max},'full_target':full_rows,'geometry':{'min_area_ratio':float(np.min(ar1/(ar0+1e-12))),'collapsed_triangles':int(np.sum(ar1<=0.1*ar0)),'max_edge_strain':float(np.max(strain)),'p95_edge_strain':float(np.percentile(strain,95)),'invalid_coordinates':int(np.sum(~np.isfinite(expressed)))},'neutral_render':str(out/'neutral.png'),'full_target_render':str(out/'full-target.png'),'neutral_wireframe':str(out/'neutral-wireframe.png'),'full_target_wireframe':str(out/'full-target-wireframe.png'),'visual_pass':False}
    (out/'result.json').write_text(json.dumps(res,indent=2),encoding='utf-8'); print(json.dumps(res,indent=2))

if __name__=='__main__':
    for label,cfg in CASES.items(): build(label,cfg)
