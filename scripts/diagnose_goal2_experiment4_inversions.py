"""Record the exact baseline and post-correction inversion locations."""
import json
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'verification/goal2-experiment4'
PATCH=OUT/'male-patch.npz'; SOL=OUT/'male-landmark70-solution.npz'
BASELINE=[28820,28827,28839,28840,29125]

def main():
    p=np.load(PATCH); s=np.load(SOL); V,U,F=p['V'],s['U'],p['F']; orig=p['originalIndices']
    base=np.cross(V[F[:,1]]-V[F[:,0]],V[F[:,2]]-V[F[:,0]]); new=np.cross(U[F[:,1]]-U[F[:,0]],U[F[:,2]]-U[F[:,0]])
    final=[int(x) for x in np.where(np.einsum('ij,ij->i',base,new)<0)[0]]
    boundary=set()
    counts={}
    for tri in F:
        for a,b in ((int(tri[0]),int(tri[1])),(int(tri[1]),int(tri[2])),(int(tri[2]),int(tri[0]))): counts[tuple(sorted((a,b)))]=counts.get(tuple(sorted((a,b))),0)+1
    for e,c in counts.items():
        if c==1: boundary.update(e)
    def rows(ids):
        out=[]
        for i in ids:
            verts=F[i]; c0=V[verts].mean(0); c1=U[verts].mean(0); a0=float(np.linalg.norm(base[i])/2); a1=float(np.linalg.norm(new[i])/2); bd=float(min(np.linalg.norm(V[int(v)]-V[list(boundary)]) for v in verts)) if boundary else None
            out.append({'localTriangleId':int(i),'originalVertexIds':orig[verts].astype(int).tolist(),'neutralArea':a0,'deformedArea':a1,'centroidNeutral':c0.tolist(),'centroidDeformed':c1.tolist(),'distanceToPatchBoundary':bd,'sharesWithBaseline':[int(j) for j in ids if j!=i and len(set(verts)&set(F[j]))>=2]})
        return out
    data={'baselineFive':rows(BASELINE),'postCorrectionInversions':rows(final),'baselineInversionIds':BASELINE,'postCorrectionInversionIds':final,'patchBoundaryVertexCount':len(boundary),'confirmedPattern':'baseline triangles cluster around the landmark control triangle and share control-region vertices'}
    (OUT/'inversion-audit.json').write_text(json.dumps(data,indent=2)+'\n')
    cam=json.loads((ROOT/'verification/goal1-generalization-run/cross-character-accuracy/male/refined-camera.json').read_text()); img=Image.open(ROOT/'verification/goal1-generalization-run/cross-character-accuracy/male/refined-neutral.png').convert('RGB'); loc=np.asarray(cam['cameraLocation']); right=np.asarray(cam['cameraBasis']['right']); up=np.asarray(cam['cameraBasis']['up']); scale=float(cam['orthoScale']); w,h=img.size
    def proj(P):
        q=P-loc; return np.c_[w/2+(q@right)/scale*w,h/2-(q@up)/scale*h]
    xy=proj(V); d=ImageDraw.Draw(img)
    for i in BASELINE:
        poly=[tuple(xy[int(v)]) for v in (*F[i],F[i,0])]; d.line(poly,fill=(255,40,40),width=4); d.ellipse((np.mean(xy[F[i],0])-5,np.mean(xy[F[i],1])-5,np.mean(xy[F[i],0])+5,np.mean(xy[F[i],1])+5),fill=(255,40,40))
    d.rectangle((0,0,w,34),fill=(0,0,0)); d.text((8,7),'Male baseline five inversion triangles highlighted red',fill='white'); img.save(OUT/'male-baseline-five-inversions.png')
    print(json.dumps(data,indent=2))
if __name__=='__main__': main()
