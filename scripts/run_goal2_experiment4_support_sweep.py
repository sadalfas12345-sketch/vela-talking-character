"""Sweep connected support-ring sizes for the existing landmark-70 ARAP test."""
import json, time, sys
from pathlib import Path
import numpy as np
import igl
from PIL import Image, ImageDraw

def arg(name):
    a=sys.argv[1:]; return Path(a[a.index(name)+1]).resolve()

def solve(name, patch_path, goal_path, marker_path, render_path, camera_path, out):
    z=np.load(patch_path.with_suffix('.npz')); V=np.asarray(z['V'],float); F=np.asarray(z['F'],np.int64); original=np.asarray(z['originalIndices'],np.int64); stationary=np.asarray(z['stationary'],np.int32)
    goal=json.loads(goal_path.read_text()); rec={int(r['index']):r for r in goal['records']}[70]; markers=json.loads(marker_path.read_text()); neutral=np.asarray(markers['neutral'][70],float); target=np.asarray(markers['samples']['100'][70],float); requested=target-neutral; reqmag=float(np.linalg.norm(requested)); tri=np.asarray([int(np.where(original==v)[0][0]) for v in rec['triangleVertexIndices']],np.int32); bary=np.asarray(rec['barycentricCoordinates'],float)
    adjacency=[set() for _ in range(len(V))]
    for face in F:
        for i,j in ((face[0],face[1]),(face[1],face[2]),(face[2],face[0])): adjacency[int(i)].add(int(j)); adjacency[int(j)].add(int(i))
    imgbase=Image.open(render_path).convert('RGB'); cam=json.loads(camera_path.read_text()); loc=np.asarray(cam['cameraLocation']); right=np.asarray(cam['cameraBasis']['right']); up=np.asarray(cam['cameraBasis']['up']); scale=float(cam['orthoScale']); w,h=imgbase.size
    def project(P):
        q=P-loc; return np.c_[w/2+(q@right)/scale*w,h/2-(q@up)/scale*h]
    rows=[]
    for rings in (1,2,3,4,6,8):
        support=set(int(x) for x in tri); frontier=set(support)
        for _ in range(rings):
            nxt=set().union(*(adjacency[i] for i in frontier))-support; support.update(nxt); frontier=nxt
        support=np.asarray(sorted(support-set(int(x) for x in stationary)),np.int32); b=np.r_[support,stationary].astype(np.int32); bc=V[b].copy(); bc[:len(support)]+=requested
        data=igl.ARAPData(); data.energy=igl.ARAP_ENERGY_TYPE_ELEMENTS; data.max_iter=100; t=time.perf_counter(); igl.arap_precomputation(V,F,3,b,data); U=igl.arap_solve(bc,data,V.copy()); runtime=time.perf_counter()-t
        achieved=(bary[:,None]*U[tri]).sum(0)-(bary[:,None]*V[tri]).sum(0); err=float(np.linalg.norm(achieved-requested)/reqmag); delta=U-V
        tri_set=set(int(x) for x in tri); neigh=set()
        for face in F:
            if tri_set.intersection(int(x) for x in face): neigh.update(int(x) for x in face)
        neigh-=tri_set; neigh-=set(int(x) for x in stationary); max_neigh=max((float(np.linalg.norm(delta[i])) for i in neigh),default=0.0)
        base=np.cross(V[F[:,1]]-V[F[:,0]],V[F[:,2]]-V[F[:,0]]); new=np.cross(U[F[:,1]]-U[F[:,0]],U[F[:,2]]-U[F[:,0]]); a0=np.linalg.norm(base,axis=1);a1=np.linalg.norm(new,axis=1); dots=np.einsum('ij,ij->i',base,new); inv=np.where(dots<0)[0].astype(int); collapsed=np.where(a1<a0*1e-4)[0].astype(int)
        edge_set=set();
        for face in F:
            for i,j in ((face[0],face[1]),(face[1],face[2]),(face[2],face[0])): edge_set.add(tuple(sorted((int(i),int(j)))))
        strain=max((abs(float(np.linalg.norm(U[i]-U[j])/max(np.linalg.norm(V[i]-V[j]),1e-20)-1)) for i,j in edge_set),default=0.0)
        row={'model':name,'supportRings':rings,'supportControlCount':len(support),'patchVertices':len(V),'patchTriangles':len(F),'landmarkRelativeError':err,'requestedMagnitude':reqmag,'achievedMagnitude':float(np.linalg.norm(achieved)),'maxNeighborMovement':max_neigh,'neighborRatio':max_neigh/reqmag,'invertedTriangles':int(len(inv)),'invertedTriangleIds':inv.tolist(),'collapsedTriangles':int(len(collapsed)),'maximumEdgeStrain':strain,'finiteCoordinates':bool(np.isfinite(U).all()),'runtimeSeconds':runtime,'formerTriangle11505Inverted':bool(11505 in set(inv)),'pass':bool(err<=.05 and max_neigh>=.1*reqmag and len(inv)==0 and len(collapsed)==0 and np.isfinite(U).all())}
        rows.append(row)
        if rings==8:
            img=imgbase.copy(); p0,p1=project(V),project(U); d=ImageDraw.Draw(img)
            for face in F[::max(1,len(F)//300)]: d.line([tuple(p0[int(i)]) for i in (*face,face[0])],fill=(80,160,255),width=1)
            for i in tri: d.line((tuple(p0[int(i)]),tuple(p1[int(i)])),fill=(255,100,0),width=3)
            m0=project(((bary[:,None]*V[tri]).sum(0))[None,:])[0]; mt=project(target[None,:])[0]; ma=project(((bary[:,None]*U[tri]).sum(0))[None,:])[0]
            d.line((tuple(m0),tuple(mt)),fill=(255,255,0),width=4)
            for p,c in ((m0,(80,160,255)),(mt,(255,255,0)),(ma,(255,60,60))): d.ellipse((p[0]-7,p[1]-7,p[0]+7,p[1]+7),outline=c,width=3)
            d.rectangle((0,0,w,34),fill=(0,0,0)); d.text((8,7),f'{name}: landmark 70, support ring 8',fill='white'); img.save(out/f'{name}-landmark70-support8.png')
    return rows

def main():
    out=arg('--output'); out.mkdir(parents=True,exist_ok=True); rows=[]
    configs=[('female',arg('--female-patch'),arg('--female-goal'),arg('--female-markers'),arg('--female-render'),arg('--female-camera')),('male',arg('--male-patch'),arg('--male-goal'),arg('--male-markers'),arg('--male-render'),arg('--male-camera'))]
    for c in configs: rows.extend(solve(*c,out))
    report={'solver':'official libigl arap_precomputation/arap_solve','landmarkId':70,'supportRings':[1,2,3,4,6,8],'sameAlgorithm':True,'sourceGeometryModified':False,'results':rows}
    (out/'support-sweep-report.json').write_text(json.dumps(report,indent=2)+'\n'); print(json.dumps(report,indent=2))
if __name__=='__main__': main()
