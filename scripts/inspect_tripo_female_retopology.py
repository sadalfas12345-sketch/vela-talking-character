import bpy, json, sys
from pathlib import Path
from mathutils import Vector

argv=sys.argv[sys.argv.index('--')+1:]
original, retopo, out, camera_json = map(Path, argv)
out.mkdir(parents=True, exist_ok=True)
caminfo=json.loads(camera_json.read_text())
target=Vector(caminfo['target']); front_loc=Vector(caminfo['cameraLocation']); ortho=float(caminfo['orthoScale'])

def load(path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    if path.suffix.lower() in ('.glb', '.gltf'): bpy.ops.import_scene.gltf(filepath=str(path))
    elif path.suffix.lower()=='.fbx': bpy.ops.import_scene.fbx(filepath=str(path), use_custom_normals=True)
    else: bpy.ops.wm.obj_import(filepath=str(path))
    meshes=[o for o in bpy.context.scene.objects if o.type=='MESH']
    if not meshes: raise RuntimeError('no mesh')
    return meshes

def camera(name, loc, look, scale):
    data=bpy.data.cameras.new(name); obj=bpy.data.objects.new(name,data); bpy.context.collection.objects.link(obj)
    obj.location=loc; obj.rotation_euler=(look-loc).to_track_quat('-Z','Y').to_euler(); data.type='ORTHO'; data.ortho_scale=scale; bpy.context.scene.camera=obj; return obj

def bounds(meshes):
    pts=[o.matrix_world@v.co for o in meshes for v in o.data.vertices]
    lo=Vector((min(p.x for p in pts),min(p.y for p in pts),min(p.z for p in pts))); hi=Vector((max(p.x for p in pts),max(p.y for p in pts),max(p.z for p in pts))); return lo,hi

def save_stats(path, meshes):
    polys=sum(len(o.data.polygons) for o in meshes); verts=sum(len(o.data.vertices) for o in meshes); mats=sum(len(o.data.materials) for o in meshes); uv=sum(len(o.data.uv_layers) for o in meshes)
    deg=0
    for o in meshes:
        for p in o.data.polygons:
            if p.area <= 1e-12: deg += 1
    (out/(path.stem+'-stats.json')).write_text(json.dumps({'vertices':verts,'polygons':polys,'materials':mats,'uv_layers':uv,'degenerate_polygons':deg,'mesh_objects':len(meshes)},indent=2)+'\n')

def render(path, label, use_goal_cam=False):
    meshes=load(path); save_stats(path,meshes)
    lo,hi=bounds(meshes); c=(lo+hi)/2; diag=(hi-lo).length
    for o in meshes:
        for m in o.data.materials:
            m.diffuse_color=(0.62,0.66,0.72,1)
    sc=bpy.context.scene; sc.render.resolution_x=700; sc.render.resolution_y=700; sc.render.resolution_percentage=100
    sc.render.engine='BLENDER_WORKBENCH'; sc.display.shading.light='STUDIO'; sc.display.shading.color_type='MATERIAL'; sc.display.shading.show_shadows=True
    front_target = target if use_goal_cam else c
    front_camera_loc = front_loc if use_goal_cam else c+Vector((0,-2.4*diag,0))
    if not use_goal_cam:
        front_camera_loc = c+Vector((0,-2.4*diag,0))
    else:
        front_camera_loc = c + (front_loc-target)
    camera('front',front_camera_loc,front_target,ortho); sc.render.filepath=str(out/(label+'-front-clay.png')); bpy.ops.render.render(write_still=True)
    for o in meshes: o.show_wire=True; o.show_all_edges=True
    sc.display.shading.color_type='SINGLE'; sc.display.shading.single_color=(0.55,0.60,0.68); sc.render.filepath=str(out/(label+'-front-wireframe.png')); bpy.ops.render.render(write_still=True)
    for o in meshes: o.show_wire=False
    side_loc=front_target+Vector((ortho*5,0,0)); camera('profile',side_loc,front_target,ortho); sc.display.shading.color_type='MATERIAL'; sc.render.filepath=str(out/(label+'-profile-clay.png')); bpy.ops.render.render(write_still=True)
    for o in meshes: o.show_wire=True; o.show_all_edges=True
    sc.display.shading.color_type='SINGLE'; sc.render.filepath=str(out/(label+'-profile-wireframe.png')); bpy.ops.render.render(write_still=True)

render(original,'original',True); render(retopo,'retopologized',False)
