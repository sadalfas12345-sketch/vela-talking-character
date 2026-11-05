"""Render a GLB with an automatically refined camera JSON."""
import json, sys
from pathlib import Path
import bpy
from mathutils import Vector
from mathutils import Matrix

def main():
    if len(sys.argv)<4: raise SystemExit('Usage: blender -b --python render_goal1_refined_camera.py -- model.glb camera.json output.png')
    glb=Path(sys.argv[-3]).resolve(); cp=Path(sys.argv[-2]).resolve(); out=Path(sys.argv[-1]).resolve(); c=json.loads(cp.read_text())
    bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=str(glb)); scene=bpy.context.scene
    cd=bpy.data.cameras.new('Goal 1 refined camera'); cam=bpy.data.objects.new('Goal 1 refined camera',cd); scene.collection.objects.link(cam); scene.camera=cam
    cam.location=Vector(c['cameraLocation'])
    # Use Blender's calibrated look-at convention for the render. The facial
    # basis is retained in the JSON as measured diagnostics; it is not silently
    # substituted into Blender's camera-axis convention.
    cam.rotation_euler=(Vector(c['target'])-cam.location).to_track_quat('-Z','Y').to_euler()
    cd.type='ORTHO'; cd.ortho_scale=float(c['orthoScale'])
    scene.render.engine='BLENDER_EEVEE'; scene.render.resolution_x=640; scene.render.resolution_y=640; scene.render.resolution_percentage=100; scene.render.image_settings.file_format='PNG'; scene.render.film_transparent=False; scene.view_settings.view_transform='Standard'; scene.view_settings.look='Medium High Contrast'; scene.view_settings.exposure=0.0
    world=bpy.data.worlds.new('Goal 1 refined world'); world.use_nodes=True; world.node_tree.nodes['Background'].inputs['Color'].default_value=(.008,.008,.008,1); world.node_tree.nodes['Background'].inputs['Strength'].default_value=.25; scene.world=world
    meshes=[o for o in scene.objects if o.type=='MESH']; corners=[o.matrix_world@Vector(q) for o in meshes for q in o.bound_box]; low=Vector((min(q.x for q in corners),min(q.y for q in corners),min(q.z for q in corners))); high=Vector((max(q.x for q in corners),max(q.y for q in corners),max(q.z for q in corners))); diagonal=(high-low).length; focus=Vector(c['target'])
    for name,loc,energy,size in [('key',focus+Vector((diagonal,-diagonal,diagonal)),900,diagonal*.8),('fill',focus+Vector((-diagonal,-diagonal*.5,diagonal*.5)),500,diagonal),('rim',focus+Vector((0,diagonal,diagonal)),700,diagonal*.7)]:
        ld=bpy.data.lights.new(name,'AREA'); ld.energy=energy; ld.shape='DISK'; ld.size=size; lo=bpy.data.objects.new(name,ld); scene.collection.objects.link(lo); lo.location=loc; lo.rotation_euler=(focus-loc).to_track_quat('-Z','Y').to_euler()
    scene.render.filepath=str(out); bpy.ops.render.render(write_still=True); print(json.dumps({'output':str(out)}))
if __name__=='__main__': main()
