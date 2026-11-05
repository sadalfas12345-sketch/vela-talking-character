"""Non-rigidly fit Vela's animation-ready Avaturn facial meshes to Tripo landmarks.

Inputs are read-only GLBs plus Blender ray-hit correspondences prepared by
evaluate_avaturn_landmark_fit.py. Outputs are deterministic NumPy arrays and a
quality report; this script does not alter or export either source character.
"""
import json
from pathlib import Path

import numpy as np
from scipy import sparse
from scipy.sparse.linalg import factorized

ROOT = Path(__file__).resolve().parents[1]
POINTS = ROOT / 'verification' / 'avaturn-face-fit-landmark-points.json'
MESHES = ROOT / 'verification' / 'avaturn-face-fit-source-meshes.npz'
LANDMARKS = ROOT / 'verification' / 'avaturn-face-fit-landmarks.json'
OUTPUT = ROOT / 'verification' / 'avaturn-tripo-facefit-deformed.npz'
REPORT = ROOT / 'verification' / 'avaturn-tripo-facefit-report.json'
FACE_OVAL = [10, 338, 297, 332, 284, 251, 389, 356, 454, 323, 361, 288,
             397, 365, 379, 378, 400, 377, 152, 148, 176, 149, 150, 136,
             172, 58, 132, 93, 234, 127, 162, 21, 54, 103, 67, 109]


def rigid_fit(source, target):
    source_mean, target_mean = source.mean(axis=0), target.mean(axis=0)
    a, b = source - source_mean, target - target_mean
    u, singular, vt = np.linalg.svd(a.T @ b)
    sign = np.linalg.det(u @ vt)
    correction = np.diag([1.0, 1.0, sign])
    rotation = u @ correction @ vt
    scale = float(np.sum(singular * np.diag(correction)) / np.sum(a * a))
    translation = target_mean - scale * source_mean @ rotation
    return scale, rotation, translation


def barycentric_handles(points, report, triangles):
    face_ids = np.asarray(report['donorFaceIds'], dtype=np.int32)
    bary = np.asarray(report['donorBarycentric'], dtype=np.float64)
    valid = np.isfinite(points[:, 0]) & np.isfinite(np.asarray(report['targetPoints'])[:, 0]) & (face_ids >= 0)
    rows = np.flatnonzero(valid)
    faces = triangles[face_ids[rows]]
    C = sparse.coo_matrix((bary[rows].ravel(),
                           (np.repeat(np.arange(len(rows)), 3), faces.ravel())),
                          shape=(len(rows), len(triangles) and int(triangles.max()) + 1)).tocsr()
    return rows, faces, C


def arap_fit(vertices, triangles, C, targets, scale, rotation, translation, iterations=30, handle_weight=10.0):
    base = scale * (vertices - np.mean(np.asarray(points['donorPoints'])[valid], axis=0)) @ rotation + translation
    edges = np.vstack((triangles[:, [0, 1]], triangles[:, [1, 2]], triangles[:, [2, 0]]))
    edges, incidence = np.unique(np.sort(edges, axis=1), axis=0, return_counts=True)
    left, right = edges[:, 0], edges[:, 1]
    weights = incidence.astype(np.float64)
    count = len(vertices)
    adjacency = sparse.coo_matrix((np.r_[weights, weights],
                                   (np.r_[left, right], np.r_[right, left])),
                                  shape=(count, count)).tocsr()
    laplacian = sparse.diags(np.asarray(adjacency.sum(axis=1)).ravel()) - adjacency
    system = laplacian + handle_weight * (C.T @ C)
    solve = factorized(system.tocsc())
    X = base.copy()
    rotations = np.tile(np.eye(3), (count, 1, 1))
    handle_rhs = handle_weight * (C.T @ targets)
    for _ in range(iterations):
        covariance = np.zeros((count, 3, 3), dtype=np.float64)
        for (i, j), w in zip(edges, weights):
            covariance[i] += w * np.outer(X[i] - X[j], base[i] - base[j])
            covariance[j] += w * np.outer(X[j] - X[i], base[j] - base[i])
        for i in range(count):
            u, _s, vt = np.linalg.svd(covariance[i])
            correction = np.eye(3)
            correction[2, 2] = np.linalg.det(u @ vt)
            rotations[i] = u @ correction @ vt
        average_rotation = 0.5 * (rotations[left] + rotations[right])
        desired_edges = np.einsum('eij,ej->ei', average_rotation,
                                  base[left] - base[right]) * weights[:, None]
        rhs = np.zeros_like(X)
        np.add.at(rhs, left, desired_edges)
        np.add.at(rhs, right, -desired_edges)
        rhs += handle_rhs
        X = np.column_stack([solve(rhs[:, axis]) for axis in range(3)])
    return base, X, rotations, edges


