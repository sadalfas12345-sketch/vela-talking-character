"""Run Experiment 5 multi-landmark controls through official libigl ARAP."""
import json, sys, time
from pathlib import Path
import numpy as np
import igl
from correct_goal2_experiment4_local_fold import pairs, side, correct

def arg(name):
    a=sys.argv[1:]; return Path(a[a.index(name)+1]).resolve()

def boundary_vertices(F):
    counts={}
    for f in F:
        for a,b in ((int(f[0]),int(f[1])),(int(f[1]),int(f[2])),(int(f[2]),int(f[0]))):
            e=tuple(sorted((a,b))); counts[e]=counts.get(e,0)+1
    return sorted({v for e,c in counts.items() if c==1 for v in e})

def solve(model, patch_path, goal_path, marker_path, ids, out):
    p=np.load(patch_path); V,F=p['V'].astype(float),p['F'].astype(np.int32); orig=p['originalIndices'].astype(int)
    records={int(r['index']):r for r in json.loads(goal_path.read_text())['records']}
    markers=json.loads(marker_path.read_text()); target=np.asarray(markers['samples']['100'],float); neutral=np.asarray(markers['neutral'],float)
    lookup={int(v):i for i,v in enumerate(orig)}; tri_local={}; unique=[]
    for lid in ids:
        tri=np.asarray([lookup[int(v)] for v in records[lid]['triangleVertexIndices']],int); tri_local[lid]=tri; unique.extend(tri.tolist())
    controls=np.asarray(sorted(set(unique)),dtype=np.int32); A=np.zeros((len(ids),len(controls))); cidx={int(v):i for i,v in enumerate(controls)}; desired=[]
    for row,lid in enumerate(ids):
        bary=np.asarray(records[lid]['barycentricCoordinates'],float)
        for v,w in zip(tri_local[lid],bary): A[row,cidx[int(v)]]=w
        desired.append(target[lid]-neutral[lid])
    desired=np.asarray(desired); rank=int(np.linalg.matrix_rank(A)); d=A.T@np.linalg.solve(A@A.T,desired)
    stationary=np.asarray([v for v in boundary_vertices(F) if v not in set(controls)],dtype=np.int32); anchors=np.r_[controls,stationary].astype(np.int32); bc=np.vstack((V[controls]+d,V[stationary]))
    data=igl.ARAPData(); data.energy=igl.ARAP_ENERGY_TYPE_ELEMENTS; data.max_iter=100; t=time.perf_counter(); igl.arap_precomputation(V,F,3,anchors,data); U=igl.arap_solve(bc,data,V.copy()); runtime=time.perf_counter()-t
    # Apply the existing automatic shared-edge correction only to detected fold pairs.
    candidates=[]
    for ia,ib,edge,oa,ob in pairs(F):
        n=np.cross(V[F[ia][1]]-V[F[ia][0]],V[F[ia][2]]-V[F[ia][0]]); nn=np.linalg.norm(n)
        if nn<=1e-20: continue
        n/=nn
        if side(V,edge,oa,n)*side(V,edge,ob,n)<0 and side(U,edge,oa,n)*side(U,edge,ob,n)>=0: candidates.append((ia,ib,edge,oa,ob))
    corrected=U.copy(); corrections=correct(corrected,V,F,candidates)
    measurements=[]
    for lid in ids:
        achieved=(np.asarray(records[lid]['barycentricCoordinates'])[:,None]*corrected[tri_local[lid]]).sum(axis=0)
        requested=target[lid]-neutral[lid]; err=float(np.linalg.norm((achieved-(V[tri_local[lid]]*np.asarray(records[lid]['barycentricCoordinates'])[:,None]).sum(axis=0))-requested)/max(np.linalg.norm(requested),1e-20))
        measurements.append({'id':lid,'requested':requested.tolist(),'achieved':(achieved-(V[tri_local[lid]]*np.asarray(records[lid]['barycentricCoordinates'])[:,None]).sum(axis=0)).tolist(),'relativeError':err})
    base=np.cross(V[F[:,1]]-V[F[:,0]],V[F[:,2]]-V[F[:,0]]); deformed=np.cross(corrected[F[:,1]]-corrected[F[:,0]],corrected[F[:,2]]-corrected[F[:,0]]); areas=np.linalg.norm(deformed,axis=1); a0=np.linalg.norm(base,axis=1); edges=np.unique(np.sort(np.vstack((F[:,[0,1]],F[:,[1,2]],F[:,[2,0]])),axis=1),axis=0); l0=np.linalg.norm(V[edges[:,0]]-V[edges[:,1]],axis=1); l1=np.linalg.norm(corrected[edges[:,0]]-corrected[edges[:,1]],axis=1)
    row={'model':model,'landmarkIds':ids,'patchVertices':len(V),'patchTriangles':len(F),'controlVertices':len(controls),'stationaryBoundaryVertices':len(stationary),'constraintRank':rank,'runtimeSeconds':runtime,'measurements':measurements,'candidateFoldPairs':len(candidates),'corrections':corrections,'newInvertedTriangles':int(np.sum(np.einsum('ij,ij->i',base,deformed)<0)),'collapsedTriangles':int(np.sum(areas<a0*1e-4)),'minimumAreaRatio':float(np.min(areas/np.maximum(a0,1e-20))),'maximumEdgeStrain':float(np.max(np.abs(l1/np.maximum(l0,1e-20)-1))),'finite':bool(np.isfinite(corrected).all())}
    return row

def main():
    out=arg('--output'); out.mkdir(parents=True,exist_ok=True); ids=[int(x) for x in sys.argv[sys.argv.index('--ids')+1].split(',')]
    rows=[solve('female',arg('--female-patch'),arg('--female-goal'),arg('--female-markers'),ids,out),solve('male',arg('--male-patch'),arg('--male-goal'),arg('--male-markers'),ids,out)]
    report={'solver':'official libigl ARAP with barycentric controls and existing automatic local-fold correction','landmarkIds':ids,'models':rows,'sameAlgorithm':True,'sourceGeometryModified':False}
    (out/f'results-{len(ids)}.json').write_text(json.dumps(report,indent=2)+'\n'); print(json.dumps(report,indent=2))
    if any(max(m['relativeError'] for m in r['measurements'])>0.05 or r['newInvertedTriangles'] or r['collapsedTriangles'] or not r['finite'] for r in rows): raise SystemExit(1)
if __name__=='__main__': main()
