"""Corrected CaptureForge setup diagnostic.

The test keeps the source GLBs untouched. It remaps the existing Goal 1
landmark surface points onto the exact input GLB with a BVH, builds the
CaptureForge rig on a temporary exact vertex copy, and runs a controlled
brow-bone movement before any video coefficient is used.
"""
import json, os, sys
from pathlib import Path
import bpy, numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

CAPTUREFORGE = r"C:\Users\USER\captureforge"
sys.path.insert(0, CAPTUREFORGE)
from captureforge.face import autofit

ROOT = Path(r"C:\Users\USER\talking-character-demo")
OUT = ROOT / "verification/captureforge-facial-rig-test/corrected"
CASES = {
    "female": {
        "glb": ROOT / "assets/tripo/vela-photoreal/generated-original.glb",
        "goal1": ROOT / "verification/goal1-generalization-run/cross-character-accuracy/female/refined/raycast-report.json",
    },
    "male": {
        "glb": ROOT / "assets/tripo/generalization-male-20261105/generated-original.glb",
        "goal1": ROOT / "verification/goal1-generalization-run/cross-character-accuracy/male/refined/raycast-report.json",
    },
}

def records(path):
    d = json.loads(path.read_text(encoding="utf-8"))
    return d, {int(r["index"]): r for r in d["records"] if r.get("meshXYZ")}

def world_vertices(obj):
    M = np.asarray(obj.matrix_world, float)
    a = np.empty(len(obj.data.vertices) * 3, float)
    obj.data.vertices.foreach_get("co", a)
    return a.reshape(-1, 3) @ M[:3,:3].T + M[:3,3]

def import_main(path):
    bpy.ops.import_scene.gltf(filepath=str(path))
    return max((o for o in bpy.context.scene.objects if o.type=='MESH'), key=lambda o:len(o.data.vertices))

def barycentric(p, a, b, c):
    v0, v1, v2 = b-a, c-a, p-a
    d00, d01, d11 = np.dot(v0,v0), np.dot(v0,v1), np.dot(v1,v1)
    d20, d21 = np.dot(v2,v0), np.dot(v2,v1)
    den = d00*d11-d01*d01
    if abs(den) < 1e-15: return [1.0,0.0,0.0]
    v, w = (d11*d20-d01*d21)/den, (d00*d21-d01*d20)/den
    return [float(1-v-w), float(v), float(w)]

def frame(p):
    center=(p[33]+p[263])/2
    right=p[263]-p[33]; right/=np.linalg.norm(right)
    up=p[10]-p[152]; up-=right*np.dot(up,right); up/=np.linalg.norm(up)
    outward=np.cross(right,up); outward/=np.linalg.norm(outward)
    return center, np.stack([right,-outward,up],axis=0)

def canon(x,c,R): return (np.asarray(x)-c)@R.T

def eval_world(obj):
    deps=bpy.context.evaluated_depsgraph_get(); eo=obj.evaluated_get(deps)
    M=np.asarray(eo.matrix_world,float); a=np.empty(len(eo.data.vertices)*3,float)
    eo.data.vertices.foreach_get('co',a)
    return a.reshape(-1,3)@M[:3,:3].T+M[:3,3]

def pose_brows(rig, axis, amount):
    for b in rig.pose.bones:
        if b.name.startswith('brow.'):
            b.rotation_mode='XYZ'; b.rotation_euler=(0.0,0.0,0.0); b.rotation_euler[axis]=amount

def render(scene, obj, path, cam):
    autofit.render_front(scene,[obj],str(path),cam,size=768,color_type='TEXTURE')

