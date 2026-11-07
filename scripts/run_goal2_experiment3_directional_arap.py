"""Experiment 3: deterministic different-direction libigl ARAP controls."""
import json, sys, time
from pathlib import Path
import numpy as np
import igl
from PIL import Image, ImageDraw

def arg(name):
    a=sys.argv[1:]; return Path(a[a.index(name)+1]).resolve()

def select_controls(V, stationary, count):
    forbidden=set(int(x) for x in stationary); candidates=[i for i in range(len(V)) if i not in forbidden]
    center=np.mean(V[candidates],axis=0); first=min(candidates,key=lambda i:(np.linalg.norm(V[i]-center),i)); selected=[first]
    while len(selected)<count:
        selected.append(max((i for i in candidates if i not in selected),key=lambda i:(min(np.linalg.norm(V[i]-V[j]) for j in selected),-i)))
    return np.asarray(selected,dtype=np.int32)

def solve_model(name, patch_path, render_path, camera_path, out):
    z=np.load(patch_path.with_suffix('.npz')); V=np.asarray(z['V'],float); F=np.asarray(z['F'],np.int64); stationary=np.asarray(z['stationary'],np.int32); eye=float(z['eyeWidth']); up=np.asarray(z['upAxis'],float); up/=max(np.linalg.norm(up),1e-20); xaxis=np.asarray(z['xAxis'],float); xaxis/=max(np.linalg.norm(xaxis),1e-20)
    center=np.mean(V,axis=0); xcoord=(V-center)@xaxis; span=max(float(np.ptp(xcoord)),1e-20); t=np.clip((xcoord-xcoord.min())/span,0,1)
    adjacency=[set() for _ in range(len(V))]
    for tri in F:
        for i,j in ((tri[0],tri[1]),(tri[1],tri[2]),(tri[2],tri[0])): adjacency[int(i)].add(int(j)); adjacency[int(j)].add(int(i))
    rows=[]; last=None; last_controls=None; last_vecs=None
    for count in (2,4,8,16):
        controls=select_controls(V,stationary,count)
        # Inner forehead is defined as the side closest to the patch centre in
        # anatomical X. Outer controls receive 0.5%, with smooth interpolation.
        inner=np.clip(1.0-2.0*np.abs(t[controls]-0.5),0.0,1.0)
        up_amount=(0.005+0.005*inner)*eye
        horizontal=((t[controls]-0.5)*0.004)*eye
        vectors=up_amount[:,None]*up[None,:]+horizontal[:,None]*xaxis[None,:]
        b=np.r_[controls,stationary].astype(np.int32); bc=V[b].copy(); bc[:count]+=vectors
        data=igl.ARAPData(); data.energy=igl.ARAP_ENERGY_TYPE_ELEMENTS; data.max_iter=100
        t0=time.perf_counter(); igl.arap_precomputation(V,F,3,b,data); U=igl.arap_solve(bc,data,V.copy()); runtime=time.perf_counter()-t0; delta=U-V
        actual=delta[controls]; errors=np.linalg.norm(actual-vectors,axis=1)/np.maximum(np.linalg.norm(vectors,axis=1),1e-20); mags=np.linalg.norm(vectors,axis=1)
        neigh=set().union(*(adjacency[int(i)] for i in controls))-set(controls)-set(int(i) for i in stationary); max_neighbor=max((float(np.linalg.norm(delta[i])) for i in neigh),default=0.0)
        base=np.cross(V[F[:,1]]-V[F[:,0]],V[F[:,2]]-V[F[:,0]]); new=np.cross(U[F[:,1]]-U[F[:,0]],U[F[:,2]]-U[F[:,0]]); a0=np.linalg.norm(base,axis=1); a1=np.linalg.norm(new,axis=1); dots=np.einsum('ij,ij->i',base,new); inv=int(np.sum(dots<0)); collapsed=int(np.sum(a1<a0*1e-4)); finite=bool(np.isfinite(U).all())
        row={'model':name,'movingControls':count,'patchVertices':len(V),'patchTriangles':len(F),'requestedVectors':[v.tolist() for v in vectors],'achievedVectors':[v.tolist() for v in actual],'maxControlRelativeError':float(errors.max()),'minControlRelativeError':float(errors.min()),'maximumRequestedDistance':float(mags.max()),'maximumNeighborMovement':max_neighbor,'neighborRatioToMaximumRequest':max_neighbor/float(mags.max()),'newInvertedTriangles':inv,'newCollapsedTriangles':collapsed,'finiteCoordinates':finite,'runtimeSeconds':runtime,'movingLocalIndices':controls.tolist(),'stationaryLocalIndices':stationary.tolist(),'pass':bool(errors.max()<=.01 and max_neighbor>=.1*float(mags.max()) and inv==0 and collapsed==0 and finite)}
        rows.append(row); last,last_controls,last_vecs=U,controls,vectors
        if not row['pass']: return rows
    img=Image.open(render_path).convert('RGB'); cam=json.loads(camera_path.read_text()); loc=np.asarray(cam['cameraLocation']); right=np.asarray(cam['cameraBasis']['right']); cu=np.asarray(cam['cameraBasis']['up']); scale=float(cam['orthoScale']); w,h=img.size
    def proj(P):
        q=P-loc; return np.c_[w/2+(q@right)/scale*w,h/2-(q@cu)/scale*h]
    p0,p1=proj(V),proj(last); d=ImageDraw.Draw(img)
    for tri in F[::max(1,len(F)//300)]: d.line([tuple(p0[int(i)]) for i in (*tri,tri[0])],fill=(80,160,255),width=1)
    for i in last_controls:
        a,b=tuple(p0[int(i)]),tuple(p1[int(i)]); d.line((a,b),fill=(255,70,60),width=3); d.ellipse((a[0]-5,a[1]-5,a[0]+5,a[1]+5),outline=(255,255,0),width=2); d.ellipse((b[0]-5,b[1]-5,b[0]+5,b[1]+5),outline=(255,70,60),width=2)
    d.rectangle((0,0,w,32),fill=(0,0,0)); d.text((8,7),f'{name}: 16-control directional ARAP overlay',fill='white'); img.save(out/f'{name}-16-control-directional-before-after.png')
    return rows

def main():
    out=arg('--output'); out.mkdir(parents=True,exist_ok=True); allrows=[]; stopped=False
    for cfg in [('female',arg('--female-patch'),arg('--female-render'),arg('--female-camera')),('male',arg('--male-patch'),arg('--male-render'),arg('--male-camera'))]:
        rows=solve_model(*cfg,out); allrows.extend(rows)
        if len(rows)<4 or not rows[-1]['pass']: stopped=True; break
    report={'solver':'official libigl arap_precomputation/arap_solve','pattern':'inner 1%, outer 0.5%, smooth horizontal component up to 0.2% eye width','controlCounts':[2,4,8,16],'sameAlgorithm':True,'sourceGeometryModified':False,'stoppedOnFailure':stopped,'models':allrows}
    (out/'experiment3-report.json').write_text(json.dumps(report,indent=2)+'\n'); print(json.dumps(report,indent=2))
    if stopped: raise SystemExit(1)
if __name__=='__main__': main()
