"""Test landmark-105 ARAP with geodesic regions normalized by eye width."""
from __future__ import annotations

import heapq
import json
import sys
import time
from collections import defaultdict
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
    return np.asarray(sorted({v for e, c in counts.items() if c == 1 for v in e}), dtype=np.int32)


def dijkstra(v, f, seeds):
    adj = defaultdict(dict)
    for t in f:
        for a, b in ((int(t[0]), int(t[1])), (int(t[1]), int(t[2])), (int(t[2]), int(t[0]))):
            w = float(np.linalg.norm(v[a] - v[b]))
            adj[a][b] = min(adj[a].get(b, w), w); adj[b][a] = min(adj[b].get(a, w), w)
    dist = np.full(len(v), np.inf); heap = []
    for s in seeds:
        dist[int(s)] = 0.0; heapq.heappush(heap, (0.0, int(s)))
    while heap:
        d, x = heapq.heappop(heap)
        if d != dist[x]: continue
        for y, w in adj[x].items():
            nd = d + w
            if nd < dist[y]: dist[y] = nd; heapq.heappush(heap, (nd, y))
    return dist


def solve(v, f, boundary, tri, bary, target, bridge):
    aeq = np.zeros((1, len(v)), dtype=float); aeq[0, tri] = bary
    return bridge.solve(v, f, boundary, aeq, target[None, :], v.copy(), 100, 0.0, np.empty((0, 3), dtype=float))


def metrics(v, f, u, boundary, tri, bary, neutral, target, requested):
    n0 = np.cross(v[f[:, 1]] - v[f[:, 0]], v[f[:, 2]] - v[f[:, 0]])
    n1 = np.cross(u[f[:, 1]] - u[f[:, 0]], u[f[:, 2]] - u[f[:, 0]])
    a0 = np.linalg.norm(n0, axis=1); a1 = np.linalg.norm(n1, axis=1)
    folds = np.flatnonzero(np.einsum("ij,ij->i", n0, n1) <= 0).astype(int)
    collapsed = np.flatnonzero(a1 <= a0 * 1e-4).astype(int)
    edges = np.unique(np.sort(np.vstack((f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]])), axis=1), axis=0)
    l0 = np.linalg.norm(v[edges[:, 0]] - v[edges[:, 1]], axis=1); l1 = np.linalg.norm(u[edges[:, 0]] - u[edges[:, 1]], axis=1)
    strain = np.abs(l1 / np.maximum(l0, 1e-20) - 1.0)
    actual = (bary[:, None] * u[tri]).sum(axis=0) - neutral
    bd = np.linalg.norm(u[boundary] - v[boundary], axis=1)
    return {
        "landmarkRelativeError": float(np.linalg.norm(actual - requested) / max(np.linalg.norm(requested), 1e-20)),
        "constraintResidual": float(np.linalg.norm(actual - requested)),
        "newGenuineFolds": int(len(folds)), "foldTriangleIds": folds.tolist(),
        "collapsedTriangles": int(len(collapsed)), "collapsedTriangleIds": collapsed.tolist(),
        "maximumEdgeStrain": float(np.max(strain)), "p95EdgeStrain": float(np.percentile(strain, 95)),
        "maximumBoundaryDisplacement": float(np.max(bd)) if len(bd) else 0.0,
        "finite": bool(np.isfinite(u).all()),
    }


