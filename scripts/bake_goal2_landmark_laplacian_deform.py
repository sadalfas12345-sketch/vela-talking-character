"""Bake existing Goal-2 landmark trajectories through Blender Laplacian Deform.

This script does not track video or recompute correspondence. It consumes the
Step-4 marker trajectories and the Goal-1 barycentric attachments, converts the
surface-point constraints to mesh-vertex anchor displacements, and bakes the
evaluated built-in Laplacian Deform modifier into shape keys on the original
render mesh.
"""
import json
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector


def arg(name):
    argv = sys.argv[sys.argv.index('--') + 1:]
    if name not in argv:
        raise SystemExit(f'missing {name}')
    return Path(argv[argv.index(name) + 1]).resolve()


def set_active(obj):
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def world_vertices(obj):
    local = np.empty((len(obj.data.vertices), 3), dtype=np.float64)
    obj.data.vertices.foreach_get('co', local.ravel())
    m = np.asarray(obj.matrix_world, dtype=np.float64)
    return local @ m[:3, :3].T + m[:3, 3], local, m


def barycentric_anchor_displacements(records, marker_neutral, marker_target, ids):
    """Solve A*d = target landmark displacement with minimum vertex motion."""
    vertices = sorted({int(v) for i in ids for v in records[i]['triangleVertexIndices']})
    col = {v: j for j, v in enumerate(vertices)}
    A = np.zeros((len(ids), len(vertices)), dtype=np.float64)
    desired = np.zeros((len(ids), 3), dtype=np.float64)
    for row, i in enumerate(ids):
        rec = records[i]
        tri = [int(v) for v in rec['triangleVertexIndices']]
        bary = np.asarray(rec['barycentricCoordinates'], dtype=np.float64)
        for v, b in zip(tri, bary):
            A[row, col[v]] = b
        desired[row] = np.asarray(marker_target[i]) - np.asarray(marker_neutral[i])
    gram = A @ A.T
    rank = int(np.linalg.matrix_rank(A))
    if rank < len(ids):
        raise RuntimeError(f'barycentric control system rank deficient: {rank}/{len(ids)}')
    # Minimum-norm exact solution for each coordinate: A.T (A A.T)^-1 b.
    d = A.T @ np.linalg.solve(gram, desired)
    residual = A @ d - desired
    return vertices, d, float(np.max(np.abs(residual))), rank


def add_laplacian_and_evaluate(body, proxy_indices, proxy_faces, anchor_proxy_indices, anchor_local_delta, iterations=30):
    """Evaluate Blender's built-in modifier on an original-surface local proxy."""
    base_local = np.empty((len(body.data.vertices), 3), dtype=np.float64)
    body.data.vertices.foreach_get('co', base_local.ravel())
    proxy_local = base_local[np.asarray(proxy_indices, dtype=int)]
    proxy_mesh = bpy.data.meshes.new('__goal2_laplacian_proxy_mesh__')
    proxy_mesh.from_pydata(proxy_local.tolist(), [], proxy_faces)
    proxy_mesh.update()
    temp = bpy.data.objects.new('__goal2_laplacian_temp__', proxy_mesh)
    temp.name = '__goal2_laplacian_temp__'
    bpy.context.collection.objects.link(temp)
    temp.matrix_world = body.matrix_world.copy()
    group = temp.vertex_groups.new(name='__goal2_laplacian_anchors__')
    group.add(anchor_proxy_indices, 1.0, 'REPLACE')
    modifier = temp.modifiers.new(name='__goal2_builtin_laplacian__', type='LAPLACIANDEFORM')
    modifier.vertex_group = group.name
    modifier.iterations = int(iterations)
    set_active(temp)
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.laplaciandeform_bind(modifier=modifier.name)
    if not modifier.is_bind:
        raise RuntimeError('Blender Laplacian Deform modifier did not bind')
    # Anchor motion is applied after binding, which is Blender's documented
    # Laplacian Deform workflow.
    for vertex_index, delta in zip(anchor_proxy_indices, anchor_local_delta):
        temp.data.vertices[int(vertex_index)].co += Vector(delta.tolist())
    temp.data.update()
    bpy.context.view_layer.update()
    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated = temp.evaluated_get(depsgraph)
    evaluated_mesh = evaluated.to_mesh()
    result = np.empty((len(evaluated_mesh.vertices), 3), dtype=np.float64)
    evaluated_mesh.vertices.foreach_get('co', result.ravel())
    evaluated.to_mesh_clear()
    bpy.data.objects.remove(temp, do_unlink=True)
    bpy.data.meshes.remove(proxy_mesh)
    return result


