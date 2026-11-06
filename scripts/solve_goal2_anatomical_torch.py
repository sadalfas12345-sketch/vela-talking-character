"""Autograd nonlinear anatomical equilibrium with true dihedral bending."""
import json,sys,time
from pathlib import Path
import numpy as np,torch
from solve_goal2_anatomical_physics import embed
def arg(n):
 a=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else sys.argv[1:];return Path(a[a.index(n)+1]).resolve()
def quads(faces):
 d={}
 for fi,t in enumerate(faces):
  for u,v in ((t[0],t[1]),(t[1],t[2]),(t[2],t[0])):d.setdefault(tuple(sorted((int(u),int(v)))),[]).append((int(t[0]),int(t[1]),int(t[2])))
 q=[]
 for e,fs in d.items():
  if len(fs)==2:
   a,b=e;c=list(set(fs[0])-set(e))[0];dd=list(set(fs[1])-set(e))[0];q.append((a,b,c,dd))
 return np.asarray(q,dtype=int)
def angles(p,q):
 a,b,c,d=[p[:,i] for i in range(4)] if p.ndim==3 else [p[i] for i in range(4)]
 e=b-a;eh=e/torch.clamp(torch.linalg.vector_norm(e,dim=-1,keepdim=True),min=1e-9);n0=torch.linalg.cross(b-a,c-a,dim=-1);n0=n0/torch.clamp(torch.linalg.vector_norm(n0,dim=-1,keepdim=True),min=1e-9);n1=torch.linalg.cross(d-a,b-a,dim=-1);n1=n1/torch.clamp(torch.linalg.vector_norm(n1,dim=-1,keepdim=True),min=1e-9);return torch.atan2(torch.sum(eh*torch.linalg.cross(n0,n1,dim=-1),dim=-1),torch.sum(n0*n1,dim=-1))
def solve_level(p,faces,edges,L,quad,qtheta,anchor,fibers,activation,contraction,init=None):
 dtype=torch.float64; P=torch.tensor(p,dtype=dtype); q=torch.nn.Parameter(P.clone() if init is None else torch.tensor(init,dtype=dtype)); E=torch.tensor(edges); LL=torch.tensor(L,dtype=dtype); Q=torch.tensor(quad); QT=torch.tensor(qtheta,dtype=dtype); A=torch.tensor(anchor,dtype=dtype); F=torch.tensor(fibers); fiberL=torch.linalg.vector_norm(P[F[:,1]]-P[F[:,0]],dim=1) if len(fibers) else torch.empty(0,dtype=dtype); N=torch.tensor(faces); neutral_n=torch.linalg.cross(P[N[:,1]]-P[N[:,0]],P[N[:,2]]-P[N[:,0]],dim=-1);neutral_area=torch.linalg.vector_norm(neutral_n,dim=1);neutral_n=neutral_n/torch.clamp(neutral_area[:,None],min=1e-9)
 def energy():
  d=q[E[:,1]]-q[E[:,0]]; el=torch.linalg.vector_norm(d,dim=1);stretch=.5*torch.mean(((el-LL)/torch.clamp(LL,min=1e-9))**2)
  if len(Q):bend=.5*.15*torch.mean(((angles(q[Q],q[Q])-QT)/torch.pi)**2)
  else:bend=q.sum()*0
  anchorE=.5*3.0*torch.mean(A[:,None]*(q-P)**2)
  if len(F):
   df=q[F[:,1]]-q[F[:,0]]; lf=torch.linalg.vector_norm(df,dim=1); muscle=.5*2.0*torch.mean(((lf-fiberL*(1-activation*contraction))/torch.clamp(fiberL,min=1e-9))**2)
  else:muscle=q.sum()*0
  area=torch.sum(neutral_n*torch.linalg.cross(q[N[:,1]]-q[N[:,0]],q[N[:,2]]-q[N[:,0]],dim=-1),dim=1)/torch.clamp(neutral_area,min=1e-9); quality=100.*torch.mean(torch.relu(.25-area)**2)+10000.*torch.mean(torch.relu(-area)**2)
  return stretch+bend+anchorE+muscle+quality,{'stretch':float(stretch.detach()),'bend':float(bend.detach()),'anchor':float(anchorE.detach()),'muscle':float(muscle.detach()),'quality':float(quality.detach()),'minArea':float(area.min().detach())}
 opt=torch.optim.LBFGS([q],lr=.5,max_iter=120,tolerance_grad=1e-8,tolerance_change=1e-12,line_search_fn='strong_wolfe'); info={}
 def closure():
  opt.zero_grad();e,_=energy();e.backward();return e
 opt.step(closure);e,info=energy();grad=torch.autograd.grad(e,q,retain_graph=False)[0];info.update({'gradientResidual':float(torch.linalg.vector_norm(grad).detach()),'energy':float(e.detach())});return q.detach().numpy(),info
