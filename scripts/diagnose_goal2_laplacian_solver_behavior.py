"""Diagnostic-only native Blender Laplacian experiments on one Tripo component.

This script does not modify or export the source GLB. It extracts the same
component-30 proxy used by the previous diagnostics, then tests scale and
anchor/evaluation hypotheses with Blender's native LAPLACIANDEFORM modifier.
"""
import json, sys
from pathlib import Path
from collections import defaultdict

import bpy
import numpy as np
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
from diagnose_goal2_laplacian_components import components, edges_and_stats, three_anchors

CONTROL_IDS = [70, 63, 105, 336, 293, 334, 159, 145, 386, 374, 33, 133, 263, 362,
               168, 6, 1, 98, 327, 234, 454, 152, 10, 127, 356]

def arg(name):
    a = sys.argv[sys.argv.index('--') + 1:]
    return Path(a[a.index(name) + 1]).resolve()

def extract_component(source, goal1_path, number=30):
    goal = json.loads(goal1_path.read_text())
    records = {int(r['index']): r for r in goal['records'] if r.get('meshXYZ') is not None}
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(source))
    body = max([o for o in bpy.context.scene.objects if o.type == 'MESH'], key=lambda o: len(o.data.vertices))
    local = np.empty((len(body.data.vertices), 3), dtype=np.float64)
    body.data.vertices.foreach_get('co', local.ravel())
    mw = np.asarray(body.matrix_world, dtype=float)
    world = local @ mw[:3, :3].T + mw[:3, 3]
    target = np.asarray([records[i]['meshXYZ'] for i in range(468)], dtype=float)
    center = np.mean(target[[33, 263, 1, 152]], axis=0)
    radius = float(np.max(np.linalg.norm(target - center, axis=1)) * 1.20)
    distance = np.linalg.norm(world - center, axis=1)
    raw, seen = [], set()
    for poly in body.data.polygons:
        pv = [int(v) for v in poly.vertices]
        if any(distance[v] <= radius for v in pv):
            for k in range(1, len(pv) - 1):
                tri = (pv[0], pv[k], pv[k + 1])
                key = tuple(sorted(tri))
                area2 = np.linalg.norm(np.cross(world[tri[1]]-world[tri[0]], world[tri[2]]-world[tri[0]]))
                if key not in seen and area2 > max(radius*radius*1e-12, 1e-18):
                    seen.add(key); raw.append(tri)
    original = sorted({v for f in raw for v in f})
    lookup = {v:i for i,v in enumerate(original)}
    faces = [tuple(lookup[v] for v in f) for f in raw]
    comps = components(len(original), faces)
    if number >= len(comps): raise RuntimeError(f'component {number} absent; count={len(comps)}')
    members = sorted(comps[number]); member_set = set(members)
    clook = {old:i for i,old in enumerate(members)}
    comp_faces = [tuple(clook[v] for v in f) for f in faces if all(v in member_set for v in f)]
    comp_original = [original[i] for i in members]
    coords = local[np.asarray(comp_original)]
    world_coords = world[np.asarray(comp_original)]
    control_orig = {v for i in CONTROL_IDS for v in records[i]['triangleVertexIndices']}
    control_local = {clook[lookup[v]] for v in control_orig if v in lookup and lookup[v] in member_set}
    edge_counts, boundary, nonmanifold = edges_and_stats(comp_faces)
    boundary_vertices = {v for e,c in edge_counts.items() if c == 1 for v in e}
    # three_anchors returns labels from the supplied member list. Convert to
    # component-local labels here; the modifier only sees local mesh indices.
    local_members = list(range(len(comp_original)))
    anchors = sorted(control_local | set(three_anchors(local_members, local_members, world_coords)))
    return {
        'coords': coords, 'world': world_coords, 'faces': comp_faces,
        'control': sorted(control_local), 'anchors': anchors,
        'boundary_vertices': sorted(boundary_vertices), 'records': records,
        'component': number, 'source': str(source), 'goal1': str(goal1_path),
        'body': body.name, 'radius': radius, 'center': center,
    }