def apply_nearest_displacement(query, source, displacement, rotations, k=8):
    from scipy.spatial import cKDTree
    distances, indices = cKDTree(source).query(query, k=min(k, len(source)))
    distances = np.atleast_2d(distances) if np.ndim(distances) == 1 else distances
    indices = np.atleast_2d(indices) if np.ndim(indices) == 1 else indices
    if distances.shape[0] != len(query):
        distances, indices = distances.T, indices.T
    weights = 1.0 / np.maximum(distances, 1e-5) ** 2
    weights /= weights.sum(axis=1, keepdims=True)
    delta = np.einsum('nk,nkd->nd', weights, displacement[indices])
    blended = np.einsum('nk,nkij->nij', weights, rotations[indices])
    projected = np.empty_like(blended)
    for i, matrix in enumerate(blended):
        u, _s, vt = np.linalg.svd(matrix)
        corr = np.eye(3)
        corr[2, 2] = np.linalg.det(u @ vt)
        projected[i] = u @ corr @ vt
    return delta, projected


points = json.loads(POINTS.read_text(encoding='utf-8'))
donor_points = np.asarray(points['donorPoints'], dtype=np.float64)
target_points = np.asarray(points['targetPoints'], dtype=np.float64)
face_ids = np.asarray(points['donorFaceIds'], dtype=np.int32)
bary = np.asarray(points['donorBarycentric'], dtype=np.float64)
valid = np.isfinite(donor_points[:, 0]) & np.isfinite(target_points[:, 0]) & (face_ids >= 0)
rows = np.flatnonzero(valid)
mesh_data = np.load(MESHES)
head_vertices = mesh_data['Head_Mesh__Basis'].astype(np.float64)
head_triangles = mesh_data['Head_Mesh__Triangles'].astype(np.int32)
handle_faces = head_triangles[face_ids[rows]]
handle_matrix = sparse.coo_matrix((bary[rows].ravel(),
                                   (np.repeat(np.arange(len(rows)), 3), handle_faces.ravel())),
                                  shape=(len(rows), len(head_vertices))).tocsr()
scale, rotation, translation = rigid_fit(donor_points[rows], target_points[rows])
base, fitted, local_rotations, edges = arap_fit(
    head_vertices, head_triangles, handle_matrix, target_points[rows], scale, rotation, translation)
handle_error = np.linalg.norm(handle_matrix @ fitted - target_points[rows], axis=1)

# Full-face acceptance groups use the same documented MediaPipe topology indices.
groups = {
    'all': rows,
    'face_oval': np.asarray([i for i in FACE_OVAL if valid[i]], dtype=np.int32),
    'eyes': np.asarray([i for i in [33, 133, 362, 263, 159, 145, 386, 374, 468, 473] if valid[i]], dtype=np.int32),
    'mouth': np.asarray([i for i in [61, 291, 13, 14, 78, 308, 95, 324, 82, 312, 87, 317] if valid[i]], dtype=np.int32),
}
per_landmark_error = np.full(len(valid), np.nan)
per_landmark_error[rows] = handle_error
group_report = {}
for name, indices in groups.items():
    errors = per_landmark_error[indices]
    group_report[name] = {
        'count': int(len(errors)), 'medianMillimeters': float(np.median(errors) * 1000),
        'p95Millimeters': float(np.percentile(errors, 95) * 1000),
        'maxMillimeters': float(np.max(errors) * 1000),
    }

