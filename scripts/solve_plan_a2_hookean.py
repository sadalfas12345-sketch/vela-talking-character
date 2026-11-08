"""Plan A2 quasistatic Hookean stretching solve with exact barycentric targets.

The only physical energy is uniform axial Hookean stretch/compression on the
original mesh edges and explicitly recorded virtual seam springs. The solver
uses a Gauss--Newton linearization and a sparse equality-constrained KKT solve.
The tiny diagonal term is a numerical rigid-mode gauge; it is not a physical
support or regularization energy. Landmark constraints remain exact.
"""
from __future__ import annotations

import argparse
import json
import time
import warnings
from pathlib import Path

import numpy as np
from scipy import sparse
from scipy.sparse.linalg import MatrixRankWarning, spsolve


def constraint_matrix(triangles, bary, local_vertex_count):
    rows = []
    cols = []
    vals = []
    for li, (tri, weights) in enumerate(zip(triangles, bary)):
        for d in range(3):
            row = 3 * li + d
            for vi, w in zip(tri, weights):
                rows.append(row)
                cols.append(3 * int(vi) + d)
                vals.append(float(w))
    return sparse.coo_matrix((vals, (rows, cols)), shape=(3 * len(triangles), 3 * local_vertex_count)).tocsr()


def spring_jacobian(x, edges, rest):
    """Return scalar axial rows, residuals, and zero-rest vector rows."""
    u = x[edges[:, 0]] - x[edges[:, 1]]
    lengths = np.linalg.norm(u, axis=1)
    nz = lengths > 1e-12
    dirs = np.zeros_like(u)
    dirs[nz] = u[nz] / lengths[nz, None]
    rows = []
    cols = []
    vals = []
    residual = []
    row = 0
    for k in np.flatnonzero(nz):
        i, j = map(int, edges[k])
        for d in range(3):
            rows.extend([row, row])
            cols.extend([3 * i + d, 3 * j + d])
            vals.extend([float(dirs[k, d]), -float(dirs[k, d])])
        residual.append(float(lengths[k] - rest[k]))
        row += 1
    # A zero-rest spring is an isotropic Hookean tether. It is represented by
    # three Cartesian residual rows, avoiding an undefined axial direction.
    for k in np.flatnonzero(~nz):
        i, j = map(int, edges[k])
        delta = x[i] - x[j]
        for d in range(3):
            rows.extend([row, row])
            cols.extend([3 * i + d, 3 * j + d])
            vals.extend([1.0, -1.0])
            residual.append(float(delta[d]))
            row += 1
    J = sparse.coo_matrix((vals, (rows, cols)), shape=(row, 3 * len(x))).tocsr()
    return J, np.asarray(residual, dtype=float), lengths


def spring_energy(x, edges, rest):
    lengths = np.linalg.norm(x[edges[:, 0]] - x[edges[:, 1]], axis=1)
    return float(0.5 * np.sum((lengths - rest) ** 2))


def projected_gradient(g, C):
    """Remove equality-constraint reactions from the stationarity residual."""
    if not C.shape[0]:
        return float(np.linalg.norm(g) / max(1.0, np.sqrt(len(g))))
    gram = (C @ C.T).toarray()
    rhs = np.asarray(C @ g).reshape(-1)
    try:
        lam = np.linalg.pinv(gram, rcond=1e-12) @ rhs
        residual = g - C.T @ lam
    except np.linalg.LinAlgError:
        residual = g
    return float(np.linalg.norm(residual) / max(1.0, np.sqrt(len(g))))


def gauge_matrix(neutral):
    """Zero-mean translation/rotation gauge for rigid null modes.

    These rows select the minimum rigid frame relative to neutral; they do not
    pin a surface vertex or add a support energy.  The three rotation rows are
    the linearized angular moment of displacement around the neutral centroid.
    """
    n = len(neutral)
    r = neutral - neutral.mean(axis=0, keepdims=True)
    rows, cols, vals = [], [], []
    # Mean displacement is zero.
    for d in range(3):
        row = d
        for i in range(n):
            rows.append(row); cols.append(3 * i + d); vals.append(1.0 / max(n, 1))
    # Sum(r cross dx) is zero.
    for axis in range(3):
        row = 3 + axis
        for i, (rx, ry, rz) in enumerate(r):
            coeff = ((0.0, -rz, ry), (rz, 0.0, -rx), (-ry, rx, 0.0))[axis]
            for d, value in enumerate(coeff):
                if abs(value) > 0:
                    rows.append(row); cols.append(3 * i + d); vals.append(float(value))
    return sparse.coo_matrix((vals, (rows, cols)), shape=(6, 3 * n)).tocsr()