def read_eval(obj, neutral, anchors):
    ev = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = ev.to_mesh()
    out = np.empty((len(mesh.vertices), 3), dtype=np.float64)
    mesh.vertices.foreach_get('co', out.ravel())
    ev.to_mesh_clear()
    delta = out - neutral
    free = np.ones(len(neutral), dtype=bool); free[list(set(anchors))] = False
    return out, delta, delta[free]

def native_test(coords, faces, anchors, move_anchor, requested, label, use_object_data=True):
    mesh = bpy.data.meshes.new('__goal2_diag_mesh__')
    mesh.from_pydata(coords.tolist(), [], [tuple(map(int,f)) for f in faces]); mesh.update()
    obj = bpy.data.objects.new('__goal2_diag_obj__', mesh); bpy.context.collection.objects.link(obj)
    group = obj.vertex_groups.new(name='__goal2_diag_anchors__'); group.add([int(x) for x in anchors], 1.0, 'REPLACE')
    mod = obj.modifiers.new(name='__goal2_diag_laplacian__', type='LAPLACIANDEFORM')
    mod.vertex_group = group.name; mod.iterations = 30
    bpy.ops.object.select_all(action='DESELECT'); obj.select_set(True); bpy.context.view_layer.objects.active=obj
    bind_error = None; eval_error = None; bind = False
    try:
        bpy.ops.object.laplaciandeform_bind(modifier=mod.name); bind = bool(mod.is_bind)
    except Exception as e: bind_error = repr(e)
    before = coords.copy(); after = None; free_delta = None
    requested_norm = float(np.linalg.norm(requested))
    if bind:
        try:
            # Deliberately move the input vertex after binding, matching the
            # already validated synthetic-grid workflow.
            obj.data.vertices[int(move_anchor)].co += Vector(tuple(map(float, requested)))
            obj.data.update(); bpy.context.view_layer.update()
            after, delta, free = read_eval(obj, before, anchors)
            free_delta = free
        except Exception as e: eval_error = repr(e)
    anchor_motion = float(np.linalg.norm(after[int(move_anchor)]-before[int(move_anchor)])) if after is not None else None
    return_data = {
        'label': label, 'vertexCount': len(coords), 'triangleCount': len(faces),
        'anchorCount': len(anchors), 'moveAnchor': int(move_anchor),
        'requestedAnchorMotion': requested_norm, 'bind': bind, 'bindError': bind_error,
        'evaluationError': eval_error, 'evaluatedAnchorMotion': anchor_motion,
        'evaluatedFreeMaxMotion': float(np.max(np.linalg.norm(free_delta,axis=1))) if free_delta is not None and len(free_delta) else None,
        'evaluatedFreeRmsMotion': float(np.sqrt(np.mean(np.sum(free_delta*free_delta,axis=1)))) if free_delta is not None and len(free_delta) else None,
        'solverStatus': 'free_motion' if free_delta is not None and len(free_delta) and np.max(np.linalg.norm(free_delta,axis=1)) > 1e-9 else ('no_free_motion' if free_delta is not None else 'not_evaluated'),
    }
    bpy.data.objects.remove(obj, do_unlink=True); bpy.data.meshes.remove(mesh)
    return return_data

