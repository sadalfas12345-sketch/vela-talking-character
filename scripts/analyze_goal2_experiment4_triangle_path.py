"""Analyze the existing one-ring ARAP result over 21 neutral-to-final samples."""
import json
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw

def angle(a,b):
    return float(np.degrees(np.arccos(np.clip((a@b)/max(np.linalg.norm(a)*np.linalg.norm(b),1e-20),-1,1))))

def normals(P,F):
    n=np.cross(P[F[:,1]]-P[F[:,0]],P[F[:,2]]-P[F[:,0]])
    return n/np.maximum(np.linalg.norm(n,axis=1)[:,None],1e-20)

def signed_side(P, edge, opposite, reference_normal):
    a, b = edge
    return float(np.dot(np.cross(P[b] - P[a], P[opposite] - P[a]), reference_normal))

def main():
    root=Path(__file__).resolve().parents[1]; out=root/'verification/goal2-experiment4'; p=np.load(out/'male-patch.npz'); s=np.load(out/'male-landmark70-solution.npz'); V,U,F=p['V'],s['U'],s['F']; tri_id=11505; tri=F[tri_id]; orig=p['originalIndices']; rec={int(r['index']):r for r in json.loads((root/'verification/goal1-generalization-run/cross-character-accuracy/male/refined/raycast-report.json').read_text())['records']}[70]
    N0=normals(V,F); n0=N0[tri_id]; area0=float(np.linalg.norm(np.cross(V[tri[1]]-V[tri[0]],V[tri[2]]-V[tri[0]]))/2); neighbors=[i for i,face in enumerate(F) if i!=tri_id and len(set(map(int,face))&set(map(int,tri)))>=2]
    neighbor_id=neighbors[0]; shared=tuple(sorted(set(map(int,tri)) & set(map(int,F[neighbor_id])))); opposite_tri=next(int(v) for v in tri if int(v) not in shared); opposite_neighbor=next(int(v) for v in F[neighbor_id] if int(v) not in shared); side0=[signed_side(V,shared,opposite_tri,n0),signed_side(V,shared,opposite_neighbor,n0)]
    rows=[]
    for alpha in np.linspace(0,1,21):
        P=V+alpha*(U-V); N=normals(P,F); area=float(np.linalg.norm(np.cross(P[tri[1]]-P[tri[0]],P[tri[2]]-P[tri[0]]))/2); pair=[angle(N[tri_id],N[i]) for i in neighbors]; sides=[signed_side(P,shared,opposite_tri,n0),signed_side(P,shared,opposite_neighbor,n0)]; rows.append({'alpha':float(alpha),'area':area,'areaRatio':area/area0,'normalDotNeutral':float(N[tri_id]@n0),'normalRotationDegrees':angle(N[tri_id],n0),'neighborDihedralDegrees':pair,'neighborDihedralMin':min(pair),'neighborDihedralMax':max(pair),'sharedEdgeSides':sides,'sharedEdgeOppositeSideProduct':float(sides[0]*sides[1]),'orientationAgainstNeutral':float(np.dot(np.cross(P[tri[1]]-P[tri[0]],P[tri[2]]-P[tri[0]]),np.cross(V[tri[1]]-V[tri[0]],V[tri[2]]-V[tri[0]]))),'finite':bool(np.isfinite(P).all())})
    first_cross=next((x['alpha'] for x in rows if x['sharedEdgeOppositeSideProduct']>=0),None)
    data={'triangleLocalId':tri_id,'originalVertexIds':orig[tri].astype(int).tolist(),'neighborTriangleIds':neighbors,'neighborCount':len(neighbors),'sharedEdge':list(shared),'oppositeVertices':[opposite_tri,opposite_neighbor],'neutralSharedEdgeSides':side0,'neutralArea':area0,'neutralVertices':V[tri].tolist(),'finalVertices':U[tri].tolist(),'vertexDisplacements':(U[tri]-V[tri]).tolist(),'samples':rows,'classificationEvidence':{'allAreasPositive':all(x['area']>0 for x in rows),'allFinite':all(x['finite'] for x in rows),'neighborDihedralsRemainDefined':True,'normalDotNegativeSamples':sum(x['normalDotNeutral']<0 for x in rows),'sharedEdgeSideCrossingDetected':first_cross is not None,'firstSampleAtOrAfterCrossing':first_cross}}
    (out/'triangle11505-path-analysis.json').write_text(json.dumps(data,indent=2)+'\n')
    cam=json.loads((root/'verification/goal1-generalization-run/cross-character-accuracy/male/refined-camera.json').read_text()); img=Image.open(root/'verification/goal1-generalization-run/cross-character-accuracy/male/refined-neutral.png').convert('RGB'); loc=np.asarray(cam['cameraLocation']); right=np.asarray(cam['cameraBasis']['right']); up=np.asarray(cam['cameraBasis']['up']); scale=float(cam['orthoScale']); q=V-loc; xy=np.c_[img.width/2+(q@right)/scale*img.width,img.height/2-(q@up)/scale*img.height]; d=ImageDraw.Draw(img); 
    for i in neighbors: d.line([tuple(xy[int(v)]) for v in (*F[i],F[i,0])],fill=(255,180,0),width=2)
    d.line([tuple(xy[int(v)]) for v in (*tri,tri[0])],fill=(255,30,30),width=4); c=xy[tri].mean(0); d.ellipse((c[0]-8,c[1]-8,c[0]+8,c[1]+8),outline=(255,30,30),width=3); d.rectangle((0,0,img.width,34),fill=(0,0,0)); d.text((8,7),'Male triangle 11505 red, edge neighbors orange',fill='white'); img.save(out/'male-triangle11505-neighbors.png'); print(json.dumps(data,indent=2))
if __name__=='__main__': main()
