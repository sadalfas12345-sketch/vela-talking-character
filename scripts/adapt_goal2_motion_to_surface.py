"""Back off a restored QP field only as far as nonlinear surface quality requires."""
import json,sys
from pathlib import Path
import numpy as np

def main():
    a=sys.argv[1:]; problem=Path(a[a.index('--problem')+1]); solution=Path(a[a.index('--solution')+1]); out=Path(a[a.index('--output')+1]); report=Path(a[a.index('--report')+1])
    z=np.load(problem); s=np.load(solution); base=z['world_coords']; d=s['delta_world']; edges=z['edges']; lens=z['edge_lengths']; moved=np.linalg.norm(d,axis=1); active=moved>max(np.percentile(moved,75),1e-12); edge_mask=active[edges].any(axis=1); e=edges[edge_mask]; l0=lens[edge_mask]
    tris=z['orientation_triangles']; q0=z['orientation_q0'];
    def quality(t):
        p=base+float(t)*d; ratio=np.linalg.norm(p[e[:,1]]-p[e[:,0]],axis=1)/np.maximum(l0,1e-12)
        q=[]
        if len(tris):
            v=p[tris]; n=np.cross(v[:,1]-v[:,0],v[:,2]-v[:,0]); q=np.einsum('ij,ij->i',n,z['orientation_normals'])
        return ratio,q
    lo,hi=0.0,1.0
    for _ in range(36):
        mid=(lo+hi)*.5; ratio,q=quality(mid)
        if (len(ratio) and (ratio.max()>1.25 or ratio.min()<.80)) or (len(q) and q.min()<=0): hi=mid
        else: lo=mid
    scale=lo; ratio,q=quality(scale); delta=d*scale; out.parent.mkdir(parents=True,exist_ok=True); np.savez_compressed(out,local_indices=s['local_indices'],delta_world=delta,eye_width=s['eye_width'],up=s['up'],constraint_residual=np.asarray(s['constraint_residual'])*scale,active_orientation_constraints=s['active_orientation_constraints'],adaptive_motion_scale=scale)
    report.parent.mkdir(parents=True,exist_ok=True); report.write_text(json.dumps({'input':str(solution),'scale':scale,'edgeCount':int(len(e)),'edgeRatioMin':float(ratio.min()) if len(ratio) else None,'edgeRatioMax':float(ratio.max()) if len(ratio) else None,'minSignedArea':float(q.min()) if len(q) else None},indent=2)+'\n')
if __name__=='__main__': main()
