"""Synthetic checks for row-frame embedding and dihedral energy derivatives."""
import json, numpy as np
from pathlib import Path
def embed_rotation_test():
    p=np.array([[0.,0.,0.],[1.,0.,0.],[0.,1.,0.]])
    q=np.array([[0.,0.,0.],[0.,1.,0.],[-1.,0.,0.]])
    off=np.array([.2,.3,.1]); e0=p[1]-p[0]; f0=p[2]-p[0]; n0=np.cross(e0,f0); n0/=np.linalg.norm(n0); e1=q[1]-q[0];f1=q[2]-q[0];n1=np.cross(e1,f1);n1/=np.linalg.norm(n1); C0=np.stack([e0,f0,n0],axis=1);C1=np.stack([e1,f1,n1],axis=1); R=np.linalg.solve(C0.T,C1.T); got=off@R; expected=np.array([-.3,.2,.1]); return {'passed':bool(np.max(np.abs(got-expected))<1e-12),'got':got.tolist(),'expected':expected.tolist()}
def dihedral_energy(x,theta0):
    p0,p1,p2,p3=x; e=p1-p0; le=np.linalg.norm(e); eh=e/le; n0=np.cross(p1-p0,p2-p0); n0/=np.linalg.norm(n0); n1=np.cross(p3-p0,p1-p0); n1/=np.linalg.norm(n1); th=np.arctan2(np.dot(eh,np.cross(n0,n1)),np.dot(n0,n1)); return .5*(th-theta0)**2
def finite_difference():
    x=np.array([[0.,0.,0.],[1.,0.,0.],[0.,1.,0.],[1.,1.,.2]],float);p0,p1,p2,p3=x;e=p1-p0;eh=e/np.linalg.norm(e);n0=np.cross(p1-p0,p2-p0);n0/=np.linalg.norm(n0);n1=np.cross(p3-p0,p1-p0);n1/=np.linalg.norm(n1);t0=np.arctan2(np.dot(eh,np.cross(n0,n1)),np.dot(n0,n1));eps=1e-6;g=np.zeros_like(x)
    for i in range(4):
        for j in range(3):
            xp=x.copy();xm=x.copy();xp[i,j]+=eps;xm[i,j]-=eps;g[i,j]=(dihedral_energy(xp,t0)-dihedral_energy(xm,t0))/(2*eps)
    return {'passed':bool(np.linalg.norm(g)<1e-8),'gradientNormAtNeutral':float(np.linalg.norm(g)),'energyAtNeutral':float(dihedral_energy(x,t0))}
def main():
    out=Path('verification/goal2-browInnerUp-proof/anatomical-math-synthetic-tests.json');out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps({'embedding90Degree':embed_rotation_test(),'dihedralFiniteDifference':finite_difference()},indent=2)+'\n')
if __name__=='__main__':main()
