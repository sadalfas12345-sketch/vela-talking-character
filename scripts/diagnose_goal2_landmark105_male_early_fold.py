"""Geometry audit for the different landmark-105 fold onsets."""
from __future__ import annotations

import json
import sys
import time
from collections import defaultdict, deque
from pathlib import Path

import numpy as np


def arg(name: str) -> Path:
    a = sys.argv[1:]
    return Path(a[a.index(name) + 1]).resolve()


def boundary_vertices(faces):
    counts = defaultdict(int)
    for t in faces:
        for a, b in ((t[0], t[1]), (t[1], t[2]), (t[2], t[0])):
            counts[tuple(sorted((int(a), int(b))))] += 1
    return np.asarray(sorted({x for e, c in counts.items() if c == 1 for x in e}), dtype=np.int32)


def graph_hops(f, seeds, hops):
    adj = defaultdict(set)
    for t in f:
        a, b, c = map(int, t)
        adj[a].update((b, c)); adj[b].update((a, c)); adj[c].update((a, b))
    seen = set(map(int, seeds)); q = deque((int(x), 0) for x in seeds)
    while q:
        v, d = q.popleft()
        if d >= hops: continue
        for n in adj[v]:
            if n not in seen:
                seen.add(n); q.append((n, d + 1))
    return np.asarray(sorted(seen), dtype=np.int32), adj


def solve_target(v, f, boundary, tri, bary, target, bridge):
    aeq = np.zeros((1, len(v)), dtype=float); aeq[0, tri] = bary
    return bridge.solve(v, f, boundary, aeq, target[None, :], v.copy(), 100, 0.0, np.empty((0, 3), dtype=float))


def local_metrics(v, f, tri, boundary, landmark):
    local, adj = graph_hops(f, tri, 5)
    local_set = set(local.tolist())
    edges = set()
    for t in f:
        for a, b in ((t[0], t[1]), (t[1], t[2]), (t[2], t[0])):
            if int(a) in local_set and int(b) in local_set: edges.add(tuple(sorted((int(a), int(b)))))
    lengths = np.asarray([np.linalg.norm(v[a] - v[b]) for a, b in edges])
    pair = v[local]
    diameter = float(np.linalg.norm(pair[:, None, :] - pair[None, :, :], axis=2).max())
    bd = float(np.min(np.linalg.norm(v[boundary] - landmark, axis=1)))
    return {
        "fiveHopVertices": int(len(local)),
        "fiveHopEdges": int(len(edges)),
        "averageLocalEdgeLength": float(np.mean(lengths)),
        "minimumLocalEdgeLength": float(np.min(lengths)),
        "localRegionDiameter": diameter,
        "landmarkToBoundaryDistance": bd,
    }


def tri_geometry(v, f, fid):
    t = f[fid]; x = v[t]; n = np.cross(x[1] - x[0], x[2] - x[0])
    return {"vertexLocalIds": t.astype(int).tolist(), "edgeLengths": [float(np.linalg.norm(x[1]-x[0])), float(np.linalg.norm(x[2]-x[1])), float(np.linalg.norm(x[0]-x[2]))], "area": float(np.linalg.norm(n) * .5), "normal": (n / max(np.linalg.norm(n), 1e-30)).tolist()}


def neighbors(f, fid):
    s = set(map(int, f[fid])); out = []
    for i, t in enumerate(f):
        if i != fid and len(s.intersection(map(int, t))) >= 2: out.append(i)
    return out


def onset_geometry(v0, vu, f, fid):
    a = tri_geometry(v0, f, fid); b = tri_geometry(vu, f, fid)
    n0 = np.asarray(a["normal"]); n1 = np.asarray(b["normal"])
    ns = {"triangle": fid, "neutral": a, "onset": b, "vertexDisplacements": np.linalg.norm(vu[f[fid]]-v0[f[fid]], axis=1).tolist(), "triangleNormalDot": float(np.dot(n0,n1)), "neighborDihedral": []}
    for j in neighbors(f, fid):
        nj0 = np.asarray(tri_geometry(v0, f, j)["normal"]); nj1 = np.asarray(tri_geometry(vu, f, j)["normal"])
        ns["neighborDihedral"].append({"neighborTriangle": j, "neutralNormalDot": float(np.dot(n0,nj0)), "onsetNormalDot": float(np.dot(n1,nj1))})
    return ns