# Face-surface element quality after the non-rigid fit.
normal_before = np.cross(base[head_triangles[:, 1]] - base[head_triangles[:, 0]],
                         base[head_triangles[:, 2]] - base[head_triangles[:, 0]])
normal_after = np.cross(fitted[head_triangles[:, 1]] - fitted[head_triangles[:, 0]],
                        fitted[head_triangles[:, 2]] - fitted[head_triangles[:, 0]])
area_before = np.linalg.norm(normal_before, axis=1)
area_after = np.linalg.norm(normal_after, axis=1)
normal_dot = np.sum(normal_before * normal_after, axis=1) / np.maximum(area_before * area_after, 1e-20)
area_ratio = area_after / np.maximum(area_before, 1e-20)

# Morphs receive the fitted neutral positions plus the local rigid rotation of
# each source deformation vector. Other facial meshes use a smooth k-neighbor
# displacement field and the same local rotation field.
arrays = {}
names = [k for k in mesh_data.files if k.endswith('__Basis')]
for key in names:
    prefix = key[:-7]
    source_base = mesh_data[key].astype(np.float64)
    pre = scale * (source_base - np.mean(donor_points[rows], axis=0)) @ rotation + translation
    if prefix == 'Head_Mesh':
        out_base = fitted
        local_r = local_rotations
    else:
        displacement, local_r = apply_nearest_displacement(pre, base, fitted - base, local_rotations)
        out_base = pre + displacement
    arrays[prefix + '__Basis'] = out_base.astype(np.float32)
    triangle_key = prefix + '__Triangles'
    if triangle_key in mesh_data:
        arrays[triangle_key] = mesh_data[triangle_key]
    key_name_key = prefix + '__KeyNames'
    if key_name_key in mesh_data:
        arrays[key_name_key] = mesh_data[key_name_key]
    for shape_key in mesh_data.files:
        stem = prefix + '__Key__'
        if not shape_key.startswith(stem):
            continue
        source_shape = mesh_data[shape_key].astype(np.float64)
        shape_pre = scale * (source_shape - np.mean(donor_points[rows], axis=0)) @ rotation + translation
        delta = shape_pre - pre
        warped_delta = np.einsum('ni,nji->nj', delta, local_r)
        arrays[shape_key] = (out_base + warped_delta).astype(np.float32)

np.savez_compressed(OUTPUT, **arrays)
report = {
    'method': 'Global similarity alignment followed by deterministic ARAP surface fitting with barycentric constraints from 478 independent face-landmark rays.',
    'inputs': {'donorGLB': 'TalkingHead/avatars/avaturn.glb', 'targetGLB': 'assets/tripo/vela-photoreal/generated-rigged.glb'},
    'landmarks': {'donorValid': int(np.isfinite(donor_points[:, 0]).sum()), 'targetValid': int(np.isfinite(target_points[:, 0]).sum()), 'jointlyConstrained': int(len(rows)), 'groups': group_report},
    'similarity': {'scale': scale, 'rotation': rotation.tolist(), 'translation': translation.tolist()},
    'arap': {'iterations': 30, 'uniformEdgeWeights': True, 'landmarkConstraintWeight': 10.0,
             'triangleCount': int(len(head_triangles)), 'normalTurnOver90Degrees': int(np.sum(normal_dot < 0)),
             'normalTurnOver90Fraction': float(np.mean(normal_dot < 0)),
             'triangleAreaRatioPercentiles': [float(x) for x in np.percentile(area_ratio, [1, 5, 50, 95, 99])],
             'trianglesBelow10PercentArea': int(np.sum(area_ratio < 0.1))},
    'outputs': {'deformedMeshes': str(OUTPUT.relative_to(ROOT)), 'preservesMorphTargets': True},
    'limitations': ['This is a fitting feasibility artifact, not an accepted avatar. Texture projection, face-patch seams, self-intersection, runtime morph behavior, and all acceptance gates remain to be verified.'],
}
REPORT.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
print(json.dumps(report, indent=2))
