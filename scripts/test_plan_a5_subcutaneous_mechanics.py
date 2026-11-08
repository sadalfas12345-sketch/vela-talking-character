"""Plan A5 Stage-A mechanics tests.

These tests are intentionally small and independent of the Tripo meshes.  They
cover the new fixed inward-anchor energy bookkeeping while reusing the A4
spring Jacobian and sparse barycentric-constraint routines.  No source GLB is
modified by this test.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
from scipy import sparse


def load_a4():
    path = Path(__file__).with_name("solve_plan_a4_projected_hookean.py")
    spec = importlib.util.spec_from_file_location("plan_a4", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod, mod.load_base()


def energy(x, springs, rest, weights=None, fixed=None):
    x = np.asarray(x, dtype=float)
    springs = np.asarray(springs, dtype=np.int64)
    rest = np.asarray(rest, dtype=float)
    if weights is None:
        weights = np.ones(len(springs), dtype=float)
    a = x[springs[:, 0]]
    b = x[springs[:, 1]] if fixed is None else np.where(springs[:, 1, None] >= 0, x[springs[:, 1]], 0.0)
    if fixed is not None:
        # A negative second index denotes a fixed anchor supplied separately.
        b = np.empty_like(a)
        for i, (u, v) in enumerate(springs):
            b[i] = x[v] if v >= 0 else fixed[i]
    lengths = np.linalg.norm(a - b, axis=1)
    return float(0.5 * np.sum(weights * (lengths - rest) ** 2))


def finite_difference_gradient(fun, x, eps=1e-7):
    out = np.zeros_like(x, dtype=float)
    for i in range(x.size):
        xp = x.copy(); xm = x.copy(); xp[i] += eps; xm[i] -= eps
        out[i] = (fun(xp) - fun(xm)) / (2.0 * eps)
    return out


def main():
    a4, base = load_a4()
    checks = {}

    # One free surface vertex linked to its fixed inward anchor and to a
    # neighboring fixed anchor.  This is the A5 support topology in miniature.
    x = np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]], dtype=float)
    edges = np.array([[0, 1], [1, 2], [2, 0]], dtype=np.int64)
    rest = np.linalg.norm(x[edges[:, 0]] - x[edges[:, 1]], axis=1)
    changed = x.copy(); changed[0] += [0.1, 0.05, -0.02]
    J, residual, lengths = base.spring_jacobian(changed, edges, rest, None)
    checks["surface_spring"] = {"pass": bool(J.shape == (3, 9) and np.all(np.isfinite(residual)) and np.all(lengths > 0)), "jacobianShape": list(J.shape)}

    support_springs = np.array([[0, -1], [0, -1]], dtype=np.int64)
    fixed_anchors = np.array([[0.0, 0.0, -0.1], [0.1, 0.0, -0.1]], dtype=float)
    support_rest = np.linalg.norm(x[0] - fixed_anchors, axis=1)
    q = changed.reshape(-1)
    fn = lambda flat: energy(flat.reshape((-1, 3)), support_springs, support_rest, np.array([2.0, 2.0]), fixed_anchors)
    analytic = np.zeros_like(q)
    a = changed[0] - fixed_anchors[0]; b = changed[0] - fixed_anchors[1]
    analytic[:3] = 2.0 * ((np.linalg.norm(a) - support_rest[0]) * a / np.linalg.norm(a) + (np.linalg.norm(b) - support_rest[1]) * b / np.linalg.norm(b))
    numeric = finite_difference_gradient(fn, q)
    checks["anchor_gradient_fd"] = {"pass": bool(np.max(np.abs(analytic - numeric)) < 2e-7), "maxAbsError": float(np.max(np.abs(analytic - numeric)))}

    # Ratio zero must remove the support contribution exactly.
    e0 = energy(q.reshape((-1, 3)), support_springs, support_rest, np.zeros(2), fixed_anchors)
    checks["zero_support_ratio"] = {"pass": bool(abs(e0) < 1e-15), "energy": e0}

    # Interior barycentric hard constraint has the expected rank and is not
    # replaced by vertex snapping.
    C = sparse.csr_matrix([[0.2, 0.0, 0.0, 0.3, 0.0, 0.0, 0.5, 0.0, 0.0]])
    reduced = a4.reduce_constraint_rows_sparse(C)
    checks["barycentric_constraint_rank"] = {"pass": bool(reduced["rank"] == 1), "rank": int(reduced["rank"])}

    passed = all(v["pass"] for v in checks.values())
    print({"passed": passed, "checks": checks})
    raise SystemExit(0 if passed else 1)


if __name__ == "__main__":
    main()
