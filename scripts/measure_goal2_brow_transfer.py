"""Measure exported original-Tripo brow transfer against Goal 1 attachments."""
import json, sys
from pathlib import Path
import bpy
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
def main():
    glb=Path(sys.argv[-2]).resolve(); out=Path(sys.argv[-1]).resolve(); ray=json.loads((ROOT/'verification/goal1-generalization-run/cross-character-accuracy/female/refined/raycast-report.json').read_text())
    attach={r['index']:np.asarray(r['meshXYZ'],float) for r in ray['records'] if r.get('meshXYZ')}
    bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=str(glb)); body=[o for o in bpy.context.scene.objects if o.type=='MESH' and o.name!='Icosphere'][0]; keys=body.data.shape_keys.key_blocks; key=keys.get('xfer_browInnerUp_original_tripo')
    base=np.empty((len(body.data.vertices),3),float); moved=np.empty_like(base); body.data.vertices.foreach_get('co',base.ravel()); key.data.foreach_get('co',moved.ravel()); delta=moved-base; mw=np.asarray(body.matrix_world,float); delta=delta@mw[:3,:3].T
    world=base@mw[:3,:3].T+mw[:3,3]; brow=[70,63,105,336,293,334]; stable=[33,263,1,152]; radius=.025
    brow_mask=np.zeros(len(world),bool)
    for i in brow: brow_mask |= np.linalg.norm(world-attach[i],axis=1)<=radius
    stable_mask=np.zeros(len(world),bool)
    for i in stable: stable_mask |= np.linalg.norm(world-attach[i],axis=1)<=radius
    eye_width=float(np.linalg.norm(attach[33]-attach[263])); mag=np.linalg.norm(delta,axis=1)
    report={'shapeKey':'xfer_browInnerUp_original_tripo','originalVertexCount':int(len(base)),'eyeWidthMillimeters':eye_width*1000,'requiredTenPercentMillimeters':eye_width*100,'browRegionVertexCount':int(brow_mask.sum()),'browMaxDisplacementMillimeters':float(mag[brow_mask].max()*1000),'browP95DisplacementMillimeters':float(np.percentile(mag[brow_mask],95)*1000),'browMedianDisplacementMillimeters':float(np.median(mag[brow_mask])*1000),'stableEyeNoseChinMaxDisplacementMillimeters':float(mag[stable_mask].max()*1000),'outsideBrowMaxDisplacementMillimeters':float(mag[~brow_mask].max()*1000),'allVerticesMaxDisplacementMillimeters':float(mag.max()*1000),'movedVertexCount':int((mag>1e-7).sum())}
    out.write_text(json.dumps(report,indent=2)+'\n'); print(json.dumps(report,indent=2))
if __name__=='__main__': main()