def main():
    source, goal1, out_path = arg('--source'), arg('--goal1'), arg('--output')
    argv = sys.argv[sys.argv.index('--') + 1:]
    component_number = int(argv[argv.index('--component') + 1]) if '--component' in argv else 30
    d = extract_component(source, goal1, component_number)
    c = d['coords']; f = d['faces']; diag = float(np.linalg.norm(np.max(c,axis=0)-np.min(c,axis=0)))
    edges = sorted({tuple(sorted((int(a),int(b)))) for tri in f for a,b in ((tri[0],tri[1]),(tri[1],tri[2]),(tri[2],tri[0]))})
    lengths = np.asarray([np.linalg.norm(c[a]-c[b]) for a,b in edges])
    anchor_sep = np.asarray([np.linalg.norm(c[a]-c[b]) for i,a in enumerate(d['anchors']) for b in d['anchors'][i+1:]], dtype=float)
    control = d['control']; move = control[0] if control else d['anchors'][0]
    direction = np.array([1.0,0.0,0.0]); requested = direction * (0.01*diag)
    baseline = native_test(c, f, d['anchors'], move, requested, f'baseline_component{component_number}')

    scales = []
    for s in [0.01,0.1,1.0,10.0,100.0]:
        cs = c*s; req = direction*(0.01*diag*s)
        r = native_test(cs, f, d['anchors'], move, req, f'scale_{s:g}')
        r['scale']=s; r['componentDiagonal']=diag*s
        for k in ('requestedAnchorMotion','evaluatedAnchorMotion','evaluatedFreeMaxMotion','evaluatedFreeRmsMotion'):
            if r[k] is not None: r[k+'NormalizedByDiagonal'] = r[k]/(diag*s)
        scales.append(r)

    # Anchor configurations are deliberately defined from geometry, not IDs.
    wide = list(dict.fromkeys(d['anchors']))
    three = list(three_anchors(list(range(len(c))), list(range(len(c))), c))
    configs = {
        'A_three_widely_separated': sorted(set(three)),
        'B_six_original': sorted(set(d['anchors'][:6])),
        'C_three_control_plus_stationary': sorted(set((control[:3] if len(control)>=3 else control) + three)),
        'D_original': sorted(set(d['anchors'])),
    }
    anchor_results=[]
    for name, anchors in configs.items():
        if len(anchors) < 3 or move in anchors is False: continue
        r=native_test(c,f,anchors,move,requested,name); r['componentDiagonal']=diag
        for k in ('requestedAnchorMotion','evaluatedAnchorMotion','evaluatedFreeMaxMotion','evaluatedFreeRmsMotion'):
            if r[k] is not None: r[k+'NormalizedByDiagonal']=r[k]/diag
        anchor_results.append(r)

    # Evaluation workflow alternatives on original component and best scale.
    best_scale = next((x for x in scales if x['solverStatus']=='free_motion'), scales[2])
    eval_results=[baseline]
    eval_results.append(native_test(c*best_scale.get('scale',1.0),f,d['anchors'],move,requested*best_scale.get('scale',1.0),'best_scale_original_anchors'))
    eval_results.append(native_test(c,f,configs['A_three_widely_separated'],move,requested,'original_geometry_best_anchor_arrangement'))
    eval_results.append(native_test(c*best_scale.get('scale',1.0),f,configs['A_three_widely_separated'],move,requested*best_scale.get('scale',1.0),'best_scale_best_anchor_arrangement'))

    out={'source':d['source'],'goal1':d['goal1'],'component':d['component'],'body':d['body'],
         'vertexCount':len(c),'triangleCount':len(f),'componentDiagonal':diag,
         'bboxMin':np.min(c,axis=0).tolist(),'bboxMax':np.max(c,axis=0).tolist(),
         'edgeLengthAverage':float(np.mean(lengths)),'edgeLengthMinimum':float(np.min(lengths)),
         'edgeLengthP05':float(np.percentile(lengths,5)),'anchorCount':len(d['anchors']),
         'anchorIDs':d['anchors'],'anchorPairwiseSeparationMin':float(np.min(anchor_sep)) if len(anchor_sep) else None,
         'anchorPairwiseSeparationMax':float(np.max(anchor_sep)) if len(anchor_sep) else None,
         'requestedMotion':float(np.linalg.norm(requested)),'baseline':baseline,'scaleTests':scales,
         'anchorConfigurations':anchor_results,'evaluationWorkflow':eval_results,
         'step1Pass':baseline['bind'] and baseline['solverStatus']=='no_free_motion',
         'step2DiagnosticComplete':len(scales)==5,'step3DiagnosticComplete':len(anchor_results)==4,
         'step4DiagnosticComplete':len(eval_results)==4}
    out_path.parent.mkdir(parents=True,exist_ok=True); out_path.write_text(json.dumps(out,indent=2)+'\n'); print(json.dumps(out,indent=2))

if __name__=='__main__': main()
