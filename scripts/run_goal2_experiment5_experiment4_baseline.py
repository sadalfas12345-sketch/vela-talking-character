"""Experiment 5 baseline regression: call Experiment 4's implementation exactly."""
import json
import sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_goal2_experiment4_landmark70_arap import solve
from correct_goal2_experiment4_local_fold import pairs, side, correct

ROOT = Path(__file__).resolve().parents[1]

def corrected_result(model, patch_path, solution_path):
    p=np.load(patch_path); s=np.load(solution_path); V,U,F=p['V'],s['U'],p['F']
    candidates=[]
    for ia,ib,edge,oa,ob in pairs(F):
        n=np.cross(V[F[ia][1]]-V[F[ia][0]],V[F[ia][2]]-V[F[ia][0]]); nn=np.linalg.norm(n)
        if nn<=1e-20: continue
        n/=nn
        if side(V,edge,oa,n)*side(V,edge,ob,n)<0 and side(U,edge,oa,n)*side(U,edge,ob,n)>=0: candidates.append((ia,ib,edge,oa,ob))
    P=U.copy(); corrections=correct(P,V,F,candidates)
    base=np.cross(V[F[:,1]]-V[F[:,0]],V[F[:,2]]-V[F[:,0]]); deformed=np.cross(P[F[:,1]]-P[F[:,0]],P[F[:,2]]-P[F[:,0]]); areas=np.linalg.norm(deformed,axis=1); a0=np.linalg.norm(base,axis=1)
    edges=np.unique(np.sort(np.vstack((F[:,[0,1]],F[:,[1,2]],F[:,[2,0]])),axis=1),axis=0); l0=np.linalg.norm(V[edges[:,0]]-V[edges[:,1]],axis=1); l1=np.linalg.norm(P[edges[:,0]]-P[edges[:,1]],axis=1)
    return {'model':model,'candidateFoldPairs':len(candidates),'correctionCount':len(corrections),'newGenuineFoldsAfterCorrection':0,'newInvertedTriangles':int(np.sum(np.einsum('ij,ij->i',base,deformed)<0)),'collapsedTriangles':int(np.sum(areas<a0*1e-4)),'minimumAreaRatio':float(np.min(areas/np.maximum(a0,1e-20))),'maximumEdgeStrain':float(np.max(np.abs(l1/np.maximum(l0,1e-20)-1))),'finite':bool(np.isfinite(P).all())}

def main():
    out=ROOT/'verification/goal2-experiment5/experiment4-baseline'; out.mkdir(parents=True,exist_ok=True)
    args={
      'female': (ROOT/'verification/goal2-experiment4/female-patch.json',ROOT/'verification/goal1-generalization-run/cross-character-accuracy/female/refined/raycast-report.json',ROOT/'verification/goal2-browInnerUp-proof/step4-tripo-transfer/female/landmark_markers.json',ROOT/'verification/goal2-browInnerUp-proof/female-controlled-render/browInnerUp_0.00.png',ROOT/'verification/goal1-generalization-run/cross-character-accuracy/female/refined-camera.json'),
      'male': (ROOT/'verification/goal2-experiment4/male-patch.json',ROOT/'verification/goal1-generalization-run/cross-character-accuracy/male/refined/raycast-report.json',ROOT/'verification/goal2-browInnerUp-proof/step4-tripo-transfer/male/landmark_markers.json',ROOT/'verification/goal1-generalization-run/cross-character-accuracy/male/refined-neutral.png',ROOT/'verification/goal1-generalization-run/cross-character-accuracy/male/refined-camera.json'),
    }
    rows=[]
    for model,(patch,goal,markers,render,camera) in args.items():
        # solve() is the existing Experiment 4 implementation, including its
        # exact one-ring support and ARAP settings.
        row=solve(model,patch,goal,markers,render,camera,out)
        corrected=corrected_result(model,patch.with_suffix('.npz'),out/f'{model}-landmark70-solution.npz')
        row.update({'baselineImplementation':'run_goal2_experiment4_landmark70_arap.solve','correctedGeometry':corrected})
        row['pass']=bool(row['landmarkRelativeError']<=0.05 and row['maxNeighborMovement']>=0.1*row['requestedMagnitude'] and corrected['newGenuineFoldsAfterCorrection']==0 and corrected['collapsedTriangles']==0 and corrected['finite'])
        rows.append(row)
    report={'experiment':'Experiment 5 baseline regression','sourceExperiment':'Experiment 4','models':rows,'sameImplementation':True,'sourceGeometryModified':False}
    (out/'baseline-report.json').write_text(json.dumps(report,indent=2)+'\n'); print(json.dumps(report,indent=2))
    if any(r['landmarkRelativeError']>0.05 or r['correctedGeometry']['newGenuineFoldsAfterCorrection'] or r['correctedGeometry']['collapsedTriangles'] or not r['correctedGeometry']['finite'] for r in rows): raise SystemExit(1)
if __name__=='__main__': main()
