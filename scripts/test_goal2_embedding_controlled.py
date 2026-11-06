"""Controlled physics-to-render embedding test with no muscle or solver activation."""
import json,sys
from pathlib import Path
import numpy as np
from solve_goal2_anatomical_physics import embed

def arg(name):
    a=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else sys.argv[1:]
    return Path(a[a.index(name)+1]).resolve()

def main():
    z=np.load(arg('--physics')); cam=json.loads(arg('--camera').read_text())
    p=z['physics_vertices'].astype(float); labels=z['labels']; valid=z['embedding_valid']; eye=float(np.linalg.norm(np.ptp(z['render_world'][valid],axis=0)))
    if 'cameraBasis' in cam: up=np.asarray(cam['cameraBasis']['up'],float)
    else:
        forward=np.asarray(cam['target'],float)-np.asarray(cam['cameraLocation'],float); forward/=max(np.linalg.norm(forward),1e-12); world_up=np.array([0.,0.,1.]); right=np.cross(forward,world_up)
        if np.linalg.norm(right)<1e-8: world_up=np.array([0.,1.,0.]); right=np.cross(forward,world_up)
        right/=max(np.linalg.norm(right),1e-12); up=np.cross(right,forward)
    up/=max(np.linalg.norm(up),1e-12)
    brow=np.flatnonzero(labels=='brow'); center=p[brow].mean(0); sigma=max(eye*.75,1e-9)
    dist=np.linalg.norm(p-center,axis=1); field=np.exp(-.5*(dist/sigma)**2)[:,None]*up[None,:]
    weights=[0,.25,.5,.75,1]; targets=[]; rows=[]
    for w in weights:
        q=p+field*(.01*eye*w)
        out=embed(z,q); targets.append(out)
        disp=np.linalg.norm(out-z['render_world'],axis=1); seam=disp[valid]
        rows.append({'weight':w,'physicsMaxDisplacement':float(np.linalg.norm(q-p,axis=1).max()),'renderDisplacementMedian':float(np.median(seam)),'renderDisplacementP95':float(np.percentile(seam,95)),'renderDisplacementMax':float(seam.max()),'neutralErrorMax':float(np.linalg.norm(out-z['render_world'],axis=1)[valid].max())})
    out=arg('--output');out.parent.mkdir(parents=True,exist_ok=True);np.savez_compressed(out,render_targets=np.asarray(targets),controlled_weights=np.asarray(weights));out.with_suffix('.json').write_text(json.dumps({'displacement':'smooth gaussian forehead field along calibrated camera up','amplitudeAt100Percent':.01*eye,'weights':rows,'extrapolatingEmbeddings':int(np.sum(np.any((z['embedding_weights'][valid]<-1e-8)|(z['embedding_weights'][valid]>1+1e-8),axis=1))),'validAttachments':int(valid.sum())},indent=2)+'\n')
if __name__=='__main__':main()