def main():
 z=np.load(arg('--physics'));donor=json.loads(arg('--donor').read_text());p=z['physics_vertices'].astype(float);faces=z['physics_faces'];edges=z['physics_edges'];L=z['rest_lengths'];quad=quads(faces);P=torch.tensor(p,dtype=torch.float64);qtheta=angles(P[torch.tensor(quad)],P[torch.tensor(quad)]).detach().numpy() if len(quad) else np.empty(0);labels=z['labels'];anchor=z['anchor_weights'].astype(float)+(labels=='eye')*3+(labels=='eyelid')*2;fib=z['muscle_fibers'];
 # Frontalis fibers need a stable superior insertion. Derive it from the brow
 # region rather than from world axes or character-specific coordinates.
 brow_nodes=np.flatnonzero(labels=='brow'); brow_center=p[brow_nodes].mean(0); superior=np.zeros(len(p));
 if len(fib):
  valid=np.linalg.norm(p[fib[:,1]]-p[fib[:,0]],axis=1)>1e-8; fib=fib[valid];
  for u,v in fib:
   superior[u if np.linalg.norm(p[u]-brow_center)>np.linalg.norm(p[v]-brow_center) else v]=2.0
 anchor=np.maximum(anchor,superior); ratio=float(np.mean(donor['desiredMagnitudesMillimeters'])/(donor['targetEyeWidth']*1000)); target=float(np.mean(donor['desiredMagnitudesMillimeters'])/1000);trial=.1; qtrial,itr=solve_level(p,faces,edges,L,quad,qtheta,anchor,fib,1,trial);brow=np.asarray(donor['browLandmarkIndices']);ray=json.loads(arg('--goal1').read_text());rec={int(r['index']):r for r in ray['records'] if r.get('meshXYZ')};btarget=np.asarray([rec[int(i)]['meshXYZ'] for i in brow]);cand=np.flatnonzero(labels=='brow');bidx=np.asarray([cand[np.argmin(np.linalg.norm(p[cand]-bt,axis=1))] for bt in btarget]);obs=float(np.mean(np.linalg.norm(qtrial[bidx]-p[bidx],axis=1)));contraction=float(np.clip(trial*target/max(obs,1e-9),.001,.10));logs=[];targets=[];qprev=None;t0=time.time()
 for a in [0,.25,.5,.75,1]:
  q,info=solve_level(p,faces,edges,L,quad,qtheta,anchor,fib,a,contraction,qprev);qprev=q;targets.append(embed(z,q));info.update({'activation':a,'browObservedPhysicsMean':float(np.mean(np.linalg.norm(q[bidx]-p[bidx],axis=1))),'browTargetMean':target});logs.append(info)
 out=arg('--output');out.parent.mkdir(parents=True,exist_ok=True);np.savez_compressed(out,render_targets=np.asarray(targets),activation=np.asarray([0,.25,.5,.75,1]),contraction=contraction,activation_ratio=ratio);out.with_suffix('.json').write_text(json.dumps({'targetRatio':ratio,'trialContraction':trial,'trialObservedBrow':obs,'calibratedContraction':contraction,'weights':logs,'runtimeSeconds':time.time()-t0},indent=2)+'\n')
if __name__=='__main__':main()
