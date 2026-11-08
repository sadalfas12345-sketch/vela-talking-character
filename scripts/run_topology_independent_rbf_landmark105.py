"""Topology-independent RBF test for the original Tripo mesh and landmark 105."""
import argparse, json, time, sys
from pathlib import Path
import bpy, numpy as np

def load_args():
    p=argparse.ArgumentParser()
    for n in ('source','goal','markers','patch','output','report'):
        p.add_argument('--'+n, type=Path, required=True)
    return p.parse_args(sys.argv[sys.argv.index('--')+1:])

def edges(f):
    return np.unique(np.sort(np.vstack((f[:,[0,1]],f[:,[1,2]],f[:,[2,0]])),axis=1),axis=0)

def rbf_fit_eval(controls, values, samples):
    # Thin-plate RBF with affine polynomial tail, equivalent to the exact
    # interpolating branch used here but implemented with Blender's NumPy.
    d=np.linalg.norm(controls[:,None,:]-controls[None,:,:],axis=2)
    K=d*d*np.log(np.maximum(d,1e-30)); K[d==0]=0.0
    P=np.column_stack((np.ones(len(controls)),controls))
    A=np.block([[K,P],[P.T,np.zeros((4,4))]])
    rhs=np.vstack((values,np.zeros((4,3))))
    coeff=np.linalg.lstsq(A,rhs,rcond=1e-12)[0]
    ds=np.linalg.norm(samples[:,None,:]-controls[None,:,:],axis=2)
    Ks=ds*ds*np.log(np.maximum(ds,1e-30)); Ks[ds==0]=0.0
    Ps=np.column_stack((np.ones(len(samples)),samples))
    return Ks@coeff[:len(controls)]+Ps@coeff[len(controls):]

def main():
    a=load_args(); t0=time.perf_counter()
    goal=json.loads(a.goal.read_text()); records={int(x['index']):x for x in goal['records']}
    markers=json.loads(a.markers.read_text())
    patch=np.load(a.patch); pv=patch['V'].astype(float); pf=patch['F'].astype(np.int32); oi=patch['originalIndices'].astype(np.int64)
    lookup={int(x):i for i,x in enumerate(oi)}; rec=records[105]
    tri=np.asarray([lookup[int(x)] for x in rec['triangleVertexIndices']],dtype=np.int32); bary=np.asarray(rec['barycentricCoordinates'],float)
    neutral_lm=(bary[:,None]*pv[tri]).sum(axis=0); peak=np.asarray(markers['samples']['100'])[105]; requested=peak-np.asarray(markers['neutral'])[105]
    target=neutral_lm+requested
    # Boundary vertices are stationary physical controls. Subsample deterministically.
    counts={}
    for face in pf:
        for x,y in ((face[0],face[1]),(face[1],face[2]),(face[2],face[0])):
            e=tuple(sorted((int(x),int(y)))); counts[e]=counts.get(e,0)+1
    boundary=np.asarray(sorted({x for e,c in counts.items() if c==1 for x in e}),dtype=np.int32)
    step=max(1,len(boundary)//96); boundary=boundary[::step]
    control_x=np.vstack((neutral_lm[None,:],pv[boundary]))
    control_d=np.vstack((requested[None,:],np.zeros((len(boundary),3))))
    # A thin-plate RBF is affine-compatible and exact at all controls.
    delta_patch=rbf_fit_eval(control_x,control_d,pv)
    # Keep the deformation on the connected anatomical component only.
    bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=str(a.source))
    body=max([o for o in bpy.context.scene.objects if o.type=='MESH'],key=lambda o:len(o.data.vertices))
    coords=np.empty((len(body.data.vertices),3),float); body.data.vertices.foreach_get('co',coords.ravel())
    mw=np.asarray(body.matrix_world,float); world=coords@mw[:3,:3].T+mw[:3,3]
    before=world.copy(); world[oi]=pv+delta_patch
    achieved=(bary[:,None]*world[oi[tri]]).sum(axis=0); err=float(np.linalg.norm(achieved-target)); req=float(np.linalg.norm(requested))
    # Geometry checks on affected component.
    base_n=np.cross(pv[pf[:,1]]-pv[pf[:,0]],pv[pf[:,2]]-pv[pf[:,0]])
    newp=world[oi]; new_n=np.cross(newp[pf[:,1]]-newp[pf[:,0]],newp[pf[:,2]]-newp[pf[:,0]])
    base_a=np.linalg.norm(base_n,axis=1); new_a=np.linalg.norm(new_n,axis=1); dots=np.einsum('ij,ij->i',base_n,new_n)
    fold=np.flatnonzero(dots<0); collapse=np.flatnonzero(new_a<=base_a*1e-4)
    ee=edges(pf); bl=np.linalg.norm(pv[ee[:,0]]-pv[ee[:,1]],axis=1); nl=np.linalg.norm(newp[ee[:,0]]-newp[ee[:,1]],axis=1); strain=np.abs(nl/np.maximum(bl,1e-20)-1)
    # Genuine seam duplicates in this patch must have identical delta.
    buckets={}
    for i,q in enumerate(np.round(pv/1e-8).astype(np.int64)): buckets.setdefault(tuple(q),[]).append(i)
    seam_gap=max((float(np.max(np.linalg.norm(delta_patch[x]-delta_patch[y],axis=1))) for x in buckets.values() if len(x)>1 for y in [x]),default=0.0)
    body.shape_key_add(name='Basis',from_mix=False); key=body.shape_key_add(name='landmark105_rbf',from_mix=False)
    local=(world-mw[:3,3])@np.linalg.inv(mw[:3,:3]).T; key.data.foreach_set('co',local.astype(np.float32).ravel()); key.value=0.0
    bpy.ops.object.select_all(action='DESELECT'); body.select_set(True); bpy.context.view_layer.objects.active=body
    a.output.parent.mkdir(parents=True,exist_ok=True); bpy.ops.export_scene.gltf(filepath=str(a.output),export_format='GLB',export_morph=True,export_apply=False)
    report={'method':'exact thin-plate RBF interpolant with affine tail, implemented in NumPy, with barycentric landmark control plus stationary patch boundary controls','source':str(a.source),'patchVertices':int(len(pv)),'boundaryControls':int(len(boundary)),'landmarkId':105,'neutralLandmark':neutral_lm.tolist(),'requestedDisplacement':requested.tolist(),'requestedMagnitude':req,'achievedDisplacement':(achieved-neutral_lm).tolist(),'targetError':err,'targetErrorPercent':100*err/max(req,1e-20),'foldovers':int(len(fold)),'collapsedTriangles':int(len(collapse)),'maxEdgeStrain':float(np.max(strain)),'p95EdgeStrain':float(np.percentile(strain,95)),'minAreaRatio':float(np.min(new_a/np.maximum(base_a,1e-20))),'finite':bool(np.isfinite(world).all()),'seamDisplacementDisagreement':seam_gap,'selfIntersections':'NOT_TESTED_BY_THIS_STAGE','runtimeSeconds':time.perf_counter()-t0,'output':str(a.output)}
    a.report.parent.mkdir(parents=True,exist_ok=True); a.report.write_text(json.dumps(report,indent=2)+'\n'); print(json.dumps(report,indent=2))

if __name__=='__main__': main()
