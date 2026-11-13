"""Constrained inverse-physics force solve for one reference-expression frame.

This is deliberately separate from the old hard-landmark solver.  Landmark
positions are observations in the objective; the state is produced by the
existing Hookean edge and abstract-support springs under a compact external
force basis.  The first pass linearizes the *physical equilibrium residual*
around neutral and solves a regularized sparse least-squares problem.  A
nonlinear force-balance audit is then evaluated at the resulting state.

The force basis is barycentric at deterministic, spatially distributed
landmark controls.  It does not add vertices, springs, cross-island links, or
hard positional constraints.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import time
from pathlib import Path

import numpy as np
from scipy import sparse
from scipy.sparse.linalg import LinearOperator, lsqr


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


ROOT = Path(__file__).resolve().parents[1]
A4 = load_module(Path(__file__).with_name("solve_plan_a4_projected_hookean.py"), "vela_a4_inverse")
A5 = load_module(Path(__file__).with_name("solve_plan_a5_subcutaneous.py"), "vela_a5_inverse")
BASE = A4.load_base()

REGIONS = {
    "eyebrows": [70, 63, 105, 336, 293, 334, 107, 300, 65, 52, 53, 46, 285, 295, 282, 283, 276],
    "eyelids": [33, 133, 159, 145, 160, 144, 153, 154, 155, 263, 362, 386, 374, 385, 380, 373, 390, 249],
    "cheeks": [50, 101, 118, 123, 187, 205, 36, 206, 216, 215, 214, 280, 330, 347, 352, 411, 425, 266, 426, 436, 435, 434],
    "mouth": [61, 291, 40, 270, 185, 409, 13, 14, 78, 308, 95, 324, 82, 312, 87, 317],
    "jaw": [152, 148, 176, 149, 150, 136, 365, 377, 400, 378, 379, 394, 172, 132, 361],
}


def load_json_axes(target_json: Path):
    data = json.loads(target_json.read_text(encoding="utf-8"))
    axes = data["targetCoordinateFrame"]
    return np.asarray(axes["right"], float), np.asarray(axes["up"], float)


def landmark_positions(V, T, B):
    return np.sum(V[T] * B[:, :, None], axis=1)


def select_controls(neutral, displacement, count):
    """Deterministic farthest-point controls among moving landmarks."""
    score = np.linalg.norm(displacement, axis=1)
    candidates = np.flatnonzero(score >= np.quantile(score, 0.60))
    if len(candidates) == 0:
        candidates = np.arange(len(neutral))
    chosen = [int(candidates[np.argmax(score[candidates])])]
    while len(chosen) < min(count, len(candidates)):
        dist = np.min(np.linalg.norm(neutral[candidates, None, :] - neutral[np.asarray(chosen)[None, :], :], axis=2), axis=1)
        nxt = int(candidates[np.argmax(dist)])
        if nxt in chosen:
            break
        chosen.append(nxt)
    return np.asarray(chosen, dtype=np.int64)


def force_basis(vertex_count, triangles, bary, controls):
    """Return sparse B mapping 3D control forces to vertex forces.

    Each control force is distributed once over its attachment triangle using
    the original barycentric weights.  The columns are the three Cartesian
    directions for each control.
    """
    rows, cols, vals = [], [], []
    for c, li in enumerate(controls):
        for vi, w in zip(triangles[li], bary[li]):
            for d in range(3):
                rows.append(3 * int(vi) + d)
                cols.append(3 * c + d)
                vals.append(float(w))
    return sparse.coo_matrix((vals, (rows, cols)), shape=(3 * vertex_count, 3 * len(controls))).tocsr()


def image_landmark_matrix(triangles, bary, n, right, up):
    rows, cols, vals = [], [], []
    for li, (tri, weights) in enumerate(zip(triangles, bary)):
        for rd, axis in enumerate((right, up)):
            row = 2 * li + rd
            for vi, w in zip(tri, weights):
                for d in range(3):
                    rows.append(row)
                    cols.append(3 * int(vi) + d)
                    vals.append(float(w) * float(axis[d]))
    return sparse.coo_matrix((vals, (rows, cols)), shape=(2 * len(triangles), 3 * n)).tocsr()


def build_support_jacobian(x, graph, edges, base, support_ratio):
    support = graph["supportSurfaceVertices"].astype(np.int64)
    ids = graph["supportAnchorIds"].astype(np.int64)
    anchors = graph["anchorPositions"].astype(float)
    rest = graph["supportRestLengths"].astype(float)
    if not len(support) or support_ratio <= 0:
        return sparse.csr_matrix((0, 3 * len(x))), np.zeros(0)
    J, residual, _ = A5.fixed_anchor_jacobian(base, x, anchors, support, ids, rest, support_ratio)
    return J, residual


def build_gpu_consistent_support(V0, F, edges, anchors, source_meters_per_unit=0.30, inner_modulus=10000.0, neighbor_count=3):
    """Build the calibrated RK4 support family without cross-island links."""
    n = len(V0)
    face_area_m2 = 0.5 * np.linalg.norm(np.cross(V0[F[:, 1]] - V0[F[:, 0]], V0[F[:, 2]] - V0[F[:, 0]]), axis=1) * source_meters_per_unit ** 2
    attributed = np.zeros(n, dtype=float)
    for tri, area in zip(F, face_area_m2):
        attributed[tri] += area / 3.0
    adjacency = [[] for _ in range(n)]
    for a, b in edges:
        a = int(a); b = int(b)
        adjacency[a].append(b); adjacency[b].append(a)
    surface, anchor_ids, rest, stiffness = [], [], [], []
    for i in range(n):
        unique = sorted(set(adjacency[i]), key=lambda j: float(np.linalg.norm(V0[j] - V0[i])))[:neighbor_count]
        per_tether = inner_modulus * attributed[i] / 0.005 / (1 + len(unique))
        surface.append(i); anchor_ids.append(i); rest.append(float(np.linalg.norm(V0[i] - anchors[i]))); stiffness.append(per_tether)
        for j in unique:
            surface.append(i); anchor_ids.append(j); rest.append(float(np.linalg.norm(V0[i] - anchors[j]))); stiffness.append(per_tether)
    return {"supportSurfaceVertices": np.asarray(surface, dtype=np.int64), "supportAnchorIds": np.asarray(anchor_ids, dtype=np.int64), "supportRestLengths": np.asarray(rest, dtype=float), "supportStiffness": np.asarray(stiffness, dtype=float), "anchorPositions": np.asarray(anchors, dtype=float), "sourceMetersPerUnit": float(source_meters_per_unit), "surfaceStiffness": 30000.0 * 0.0015, "virtualSprings": 0, "mode": "gpu-rk4-consistent-static"}


def weighted_spring_jacobian(base, x, edges, rest, reference, stiffness, scale):
    J, residual, lengths = base.spring_jacobian(x, edges, rest, reference)
    if np.isscalar(stiffness):
        weights = np.full(len(residual), np.sqrt(float(stiffness)) * scale)
    else:
        weights = np.sqrt(np.asarray(stiffness, dtype=float)) * scale
    return J.multiply(weights[:, None]), residual * weights, lengths


def gpu_consistent_support_jacobian(x, support_data, base, scale):
    surface = support_data["supportSurfaceVertices"]
    ids = support_data["supportAnchorIds"]
    anchors = support_data["anchorPositions"]
    rest = support_data["supportRestLengths"]
    stiffness = support_data["supportStiffness"]
    n = len(x)
    aug = np.vstack((x, anchors))
    E = np.column_stack((surface, n + ids)).astype(np.int64)
    J_aug, residual, lengths = base.spring_jacobian(aug, E, rest, np.vstack((x, anchors)))
    weights = np.sqrt(stiffness) * scale
    return J_aug[:, : 3 * n].multiply(weights[:, None]), residual * weights, lengths


def nonlinear_force_equilibrium(x0, x, external, graph, edges, rest, base, support_ratio, iterations, inner_iterations, physics=None):
    """Relax the force-controlled state with the same nonlinear spring energy."""
    n = len(x)
    history = []

    def terms(state):
        if physics is None:
            Je, re, lengths = base.spring_jacobian(state, edges, rest, x0)
            Js, rs = build_support_jacobian(state, graph, edges, base, support_ratio)
        else:
            Je, re, lengths = weighted_spring_jacobian(base, state, edges, rest, x0, physics["surfaceStiffness"], physics["sourceMetersPerUnit"])
            Js, rs, _ = gpu_consistent_support_jacobian(state, physics["supportData"], base, physics["sourceMetersPerUnit"])
        J = sparse.vstack((Je, Js), format="csr")
        r = np.concatenate((re, rs))
        external_gradient = external.reshape(-1) * (physics["sourceMetersPerUnit"] if physics is not None else 1.0)
        g = np.asarray(J.T @ r).reshape(-1) - external_gradient
        energy = float(0.5 * np.dot(r, r) - np.dot(external_gradient, (state - x0).reshape(-1)))
        return J, r, g, energy, lengths

    for it in range(iterations):
        J, residual, gradient, old_energy, lengths = terms(x)
        grad_norm = float(np.linalg.norm(gradient))
        if not np.isfinite(grad_norm):
            history.append({"iteration": it, "status": "nonfinite_gradient"})
            break

        def hess_apply(v):
            return np.asarray(J.T @ (J @ v)).reshape(-1)

        hop = LinearOperator((3 * n, 3 * n), matvec=hess_apply, rmatvec=hess_apply, dtype=float)
        step_result = lsqr(hop, -gradient, atol=1e-6, btol=1e-6, iter_lim=inner_iterations)
        direction = np.asarray(step_result[0]).reshape(-1)
        if not np.isfinite(direction).all() or float(np.dot(gradient, direction)) >= 0.0:
            direction = -gradient
        directional = float(np.dot(gradient, direction))
        alpha = 1.0
        accepted = False
        for _ in range(20):
            trial = (x.reshape(-1) + alpha * direction).reshape(n, 3)
            _, _, _, trial_energy, _ = terms(trial)
            if np.isfinite(trial).all() and trial_energy <= old_energy + 1e-4 * alpha * directional:
                x = trial
                accepted = True
                break
            alpha *= 0.5
        history.append({"iteration": it + 1, "energy": old_energy, "gradientNorm": grad_norm, "acceptedAlpha": alpha if accepted else 0.0, "lsqrIterations": int(step_result[2]), "accepted": accepted})
        if not accepted:
            break
    _, residual, gradient, energy, lengths = terms(x)
    return x, {"iterations": len(history), "history": history, "finalGradientNorm": float(np.linalg.norm(gradient)), "finalEnergy": energy, "finalLengths": lengths}


def geometry_metrics(x0, x, F, edges, rest):
    area0 = np.cross(x0[F[:, 1]] - x0[F[:, 0]], x0[F[:, 2]] - x0[F[:, 0]], axis=1)
    area1 = np.cross(x[F[:, 1]] - x[F[:, 0]], x[F[:, 2]] - x[F[:, 0]], axis=1)
    area0n = np.linalg.norm(area0, axis=1)
    area1n = np.linalg.norm(area1, axis=1)
    positive = rest > 1e-12
    lengths = np.linalg.norm(x[edges[:, 0]] - x[edges[:, 1]], axis=1)
    strains = lengths[positive] / rest[positive] - 1.0 if np.any(positive) else np.zeros(0)
    return {
        "finite": bool(np.isfinite(x).all()),
        "orientationReversals": int(np.sum(np.sum(area0 * area1, axis=1) < 0)) if len(F) else 0,
        "collapses": int(np.sum(area1n <= np.maximum(area0n * 1e-4, 1e-15))) if len(F) else 0,
        "p95AbsPositiveRestStrain": float(np.quantile(np.abs(strains), 0.95)) if len(strains) else 0.0,
    }


def candidate_is_acceptable(baseline, candidate, tolerance=1e-12):
    """Monotone acceptance gate for an inverse-physics update.

    Alpha zero is the baseline. A candidate must improve the actual image
    objective without worsening finite-state, collapse, reversal, or force-
    balance metrics. This pure predicate is intentionally unit-testable.
    """
    if not candidate["finite"]:
        return False, "nonfinite"
    if candidate["imageObjective"] >= baseline["imageObjective"] - tolerance:
        return False, "image_objective_not_improved"
    if candidate["orientationReversals"] > baseline["orientationReversals"]:
        return False, "orientation_reversals_increased"
    if candidate["collapses"] > baseline["collapses"]:
        return False, "collapses_increased"
    if candidate["forceBalance"] > baseline["forceBalance"] * (1.0 + 1e-6) + tolerance:
        return False, "force_balance_worsened"
    return True, "accepted"


def choose_accepted_candidate(baseline, candidates):
    """Choose an improving candidate, always retaining candidates[0] as alpha zero."""
    if not candidates:
        raise ValueError("candidate list must include the alpha-zero baseline")
    baseline_candidate = candidates[0]
    rejections = []
    accepted = []
    for candidate in candidates[1:]:
        ok, reason = candidate_is_acceptable(baseline, candidate)
        candidate["accepted"] = ok
        candidate["rejectionReason"] = reason
        if ok:
            accepted.append(candidate)
        else:
            rejections.append({"alpha": candidate.get("alpha"), "reason": reason})
    if not accepted:
        baseline_candidate["accepted"] = False
        baseline_candidate["rejectionReason"] = "all_updates_rejected"
        return baseline_candidate, rejections
    return min(accepted, key=lambda value: value["error"]), rejections


def iterative_force_update(x0, x, u, Bforce, L, d2, F, graph, edges, rest, base, support_ratio, eye, regularization, outer_iterations, response_iterations, nonlinear_inner_iterations, initial_gradient, physics=None):
    """Update force coefficients with an implicit equilibrium sensitivity map."""
    history = []
    current = x.copy()
    current_u = u.copy()
    n = len(x0)
    current_error = float(np.linalg.norm((L @ (current - x0).reshape(-1) - d2) / max(eye, 1e-30)))
    current_quality = geometry_metrics(x0, current, F, edges, rest)
    current_balance = float(initial_gradient)
    for outer in range(outer_iterations):
        if physics is None:
            Je, re, _ = base.spring_jacobian(current, edges, rest, x0)
            Js, rs = build_support_jacobian(current, graph, edges, base, support_ratio)
        else:
            Je, re, _ = weighted_spring_jacobian(base, current, edges, rest, x0, physics["surfaceStiffness"], physics["sourceMetersPerUnit"])
            Js, rs, _ = gpu_consistent_support_jacobian(current, physics["supportData"], base, physics["sourceMetersPerUnit"])
        J = sparse.vstack((Je, Js), format="csr")
        hop = LinearOperator((3 * n, 3 * n), matvec=lambda v: np.asarray(J.T @ (J @ v)).reshape(-1), rmatvec=lambda v: np.asarray(J.T @ (J @ v)).reshape(-1), dtype=float)
        sensitivities = []
        for col in range(Bforce.shape[1]):
            rhs_force = Bforce[:, col].toarray().reshape(-1) * (physics["sourceMetersPerUnit"] if physics is not None else 1.0)
            response = lsqr(hop, rhs_force, atol=1e-5, btol=1e-5, iter_lim=response_iterations)
            sensitivities.append(response[0])
        S = np.column_stack(sensitivities) if sensitivities else np.zeros((3 * n, 0))
        A = np.asarray(L @ S)
        residual = d2 - np.asarray(L @ (current - x0).reshape(-1)).reshape(-1)
        normal = (A.T @ A) / max(eye * eye, 1e-30) + regularization * np.eye(A.shape[1])
        rhs = (A.T @ residual) / max(eye * eye, 1e-30) - regularization * current_u
        du = np.linalg.lstsq(normal, rhs, rcond=1e-10)[0] if len(rhs) else np.zeros(0)
        old_error = current_error
        baseline = {"imageObjective": current_error, "forceBalance": current_balance, **current_quality}
        candidates = [{"alpha": 0.0, "u": current_u, "x": current, "report": {"finalGradientNorm": current_balance}, "error": current_error, **current_quality}]
        for alpha in (1.0, 0.5, 0.25, 0.125):
            candidate_u = current_u + alpha * du
            candidate_force = np.asarray(Bforce @ candidate_u).reshape(n, 3)
            candidate_x, candidate_report = nonlinear_force_equilibrium(x0, current, candidate_force, graph, edges, rest, base, support_ratio, 3, nonlinear_inner_iterations, physics)
            candidate_error = float(np.linalg.norm((L @ (candidate_x - x0).reshape(-1) - d2) / max(eye, 1e-30)))
            quality = geometry_metrics(x0, candidate_x, F, edges, rest)
            candidates.append({"alpha": alpha, "u": candidate_u, "x": candidate_x, "report": candidate_report, "error": candidate_error, **quality})
        prepared = [{"imageObjective": candidate["error"], "forceBalance": candidate["report"]["finalGradientNorm"], **candidate} for candidate in candidates]
        chosen, rejection_reasons = choose_accepted_candidate(baseline, prepared)
        if chosen["alpha"] != 0.0:
            current_u = chosen["u"]
            current = chosen["x"]
            current_error = chosen["error"]
            current_quality = {key: chosen[key] for key in ("finite", "orientationReversals", "collapses", "p95AbsPositiveRestStrain")}
            current_balance = float(chosen["report"]["finalGradientNorm"])
        else:
            chosen = candidates[0]
        history.append({"outerIteration": outer + 1, "linearizedErrorBefore": old_error, "linearizedControlStepNorm": float(np.linalg.norm(du)), "acceptedAlpha": float(chosen["alpha"]), "actualImageObjective": float(chosen["error"]), "equilibriumGradientNorm": float(chosen["report"]["finalGradientNorm"]), "accepted": bool(chosen["alpha"] != 0.0), "rejections": rejection_reasons, "baselineQuality": baseline})
        if chosen["alpha"] == 0.0:
            break
    return current, current_u, history


def solve_inverse(args):
    started = time.perf_counter()
    graph = np.load(args.graph)
    targets = np.load(args.targets)["targets"].astype(float)
    target = targets[args.frame]
    V0 = graph["V"].astype(float)
    F = graph["F"].astype(np.int64)
    T = graph["constraintTriangles"].astype(np.int64)
    Bary = graph["constraintBary"].astype(float)
    if args.gpu_consistent:
        edges = graph["edgeSprings"].astype(np.int64)
        rest = graph["edgeRestLengths"].astype(float)
    else:
        edges = np.vstack((graph["edgeSprings"], graph["virtualSprings"])).astype(np.int64)
        rest = np.concatenate((graph["edgeRestLengths"], graph["virtualRestLengths"])).astype(float)
    right, up = load_json_axes(args.target_json)
    neutral_lm = landmark_positions(V0, T, Bary)
    d3 = target - neutral_lm
    physics = None
    support_graph = graph
    if args.gpu_consistent:
        physics = {"sourceMetersPerUnit": 0.30, "surfaceStiffness": 30000.0 * 0.0015, "virtualSprings": 0}
        physics["supportData"] = build_gpu_consistent_support(V0, F, edges, graph["anchorPositions"].astype(float), physics["sourceMetersPerUnit"], 10000.0, 3)
        support_graph = {**graph, **physics["supportData"]}
    saved_state = np.load(args.initial_state) if args.initial_state else None
    controls = saved_state["controls"].astype(np.int64) if saved_state is not None else select_controls(neutral_lm, d3, args.controls)
    n = len(V0)
    Bforce = force_basis(n, T, Bary, controls)
    L = image_landmark_matrix(T, Bary, n, right, up)
    d2 = np.column_stack((d3 @ right, d3 @ up)).reshape(-1)
    eye = float(np.linalg.norm(neutral_lm[33] - neutral_lm[263])) if len(neutral_lm) > 263 else float(np.ptp(neutral_lm, axis=0).max())
    eye = max(eye, 1e-9)

    # Linearized physical equilibrium at neutral.  The residual is Kq-Bu,
    # where K is J'J plus the existing support-spring contribution.
    if physics is None:
        Jedge, redge, _ = BASE.spring_jacobian(V0, edges, rest, V0)
        Jsupp, rsupp = build_support_jacobian(V0, graph, edges, BASE, args.support_ratio)
        force_coordinate_scale = 1.0
    else:
        Jedge, redge, _ = weighted_spring_jacobian(BASE, V0, edges, rest, V0, physics["surfaceStiffness"], physics["sourceMetersPerUnit"])
        Jsupp, rsupp, _ = gpu_consistent_support_jacobian(V0, physics["supportData"], BASE, physics["sourceMetersPerUnit"])
        force_coordinate_scale = physics["sourceMetersPerUnit"]
    J = sparse.vstack((Jedge, Jsupp), format="csr")
    residual0 = np.concatenate((redge, rsupp))
    # Neutral should be at rest. Keep any measured residual in the report, but
    # do not silently alter the source geometry.
    def K_apply(q):
        return np.asarray(J.T @ (J @ q)).reshape(-1)

    eq_scale = max(eye * args.equilibrium_scale, 1e-12)
    force_scale = max((args.force_scale if physics is not None else eye * args.force_scale), 1e-12)
    image_scale = eye
    p = Bforce.shape[1]
    rows = J.shape[1] + L.shape[0] + p
    cols = 3 * n + p

    def matvec(y):
        q, u = y[: 3 * n], y[3 * n :]
        eq = (K_apply(q) - Bforce @ u * force_coordinate_scale) / eq_scale
        img = (L @ q - d2) / image_scale
        reg = u / force_scale * np.sqrt(args.force_regularization)
        return np.concatenate((eq, img, reg))

    def rmatvec(z):
        zeq = z[: 3 * n]
        zimg = z[3 * n : 3 * n + L.shape[0]]
        zreg = z[3 * n + L.shape[0] :]
        gq = K_apply(zeq / eq_scale) / eq_scale + np.asarray(L.T @ (zimg / image_scale)).reshape(-1)
        gu = -np.asarray(Bforce.T @ (zeq / eq_scale)).reshape(-1) * force_coordinate_scale + zreg / force_scale * np.sqrt(args.force_regularization)
        return np.concatenate((gq, gu))

    if saved_state is None:
        op = LinearOperator((rows, cols), matvec=matvec, rmatvec=rmatvec, dtype=float)
        rhs = np.concatenate((np.zeros(3 * n), d2 / image_scale, np.zeros(p)))
        result = lsqr(op, rhs, atol=args.linear_atol, btol=args.linear_btol, iter_lim=args.linear_iterations, show=False)
        solution = np.asarray(result[0])
        q = solution[: 3 * n]
        u = solution[3 * n :]
        x = V0 + q.reshape(n, 3)
        linear_report = {"iterations": int(result[2]), "istop": int(result[1]), "residualNorm": float(result[3]), "arnorm": float(result[7]), "acond": float(result[6]), "xnorm": float(result[8]), "source": "neutral_linear_inverse"}
    else:
        x = saved_state["positions"].astype(float)
        u = saved_state["controlCoefficients"].astype(float)
        q = x - V0
        result = None
        linear_report = {"iterations": 0, "istop": 0, "residualNorm": None, "arnorm": None, "acond": None, "xnorm": float(np.linalg.norm(q)), "source": str(args.initial_state)}
    external = np.asarray(Bforce @ u).reshape(n, 3)

    initial_relax_iterations = 0 if saved_state is not None else args.nonlinear_iterations
    x, nonlinear = nonlinear_force_equilibrium(V0, x, external, support_graph, edges, rest, BASE, args.support_ratio, initial_relax_iterations, args.nonlinear_inner_iterations, physics)
    optimization_history = []
    if args.outer_iterations > 0:
        x, u, optimization_history = iterative_force_update(V0, x, u, Bforce, L, d2, F, support_graph, edges, rest, BASE, args.support_ratio, eye, args.outer_regularization, args.outer_iterations, args.response_iterations, args.nonlinear_inner_iterations, nonlinear["finalGradientNorm"], physics)
        external = np.asarray(Bforce @ u).reshape(n, 3)

    # Nonlinear audit at the actual state. This is not a hard landmark
    # projection. It reports the physical residual for the force-controlled
    # state and geometry integrity independently.
    if physics is None:
        Jx, rx, lengths = BASE.spring_jacobian(x, edges, rest, V0)
        Jxs, rxs = build_support_jacobian(x, graph, edges, BASE, args.support_ratio)
        source_scale = 1.0
    else:
        Jx, rx, lengths = weighted_spring_jacobian(BASE, x, edges, rest, V0, physics["surfaceStiffness"], physics["sourceMetersPerUnit"])
        Jxs, rxs, _ = gpu_consistent_support_jacobian(x, physics["supportData"], BASE, physics["sourceMetersPerUnit"])
        source_scale = physics["sourceMetersPerUnit"]
    grad = np.asarray(Jx.T @ rx).reshape(-1)
    if len(rxs):
        grad += np.asarray(Jxs.T @ rxs).reshape(-1)
    force_balance = grad.reshape(n, 3) / source_scale - external
    achieved_lm = landmark_positions(x, T, Bary)
    achieved_2d = np.column_stack(((achieved_lm - neutral_lm) @ right, (achieved_lm - neutral_lm) @ up))
    target_2d = np.column_stack((d3 @ right, d3 @ up))
    error_2d = achieved_2d - target_2d
    before_2d = -target_2d
    regional_errors = {}
    for name, ids in REGIONS.items():
        valid = np.asarray([i for i in ids if i < len(error_2d)], dtype=np.int64)
        regional_errors[name] = {
            "landmarkCount": int(len(valid)),
            "beforeMean": float(np.mean(np.linalg.norm(before_2d[valid], axis=1))) if len(valid) else None,
            "afterMean": float(np.mean(np.linalg.norm(error_2d[valid], axis=1))) if len(valid) else None,
            "afterP95": float(np.quantile(np.linalg.norm(error_2d[valid], axis=1), 0.95)) if len(valid) else None,
        }
    area0 = np.cross(V0[F[:, 1]] - V0[F[:, 0]], V0[F[:, 2]] - V0[F[:, 0]], axis=1)
    area1 = np.cross(x[F[:, 1]] - x[F[:, 0]], x[F[:, 2]] - x[F[:, 0]], axis=1)
    area0n = np.linalg.norm(area0, axis=1)
    area1n = np.linalg.norm(area1, axis=1)
    folds = int(np.sum((area0 * area1).sum(axis=1) < 0))
    collapsed = int(np.sum(area1n <= np.maximum(area0n * 1e-4, 1e-15)))
    positive_rest = rest > 1e-12
    strains = lengths[positive_rest] / rest[positive_rest] - 1.0 if np.any(positive_rest) else np.zeros(0)
    zero_rest_displacement = lengths[~positive_rest] if np.any(~positive_rest) else np.zeros(0)
    report = {
        "schema": "vela-reference-inverse-physics-v1",
        "model": args.model,
        "frame": int(args.frame),
        "method": "linearized constrained equilibrium inverse with compact barycentric force basis",
        "physicsDefinition": "gpu-rk4-consistent-static" if physics is not None else "legacy-plan-a5-static",
        "objective": {
            "landmarkTerm": "confidence-weighted image-plane squared error in target right/up axes",
            "forceRegularization": float(args.force_regularization),
            "temporalTerm": "not used for single-frame probe",
            "depth": "not optimized; existing target depth is not included in the image objective",
        },
        "inputs": {"vertices": int(n), "triangles": int(len(F)), "springs": int(len(edges)), "virtualSprings": int(graph["virtualSprings"].shape[0]) if not args.gpu_consistent else 0, "supportSprings": int(Jsupp.shape[0]), "landmarks": int(len(T)), "neutralSpringResidualMax": float(np.max(np.abs(residual0))) if len(residual0) else 0.0},
        "controls": {"count": int(len(controls)), "landmarkIds": controls.tolist(), "basisColumns": int(p), "forceDistribution": "original attachment triangle barycentric weights"},
        "scales": {"eyeWidth": eye, "equilibriumScale": eq_scale, "forceScale": force_scale},
        "linearSolve": linear_report,
        "nonlinearEquilibrium": {"iterations": int(nonlinear["iterations"]), "finalGradientNorm": float(nonlinear["finalGradientNorm"]), "finalEnergy": float(nonlinear["finalEnergy"]), "history": nonlinear["history"]},
        "forceOptimization": {"outerIterations": int(args.outer_iterations), "responseIterations": int(args.response_iterations), "regularization": float(args.outer_regularization), "history": optimization_history},
        "regionalErrors": regional_errors,
        "result": {"meanImageError": float(np.mean(np.linalg.norm(error_2d, axis=1))), "medianImageError": float(np.median(np.linalg.norm(error_2d, axis=1))), "p95ImageError": float(np.quantile(np.linalg.norm(error_2d, axis=1), 0.95)), "maxImageError": float(np.max(np.linalg.norm(error_2d, axis=1))), "forceNorm": float(np.linalg.norm(u)), "maxVertexDisplacement": float(np.max(np.linalg.norm(q.reshape(n, 3), axis=1))), "springEnergy": float(0.5 * np.sum(rx * rx) + 0.5 * args.support_ratio * np.sum(rxs * rxs)), "forceBalanceNorm": float(np.linalg.norm(force_balance)), "forceBalanceMax": float(np.max(np.linalg.norm(force_balance, axis=1))), "maxAbsPositiveRestEdgeStrain": float(np.max(np.abs(strains))) if len(strains) else 0.0, "p95AbsPositiveRestEdgeStrain": float(np.quantile(np.abs(strains), 0.95)) if len(strains) else 0.0, "maxZeroRestSpringLength": float(np.max(zero_rest_displacement)) if len(zero_rest_displacement) else 0.0, "positiveRestSpringCount": int(np.sum(positive_rest)), "zeroRestSpringCount": int(np.sum(~positive_rest)), "orientationReversalsConservative": folds, "triangleCollapses": collapsed, "finite": bool(np.isfinite(x).all())},
        "runtimeSeconds": time.perf_counter() - started,
        "status": "valid_state_unconverged_force_balance" if np.isfinite(x).all() and folds == 0 and collapsed == 0 else "invalid_geometry_or_orientation_reversals",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    np.savez_compressed(args.output.with_name(args.output.stem + "-positions.npz"), positions=x, originalPositions=V0, externalForces=external, controls=controls, controlCoefficients=u, originalIndices=graph["originalIndices"])
    print(json.dumps({"model": args.model, "frame": args.frame, "status": report["status"], "medianImageError": report["result"]["medianImageError"], "p95ImageError": report["result"]["p95ImageError"], "forceBalanceNorm": report["result"]["forceBalanceNorm"], "folds": folds, "runtimeSeconds": report["runtimeSeconds"]}))
    return report


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--model", required=True)
    p.add_argument("--gpu-consistent", action="store_true", help="use the calibrated RK4 spring, support, unit, and no-cross-island definition")
    p.add_argument("--graph", type=Path, required=True)
    p.add_argument("--targets", type=Path, required=True)
    p.add_argument("--target-json", type=Path, required=True)
    p.add_argument("--frame", type=int, default=45)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--initial-state", type=Path, default=None, help="reuse a saved inverse state and its force coefficients as the alpha-zero baseline")
    p.add_argument("--controls", type=int, default=16)
    p.add_argument("--support-ratio", type=float, default=0.1)
    p.add_argument("--equilibrium-scale", type=float, default=1.0)
    p.add_argument("--force-scale", type=float, default=0.01)
    p.add_argument("--force-regularization", type=float, default=1e-4)
    p.add_argument("--linear-iterations", type=int, default=80)
    p.add_argument("--linear-atol", type=float, default=1e-6)
    p.add_argument("--linear-btol", type=float, default=1e-6)
    p.add_argument("--nonlinear-iterations", type=int, default=6)
    p.add_argument("--nonlinear-inner-iterations", type=int, default=40)
    p.add_argument("--outer-iterations", type=int, default=0)
    p.add_argument("--response-iterations", type=int, default=30)
    p.add_argument("--outer-regularization", type=float, default=1e-4)
    args = p.parse_args()
    solve_inverse(args)


if __name__ == "__main__":
    main()
