"""Apply normalized landmark targets to the original render mesh with smooth RBF interpolation."""
import argparse,json,sys
from pathlib import Path
import bpy,numpy as np
def main():
 p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--goal1',type=Path,required=True);p.add_argument('--targets',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--report',type=Path,required=True);a=p.parse_args(sys.argv[sys.argv.index('--')+1:])
 ray=json.loads(a.goal1.read_text());rec={int(x['index']):x for x in ray['records'] if x.get('meshXYZ')};lm={i:np.asarray(rec[i]['meshXYZ'],float) for i in rec}; td=json.loads(a.targets.read_text());brow=[70,63,105,336,293,334];
 stable=[159,145,386,374,33,263,1,152]; pts=np.asarray([lm[i] for i in brow+stable]); deltas=np.asarray([np.asarray(td['landmarkTargets'][str(i)])-lm[i] for i in brow]+[np.zeros(3) for _ in stable]); eye=float(td['interocularDistance']);
 bpy.ops.wm.read_factory_settings(use_empty=True);bpy.ops.import_scene.gltf(filepath=str(a.source));body=max([o for o in bpy.context.scene.objects if o.type=='MESH'],key=lambda o:len(o.data.vertices));n=len(body.data.vertices);local=np.empty((n,3),float);body.data.vertices.foreach_get('co',local.ravel());mw=np.asarray(body.matrix_world,float);world=local@mw[:3,:3].T+mw[:3,3];bc=pts[:len(brow)].mean(0);d=np.min(np.linalg.norm(world[:,None,:]-pts[:len(brow)][None,:,:],axis=2),axis=1);front=(world-bc)@(lm[1]-((lm[33]+lm[263])*.5));front/=max(np.linalg.norm(lm[1]-((lm[33]+lm[263])*.5)),1e-12);rad=2.25*eye;support=np.clip(1-(d/max(rad,1e-12))**2,0,1)**2
 sigma=.70*eye;dist2=np.sum((world[:,None,:]-pts[None,:,:])**2,axis=2);ww=np.exp(-dist2/(2*sigma*sigma));delta=(ww@deltas)/np.maximum(ww.sum(1)[:,None],1e-12)*support[:,None];delta[(d>rad)|(front<-.5*eye)]=0
 buckets={}
 for i,q in enumerate(np.round(world/1e-7).astype(np.int64)):buckets.setdefault(tuple(q),[]).append(i)
 for ids in buckets.values():
  if len(ids)>1:delta[ids]=delta[ids].mean(0)
 body.data.calc_loop_triangles();faces=np.asarray([x.vertices[:] for x in body.data.loop_triangles],int);base=world.copy();b=base[faces];
 def measure(s):
  x=base+s*delta;tri=x[faces];nb=np.cross(b[:,1]-b[:,0],b[:,2]-b[:,0]);nn=np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]);area=np.linalg.norm(nn,axis=1);ba=np.linalg.norm(nb,axis=1);return {'inversions':int(np.sum(np.einsum('ij,ij->i',nb,nn)<0)),'collapsed':int(np.sum(area<ba*1e-4)),'minAreaRatio':float(np.min(area/np.maximum(ba,1e-12)))}
 amp=1.;
 for _ in range(30):
  if all(measure(amp*x)['inversions']==0 and measure(amp*x)['collapsed']==0 for x in [.25,.5,.75,1]):break
  amp*=.5
 target=base+amp*delta;target_local=(target-mw[:3,3])@np.linalg.inv(mw[:3,:3]).T;body.shape_key_add(name='Basis',from_mix=False);key=body.shape_key_add(name='normalized_browInnerUp_test',from_mix=False);key.data.foreach_set('co',target_local.astype(np.float32).ravel());key.value=0;body.data.shape_keys.use_relative=True;bpy.ops.object.select_all(action='DESELECT');[o.select_set(True) for o in bpy.context.scene.objects if o.type in {'MESH','ARMATURE','EMPTY'}];bpy.context.view_layer.objects.active=body;a.output.parent.mkdir(parents=True,exist_ok=True);bpy.ops.export_scene.gltf(filepath=str(a.output),export_format='GLB',export_morph=True,export_skins=True,export_animations=True,export_apply=False)
 closest=np.asarray([np.argmin(np.linalg.norm(world-lm[i],axis=1)) for i in brow]);rep={'source':str(a.source),'targets':str(a.targets),'shapeKey':key.name,'backtrackedAmplitude':amp,'targetNormalizedBrowMotion':td['peakBrowMotionNorm'],'targetLandmarkDisplacementsMeters':{str(i):float(np.linalg.norm(deltas[k])) for k,i in enumerate(brow)},'achievedNearestVertexDisplacementsMeters':{str(i):float(np.linalg.norm(amp*delta[closest[k]])) for k,i in enumerate(brow)},'weights':{str(x):measure(amp*x) for x in [0,.25,.5,.75,1]}};a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text(json.dumps(rep,indent=2)+'\n')
if __name__=='__main__':main()
