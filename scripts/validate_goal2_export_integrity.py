"""Check exported Goal-2 mesh topology and evaluated shape-key triangle integrity."""
import json, sys, os
from pathlib import Path
import bpy, numpy as np

def main():
    a=sys.argv[sys.argv.index('--')+1:]; glb=Path(a[a.index('--glb')+1]).resolve(); out=Path(a[a.index('--report')+1]).resolve()
    bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=str(glb)); body=max([o for o in bpy.context.scene.objects if o.type=='MESH'],key=lambda o:len(o.data.vertices)); mesh=body.data
    key_name=os.environ.get('VELA_GOAL2_BROW_KEY','xfer_browInnerUp_model_agnostic'); base=np.empty((len(mesh.vertices),3),float); key=np.empty_like(base); mesh.vertices.foreach_get('co',base.ravel()); body.data.shape_keys.key_blocks[key_name].data.foreach_get('co',key.ravel())
    faces=np.asarray([[v for v in p.vertices] for p in mesh.polygons],int); b=base[faces]; k=key[faces]
    def areas(x): return np.linalg.norm(np.cross(x[:,1]-x[:,0],x[:,2]-x[:,0]),axis=1)
    ab,ak=areas(b),areas(k)
    edge_counts={}
    for tri in faces:
        for x,y in ((tri[0],tri[1]),(tri[1],tri[2]),(tri[2],tri[0])):
            e=tuple(sorted((int(x),int(y)))); edge_counts[e]=edge_counts.get(e,0)+1
    nonmanifold=sum(v!=2 for v in edge_counts.values());
    by_weight={}
    for weight in (0.0,0.25,0.5,0.75,1.0):
        x=b+(k-b)*weight; ax=areas(x)
        n0=np.cross(b[:,1]-b[:,0],b[:,2]-b[:,0]); nx=np.cross(x[:,1]-x[:,0],x[:,2]-x[:,0])
        by_weight[str(weight)]={'zeroAreaTriangles':int(np.count_nonzero(ax<=1e-12)),'collapsedTriangles':int(np.count_nonzero(ax < ab*1e-4)),'windingFlips':int(np.count_nonzero(np.einsum('ij,ij->i',n0,nx)<0))}
    full=by_weight['1.0']
    result={'glb':str(glb),'vertexCount':len(mesh.vertices),'triangleCount':len(faces),'neutralZeroAreaTriangles':int(np.count_nonzero(ab<=1e-12)),'deformedZeroAreaTriangles':full['zeroAreaTriangles'],'deformedCollapsedTriangles':full['collapsedTriangles'],'deformedWindingFlips':full['windingFlips'],'byWeight':by_weight,'nonManifoldOrBoundaryEdges':nonmanifold,'topologyStable':len(mesh.vertices)==len(key) and nonmanifold==0,'shapeKey':key_name}
    out.write_text(json.dumps(result,indent=2)+'\n'); print(json.dumps(result,indent=2))
if __name__=='__main__': main()
