"""Read-only topology audit for the preserved Tripo face and Vela derivative."""
import importlib.util, json
from pathlib import Path
import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('integrity',ROOT/'scripts'/'tripo-certify-integrity.py')
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
ASSET=ROOT/'assets'/'tripo'/'vela-photoreal'
FILES=['generated-original.glb','generated-rigged.glb','vela-photoreal-faced.glb']

def audit(name):
 data,doc,binary=mod.read_glb(ASSET/name)
 rows=[]
 for ni,node in enumerate(doc.get('nodes',[])):
  if 'mesh' not in node: continue
  mesh=doc['meshes'][node['mesh']]
  for pi,prim in enumerate(mesh.get('primitives',[])):
   attrs=prim.get('attributes',{})
   if 'POSITION' not in attrs: continue
   pos,_=mod.accessor_array(doc,binary,attrs['POSITION'])
   idx,_=mod.accessor_array(doc,binary,prim['indices']) if 'indices' in prim else (np.arange(len(pos),dtype=np.uint32)[:,None],None)
   idx=idx.reshape(-1)
   if prim.get('mode',4)!=4 or len(idx)%3: continue
   tri=idx.reshape(-1,3).astype(np.int64)
   # Blender's glTF export duplicates vertices at UV/normal seams. Weld only
   # coincident positions for the diagnostic connectivity calculation so those
   # export splits are not mistaken for anatomical openings.
   _,weld= np.unique(np.round(pos,7),axis=0,return_inverse=True)
   tri=weld[tri]
   edge=np.concatenate((tri[:,[0,1]],tri[:,[1,2]],tri[:,[2,0]]),axis=0)
   edge.sort(axis=1)
   unique,count=np.unique(edge,axis=0,return_counts=True)
   valid=unique[:,0]!=unique[:,1]
   unique,count=unique[valid],count[valid]
   graph=coo_matrix((np.ones(2*len(unique),dtype=np.uint8),(np.r_[unique[:,0],unique[:,1]],np.r_[unique[:,1],unique[:,0]])),shape=(len(pos),len(pos))).tocsr()
   component_count,labels=connected_components(graph,directed=False,return_labels=True)
   comp_sizes=np.bincount(labels,minlength=component_count)
   rows.append({'node':node.get('name',f'node_{ni}'),'mesh':mesh.get('name',f'mesh_{node["mesh"]}'),'primitive':pi,'vertices':int(len(pos)),'weldedPositionVertices':int(weld.max()+1),'triangles':int(len(tri)),'boundaryEdgesAfterPositionWeld':int((count==1).sum()),'nonManifoldEdgesAfterPositionWeld':int((count>2).sum()),'connectedComponentsAfterPositionWeld':int(component_count),'largestComponentVertices':int(comp_sizes.max()) if len(comp_sizes) else 0,'morphTargetNames':mesh.get('extras',{}).get('targetNames',[]),'skinned':'JOINTS_0' in attrs})
 return {'file':name,'meshObjects':len(doc.get('meshes',[])),'sceneMeshNodes':len(rows),'nodes':rows,'imageCount':len(doc.get('images',[])),'textureCount':len(doc.get('textures',[]))}

out={'method':'Direct GLB accessor inspection; coincident positions are welded at 0.1 micrometre tolerance for undirected triangle-edge incidence and sparse connected-component analysis. No geometry was modified.','files':[audit(f) for f in FILES], 'facialPartsNamedSeparately':False,'note':'The character is exported as one skinned mesh object with no independently named upper/lower lip objects and no original facial blendshapes. The lips are a textured region of the outer face surface. Whole-character topology can contain separate hair/clothing islands and open boundaries, so those counts do not imply a watertight whole-body shell.'}
path=ROOT/'verification'/'tripo-mouth-topology.json';path.write_text(json.dumps(out,indent=2)+'\n',encoding='utf-8')
print(json.dumps(out,indent=2))
