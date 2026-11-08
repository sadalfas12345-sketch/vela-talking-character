"""Small analytic and independent regression tests for the A3 solver."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np


def load_solver():
    path = Path(__file__).with_name("solve_plan_a2_hookean.py")
    spec = importlib.util.spec_from_file_location("plan_a3_solver", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_single_spring():
    s = load_solver()
    x = np.array([[0.0, 0.0, 0.0], [2.0, 0.0, 0.0]])
    edges = np.array([[0, 1]], dtype=np.int64)
    J, residual, lengths = s.spring_jacobian(x, edges, np.array([1.0]))
    assert np.allclose(lengths, [2.0])
    assert np.allclose(residual, [1.0])
    assert np.allclose(J.toarray(), [[-1.0, 0.0, 0.0, 1.0, 0.0, 0.0]])


def test_two_springs_series():
    s = load_solver()
    x = np.array([[0.0, 0.0, 0.0], [1.5, 0.0, 0.0], [3.0, 0.0, 0.0]])
    edges = np.array([[0, 1], [1, 2]], dtype=np.int64)
    rest = np.array([1.0, 1.0])
    assert np.isclose(s.spring_energy(x, edges, rest), 0.25)
    J, residual, _ = s.spring_jacobian(x, edges, rest)
    assert np.allclose(residual, [0.5, 0.5])
    assert J.shape == (2, 9)


def test_zero_rest_seam():
    s = load_solver()
    x = np.array([[0.0, 0.0, 0.0], [0.1, -0.2, 0.3]])
    J, residual, _ = s.spring_jacobian(x, np.array([[0, 1]]), np.array([0.0]))
    assert np.allclose(residual, [-0.1, 0.2, -0.3])
    assert np.allclose(J.toarray(), [[1, 0, 0, -1, 0, 0], [0, 1, 0, 0, -1, 0], [0, 0, 1, 0, 0, -1]])


def test_barycentric_constraint_and_triangle():
    s = load_solver()
    x0 = np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]])
    edges = np.array([[0, 1], [1, 2], [2, 0]], dtype=np.int64)
    target = np.array([[0.05, 0.05, 0.0]])
    solved, report = s.solve_component(
        x0,
        edges,
        np.ones(3),
        np.array([[0, 1, 2]], dtype=np.int64),
        np.array([[0.5, 0.25, 0.25]]),
        target,
        max_iter=80,
        residual_tol=1e-9,
        force_tol=1e-7,
    )
    actual = np.sum(solved * np.array([[0.5], [0.25], [0.25]]), axis=0)
    assert np.allclose(actual, target[0], atol=1e-8)
    assert report["status"] == "converged", report
    assert report["maxStep"] < 1.0


def test_gauge_rank():
    s = load_solver()
    G = s.gauge_matrix(np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1]], dtype=float))
    assert np.linalg.matrix_rank(G.toarray()) == 6


if __name__ == "__main__":
    test_single_spring()
    test_two_springs_series()
    test_zero_rest_seam()
    test_barycentric_constraint_and_triangle()
    test_gauge_rank()
    print("Plan A3 Hookean solver regression tests: PASS")
