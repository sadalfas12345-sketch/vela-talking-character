import bpy, json, sys
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree

root=Path(__file__).resolve().parents[1]
asset=root/'assets/tripo/vela-photoreal'
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(asset/'vela-photoreal-faced.glb'))
cal=json.loads((asset/'face-calibration.json').read_text(encoding='utf-8'))['landmarks3d']
scene=bpy.context.scene
meshes=[o for o in scene.objects if o.type=='MESH' and o.data.vertices and 'inner mouth' not in o.name.lower()]
deps=bpy.context.evaluated_depsgraph_get()
tree=BVHTree.FromObject(meshes[0],deps)
rows=[]
for name,p in cal.items():
    marker=scene.objects.get(f'VelaLandmark_{name}')
    expected=Vector(p)
    actual=marker.matrix_world.translation.copy() if marker else None
    nearest=tree.find_nearest(actual) if actual else None
    rows.append({'name':name,'markerPresent':bool(marker),'expectedBlenderWorld':list(expected),'actualBlenderWorld':list(actual) if actual else None,'exportCoordinateErrorMeters':float((actual-expected).length) if actual else None,'nearestMeshDistanceMeters':float(nearest[3]) if nearest else None,'parent':marker.parent.name if marker and marker.parent else None,'parentBone':marker.parent_bone if marker else None})
report={'markerCount':sum(x['markerPresent'] for x in rows),'landmarks':rows}
Path('verification/tripo-landmark-node-inspection.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps(report,indent=2))
