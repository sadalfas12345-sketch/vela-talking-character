import json, math, os, sys
from pathlib import Path
import bpy, bmesh, numpy as np
from mathutils import Matrix, Vector

CAPTUREFORGE = r"C:\Users\USER\captureforge"
HELPER = r"C:\Users\USER\captureforge\.venv\Scripts\python.exe"
MODEL = r"C:\Users\USER\captureforge\models\face_landmarker.task"
sys.path.insert(0, CAPTUREFORGE)
from captureforge.face import autofit, video

ROOT = Path(r"C:\Users\USER\talking-character-demo")
CASES = {
    "female": {
        "glb": ROOT / "assets/tripo/vela-photoreal/generated-original.glb",
        "goal1": ROOT / "verification/goal1-generalization-run/cross-character-accuracy/female/refined/raycast-report.json",
        "camera": ROOT / "verification/goal1-generalization-run/cross-character-accuracy/female/refined-camera.json",
    },
    "male": {
        "glb": ROOT / "assets/tripo/generalization-male-20261105/generated-original.glb",
        "goal1": ROOT / "verification/goal1-generalization-run/cross-character-accuracy/male/refined/raycast-report.json",
        "camera": ROOT / "verification/goal1-generalization-run/cross-character-accuracy/male/refined-camera.json",
    },
}
OUT = ROOT / "verification/captureforge-facial-rig-test"
_CURRENT_CAMERA_SCALE = 1.0

def load_points(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    recs = [r for r in data["records"] if r.get("meshXYZ") and r.get("triangleVertexIndices")]
    ids = {int(r["index"]): r for r in recs}
    return data, ids

def world_vertices(obj):
    M = np.array(obj.matrix_world, dtype=float)
    co = np.empty(len(obj.data.vertices) * 3, dtype=np.float64)
    obj.data.vertices.foreach_get("co", co)
    return co.reshape(-1, 3) @ M[:3, :3].T + M[:3, 3]

def canonical_frame(ids, camera_location):
    p33 = np.array(ids[33]["meshXYZ"], dtype=float)
    p263 = np.array(ids[263]["meshXYZ"], dtype=float)
    p1 = np.array(ids[1]["meshXYZ"], dtype=float)
    p152 = np.array(ids[152]["meshXYZ"], dtype=float)
    center = (p33 + p263) * 0.5
    right = p263 - p33
    right /= np.linalg.norm(right)
    up = p10 = np.array(ids[10]["meshXYZ"], dtype=float) - p152
    up = up - right * np.dot(up, right)
    up /= np.linalg.norm(up)
    outward = np.cross(right, up)
    outward /= np.linalg.norm(outward)
    cam_dir = np.asarray(camera_location, dtype=float) - center
    if np.dot(outward, cam_dir) < 0.0:
        outward = -outward
    # CaptureForge canonical face orientation: front is -Y, up is +Z, image right is +X.
    R = np.stack([right, -outward, up], axis=0)
    return center, R

def xform(points, center, R):
    return (np.asarray(points) - center) @ R.T

def make_head_copy(body, canonical_world, center, R, ids, name):
    head = body.copy()
    head.data = body.data.copy()
    head.name = name
    body.users_collection[0].objects.link(head)
    for i, v in enumerate(head.data.vertices):
        v.co = Vector(canonical_world[i])
    # Keep only a dynamically derived face slab around all Goal 1 points.
    pts_by_id = {i: xform(r["meshXYZ"], center, R) for i, r in ids.items()}
    pts = np.array(list(pts_by_id.values()))
    ew = float(np.linalg.norm(pts_by_id[33] - pts_by_id[263])) if 33 in pts_by_id and 263 in pts_by_id else 1.0
    lo = pts.min(axis=0) - np.array([0.45 * ew, 0.65 * ew, 0.45 * ew])
    hi = pts.max(axis=0) + np.array([0.45 * ew, 0.65 * ew, 0.45 * ew])
    # Keep only connected mesh components touched by CaptureForge's own
    # anatomical landmark set. This excludes unrelated body, hair, clothing,
    # and accessory islands without using character-specific vertex IDs.
    n = len(body.data.vertices)
    parent = list(range(n))
    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]; a = parent[a]
        return a
    def union(a,b):
        ra, rb = find(a), find(b)
        if ra != rb: parent[rb] = ra
    for poly in body.data.polygons:
        vs = list(poly.vertices)
        if len(vs) >= 3:
            union(vs[0], vs[1]); union(vs[1], vs[2]); union(vs[2], vs[0])
    roots = set()
    for idx in autofit.LANDMARKS.values():
        if idx in ids:
            roots.update(find(int(v)) for v in ids[idx]['triangleVertexIndices'])
    keep_components = {i for i in range(n) if find(i) in roots}
    bm = bmesh.new(); bm.from_mesh(head.data); bm.verts.ensure_lookup_table(); bm.verts.index_update()
    for v in list(bm.verts):
        if v.index not in keep_components or not (lo[0] <= v.co.x <= hi[0] and lo[1] <= v.co.y <= hi[1] and lo[2] <= v.co.z <= hi[2]):
            bm.verts.remove(v)
    bm.to_mesh(head.data); bm.free(); head.data.update()
    head.parent = None
    head.location = (0.0, 0.0, 0.0)
    head.rotation_euler = (0.0, 0.0, 0.0)
    head.scale = (1.0, 1.0, 1.0)
    return head, ew, lo, hi

