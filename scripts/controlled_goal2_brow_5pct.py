"""Controlled Goal-2 test: prescribe 5% interocular upward brow motion."""
import json,sys
from pathlib import Path
import bpy,numpy as np

ROOT=Path(__file__).resolve().parents[1]; BROW=[70,63,105,336,293,334]; ANCHORS=[159,145,386,374,33,133,263,362,168,6,1,98,327,234,454,152,10,127,356]
def arg(n):
 a=sys.argv[sys.argv.index('--')+1:]; return Path(a[a.index(n)+1]).resolve()
def main():
 source,goal1,camera,output,report=arg('--source'),arg('--goal1'),arg('--camera'),arg('--output'),arg('--report'); ray=json.loads(goal1.read_text()); rec={int(r['index']):r for r in ray['records'] if r.get('frontSurface') and r.get('meshXYZ')}; cam=json.loads(camera.read_text()); up=np.asarray(cam['cameraBasis']['up'],float); up/=np.linalg.norm(up)
 bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=str(source)); body=max([o for o in bpy.context.scene.objects if o.type=='MESH'],key=lambda o:len(o.data.vertices)); n=len(body.data.vertices); local=np.empty((n,3),float); body.data.vertices.foreach_get('co',local.ravel()); mw=np.asarray(body.matrix_world,float); world=local@mw[:3,:3].T+mw[:3,3]; target={i:np.asarray(rec[i]['meshXYZ'],float) for i in rec}; eye=float(np.linalg.norm(target[33]-target[263])); requested=.05*eye*up
 center=np.mean([target[i] for i in BROW],axis=0); radius=float(np.linalg.norm(center-target[152]))*.5; handles=np.asarray([target[i] for i in BROW+ANCHORS]); candidate=np.flatnonzero(np.min(np.linalg.norm(world[:,None]-handles[None],axis=2),axis=1)<=radius); mask=np.zeros(n,bool); mask[candidate]=1; tris=np.asarray([[v for v in p.vertices] for p in body.data.polygons],int); edge=np.concatenate([tris[:,[0,1]],tris[:,[1,2]],tris[:,[2,0]]]); edge=edge[mask[edge[:,0]]&mask[edge[:,1]]]
 delta=np.zeros((n,3)); constraints=[]
 for i in BROW+ANCHORS:
  r=rec[i]; vi=np.asarray(r['triangleVertexIndices'],int); b=np.asarray(r['barycentricCoordinates'],float); desired=requested if i in BROW else np.zeros(3); constraints.append((vi,b,desired)); delta[vi]+=b[:,None]*desired/max(float((b*b).sum()),1e-12)
 def enforce():
  for vi,b,d in constraints:
   delta[vi]+=b[:,None]*(d-(b[:,None]*delta[vi]).sum(0))/max(float((b*b).sum()),1e-12)
 enforce(); degree=np.zeros(n); np.add.at(degree,edge[:,0],1); np.add.at(degree,edge[:,1],1)
 for _ in range(24):
  total=np.zeros_like(delta); np.add.at(total,edge[:,0],delta[edge[:,1]]); np.add.at(total,edge[:,1],delta[edge[:,0]]); delta[candidate]=.65*delta[candidate]+.35*total[candidate]/np.maximum(degree[candidate,None],1); enforce()
 def stage():
  vals=[np.linalg.norm((b[:,None]*delta[vi]).sum(0)) for i in BROW for vi,b,d in constraints if i in []]; return [float(np.linalg.norm((b[:,None]*delta[vi]).sum(0))*1000) for vi,b,d in constraints[:len(BROW)]]
 before=stage(); base_tri=world[tris]; base_norm=np.cross(base_tri[:,1]-base_tri[:,0],base_tri[:,2]-base_tri[:,0]); factors=np.ones(n); inv_iters=0
 for _ in range(24):
  posed=(world+delta*factors[:,None])[tris]; norm=np.cross(posed[:,1]-posed[:,0],posed[:,2]-posed[:,0]); bad=np.einsum('ij,ij->i',base_norm,norm)<0
  if not bad.any(): break
  factors[np.unique(tris[bad].ravel())]*=.5; inv_iters+=1
 delta*=factors[:,None]; corrected=stage(); enforce(); after_enforce=stage(); posed=(world+delta)[tris]; norm=np.cross(posed[:,1]-posed[:,0],posed[:,2]-posed[:,0]); inversions=int(np.count_nonzero(np.einsum('ij,ij->i',base_norm,norm)<0))
 local_delta=delta@np.linalg.inv(mw[:3,:3]).T; body.shape_key_add(name='Basis',from_mix=False); key=body.shape_key_add(name='controlled_brow_5pct',from_mix=False); key.data.foreach_set('co',(local+local_delta).astype(np.float32).ravel()); key.value=0; body.data.shape_keys.use_relative=True
 bpy.ops.object.select_all(action='DESELECT'); [o.select_set(True) for o in bpy.context.scene.objects if o.type in {'MESH','ARMATURE','EMPTY'}]; bpy.context.view_layer.objects.active=body; output.parent.mkdir(parents=True,exist_ok=True); bpy.ops.export_scene.gltf(filepath=str(output),export_format='GLB',export_morph=True,export_skins=True,export_animations=True,export_apply=False)
 result={'architecture':'controlled 5% anatomical-up constrained surface test','shapeKey':key.name,'eyeWidthMillimeters':eye*1000,'requestedMillimeters':float(np.linalg.norm(requested)*1000),'requestedVector':(requested*1000).tolist(),'browBeforeCorrectionMillimeters':before,'browAfterInversionCorrectionMillimeters':corrected,'browAfterHardConstraintReenforcementMillimeters':after_enforce,'inversionsBeforeExport':inversions,'inversionProjectionIterations':inv_iters,'minimumLocalFactor':float(factors.min()),'output':str(output)}; report.parent.mkdir(parents=True,exist_ok=True); report.write_text(json.dumps(result,indent=2)+'\n'); print(json.dumps(result,indent=2))
if __name__=='__main__': main()
