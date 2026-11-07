"""Step 2: one-cause-at-a-time tests on the Step-1 minimal failing component."""
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import bpy
import numpy as np

from diagnose_goal2_laplacian_components import test_modifier, edges_and_stats, components, three_anchors

CONTROL_IDS = [70, 63, 105, 336, 293, 334, 159, 145, 386, 374, 33, 133, 263, 362, 168, 6, 1, 98, 327, 234, 454, 152, 10, 127, 356]


def arg(name):
    a = sys.argv[sys.argv.index('--') + 1:]
    return Path(a[a.index(name) + 1]).resolve()


def orient_faces(faces):
    """Orient each connected face set consistently across shared edges."""
    faces = [list(map(int, f)) for f in faces]
    edge_map = defaultdict(list)
    for fi, f in enumerate(faces):
        for a, b in ((f[0], f[1]), (f[1], f[2]), (f[2], f[0])):
            edge_map[tuple(sorted((a, b)))].append((fi, a, b))
    adjacency = defaultdict(list)
    for entries in edge_map.values():
        for i in range(len(entries)):
            for j in range(i + 1, len(entries)):
                adjacency[entries[i][0]].append(entries[j]); adjacency[entries[j][0]].append(entries[i])
    seen = set()
    for start in range(len(faces)):
        if start in seen:
            continue
        seen.add(start); queue = [start]
        while queue:
            current = queue.pop()
            current_edges = {(min(a,b), max(a,b)): (a,b) for a,b in ((faces[current][0],faces[current][1]),(faces[current][1],faces[current][2]),(faces[current][2],faces[current][0]))}
            for neighbor, na, nb in adjacency[current]:
                if neighbor in seen:
                    continue
                key = (min(na, nb), max(na, nb)); ca, cb = current_edges.get(key, (None, None))
                if ca == na and cb == nb:
                    faces[neighbor][1], faces[neighbor][2] = faces[neighbor][2], faces[neighbor][1]
                seen.add(neighbor); queue.append(neighbor)
    return [tuple(f) for f in faces]


def test_variant(name, coords, faces, anchors, move_anchor):
    stats = {}
    edge_counts, boundary, nonmanifold = edges_and_stats(faces)
    stats.update({'vertices': len(coords), 'triangles': len(faces), 'openBoundaryEdges': boundary, 'nonmanifoldEdgesGT2': nonmanifold, 'zeroAreaTriangles': int(sum(np.linalg.norm(np.cross(coords[f[1]]-coords[f[0]],coords[f[2]]-coords[f[0]])) <= 1e-18 for f in faces)), 'duplicateTriangles': len(faces)-len(set(tuple(sorted(f)) for f in faces)), 'anchorCount': len(anchors), 'freeVertices': len(coords)-len(set(anchors))})
    stats['modifier'] = test_modifier(coords, faces, anchors, move_anchor)
    return {'variant': name, **stats}


def main():
    source, goal1_path, out_path = arg('--source'), arg('--goal1'), arg('--output')
    goal1 = json.loads(goal1_path.read_text()); records = {int(r['index']): r for r in goal1['records'] if r.get('meshXYZ') is not None}
    bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=str(source))
    body = max([o for o in bpy.context.scene.objects if o.type == 'MESH'], key=lambda o: len(o.data.vertices))
    local = np.empty((len(body.data.vertices), 3), dtype=float); body.data.vertices.foreach_get('co', local.ravel())
    m=np.asarray(body.matrix_world,dtype=float); world=local@m[:3,:3].T+m[:3,3]
    target=np.asarray([records[i]['meshXYZ'] for i in range(468)]); center=np.mean(target[[33,263,1,152]],axis=0); radius=float(np.max(np.linalg.norm(target-center,axis=1))*1.20); distance=np.linalg.norm(world-center,axis=1)
    raw=[]; seen=set()
    for poly in body.data.polygons:
        pv=[int(v) for v in poly.vertices]
        if any(distance[v]<=radius for v in pv):
            for k in range(1,len(pv)-1):
                tri=(pv[0],pv[k],pv[k+1]); key=tuple(sorted(tri))
                if key not in seen and np.linalg.norm(np.cross(world[tri[1]]-world[tri[0]],world[tri[2]]-world[tri[0]]))>max(radius*radius*1e-12,1e-18):
                    seen.add(key); raw.append(tri)
    original=sorted({v for f in raw for v in f}); lookup={v:i for i,v in enumerate(original)}; faces=[tuple(lookup[v] for v in f) for f in raw]
    comps=components(len(original),faces); component_number=30
    if component_number>=len(comps): raise RuntimeError('component 30 is absent')
    members=sorted(comps[component_number]); member_set=set(members); comp_lookup={old:i for i,old in enumerate(members)}; comp_faces=[tuple(comp_lookup[v] for v in f) for f in faces if all(v in member_set for v in f)]
    comp_original=[original[i] for i in members]; comp_coords=local[np.asarray(comp_original)]; comp_world=world[np.asarray(comp_original)]
    control_orig={v for i in CONTROL_IDS for v in records[i]['triangleVertexIndices']}; control_local={comp_lookup[lookup[v]] for v in control_orig if v in lookup and lookup[v] in member_set}
    edge_counts,boundary_edges,nonmanifold=edges_and_stats(comp_faces); boundary_vertices={v for e,c in edge_counts.items() if c==1 for v in e}; three=set(three_anchors(members,original,world)); baseline=sorted(control_local|three); move=next(iter(control_local))
    variants=[]
    variants.append(test_variant('baseline_raw_component',comp_coords,comp_faces,baseline,move))
    variants.append(test_variant('remove_isolated_vertices_noop',comp_coords,comp_faces,baseline,move))
    variants.append(test_variant('remove_degenerate_duplicate_triangles_noop',comp_coords,comp_faces,baseline,move))
    variants.append(test_variant('separate_unrelated_components_noop',comp_coords,comp_faces,baseline,move))
    variants.append(test_variant('weld_coincident_vertices_noop',comp_coords,comp_faces,baseline,move))
    variants.append(test_variant('consistent_triangle_orientation',comp_coords,orient_faces(comp_faces),baseline,move))
    boundary_anchors=sorted(set(baseline)|boundary_vertices)
    variants.append(test_variant('add_all_open_boundary_vertices_as_anchors',comp_coords,comp_faces,boundary_anchors,move))
    out={'source':str(source),'goal1':str(goal1_path),'componentNumber':component_number,'componentVertices':len(comp_coords),'componentTriangles':len(comp_faces),'componentOpenBoundaryEdges':boundary_edges,'componentNonmanifoldEdgesGT2':nonmanifold,'componentControlAnchorCount':len(control_local),'variants':variants,'step2Pass':any(v['modifier']['evaluation']=='evaluated_with_free_motion' for v in variants)}
    out_path.parent.mkdir(parents=True,exist_ok=True); out_path.write_text(json.dumps(out,indent=2)+'\n'); print(json.dumps(out,indent=2))

if __name__=='__main__': main()