def setup_camera(scene, loc, target, path):
    data = bpy.data.cameras.new("CaptureForgeTestCamera")
    cam = bpy.data.objects.new("CaptureForgeTestCamera", data)
    scene.collection.objects.link(cam)
    cam.location = Vector(loc)
    direction = Vector(target) - cam.location
    cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    data.type = "ORTHO"
    data.ortho_scale = float(_CURRENT_CAMERA_SCALE)
    scene.camera = cam
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.render.resolution_x = 768; scene.render.resolution_y = 768; scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = str(path)
    scene.display.shading.light = "STUDIO"
    scene.display.shading.color_type = "TEXTURE"

def set_brow_pose(rig, amount):
    names = [b.name for b in rig.pose.bones if b.name.startswith("brow.")]
    for n in names:
        pb = rig.pose.bones[n]
        pb.rotation_mode = "XYZ"
        pb.rotation_euler[0] = amount
    return names

def evaluated_world(obj):
    deps = bpy.context.evaluated_depsgraph_get()
    eo = obj.evaluated_get(deps)
    M = np.array(eo.matrix_world, dtype=float)
    co = np.empty(len(eo.data.vertices) * 3, dtype=np.float64)
    eo.data.vertices.foreach_get("co", co)
    return co.reshape(-1, 3) @ M[:3, :3].T + M[:3, 3]

def landmark_position(vertices, rec):
    tri = rec["triangleVertexIndices"]; w = np.array(rec["barycentricCoordinates"], dtype=float)
    return w[0]*vertices[tri[0]] + w[1]*vertices[tri[1]] + w[2]*vertices[tri[2]]

