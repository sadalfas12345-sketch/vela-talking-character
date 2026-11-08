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
from scipy import linalg
from scipy import sparse
from scipy.sparse.linalg import LinearOperator, MatrixRankWarning, lsqr, minres, spsolve


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


def spring_jacobian(x, edges, rest, reference=None):
    """Return exact Hookean residual rows and their Gauss--Newton Jacobian.

    A zero-rest spring is represented by its three Cartesian residuals.  This
    is the differentiable form of 0.5*||x_i-x_j||^2 and avoids an undefined
    axial direction at a coincident seam.
    """
    u = x[edges[:, 0]] - x[edges[:, 1]]
    lengths = np.linalg.norm(u, axis=1)
    zero_rest = rest <= 1e-12
    axial = (~zero_rest) & (lengths > 1e-12)
    dirs = np.zeros_like(u)
    dirs[axial] = u[axial] / lengths[axial, None]
    rows = []
    cols = []
    vals = []
    residual = []
    row = 0
    for k in np.flatnonzero(axial):
        i, j = map(int, edges[k])
        for d in range(3):
            rows.extend([row, row])
            cols.extend([3 * i + d, 3 * j + d])
            vals.extend([float(dirs[k, d]), -float(dirs[k, d])])
        residual.append(float(lengths[k] - rest[k]))
        row += 1
    # A zero-rest spring is an isotropic Hookean tether. It is represented by
    # three Cartesian residual rows, avoiding an undefined axial direction.
    for k in np.flatnonzero(zero_rest):
        i, j = map(int, edges[k])
        delta = x[i] - x[j]
        for d in range(3):
            rows.extend([row, row])
            cols.extend([3 * i + d, 3 * j + d])
            vals.extend([1.0, -1.0])
            residual.append(float(delta[d]))
            row += 1
    # A positive-rest spring at a collapsed state has no unique derivative of
    # its length.  Use its neutral direction as a deterministic subgradient;
    # this keeps the residual equal to length-rest instead of accidentally
    # treating the spring as relaxed.
    for k in np.flatnonzero((~zero_rest) & (~axial)):
        i, j = map(int, edges[k])
        ref = reference[i] - reference[j] if reference is not None else np.zeros(3)
        ref_len = float(np.linalg.norm(ref))
        direction = ref / ref_len if ref_len > 1e-12 else np.array([1.0, 0.0, 0.0])
        for d in range(3):
            rows.extend([row, row])
            cols.extend([3 * i + d, 3 * j + d])
            vals.extend([float(direction[d]), -float(direction[d])])
        residual.append(float(lengths[k] - rest[k]))
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


def reduce_constraint_rows(C, rank_tolerance=1e-11):
    """Keep an independent row basis and a representation of redundant rows.

    Repeated barycentric constraints and numerical gauge rows can make the
    KKT matrix singular even when the requested target is compatible.  A
    pivoted QR of C.T gives a deterministic independent row set.  The
    representation matrix is retained so incompatible redundant target rows
    are reported instead of being silently discarded.
    """
    if not C.shape[0]:
        return {"indices": np.zeros(0, dtype=np.int64), "omitted": np.zeros(0, dtype=np.int64), "representation": np.zeros((0, 0)), "rank": 0}
    dense = C.toarray()
    _, R, piv = linalg.qr(dense.T, mode="economic", pivoting=True)
    diagonal = np.abs(np.diag(R)) if R.size else np.zeros(0)
    scale = float(diagonal[0]) if len(diagonal) else 0.0
    rank = int(np.sum(diagonal > rank_tolerance * max(scale, 1e-30)))
    keep = np.asarray(piv[:rank], dtype=np.int64)
    omitted = np.asarray([i for i in range(C.shape[0]) if i not in set(keep.tolist())], dtype=np.int64)
    if len(omitted):
        independent = dense[keep]
        # Each omitted row is represented as representation @ independent.
        representation = np.linalg.lstsq(independent.T, dense[omitted].T, rcond=rank_tolerance)[0].T
    else:
        representation = np.zeros((0, rank), dtype=float)
    return {"indices": keep, "omitted": omitted, "representation": representation, "rank": rank}


