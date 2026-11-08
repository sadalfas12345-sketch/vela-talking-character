"""Plan A4 scalable Hookean equilibrium by sparse affine projection.

The physical objective is unchanged from Plan A: unit Hookean stretch energy on
original and anatomically justified virtual seam edges.  Hard barycentric and
minimal rigid-mode constraints are represented by a sparse independent-row
matrix.  A sparse factorization of C*C.T is reused to construct one feasible
state and to project every nonlinear gradient/step into the exact constraint
null space.  No dense vertex-space null basis is built.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import time
from pathlib import Path

import numpy as np
from scipy import linalg
from scipy import sparse
from scipy.sparse.csgraph import connected_components
from scipy.sparse.linalg import LinearOperator, cg, lsqr, splu


def load_base():
    path = Path(__file__).with_name("solve_plan_a2_hookean.py")
    spec = importlib.util.spec_from_file_location("plan_a4_base", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SparseConstraintProjector:
    def __init__(self, C):
        self.C = C.tocsc()
        self.rows = int(C.shape[0])
        self.gram = (self.C @ self.C.T).tocsc()
        self.factor = splu(self.gram)

    def solve(self, rhs):
        if self.rows == 0:
            return np.zeros(self.C.shape[1], dtype=float)
        lam = self.factor.solve(np.asarray(rhs, dtype=float).reshape(-1))
        return np.asarray(self.C.T @ lam).reshape(-1)

    def project(self, vector):
        vector = np.asarray(vector, dtype=float).reshape(-1)
        if self.rows == 0:
            return vector
        return vector - self.solve(self.C @ vector)

    def residual(self, vector):
        if self.rows == 0:
            return 0.0
        return float(np.max(np.abs(self.C @ vector)))


def reduce_constraint_rows_sparse(C, rank_tolerance=1e-11):
    """Find independent constraint rows without materializing C in vertex space.

    Only the small row Gram matrix is dense.  This keeps the memory cost tied
    to the number of constraints, not to 3 * the number of mesh vertices.
    """
    C = C.tocsr()
    m = int(C.shape[0])
    if m == 0:
        return {"indices": np.zeros(0, dtype=np.int64), "omitted": np.zeros(0, dtype=np.int64), "representation": np.zeros((0, 0)), "rank": 0, "gramCondition": 0.0}
    gram = (C @ C.T).toarray()
    gram = 0.5 * (gram + gram.T)
    _, R, piv = linalg.qr(gram, mode="economic", pivoting=True)
    diagonal = np.abs(np.diag(R)) if R.size else np.zeros(0)
    scale = float(diagonal[0]) if len(diagonal) else 0.0
    rank = int(np.sum(diagonal > rank_tolerance * max(scale, 1e-30)))
    keep = np.asarray(piv[:rank], dtype=np.int64)
    omitted = np.asarray([i for i in range(m) if i not in set(keep.tolist())], dtype=np.int64)
    if len(omitted) and rank:
        gram_keep = gram[np.ix_(keep, keep)]
        cross = (C[omitted] @ C[keep].T).toarray()
        representation = linalg.solve(gram_keep.T, cross.T, assume_a="sym").T
    else:
        representation = np.zeros((len(omitted), rank), dtype=float)
    positive = diagonal[diagonal > rank_tolerance * max(scale, 1e-30)]
    condition = float((positive[0] / positive[-1]) ** 2) if len(positive) else float("inf")
    return {"indices": keep, "omitted": omitted, "representation": representation, "rank": rank, "gramCondition": condition}


def solve_component_projected(base, x0, edges, rest, triangles, bary, target, max_iter, residual_tol, force_tol, step_tol, max_backtracks, rank_tolerance, inner_iterations=150, start=None):
    x0 = np.asarray(x0, dtype=float)
    x = x0.copy() if start is None else np.asarray(start, dtype=float).copy()
    n = len(x)
    C_landmark = base.constraint_matrix(triangles, bary, n)
    full_gauge = base.gauge_matrix(x0)
    G, rigid_rank = base.select_gauge_rows(C_landmark, full_gauge, x0)
    C_full = sparse.vstack((C_landmark, G), format="csr")
    reduction = reduce_constraint_rows_sparse(C_full, rank_tolerance)
    C = C_full[reduction["indices"]] if reduction["rank"] else sparse.csr_matrix((0, 3 * n))
    target_flat = target.reshape(-1)
    gauge_target = G @ x0.reshape(-1)
    rhs_full = np.concatenate((target_flat - C_landmark @ x.reshape(-1), gauge_target - G @ x.reshape(-1)))
    rhs_keep, compatibility_error = base.reduced_rhs(reduction, rhs_full, max(residual_tol * 10.0, 1e-12))
    if rhs_keep is None:
        return x, {"status": "incompatible_constraints", "constraintRank": int(reduction["rank"]), "constraintRows": int(C_full.shape[0]), "rigidConstraintRank": int(rigid_rank), "compatibilityError": compatibility_error, "iterations": 0}
    projector = SparseConstraintProjector(C)
    correction = projector.solve(rhs_keep)
    x = x + correction.reshape(n, 3)
    initial_projection = float(np.max(np.linalg.norm(correction.reshape(n, 3), axis=1))) if n else 0.0
    edge_scale = max(float(np.median(rest[rest > 0])) if np.any(rest > 0) else 1.0, 1e-12)
    force_scale = edge_scale * max(1.0, float(np.sqrt(len(edges) / max(n, 1))))
    history = [{"iteration": 0, "type": "feasible_projection", "maxStep": initial_projection, "constraintResidual": projector.residual(x.reshape(-1) - x0.reshape(-1) - correction)}]
    previous_gradient = None
    previous_direction = None
    previous_x = None
    previous_gradient_projected = None
    accepted_alphas = []
    max_step = initial_projection
    status = "max_iterations"
    start = time.perf_counter()

    def energy(state):
        return base.spring_energy(state, edges, rest)

    for iteration in range(1, max_iter + 1):
        J, residual, lengths = base.spring_jacobian(x, edges, rest, x0)
        gradient = np.asarray(J.T @ residual).reshape(-1)
        projected = projector.project(gradient)
        projected_residual = float(np.linalg.norm(projected) / max(force_scale, 1e-30))
        hard_error = max(
            float(np.max(np.abs(C_landmark @ x.reshape(-1) - target_flat))) if C_landmark.shape[0] else 0.0,
            float(np.max(np.abs(G @ (x.reshape(-1) - x0.reshape(-1))))) if G.shape[0] else 0.0,
        )
        if hard_error <= residual_tol and projected_residual <= force_tol:
            status = "converged"
            history.append({"iteration": iteration - 1, "energy": energy(x), "hardConstraintError": hard_error, "projectedForceResidual": projected_residual, "maxStep": 0.0})
            break

        # Matrix-free projected Gauss--Newton step.  The operator is applied
        # only in the tangent space C*d=0, so no dense null-space basis and no
        # vertex-space KKT factorization are formed.  LSQR solves the
        # linearized spring residual directly and is robust to the floppy
        # stretching modes that made the old KKT update explode.
        def hess_vec(v):
            tangent = projector.project(v)
            return projector.project(np.asarray(J.T @ (J @ tangent)).reshape(-1)) + 1e-8 * tangent

        def tangent_forward(v):
            return J @ projector.project(v)

        def tangent_transpose(v):
            return projector.project(np.asarray(J.T @ v).reshape(-1))

        tangent_jacobian = LinearOperator((J.shape[0], 3 * n), matvec=tangent_forward, rmatvec=tangent_transpose, dtype=float)
        lsqr_result = lsqr(tangent_jacobian, -residual, atol=1e-7, btol=1e-7, iter_lim=inner_iterations)
        direction = projector.project(lsqr_result[0])
        lsqr_stop = int(lsqr_result[1])
        lsqr_iters = int(lsqr_result[2])
        direction = np.asarray(direction).reshape(-1)
        if lsqr_stop not in (1, 2, 3, 4, 5, 6, 7) or not np.isfinite(direction).all() or float(np.dot(projected, direction)) >= -1e-14:
            direction = -projected
            inner_info = f"fallback_gradient_stop_{lsqr_stop}"
        else:
            inner_info = {"stop": lsqr_stop, "iterations": lsqr_iters}
        alpha0 = 1.0
        directional = float(np.dot(projected, direction))
        if directional >= 0.0:
            direction = -projected
            directional = -float(np.dot(projected, projected))
        old_energy = energy(x)
        previous_state = x.copy()
        alpha = alpha0
        accepted = False
        trial_energy = None
        for _ in range(max_backtracks + 1):
            # x is already feasible.  Project only the proposed tangent
            # increment; projecting the full displacement from x0 would erase
            # the affine landmark target itself.
            trial = x.reshape(-1) + projector.project(alpha * direction)
            trial = trial.reshape(n, 3)
            trial_energy = energy(trial)
            if np.isfinite(trial).all() and trial_energy <= old_energy + 1e-4 * alpha * directional:
                accepted = True
                x = trial
                break
            alpha *= 0.5
        if not accepted:
            status = "line_search_stagnation"
            history.append({"iteration": iteration, "energy": old_energy, "hardConstraintError": hard_error, "projectedForceResidual": projected_residual, "maxStep": 0.0, "acceptedAlpha": 0.0})
            break
        accepted_step = float(np.max(np.linalg.norm(x - previous_state, axis=1)))
        max_step = max(max_step, accepted_step)
        accepted_alphas.append(alpha)
        history.append({"iteration": iteration, "energy": trial_energy, "relativeEnergyChange": (old_energy - trial_energy) / max(abs(old_energy), 1e-30), "hardConstraintError": hard_error, "projectedForceResidual": projected_residual, "maxStep": accepted_step, "acceptedAlpha": alpha, "innerLsqrInfo": inner_info})
        previous_x = previous_state.reshape(-1).copy()
        previous_gradient = projected.copy()
        previous_direction = direction.copy()
        previous_gradient_projected = projected.copy()

    final_J, final_residual, final_lengths = base.spring_jacobian(x, edges, rest, x0)
    final_gradient = np.asarray(final_J.T @ final_residual).reshape(-1)
    final_projected = projector.project(final_gradient)
    final_hard_error = max(
        float(np.max(np.abs(C_landmark @ x.reshape(-1) - target_flat))) if C_landmark.shape[0] else 0.0,
        float(np.max(np.abs(G @ (x.reshape(-1) - x0.reshape(-1))))) if G.shape[0] else 0.0,
    )
    return x, {
        "status": status,
        "iterations": len(history) - 1,
        "constraintRank": int(reduction["rank"]),
        "constraintRows": int(C_full.shape[0]),
        "constraintGramCondition": float(reduction.get("gramCondition", 0.0)),
        "rigidConstraintRank": int(rigid_rank),
        "gaugeRows": int(G.shape[0]),
        "initialProjectionStep": initial_projection,
        "finalConstraintError": final_hard_error,
        "projectedForceResidual": float(np.linalg.norm(final_projected) / max(force_scale, 1e-30)),
        "forceScale": force_scale,
        "springEnergy": energy(x),
        "maxStep": max_step,
        "minEdgeLength": float(np.min(final_lengths)) if len(final_lengths) else None,
        "acceptedAlphas": accepted_alphas,
        "runtimeSeconds": time.perf_counter() - start,
        "history": history,
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--graph", type=Path, required=True)
    p.add_argument("--targets", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--frame", type=int, default=99)
    p.add_argument("--substeps", type=int, default=20)
    p.add_argument("--max-iterations", type=int, default=200)
    p.add_argument("--residual-tol", type=float, default=1e-9)
    p.add_argument("--force-tol", type=float, default=1e-6)
    p.add_argument("--step-tol", type=float, default=1e-8)
    p.add_argument("--rank-tolerance", type=float, default=1e-11)
    p.add_argument("--max-backtracks", type=int, default=24)
    p.add_argument("--inner-iterations", type=int, default=150)
    p.add_argument("--save-positions", action="store_true")
    a = p.parse_args()
    base = load_base()
    graph = np.load(a.graph)
    V0 = graph["V"].astype(float)
    F = graph["F"].astype(np.int64)
    T = graph["constraintTriangles"].astype(np.int64)
    B = graph["constraintBary"].astype(float)
    edges = np.vstack((graph["edgeSprings"], graph["virtualSprings"])).astype(np.int64)
    rest = np.concatenate((graph["edgeRestLengths"], graph["virtualRestLengths"])).astype(float)
    target_data = np.load(a.targets)
    if "targetLandmarks" in target_data:
        target = target_data["targetLandmarks"].astype(float)
    else:
        target = target_data["targets"].astype(float)[a.frame]
    # Use the actual spring graph for components.  Reconstructing connectivity
    # from triangle edges alone would silently drop valid virtual/original
    # graph edges and split one simulation component into artificial pieces.
    conn = sparse.coo_matrix((np.ones(len(edges)), (edges[:, 0], edges[:, 1])), shape=(len(V0), len(V0))).tocsr()
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
    stats = []
    global_start = time.perf_counter()
    failure = None
    for ci, lm_ids in enumerate(by_component):
        if not lm_ids:
            continue
        verts = vertex_lists[ci]
        local_tri = local_maps[ci][T[lm_ids]]
        neutral_component_landmarks = graph["neutralLandmarks"][lm_ids].astype(float)
        start = x[verts].copy()
        substep_reports = []
        for substep in range(1, max(1, a.substeps) + 1):
            fraction = substep / max(1, a.substeps)
            stage_target = neutral_component_landmarks + fraction * (target[lm_ids] - neutral_component_landmarks)
            solved, report = solve_component_projected(base, V0[verts], edge_lists[ci][0], edge_lists[ci][1], local_tri, B[lm_ids], stage_target, a.max_iterations, a.residual_tol, a.force_tol, a.step_tol, a.max_backtracks, a.rank_tolerance, a.inner_iterations, start=start)
            x[verts] = solved
            start = solved
            substep_reports.append({"substep": substep, "fraction": fraction, **report})
            if report["status"] != "converged":
                failure = {"component": ci, "substep": substep, "fraction": fraction, **report}
                break
        stats.append({"component": ci, "vertices": len(verts), "landmarks": len(lm_ids), "substeps": substep_reports})
        if failure:
            break
    report = {
        "solver": "sparse affine hard-constraint projection plus projected nonlinear Hookean energy optimization",
        "physicalTerms": ["original edge stretching", "virtual seam edge stretching"],
        "excludedTerms": ["bending", "volume", "support stiffness", "ARAP", "gravity", "inertia", "damping"],
        "frame": a.frame,
        "vertices": len(V0),
        "triangles": len(F),
        "edges": len(edges),
        "landmarks": len(T),
        "simulationComponents": int(component_count),
        "componentsSolved": len(stats),
        "failure": failure,
        "runtimeSeconds": time.perf_counter() - global_start,
        "componentReports": stats,
        "finalPositionsOutput": None,
    }
    a.output.parent.mkdir(parents=True, exist_ok=True)
    if a.save_positions:
        path = a.output.with_name(a.output.stem + "-positions.npz")
        np.savez_compressed(path, positions=x, originalPositions=V0, originalIndices=graph["originalIndices"] if "originalIndices" in graph else np.arange(len(V0)))
        report["finalPositionsOutput"] = str(path)
    a.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"frame": a.frame, "vertices": len(V0), "components": component_count, "componentsSolved": len(stats), "failure": failure, "runtimeSeconds": report["runtimeSeconds"]}, indent=2))
    if failure:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