def run_case(label, cfg):
    global _CURRENT_CAMERA_SCALE
    out = OUT / label; out.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(cfg["glb"]))
    scene = bpy.context.scene
    body = max((o for o in scene.objects if o.type == "MESH"), key=lambda o: len(o.data.vertices))
    body.name = f"{label}_original_body"
    data, ids = load_points(cfg["goal1"])
    center, R = canonical_frame(ids, data["camera"]["cameraLocation"])
    preview = out / "captureforge-fit-preview.png"
    invC = np.eye(4); invC[:3,:3] = R.T; invC[:3,3] = center
    can = xform(world_vertices(body), center, R)
    head, ew, lo, hi = make_head_copy(body, can, center, R, ids, f"{label}_captureforge_fit_surface")
    bb = np.array([head.matrix_world @ Vector(c) for c in head.bound_box], dtype=float)
    print('HEAD_BBOX', label, bb.min(axis=0).tolist(), bb.max(axis=0).tolist(), 'verts', len(head.data.vertices), 'polys', len(head.data.polygons))
    if len(head.data.vertices) == 0:
        result = {
            'character': label, 'status': 'FAILED', 'failure_stage': 'dynamic face-surface isolation',
            'failure': 'No original-GLB vertices intersect the Goal 1 attachment-derived face slab and landmark components.',
            'goal1_source_glb': data.get('sourceGLB'), 'tested_source_glb': str(cfg['glb']),
            'diagnosis': f'Goal 1 source is {data.get("sourceGLB")}; tested source is {cfg["glb"]}. The attachment-derived surface does not intersect this input mesh.',
            'captureforge_render_detection': False, 'fit_preview': str(preview),
        }
        (out/'result.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
        print(json.dumps(result, indent=2))
        return
    camfit = autofit.front_camera([head], margin=1.25)
    print('FIT_BBOX', label, 'ew', ew, 'lo', lo.tolist(), 'hi', hi.tolist(), 'cam', camfit)
    autofit.render_front(scene, [head], str(preview), camfit, size=768, color_type="MATERIAL")
    detection_ok = True
    try:
        lm = video.landmarks(HELPER, MODEL, str(preview))["landmarks"]
        deps = bpy.context.evaluated_depsgraph_get()
        P = autofit.map_landmarks(lm, camfit, head, deps)
    except Exception as exc:
        # CaptureForge's documented auto-rig path is render -> MediaPipe ->
        # surface mapping. The original mesh render is a valid diagnostic
        # failure when MediaPipe cannot see it. For the requested rig test,
        # use the already verified Goal 1 surface attachments as the explicit
        # correspondence input to CaptureForge's own rig builder.
        detection_ok = False
        P = {name: Vector(xform(np.array(ids[idx]["meshXYZ"]), center, R))
             for name, idx in autofit.LANDMARKS.items() if idx in ids}
        print('CAPTUREFORGE_RENDER_DETECTION_FAILED', label, repr(str(exc)))
    rig = autofit.build_faceforge_rig(P, head, (), name=f"{label}_CaptureForgeFaceRig")
    rig.matrix_world = Matrix(invC.tolist())
    g = autofit.face_geometry(P, head, ())
    specs = autofit.bone_specs(P, g)
    can_body = can
    weights = autofit.skin_weights(can_body, specs, g)
    # Face mask is derived from the same Goal 1 landmark bounds, not character constants.
    fpts_by_id = {i: xform(r["meshXYZ"], center, R) for i, r in ids.items()}
    fpts = np.array(list(fpts_by_id.values()))
    ew = np.linalg.norm(fpts_by_id[33]-fpts_by_id[263])
    face_mask = ((can_body[:,0] >= fpts[:,0].min()-0.6*ew) & (can_body[:,0] <= fpts[:,0].max()+0.6*ew) &
                 (can_body[:,2] >= fpts[:,2].min()-0.6*ew) & (can_body[:,2] <= fpts[:,2].max()+0.6*ew) &
                 (can_body[:,1] >= fpts[:,1].min()-0.8*ew) & (can_body[:,1] <= fpts[:,1].max()+0.8*ew)).astype(float)
    for name in list(weights): weights[name] *= face_mask
    autofit._bind(body, rig, weights)
    head.hide_render = True; head.hide_viewport = True
    neutral = evaluated_world(body)
    # Direction test: choose the sign that raises the mapped eyebrow landmarks in canonical +Z.
    candidates = []
    for sign in (-0.25, 0.25):
        set_brow_pose(rig, sign)
        v = evaluated_world(body)
        dz = np.mean([landmark_position(xform(v, center, R), ids[i])[2] - landmark_position(xform(neutral, center, R), ids[i])[2] for i in [70,105,334,336]])
        candidates.append((dz, sign))
    set_brow_pose(rig, max(candidates)[1])
    raised = evaluated_world(body)
    # Render neutral and raised actual original mesh.
    rig.hide_render = True
    set_brow_pose(rig, 0.0)
    _CURRENT_CAMERA_SCALE = float(data["camera"]["orthoScale"])
    setup_camera(scene, data["camera"]["cameraLocation"], data["camera"]["target"], out/"neutral.png")
    bpy.context.scene.frame_set(1); bpy.ops.render.render(write_still=True)
    set_brow_pose(rig, max(candidates)[1])
    setup_camera(scene, data["camera"]["cameraLocation"], data["camera"]["target"], out/"raised.png")
    bpy.ops.render.render(write_still=True)
    # Compare actual barycentric landmarks and triangle quality.
    ncan = xform(neutral, center, R); rcan = xform(raised, center, R)
    rows=[]
    for i in [70,105,334,336,293,63]:
        a=landmark_position(ncan, ids[i]); b=landmark_position(rcan, ids[i])
        rows.append({'id':i,'neutral':a.tolist(),'raised':b.tolist(),'delta':(b-a).tolist(),'delta_mm_or_units':float(np.linalg.norm(b-a))})
    tri = np.empty(len(body.data.polygons)*3, dtype=np.int32); body.data.polygons.foreach_get('vertices',tri)
    tri=tri.reshape(-1,3); N=neutral; V=raised
    a=N[tri[:,1]]-N[tri[:,0]]; b=N[tri[:,2]]-N[tri[:,0]]; c=V[tri[:,1]]-V[tri[:,0]]; d=V[tri[:,2]]-V[tri[:,0]]
    area0=np.linalg.norm(np.cross(a,b),axis=1); area1=np.linalg.norm(np.cross(c,d),axis=1)
    min_ratio=float(np.min(area1/(area0+1e-12))); collapsed=int(np.sum(area1 <= 0.1*area0)); invalid=int(np.sum(~np.isfinite(V)))
    result={'character':label,'source_glb':str(cfg['glb']),'vertex_count':len(body.data.vertices),'rig_bones':len(rig.data.bones),
            'face_weighted_vertices':int(face_mask.sum()),'goal1_landmarks':len(ids),'canonical_interocular':float(ew),
            'fit_preview':str(preview),'neutral_render':str(out/'neutral.png'),'raised_render':str(out/'raised.png'),
            'captureforge_render_detection': detection_ok,
            'pose_angle_radians':float(max(candidates)[1]),'direction_candidates':candidates,'landmarks':rows,
            'min_area_ratio':min_ratio,'collapsed_triangles':collapsed,'invalid_coordinates':invalid,
            'captureforge_version':'local checkout; FaceForge auto-rig fit', 'expression_driver':'browInnerUp test pose on fitted brow bones'}
    (out/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    bpy.ops.wm.save_as_mainfile(filepath=str(out/f'{label}-captureforge-rig.blend'))
    print(json.dumps(result,indent=2))

for label,cfg in CASES.items(): run_case(label,cfg)