def reduced_rhs(reduction, rhs, compatibility_tolerance):
    keep = reduction["indices"]
    omitted = reduction["omitted"]
    if len(omitted):
        predicted = reduction["representation"] @ rhs[keep]
        residual = rhs[omitted] - predicted
        err = float(np.max(np.abs(residual))) if len(residual) else 0.0
        if err > compatibility_tolerance:
            return None, err
    return rhs[keep], 0.0


def constrained_linear_step(K, C, rhs, solver="auto", iterative_threshold=20000, iterative_maxiter=5000):
    """Solve one sparse equality-constrained Gauss--Newton step.

    Direct sparse KKT factorization is retained for small blocks.  Larger
    blocks use matrix-free MINRES with a positive diagonal block preconditioner
    so a 10k-vertex facial patch does not trigger uncontrolled fill-in.
    """
    n = K.shape[0]
    m = C.shape[0]
    use_iterative = solver == "iterative" or (solver == "auto" and n >= iterative_threshold)
    if not use_iterative:
        KKT = sparse.bmat([[K, C.T], [C, None]], format="csc") if m else K.tocsc()
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always", MatrixRankWarning)
            sol = spsolve(KKT, rhs)
        return sol, [str(w.message) for w in caught], {"solver": "direct", "info": 0}
    if not m:
        op = LinearOperator((n, n), matvec=lambda z: K @ z, dtype=float)
        diag = np.maximum(np.abs(K.diagonal()), 1e-30)
        M = LinearOperator((n, n), matvec=lambda z: z / diag, dtype=float)
    else:
        size = n + m
        def matvec(z):
            return np.concatenate((K @ z[:n] + C.T @ z[n:], C @ z[:n]))
        op = LinearOperator((size, size), matvec=matvec, dtype=float)
        primal_diag = np.maximum(np.abs(K.diagonal()), 1e-30)
        row_diag = np.maximum(np.asarray(C.multiply(C).sum(axis=1)).reshape(-1), 1e-12)
        def precondition(z):
            return np.concatenate((z[:n] / primal_diag, z[n:] / row_diag))
        M = LinearOperator((size, size), matvec=precondition, dtype=float)
    sol, info = minres(op, rhs, rtol=1e-10, maxiter=iterative_maxiter, M=M)
    return sol, ([] if info == 0 else [f"MINRES info={info}"]), {"solver": "minres", "info": int(info)}


def lsqr_tangent_step(J, residual, C, maxiter=5000):
    """Solve a sparse Gauss--Newton step while staying on C dx = 0."""
    if C.shape[0]:
        weight = 1e8
        A = sparse.vstack((J, C * weight), format="csr")
        b = np.concatenate((-residual, np.zeros(C.shape[0])))
    else:
        A = J
        b = -residual
    result = lsqr(A, b, atol=1e-11, btol=1e-11, iter_lim=maxiter)
    dx = np.asarray(result[0]).reshape(-1)
    projection_stop = 1
    projection_iters = 0
    if C.shape[0]:
        correction = lsqr(C, -np.asarray(C @ dx).reshape(-1), atol=1e-13, btol=1e-13, iter_lim=maxiter)
        dx += np.asarray(correction[0]).reshape(-1)
        projection_stop = int(correction[1])
        projection_iters = int(correction[2])
    info = {"solver": "lsqr", "lsqrIters": int(result[2]), "projectionIters": projection_iters, "lsqrStop": int(result[1]), "projectionStop": projection_stop}
    return dx, info


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


def select_gauge_rows(C_landmark, full_gauge, neutral):
    """Add only the gauge rows needed to remove remaining rigid modes.

    If the hard landmark constraints already determine a component's rigid
    translation and rotation, adding all six zero-moment rows can overconstrain
    the deformation.  Select a minimal complementary subset in rigid-motion
    space instead.
    """
    n = len(neutral)
    centered = neutral - neutral.mean(axis=0, keepdims=True)
    rigid = np.zeros((3 * n, 6), dtype=float)
    for i, (rx, ry, rz) in enumerate(centered):
        rigid[3 * i : 3 * i + 3, :3] = np.eye(3)
        rigid[3 * i : 3 * i + 3, 3:] = np.array([[0.0, -rz, ry], [rz, 0.0, -rx], [-ry, rx, 0.0]])
    landmark_rigid = np.asarray(C_landmark @ rigid)
    rigid_rank = int(np.linalg.matrix_rank(landmark_rigid, tol=1e-11)) if landmark_rigid.size else 0
    if rigid_rank >= 6:
        return sparse.csr_matrix((0, 3 * n)), rigid_rank
    null = linalg.null_space(landmark_rigid)
    gauge_rigid = np.asarray(full_gauge @ rigid)
    projected = gauge_rigid @ null
    _, _, piv = linalg.qr(projected.T, mode="economic", pivoting=True)
    needed = 6 - rigid_rank
    selected = np.asarray(piv[:needed], dtype=np.int64)
    return full_gauge[selected], rigid_rank


