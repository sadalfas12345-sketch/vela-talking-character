import bpy,sys
from mathutils import Vector
from pathlib import Path
argv=sys.argv[sys.argv.index('--')+1:]; src,out=map(Path,argv); out.mkdir(parents=True,exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
if src.suffix.lower() in ('.glb','.gltf'): bpy.ops.import_scene.gltf(filepath=str(src))
elif src.suffix.lower()=='.fbx': bpy.ops.import_scene.fbx(filepath=str(src),use_custom_normals=True)
else: bpy.ops.wm.obj_import(filepath=str(src))
objs=[o for o in bpy.context.scene.objects if o.type=='MESH']; pts=[o.matrix_world@v.co for o in objs for v in o.data.vertices]; lo=Vector((min(p.x for p in pts),min(p.y for p in pts),min(p.z for p in pts))); hi=Vector((max(p.x for p in pts),max(p.y for p in pts),max(p.z for p in pts))); c=(lo+hi)/2; d=(hi-lo).length
for o in objs:
 for m in o.data.materials: m.diffuse_color=(0.62,0.66,0.72,1)
for name,axis in [('xpos',(1,0,0)),('xneg',(-1,0,0)),('ypos',(0,1,0)),('yneg',(0,-1,0)),('zpos',(0,0,1)),('zneg',(0,0,-1))]:
 bpy.ops.object.camera_add(location=c+Vector(axis)*d*2.4); cam=bpy.context.object; cam.data.type='ORTHO'; cam.data.ortho_scale=d*0.72; cam.rotation_euler=(c-cam.location).to_track_quat('-Z','Y').to_euler(); bpy.context.scene.camera=cam
 sc=bpy.context.scene; sc.render.engine='BLENDER_WORKBENCH'; sc.render.resolution_x=600; sc.render.resolution_y=600; sc.render.resolution_percentage=100; sc.display.shading.light='STUDIO'; sc.display.shading.color_type='MATERIAL'; sc.display.shading.show_shadows=True; sc.render.filepath=str(out/(name+'.png')); bpy.ops.render.render(write_still=True); bpy.data.objects.remove(cam,do_unlink=True)
