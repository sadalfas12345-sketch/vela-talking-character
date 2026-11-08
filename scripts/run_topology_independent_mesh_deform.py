"""Blender Mesh Deform cage fallback for the original Tripo landmark-105 test."""
import argparse, json, sys, time
from pathlib import Path
import bpy, numpy as np
from mathutils import Vector

def main():
    p=argparse.ArgumentParser()
    for n in ('source','goal','markers','patch','output','report'):
        p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args(sys.argv[sys.argv.index('--')+1:]); start=time.perf_counter()
    goal=json.loads(a.goal.read_text()); rec={int(x['index']):x for x in goal['records']}[105]
    markers=json.loads(a.markers.read_text()); pv=np.load(a.patch)['V'].astype(float); oi=np.load(a.patch)['originalIndices'].astype(np.int64)
    bary=np.asarray(rec['barycentricCoordinates'],float); lookup={int(x):i for i,x in enumerate(oi)}; tri=np.asarray([lookup[int(x)] for x in rec['triangleVertexIndices']],int)
    neutral=(bary[:,None]*pv[tri]).sum(0); requested=np.asarray(markers['samples']['100'])[105]-np.asarray(markers['neutral'])[105]
    bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=str(a.source)); body=max([o for o in bpy.context.scene.objects if o.type=='MESH'],key=lambda o:len(o.data.vertices))
    coords=np.empty((len(body.data.vertices),3),float); body.data.vertices.foreach_get('co',coords.ravel()); mw=np.asarray(body.matrix_world,float); world=coords@mw[:3,:3].T+mw[:3,3]
    lo=pv.min(0); hi=pv.max(0); pad=np.maximum((hi-lo)*0.15,1e-4); lo-=pad; hi+=pad
    cv=np.array([[x,y,z] for x in (lo[0],hi[0]) for y in (lo[1],hi[1]) for z in (lo[2],hi[2])],float)
    cf=np.array([[0,1,3,2],[4,6,7,5],[0,4,5,1],[2,3,7,6],[0,2,6,4],[1,5,7,3]],np.int32)
    me=bpy.data.meshes.new('temporary_face_cage_mesh'); me.from_pydata(cv.tolist(),[],cf.tolist()); cage=bpy.data.objects.new('temporary_face_cage',me); bpy.context.collection.objects.link(cage)
    vg=body.vertex_groups.new(name='landmark105_patch'); vg.add(oi.tolist(),1.0,'REPLACE')
    mod=body.modifiers.new('native_mesh_deform_test','MESH_DEFORM'); mod.object=cage; mod.vertex_group=vg.name; mod.precision=3; mod.use_dynamic_bind=False
    bpy.context.view_layer.objects.active=body; body.select_set(True); cage.select_set(False)
    bind_error=None
    try:
        bpy.ops.object.meshdeform_bind(modifier=mod.name)
    except Exception as e: bind_error=repr(e)
    result={'method':'Blender native Mesh Deform modifier with automatically bounded closed box cage','source':str(a.source),'patchVertices':int(len(oi)),'requestedDisplacement':requested.tolist(),'requestedMagnitude':float(np.linalg.norm(requested)),'bindError':bind_error,'bindState':bool(mod.is_bound),'runtimeSeconds':None}
    if not mod.is_bound:
        result['status']='FAILED_BIND'; a.report.parent.mkdir(parents=True,exist_ok=True); a.report.write_text(json.dumps(result,indent=2)+'\n'); print(json.dumps(result,indent=2)); return
    # Whole cage translation is a deliberate control: it tests native binding
    # and exposes the boundary seam without inventing a cage solver.
    cage.location += Vector(tuple(requested)); bpy.context.view_layer.update()
    solved=np.empty((len(body.data.vertices),3),float); body.data.vertices.foreach_get('co',solved.ravel()); solved=solved@mw[:3,:3].T+mw[:3,3]
    achieved=(bary[:,None]*solved[oi[tri]]).sum(0); err=float(np.linalg.norm((achieved-neutral)-requested)); req=float(np.linalg.norm(requested))
    base=world[oi]; new=solved[oi]
    # Patch-only orientation and strain checks after modifier evaluation.
    npz=np.load(a.patch); f=npz['F'].astype(np.int32); bn=np.cross(base[f[:,1]]-base[f[:,0]],base[f[:,2]]-base[f[:,0]]); nn=np.cross(new[f[:,1]]-new[f[:,0]],new[f[:,2]]-new[f[:,0]]); dots=np.einsum('ij,ij->i',bn,nn); area=np.linalg.norm(nn,axis=1); ba=np.linalg.norm(bn,axis=1); fold=int(np.sum(dots<0)); collapse=int(np.sum(area<=ba*1e-4)); ed=np.unique(np.sort(np.vstack((f[:,[0,1]],f[:,[1,2]],f[:,[2,0]])),axis=1),axis=0); bl=np.linalg.norm(base[ed[:,0]]-base[ed[:,1]],axis=1); nl=np.linalg.norm(new[ed[:,0]]-new[ed[:,1]],axis=1); strain=np.abs(nl/np.maximum(bl,1e-20)-1)
    result.update({'status':'EVALUATED','achievedDisplacement':(achieved-neutral).tolist(),'targetError':err,'targetErrorPercent':100*err/max(req,1e-20),'foldovers':fold,'collapsedTriangles':collapse,'maxEdgeStrain':float(np.max(strain)),'p95EdgeStrain':float(np.percentile(strain,95)),'boundarySeamDisplacement':float(np.max(np.linalg.norm(solved[oi]-world[oi],axis=1))),'selfIntersections':'NOT_TESTED_BY_THIS_STAGE','runtimeSeconds':time.perf_counter()-start})
    bpy.ops.object.modifier_apply(modifier=mod.name); cage.hide_render=True
    body.shape_key_add(name='Basis',from_mix=False); key=body.shape_key_add(name='landmark105_mesh_deform',from_mix=False); local=(solved-np.asarray(body.matrix_world)[:3,3])@np.linalg.inv(np.asarray(body.matrix_world)[:3,:3]).T; key.data.foreach_set('co',local.astype(np.float32).ravel()); key.value=0.0
    bpy.ops.object.select_all(action='DESELECT'); body.select_set(True); bpy.context.view_layer.objects.active=body; a.output.parent.mkdir(parents=True,exist_ok=True); bpy.ops.export_scene.gltf(filepath=str(a.output),export_format='GLB',export_morph=True,export_apply=False); result['output']=str(a.output); a.report.parent.mkdir(parents=True,exist_ok=True); a.report.write_text(json.dumps(result,indent=2)+'\n'); print(json.dumps(result,indent=2))

if __name__=='__main__': main()
