"""Smallest direct original-render-mesh brow deformation test."""
import json,sys
from pathlib import Path
import bpy,numpy as np

def arg(name):
    a=sys.argv[sys.argv.index('--')+1:]; return Path(a[a.index(name)+1]).resolve()

def main():
    src,goal1,out,report=arg('--source'),arg('--goal1'),arg('--output'),arg('--report')
    key_name='direct_browInnerUp_test'
    ray=json.loads(goal1.read_text()); rec={int(x['index']):x for x in ray['records'] if x.get('meshXYZ')}
    lm={i:np.asarray(rec[i]['meshXYZ'],float) for i in rec}
    eye_mid=(lm[33]+lm[263])*.5; eye_width=float(np.linalg.norm(lm[33]-lm[263])); chin=lm[152]
    up=eye_mid-chin; up/=max(np.linalg.norm(up),1e-12)
    forward=lm[1]-eye_mid; forward/=max(np.linalg.norm(forward),1e-12)
    brow_ids=[70,63,105,336,293,334]; brow=np.asarray([lm[i] for i in brow_ids]); center=brow.mean(0)
    bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=str(src))
    body=max([o for o in bpy.context.scene.objects if o.type=='MESH'],key=lambda o:len(o.data.vertices)); n=len(body.data.vertices)
    local=np.empty((n,3),float); body.data.vertices.foreach_get('co',local.ravel()); mw=np.asarray(body.matrix_world,float); world=local@mw[:3,:3].T+mw[:3,3]
    # Normalized, connected forehead field. The lower mask suppresses eyelids and eyes.
    d=np.min(np.linalg.norm(world[:,None,:]-brow[None,:,:],axis=2),axis=1)
    eyelid=np.asarray([lm[i] for i in [159,145,386,374]])
    de=np.min(np.linalg.norm(world[:,None,:]-eyelid[None,:,:],axis=2),axis=1)
    vertical=(world-center)@up; front=(world-center)@forward
    radius=2.35*eye_width
    radial=np.clip(1-(d/max(radius,1e-12))**2,0,1)**2
    upper=np.clip((vertical+.25*eye_width)/(.75*eye_width),0,1)
    eye_guard=np.clip((de-.08*eye_width)/(.22*eye_width),0,1)
    w=radial*upper*eye_guard
    w[(d>radius)|(front<-.35*eye_width)]=0
    # Coincident render vertices share one displacement exactly.
    buckets={}
    for i,p in enumerate(np.round(world/1e-7).astype(np.int64)): buckets.setdefault(tuple(p),[]).append(i)
    for ids in buckets.values():
        if len(ids)>1:
            val=float(np.mean(w[ids])); w[ids]=val
    base=world.copy(); body.data.calc_loop_triangles(); faces=np.asarray([p.vertices[:] for p in body.data.loop_triangles],int); b=base[faces]
    updisp=up[None,:]*w[:,None]
    def measure(a):
        x=base+a*updisp; tri=x[faces]; nb=np.cross(b[:,1]-b[:,0],b[:,2]-b[:,0]); nn=np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]); area=np.linalg.norm(nn,axis=1); dot=np.einsum('ij,ij->i',nb,nn); base_area=np.linalg.norm(nb,axis=1); return {'inversions':int(np.sum(dot<0)),'collapsed':int(np.sum(area<base_area*1e-4)),'zeroArea':int(np.sum(area<=1e-12)),'minAreaRatio':float(np.min(area/np.maximum(base_area,1e-12)))}
    requested=.001; chosen=requested
    for _ in range(30):
        if all(measure(chosen*a)['inversions']==0 and measure(chosen*a)['collapsed']==0 for a in [0.25,0.5,0.75,1]): break
        chosen*=.5
    delta_world=chosen*updisp; target_local=(base+delta_world-mw[:3,3])@np.linalg.inv(mw[:3,:3]).T
    body.shape_key_add(name='Basis',from_mix=False); key=body.shape_key_add(name=key_name,from_mix=False); key.data.foreach_set('co',target_local.astype(np.float32).ravel()); key.value=0; body.data.shape_keys.use_relative=True
    bpy.ops.object.select_all(action='DESELECT'); [o.select_set(True) for o in bpy.context.scene.objects if o.type in {'MESH','ARMATURE','EMPTY'}]; bpy.context.view_layer.objects.active=body
    out.parent.mkdir(parents=True,exist_ok=True); bpy.ops.export_scene.gltf(filepath=str(out),export_format='GLB',export_morph=True,export_skins=True,export_animations=True,export_apply=False)
    report.parent.mkdir(parents=True,exist_ok=True); report.write_text(json.dumps({'source':str(src),'shapeKey':key_name,'eyeWidth':eye_width,'upAxis':up.tolist(),'browLandmarks':brow_ids,'candidateMovedVertices':int(np.sum(w>0)),'requestedBrowDisplacementMeters':requested,'chosenBrowDisplacementMeters':chosen,'achievedWeightedMeanMeters':float(np.average(chosen*w,weights=np.maximum(w,1e-12))),'weights':{str(a):measure(chosen*a) for a in [0,.25,.5,.75,1]},'neutralTopologyTriangleCount':len(faces),'neutralVertexCount':n},indent=2)+'\n')
if __name__=='__main__': main()
