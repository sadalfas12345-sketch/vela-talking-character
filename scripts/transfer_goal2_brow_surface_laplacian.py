"""Constrained surface-Laplacian brow transfer for rigged or unrigged GLBs.

This is a surface-aware equivalent to a local ARAP preconditioner: displacement
is diffused over the actual target mesh adjacency while barycentric Goal-1
landmarks remain hard constraints. No target vertex ids or per-character masks
are encoded; all target topology comes from the imported GLB and manifest.
"""
import json, sys
from pathlib import Path
import bpy
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
BROW=[70,63,105,336,293,334]
ANCHORS=[159,145,386,374,33,133,263,362,168,6,1,98,327,234,454,152,10,127,356]

def arg(name):
    a=sys.argv[sys.argv.index('--')+1:]
    return Path(a[a.index(name)+1]).resolve()

def main():
    source, donor_npz, fit_json = arg('--source'),arg('--donor-npz'),arg('--fit')
    goal1, output, report_path = arg('--goal1'),arg('--output'),arg('--report')
    points=json.loads((ROOT/'verification/avaturn-face-fit-landmark-points.json').read_text())
    ray=json.loads(goal1.read_text()); records={int(r['index']):r for r in ray['records'] if r.get('frontSurface') and r.get('meshXYZ')}
    if sorted(set(BROW+ANCHORS)-set(records)): raise SystemExit('missing required Goal-1 attachments')
    donor=np.load(donor_npz); base_d=donor['Head_Mesh__Basis'].astype(float); expr=donor['Head_Mesh__Key__browInnerUp'].astype(float); faces_d=donor['Head_Mesh__Triangles'].astype(int)
    rot=np.asarray(json.loads(fit_json.read_text())['similarity']['rotation'],float)
    bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=str(source)); meshes=[o for o in bpy.context.scene.objects if o.type=='MESH']; body=max(meshes,key=lambda o:len(o.data.vertices)); n=len(body.data.vertices)
    local=np.empty((n,3),float); body.data.vertices.foreach_get('co',local.ravel()); mw=np.asarray(body.matrix_world,float); world=local@mw[:3,:3].T+mw[:3,3]
    target={i:np.asarray(records[i]['meshXYZ'],float) for i in records}; eye=float(np.linalg.norm(target[33]-target[263])); donor_eye=float(np.linalg.norm(np.asarray(points['donorPoints'][33])-np.asarray(points['donorPoints'][263]))); scale=eye/donor_eye
    donor_delta={}
    for i in BROW:
        tri=faces_d[int(points['donorFaceIds'][i])]; b=np.asarray(points['donorBarycentric'][i],float); donor_delta[i]=scale*((b[:,None]*(expr[tri]-base_d[tri])).sum(0))@rot
    center=np.mean([target[i] for i in BROW],axis=0); face_extent=float(np.linalg.norm(center-target[152])); radius=face_extent*.50
    handles=np.asarray([target[i] for i in BROW+ANCHORS]); candidate=np.flatnonzero(np.min(np.linalg.norm(world[:,None]-handles[None],axis=2),axis=1)<=radius); mask=np.zeros(n,bool); mask[candidate]=True
    tris=np.asarray([[v for v in p.vertices] for p in body.data.polygons],int); edge=np.concatenate([tris[:,[0,1]],tris[:,[1,2]],tris[:,[2,0]]],axis=0); keep=mask[edge[:,0]]&mask[edge[:,1]]; edge=edge[keep]
    delta=np.zeros((n,3),float)
    constraints=[]
    for i in BROW+ANCHORS:
        r=records[i]; vi=np.asarray(r['triangleVertexIndices'],int); b=np.asarray(r['barycentricCoordinates'],float); desired=donor_delta[i] if i in donor_delta else np.zeros(3); constraints.append((vi,b,desired)); delta[vi]+=b[:,None]*desired/max(float((b*b).sum()),1e-12)
    def enforce():
        for vi,b,desired in constraints:
            residual=desired-(b[:,None]*delta[vi]).sum(0); delta[vi]+=b[:,None]*residual/max(float((b*b).sum()),1e-12)
    enforce(); degree=np.zeros(n,float); np.add.at(degree,edge[:,0],1); np.add.at(degree,edge[:,1],1)
    for _ in range(24):
        total=np.zeros_like(delta); np.add.at(total,edge[:,0],delta[edge[:,1]]); np.add.at(total,edge[:,1],delta[edge[:,0]])
        smooth=total[candidate]/np.maximum(degree[candidate,None],1)
        delta[candidate]=.65*delta[candidate]+.35*smooth; enforce()
    # Geometric validity projection, applied only to vertices in inverted faces.
    base_tri=world[tris]; base_norm=np.cross(base_tri[:,1]-base_tri[:,0],base_tri[:,2]-base_tri[:,0]); factors=np.ones(n); inv_iters=0
    for _ in range(24):
        posed=(world+delta*factors[:,None])[tris]; norm=np.cross(posed[:,1]-posed[:,0],posed[:,2]-posed[:,0]); invalid=np.einsum('ij,ij->i',base_norm,norm)<0
        if not invalid.any(): break
        factors[np.unique(tris[invalid].ravel())]*=.5; inv_iters+=1
    delta*=factors[:,None]; local_delta=delta@np.linalg.inv(mw[:3,:3]).T
    body.shape_key_add(name='Basis',from_mix=False); key=body.shape_key_add(name='xfer_browInnerUp_surface_laplacian',from_mix=False); key.data.foreach_set('co',(local+local_delta).astype(np.float32).ravel()); key.value=0; body.data.shape_keys.use_relative=True; body.data.shape_keys.animation_data_clear()
    bpy.ops.object.select_all(action='DESELECT')
    for obj in bpy.context.scene.objects:
        if obj.type in {'MESH','ARMATURE','EMPTY'}: obj.select_set(True)
    bpy.context.view_layer.objects.active=body; output.parent.mkdir(parents=True,exist_ok=True); bpy.ops.export_scene.gltf(filepath=str(output),export_format='GLB',export_morph=True,export_skins=True,export_animations=True,export_apply=False)
    result={'architecture':'constrained surface Laplacian deformation on local target mesh adjacency; donor motion only; original target vertices retained','shapeKey':key.name,'source':str(source),'goal1Manifest':str(goal1),'targetVertexCount':n,'targetHasArmature':any(o.type=='ARMATURE' for o in bpy.context.scene.objects),'eyeWidthMillimeters':eye*1000,'donorEyeWidthMillimeters':donor_eye*1000,'motionScaleTargetOverDonorEyeWidth':scale,'localSubmeshVertexCount':int(len(candidate)),'surfaceEdgeCount':int(len(edge)),'laplacianIterations':24,'inversionProjectionIterations':inv_iters,'minimumLocalMotionFactor':float(factors.min()),'output':str(output)}
    report_path.parent.mkdir(parents=True,exist_ok=True); report_path.write_text(json.dumps(result,indent=2)+'\n'); print(json.dumps(result,indent=2))
if __name__=='__main__': main()