def solve_component(
    x0,
    edges,
    rest,
    triangles,
    bary,
    target,
    max_iter,
    residual_tol,
    force_tol=1e-8,
    step_tol=1e-8,
    max_backtracks=24,
    rank_tolerance=1e-11,
    linear_damping=1e-6,
    linear_solver="auto",
    iterative_threshold=20000,
    iterative_maxiter=5000,
):
    x = x0.copy()
    n = len(x)
    C_landmark = constraint_matrix(triangles, bary, n)
    full_gauge = gauge_matrix(x0)
    G, rigid_constraint_rank = select_gauge_rows(C_landmark, full_gauge, x0)
    C = sparse.vstack((C_landmark, G), format="csr")
    gauge_state = G @ (x.reshape(-1) - x0.reshape(-1))
    reduction = reduce_constraint_rows(C, rank_tolerance)
    initial_res = max(float(np.max(np.abs(C_landmark @ x.reshape(-1) - target.reshape(-1)))) if C_landmark.shape[0] else 0.0, float(np.max(np.abs(gauge_state))) if len(gauge_state) else 0.0)
    status = "max_iterations"
    iterations = 0
    warnings_seen = []
    history = []
    accepted_alphas = []
    max_actual_step = 0.0
    edge_scale = max(float(np.median(rest[rest > 0])) if np.any(rest > 0) else 1.0, 1e-12)
    compatibility_tolerance = max(residual_tol * 10.0, edge_scale * 1e-10)

    def constraint_residual(state):
        return max(
            float(np.max(np.abs(C_landmark @ state.reshape(-1) - target.reshape(-1)))) if C_landmark.shape[0] else 0.0,
            float(np.max(np.abs(G @ (state.reshape(-1) - x0.reshape(-1))))) if G.shape[0] else 0.0,
        )

    # The merit penalty is numerical globalization only.  It gives the exact
    # equality constraints priority while the line search is temporarily off
    # the affine constraint manifold; it is not a physical spring or support
    # term and is never retained in the equilibrium energy.
    constraint_weight = 100.0

    def merit(state, energy_scale):
        cres = constraint_residual(state)
        return spring_energy(state, edges, rest) / energy_scale + constraint_weight * (cres / edge_scale) ** 2

    C_reduced = C[reduction["indices"]] if reduction["rank"] else sparse.csr_matrix((0, 3 * n))
    if linear_solver == "lsqr" and reduction["rank"]:
        initial_rhs_full = np.concatenate((target.reshape(-1) - C_landmark @ x.reshape(-1), -gauge_state))
        initial_rhs, initial_compatibility_error = reduced_rhs(reduction, initial_rhs_full, compatibility_tolerance)
        if initial_rhs is None:
            status = "incompatible_constraints"
            final_cres = constraint_residual(x)
            return x, {"status": status, "iterations": 0, "constraintRank": int(reduction["rank"]), "constraintRows": int(C.shape[0]), "rigidConstraintRank": rigid_constraint_rank, "gaugeRows": int(G.shape[0]), "linearDamping": linear_damping, "linearSolver": linear_solver, "initialConstraintResidual": initial_res, "finalConstraintResidual": final_cres, "compatibilityError": initial_compatibility_error, "springEnergy": spring_energy(x, edges, rest), "projectedGradientResidual": None, "maxStep": 0.0, "warnings": []}
        projection = lsqr(C_reduced, initial_rhs, atol=1e-13, btol=1e-13, iter_lim=iterative_maxiter)
        if projection[1] not in (0, 1, 2) or projection[3] > compatibility_tolerance:
            status = "constraint_projection_failed"
            final_cres = constraint_residual(x)
            return x, {"status": status, "iterations": 0, "constraintRank": int(reduction["rank"]), "constraintRows": int(C.shape[0]), "rigidConstraintRank": rigid_constraint_rank, "gaugeRows": int(G.shape[0]), "linearDamping": linear_damping, "linearSolver": linear_solver, "initialConstraintResidual": initial_res, "finalConstraintResidual": final_cres, "compatibilityError": float(projection[3]), "springEnergy": spring_energy(x, edges, rest), "projectedGradientResidual": None, "maxStep": 0.0, "warnings": []}
        correction = np.asarray(projection[0]).reshape(n, 3)
        x += correction
        history.append({"iteration": 0, "type": "hard_constraint_projection", "constraintResidual": constraint_residual(x), "acceptedStep": float(np.max(np.linalg.norm(correction, axis=1))) if len(correction) else 0.0, "lsqrIters": int(projection[2])})

    for it in range(max_iter):
        J, r, lengths = spring_jacobian(x, edges, rest, x0)
        current_gradient = np.asarray(J.T @ r).reshape(-1)
        current_projected = projected_gradient(current_gradient, C)
        current_constraint = constraint_residual(x)
        if current_constraint <= residual_tol and current_projected <= force_tol:
            status = "converged"
            break
        if linear_solver == "lsqr":
            dx_flat, solver_meta = lsqr_tangent_step(J, r, C_reduced, iterative_maxiter)
            sol = dx_flat
            solver_warnings = [] if solver_meta["lsqrStop"] in (0, 1, 2) and solver_meta["projectionStop"] in (0, 1, 2) else [str(solver_meta)]
        else:
            K = (J.T @ J).tocsr()
            g = J.T @ r
            diag = K.diagonal()
            diag_scale = float(np.median(diag[diag > 0])) if np.any(diag > 0) else 1.0
            # Numerical Levenberg--Marquardt damping selects a bounded minimum
            # norm step from the many floppy modes of stretching-only surface
            # springs. It is a linear-solve globalization parameter, not a
            # physical support or extra deformation energy.
            K = K + sparse.eye(3 * n, format="csr") * (linear_damping * diag_scale)
            gauge_state = G @ (x.reshape(-1) - x0.reshape(-1))
            rhs_full = np.concatenate((target.reshape(-1) - C_landmark @ x.reshape(-1), -gauge_state))
            rhs, compatibility_error = reduced_rhs(reduction, rhs_full, compatibility_tolerance)
            if rhs is None:
                status = "incompatible_constraints"
                break
            linear_rhs = np.concatenate((-np.asarray(g).reshape(-1), rhs)) if reduction["rank"] else -np.asarray(g).reshape(-1)
            sol, solver_warnings, solver_meta = constrained_linear_step(K, C_reduced, linear_rhs, linear_solver, iterative_threshold, iterative_maxiter)
        warnings_seen.extend(solver_warnings)
        if not np.isfinite(sol).all():
            status = "nonfinite_linear_solve"
            break
        dx = np.asarray(sol[: 3 * n]).reshape(n, 3)
        proposed_step = float(np.max(np.linalg.norm(dx, axis=1)))
        if not np.isfinite(proposed_step):
            status = "nonfinite_step"
            break
        old_energy = spring_energy(x, edges, rest)
        energy_scale = max(float(len(edges)) * edge_scale * edge_scale, 1e-30)
        old_merit = merit(x, energy_scale)
        alpha = 1.0
        accepted = False
        trial_energy = None
        trial_merit = None
        for _ in range(max_backtracks + 1):
            trial = x + alpha * dx
            if np.isfinite(trial).all():
                trial_energy = spring_energy(trial, edges, rest)
                trial_merit = merit(trial, energy_scale)
                # Merit reduction is the globalization criterion.  The
                # equality residual is part of the merit, so a partial step
                # cannot be mistaken for equilibrium merely because the
                # springs relaxed while the target was abandoned.
                if trial_merit <= old_merit * (1.0 - 1e-4 * alpha) or (constraint_residual(trial) < constraint_residual(x) * 0.25 and trial_merit < old_merit):
                    accepted = True
                    x = trial
                    break
            alpha *= 0.5
        if not accepted:
            status = "line_search_failed"
            history.append({"iteration": it + 1, "energy": old_energy, "constraintResidual": constraint_residual(x), "proposedStep": proposed_step, "acceptedAlpha": 0.0, "merit": old_merit})
            break
        actual_step = float(np.max(np.linalg.norm(alpha * dx, axis=1)))
        max_actual_step = max(max_actual_step, actual_step)
        accepted_alphas.append(alpha)
        iterations = it + 1
        cres = constraint_residual(x)
        J_new, r_new, lengths_new = spring_jacobian(x, edges, rest, x0)
        gradient_new = np.asarray(J_new.T @ r_new).reshape(-1)
        projected_new = projected_gradient(gradient_new, C)
        history.append({"iteration": iterations, "energy": spring_energy(x, edges, rest), "constraintResidual": cres, "projectedGradientResidual": projected_new, "proposedStep": proposed_step, "acceptedStep": actual_step, "acceptedAlpha": alpha, "merit": trial_merit})
        if cres <= residual_tol and projected_new <= force_tol and actual_step <= step_tol:
            status = "converged"
            break
    final_cres = constraint_residual(x)
    J, r, lengths = spring_jacobian(x, edges, rest, x0)
    gradient = np.asarray(J.T @ r).reshape(-1)
    projected = projected_gradient(gradient, C)
    return x, {"status": status, "iterations": iterations, "constraintRank": int(reduction["rank"]), "constraintRows": int(C.shape[0]), "rigidConstraintRank": rigid_constraint_rank, "gaugeRows": int(G.shape[0]), "linearDamping": linear_damping, "linearSolver": linear_solver, "initialConstraintResidual": initial_res, "finalConstraintResidual": final_cres, "springEnergy": spring_energy(x, edges, rest), "maxGradientResidual": float(np.linalg.norm(gradient) / max(1.0, np.sqrt(len(gradient)))), "projectedGradientResidual": projected, "maxStep": max_actual_step, "minEdgeLength": float(lengths.min()) if len(lengths) else None, "acceptedAlphas": accepted_alphas, "iterationHistory": history, "warnings": warnings_seen[-5:]}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--graph", type=Path, required=True)
    p.add_argument("--targets", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--max-frames", type=int, default=121)
    p.add_argument("--substeps", type=int, default=20)
    p.add_argument("--max-iterations", type=int, default=30)
    p.add_argument("--residual-tol", type=float, default=1e-9)
    p.add_argument("--force-tol", type=float, default=1e-8)
    p.add_argument("--step-tol", type=float, default=1e-8)
    p.add_argument("--linear-damping", type=float, default=1e-6)
    p.add_argument("--linear-solver", choices=["auto", "direct", "iterative", "lsqr"], default="auto")
    p.add_argument("--iterative-threshold", type=int, default=20000)
    p.add_argument("--iterative-maxiter", type=int, default=5000)
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
                solved, stat = solve_component(x[verts], local_edges, local_rest, local_tri, B[lm_ids], desired[lm_ids], a.max_iterations, a.residual_tol, a.force_tol, a.step_tol, linear_damping=a.linear_damping, linear_solver=a.linear_solver, iterative_threshold=a.iterative_threshold, iterative_maxiter=a.iterative_maxiter)
                x[verts] = solved
                comp_stats.append(stat)
                if stat["status"] != "converged":
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
    report = {"solver": "uniform Hookean stretch/compression on original and recorded virtual seam edges; sparse Gauss-Newton equality-constrained KKT with line search and numerical LM damping", "physicalTerms": ["original edge stretching", "virtual seam edge stretching"], "excludedTerms": ["bending", "volume", "support stiffness", "ARAP", "gravity", "inertia", "damping"], "numericalGauge": "minimal zero-mean translation/rotation rows only for rigid modes not fixed by landmarks", "linearSolveDamping": a.linear_damping, "frames": frame_limit, "vertices": len(V0), "triangles": len(F), "landmarks": len(T), "simulationComponents": int(component_count), "framesRequested": frame_limit, "framesSolved": len(frame_metrics), "substepsPerTransition": a.substeps, "runtimeSeconds": time.perf_counter() - total_start, "failure": failure, "frameMetrics": frame_metrics, "finalPositionsOutput": None}
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
