"""Audit the implemented Goal-2 QP and its geometric field, without changing it."""
import json,sys
from pathlib import Path
import numpy as np
from scipy.sparse import coo_matrix,eye,bmat
from scipy.sparse.linalg import svds

def main():
    a=sys.argv[1:]; problem=Path(a[a.index('--problem')+1]); solution=Path(a[a.index('--solution')+1]); out=Path(a[a.index('--report')+1]); z=np.load(problem); s=np.load(solution)
    n=len(z['local_indices']); edges=z['edges']; x=z['world_coords']; d=s['delta_world']; moved=np.linalg.norm(d,axis=1); lengths=z['edge_lengths']; posed=x+d
    e0=x[edges[:,0]]; e1=x[edges[:,1]]; p0=posed[edges[:,0]]; p1=posed[edges[:,1]]; ratio=np.linalg.norm(p1-p0,axis=1)/np.maximum(lengths,1e-12)
    degree=np.bincount(edges.ravel(),minlength=n); boundary=np.flatnonzero(degree==1); active=np.flatnonzero(moved>1e-9)
    # Connected components in the extracted local graph.
    parent=np.arange(n)
    def find(i):
        while parent[i]!=i: parent[i]=parent[parent[i]]; i=parent[i]
        return i
    for u,v in edges:
        ru,rv=find(int(u)),find(int(v))
        if ru!=rv: parent[rv]=ru
    comps=len(np.unique([find(i) for i in range(n)]))
    cv=z['constraint_vertices']; cb=z['constraint_bary']; A=np.zeros((len(cv),n))
    for j,(vs,bs) in enumerate(zip(cv,cb)):
        for v,b in zip(vs,bs): A[j,int(v)]+=b
    sv=np.linalg.svd(A,compute_uv=False); rank=int(np.linalg.matrix_rank(A,tol=1e-10))
    # Exact barycentric constraint residual in world units.
    cres=[]
    for vs,bs in zip(cv,cb): cres.append(np.sum(d[vs]*np.asarray(bs)[:,None],axis=0))
    cres=np.asarray(cres); desired=z['desired']; residual=np.max(np.abs(cres-desired))
    # Reproduce the implemented edge objective and its gradient norm.
    rows=np.repeat(np.arange(len(edges)),2); cols=edges.ravel(); invlen=1/np.maximum(lengths,1e-9); vals=np.column_stack((-invlen,invlen)).ravel(); D=coo_matrix((vals,(rows,cols)),shape=(len(edges),n)).tocsc(); H=D.T@D+eye(n)*1e-4; grad=np.column_stack([(H@d[:,k]) for k in range(3)])
    # Coincident duplicate vertices in the local mesh and their displacement disagreement.
    keys=np.round(x,8); _,inv,counts=np.unique(keys,axis=0,return_inverse=True,return_counts=True); dup_groups=[]; dup_diff=[]
    for g,c in enumerate(counts):
        if c>1:
            ids=np.flatnonzero(inv==g); dup_groups.append(ids.tolist()); dup_diff.append(float(np.max(np.linalg.norm(d[ids]-d[ids[0]],axis=1))))
    report={'problem':str(problem),'solution':str(solution),'vertices':n,'edges':len(edges),'connectedComponents':comps,'localBoundaryVertices':len(boundary),'activeVertices':len(active),'boundaryMotionMax':float(moved[boundary].max()) if len(boundary) else 0.0,'interiorMotionMax':float(moved[degree>1].max()),'edgeStretchMin':float(ratio.min()),'edgeStretchP95':float(np.percentile(ratio,95)),'edgeStretchMax':float(ratio.max()),'constraintRows':len(cv),'constraintRank':rank,'constraintSingularValues':sv.tolist(),'maxBarycentricResidual':float(residual),'objectiveGradientNorm':float(np.linalg.norm(grad)),'coincidentVertexGroups':len(dup_groups),'maxCoincidentDisplacementDifference':float(max(dup_diff) if dup_diff else 0.0),'orientationTriangleCount':len(z['orientation_triangles']),'activeOrientationConstraints':s['active_orientation_constraints'].tolist(),'implementedObjective':'min_delta sum_(u,v) ||(delta_u-delta_v)/L_uv||^2 + 1e-4||delta||^2','implementedConstraints':'A delta = desired for x,y,z; active linearized signed-area rows >= 0.5*q0','boundaryCondition':'vertices outside extracted local submesh are implicitly fixed at zero displacement; no explicit Dirichlet halo'}
    out.parent.mkdir(parents=True,exist_ok=True); out.write_text(json.dumps(report,indent=2)+'\n')
if __name__=='__main__': main()