def run_model(model, patch, goal, markers, sweep, out, bridge):
    p = np.load(patch); v=p["V"].astype(float); f=p["F"].astype(np.int32); orig=p["originalIndices"].astype(int); lookup={int(x):i for i,x in enumerate(orig)}
    records={int(r["index"]):r for r in json.loads(goal.read_text())["records"]}; mk=json.loads(markers.read_text()); peak=np.asarray(mk["samples"]["100"],float); neutral_m=np.asarray(mk["neutral"],float)
    rec=records[105]; tri=np.asarray([lookup[int(x)] for x in rec["triangleVertexIndices"]],dtype=np.int32); bary=np.asarray(rec["barycentricCoordinates"],float); neutral=(bary[:,None]*v[tri]).sum(0); req=peak[105]-neutral_m[105]; target=neutral+req; boundary=boundary_vertices(f); eye=float(np.linalg.norm(np.asarray(records[33]["meshXYZ"])-np.asarray(records[263]["meshXYZ"])))
    lm=local_metrics(v,f,tri,boundary,neutral); lm.update({"interocularWidth":eye,"requestedDisplacement":req.tolist(),"requestedMagnitude":float(np.linalg.norm(req)),"movementOverAverageLocalEdge":float(np.linalg.norm(req)/lm["averageLocalEdgeLength"]),"movementOverMinimumLocalEdge":float(np.linalg.norm(req)/lm["minimumLocalEdgeLength"]),"movementOverRegionDiameter":float(np.linalg.norm(req)/lm["localRegionDiameter"]),"boundaryDistanceOverEyeWidth":float(lm["landmarkToBoundaryDistance"]/eye)})
    att=tri_geometry(v,f, next(i for i,t in enumerate(f) if set(t)==set(tri))) if False else {"vertexOriginalIds":orig[tri].tolist(),"edgeLengths":tri_geometry(v,f,next(i for i,t in enumerate(f) if set(t)==set(tri)))["edgeLengths"] if any(set(t)==set(tri) for t in f) else None}
    onset=int(next(x["firstFoldOnsetPercent"] for x in sweep["models"] if x["model"]==model)); prev=max(0,onset-1)
    states={}
    for pct in (prev,onset):
        sol=solve_target(v,f,boundary,tri,bary,neutral+(pct/100)*req,bridge); states[pct]=sol
    first=next(x for x in next(m for m in sweep["models"] if m["model"]==model)["results"] if x["intensityPercent"]==onset)
    fold_detail=[]
    for d in first["foldedTriangles"]:
        fid=int(d["localTriangleId"]); fold_detail.append({"localTriangleId":fid,"originalVertexIds":orig[f[fid]].tolist(),"distanceFromLandmark":d["distanceFromLandmark"],"preOnset":onset_geometry(states[prev],states[prev],f,fid) if False else onset_geometry(v,states[prev],f,fid),"onset":onset_geometry(v,states[onset],f,fid)})
    return {"model":model,"landmark105":lm,"attachment":att,"firstFoldOnsetPercent":onset,"preOnsetPercent":prev,"preOnsetTargetAccuracy":float(np.linalg.norm((bary[:,None]*states[prev][tri]).sum(0)-neutral-(prev/100)*req)),"foldedTriangles":fold_detail}


def main():
    import libigl_barycentric_bridge as bridge
    out=arg("--output"); out.mkdir(parents=True,exist_ok=True); sweep=json.loads((arg("--sweep")/"landmark105-intensity-sweep.json").read_text())
    result={"models":[run_model("female",arg("--female-patch"),arg("--female-goal"),arg("--female-markers"),sweep,out,bridge),run_model("male",arg("--male-patch"),arg("--male-goal"),arg("--male-markers"),sweep,out,bridge)],"hypothesisTest":"The male has a larger displacement relative to local edge scale; a temporary male target is tested at the female movement/local-edge ratio.","sameSolver":True}
    fm=result["models"][0]["landmark105"]; mm=result["models"][1]["landmark105"]; scale=(fm["movementOverAverageLocalEdge"]/mm["movementOverAverageLocalEdge"])
    # One controlled test: keep the male geometry and solver unchanged, but use a
    # temporary target with the female movement/average-local-edge ratio.
    p=np.load(arg("--male-patch")); v=p["V"].astype(float); f=p["F"].astype(np.int32); orig=p["originalIndices"].astype(int); records={int(r["index"]):r for r in json.loads(arg("--male-goal").read_text())["records"]}; lookup={int(x):i for i,x in enumerate(orig)}; rec=records[105]; tri=np.asarray([lookup[int(x)] for x in rec["triangleVertexIndices"]],dtype=np.int32); bary=np.asarray(rec["barycentricCoordinates"],float); neutral=(bary[:,None]*v[tri]).sum(0); b=boundary_vertices(f); actual=np.asarray(json.loads(arg("--male-markers").read_text())["samples"]["100"],float)[105]-neutral; temp=actual*scale; sol=solve_target(v,f,b,tri,bary,neutral+.25*temp,bridge); n=np.cross(v[f[:,1]]-v[f[:,0]],v[f[:,2]]-v[f[:,0]]); q=np.cross(sol[f[:,1]]-sol[f[:,0]],sol[f[:,2]]-sol[f[:,0]]); folds=np.flatnonzero(np.einsum("ij,ij->i",n,q)<=0).astype(int); result["controlledHypothesisTest"]={"maleIntensityPercent":25,"scaleFactorAppliedToMaleTarget":float(scale),"temporaryTargetDisplacement":(.25*temp).tolist(),"originalTargetDisplacementAt25Percent":(.25*actual).tolist(),"foldCount":int(len(folds)),"foldTriangleIds":folds.tolist(),"supportsHypothesis":bool(len(folds)==0)}
    (out/"landmark105-male-early-fold-audit.json").write_text(json.dumps(result,indent=2)+"\n"); print(json.dumps(result,indent=2))

if __name__=="__main__": main()
