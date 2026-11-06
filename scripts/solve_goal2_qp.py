import json,sys
from pathlib import Path
import numpy as np
from scipy.sparse import coo_matrix,eye,bmat,csc_matrix,vstack
from scipy.sparse.linalg import splu
def main():
 a=sys.argv[1:]; problem=Path(a[a.index('--problem')+1]); out=Path(a[a.index('--solution')+1]); z=np.load(problem); n=len(z['local_indices']); edges=z['edges']; rows=np.repeat(np.arange(len(edges)),2); cols=edges.ravel(); invlen=1/np.maximum(z['edge_lengths'],1e-9); vals=np.column_stack((-invlen,invlen)).ravel(); D=coo_matrix((vals,(rows,cols)),shape=(len(edges),n)).tocsc(); H=(D.T@D+eye(n)*1e-4).tocsc(); cv=z['constraint_vertices']; cb=z['constraint_bary']; m=len(cv); ar=[]; ac=[]; av=[]
 for j,(vi,b) in enumerate(zip(cv,cb)):
  for v,w in zip(vi,b): ar.append(j); ac.append(v); av.append(w)
 A=coo_matrix((av,(ar,ac)),shape=(m,n)).tocsc(); ot=z['orientation_triangles']; on=z['orientation_normals']; oq=z['orientation_q0']
 # Keep a conservative positive-area margin so the linearized constraint
 # remains orientation-safe under the quadratic term of the true triangle
 # area, including at full morph weight.
 margin=.50*oq
 def orientation_rows(active):
  rr=[]; cc=[]; vv=[]
  for row,t in enumerate(ot[active]):
   p=z['world_coords'][t]; nn=on[active[row]]; e1=p[1]-p[0]; e2=p[2]-p[0]
   g1=np.cross(e2,nn); g2=np.cross(nn,e1); g0=-g1-g2
   for v,g in zip(t,(g0,g1,g2)):
    for axis in range(3): rr.append(row); cc.append(axis*n+int(v)); vv.append(float(g[axis]))
  return coo_matrix((vv,(rr,cc)),shape=(len(active),3*n)).tocsc()
 active=[]; delta=np.zeros((n,3)); residual=[]
 for iteration in range(12):
  O=orientation_rows(active)
  A3=bmat([[A,None,None],[None,A,None],[None,None,A]],format='csc')
  if active:
   # Assemble the block-diagonal objective and stack equality rows in 3D.
   H3=bmat([[H,None,None],[None,H,None],[None,None,H]],format='csc'); C=vstack([A3,O],format='csc'); K=bmat([[H3,C.T],[C,None]],format='csc')
  else:
   H3=bmat([[H,None,None],[None,H,None],[None,None,H]],format='csc'); C=bmat([[A,None,None],[None,A,None],[None,None,A]],format='csc'); K=bmat([[H3,C.T],[C,None]],format='csc')
  rhs=np.r_[np.zeros(3*n),z['desired'][:,0],z['desired'][:,1],z['desired'][:,2],(-oq[active]+margin[active]) if active else np.zeros(0)]
  x=splu(K).solve(rhs); delta=x[:3*n].reshape(3,n).T
  if len(ot):
   vals=[]
   for j,t in enumerate(ot):
    p=z['world_coords'][t]; nn=on[j]; e1=p[1]-p[0]; e2=p[2]-p[0]; g1=np.cross(e2,nn); g2=np.cross(nn,e1); g0=-g1-g2
    vals.append(float(np.dot(g0,delta[t[0]])+np.dot(g1,delta[t[1]])+np.dot(g2,delta[t[2]])+oq[j]-margin[j]))
   bad=[j for j,v in enumerate(vals) if v < -1e-9 and j not in active]
   if bad: active.append(min(bad,key=lambda j:vals[j])); continue
  break
 for k in range(3): residual.append(float(np.max(np.abs(A@delta[:,k]-z['desired'][:,k]))))
 out.parent.mkdir(parents=True,exist_ok=True); np.savez_compressed(out,local_indices=z['local_indices'],delta_world=delta,eye_width=z['eye_width'],up=z['up'],constraint_residual=residual,active_orientation_constraints=np.asarray(active)); print(json.dumps({'vertices':n,'constraints':m,'orientationTriangles':len(ot),'activeOrientationConstraints':len(active),'maxConstraintResidual':max(residual),'solution':str(out)}))
if __name__=='__main__': main()
