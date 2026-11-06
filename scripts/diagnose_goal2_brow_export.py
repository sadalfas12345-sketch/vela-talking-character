"""Diagnose exported brow transfer using spatial, not stale vertex-index, matches."""
import json, sys
from pathlib import Path
import bpy, numpy as np
from mathutils.kdtree import KDTree

def arg(n):
    a=sys.argv[sys.argv.index('--')+1:]; return Path(a[a.index(n)+1]).resolve()

def main():
    glb, manifest, camera, out = arg('--glb'), arg('--goal1'), arg('--camera'), arg('--report')
    ray=json.loads(manifest.read_text()); rec={int(r['index']):r for r in ray['records'] if r.get('meshXYZ')}
    groups={'brows':[70,63,105,336,293,334],'eyelids':[159,145,386,374],'eyes':[33,133,263,362],'nose':[168,6,1,98,327],'cheeks':[234,454],'chin':[152],'skull':[10,127,356]}
    bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=str(glb))
    body=max([o for o in bpy.context.scene.objects if o.type=='MESH'], key=lambda o:len(o.data.vertices))
    keys=body.data.shape_keys.key_blocks if body.data.shape_keys else []
    key=next((k for k in keys if k.name=='xfer_browInnerUp_model_agnostic'),None)
    if key is None: raise SystemExit('shape key not found')
    base=np.empty((len(body.data.vertices),3),float); posed=np.empty_like(base); body.data.vertices.foreach_get('co',base.ravel()); key.data.foreach_get('co',posed.ravel())
    mw=np.asarray(body.matrix_world,float); world=base@mw[:3,:3].T+mw[:3,3]; delta=(posed-base)@mw[:3,:3].T
    tree=KDTree(len(world))
    for i,p in enumerate(world): tree.insert(tuple(p),i)
    tree.balance(); up=np.asarray(json.loads(camera.read_text())['cameraBasis']['up'],float); up/=np.linalg.norm(up)
    rows=[]
    for group, ids in groups.items():
        for i in ids:
            if i not in rec: continue
            p=np.asarray(rec[i]['meshXYZ'],float); co,vi,dist=tree.find(tuple(p)); d=delta[vi]
            rows.append({'group':group,'landmark':i,'nearestVertex':int(vi),'nearestDistanceMillimeters':float(dist*1000),'deltaMillimeters':(d*1000).tolist(),'magnitudeMillimeters':float(np.linalg.norm(d)*1000),'upwardMillimeters':float(np.dot(d,up)*1000)})
    report={'glb':str(glb),'shapeKey':key.name,'spatiallyMatchedLandmarks':rows,'rawShapeKeyMaxMillimeters':float(np.linalg.norm(delta,axis=1).max()*1000),'rawShapeKeyP95Millimeters':float(np.percentile(np.linalg.norm(delta,axis=1),95)*1000)}
    out.parent.mkdir(parents=True,exist_ok=True); out.write_text(json.dumps(report,indent=2)+'\n'); print(json.dumps(report,indent=2))
if __name__=='__main__': main()
