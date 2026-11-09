"""Plan A5 Hookean solve with an abstract fixed-anchor support layer.

This reuses Plan A4's sparse affine hard-constraint projection and projected
nonlinear line-search update.  The only added energy is the requested fixed
anchor spring family.  Anchors are solver-only points and never replace source
vertices or triangles.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import time
from pathlib import Path

import numpy as np
from scipy import sparse
from scipy.sparse.csgraph import connected_components
from scipy.sparse.linalg import LinearOperator, lsqr


def load_a4():
    path = Path(__file__).with_name("solve_plan_a4_projected_hookean.py")
    spec = importlib.util.spec_from_file_location("plan_a4_for_a5", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod, mod.load_base()


def weighted_free_jacobian(base, x, edges, rest, x0, weight=1.0):
    if len(edges) == 0 or weight <= 0.0:
        return sparse.csr_matrix((0, 3 * len(x))), np.zeros(0), np.zeros(0)
    J, r, lengths = base.spring_jacobian(x, edges, rest, x0)
    scale = float(np.sqrt(weight))
    return J * scale, r * scale, lengths


def fixed_anchor_jacobian(base, x, anchors, surface, anchor_ids, rest, weight):
    if len(surface) == 0 or weight <= 0.0:
        return sparse.csr_matrix((0, 3 * len(x))), np.zeros(0), np.zeros(0)
    n = len(x)
    aug = np.vstack((x, anchors))
    ref = aug.copy()
    E = np.column_stack((surface, n + anchor_ids)).astype(np.int64)
    J_aug, r, lengths = base.spring_jacobian(aug, E, rest, ref)
    J = J_aug[:, : 3 * n]
    scale = float(np.sqrt(weight))
    return J * scale, r * scale, lengths


def fixed_anchor_energy(x, anchors, surface, anchor_ids, rest, weight):
    if len(surface) == 0 or weight <= 0.0:
        return 0.0
    d = x[surface] - anchors[anchor_ids]
    return float(0.5 * weight * np.sum((np.linalg.norm(d, axis=1) - rest) ** 2))


def solve_component(base, x0, edges, rest, triangles, bary, target, support, support_anchors, support_ids, support_rest, support_ratio, max_iter, residual_tol, force_tol, max_backtracks, rank_tolerance, inner_iterations, start=None):
    x0 = np.asarray(x0, dtype=float)
    x = x0.copy() if start is None else np.asarray(start, dtype=float).copy()
    n = len(x)
    C_landmark = base.constraint_matrix(triangles, bary, n)
    full_gauge = base.gauge_matrix(x0)
    G, rigid_rank = base.select_gauge_rows(C_landmark, full_gauge, x0)
    C_full = sparse.vstack((C_landmark, G), format="csr")
    reduction = load_a4()[0].reduce_constraint_rows_sparse(C_full, rank_tolerance)
    C = C_full[reduction["indices"]] if reduction["rank"] else sparse.csr_matrix((0, 3 * n))
    projector = load_a4()[0].SparseConstraintProjector(C)
    target_flat = target.reshape(-1)
    gauge_target = G @ x0.reshape(-1)
    rhs_full = np.concatenate((target_flat - C_landmark @ x.reshape(-1), gauge_target - G @ x.reshape(-1)))
    rhs_keep, compatibility_error = base.reduced_rhs(reduction, rhs_full, max(residual_tol * 10.0, 1e-12))
    if rhs_keep is None:
        return x, {"status": "incompatible_constraints", "compatibilityError": compatibility_error, "iterations": 0}
    correction = projector.solve(rhs_keep)
    x += correction.reshape(n, 3)

    def objective(state):
        free = base.spring_energy(state, edges, rest)
        support_energy = fixed_anchor_energy(state, support_anchors, support, support_ids, support_rest, support_ratio)
        return free + support_energy

    history = [{"iteration": 0, "type": "feasible_projection", "maxStep": float(np.max(np.linalg.norm(correction.reshape(n, 3), axis=1))) if n else 0.0}]
    max_step = history[0]["maxStep"]
    status = "max_iterations"
    started = time.perf_counter()
    for iteration in range(1, max_iter + 1):
        J1, r1, lengths1 = weighted_free_jacobian(base, x, edges, rest, x0, 1.0)
        J2, r2, lengths2 = fixed_anchor_jacobian(base, x, support_anchors, support, support_ids, support_rest, support_ratio)
        J = sparse.vstack((J1, J2), format="csr")
        residual = np.concatenate((r1, r2))
        gradient = np.asarray(J.T @ residual).reshape(-1)
        projected = projector.project(gradient)
        projected_residual = float(np.linalg.norm(projected) / max(1.0, np.sqrt(len(edges) + len(support))))
        hard_error = max(float(np.max(np.abs(C_landmark @ x.reshape(-1) - target_flat))) if C_landmark.shape[0] else 0.0, float(np.max(np.abs(G @ (x.reshape(-1) - x0.reshape(-1))))) if G.shape[0] else 0.0)
        if hard_error <= residual_tol and projected_residual <= force_tol:
            status = "converged"
            history.append({"iteration": iteration - 1, "objective": objective(x), "hardConstraintError": hard_error, "projectedForceResidual": projected_residual, "maxStep": 0.0})
            break
        def fwd(v): return J @ projector.project(v)
        def tr(v): return projector.project(np.asarray(J.T @ v).reshape(-1))
        op = LinearOperator((J.shape[0], 3 * n), matvec=fwd, rmatvec=tr, dtype=float)
        result = lsqr(op, -residual, atol=1e-7, btol=1e-7, iter_lim=inner_iterations)
        direction = projector.project(result[0])
        if not np.isfinite(direction).all() or float(np.dot(projected, direction)) >= -1e-14:
            direction = -projected
        directional = float(np.dot(projected, direction))
        old = objective(x)
        alpha = 1.0
        accepted = False
        for _ in range(max_backtracks + 1):
            trial = (x.reshape(-1) + projector.project(alpha * direction)).reshape(n, 3)
            value = objective(trial)
            if np.isfinite(trial).all() and value <= old + 1e-4 * alpha * directional:
                accepted = True
                x = trial
                break
            alpha *= 0.5
        if not accepted:
            status = "line_search_stagnation"
            break
        step = float(np.max(np.linalg.norm(alpha * projector.project(direction).reshape(n, 3), axis=1)))
        max_step = max(max_step, step)
        history.append({"iteration": iteration, "objective": value, "hardConstraintError": hard_error, "projectedForceResidual": projected_residual, "maxStep": step, "acceptedAlpha": alpha, "lsqrStop": int(result[1]), "lsqrIterations": int(result[2])})
    J1, r1, lengths1 = weighted_free_jacobian(base, x, edges, rest, x0, 1.0)
    J2, r2, lengths2 = fixed_anchor_jacobian(base, x, support_anchors, support, support_ids, support_rest, support_ratio)
    final_projected = projector.project(np.asarray(sparse.vstack((J1, J2), format="csr").T @ np.concatenate((r1, r2))).reshape(-1))
    final_hard = float(np.max(np.abs(C_landmark @ x.reshape(-1) - target_flat))) if C_landmark.shape[0] else 0.0
    return x, {"status": status, "iterations": len(history) - 1, "constraintRank": int(reduction["rank"]), "constraintRows": int(C_full.shape[0]), "rigidConstraintRank": int(rigid_rank), "finalConstraintError": final_hard, "projectedForceResidual": float(np.linalg.norm(final_projected) / max(1.0, np.sqrt(len(edges) + len(support)))), "objective": objective(x), "maxStep": max_step, "runtimeSeconds": time.perf_counter() - started, "history": history}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--graph", type=Path, required=True)
    p.add_argument("--targets", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--frame", type=int, required=True)
    p.add_argument("--support-ratio", type=float, default=0.0)
    p.add_argument("--max-iterations", type=int, default=30)
    p.add_argument("--inner-iterations", type=int, default=80)
    p.add_argument("--max-backtracks", type=int, default=20)
    args = p.parse_args()
    a4, base = load_a4()
    g = np.load(args.graph); V0 = g["V"].astype(float); F = g["F"].astype(np.int64); T = g["constraintTriangles"].astype(np.int64); B = g["constraintBary"].astype(float)
    edges = np.vstack((g["edgeSprings"], g["virtualSprings"])).astype(np.int64); rest = np.concatenate((g["edgeRestLengths"], g["virtualRestLengths"])).astype(float)
    targets = np.load(args.targets)["targets"].astype(float)[args.frame]
    support = g["supportSurfaceVertices"].astype(np.int64); support_ids = g["supportAnchorIds"].astype(np.int64); support_rest = g["supportRestLengths"].astype(float); anchors = g["anchorPositions"].astype(float)
    conn = sparse.coo_matrix((np.ones(len(edges)), (edges[:, 0], edges[:, 1])), shape=(len(V0), len(V0))).tocsr()
    ncomp, labels = connected_components(conn, directed=False)
    x = V0.copy(); records = []; failure = None
    started = time.perf_counter()
    for ci in range(ncomp):
        verts = np.flatnonzero(labels == ci); lm = np.flatnonzero(np.array([labels[int(t[0])] == ci for t in T]))
        if not len(lm): continue
        remap = -np.ones(len(V0), dtype=np.int64); remap[verts] = np.arange(len(verts))
        e_mask = np.all(np.isin(edges, verts), axis=1); local_e = remap[edges[e_mask]]; local_r = rest[e_mask]
        s_mask = np.isin(support, verts); local_s = remap[support[s_mask]]; local_aids = support_ids[s_mask]; local_sr = support_rest[s_mask]
        solved, rep = solve_component(base, V0[verts], local_e, local_r, remap[T[lm]], B[lm], targets[lm], local_s, anchors, local_aids, local_sr, args.support_ratio, args.max_iterations, 1e-9, 1e-6, args.max_backtracks, 1e-11, args.inner_iterations, start=x[verts])
        x[verts] = solved; records.append({"component": int(ci), "vertices": int(len(verts)), "landmarks": int(len(lm)), **rep})
        if rep["status"] != "converged": failure = {"component": int(ci), **rep}; break
    report = {"solver": "A4 sparse projected nonlinear Hookean solver plus fixed abstract-anchor springs", "frame": int(args.frame), "supportRatio": float(args.support_ratio), "vertices": int(len(V0)), "triangles": int(len(F)), "landmarks": int(len(T)), "components": int(ncomp), "failure": failure, "runtimeSeconds": time.perf_counter() - started, "componentReports": records, "topologyChanged": False}
    args.output.parent.mkdir(parents=True, exist_ok=True); args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8"); np.savez_compressed(args.output.with_name(args.output.stem + "-positions.npz"), positions=x, originalPositions=V0, originalIndices=g["originalIndices"])
    print(json.dumps({k: report[k] for k in ("frame", "supportRatio", "vertices", "components", "failure", "runtimeSeconds")}))
    raise SystemExit(0 if failure is None else 2)


if __name__ == "__main__": main()
