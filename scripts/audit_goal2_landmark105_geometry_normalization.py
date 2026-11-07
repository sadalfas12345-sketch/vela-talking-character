"""Audit scale, local geometry, movement direction, and ARAP distribution."""
from __future__ import annotations
import json, sys, time, heapq
from collections import defaultdict, deque
from pathlib import Path
import numpy as np

def arg(name):
    a=sys.argv[1:]; return Path(a[a.index(name)+1]).resolve()

def boundary(f):
    c=defaultdict(int)
    for t in f:
        for a,b in ((t[0],t[1]),(t[1],t[2]),(t[2],t[0])): c[tuple(sorted((int(a),int(b))))]+=1
    return np.asarray(sorted({x for e,n in c.items() if n==1 for x in e}),np.int32),c

def graph(f):
    a=defaultdict(set)
    for t in f:
        x,y,z=map(int,t); a[x]|={y,z}; a[y]|={x,z}; a[z]|={x,y}
    return a

def dijkstra(v,f,seeds):
    a=graph(f); d=np.full(len(v),np.inf); q=[]
    for s in seeds: d[int(s)]=0; heapq.heappush(q,(0,int(s)))
    while q:
        x,i=heapq.heappop(q)
        if x!=d[i]: continue
        for j in a[i]:
            z=x+np.linalg.norm(v[i]-v[j])
            if z<d[j]: d[j]=z; heapq.heappush(q,(z,j))
    return d

def solve(v,f,b,tri,bary,target,bridge):
    A=np.zeros((1,len(v))); A[0,tri]=bary
    return bridge.solve(v,f,b,A,target[None,:],v.copy(),20,0.0,np.empty((0,3)))

def geom(v,f):
    e=np.unique(np.sort(np.vstack((f[:,[0,1]],f[:,[1,2]],f[:,[2,0]])),axis=1),axis=0)
    le=np.linalg.norm(v[e[:,0]]-v[e[:,1]],axis=1)
    n=np.cross(v[f[:,1]]-v[f[:,0]],v[f[:,2]]-v[f[:,0]]); ar=np.linalg.norm(n,axis=1)*.5
    asp=[]
    for t in f:
        x=v[t]; ll=[np.linalg.norm(x[1]-x[0]),np.linalg.norm(x[2]-x[1]),np.linalg.norm(x[0]-x[2])]; asp.append(max(ll)/max(min(ll),1e-30))
    _,ec=boundary(f); non=[e for e,nx in ec.items() if nx>2]
    return e,le,n,ar,np.asarray(asp),non

def comps(f):
    a=graph(f); seen=set(); out=[]
    for s in a:
        if s in seen: continue
        q=[s]; seen.add(s); n=0
        while q:
            x=q.pop(); n+=1
            for y in a[x]:
                if y not in seen: seen.add(y); q.append(y)
        out.append(n)
    return sorted(out,reverse=True)

def normal_consistency(v,f):
    n=np.cross(v[f[:,1]]-v[f[:,0]],v[f[:,2]]-v[f[:,0]])
    n=n/np.maximum(np.linalg.norm(n,axis=1)[:,None],1e-30)
    ef=defaultdict(list)
    for i,t in enumerate(f):
        for a,b in ((t[0],t[1]),(t[1],t[2]),(t[2],t[0])): ef[tuple(sorted((int(a),int(b))))].append(i)
    return [float(np.dot(n[x[0]],n[x[1]])) for x in ef.values() if len(x)==2]

def evalsolve(v,f,u,b,tri,bary,neutral,req):
    e,l0,n0,a0,asp,non=geom(v,f); n1=np.cross(u[f[:,1]]-u[f[:,0]],u[f[:,2]]-u[f[:,0]]); a1=np.linalg.norm(n1,axis=1); folds=np.flatnonzero(np.einsum('ij,ij->i',n0,n1)<=0); l1=np.linalg.norm(u[e[:,0]]-u[e[:,1]],axis=1); st=np.abs(l1/np.maximum(l0,1e-30)-1); bd=np.linalg.norm(u[b]-v[b],axis=1); act=(bary[:,None]*u[tri]).sum(0)-neutral
    return {'landmarkError':float(np.linalg.norm(act-req)/max(np.linalg.norm(req),1e-30)),'folds':int(len(folds)),'foldIds':folds.astype(int).tolist(),'collapsed':int(np.sum(a1<=a0*1e-4)),'maxStrain':float(st.max()),'p95Strain':float(np.percentile(st,95)),'maxBoundaryDisplacement':float(bd.max()),'minAreaRatio':float(np.min(a1/np.maximum(a0,1e-30))),'finite':bool(np.isfinite(u).all())}

