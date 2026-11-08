"""Regression tests for Plan A3 triangle-edge topology classification."""
from __future__ import annotations

from collections import Counter

import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components


def edge_counts(faces: np.ndarray) -> Counter:
    raw = np.vstack((faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]))
    raw = np.sort(raw, axis=1)
    return Counter(tuple(edge) for edge in raw.tolist())


def stats(faces: np.ndarray, vertex_count: int) -> dict:
    counts = edge_counts(faces)
    graph_edges = np.asarray(list(counts), dtype=np.int64).reshape(-1, 2)
    graph = coo_matrix(
        (np.ones(len(graph_edges)), (graph_edges[:, 0], graph_edges[:, 1])),
        shape=(vertex_count, vertex_count),
    ).tocsr()
    components, _ = connected_components(graph, directed=False)
    return {
        "edges": len(counts),
        "boundary_edges": sum(v == 1 for v in counts.values()),
        "interior_edges": sum(v == 2 for v in counts.values()),
        "nonmanifold_edges": sum(v > 2 for v in counts.values()),
        "components": int(components),
    }


def test_two_triangles():
    # A square made of two triangles has one shared interior edge and four
    # boundary edges.
    f = np.array([[0, 1, 2], [0, 2, 3]], dtype=np.int64)
    assert stats(f, 4) == {
        "edges": 5,
        "boundary_edges": 4,
        "interior_edges": 1,
        "nonmanifold_edges": 0,
        "components": 1,
    }


def test_closed_tetrahedron():
    f = np.array(
        [[0, 1, 2], [0, 3, 1], [1, 3, 2], [0, 2, 3]], dtype=np.int64
    )
    assert stats(f, 4) == {
        "edges": 6,
        "boundary_edges": 0,
        "interior_edges": 6,
        "nonmanifold_edges": 0,
        "components": 1,
    }


def test_disconnected_open_patches():
    f = np.array(
        [[0, 1, 2], [0, 2, 3], [4, 5, 6], [4, 6, 7]], dtype=np.int64
    )
    result = stats(f, 8)
    assert result["boundary_edges"] == 8
    assert result["interior_edges"] == 2
    assert result["components"] == 2


def test_overlapping_surfaces_remain_disconnected():
    # Same coordinates are irrelevant to topology: two coincident triangles
    # with distinct vertex IDs must remain two components and must not become
    # a virtual connection merely because they overlap spatially.
    f = np.array([[0, 1, 2], [3, 4, 5]], dtype=np.int64)
    result = stats(f, 6)
    assert result["boundary_edges"] == 6
    assert result["components"] == 2


if __name__ == "__main__":
    test_two_triangles()
    test_closed_tetrahedron()
    test_disconnected_open_patches()
    test_overlapping_surfaces_remain_disconnected()
    print("Plan A3 topology regression tests: PASS")
