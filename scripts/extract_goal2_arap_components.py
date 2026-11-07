"""Extract the existing Goal-2 local-proxy components without modifying GLBs."""
import json, sys
from pathlib import Path
from collections import defaultdict
import bpy, numpy as np

CONTROL_IDS=[70,63,105,336,293,334,159,145,386,374,33,133,263,362,168,6,1,98,327,234,454,152,10,127,356]
def arg(name):
    a=sys.argv[sys.argv.index('--')+1:]; return Path(a[a.index(name)+1]).resolve()
def components(n,faces):
    p=list(range(n))
    def f(x):
        while p[x]!=x:p[x]=p[p[x]];x=p[x]
        return x
    def u(a,b):
        a,b=f(a),f(b)
        if a!=b:p[b]=a
    for t in faces:u(*t[:2]);u(*t[1:]);u(t[0],t[2])
    d=defaultdict(list)
    for i in range(n):d[f(i)].append(i)
    return list(d.values())
def main():
    source,goal,out=arg('--source'),arg('--goal1'),arg('--output')
    j=json.loads(goal.read_text());rec={int(x['index']):x for x in j['records'] if x.get('meshXYZ') is not None}
    bpy.ops.wm.read_factory_settings(use_empty=True);bpy.ops.import_scene.gltf(filepath=str(source))
    body=max([o for o in bpy.context.scene.objects if o.type=='MESH'],key=lambda o:len(o.data.vertices))
    local=np.empty((len(body.data.vertices),3),float);body.data.vertices.foreach_get('co',local.ravel());m=np.asarray(body.matrix_world,float);world=local@m[:3,:3].T+m[:3,3]
    target=np.asarray([rec[i]['meshXYZ'] for i in range(468)]);center=np.mean(target[[33,263,1,152]],axis=0);radius=float(np.max(np.linalg.norm(target-center,axis=1))*1.20);dist=np.linalg.norm(world-center,axis=1)
    raw=[];seen=set()
    for poly in body.data.polygons:
        pv=[int(v) for v in poly.vertices]
        if any(dist[v]<=radius for v in pv):
            for k in range(1,len(pv)-1):
                t=(pv[0],pv[k],pv[k+1]);key=tuple(sorted(t));area=np.linalg.norm(np.cross(world[t[1]]-world[t[0]],world[t[2]]-world[t[0]]))
                if key not in seen and area>max(radius*radius*1e-12,1e-18):seen.add(key);raw.append(t)
    original=sorted({v for t in raw for v in t});lookup={v:i for i,v in enumerate(original)};faces=[tuple(lookup[v] for v in t) for t in raw];comps=components(len(original),faces);out.parent.mkdir(parents=True,exist_ok=True)
    for number in [30,1]:
        members=sorted(comps[number]);ms=set(members);clook={v:i for i,v in enumerate(members)};cf=[tuple(clook[v] for v in t) for t in faces if all(v in ms for v in t)];coords=world[np.asarray([original[i] for i in members])]
        np.savez_compressed(out.parent/f'female-component-{number}.npz',V=coords,F=np.asarray(cf,dtype=np.int64),originalIndices=np.asarray([original[i] for i in members],dtype=np.int64))
        print(number,len(coords),len(cf))
    out.write_text(json.dumps({'source':str(source),'proxyVertices':len(original),'proxyTriangles':len(faces),'components':[{'component':n,'vertices':int(np.load(out.parent/f'female-component-{n}.npz')['V'].shape[0]),'triangles':int(np.load(out.parent/f'female-component-{n}.npz')['F'].shape[0])} for n in [30,1]],'worldSpace':True},indent=2)+'\n')
if __name__=='__main__':main()
