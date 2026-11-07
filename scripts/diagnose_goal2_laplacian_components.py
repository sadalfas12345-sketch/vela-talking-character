"""Step 1 diagnostic for the native Blender Laplacian failure.

Builds the same local original-surface proxy used by Goal 2, splits it only by
existing mesh connectivity, and tests the native modifier independently on each
component. No source mesh or topology is modified.
"""
import json
import sys
from pathlib import Path
from collections import defaultdict

import bpy
import numpy as np
from mathutils import Vector


CONTROL_IDS = [70, 63, 105, 336, 293, 334, 159, 145, 386, 374, 33, 133, 263, 362, 168, 6, 1, 98, 327, 234, 454, 152, 10, 127, 356]


def arg(name):
    argv = sys.argv[sys.argv.index('--') + 1:]
    if name not in argv:
        raise SystemExit(f'missing {name}')
    return Path(argv[argv.index(name) + 1]).resolve()


def edges_and_stats(faces):
    counts = defaultdict(int)
    for tri in faces:
        for a, b in ((tri[0], tri[1]), (tri[1], tri[2]), (tri[2], tri[0])):
            counts[tuple(sorted((int(a), int(b))))] += 1
    return counts, sum(v == 1 for v in counts.values()), sum(v > 2 for v in counts.values())


def components(vertex_count, faces):
    parent = list(range(vertex_count))
    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra
    for tri in faces:
        union(int(tri[0]), int(tri[1])); union(int(tri[1]), int(tri[2])); union(int(tri[2]), int(tri[0]))
    out = defaultdict(list)
    for i in range(vertex_count):
        out[find(i)].append(i)
    return list(out.values())


def three_anchors(members, original_indices, world):
    chosen = [members[0]]
    if len(members) > 1:
        p = world[np.asarray([original_indices[i] for i in members])]
        chosen.append(members[int(np.argmax(np.linalg.norm(p - p[0], axis=1)))])
    if len(members) > 2:
        p0 = world[original_indices[chosen[0]]]; p1 = world[original_indices[chosen[1]]]
        line = p1 - p0; ln = max(float(np.linalg.norm(line)), 1e-12)
        ds = []
        for i in members:
            v = world[original_indices[i]] - p0
            ds.append(float(np.linalg.norm(v - line * (np.dot(v, line) / (ln * ln)))))
        chosen.append(members[int(np.argmax(ds))])
    return chosen


def test_modifier(local_coords, faces, anchors, move_anchor):
    mesh = bpy.data.meshes.new('__goal2_step1_component_mesh__')
    mesh.from_pydata(local_coords.tolist(), [], [tuple(map(int, f)) for f in faces])
    mesh.update()
    obj = bpy.data.objects.new('__goal2_step1_component__', mesh)
    bpy.context.collection.objects.link(obj)
    group = obj.vertex_groups.new(name='__goal2_step1_anchors__')
    group.add([int(i) for i in anchors], 1.0, 'REPLACE')
    mod = obj.modifiers.new(name='__goal2_step1_laplacian__', type='LAPLACIANDEFORM')
    mod.vertex_group = group.name; mod.iterations = 30
    bpy.ops.object.select_all(action='DESELECT'); obj.select_set(True); bpy.context.view_layer.objects.active = obj
    bind_error = None
    try:
        bpy.ops.object.laplaciandeform_bind(modifier=mod.name)
        bind_result = bool(mod.is_bind)
    except Exception as exc:
        bind_result = False; bind_error = repr(exc)
    eval_result = 'not_run'; free_motion = None; eval_error = None
    if bind_result:
        try:
            obj.data.vertices[int(move_anchor)].co += Vector((0.0001, 0.0, 0.0))
            obj.data.update(); bpy.context.view_layer.update()
            evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
            out_mesh = evaluated.to_mesh()
            out = np.empty((len(out_mesh.vertices), 3), dtype=np.float64); out_mesh.vertices.foreach_get('co', out.ravel())
            evaluated.to_mesh_clear()
            free = [i for i in range(len(local_coords)) if i not in set(anchors)]
            free_motion = float(np.max(np.linalg.norm(out[free] - local_coords[free], axis=1))) if free else None
            eval_result = 'evaluated_with_free_motion' if free_motion is not None and free_motion > 1e-9 else ('evaluated_no_free_motion' if free_motion is not None else 'no_free_vertices')
        except Exception as exc:
            eval_result = 'evaluation_exception'; eval_error = repr(exc)
    bpy.data.objects.remove(obj, do_unlink=True); bpy.data.meshes.remove(mesh)
    return {'bind': bind_result, 'bindError': bind_error, 'evaluation': eval_result, 'freeVertexMaxMotion': free_motion, 'evaluationError': eval_error}


