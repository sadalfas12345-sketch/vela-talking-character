"""Record mesh transforms, bounds, and Goal-1 interocular units for both models."""
import json, sys
from pathlib import Path
import bpy, numpy as np

def inspect(path, report):
    bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=str(path)); meshes=[o for o in bpy.context.scene.objects if o.type=='MESH']; body=max(meshes,key=lambda o:len(o.data.vertices)); co=np.empty((len(body.data.vertices),3),float); body.data.vertices.foreach_get('co',co.ravel()); mw=np.asarray(body.matrix_world,float); w=co@mw[:3,:3].T+mw[:3,3]; return {'glb':str(path),'mesh':body.name,'vertexCount':len(co),'localBoundsMin':co.min(0).tolist(),'localBoundsMax':co.max(0).tolist(),'worldBoundsMin':w.min(0).tolist(),'worldBoundsMax':w.max(0).tolist(),'worldExtentsMillimeters':((w.max(0)-w.min(0))*1000).tolist(),'matrixWorld':mw.tolist(),'objectScale':[float(np.linalg.norm(mw[:3,i])) for i in range(3)],'armaturePresent':any(o.type=='ARMATURE' for o in bpy.context.scene.objects),'sceneUnitScale':bpy.context.scene.unit_settings.scale_length}

def main():
    a=sys.argv[sys.argv.index('--')+1:]; out=Path(a[a.index('--report')+1]).resolve(); result={}
    for model,key in [('female','--female'),('male','--male')]:
        path=Path(a[a.index(key)+1]).resolve(); m=inspect(path,None); ray=json.loads(Path(a[a.index('--'+model+'-ray')+1]).read_text()); rec={int(r['index']):np.asarray(r['meshXYZ'],float) for r in ray['records'] if r.get('meshXYZ')}; m['goal1InterocularMillimeters']=float(np.linalg.norm(rec[33]-rec[263])*1000); result[model]=m
    out.write_text(json.dumps(result,indent=2)+'\n'); print(json.dumps(result,indent=2))
if __name__=='__main__': main()
