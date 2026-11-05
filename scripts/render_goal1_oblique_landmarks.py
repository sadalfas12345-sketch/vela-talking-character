"""Render accepted Goal 1 mesh attachments from an oblique camera."""
import json, sys
from pathlib import Path
import bpy
from mathutils import Vector

def main():
    if len(sys.argv) < 4:
        raise SystemExit('Usage: blender -b --python render_goal1_oblique_landmarks.py -- model.glb raycast.json output.png')
    glb = Path(sys.argv[-3]).resolve(); report_path = Path(sys.argv[-2]).resolve(); output = Path(sys.argv[-1]).resolve()
    report = json.loads(report_path.read_text())
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(glb))
    scene = bpy.context.scene; target = Vector(report['camera']['target']); location = Vector(report['camera']['cameraLocation'])
    rotation = (target-location).to_track_quat('-Z','Y')
    right = rotation @ Vector((1,0,0))
    oblique = location + right * ((location-target).length * 0.42)
    cam_data = bpy.data.cameras.new('Goal 1 oblique attachment camera'); cam = bpy.data.objects.new('Goal 1 oblique attachment camera', cam_data)
    scene.collection.objects.link(cam); scene.camera = cam; cam.location = oblique; cam.rotation_euler = (target-oblique).to_track_quat('-Z','Y').to_euler(); cam.data.type='ORTHO'; cam.data.ortho_scale=float(report['camera']['orthoScale'])*1.15
    scene.render.engine='BLENDER_EEVEE'; scene.render.resolution_x=640; scene.render.resolution_y=640; scene.render.resolution_percentage=100; scene.render.image_settings.file_format='PNG'; scene.render.film_transparent=False
    mat = bpy.data.materials.new('Accepted landmark markers'); mat.diffuse_color=(1,0.05,0.02,1); mat.use_nodes=True; bs=mat.node_tree.nodes.get('Principled BSDF'); bs.inputs['Base Color'].default_value=(1,0.02,0.01,1); bs.inputs['Emission Color'].default_value=(1,0.01,0.0,1); bs.inputs['Emission Strength'].default_value=2.0; bs.inputs['Roughness'].default_value=.3
    verts=[]; faces=[]
    for rec in report['records']:
        if not rec.get('frontSurface') or not rec.get('meshXYZ'): continue
        p=Vector(rec['meshXYZ']); n=Vector(rec.get('surfaceNormal') or (0,0,1)).normalized(); r=.0035
        base=len(verts); verts += [tuple(p+n*r),tuple(p+Vector((r,0,0))),tuple(p+Vector((-r,0,0))),tuple(p+Vector((0,r,0))),tuple(p+Vector((0,-r,0))),tuple(p+Vector((0,0,r))),tuple(p+Vector((0,0,-r)))]
        faces += [(base,base+1,base+3),(base,base+3,base+2),(base,base+2,base+4),(base,base+4,base+1),(base+5,base+3,base+1),(base+5,base+2,base+3),(base+5,base+4,base+2),(base+5,base+1,base+4),(base+6,base+3,base+1),(base+6,base+2,base+3),(base+6,base+4,base+2),(base+6,base+1,base+4)]
    mesh=bpy.data.meshes.new('Accepted 3D landmark attachment markers'); mesh.from_pydata(verts,[],faces); mesh.materials.append(mat); obj=bpy.data.objects.new('Accepted 3D landmark attachments',mesh); scene.collection.objects.link(obj)
    world=bpy.data.worlds.new('Goal 1 oblique world'); world.use_nodes=True; world.node_tree.nodes['Background'].inputs['Color'].default_value=(.008,.008,.008,1); world.node_tree.nodes['Background'].inputs['Strength'].default_value=.2; scene.world=world
    scene.render.filepath=str(output); bpy.ops.render.render(write_still=True); print(json.dumps({'output':str(output),'markers':len(verts)//7}))
if __name__=='__main__': main()