def solve_component(x0, edges, rest, triangles, bary, target, max_iter, residual_tol):
    x = x0.copy()
    n = len(x)
    C_landmark = constraint_matrix(triangles, bary, n)
    G = gauge_matrix(x0)
    C = sparse.vstack((C_landmark, G), format="csr")
    ctarget = np.concatenate((target.reshape(-1), np.zeros(6)))
    gauge_state = G @ (x.reshape(-1) - x0.reshape(-1))
    initial_res = max(float(np.max(np.abs(C_landmark @ x.reshape(-1) - target.reshape(-1)))) if C_landmark.shape[0] else 0.0, float(np.max(np.abs(gauge_state))))
    status = "converged"
    iterations = 0
    warnings_seen = []
    for it in range(max_iter):
        J, r, lengths = spring_jacobian(x, edges, rest)
        K = (J.T @ J).tocsr()
        g = J.T @ r
        # Numerical gauge only: selects one equilibrium among rigidly
        # equivalent states without adding a physical support force.
        diag = K.diagonal()
        scale = float(np.median(diag[diag > 0])) if np.any(diag > 0) else 1.0
        K = K + sparse.eye(3 * n, format="csr") * (1e-12 * scale)
        gauge_state = G @ (x.reshape(-1) - x0.reshape(-1))
        if C.shape[0]:
            KKT = sparse.bmat([[K, C.T], [C, None]], format="csc")
            rhs = np.concatenate([-np.asarray(g).reshape(-1), np.concatenate((target.reshape(-1) - C_landmark @ x.reshape(-1), -gauge_state))])
        else:
            KKT = K.tocsc()
            rhs = -np.asarray(g).reshape(-1)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always", MatrixRankWarning)
            sol = spsolve(KKT, rhs)
        warnings_seen.extend(str(w.message) for w in caught)
        if not np.isfinite(sol).all():
            status = "nonfinite_linear_solve"
            break
        dx = np.asarray(sol[: 3 * n]).reshape(n, 3)
        x += dx
        iterations = it + 1
        cres = max(float(np.max(np.abs(C_landmark @ x.reshape(-1) - target.reshape(-1)))) if C_landmark.shape[0] else 0.0, float(np.max(np.abs(G @ (x.reshape(-1) - x0.reshape(-1))))))
        grad_norm = float(np.linalg.norm(J.T @ r) / max(1.0, np.sqrt(len(r))))
        step_norm = float(np.max(np.linalg.norm(dx, axis=1)))
        # The projected reaction residual is evaluated once after convergence;
        # computing a dense pseudoinverse inside every component iteration is
        # unnecessary bookkeeping and dominates the multi-component run.
        if cres <= residual_tol and step_norm <= residual_tol:
            break
        if not np.isfinite(x).all():
            status = "nonfinite_state"
            break
    else:
        status = "max_iterations"
    final_cres = max(float(np.max(np.abs(C_landmark @ x.reshape(-1) - target.reshape(-1)))) if C_landmark.shape[0] else 0.0, float(np.max(np.abs(G @ (x.reshape(-1) - x0.reshape(-1))))))
    J, r, lengths = spring_jacobian(x, edges, rest)
    gradient = np.asarray(J.T @ r).reshape(-1)
    projected = projected_gradient(gradient, C)
    return x, {"status": status, "iterations": iterations, "initialConstraintResidual": initial_res, "finalConstraintResidual": final_cres, "springEnergy": spring_energy(x, edges, rest), "maxGradientResidual": float(np.linalg.norm(gradient) / max(1.0, np.sqrt(len(gradient)))), "projectedGradientResidual": projected, "maxStep": float(np.max(np.linalg.norm(x - x0, axis=1))), "minEdgeLength": float(lengths.min()) if len(lengths) else None, "warnings": warnings_seen[-5:]}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--graph", type=Path, required=True)
    p.add_argument("--targets", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--max-frames", type=int, default=121)
    p.add_argument("--substeps", type=int, default=20)
    p.add_argument("--max-iterations", type=int, default=30)
    p.add_argument("--residual-tol", type=float, default=1e-9)
    p.add_argument("--save-positions", action="store_true")
    a = p.parse_args()
    graph = np.load(a.graph)
    V0 = graph["V"].astype(float)
    F = graph["F"].astype(np.int64)
    T = graph["constraintTriangles"].astype(np.int64)
    B = graph["constraintBary"].astype(float)
    original_edges = graph["edgeSprings"].astype(np.int64)
    original_rest = graph["edgeRestLengths"].astype(float)
    virtual_edges = graph["virtualSprings"].astype(np.int64)
    virtual_rest = graph["virtualRestLengths"].astype(float)
    edges = np.vstack((original_edges, virtual_edges))
    rest = np.concatenate((original_rest, virtual_rest))
    targets_data = np.load(a.targets)
    targets = targets_data["targets"].astype(float)[: a.max_frames]
    if len(targets) == 0:
        raise RuntimeError("No targets")
    # Solve each physically disconnected component as its own sparse KKT
    # block.  This avoids a large fill-in-heavy global factorization while
    # preserving exactly the same independent Hookean equilibria.
    graph_edges = np.vstack((F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]], virtual_edges))
    conn = sparse.coo_matrix((np.ones(len(graph_edges)), (graph_edges[:, 0], graph_edges[:, 1])), shape=(len(V0), len(V0))).tocsr()
    from scipy.sparse.csgraph import connected_components
    component_count, labels = connected_components(conn, directed=False)
    by_component = [[] for _ in range(component_count)]
    for li, tri in enumerate(T):
        by_component[int(labels[int(tri[0])])].append(li)
    vertex_lists = [np.flatnonzero(labels == ci) for ci in range(component_count)]
    local_maps = []
    edge_lists = []
    for ci, verts in enumerate(vertex_lists):
        remap = -np.ones(len(V0), dtype=np.int64)
        remap[verts] = np.arange(len(verts))
        eidx = np.all(np.isin(edges, verts), axis=1)
        edge_lists.append((remap[edges[eidx]], rest[eidx]))
        local_maps.append(remap)
    x = V0.copy()
    frame_metrics = []
    saved = []
    total_start = time.perf_counter()
    failure = None
    frame_limit = len(targets)
    for fi in range(frame_limit):
        prev_target = targets[fi - 1] if fi else targets[0]
        current_target = targets[fi]
        steps = 1 if fi == 0 else max(1, a.substeps)
        for si in range(1, steps + 1):
            alpha = si / steps
            desired = prev_target + alpha * (current_target - prev_target) if fi else current_target
            target_frame_start = time.perf_counter()
            comp_stats = []
            for ci, lm_ids in enumerate(by_component):
                if not lm_ids:
                    continue
                verts = vertex_lists[ci]
                local_tri = local_maps[ci][T[lm_ids]]
                local_edges, local_rest = edge_lists[ci]
                solved, stat = solve_component(x[verts], local_edges, local_rest, local_tri, B[lm_ids], desired[lm_ids], a.max_iterations, a.residual_tol)
                x[verts] = solved
                comp_stats.append(stat)
                if stat["status"] != "converged" and stat["finalConstraintResidual"] > a.residual_tol:
                    failure = {"frame": fi, "substep": si, "component": ci, **stat}
                    break
            if failure:
                break
            if fi == 0 or si == steps:
                frame_metrics.append({"frame": fi, "substep": si, "elapsedSeconds": time.perf_counter() - target_frame_start, "simulationComponents": int(component_count), "maxConstraintResidual": max((s["finalConstraintResidual"] for s in comp_stats), default=0.0), "maxGradientResidual": max((s["maxGradientResidual"] for s in comp_stats), default=0.0), "maxProjectedGradientResidual": max((s.get("projectedGradientResidual", 0.0) for s in comp_stats), default=0.0), "maxIterations": max((s["iterations"] for s in comp_stats), default=0), "statuses": sorted(set(s["status"] for s in comp_stats))})
        if failure:
            break
        if a.save_positions:
            saved.append(x.copy())
    report = {"solver": "uniform Hookean stretch/compression on original and recorded virtual seam edges; sparse Gauss-Newton equality-constrained KKT", "physicalTerms": ["original edge stretching", "virtual seam edge stretching"], "excludedTerms": ["bending", "volume", "support stiffness", "ARAP", "gravity", "inertia", "damping"], "numericalGauge": "1e-12 median diagonal added only to select rigidly equivalent equilibrium; not a physical energy", "vertices": len(V0), "triangles": len(F), "landmarks": len(T), "simulationComponents": int(component_count), "framesRequested": frame_limit, "framesSolved": len(frame_metrics), "substepsPerTransition": a.substeps, "runtimeSeconds": time.perf_counter() - total_start, "failure": failure, "frameMetrics": frame_metrics, "finalPositionsOutput": None}
    a.output.parent.mkdir(parents=True, exist_ok=True)
    if saved:
        pos_path = a.output.with_name(a.output.stem + "-positions.npz")
        np.savez_compressed(pos_path, positions=np.asarray(saved), originalPositions=V0)
        report["finalPositionsOutput"] = str(pos_path)
    a.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"framesSolved": len(frame_metrics), "framesRequested": frame_limit, "failure": failure, "runtimeSeconds": report["runtimeSeconds"]}, indent=2))
    if failure:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
