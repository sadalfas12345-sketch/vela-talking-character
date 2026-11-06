"""Nonlinear spring/bending/anchor/muscle equilibrium on the cached face mesh."""
import json,sys,time
from pathlib import Path
import numpy as np
from scipy.sparse import coo_matrix

def arg(n):
 a=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else sys.argv[1:]; return Path(a[a.index(n)+1]).resolve()
def pairs_from_faces(faces,p):
 ef={}
 for fi,t in enumerate(faces):
  for u,v in ((t[0],t[1]),(t[1],t[2]),(t[2],t[0])):ef.setdefault(tuple(sorted((int(u),int(v)))),[]).append((fi,set(map(int,t))))
 out=[]
 for e,fs in ef.items():
  if len(fs)==2:
   a=list(fs[0][1]-set(e))[0];b=list(fs[1][1]-set(e))[0];out.append((a,b))
 return np.asarray(out,dtype=int)
def embed(z,q):
 tri=z['embedding_triangles']; w=z['embedding_weights']; out=z['render_world'].copy(); valid=z['embedding_valid']; ids=np.flatnonzero(valid); t=tri[ids]; pn=z['physics_vertices']; p0=pn[t]; q0=q[t]; e10=p0[:,1]-p0[:,0];e20=p0[:,2]-p0[:,0];n0=np.cross(e10,e20);n0/=np.maximum(np.linalg.norm(n0,axis=1,keepdims=True),1e-12);e1=q0[:,1]-q0[:,0];e2=q0[:,2]-q0[:,0];n1=np.cross(e1,e2);n1/=np.maximum(np.linalg.norm(n1,axis=1,keepdims=True),1e-12);C0=np.stack([e10,e20,n0],axis=2);C1=np.stack([e1,e2,n1],axis=2);R=np.linalg.solve(np.swapaxes(C0,-1,-2),np.swapaxes(C1,-1,-2));o=z['embedding_offsets'][ids];o2=np.einsum('...j,...ji->...i',o,R);out[ids]=(q0*w[ids,:,None]).sum(axis=1)+o2;return out
def main():
 z=np.load(arg('--physics')); donor=json.loads(arg('--donor').read_text()); out=arg('--output'); t0=time.time();p=z['physics_vertices'].astype(float);faces=z['physics_faces']; edges=z['physics_edges'];L=z['rest_lengths']; fibers=z['muscle_fibers']; fpair=pairs_from_faces(faces,p); bL=np.linalg.norm(p[fpair[:,0]]-p[fpair[:,1]],axis=1) if len(fpair) else np.empty(0); labels=z['labels']; eye=float(donor['targetEyeWidth']); activation_ratio=float(np.mean(donor['desiredMagnitudesMillimeters'])/(eye*1000.0)); contraction=min(.12,max(.01,.5*activation_ratio)); face_normals=np.cross(p[faces[:,1]]-p[faces[:,0]],p[faces[:,2]]-p[faces[:,0]]);face_normals/=np.maximum(np.linalg.norm(face_normals,axis=1,keepdims=True),1e-12); rest_area=np.einsum('ij,ij->i',face_normals,np.cross(p[faces[:,1]]-p[faces[:,0]],p[faces[:,2]]-p[faces[:,0]])); anchor=z['anchor_weights'].astype(float); anchor+=(labels=='eye')*3+(labels=='eyelid')*2
 def solve(a):
  q=p.copy(); activeL=L*(1-a*contraction); activeB=bL; dt=.12
  for it in range(500):
   F=np.zeros_like(q); d=q[edges[:,1]]-q[edges[:,0]];ln=np.linalg.norm(d,axis=1);dir=d/np.maximum(ln[:,None],1e-12);fs=(ln-L)/np.maximum(L,1e-9);force=dir*fs[:,None];np.add.at(F,edges[:,0],force);np.add.at(F,edges[:,1],-force)
   if len(fpair):
    d=q[fpair[:,1]]-q[fpair[:,0]];ln=np.linalg.norm(d,axis=1);dir=d/np.maximum(ln[:,None],1e-12);fb=(ln-activeB)/np.maximum(activeB,1e-9);force=.25*dir*fb[:,None];np.add.at(F,fpair[:,0],force);np.add.at(F,fpair[:,1],-force)
   if len(fibers):
    d=q[fibers[:,1]]-q[fibers[:,0]];ln=np.linalg.norm(d,axis=1);dir=d/np.maximum(ln[:,None],1e-12);lf=np.linalg.norm(p[fibers[:,1]]-p[fibers[:,0]],axis=1);fm=(ln-lf*(1-a*contraction))/np.maximum(lf,1e-9);force=.8*dir*fm[:,None];np.add.at(F,fibers[:,0],force);np.add.at(F,fibers[:,1],-force)
   F-=anchor[:,None]*(q-p)*2.0; step=dt/(1.0+np.bincount(edges.ravel(),minlength=len(p))[:,None]);cand=q+step*F; area=np.einsum('ij,ij->i',face_normals,np.cross(cand[faces[:,1]]-cand[faces[:,0]],cand[faces[:,2]]-cand[faces[:,0]]));
   if np.min(area)<=0: dt*=.5; continue
   q=cand
   if np.max(np.linalg.norm(step*F,axis=1))<1e-8:break
  return q,it+1
 targets=[];logs=[]
 for a in [0,.25,.5,.75,1]:
  q,it=solve(a);targets.append(embed(z,q));logs.append({'activation':a,'iterations':it,'maxPhysicsDisplacement':float(np.max(np.linalg.norm(q-p,axis=1))),'minTriangleAreaRatio':float(np.min(np.einsum('ij,ij->i',face_normals,np.cross(q[faces[:,1]]-q[faces[:,0]],q[faces[:,2]]-q[faces[:,0]]))/np.maximum(rest_area,1e-12)))})
 out.parent.mkdir(parents=True,exist_ok=True);np.savez_compressed(out,physics_targets=np.asarray([p]),render_targets=np.asarray(targets),activation=np.asarray([0,.25,.5,.75,1]),activation_ratio=activation_ratio,contraction=contraction);out.with_suffix('.json').write_text(json.dumps({'physics':str(arg('--physics')),'donor':str(arg('--donor')),'activationRatio':activation_ratio,'contraction':contraction,'weights':logs,'runtimeSeconds':time.time()-t0},indent=2)+'\n')
if __name__=='__main__':main()