def one_model(model, patch_path, goal_path, marker_path, out, bridge):
    p = np.load(patch_path); v=p["V"].astype(float); f=p["F"].astype(np.int32); orig=p["originalIndices"].astype(int); lookup={int(x):i for i,x in enumerate(orig)}
    records={int(r["index"]):r for r in json.loads(goal_path.read_text())["records"]}; mk=json.loads(marker_path.read_text()); peak=np.asarray(mk["samples"]["100"],float); neutral_m=np.asarray(mk["neutral"],float)
    rec=records[105]; tri=np.asarray([lookup[int(x)] for x in rec["triangleVertexIndices"]],dtype=np.int32); bary=np.asarray(rec["barycentricCoordinates"],float); neutral=(bary[:,None]*v[tri]).sum(0); requested=peak[105]-neutral_m[105]; target=neutral+requested; eye=float(np.linalg.norm(np.asarray(records[33]["meshXYZ"])-np.asarray(records[263]["meshXYZ"])))
    distances=dijkstra(v,f,tri); radii=[.10,.20,.30,.50]; rows=[]
    for radius in radii:
        threshold=radius*eye; selected=np.flatnonzero(distances<=threshold).astype(np.int32); selected_set=set(selected.tolist()); face_mask=np.all(np.isin(f,selected),axis=1); faces=f[face_mask]; remap={int(x):i for i,x in enumerate(selected)}; faces_local=np.asarray([[remap[int(x)] for x in t] for t in faces],dtype=np.int32); tri_local=np.asarray([remap[int(x)] for x in tri],dtype=np.int32); vv=v[selected]; boundary=boundary_vertices(faces_local)
        t0=time.perf_counter()
        try:
            u=solve(vv,faces_local,boundary,tri_local,bary,target,bridge)
            runtime=time.perf_counter()-t0; m=metrics(vv,faces_local,u,boundary,tri_local,bary,neutral,target,requested)
            row={"radiusEyeWidth":radius,"geodesicThreshold":threshold,"actualSelectedGeodesicRadius":float(np.max(distances[selected])) if len(selected) else 0.0,"selectedVertices":int(len(selected)),"selectedTriangles":int(len(faces_local)),"boundaryVertices":int(len(boundary)),"runtimeSeconds":runtime,"originalSelectedVertexIds":orig[selected].tolist(),"originalFoldTriangleIds":faces_local[m["foldTriangleIds"]].tolist() if m["foldTriangleIds"] else [],**m}
            np.savez_compressed(out/f"{model}-radius-{radius:.2f}.npz",VNeutral=vv,VDeformed=u,F=faces_local,originalIndices=orig[selected],boundary=boundary,foldIds=np.asarray(m["foldTriangleIds"],dtype=np.int32))
        except RuntimeError as exc:
            row={"radiusEyeWidth":radius,"geodesicThreshold":threshold,"actualSelectedGeodesicRadius":float(np.max(distances[selected])) if len(selected) else 0.0,"selectedVertices":int(len(selected)),"selectedTriangles":int(len(faces_local)),"boundaryVertices":int(len(boundary)),"runtimeSeconds":time.perf_counter()-t0,"solverError":str(exc),"valid":False}
        rows.append(row)
        if radius in (.20,.50):
            np.savez_compressed(out/f"{model}-region-{radius:.2f}.npz",V=vv,F=faces_local,originalIndices=orig[selected],boundary=boundary)
    return {"model":model,"interocularWidth":eye,"landmark105TriangleVertexIds":rec["triangleVertexIndices"],"requestedDisplacement":requested.tolist(),"requestedMagnitude":float(np.linalg.norm(requested)),"patchVertices":int(len(v)),"patchTriangles":int(len(f)),"maxPatchGeodesicDistance":float(np.max(distances[np.isfinite(distances)])),"results":rows}


def main():
    import libigl_barycentric_bridge as bridge
    out=arg("--output"); out.mkdir(parents=True,exist_ok=True)
    report={"solver":"official libigl ARAP with exact landmark-105 barycentric constraint and fixed generated boundary","regionSelection":"edge-length Dijkstra geodesic distance from landmark attachment triangle, normalized by measured interocular width","sameAlgorithm":True,"models":[one_model("female",arg("--female-patch"),arg("--female-goal"),arg("--female-markers"),out,bridge),one_model("male",arg("--male-patch"),arg("--male-goal"),arg("--male-markers"),out,bridge)]}
    (out/"geodesic-region-report.json").write_text(json.dumps(report,indent=2)+"\n"); print(json.dumps(report,indent=2))

if __name__=="__main__": main()
