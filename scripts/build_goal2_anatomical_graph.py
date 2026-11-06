"""Build conservative model-derived seam ties without changing the source GLB."""
import json,sys
from pathlib import Path
import bpy,numpy as np

def arg(n):
    a=sys.argv[sys.argv.index('--')+1:]; return Path(a[a.index(n)+1]).resolve()

def main():
    glb,problem,goal1,out=arg('--glb'),arg('--problem'),arg('--goal1'),arg('--output')
    z=np.load(problem); pairs=z['duplicate_pairs'] if 'duplicate_pairs' in z.files else np.empty((0,2),int)
    ray=json.loads(goal1.read_text()); rec={int(r['index']):r for r in ray['records'] if r.get('meshXYZ')}; target={i:np.asarray(rec[i]['meshXYZ'],float) for i in rec}; eye=float(np.linalg.norm(target[33]-target[263]));
    groups={'brow':[70,63,105,336,293,334],'eyelid':[159,145,386,374],'eye':[33,133,263,362],'nose':[168,6,1,98,327],'mouth':[61,291,13,14],'jaw':[152,234,454]}; centers={k:np.mean([target[i] for i in v if i in target],axis=0) for k,v in groups.items()}
    bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=str(glb)); body=max([o for o in bpy.context.scene.objects if o.type=='MESH'],key=lambda o:len(o.data.vertices)); n=len(body.data.vertices); local=np.empty((n,3),float); body.data.vertices.foreach_get('co',local.ravel()); mw=np.asarray(body.matrix_world,float); world=local@mw[:3,:3].T+mw[:3,3]; normals=np.empty((n,3),float); body.data.vertices.foreach_get('normal',normals.ravel()); normals=normals@mw[:3,:3]; normals/=np.maximum(np.linalg.norm(normals,axis=1,keepdims=True),1e-12); local_ids=np.asarray(z['local_indices'],int); w=world[local_ids]; vn=normals[local_ids]
    def region(p):
        d={k:float(np.linalg.norm(p-c)/eye) for k,c in centers.items()}; return min(d,key=d.get),min(d.values())
    accepted=[]; rejected=[]; counts={}
    for u,v in pairs:
        ru,du=region(w[u]); rv,dv=region(w[v]); nd=float(np.dot(vn[u],vn[v])); key='accepted'
        if du>2.25 or dv>2.25: key='outside_face_envelope'
        elif ru!=rv: key='region_mismatch'
        elif nd<.985: key='normal_mismatch'
        if key=='accepted': accepted.append((int(u),int(v)))
        else: rejected.append({'pair':[int(u),int(v)],'reason':key,'regions':[ru,rv],'normalDot':nd,'normalizedDistances':[du,dv]})
        counts[key]=counts.get(key,0)+1
    out.parent.mkdir(parents=True,exist_ok=True); np.savez_compressed(out.with_suffix('.npz'),accepted_pairs=np.asarray(accepted,dtype=int),local_indices=local_ids); out.write_text(json.dumps({'glb':str(glb),'problem':str(problem),'acceptedPairs':len(accepted),'rejectedPairs':len(rejected),'rejectionCounts':counts,'regions':groups,'method':'coincident position + transformed normal dot >= .985 + landmark-derived region agreement + 2.25 interocular envelope','rejected':rejected[:1000]},indent=2)+'\n')
if __name__=='__main__': main()
