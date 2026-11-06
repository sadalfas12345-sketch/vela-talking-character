import json,sys
from pathlib import Path
import numpy as np
from scipy.sparse import coo_matrix,eye,bmat,csc_matrix
from scipy.sparse.linalg import splu
def main():
 a=sys.argv[1:]; problem=Path(a[a.index('--problem')+1]); out=Path(a[a.index('--solution')+1]); z=np.load(problem); n=len(z['local_indices']); edges=z['edges']; rows=np.repeat(np.arange(len(edges)),2); cols=edges.ravel(); invlen=1/np.maximum(z['edge_lengths'],1e-9); vals=np.column_stack((-invlen,invlen)).ravel(); D=coo_matrix((vals,(rows,cols)),shape=(len(edges),n)).tocsc(); H=(D.T@D+eye(n)*1e-4).tocsc(); cv=z['constraint_vertices']; cb=z['constraint_bary']; m=len(cv); ar=[]; ac=[]; av=[]
 for j,(vi,b) in enumerate(zip(cv,cb)):
  for v,w in zip(vi,b): ar.append(j); ac.append(v); av.append(w)
 A=coo_matrix((av,(ar,ac)),shape=(m,n)).tocsc(); K=bmat([[H,A.T],[A,None]],format='csc'); lu=splu(K); delta=np.zeros((n,3)); residual=[]
 for k in range(3):
  b=np.r_[np.zeros(n),z['desired'][:,k]]; x=lu.solve(b); delta[:,k]=x[:n]; residual.append(float(np.max(np.abs(A@delta[:,k]-z['desired'][:,k]))))
 out.parent.mkdir(parents=True,exist_ok=True); np.savez_compressed(out,local_indices=z['local_indices'],delta_world=delta,eye_width=z['eye_width'],up=z['up'],constraint_residual=residual); print(json.dumps({'vertices':n,'constraints':m,'maxConstraintResidual':max(residual),'solution':str(out)}))
if __name__=='__main__': main()