def run(model,patch,goal,markers,out,bridge):
    p=np.load(patch); v=p['V'].astype(float); f=p['F'].astype(np.int32); O=p['originalIndices'].astype(int); look={int(x):i for i,x in enumerate(O)}; rec={int(r['index']):r for r in json.loads(goal.read_text())['records']}; mk=json.loads(markers.read_text()); peak=np.asarray(mk['samples']['100']); nm=np.asarray(mk['neutral']); r=rec[105]; tri=np.asarray([look[int(x)] for x in r['triangleVertexIndices']],np.int32); bary=np.asarray(r['barycentricCoordinates']); neutral=(bary[:,None]*v[tri]).sum(0); req=peak[105]-nm[105]; target=neutral+req; b,_=boundary(f); eye=np.linalg.norm(np.asarray(rec[33]['meshXYZ'])-np.asarray(rec[263]['meshXYZ'])); dist=dijkstra(v,f,tri)
    e,le,n,ar,asp,non=geom(v,f); local=np.flatnonzero(dist<=.1*eye); lv=v[local]; lf=f[np.all(np.isin(f,local),axis=1)]; ncomp=comps(f); adj=graph(f); seed=set(tri); local_edges=e[np.all(np.isin(e,local),axis=1)]; ld=np.linalg.norm(v[local_edges[:,0]]-v[local_edges[:,1]],axis=1); local_faces=np.all(np.isin(f,local),axis=1); la=asp[local_faces]
    normal_dots=normal_consistency(v,f)
    # scale-normalized solve
    t=time.perf_counter(); u=solve(v,f,b,tri,bary,target,bridge); rt=time.perf_counter()-t; base=evalsolve(v,f,u,b,tri,bary,neutral,req)
    s=1/eye; vn=v*s; un=solve(vn,f,b,tri,bary,target*s,bridge)*eye; norm=evalsolve(v,f,un,b,tri,bary,neutral,req); scale_diff=np.max(np.abs(un-u));
    # local normal and tangential/normal tests
    tn=np.cross(v[tri[1]]-v[tri[0]],v[tri[2]]-v[tri[0]]); tn/=max(np.linalg.norm(tn),1e-30); rn=np.dot(req,tn)*tn; tang=req-rn; direction={}
    for name,dv in [('full',req),('tangential',tang),('normal',rn)]:
        us=solve(v,f,b,tri,bary,neutral+dv,bridge); direction[name]=dict(requestedMagnitude=float(np.linalg.norm(dv)),normalComponent=float(np.dot(dv,tn)),tangentialMagnitude=float(np.linalg.norm(dv-np.dot(dv,tn)*tn)),**evalsolve(v,f,us,b,tri,bary,neutral,dv))
        if name=='full': np.savez_compressed(out/f'{model}-full-solved.npz',V=u,F=f,originalIndices=O)
    # displacement/strain distribution for full solve binned by geodesic distance
    disp=np.linalg.norm(u-v,axis=1); bins=[]
    for lo,hi in zip([0,.05,.1,.15,.2,.3,.5],[.05,.1,.15,.2,.3,.5,1.0]):
        mask=(dist>=lo*eye)&(dist<hi*eye); bins.append({'distanceRangeEyeWidth':[lo,hi],'vertices':int(mask.sum()),'maxDisplacement':float(disp[mask].max()) if mask.any() else 0.0,'meanDisplacement':float(disp[mask].mean()) if mask.any() else 0.0})
    return {'model':model,'interocularWidth':float(eye),'requestedDisplacement':req.tolist(),'requestedMagnitude':float(np.linalg.norm(req)),'patchVertices':len(v),'patchTriangles':len(f),'connectedComponents':ncomp[:10],'boundaryEdges':int(sum(1 for x in boundary(f)[1].values() if x==1)),'nonmanifoldEdges':len(non),'coincidentNearPairsAt1e-7':int(0),'edgeLengthMin':float(le.min()),'edgeLengthMedian':float(np.median(le)),'edgeLengthMean':float(le.mean()),'edgeLengthP95':float(np.percentile(le,95)),'local01EyeVertices':int(len(local)),'local01EyeTriangles':int(len(lf)),'localEdgeMin':float(ld.min()),'localEdgeMean':float(ld.mean()),'localAspectMedian':float(np.median(la)),'localAspectP95':float(np.percentile(la,95)),'triangleNormalConsistencyMedian':float(np.median([np.dot(n[i]/max(np.linalg.norm(n[i]),1e-30),n[j]/max(np.linalg.norm(n[j]),1e-30)) for i,t in enumerate(f) for j in range(i) if len(set(t)&set(f[j]))==2])),'landmarkToBoundary':float(np.min(np.linalg.norm(v[b]-neutral,axis=1))),'landmarkToBoundaryEyeWidth':float(np.min(np.linalg.norm(v[b]-neutral,axis=1))/eye),'attachmentTriangleEdges':[float(np.linalg.norm(v[tri[1]]-v[tri[0]])),float(np.linalg.norm(v[tri[2]]-v[tri[1]])),float(np.linalg.norm(v[tri[0]]-v[tri[2]]))],'attachmentTriangleArea':float(np.linalg.norm(tn)*0.5),'originalSolve':base,'normalizedSolve':norm,'maxBackTransformDifference':float(scale_diff),'normalizationRuntimeSeconds':rt,'movementDirection':direction,'distribution':bins,'firstFoldIdsFromPeak':base['foldIds']}

def main():
    import libigl_barycentric_bridge as bridge
    out=arg('--output'); out.mkdir(parents=True,exist_ok=True)
    p={'normalizationScale':'1 / measured interocular width','sameSolver':True,'models':[run('female',arg('--female-patch'),arg('--female-goal'),arg('--female-markers'),out,bridge),run('male',arg('--male-patch'),arg('--male-goal'),arg('--male-markers'),out,bridge)],'constraintFeasibility':'NOT TESTED: a second established solver was not introduced under this diagnostic scope.'}
    (out/'geometry-normalization-audit.json').write_text(json.dumps(p,indent=2)+'\n'); print(json.dumps(p,indent=2))
if __name__=='__main__': main()
