"""Render the exported/reimported model-agnostic brow key at five weights."""
import json, os, sys
from pathlib import Path
import bpy
from mathutils import Vector

def main():
    a=sys.argv[sys.argv.index('--')+1:]
    glb=Path(a[a.index('--glb')+1]).resolve(); camj=Path(a[a.index('--camera')+1]).resolve(); out=Path(a[a.index('--output')+1]).resolve(); out.mkdir(parents=True,exist_ok=True)
    c=json.loads(camj.read_text()); bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=str(glb)); scene=bpy.context.scene
    cd=bpy.data.cameras.new('Goal 2 independent sweep camera'); cam=bpy.data.objects.new('Goal 2 independent sweep camera',cd); scene.collection.objects.link(cam); scene.camera=cam; cam.location=Vector(c['cameraLocation']); cam.rotation_euler=(Vector(c['target'])-cam.location).to_track_quat('-Z','Y').to_euler(); cd.type='ORTHO'; cd.ortho_scale=float(c['orthoScale'])
    res=int(os.environ.get('VELA_GOAL2_RENDER_RES','640')); scene.render.engine='BLENDER_EEVEE'; scene.render.resolution_x=res; scene.render.resolution_y=res; scene.render.resolution_percentage=100; scene.render.image_settings.file_format='PNG'; scene.view_settings.view_transform='Standard'; scene.view_settings.look='Medium High Contrast'; scene.view_settings.exposure=float(os.environ.get('VELA_GOAL2_EXPOSURE','-2'))
    world=bpy.data.worlds.new('Goal 2 independent sweep world'); world.use_nodes=True; world.node_tree.nodes['Background'].inputs['Color'].default_value=(.008,.008,.008,1); world.node_tree.nodes['Background'].inputs['Strength'].default_value=.25; scene.world=world
    focus=Vector(c['target']); s=float(c['orthoScale'])
    for name,loc,energy,size in [('key',focus+Vector((s*1.4,-s*1.4,s*1.4)),300,s*.9),('fill',focus+Vector((-s*1.1,-s*.5,s*.7)),150,s),('rim',focus+Vector((0,s,s*1.1)),220,s*.8)]:
        ld=bpy.data.lights.new(name,'AREA'); ld.energy=energy; ld.shape='DISK'; ld.size=size; ob=bpy.data.objects.new(name,ld); scene.collection.objects.link(ob); ob.location=loc; ob.rotation_euler=(focus-ob.location).to_track_quat('-Z','Y').to_euler()
    keyname='xfer_browInnerUp_model_agnostic'; captures=[]
    for weight in [0,.25,.5,.75,1]:
        for ob in scene.objects:
            if ob.type=='MESH' and ob.data.shape_keys:
                for key in ob.data.shape_keys.key_blocks: key.value=weight if key.name==keyname else 0
        p=out/f'browInnerUp_{weight:.2f}.png'; scene.render.filepath=str(p); bpy.ops.render.render(write_still=True); captures.append(str(p))
    (out/'weight-sweep-report.json').write_text(json.dumps({'glb':str(glb),'shapeKey':keyname,'weights':[0,.25,.5,.75,1],'captures':captures},indent=2)+'\n')
if __name__=='__main__': main()