def main():
    source, goal1, out_path = arg('--source'), arg('--goal1'), arg('--output')
    ray = json.loads(goal1.read_text())
    records = {int(r['index']): r for r in ray['records'] if r.get('meshXYZ') is not None}
    bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=str(source))
    body = max([o for o in bpy.context.scene.objects if o.type == 'MESH'], key=lambda o: len(o.data.vertices))
    local = np.empty((len(body.data.vertices), 3), dtype=np.float64); body.data.vertices.foreach_get('co', local.ravel())
    m = np.asarray(body.matrix_world, dtype=float); world = local @ m[:3, :3].T + m[:3, 3]
    target = np.asarray([records[i]['meshXYZ'] for i in range(468)], dtype=float)
    center = np.mean(target[[33, 263, 1, 152]], axis=0); radius = float(np.max(np.linalg.norm(target - center, axis=1)) * 1.20)
    distance = np.linalg.norm(world - center, axis=1)
    raw_faces=[]; seen=set(); degenerate=0; duplicate=0
    for poly in body.data.polygons:
        pv=[int(v) for v in poly.vertices]
        if any(distance[v] <= radius for v in pv):
            for k in range(1,len(pv)-1):
                tri=(pv[0],pv[k],pv[k+1]); area=float(np.linalg.norm(np.cross(world[tri[1]]-world[tri[0]],world[tri[2]]-world[tri[0]])))
                if area <= max(radius*radius*1e-12,1e-18): degenerate += 1; continue
                key=tuple(sorted(tri))
                if key in seen: duplicate += 1; continue
                seen.add(key); raw_faces.append(tri)
    original_indices=sorted({v for f in raw_faces for v in f}); lookup={v:i for i,v in enumerate(original_indices)}
    faces=[tuple(lookup[v] for v in f) for f in raw_faces]
    comps=components(len(original_indices),faces)
    control_orig={v for i in CONTROL_IDS for v in records[i]['triangleVertexIndices']}
    rows=[]
    for number,members in enumerate(comps):
        member_orig={original_indices[i] for i in members}; control=sorted(control_orig & member_orig)
        if not control: continue
        member_set=set(members); comp_faces=[f for f in faces if all(v in member_set for v in f)]
        comp_lookup={old:i for i,old in enumerate(members)}; comp_faces=[tuple(comp_lookup[v] for v in f) for f in comp_faces]
        edge_counts,boundary,nonmanifold=edges_and_stats(comp_faces)
        comp_coords=local[np.asarray([original_indices[i] for i in members])]
        comp_world=world[np.asarray([original_indices[i] for i in members])]
        zero=int(sum(np.linalg.norm(np.cross(comp_world[f[1]]-comp_world[f[0]],comp_world[f[2]]-comp_world[f[0]])) <= max(radius*radius*1e-12,1e-18) for f in comp_faces))
        tri_keys=[tuple(sorted(f)) for f in comp_faces]; dup=len(tri_keys)-len(set(tri_keys))
        used={v for f in comp_faces for v in f}; isolated=len(members)-len(used)
        quant=defaultdict(list)
        for i,p in enumerate(comp_world): quant[tuple(np.round(p/1e-8).astype(np.int64))].append(i)
        coincident_groups=0; coincident_vertices=0
        for ids in quant.values():
            if len(ids)>1:
                coincident_groups += 1; coincident_vertices += len(ids)
        boundary_anchors={i for i in range(len(members)) if distance[original_indices[members[i]]] > radius}
        control_anchors={comp_lookup[lookup[v]] for v in control}
        anchors=sorted(boundary_anchors | control_anchors | set(three_anchors(members,original_indices,world)))
        move=next(iter(control_anchors)) if control_anchors else anchors[0]
        mod=test_modifier(comp_coords,comp_faces,anchors,move)
        rows.append({'component':number,'vertices':len(members),'triangles':len(comp_faces),'connectedComponents':1,'openBoundaryEdges':boundary,'nonmanifoldEdgesGT2':nonmanifold,'zeroAreaTriangles':zero,'duplicateTriangles':dup,'coincidentDisconnectedGroups':coincident_groups,'coincidentDisconnectedVertices':coincident_vertices,'isolatedVertices':isolated,'controlLandmarkVertexCount':len(control),'anchorCount':len(anchors),'boundaryAnchorCount':len(boundary_anchors),'controlAnchorCount':len(control_anchors),'freeVertices':len(members)-len(anchors),'modifier':mod})
    failing=[r for r in rows if r['modifier']['evaluation'] in {'evaluated_no_free_motion','evaluation_exception'} or not r['modifier']['bind']]
    smallest=min(failing,key=lambda r:r['vertices']) if failing else None
    out={'source':str(source),'goal1':str(goal1),'body':body.name,'proxyRadiusWorldUnits':radius,'proxyVertices':len(original_indices),'proxyTriangles':len(faces),'proxyConnectedComponents':len(comps),'proxyDiscardedDegenerateTriangles':degenerate,'proxyDiscardedDuplicateTriangles':duplicate,'processedComponents':len(rows),'components':rows,'smallestReproducibleFailure':smallest,'step1Pass':smallest is not None}
    out_path.parent.mkdir(parents=True,exist_ok=True); out_path.write_text(json.dumps(out,indent=2)+'\n'); print(json.dumps(out,indent=2))

if __name__=='__main__': main()
