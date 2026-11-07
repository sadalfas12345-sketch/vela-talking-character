"""Experiment 2: simultaneous same-direction libigl ARAP controls."""
import json, sys, time
from pathlib import Path
import numpy as np
import igl
from PIL import Image, ImageDraw

def arg(name):
    a=sys.argv[1:]; return Path(a[a.index(name)+1]).resolve()

def select_controls(V, stationary, count):
    forbidden=set(int(x) for x in stationary); candidates=[i for i in range(len(V)) if i not in forbidden]
    # Farthest-point sampling gives the same deterministic geometric rule on both meshes.
    center=np.mean(V[candidates],axis=0); first=min(candidates,key=lambda i: (np.linalg.norm(V[i]-center),i)); selected=[first]
    while len(selected)<count:
        nxt=max((i for i in candidates if i not in selected),key=lambda i:(min(np.linalg.norm(V[i]-V[j]) for j in selected),-i))
        selected.append(nxt)
    return np.asarray(selected,dtype=np.int32)

def project(points, camera, size):
    loc=np.asarray(camera['cameraLocation'],float); right=np.asarray(camera['cameraBasis']['right'],float); up=np.asarray(camera['cameraBasis']['up'],float); scale=float(camera['orthoScale']); w,h=size
    v=points-loc[None,:]
    return np.c_[w/2+(v@right)/scale*w, h/2-(v@up)/scale*h]

def run_model(name, patch_path, render_path, camera_path, outdir):
    z=np.load(patch_path.with_suffix('.npz')); V=np.asarray(z['V'],float); F=np.asarray(z['F'],np.int64); stationary=np.asarray(z['stationary'],np.int32); eye=float(z['eyeWidth']); up=np.asarray(z['upAxis'],float); up/=max(np.linalg.norm(up),1e-20); req=.01*eye
    edge_pairs=set(); adjacency=[set() for _ in range(len(V))]
    for tri in F:
        for i,j in ((tri[0],tri[1]),(tri[1],tri[2]),(tri[2],tri[0])):
            i,j=int(i),int(j); edge_pairs.add(tuple(sorted((i,j)))); adjacency[i].add(j); adjacency[j].add(i)
    rows=[]; lastU=None; lastControls=None
    for count in (2,4,8,16):
        controls=select_controls(V,stationary,count); b=np.r_[controls,stationary].astype(np.int32); bc=V[b].copy(); bc[:count]+=up*req
        data=igl.ARAPData(); data.energy=igl.ARAP_ENERGY_TYPE_ELEMENTS; data.max_iter=100
        t=time.perf_counter(); igl.arap_precomputation(V,F,3,b,data); U=igl.arap_solve(bc,data,V.copy()); runtime=time.perf_counter()-t; delta=U-V
        control_vectors=delta[controls]; mags=np.linalg.norm(control_vectors,axis=1); ratios=mags/req; dirs=(control_vectors@up)/req
        noncontrol=set(range(len(V)))-set(controls)-set(int(x) for x in stationary); neigh=set().union(*(adjacency[int(i)] for i in controls))-set(controls)-set(int(x) for x in stationary); neigh &= noncontrol
        max_neighbor=max((float(np.linalg.norm(delta[i])) for i in neigh),default=0.0)
        base=np.cross(V[F[:,1]]-V[F[:,0]],V[F[:,2]]-V[F[:,0]]); new=np.cross(U[F[:,1]]-U[F[:,0]],U[F[:,2]]-U[F[:,0]]); a0=np.linalg.norm(base,axis=1); a1=np.linalg.norm(new,axis=1); dots=np.einsum('ij,ij->i',base,new)
        inv=int(np.sum(dots<0)); collapsed=int(np.sum(a1<a0*1e-4)); max_error=float(max(np.maximum(0,1-ratios).max(),np.maximum(0,ratios-1).max(),np.maximum(0,1-dirs).max(),np.maximum(0,dirs-1).max()))
        row={'model':name,'movingControls':count,'patchVertices':len(V),'patchTriangles':len(F),'requestedDisplacement':req,'achievedMin':float(mags.min()),'achievedMax':float(mags.max()),'maxControlRelativeError':max_error,'minDirectionRatio':float(dirs.min()),'maxDirectionRatio':float(dirs.max()),'neighborCandidates':len(neigh),'maxNeighborMovement':max_neighbor,'neighborRatio':max_neighbor/req,'newInvertedTriangles':inv,'newCollapsedTriangles':collapsed,'runtimeSeconds':runtime,'movingLocalIndices':controls.tolist(),'stationaryLocalIndices':stationary.tolist(),'pass':bool(max_error<=.01 and max_neighbor>=.1*req and inv==0 and collapsed==0)}
        rows.append(row); lastU,lastControls=U,controls
        if not row['pass']: return rows, None
    img=Image.open(render_path).convert('RGB'); cam=json.loads(camera_path.read_text()); xy0=project(V,cam,img.size); xy1=project(lastU,cam,img.size); d=ImageDraw.Draw(img)
    for tri in F[::max(1,len(F)//300)]: d.line([tuple(xy0[int(i)]) for i in (*tri,tri[0])],fill=(80,160,255),width=1)
    for i in lastControls:
        p0=tuple(xy0[int(i)]); p1=tuple(xy1[int(i)]); d.line((p0,p1),fill=(255,60,60),width=3); d.ellipse((p0[0]-5,p0[1]-5,p0[0]+5,p0[1]+5),outline=(255,255,0),width=2); d.ellipse((p1[0]-5,p1[1]-5,p1[0]+5,p1[1]+5),outline=(255,60,60),width=2)
    d.rectangle((0,0,img.width,32),fill=(0,0,0)); d.text((8,7),f'{name}: 16-control ARAP overlay',fill='white'); img.save(outdir/f'{name}-16-control-before-after.png')
    return rows, lastU

def main():
    out=arg('--output'); out.mkdir(parents=True,exist_ok=True); allrows=[]; stopped=False
    configs=[('female',arg('--female-patch'),arg('--female-render'),arg('--female-camera')),('male',arg('--male-patch'),arg('--male-render'),arg('--male-camera'))]
    for name,patch,render,cam in configs:
        rows,_=run_model(name,patch,render,cam,out); allrows.extend(rows)
        if len(rows)<4 or not rows[-1]['pass']:
            stopped=True; break
    report={'solver':'official libigl arap_precomputation/arap_solve','controlCounts':[2,4,8,16],'stoppedOnFailure':stopped,'models':allrows,'sameAlgorithm':True,'sourceGeometryModified':False}
    (out/'experiment2-report.json').write_text(json.dumps(report,indent=2)+'\n'); print(json.dumps(report,indent=2))
    if stopped: raise SystemExit(1)
if __name__=='__main__': main()
