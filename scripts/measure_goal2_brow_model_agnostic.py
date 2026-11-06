"""Measure Goal-2 brow motion from an exported target and its Goal-1 manifest."""
import json, sys
from pathlib import Path
import bpy, numpy as np

def arg(name):
    a=sys.argv[sys.argv.index('--')+1:]
    return Path(a[a.index(name)+1]).resolve()

def main():
    glb, goal1, out = arg('--glb'), arg('--goal1'), arg('--report')
    ray=json.loads(goal1.read_text()); rec={int(r['index']):r for r in ray['records'] if r.get('frontSurface') and r.get('meshXYZ')}
    groups={'brows':[70,63,105,336,293,334],'eyelids':[159,145,386,374],'eyes':[33,133,263,362],'nose':[168,6,1,98,327],'cheeks':[234,454],'chin':[152],'skull':[10,127,356]}
    bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=str(glb))
    body=max([o for o in bpy.context.scene.objects if o.type=='MESH'],key=lambda o:len(o.data.vertices)); keys=body.data.shape_keys.key_blocks if body.data.shape_keys else []
    key=next((k for k in keys if k.name=='xfer_browInnerUp_model_agnostic'),None)
    if key is None: raise SystemExit('model-agnostic shape key missing after reimport')
    base=np.empty((len(body.data.vertices),3),float); posed=np.empty_like(base); body.data.vertices.foreach_get('co',base.ravel()); key.data.foreach_get('co',posed.ravel())
    mw=np.asarray(body.matrix_world,float); delta=(posed-base)@mw[:3,:3].T
    def point(i):
        r=rec[i]; ids=np.asarray(r['triangleVertexIndices'],int); b=np.asarray(r['barycentricCoordinates'],float); return (delta[ids]*b[:,None]).sum(0)
    per={str(i):{'magnitudeMillimeters':float(np.linalg.norm(point(i))*1000),'deltaMillimeters':(point(i)*1000).tolist()} for i in sum(groups.values(),[]) if i in rec}
    regional={}
    for name,ids in groups.items():
        vals=[np.linalg.norm(point(i))*1000 for i in ids if i in rec]
        regional[name]={'landmarks':len(vals),'maxMillimeters':float(max(vals)) if vals else None,'p95Millimeters':float(np.percentile(vals,95)) if vals else None,'medianMillimeters':float(np.median(vals)) if vals else None}
    out.parent.mkdir(parents=True,exist_ok=True); out.write_text(json.dumps({'glb':str(glb),'shapeKey':key.name,'regions':regional,'landmarkDisplacements':per},indent=2)+'\n'); print(json.dumps({'regions':regional},indent=2))
if __name__=='__main__': main()
