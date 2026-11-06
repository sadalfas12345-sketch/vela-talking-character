import sys
from pathlib import Path
import numpy as np
from scipy.sparse import coo_matrix,eye,bmat,vstack
from scipy.sparse.linalg import splu

def main():
 a=sys.argv[1:]; problem=Path(a[a.index('--problem')+1]); out=Path(a[a.index('--solution')+1]); z=np.load(problem)
 all_edges=z['edges']; seed=np.unique(np.concatenate([z['quality_edges'].ravel(),z['orientation_triangles'].ravel(),z['constraint_vertices'].ravel()]))
 for _ in range(2):
  hit=np.isin(all_edges,seed).any(axis=1); seed=np.unique(np.concatenate([seed,all_edges[hit].ravel()]))
 keep=np.sort(seed); remap=-np.ones(len(z['local_indices']),dtype=int); remap[keep]=np.arange(len(keep)); edge_mask=np.all(np.isin(all_edges,keep),axis=1); edges=remap[all_edges[edge_mask]]
 n=len(keep); edge_lengths=z['edge_lengths'][edge_mask]; world_coords=z['world_coords'][keep]; z_local_indices=z['local_indices'][keep]; rows=np.repeat(np.arange(len(edges)),2); cols=edges.ravel(); invlen=1/np.maximum(edge_lengths,1e-9); vals=np.column_stack((-invlen,invlen)).ravel(); D=coo_matrix((vals,(rows,cols)),shape=(len(edges),n)).tocsc(); H=(D.T@D+eye(n)*1e-4).tocsc()
 cv=remap[z['constraint_vertices']]; cb=z['constraint_bary']; m=len(cv); ar=[]; ac=[]; av=[]
 for j,(vi,b) in enumerate(zip(cv,cb)):
  for v,w in zip(vi,b): ar.append(j); ac.append(v); av.append(w)
 A=coo_matrix((av,(ar,ac)),shape=(m,n)).tocsc(); ot=remap[z['orientation_triangles']]; on=z['orientation_normals']; oq=z['orientation_q0']; margin=.90*oq
 qe=remap[z['quality_edges']]; ql=z['quality_edge_lengths']; strain=.20*ql
 def ori_row(j):
   t=ot[j]; p=world_coords[t]; nn=on[j]; e1=p[1]-p[0]; e2=p[2]-p[0]; g1=np.cross(e2,nn); g2=np.cross(nn,e1); return t,(-g1-g2,g1,g2)
 def edge_row(j):
  t=qe[j]; p=world_coords[t]; u=(p[1]-p[0])/max(ql[j],1e-12); return t,(-u,u)
 def rows_for(active_ori,active_edge):
  rr=[]; cc=[]; vv=[]
  for row,j in enumerate(active_ori):
   t,gs=ori_row(j)
   for v,g in zip(t,gs):
    for axis in range(3): rr.append(row); cc.append(axis*n+int(v)); vv.append(float(g[axis]))
  off=len(active_ori)
  for row,j in enumerate(active_edge):
   t,gs=edge_row(j)
   for v,g in zip(t,gs):
    for axis in range(3): rr.append(off+row); cc.append(axis*n+int(v)); vv.append(float(g[axis]))
  return coo_matrix((vv,(rr,cc)),shape=(off+len(active_edge),3*n)).tocsc()
 active_ori=[]; active_edge=[]; edge_sign=[]; delta=np.zeros((n,3)); residual=[]
 for iteration in range(24):
  H3=bmat([[H,None,None],[None,H,None],[None,None,H]],format='csc'); A3=bmat([[A,None,None],[None,A,None],[None,None,A]],format='csc'); Q=rows_for(active_ori,active_edge); C=vstack([A3,Q],format='csc') if active_ori or active_edge else A3; K=bmat([[H3,C.T],[C,None]],format='csc')
  rhs=np.r_[np.zeros(3*n),z['desired'][:,0],z['desired'][:,1],z['desired'][:,2]]
  if active_ori: rhs=np.r_[rhs,(-oq[np.asarray(active_ori)]+margin[np.asarray(active_ori)])]
  for j,s in zip(active_edge,edge_sign): rhs=np.r_[rhs,s*strain[j]]
  x=splu(K).solve(rhs); delta=x[:3*n].reshape(3,n).T; bad=[]
  for j in range(len(ot)):
   t,gs=ori_row(j); q=float(oq[j]+sum(np.dot(g,delta[v]) for g,v in zip(gs,t))-margin[j])
   if q < -1e-9 and j not in active_ori: bad.append(('o',j,q))
  for j in range(len(qe)):
   t,gs=edge_row(j); dl=float(sum(np.dot(g,delta[v]) for g,v in zip(gs,t))); active=[(k,s) for k,s in zip(active_edge,edge_sign)]
   if dl > strain[j]+1e-9 and (j,1) not in active: bad.append(('e',j,dl-strain[j]))
   if dl < -strain[j]-1e-9 and (j,-1) not in active: bad.append(('e',j,dl+strain[j]))
  if not bad: break
  kind,j,val=min(bad,key=lambda x:x[2])
  if kind=='o': active_ori.append(j)
  else: active_edge.append(j); edge_sign.append(1 if val>0 else -1)
 for k in range(3): residual.append(float(np.max(np.abs(A@delta[:,k]-z['desired'][:,k]))))
 out.parent.mkdir(parents=True,exist_ok=True); np.savez_compressed(out,local_indices=z_local_indices,delta_world=delta,eye_width=z['eye_width'],up=z['up'],constraint_residual=residual,active_orientation_constraints=np.asarray(active_ori),active_quality_edges=np.asarray(active_edge),active_quality_signs=np.asarray(edge_sign)); print({'vertices':n,'qualityEdges':len(qe),'activeOrientationConstraints':len(active_ori),'activeQualityConstraints':len(active_edge),'maxConstraintResidual':max(residual),'solution':str(out)})
if __name__=='__main__': main()
