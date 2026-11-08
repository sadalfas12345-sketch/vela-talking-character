"""Bounded Plan A4 unit tests for projected Hookean equilibrium."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
from scipy import sparse


def load():
    path = Path(__file__).with_name("solve_plan_a4_projected_hookean.py")
    spec = importlib.util.spec_from_file_location("plan_a4", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod, mod.load_base()


def main():
    a4, base = load()
    checks = {}
    # Non-vertex barycentric constraint on a triangle.
    x = np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]])
    edges = np.array([[0, 1], [1, 2], [2, 0]], dtype=np.int64)
    rest = np.array([1.0, np.sqrt(2.0), 1.0])
    tri = np.array([[0, 1, 2]], dtype=np.int64)
    bary = np.array([[0.2, 0.3, 0.5]])
    target = np.array([[0.3, 0.5, 0.1]])
    solved, report = a4.solve_component_projected(base, x, edges, rest, tri, bary, target, 50, 1e-9, 1e-6, 1e-8, 20, 1e-11, 100)
    actual = bary[0, 0] * solved[0] + bary[0, 1] * solved[1] + bary[0, 2] * solved[2]
    checks["barycentric_triangle"] = {"pass": bool(report["status"] == "converged" and np.linalg.norm(actual - target[0]) < 1e-9), "status": report["status"], "error": float(np.linalg.norm(actual - target[0]))}

    # Redundant constraints are detected in row space without dense vertex data.
    C = sparse.csr_matrix([[1.0, 0, 0], [2.0, 0, 0], [0, 1.0, 0]])
    reduction = a4.reduce_constraint_rows_sparse(C)
    checks["redundant_rows"] = {"pass": bool(reduction["rank"] == 2 and len(reduction["omitted"]) == 1), "rank": int(reduction["rank"]), "omitted": reduction["omitted"].tolist()}

    # A coincident zero-rest seam remains a Cartesian Hookean residual.
    J, residual, _ = base.spring_jacobian(np.array([[0.0, 0.0, 0.0], [0.1, 0.0, 0.0]]), np.array([[0, 1]], dtype=np.int64), np.array([0.0]), None)
    checks["zero_rest_spring"] = {"pass": bool(J.shape == (3, 6) and np.allclose(residual, [-0.1, 0.0, 0.0])), "jacobianShape": list(J.shape), "residual": residual.tolist()}
    passed = all(v["pass"] for v in checks.values())
    print({"passed": passed, "checks": checks})
    raise SystemExit(0 if passed else 1)


if __name__ == "__main__":
    main()
