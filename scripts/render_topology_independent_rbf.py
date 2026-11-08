import bpy, json, sys
from pathlib import Path
from mathutils import Vector

args=sys.argv[sys.argv.index('--')+1:]
source, deformed, camera_json, out=map(Path,args); out.mkdir(parents=True,exist_ok=True)
cam=json.loads(camera_json.read_text()); target=Vector(cam['target']); loc=Vector(cam['cameraLocation']); scale=float(cam['orthoScale'])

def setup(path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(path))
    return [o for o in bpy.context.scene.objects if o.type=='MESH']

def camera():
    d=bpy.data.cameras.new('RBF camera'); c=bpy.data.objects.new('RBF camera',d); bpy.context.scene.collection.objects.link(c)
    c.location=loc; c.rotation_euler=(target-loc).to_track_quat('-Z','Y').to_euler(); d.type='ORTHO'; d.ortho_scale=scale; bpy.context.scene.camera=c

def textured(path,label):
    meshes=setup(path); sc=bpy.context.scene; camera(); sc.render.engine='BLENDER_EEVEE'; sc.render.resolution_x=640; sc.render.resolution_y=640; sc.render.resolution_percentage=100; sc.render.image_settings.file_format='PNG'; sc.view_settings.view_transform='Standard'; sc.view_settings.look='Medium High Contrast'; sc.view_settings.exposure=-1.0
    if sc.world is None: sc.world=bpy.data.worlds.new('RBF world')
    sc.world.color=(0.025,0.025,0.025)
    for name,position,power,size in [('Key',(target.x+0.35,target.y-0.35,target.z+0.35),80,0.5),('Fill',(target.x-0.25,target.y+0.4,target.z+0.15),35,0.7),('Rim',(target.x-0.2,target.y-0.1,target.z+0.6),50,0.4)]:
        ld=bpy.data.lights.new(name,'AREA'); ld.energy=power; ld.shape='DISK'; ld.size=size; lo=bpy.data.objects.new(name,ld); bpy.context.scene.collection.objects.link(lo); lo.location=position; lo.rotation_euler=(target-lo.location).to_track_quat('-Z','Y').to_euler()
    sc.render.filepath=str(out/f'{label}-textured.png'); bpy.ops.render.render(write_still=True)
    return meshes

textured(source,'neutral')
meshes=textured(deformed,'deformed')
key_name='landmark105_rbf'
for o in meshes:
    if o.data.shape_keys:
        for k in o.data.shape_keys.key_blocks: k.value=1.0 if k.name==key_name else 0.0
sc=bpy.context.scene; sc.render.filepath=str(out/'deformed-textured.png'); bpy.ops.render.render(write_still=True)
