"""Audit whether Goal-1 barycentric triangles are representable in ARAP components."""
import json,sys
from pathlib import Path
import numpy as np
def arg(name):
    a=sys.argv[1:];return Path(a[a.index(name)+1]).resolve()
def main():
    goal=json.loads(arg('--goal1').read_text());rec={int(x['index']):x for x in goal['records'] if x.get('meshXYZ') is not None};ids=[70,63,105,336,293,334,159,145,386,374]
    rows=[]
    for n in [30,1]:
        z=np.load(arg('--directory')/f'female-component-{n}.npz');members=set(map(int,z['originalIndices']));represented=[];partial=[];outside=[]
        for i in ids:
            tri=[int(v) for v in rec[i]['triangleVertexIndices']];inside=sum(v in members for v in tri)
            if inside==3:represented.append(i)
            elif inside:partial.append({'id':i,'insideTriangleVertices':inside,'triangleVertexIndices':tri})
            else:outside.append(i)
        rows.append({'component':n,'vertices':len(members),'browAndEyelidIds':ids,'fullyRepresentedIds':represented,'partialBoundaryIds':partial,'outsideIds':outside,'adapterReadyForAllSelectedControls':len(represented)==len(ids)})
    out=arg('--output');out.write_text(json.dumps({'goal1AttachmentCount':sum(i in rec for i in range(468)),'components':rows},indent=2)+'\n');print(out.read_text())
if __name__=='__main__':main()