def main():
    source = arg('--source')
    goal1_path = arg('--goal1')
    markers_path = arg('--markers')
    output = arg('--output')
    report_path = arg('--report')

    goal1 = json.loads(goal1_path.read_text())
    records = {int(r['index']): r for r in goal1['records'] if r.get('meshXYZ') is not None}
    markers = json.loads(markers_path.read_text())
    required = list(range(468))
    missing = [i for i in required if i not in records]
    if missing:
        raise SystemExit(f'missing Goal-1 attachments: {missing}')
    marker_neutral = {i: markers['neutral'][i] for i in required}
    for i in required:
        if np.linalg.norm(np.asarray(marker_neutral[i]) - np.asarray(records[i]['meshXYZ'])) > 1e-7:
            raise SystemExit(f'marker neutral does not match Goal-1 attachment at landmark {i}')

    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(source))
    meshes = [o for o in bpy.context.scene.objects if o.type == 'MESH']
    if not meshes:
        raise SystemExit('GLB contains no mesh')
    body = max(meshes, key=lambda o: len(o.data.vertices))
    base_world, base_local, matrix = world_vertices(body)
    inv_linear = np.linalg.inv(matrix[:3, :3])

    target_points = np.asarray([records[i]['meshXYZ'] for i in required], dtype=np.float64)
    face_center = np.mean(target_points[[33, 263, 1, 152]], axis=0)
    face_radius = float(np.max(np.linalg.norm(target_points - face_center, axis=1)) * 1.20)
    vertex_distance = np.linalg.norm(base_world - face_center, axis=1)
    control_ids = [70, 63, 105, 336, 293, 334, 159, 145, 386, 374, 33, 133, 263, 362, 168, 6, 1, 98, 327, 234, 454, 152, 10, 127, 356]
    marker_ids = {str(i): i for i in range(468)}
    neutral = markers['neutral']
    sample_names = [k for k in ('25', '50', '75', '100') if k in markers['samples']]
    if not sample_names:
        raise SystemExit('marker manifest has no 25/50/75/100 samples')

    # Build a local proxy from the original render mesh. A face triangle enters
    # when it touches the automatically derived facial region; all original
    # vertices of those triangles are retained in the proxy. The proxy boundary
    # is held fixed, and control-triangle vertices are added as anchors.
    polygons = []
    proxy_orig_set = set()
    discarded_degenerate = 0
    discarded_duplicate = 0
    seen_triangles = set()
    for poly in body.data.polygons:
        pv = [int(v) for v in poly.vertices]
        if any(vertex_distance[v] <= face_radius for v in pv):
            for k in range(1, len(pv) - 1):
                tri = (pv[0], pv[k], pv[k + 1])
                area2 = float(np.linalg.norm(np.cross(base_world[tri[1]] - base_world[tri[0]], base_world[tri[2]] - base_world[tri[0]])))
                if area2 <= max(face_radius * face_radius * 1e-12, 1e-18):
                    discarded_degenerate += 1
                    continue
                tri_key = tuple(sorted(tri))
                if tri_key in seen_triangles:
                    discarded_duplicate += 1
                    continue
                seen_triangles.add(tri_key)
                polygons.append(tri)
                proxy_orig_set.update(tri)
    proxy_indices = sorted(proxy_orig_set)
    proxy_lookup = {v: i for i, v in enumerate(proxy_indices)}
    proxy_faces = [tuple(proxy_lookup[v] for v in tri) for tri in polygons]
    control_orig = set(int(v) for i in control_ids for v in records[i]['triangleVertexIndices'])
    # Every disconnected proxy component needs at least one fixed anchor for
    # Blender's Laplacian system to be nonsingular. Representatives are derived
    # from the proxy connectivity, never from character-specific vertex IDs.
    parent = list(range(len(proxy_indices)))
    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra
    for tri in proxy_faces:
        union(tri[0], tri[1]); union(tri[1], tri[2]); union(tri[2], tri[0])
    component_members = {}
    for i in range(len(proxy_indices)):
        component_members.setdefault(find(i), []).append(i)
    component_solves = []
    for members in component_members.values():
        member_orig = {proxy_indices[i] for i in members}
        component_control_orig = control_orig.intersection(member_orig)
        if not component_control_orig:
            continue
        old_members = sorted(members)
        old_to_new = {old: j for j, old in enumerate(old_members)}
        comp_proxy_indices = [proxy_indices[old] for old in old_members]
        comp_faces = [tuple(old_to_new[v] for v in tri) for tri in proxy_faces if all(v in set(old_members) for v in tri)]
        comp_lookup = {v: i for i, v in enumerate(comp_proxy_indices)}
        comp_boundary = set()
        for pface in comp_faces:
            if any(vertex_distance[comp_proxy_indices[v]] > face_radius for v in pface):
                comp_boundary.update(pface)
        # Three separated fixed points remove translation and rotational null
        # modes without relying on any target-model vertex numbering.
        chosen = [old_members[0]]
        if len(old_members) > 1:
            p = base_world[np.asarray(comp_proxy_indices)]
            chosen.append(old_members[int(np.argmax(np.linalg.norm(p - p[0], axis=1)))])
        if len(old_members) > 2:
            p0 = base_world[proxy_indices[chosen[0]]]
            p1 = base_world[proxy_indices[chosen[1]]]
            line = p1 - p0
            line_norm = max(float(np.linalg.norm(line)), 1e-12)
            distances = []
            for i in old_members:
                v = base_world[proxy_indices[i]] - p0
                distances.append(np.linalg.norm(v - line * (np.dot(v, line) / (line_norm * line_norm))))
            chosen.append(old_members[int(np.argmax(distances))])
        component_anchor_orig = set(component_control_orig)
        component_anchor_orig.update(comp_proxy_indices[i] for i in comp_boundary)
        component_anchor_orig.update(proxy_indices[i] for i in chosen)
        anchor_orig = sorted(component_anchor_orig)
        component_solves.append({'proxy_indices': comp_proxy_indices, 'proxy_faces': comp_faces, 'anchor_orig': anchor_orig, 'anchor_proxy_indices': [comp_lookup[v] for v in anchor_orig]})
    missing_control_vertices = sorted(control_orig - {v for c in component_solves for v in c['anchor_orig'] if v in control_orig})
    if missing_control_vertices:
        raise RuntimeError(f'required anatomical controls were not assigned to a local solve: {missing_control_vertices[:12]}')
    # A temporary neutral Basis preserves the original GLB neutral exactly.
    if not body.data.shape_keys:
        body.shape_key_add(name='Basis', from_mix=False)
    elif body.data.shape_keys.key_blocks.get('Basis') is None:
        body.shape_key_add(name='Basis', from_mix=False)

    metrics = {}
    for sample_name in sample_names:
        target = markers['samples'][sample_name]
        moving_vertices, moving_delta_world, residual, rank = barycentric_anchor_displacements(records, neutral, target, control_ids)
        delta_by_vertex = {v: d for v, d in zip(moving_vertices, moving_delta_world)}
        posed_local = base_local.copy()
        for component in component_solves:
            anchor_local_delta = np.zeros((len(component['anchor_orig']), 3), dtype=np.float64)
            for j, v in enumerate(component['anchor_orig']):
                if v in delta_by_vertex:
                    anchor_local_delta[j] = delta_by_vertex[v] @ inv_linear.T
            posed_proxy_local = add_laplacian_and_evaluate(body, component['proxy_indices'], component['proxy_faces'], component['anchor_proxy_indices'], anchor_local_delta)
            posed_local[np.asarray(component['proxy_indices'], dtype=int)] = posed_proxy_local
        key = body.data.shape_keys.key_blocks.get(f'video_landmark_{sample_name}')
        if key is None:
            key = body.shape_key_add(name=f'video_landmark_{sample_name}', from_mix=False)
        key.data.foreach_set('co', posed_local.astype(np.float32).ravel())
        key.value = 0.0
        posed_world = posed_local @ matrix[:3, :3].T + matrix[:3, 3]
        # Check actual barycentric landmark positions after the modifier bake.
        achieved = []
        for i in control_ids:
            tri = np.asarray(records[i]['triangleVertexIndices'], dtype=int)
            bary = np.asarray(records[i]['barycentricCoordinates'], dtype=float)
            achieved.append((bary[:, None] * posed_world[tri]).sum(axis=0))
        achieved = np.asarray(achieved)
        requested = np.asarray([target[i] for i in control_ids], dtype=float)
        metrics[sample_name] = {
            'requestedAnchorResidualBeforeModifierMax': residual,
            'barycentricControlRank': rank,
            'maxBarycentricErrorAfterModifier': float(np.max(np.linalg.norm(achieved - requested, axis=1))),
            'meanBarycentricErrorAfterModifier': float(np.mean(np.linalg.norm(achieved - requested, axis=1))),
            'shapeKey': key.name,
        }

    body.data.shape_keys.animation_data_clear()
    bpy.ops.object.select_all(action='DESELECT')
    for obj in bpy.context.scene.objects:
        if obj.type in {'MESH', 'ARMATURE', 'EMPTY'}:
            obj.select_set(True)
    bpy.context.view_layer.objects.active = body
    output.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.gltf(filepath=str(output), export_format='GLB', export_morph=True, export_skins=True, export_animations=True, export_apply=False)
    report = {
        'architecture': 'Blender built-in Laplacian Deform modifier; Goal-1 barycentric controls converted to mesh anchors; original render mesh retained',
        'source': str(source), 'goal1Manifest': str(goal1_path), 'markerManifest': str(markers_path), 'output': str(output),
        'targetMesh': body.name, 'targetVertexCount': len(body.data.vertices),
        'targetHasArmature': any(o.type == 'ARMATURE' for o in bpy.context.scene.objects),
        'requiredLandmarkCount': 468, 'missingLandmarkIds': missing,
        'controlLandmarkIds': control_ids, 'proxyVertexCount': int(sum(len(c['proxy_indices']) for c in component_solves)), 'proxyTriangleCount': int(sum(len(c['proxy_faces']) for c in component_solves)), 'discardedDegenerateProxyTriangles': discarded_degenerate, 'discardedDuplicateProxyTriangles': discarded_duplicate,
        'anchorVertexCount': int(sum(len(c['anchor_orig']) for c in component_solves)), 'solveComponentCount': len(component_solves), 'faceRadiusWorldUnits': face_radius,
        'modifier': {'type': 'LAPLACIANDEFORM', 'iterations': 30, 'blenderVersion': '.'.join(map(str, bpy.app.version))},
        'samples': metrics,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
