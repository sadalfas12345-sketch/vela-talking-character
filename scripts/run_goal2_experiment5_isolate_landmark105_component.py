"""Remove unrelated patch components and repeat the landmark-105 intensity test."""
from __future__ import annotations
import heapq, json, sys, time
from collections import defaultdict, deque
from pathlib import Path
import numpy as np

def arg(name):
    a=sys.argv[1:]; return Path(a[a.index(name)+1]).resolve()

def boundary(f):
    c=defaultdict(int)
    for t in f:
        for a,b in ((t[0],t[1]),(t[1],t[2]),(t[2],t[0])): c[tuple(sorted((int(a),int(b))))]+=1
    return np.asarray(sorted({x for e,n in c.items() if n==1 for x in e}),np.int32)

def component(f,seeds):
    a=defaultdict(set)
    for t in f:
        x,y,z=map(int,t); a[x]|={y,z}; a[y]|={x,z}; a[z]|={x,y}
    seen=set(map(int,seeds)); q=list(seen)
    while q:
        x=q.pop()
        for y in a[x]:
            if y not in seen: seen.add(y); q.append(y)
    return np.asarray(sorted(seen),np.int32)

def solve(v,f,b,tri,bary,target,bridge):
    A=np.zeros((1,len(v))); A[0,tri]=bary
    return bridge.solve(v,f,b,A,target[None,:],v.copy(),100,0.0,np.empty((0,3)))

def measure(v,f,u,b,tri,bary,neutral,req):
    n0=np.cross(v[f[:,1]]-v[f[:,0]],v[f[:,2]]-v[f[:,0]]); n1=np.cross(u[f[:,1]]-u[f[:,0]],u[f[:,2]]-u[f[:,0]]); a0=np.linalg.norm(n0,axis=1); a1=np.linalg.norm(n1,axis=1); folds=np.flatnonzero(np.einsum('ij,ij->i',n0,n1)<=0); col=np.flatnonzero(a1<=a0*1e-4); e=np.unique(np.sort(np.vstack((f[:,[0,1]],f[:,[1,2]],f[:,[2,0]])),axis=1),axis=0); l0=np.linalg.norm(v[e[:,0]]-v[e[:,1]],axis=1); l1=np.linalg.norm(u[e[:,0]]-u[e[:,1]],axis=1); st=np.abs(l1/np.maximum(l0,1e-30)-1); act=(bary[:,None]*u[tri]).sum(0)-neutral; bd=np.linalg.norm(u[b]-v[b],axis=1)
    return {'landmarkRelativeError':float(np.linalg.norm(act-req)/max(np.linalg.norm(req),1e-30)) if np.linalg.norm(req)>0 else 0.0,'constraintResidual':float(np.linalg.norm(act-req)),'folds':int(len(folds)),'foldIds':folds.astype(int).tolist(),'collapsed':int(len(col)),'maxStrain':float(st.max()),'p95Strain':float(np.percentile(st,95)),'maxBoundaryDisplacement':float(bd.max()),'minAreaRatio':float(np.min(a1/np.maximum(a0,1e-30))),'finite':bool(np.isfinite(u).all())}

def run_model(model,patch,goal,markers,out,bridge):
    p=np.load(patch); V=p['V'].astype(float); F=p['F'].astype(np.int32); O=p['originalIndices'].astype(int); records={int(r['index']):r for r in json.loads(goal.read_text())['records']}; mk=json.loads(markers.read_text()); peak=np.asarray(mk['samples']['100']); nm=np.asarray(mk['neutral']); look={int(x):i for i,x in enumerate(O)}; rec=records[105]; tri0=np.asarray([look[int(x)] for x in rec['triangleVertexIndices']],np.int32); keep=component(F,tri0); keep_set=set(keep.tolist()); face_mask=np.all(np.isin(F,keep),axis=1); FF=F[face_mask]; remap={int(x):i for i,x in enumerate(keep)}; f=np.asarray([[remap[int(x)] for x in t] for t in FF],np.int32); v=V[keep]; orig=O[keep]; tri=np.asarray([remap[int(x)] for x in tri0]); bary=np.asarray(rec['barycentricCoordinates']); neutral=(bary[:,None]*v[tri]).sum(0); req=peak[105]-nm[105]; eye=float(np.linalg.norm(np.asarray(records[33]['meshXYZ'])-np.asarray(records[263]['meshXYZ']))); b=boundary(f)
    np.savez_compressed(out/f'{model}-isolated-component.patch.npz',V=v,F=f,originalIndices=orig)
    coarse=list(range(0,101,10)); rows=[]
    def one(pct):
        t=time.perf_counter(); u=solve(v,f,b,tri,bary,neutral+(pct/100)*req,bridge); runtime=time.perf_counter()-t; return {'intensityPercent':pct,'runtimeSeconds':runtime,**measure(v,f,u,b,tri,bary,neutral,(pct/100)*req)}
    for pct in coarse: rows.append(one(pct))
    valid=[r for r in rows if r['folds']>0]; onset=min((r['intensityPercent'] for r in valid),default=None)
    if onset is not None:
        lo=max(0,onset-10); hi=onset
        for pct in range(lo,hi):
            if pct not in [r['intensityPercent'] for r in rows]: rows.append(one(pct))
        rows.sort(key=lambda r:r['intensityPercent'])
        onset=min((r['intensityPercent'] for r in rows if r['folds']>0),default=None)
    return {'model':model,'beforeVertices':int(len(V)),'afterVertices':int(len(v)),'beforeTriangles':int(len(F)),'afterTriangles':int(len(f)),'beforeComponents':2,'afterComponents':1,'interocularWidth':eye,'requestedDisplacement':req.tolist(),'requestedMagnitude':float(np.linalg.norm(req)),'results':rows,'firstFoldOnsetPercent':onset,'isolatedOriginalVertexIds':orig.tolist()}

def main():
    import libigl_barycentric_bridge as bridge
    out=arg('--output'); out.mkdir(parents=True,exist_ok=True); p={'solver':'official libigl ARAP with exact barycentric landmark-105 constraint and original fixed-boundary rule','sameTarget':True,'sameSolverSettings':True,'models':[run_model('female',arg('--female-patch'),arg('--female-goal'),arg('--female-markers'),out,bridge),run_model('male',arg('--male-patch'),arg('--male-goal'),arg('--male-markers'),out,bridge)]}; (out/'isolated-component-report.json').write_text(json.dumps(p,indent=2)+'\n'); print(json.dumps(p,indent=2))
if __name__=='__main__': main()
