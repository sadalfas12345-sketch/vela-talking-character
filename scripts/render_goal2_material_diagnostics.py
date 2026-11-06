"""Render neutral and full brow poses with clay, unlit, and normal materials."""
import json, os, sys
from pathlib import Path
import bpy
from mathutils import Vector

def args():
    a=sys.argv[sys.argv.index('--')+1:]
    return {k:Path(a[a.index(k)+1]).resolve() for k in ('--glb','--camera','--output')}

def material_mode(mode):
    for mat in bpy.data.materials:
        mat.use_nodes=True
        nt=mat.node_tree; nt.nodes.clear()
        out=nt.nodes.new('ShaderNodeOutputMaterial'); out.location=(420,0)
        if mode=='normals':
            geo=nt.nodes.new('ShaderNodeNewGeometry'); geo.location=(-500,0)
            mul=nt.nodes.new('ShaderNodeVectorMath'); mul.operation='SCALE'; mul.location=(-300,0); mul.inputs[1].default_value=(.5,.5,.5)
            add=nt.nodes.new('ShaderNodeVectorMath'); add.operation='ADD'; add.location=(-100,0); add.inputs[1].default_value=(.5,.5,.5)
            bs=nt.nodes.new('ShaderNodeBsdfDiffuse'); bs.location=(180,0); bs.inputs['Roughness'].default_value=.9
            nt.links.new(geo.outputs['Normal'],mul.inputs[0]); nt.links.new(mul.outputs[0],add.inputs[0]); nt.links.new(add.outputs[0],bs.inputs['Color']); nt.links.new(bs.outputs[0],out.inputs['Surface'])
        elif mode=='unlit':
            em=nt.nodes.new('ShaderNodeEmission'); em.inputs['Color'].default_value=(.55,.55,.55,1); em.inputs['Strength'].default_value=1; nt.links.new(em.outputs[0],out.inputs['Surface'])
        else:
            bs=nt.nodes.new('ShaderNodeBsdfPrincipled'); bs.inputs['Base Color'].default_value=(.42,.42,.42,1); bs.inputs['Roughness'].default_value=.82; bs.inputs['Metallic'].default_value=0; nt.links.new(bs.outputs[0],out.inputs['Surface'])

def main():
    a=args(); c=json.loads(a['--camera'].read_text()); out=a['--output']; out.mkdir(parents=True,exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=str(a['--glb'])); scene=bpy.context.scene
    cd=bpy.data.cameras.new('Goal 2 material diagnostic camera'); cam=bpy.data.objects.new('Goal 2 material diagnostic camera',cd); scene.collection.objects.link(cam); scene.camera=cam
    cam.location=Vector(c['cameraLocation']); cam.rotation_euler=(Vector(c['target'])-cam.location).to_track_quat('-Z','Y').to_euler(); cd.type='ORTHO'; cd.ortho_scale=float(c['orthoScale'])
    res=int(os.environ.get('VELA_GOAL2_RENDER_RES','640')); scene.render.engine='BLENDER_EEVEE'; scene.render.resolution_x=res; scene.render.resolution_y=res; scene.render.resolution_percentage=100; scene.render.image_settings.file_format='PNG'; scene.view_settings.view_transform='Standard'; scene.view_settings.look='Medium High Contrast'; scene.view_settings.exposure=float(os.environ.get('VELA_GOAL2_EXPOSURE','-2'))
    world=bpy.data.worlds.new('Goal 2 material diagnostic world'); world.use_nodes=True; world.node_tree.nodes['Background'].inputs['Color'].default_value=(.008,.008,.008,1); world.node_tree.nodes['Background'].inputs['Strength'].default_value=.25; scene.world=world
    focus=Vector(c['target']); s=float(c['orthoScale'])
    for name,loc,energy,size in [('key',focus+Vector((s*1.4,-s*1.4,s*1.4)),300,s*.9),('fill',focus+Vector((-s*1.1,-s*.5,s*.7)),150,s),('rim',focus+Vector((0,s,s*1.1)),220,s*.8)]:
        ld=bpy.data.lights.new(name,'AREA'); ld.energy=energy; ld.shape='DISK'; ld.size=size; ob=bpy.data.objects.new(name,ld); scene.collection.objects.link(ob); ob.location=loc; ob.rotation_euler=(focus-ob.location).to_track_quat('-Z','Y').to_euler()
    keyname=os.environ.get('VELA_GOAL2_BROW_KEY','real_browInnerUp_quality_qp')
    for mode in ('clay','unlit','normals'):
        material_mode(mode)
        for weight,label in ((0,'neutral'),(1,'full')):
            for ob in scene.objects:
                if ob.type=='MESH' and ob.data.shape_keys:
                    for key in ob.data.shape_keys.key_blocks: key.value=weight if key.name==keyname else 0
            scene.render.filepath=str(out/f'{mode}_{label}.png'); bpy.ops.render.render(write_still=True)
if __name__=='__main__': main()
