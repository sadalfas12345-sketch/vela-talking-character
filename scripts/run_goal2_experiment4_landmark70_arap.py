"""Experiment 4: drive one existing barycentric landmark through libigl ARAP."""
import json, sys, time
from pathlib import Path
import numpy as np
import igl
from PIL import Image, ImageDraw

def arg(name):
    a=sys.argv[1:]; return Path(a[a.index(name)+1]).resolve()

def solve(name, patch_path, goal_path, marker_path, render_path, camera_path, out):
    z=np.load(patch_path.with_suffix('.npz')); V=np.asarray(z['V'],float); F=np.asarray(z['F'],np.int64); original=np.asarray(z['originalIndices'],np.int64); stationary=np.asarray(z['stationary'],np.int32); eye=float(z['eyeWidth']);
    goal=json.loads(goal_path.read_text()); records={int(r['index']):r for r in goal['records']}; rec=records[70]
    tri_global=np.asarray(rec['triangleVertexIndices'],np.int64); local={int(v):i for i,v in enumerate(original)}; tri=np.asarray([local[int(v)] for v in tri_global],np.int32); bary=np.asarray(rec['barycentricCoordinates'],float)
    markers=json.loads(marker_path.read_text()); neutral=np.asarray(markers['neutral'][70],float); target=np.asarray(markers['samples']['100'][70],float); requested=target-neutral
    # Minimum-norm vertex displacement satisfying the actual barycentric constraint.
    vertex_delta=np.outer(bary,requested)/max(float(bary@bary),1e-20)
    b=np.r_[tri,stationary].astype(np.int32); bc=V[b].copy(); bc[:3]+=vertex_delta
    data=igl.ARAPData(); data.energy=igl.ARAP_ENERGY_TYPE_ELEMENTS; data.max_iter=100; t=time.perf_counter(); igl.arap_precomputation(V,F,3,b,data); U=igl.arap_solve(bc,data,V.copy()); runtime=time.perf_counter()-t
    achieved=(bary[:,None]*U[tri]).sum(0)-(bary[:,None]*V[tri]).sum(0); error=float(np.linalg.norm(achieved-requested)/max(np.linalg.norm(requested),1e-20)); delta=U-V
    tri_set=set(int(x) for x in tri); neighbors=set()
    for face in F:
        if tri_set.intersection(int(x) for x in face): neighbors.update(int(x) for x in face)
    neighbors-=tri_set; neighbors-=set(int(x) for x in stationary); max_neighbor=max((float(np.linalg.norm(delta[i])) for i in neighbors),default=0.0)
    base=np.cross(V[F[:,1]]-V[F[:,0]],V[F[:,2]]-V[F[:,0]]); new=np.cross(U[F[:,1]]-U[F[:,0]],U[F[:,2]]-U[F[:,0]]); a0=np.linalg.norm(base,axis=1); a1=np.linalg.norm(new,axis=1); dots=np.einsum('ij,ij->i',base,new); inv=int(np.sum(dots<0)); collapsed=int(np.sum(a1<a0*1e-4)); finite=bool(np.isfinite(U).all())
    row={'model':name,'landmarkId':70,'triangleVertexIds':tri_global.tolist(),'localTriangleIndices':tri.tolist(),'barycentricWeights':bary.tolist(),'neutralLandmark':neutral.tolist(),'requestedTarget':target.tolist(),'requestedDisplacement':requested.tolist(),'requestedMagnitude':float(np.linalg.norm(requested)),'achievedDisplacement':achieved.tolist(),'achievedMagnitude':float(np.linalg.norm(achieved)),'landmarkRelativeError':error,'maxNeighborMovement':max_neighbor,'neighborCount':len(neighbors),'newInvertedTriangles':inv,'newCollapsedTriangles':collapsed,'finiteCoordinates':finite,'patchVertices':len(V),'patchTriangles':len(F),'runtimeSeconds':runtime,'pass':bool(error<=.05 and max_neighbor>=.1*float(np.linalg.norm(requested)) and inv==0 and collapsed==0 and finite)}
    np.savez_compressed(out/f'{name}-landmark70-solution.npz',V=V,U=U,F=F,triangle=tri,bary=bary)
    cam=json.loads(camera_path.read_text()); img=Image.open(render_path).convert('RGB'); loc=np.asarray(cam['cameraLocation']); right=np.asarray(cam['cameraBasis']['right']); up=np.asarray(cam['cameraBasis']['up']); scale=float(cam['orthoScale']); w,h=img.size
    def proj(P):
        q=P-loc; return np.c_[w/2+(q@right)/scale*w,h/2-(q@up)/scale*h]
    p0,p1=proj(V),proj(U); d=ImageDraw.Draw(img)
    for i in tri: d.line([tuple(p0[int(i)]) for i in (*tri,tri[0])],fill=(80,160,255),width=3)
    for i in tri: d.line((tuple(p0[int(i)]),tuple(p1[int(i)])),fill=(255,100,0),width=2)
    marker0=proj((bary[:,None]*V[tri]).sum(0)[None,:])[0]; markert=proj(target[None,:])[0]; markera=proj(((bary[:,None]*U[tri]).sum(0))[None,:])[0]
    d.line((tuple(marker0),tuple(markert)),fill=(255,255,0),width=4); d.ellipse((marker0[0]-7,marker0[1]-7,marker0[0]+7,marker0[1]+7),outline=(80,160,255),width=3); d.ellipse((markert[0]-7,markert[1]-7,markert[0]+7,markert[1]+7),outline=(255,255,0),width=3); d.ellipse((markera[0]-6,markera[1]-6,markera[0]+6,markera[1]+6),outline=(255,60,60),width=3); d.rectangle((0,0,w,34),fill=(0,0,0)); d.text((8,7),f'{name}: landmark 70 blue neutral, yellow target, red achieved',fill='white'); img.save(out/f'{name}-landmark70-before-after.png')
    return row

def main():
    out=arg('--output'); out.mkdir(parents=True,exist_ok=True); rows=[]
    cfg=[('female',arg('--female-patch'),arg('--female-goal'),arg('--female-markers'),arg('--female-render'),arg('--female-camera')),('male',arg('--male-patch'),arg('--male-goal'),arg('--male-markers'),arg('--male-render'),arg('--male-camera'))]
    for c in cfg: rows.append(solve(*c,out))
    report={'solver':'official libigl arap_precomputation/arap_solve','landmarkId':70,'models':rows,'sourceGeometryModified':False,'sameAlgorithm':True}
    (out/'experiment4-report.json').write_text(json.dumps(report,indent=2)+'\n'); print(json.dumps(report,indent=2))
    if not all(r['pass'] for r in rows): raise SystemExit(1)
if __name__=='__main__': main()
