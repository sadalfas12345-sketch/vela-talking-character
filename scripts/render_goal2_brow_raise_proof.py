"""Render neutral, half, and full browInnerUp on the exported Tripo GLB."""
import json, sys
from pathlib import Path
import bpy
from mathutils import Vector

def main():
    if len(sys.argv)<4: raise SystemExit('Usage: blender -b --python render_goal2_brow_raise_proof.py -- transfer.glb camera.json output-dir')
    glb=Path(sys.argv[-3]).resolve(); camera_json=Path(sys.argv[-2]).resolve(); out=Path(sys.argv[-1]).resolve(); out.mkdir(parents=True,exist_ok=True); c=json.loads(camera_json.read_text())
    bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=str(glb)); scene=bpy.context.scene
    cd=bpy.data.cameras.new('Goal 2 brow proof camera'); cam=bpy.data.objects.new('Goal 2 brow proof camera',cd); scene.collection.objects.link(cam); scene.camera=cam; cam.location=Vector(c['cameraLocation']); cam.rotation_euler=(Vector(c['target'])-cam.location).to_track_quat('-Z','Y').to_euler(); cd.type='ORTHO'; cd.ortho_scale=float(c['orthoScale'])
    scene.render.engine='BLENDER_EEVEE'; scene.render.resolution_x=640; scene.render.resolution_y=640; scene.render.resolution_percentage=100; scene.render.image_settings.file_format='PNG'; scene.view_settings.view_transform='Standard'; scene.view_settings.look='Medium High Contrast'; scene.view_settings.exposure=-1.0
    world=bpy.data.worlds.new('Goal 2 brow proof world'); world.use_nodes=True; world.node_tree.nodes['Background'].inputs['Color'].default_value=(.008,.008,.008,1); world.node_tree.nodes['Background'].inputs['Strength'].default_value=.25; scene.world=world
    focus=Vector(c['target']);
    for name,loc,energy,size in [('key',focus+Vector((.8,-.8,.8)),300,.8),('fill',focus+Vector((-.6,-.3,.4)),150,1.0),('rim',focus+Vector((0,.6,.8)),220,.7)]:
        ld=bpy.data.lights.new(name,'AREA'); ld.energy=energy; ld.shape='DISK'; ld.size=size; lo=bpy.data.objects.new(name,ld); scene.collection.objects.link(lo); lo.location=loc; lo.rotation_euler=(focus-lo.location).to_track_quat('-Z','Y').to_euler()
    key_name='xfer_browInnerUp_original_tripo'; captures=[]
    for label,value in [('neutral',0.0),('browInnerUp_50',0.5),('browInnerUp_100',1.0)]:
        for obj in scene.objects:
            if obj.type!='MESH' or not obj.data.shape_keys: continue
            for key in obj.data.shape_keys.key_blocks: key.value=value if key.name==key_name else 0.0
        scene.render.filepath=str(out/f'{label}.png'); bpy.ops.render.render(write_still=True); captures.append(str((out/f'{label}.png')))
    (out/'render-report.json').write_text(json.dumps({'glb':str(glb),'shapeKey':key_name,'captures':captures},indent=2)+'\n')
    print(json.dumps({'shapeKey':key_name,'captures':captures}))
if __name__=='__main__': main()
