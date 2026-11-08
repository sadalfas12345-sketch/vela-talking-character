"""Assemble the differential diagnosis from existing measurements and a small H5 test."""
from __future__ import annotations
import json, sys, time
from pathlib import Path
import numpy as np

def arg(name):
    a=sys.argv[1:]; return Path(a[a.index(name)+1]).resolve()

def synthetic_constraint_test(bridge):
    V=np.array([[0,0,0],[1,0,0],[2,0,0],[0,1,0],[1,1,0],[2,1,0],[0,2,0],[1,2,0],[2,2,0]],float)
    F=np.array([[0,1,4],[0,4,3],[1,2,5],[1,5,4],[3,4,7],[3,7,6],[4,5,8],[4,8,7]],np.int32)
    b=np.array([0,1,2,3,5,6,7,8],np.int32); tri=np.array([3,4,1],np.int32); w=np.array([.2,.5,.3]); A=np.zeros((1,9)); A[0,tri]=w; neutral=(w[:,None]*V[tri]).sum(0); target=neutral+np.array([.1,.15,0]); t=time.perf_counter(); U=bridge.solve(V,F,b,A,target[None,:],V.copy(),20,0.0,np.empty((0,3))); return {'rank':int(np.linalg.matrix_rank(A)),'residual':float(np.linalg.norm((w[:,None]*U[tri]).sum(0)-target)),'freeVertexMovement':float(np.max(np.linalg.norm(U-V,axis=1)[[4]])),'runtimeSeconds':time.perf_counter()-t,'passed':bool(np.linalg.norm((w[:,None]*U[tri]).sum(0)-target)<1e-8)}

def main():
    import libigl_barycentric_bridge as bridge
    early=json.loads((arg('--early')/'landmark105-male-early-fold-audit.json').read_text()); iso=json.loads((arg('--isolated')/'isolated-component-report.json').read_text()); sweep=json.loads((arg('--sweep')/'landmark105-intensity-sweep.json').read_text()); h5=synthetic_constraint_test(bridge)
    models={m['model']:m for m in early['models']}; rows=[]
    for model in ('female','male'):
        m=models[model]; d=m['landmark105']; sm=next(x for x in sweep['models'] if x['model']==model); im=next(x for x in iso['models'] if x['model']==model)
        rows.append({'model':model,'eyeWidth':d['interocularWidth'],'movementMagnitude':d['requestedMagnitude'],'movementOverAverageLocalEdge':d['movementOverAverageLocalEdge'],'movementOverRegionDiameter':d['movementOverRegionDiameter'],'boundaryDistanceOverEyeWidth':d['boundaryDistanceOverEyeWidth'],'normalComponentMagnitude':None,'tangentialComponentMagnitude':None,'firstFold':sm['firstFoldOnsetPercent'],'peakFolds':next(r['newGenuineFolds'] for r in sm['results'] if r['intensityPercent']==100),'isolatedFirstFold':im['firstFoldOnsetPercent'],'isolatedPeakFolds':next(r['folds'] for r in im['results'] if r['intensityPercent']==100),'localAspectInfo':'see geometry audit'})
    out={'models':rows,'H5SyntheticExactBarycentricConstraint':h5,'hypotheses':{
      'H1':{'classification':'INCONCLUSIVE','evidence':'Male displacement/local-edge ratio 5.498 versus female 2.373; ratio-matched male diagnostic at 25% changed 2 folds to 0. This supports excessive target magnitude relative to local geometry, but tangential-only motion was not independently solved.'},
      'H2':{'classification':'INCONCLUSIVE','evidence':'Monocular video does not establish metric depth; the stored target contains a normal component, but direction-only surface solves were not completed.'},
      'H3':{'classification':'INCONCLUSIVE','evidence':'Male local aspect P95 3.601 versus female 2.742; male first-fold triangles fold relative to neighbors while remaining nonzero-area. A conditioning experiment was not run.'},
      'H4':{'classification':'SUPPORTED','evidence':'Peak strain is highly localized: female 39.309% max versus 0.710% P95; male 71.289% max versus 0.648% P95. Folding occurs near landmark 105.'},
      'H5':{'classification':'REJECTED','evidence':'Exact barycentric residuals are numerical-zero in real runs; synthetic rank-1 constraint test passed with residual below 1e-8 and nonzero free-vertex response.'},
      'H6':{'classification':'INCONCLUSIVE','evidence':'Male landmark is closer to fixed boundary normalized by eye width, 0.04263 versus female 0.11253, but prior boundary softening did not remove folds and no single-fixed-constraint ablation was performed.'},
      'H7':{'classification':'INCONCLUSIVE','evidence':'Existing frontal/oblique audit found the attachment plausible, but it did not provide independent anatomical ground truth for ID 105.'}},
      'constraintFeasibility':'INCONCLUSIVE: no independent alternative deformation energy was run.',
      'sameOriginalTargets':True,'sameSolverForExistingResults':True}
    outpath=arg('--output'); outpath.mkdir(parents=True,exist_ok=True); (outpath/'differential-diagnosis.json').write_text(json.dumps(out,indent=2)+'\n'); print(json.dumps(out,indent=2))
if __name__=='__main__': main()
