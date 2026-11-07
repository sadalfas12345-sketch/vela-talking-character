"""Extract one connected original-surface patch around multiple Goal-1 landmarks."""
import json, sys
from collections import defaultdict, deque
from pathlib import Path
import bpy, numpy as np

def arg(name):
    a=sys.argv[sys.argv.index('--')+1:]
    return Path(a[a.index(name)+1]).resolve()

def main():
    source, goal, out = arg('--source'), arg('--goal1'), arg('--output')
    ids = [int(x) for x in sys.argv[sys.argv.index('--')+1:][sys.argv[sys.argv.index('--')+1:].index('--landmark-ids')+1].split(',')]
    hops = int(sys.argv[sys.argv.index('--')+1:][sys.argv[sys.argv.index('--')+1:].index('--hop-radius')+1])
    report=json.loads(goal.read_text()); records={int(x['index']):x for x in report['records']}
    bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=str(source))
    body=max([o for o in bpy.context.scene.objects if o.type=='MESH'],key=lambda o:len(o.data.vertices))
    V=np.empty((len(body.data.vertices),3),float); body.data.vertices.foreach_get('co',V.ravel()); mw=np.asarray(body.matrix_world,float); W=V@mw[:3,:3].T+mw[:3,3]
    faces=[]
    for p in body.data.polygons:
        pv=[int(v) for v in p.vertices]
        for k in range(1,len(pv)-1): faces.append((pv[0],pv[k],pv[k+1]))
    edge_faces=defaultdict(list)
    for fi,f in enumerate(faces):
        for a,b in ((f[0],f[1]),(f[1],f[2]),(f[2],f[0])): edge_faces[tuple(sorted((a,b)))].append(fi)
    adj=defaultdict(list)
    for fs in edge_faces.values():
        for a in fs:
            for b in fs:
                if a!=b: adj[a].append(b)
    chosen=set()
    for lid in ids:
        wanted=set(int(v) for v in records[lid]['triangleVertexIndices'])
        seed=next(i for i,f in enumerate(faces) if wanted.issubset(set(f)))
        q=deque([(seed,0)]); seen={seed}
        while q:
            fi,d=q.popleft(); chosen.add(fi)
            if d>=hops: continue
            for ni in adj[fi]:
                if ni not in seen: seen.add(ni); q.append((ni,d+1))
    used=sorted({v for fi in chosen for v in faces[fi]}); lookup={v:i for i,v in enumerate(used)}
    F=np.asarray([[lookup[v] for v in faces[fi]] for fi in sorted(chosen)],dtype=np.int64); PV=W[np.asarray(used)]
    eye=float(np.linalg.norm(np.asarray(records[33]['meshXYZ'])-np.asarray(records[263]['meshXYZ'])))
    out.parent.mkdir(parents=True,exist_ok=True); np.savez_compressed(out.with_suffix('.npz'),V=PV,F=F,originalIndices=np.asarray(used),eyeWidth=np.float64(eye),landmarkIds=np.asarray(ids,dtype=np.int32))
    out.write_text(json.dumps({'source':str(source),'meshObject':body.name,'landmarkIds':ids,'hopRadius':hops,'vertices':len(PV),'triangles':len(F),'triangleIndices':[int(records[i]['triangleIndex']) for i in ids]},indent=2)+'\n')
if __name__=='__main__': main()
