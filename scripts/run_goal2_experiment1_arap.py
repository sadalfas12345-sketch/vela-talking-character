"""Experiment 1: one controlled official libigl ARAP forehead-patch move."""
import json, sys, time
from pathlib import Path
import numpy as np
import igl
from PIL import Image, ImageDraw

def arg(name):
    a=sys.argv[1:]; return Path(a[a.index(name)+1]).resolve()

def project(points, camera, size):
    loc=np.asarray(camera['cameraLocation'],float); right=np.asarray(camera['cameraBasis']['right'],float); up=np.asarray(camera['cameraBasis']['up'],float); scale=float(camera['orthoScale']); w,h=size
    v=points-loc[None,:]
    return np.c_[w/2+(v@right)/scale*w, h/2-(v@up)/scale*h]

def solve(name, patch_path, render_path, camera_path, outdir):
    z=np.load(patch_path.with_suffix('.npz')); V=np.asarray(z['V'],float); F=np.asarray(z['F'],np.int64); moved=int(z['moved']); stationary=np.asarray(z['stationary'],np.int64); eye=float(z['eyeWidth']); up=np.asarray(z['upAxis'],float)
    req_mag=.01*eye; target=V.copy(); target[moved]+=up*req_mag; b=np.asarray([moved,*stationary],np.int32); bc=V[b].copy(); bc[0]=target[moved]
    data=igl.ARAPData(); data.energy=igl.ARAP_ENERGY_TYPE_ELEMENTS; data.max_iter=100
    t=time.perf_counter(); igl.arap_precomputation(V,F,3,b,data); U=igl.arap_solve(bc,data,V.copy()); runtime=time.perf_counter()-t
    delta=U-V
    neighbors=set()
    for tri in F:
        if moved in tri: neighbors.update(int(v) for v in tri if int(v)!=moved)
    neighbor=max((float(np.linalg.norm(delta[i])) for i in neighbors),default=0.0)
    base=np.cross(V[F[:,1]]-V[F[:,0]],V[F[:,2]]-V[F[:,0]]); new=np.cross(U[F[:,1]]-U[F[:,0]],U[F[:,2]]-U[F[:,0]])
    a0=np.linalg.norm(base,axis=1); a1=np.linalg.norm(new,axis=1); dots=np.einsum('ij,ij->i',base,new)
    edge_pairs=set();
    for tri in F:
        for i,j in ((tri[0],tri[1]),(tri[1],tri[2]),(tri[2],tri[0])): edge_pairs.add(tuple(sorted((int(i),int(j)))))
    strains=[abs(float(np.linalg.norm(U[i]-U[j])/max(np.linalg.norm(V[i]-V[j]),1e-20)-1)) for i,j in edge_pairs]
    row={'model':name,'vertices':len(V),'triangles':len(F),'movedVertex':moved,'stationaryVertices':stationary.tolist(),'eyeWidth':eye,'requestedMovement':req_mag,'achievedMovement':float(np.linalg.norm(delta[moved])),'achievementRatio':float(np.linalg.norm(delta[moved])/req_mag),'maxNeighborMovement':neighbor,'neighborCount':len(neighbors),'newInvertedTriangles':int(np.sum(dots<0)),'newCollapsedTriangles':int(np.sum(a1< a0*1e-4)),'minimumAreaRatio':float(np.min(a1/np.maximum(a0,1e-20))),'maxEdgeStrain':max(strains,default=0.0),'runtimeSeconds':runtime,'status':'SOLVED'}
    np.savez_compressed(outdir/f'{name}-solution.npz',V=V,U=U,F=F)
    img=Image.open(render_path).convert('RGB'); xy0=project(V,camera_path and json.loads(camera_path.read_text()),img.size); xy1=project(U,json.loads(camera_path.read_text()),img.size); d=ImageDraw.Draw(img)
    for tri in F[::max(1,len(F)//300)]:
        pts=[tuple(xy0[int(i)]) for i in tri]; d.line(pts+[pts[0]],fill=(80,160,255),width=1)
    p0=tuple(xy0[moved]); p1=tuple(xy1[moved]); d.line((p0,p1),fill=(255,50,50),width=4); d.ellipse((p0[0]-6,p0[1]-6,p0[0]+6,p0[1]+6),outline=(255,255,0),width=3); d.ellipse((p1[0]-6,p1[1]-6,p1[0]+6,p1[1]+6),outline=(255,50,50),width=3); d.text((10,10),f'{name}: blue neutral patch, red solved vertex',fill='white')
    img.save(outdir/f'{name}-before-after-overlay.png')
    return row

def main():
    out=arg('--output'); out.mkdir(parents=True,exist_ok=True); rows=[]
    configs=[('female',arg('--female-patch'),arg('--female-render'),arg('--female-camera')),('male',arg('--male-patch'),arg('--male-render'),arg('--male-camera'))]
    for name,patch,render,cam in configs: rows.append(solve(name,patch,render,cam,out))
    (out/'experiment1-report.json').write_text(json.dumps({'solver':'official libigl arap_precomputation/arap_solve','request':'1% of each target eye width upward using existing anatomical up axis','models':rows},indent=2)+'\n')
    print(json.dumps(rows,indent=2))
if __name__=='__main__': main()
