"""Step 1 official libigl ARAP test on extracted real Tripo components."""
import json, time, sys
from pathlib import Path
import numpy as np
import igl
try:
    import psutil
except ImportError:
    psutil=None

def arg(name):
    a=sys.argv[1:]; return Path(a[a.index(name)+1]).resolve()
def handles(V):
    out=[0];out.append(int(np.argmax(np.linalg.norm(V-V[0],axis=1))))
    a,b=V[out[0]],V[out[1]];line=b-a;ll=max(float(np.dot(line,line)),1e-20)
    out.append(int(np.argmax([np.linalg.norm(q-a-line*np.dot(q-a,line)/ll) for q in V])))
    return np.asarray(out,dtype=np.int32)
def main():
    out=arg('--output');rows=[];proc=psutil.Process() if psutil else None
    for n in [30,1]:
        z=np.load(out.parent/f'female-component-{n}.npz');V=np.asarray(z['V'],dtype=np.float64);F=np.asarray(z['F'],dtype=np.int64);b=handles(V);diag=float(np.linalg.norm(V.max(0)-V.min(0)));direction=np.array([1.,0.,0.]);req=direction*.01*diag;bc=V[b].copy();bc[2]+=req
        data=igl.ARAPData();data.energy=igl.ARAP_ENERGY_TYPE_ELEMENTS;data.max_iter=100
        rss0=proc.memory_info().rss if proc else None;t0=time.perf_counter();status='ok';err=None
        try:
            igl.arap_precomputation(V,F,3,b,data);U=igl.arap_solve(bc,data,V.copy())
        except Exception as e:
            status='exception';err=repr(e);U=None
        runtime=time.perf_counter()-t0;rss1=proc.memory_info().rss if proc else None
        if U is not None:
            handle=float(np.linalg.norm(U[b[2]]-V[b[2]]));delta=U-V;free=np.ones(len(V),bool);free[b]=False;fd=delta[free]
            base=np.cross(V[F[:,1]]-V[F[:,0]],V[F[:,2]]-V[F[:,0]]);new=np.cross(U[F[:,1]]-U[F[:,0]],U[F[:,2]]-U[F[:,0]]);area0=np.linalg.norm(base,axis=1);area1=np.linalg.norm(new,axis=1)
            rows.append({'component':n,'vertices':len(V),'triangles':len(F),'bboxDiagonal':diag,'handles':b.tolist(),'requestedHandleMotion':float(np.linalg.norm(req)),'achievedHandleMotion':handle,'handleRatio':handle/float(np.linalg.norm(req)),'maxFreeMotion':float(np.max(np.linalg.norm(fd,axis=1))),'rmsFreeMotion':float(np.sqrt(np.mean(np.sum(fd*fd,axis=1)))),'newInversions':int(np.sum(np.einsum('ij,ij->i',base,new)<0)),'collapsedTriangles':int(np.sum(area1<area0*1e-4)),'minAreaRatio':float(np.min(area1/np.maximum(area0,1e-20))),'runtimeSeconds':runtime,'peakRssDeltaBytes':None if rss0 is None else max(0,rss1-rss0),'status':status,'error':err})
        else: rows.append({'component':n,'vertices':len(V),'triangles':len(F),'bboxDiagonal':diag,'handles':b.tolist(),'status':status,'error':err,'runtimeSeconds':runtime})
    out.write_text(json.dumps({'libiglVersion':getattr(igl,'__version__','2.6.3'),'api':'arap_precomputation/arap_solve','components':rows},indent=2)+'\n');print(json.dumps({'components':rows},indent=2))
if __name__=='__main__':main()
