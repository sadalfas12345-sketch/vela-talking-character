"""Extract a small connected original-mesh patch around existing landmark 336."""
import json, sys
from collections import defaultdict, deque
from pathlib import Path
import bpy, numpy as np

def arg(name):
    a=sys.argv[sys.argv.index('--')+1:]
    return Path(a[a.index(name)+1]).resolve()

def main():
    source, goal, out = arg('--source'), arg('--goal1'), arg('--output')
    hop_radius = int(sys.argv[sys.argv.index('--')+1:][sys.argv[sys.argv.index('--')+1:].index('--hop-radius')+1]) if '--hop-radius' in sys.argv else 16
    report=json.loads(goal.read_text())
    records={int(x['index']):x for x in report['records']}
    rec=records[336]
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(source))
    body=max([o for o in bpy.context.scene.objects if o.type=='MESH'], key=lambda o:len(o.data.vertices))
    V=np.empty((len(body.data.vertices),3),float); body.data.vertices.foreach_get('co',V.ravel())
    mw=np.asarray(body.matrix_world,float); W=V@mw[:3,:3].T+mw[:3,3]
    seed_face=int(rec['triangleIndex'])
    if seed_face >= len(body.data.polygons): raise RuntimeError(f'seed face {seed_face} unavailable')
    faces=[tuple(int(v) for v in p.vertices) for p in body.data.polygons if len(p.vertices)==3]
    if seed_face >= len(faces): raise RuntimeError('mesh polygon indexing is not triangular')
    edge_faces=defaultdict(list)
    for fi,f in enumerate(faces):
        for a,b in ((f[0],f[1]),(f[1],f[2]),(f[2],f[0])): edge_faces[tuple(sorted((a,b)))].append(fi)
    adj=defaultdict(list)
    for fs in edge_faces.values():
        for a in fs:
            for b in fs:
                if a!=b: adj[a].append(b)
    chosen={seed_face}; q=deque([(seed_face,0)])
    while q:
        fi,depth=q.popleft()
        if depth>=hop_radius: continue
        for ni in adj[fi]:
            if ni not in chosen: chosen.add(ni); q.append((ni,depth+1))
    used=sorted({v for fi in chosen for v in faces[fi]}); lookup={v:i for i,v in enumerate(used)}
    F=np.asarray([[lookup[v] for v in faces[fi]] for fi in sorted(chosen)],dtype=np.int64)
    PV=W[np.asarray(used)]
    p=np.asarray(rec['meshXYZ'],float); moved=int(np.argmin(np.linalg.norm(PV-p,axis=1)))
    # Two stable controls are chosen geometrically from the same connected patch.
    d=np.linalg.norm(PV-PV[moved],axis=1); s1=int(np.argmax(d));
    line=PV[s1]-PV[moved]; ll=max(float(line@line),1e-20)
    s2=int(np.argmax([np.linalg.norm(x-PV[moved]-line*((x-PV[moved])@line)/ll) for x in PV]))
    eye=float(np.linalg.norm(np.asarray(records[33]['meshXYZ'])-np.asarray(records[263]['meshXYZ'])))
    root=Path(__file__).resolve().parents[1]
    manifest_path=root / 'verification' / 'goal2-browInnerUp-proof' / 'step4-tripo-transfer' / ('female' if 'vela-photoreal' in str(source) else 'male') / 'landmark_markers.json'
    markers=json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    up=np.asarray(markers.get('upAxis',[0,1,0]),float); up/=max(float(np.linalg.norm(up)),1e-20)
    out.parent.mkdir(parents=True,exist_ok=True)
    np.savez_compressed(out.with_suffix('.npz'),V=PV,F=F,originalIndices=np.asarray(used),moved=np.int64(moved),stationary=np.asarray([s1,s2],dtype=np.int64),seedPoint=p,eyeWidth=np.float64(eye),upAxis=up)
    out.write_text(json.dumps({'source':str(source),'meshObject':body.name,'seedLandmark':336,'seedTriangle':seed_face,'vertices':len(PV),'triangles':len(F),'movedLocalIndex':moved,'stationaryLocalIndices':[s1,s2],'eyeWidth':eye,'upAxis':up.tolist(),'hopRadius':hop_radius},indent=2)+'\n')
if __name__=='__main__': main()
