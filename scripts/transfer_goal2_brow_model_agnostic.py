"""Model-agnostic single-expression transfer from Avaturn to a Goal-1 target.

The target has no required rig.  Target geometry is discovered from the supplied
GLB and Goal-1 raycast manifest; no target vertex ids or dimensions are encoded.
The only fixed ids are MediaPipe semantic landmark ids, which are detector
standard labels and are resolved through the per-model manifest.
"""
import json, sys
from pathlib import Path
import bpy
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
BROW = [70, 63, 105, 336, 293, 334]
ANCHORS = [159, 145, 386, 374, 33, 133, 263, 362, 168, 6, 1, 98, 327, 234, 454, 152, 10, 127, 356]

def arg(name):
    a = sys.argv[sys.argv.index('--') + 1:]
    if name not in a: raise SystemExit(f'missing {name}')
    return Path(a[a.index(name) + 1]).resolve()

def main():
    source, donor_npz, fit_json = arg('--source'), arg('--donor-npz'), arg('--fit')
    goal1, output, report_path = arg('--goal1'), arg('--output'), arg('--report')
    fit = json.loads(fit_json.read_text())
    points = json.loads((ROOT/'verification/avaturn-face-fit-landmark-points.json').read_text())
    ray = json.loads(goal1.read_text())
    records = {int(r['index']): r for r in ray['records'] if r.get('frontSurface') and r.get('meshXYZ')}
    missing = sorted(set(BROW + ANCHORS) - set(records))
    if missing: raise SystemExit(f'Goal-1 manifest lacks required visible anchors: {missing}')

    donor = np.load(donor_npz)
    base, expr = donor['Head_Mesh__Basis'].astype(float), donor['Head_Mesh__Key__browInnerUp'].astype(float)
    faces = donor['Head_Mesh__Triangles'].astype(int)
    rot = np.asarray(fit['similarity']['rotation'], float)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(source))
    meshes = [o for o in bpy.context.scene.objects if o.type == 'MESH']
    if not meshes: raise SystemExit('GLB has no mesh')
    body = max(meshes, key=lambda o: len(o.data.vertices))
    n = len(body.data.vertices)
    local = np.empty((n, 3), float); body.data.vertices.foreach_get('co', local.ravel())
    mw = np.asarray(body.matrix_world, float); world = local @ mw[:3, :3].T + mw[:3, 3]
    target = {i: np.asarray(records[i]['meshXYZ'], float) for i in records}
    eye_width = float(np.linalg.norm(target[33] - target[263]))
    if eye_width <= 0: raise SystemExit('invalid interocular scale in Goal-1 manifest')
    donor_eye_width = float(np.linalg.norm(np.asarray(points['donorPoints'][33]) - np.asarray(points['donorPoints'][263])))
    if donor_eye_width <= 0: raise SystemExit('invalid donor interocular scale')
    scale = eye_width / donor_eye_width
    donor_delta = {}
    for i in BROW:
        tri = faces[int(points['donorFaceIds'][i])]
        bary = np.asarray(points['donorBarycentric'][i], float)
        donor_delta[i] = scale * ((bary[:, None] * (expr[tri] - base[tri])).sum(0)) @ rot
    # All radii are proportions of this model's own interocular distance.
    # Smooth support is derived from the model's own Goal-1 brow-to-chin extent,
    # not from a character-specific dimension. This keeps the deformation field
    # broad enough for different target proportions and mesh densities.
    brow_center = np.mean([target[i] for i in BROW], axis=0)
    face_extent = float(np.linalg.norm(brow_center - target[152]))
    if face_extent <= 0: raise SystemExit('invalid brow-to-chin extent')
    sigma, radius = face_extent * 0.25, face_extent * 0.50
    handles = np.asarray([target[i] for i in BROW + ANCHORS])
    motions = np.asarray([donor_delta[i] for i in BROW] + [np.zeros(3) for _ in ANCHORS])
    nearest = np.min(np.linalg.norm(world[:, None] - handles[None], axis=2), axis=1)
    candidate = np.flatnonzero(nearest <= radius)
    delta = np.zeros_like(world)
    for start in range(0, len(candidate), 20000):
        ids = candidate[start:start+20000]
        d2 = np.sum((world[ids, None] - handles[None]) ** 2, axis=2)
        k = min(12, len(handles)); idx = np.argpartition(d2, k-1, axis=1)[:, :k]
        w = np.exp(-np.take_along_axis(d2, idx, axis=1) / (2*sigma*sigma)); w /= np.maximum(w.sum(1, keepdims=True), 1e-12)
        delta[ids] = np.einsum('nk,nkd->nd', w, motions[idx])

    # Enforce each Goal-1 barycentric attachment without referring to any
    # character-specific ids. The triangle ids come only from this run's manifest.
    constraints = []
    for i in BROW + ANCHORS:
        r = records[i]; vi = np.asarray(r['triangleVertexIndices'], int); b = np.asarray(r['barycentricCoordinates'], float)
        desired = donor_delta[i] if i in donor_delta else np.zeros(3)
        constraints.append((vi, b, desired))
    for _ in range(8):
        for vi, b, desired in constraints:
            residual = desired - (b[:, None] * delta[vi]).sum(0)
            denom = max(float((b*b).sum()), 1e-12)
            delta[vi] += b[:, None] * residual / denom
    # Prevent geometric inversions without using a character-specific clamp.
    # Project only vertices participating in invalid triangles toward neutral;
    # unaffected brow vertices retain their computed donor motion.
    tris = np.asarray([[v for v in p.vertices] for p in body.data.polygons], int)
    base_tri = world[tris]
    base_norm = np.cross(base_tri[:, 1]-base_tri[:, 0], base_tri[:, 2]-base_tri[:, 0])
    vertex_factor = np.ones(n, float)
    inversion_iterations = 0
    for _ in range(24):
        posed_tri = (world + delta*vertex_factor[:, None])[tris]
        posed_norm = np.cross(posed_tri[:, 1]-posed_tri[:, 0], posed_tri[:, 2]-posed_tri[:, 0])
        invalid = np.einsum('ij,ij->i', base_norm, posed_norm) < 0
        if not bool(invalid.any()): break
        vertex_factor[np.unique(tris[invalid].ravel())] *= 0.5
        inversion_iterations += 1
    delta *= vertex_factor[:, None]
    local_delta = delta @ np.linalg.inv(mw[:3, :3]).T
    body.shape_key_add(name='Basis', from_mix=False)
    key = body.shape_key_add(name='xfer_browInnerUp_model_agnostic', from_mix=False)
    key.data.foreach_set('co', (local + local_delta).astype(np.float32).ravel()); key.value = 0.0
    body.data.shape_keys.use_relative = True; body.data.shape_keys.animation_data_clear()
    bpy.ops.object.select_all(action='DESELECT')
    for obj in bpy.context.scene.objects:
        if obj.type in {'MESH', 'ARMATURE', 'EMPTY'}: obj.select_set(True)
    bpy.context.view_layer.objects.active = body
    output.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.gltf(filepath=str(output), export_format='GLB', export_morph=True, export_skins=True, export_animations=True, export_apply=False)
    result = {'architecture':'model-agnostic Goal-1 attachment-driven anchored RBF; Avaturn motion only; original target vertices retained', 'shapeKey':key.name, 'source':str(source), 'goal1Manifest':str(goal1), 'targetMesh':body.name, 'targetVertexCount':n, 'targetHasArmature':any(o.type=='ARMATURE' for o in bpy.context.scene.objects), 'eyeWidthMillimeters':eye_width*1000, 'donorEyeWidthMillimeters':donor_eye_width*1000, 'motionScaleTargetOverDonorEyeWidth':scale, 'browToChinExtentMillimeters':face_extent*1000, 'localInversionProjectionIterations':inversion_iterations, 'minimumLocalMotionFactor':float(vertex_factor.min()), 'sigmaFractionOfBrowChinExtent':.25, 'radiusFractionOfBrowChinExtent':.50, 'movedVertexCount':int((np.linalg.norm(delta,axis=1)>1e-7).sum()), 'constraintLandmarks':BROW+ANCHORS, 'output':str(output)}
    report_path.parent.mkdir(parents=True, exist_ok=True); report_path.write_text(json.dumps(result, indent=2)+'\n'); print(json.dumps(result, indent=2))

if __name__ == '__main__': main()