def run(label,cfg):
    out=OUT/label; out.mkdir(parents=True,exist_ok=True)
    goal, src_ids=records(cfg['goal1'])
    bpy.ops.wm.read_factory_settings(use_empty=True)
    source_path=Path(goal.get('sourceGLB',''))
    if not source_path.exists(): source_path=Path(cfg['glb'])
    source_center=np.zeros(3)
    if source_path.resolve()!=Path(cfg['glb']).resolve():
        source_body=import_main(source_path); sv=world_vertices(source_body); source_center=(sv.min(0)+sv.max(0))/2
        bpy.ops.wm.read_factory_settings(use_empty=True)
    body=import_main(cfg['glb']); tv=world_vertices(body); target_center=(tv.min(0)+tv.max(0))/2
    scene=bpy.context.scene
    source_translation=target_center-source_center if source_path.resolve()!=Path(cfg['glb']).resolve() else np.zeros(3)
    src_pts=np.array([src_ids[i]['meshXYZ'] for i in sorted(src_ids)],float)
    deps=bpy.context.evaluated_depsgraph_get()
    bvh=BVHTree.FromObject(body,deps)
    mapped={}; attachments={}; dists=[]; misses=[]
    M=np.asarray(body.matrix_world,float)
    local=np.empty(len(body.data.vertices)*3,float); body.data.vertices.foreach_get('co',local)
    local=local.reshape(-1,3); world=local@M[:3,:3].T+M[:3,3]
    for i,r in src_ids.items():
        query=np.asarray(r['meshXYZ'],float)+source_translation
        q=bvh.find_nearest(Vector(query))
        if q is None:
            misses.append(i); continue
        loc, normal, poly, dist=q
        poly=body.data.polygons[int(poly)]
        if len(poly.vertices)!=3:
            misses.append(i); continue
        tri=[int(x) for x in poly.vertices]
        p=np.array(loc,float); mapped[i]=p; attachments[i]={'triangleVertexIndices':tri,'barycentricCoordinates':barycentric(p,world[tri[0]],world[tri[1]],world[tri[2]]),'distance':float(dist)}; dists.append(float(dist))
    if len(mapped)<468:
        res={'character':label,'status':'FAILED','stage':'original-surface-correspondence','mapped':len(mapped),'missing_ids':misses,'source_glb':str(cfg['glb']),'goal1_source':goal.get('sourceGLB')}
        (out/'result.json').write_text(json.dumps(res,indent=2),encoding='utf-8'); print(json.dumps(res,indent=2)); return
    p=np.array([mapped[i] for i in range(468)],float)
    c,R=frame({i:mapped[i] for i in [10,33,152,263]})
    can=canon(world,c,R)
    work=body.copy(); work.data=body.data.copy(); work.name=label+'_CaptureForgeExactOriginalCopy'; body.users_collection[0].objects.link(work)
    for i,v in enumerate(work.data.vertices): v.co=Vector(can[i])
    work.location=(0,0,0); work.rotation_euler=(0,0,0); work.scale=(1,1,1); work.parent=None
    P={name:Vector(canon(mapped[idx],c,R)) for name,idx in autofit.LANDMARKS.items()}
    rig=autofit.build_faceforge_rig(P,work,(),name=label+'_CaptureForgeFaceRigCorrected')
    neutral=eval_world(work)
    pcan={i:canon(mapped[i],c,R) for i in mapped}
    brow_ids=[70,105,334,336,293,63]
    region=np.zeros(len(neutral),bool)
    for i in brow_ids: region |= np.linalg.norm(neutral-pcan[i],axis=1)<0.75*np.linalg.norm(pcan[33]-pcan[263])
    tests=[]
    for axis in range(3):
        for sign in (-1,1):
            pose_brows(rig,axis,sign*0.25); v=eval_world(work); delta=v-neutral
            tests.append({'axis':axis,'sign':sign,'mean_region_up':float(np.mean(delta[region,2])),'max_region_motion':float(np.max(np.linalg.norm(delta[region],axis=1))),'nonzero_vertices':int(np.sum(np.linalg.norm(delta,axis=1)>1e-8))})
    best=max(tests,key=lambda x:x['mean_region_up'])
    pose_brows(rig,best['axis'],best['sign']*0.25); raised=eval_world(work)
    bone_transforms=[]
    for b in rig.pose.bones:
        if b.name.startswith('brow.'):
            bone_transforms.append({'name':b.name,'rotation_euler':list(map(float,b.rotation_euler)),'matrix_translation':list(map(float,b.matrix.translation))})
    armature_modifiers=[{'name':m.name,'type':m.type,'object':m.object.name if getattr(m,'object',None) else None} for m in work.modifiers if m.type=='ARMATURE']
    brow_group_names={b.name for b in rig.data.bones if b.name.startswith('brow.')}
    brow_group_indices={g.index:g.name for g in work.vertex_groups if g.name in brow_group_names}
    brow_weight_stats={name:{'vertices_with_weight':0,'max_weight':0.0} for name in brow_group_names}
    for v in work.data.vertices:
        for g in v.groups:
            if g.group in brow_group_indices:
                name=brow_group_indices[g.group]; brow_weight_stats[name]['vertices_with_weight']+=1; brow_weight_stats[name]['max_weight']=max(brow_weight_stats[name]['max_weight'],float(g.weight))
    rows=[]
    for i in brow_ids:
        rec=attachments[i]; tri=rec['triangleVertexIndices']; w=np.array(rec['barycentricCoordinates']); a=(w[:,None]*neutral[tri]).sum(axis=0); b=(w[:,None]*raised[tri]).sum(axis=0); rows.append({'id':i,'delta':(b-a).tolist(),'distance':float(np.linalg.norm(b-a))})
    tri=np.asarray([[int(x) for x in f.vertices] for f in work.data.polygons if len(f.vertices)==3],int); a=neutral[tri[:,1]]-neutral[tri[:,0]]; b=neutral[tri[:,2]]-neutral[tri[:,0]]; c1=raised[tri[:,1]]-raised[tri[:,0]]; d=raised[tri[:,2]]-raised[tri[:,0]]; ar0=np.linalg.norm(np.cross(a,b),axis=1); ar1=np.linalg.norm(np.cross(c1,d),axis=1)
    fp=np.array(list(pcan.values())); fscale=max(float(fp[:,0].max()-fp[:,0].min()),float(fp[:,2].max()-fp[:,2].min()))*1.6
    cam={'cx':float((fp[:,0].min()+fp[:,0].max())/2),'cz':float((fp[:,2].min()+fp[:,2].max())/2),'scale':fscale,'y':float(fp[:,1].min()-fscale),'depth':float(fp[:,1].max()-fp[:,1].min())}
    pose_brows(rig, best['axis'], 0.0); render(scene,work,out/'neutral.png',cam); pose_brows(rig,best['axis'],best['sign']*0.25); render(scene,work,out/'controlled-brow.png',cam)
    res={'character':label,'status':'CONTROLLED_TEST_COMPLETE','source_glb':str(cfg['glb']),'goal1_source':goal.get('sourceGLB'),'automatic_source_translation':source_translation.tolist(),'source_vertex_count':len(body.data.vertices),'mapped_landmarks':len(mapped),'missing_ids':misses,'nearest_surface_distance':{'median':float(np.median(dists)),'p95':float(np.percentile(dists,95)),'max':float(max(dists))},'eye_width':float(np.linalg.norm(pcan[33]-pcan[263])),'rig_bones':len(rig.data.bones),'brow_bone_names':[b.name for b in rig.data.bones if b.name.startswith('brow.')],'weight_groups':len(work.vertex_groups),'armature_modifiers':armature_modifiers,'brow_weight_stats':brow_weight_stats,'evaluated_brow_bone_transforms':bone_transforms,'controlled_axis':best['axis'],'controlled_sign':best['sign'],'axis_tests':tests,'brow_landmark_motion':rows,'nonzero_vertices':int(np.sum(np.linalg.norm(raised-neutral,axis=1)>1e-8)),'min_area_ratio':float(np.min(ar1/(ar0+1e-12))),'collapsed_triangles':int(np.sum(ar1<=0.1*ar0)),'neutral_render':str(out/'neutral.png'),'controlled_render':str(out/'controlled-brow.png'),'controlled_bone_test_pass':bool(best['max_region_motion']>1e-8),'visible_expression_pass':False}
    (out/'attachments.json').write_text(json.dumps(attachments,indent=2),encoding='utf-8'); (out/'result.json').write_text(json.dumps(res,indent=2),encoding='utf-8'); print(json.dumps(res,indent=2))

for label,cfg in CASES.items(): run(label,cfg)
