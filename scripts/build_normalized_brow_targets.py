"""Map measured 2D reference-video motion into each Tripo landmark frame."""
import argparse,json
from pathlib import Path
import numpy as np
def main():
 p=argparse.ArgumentParser();p.add_argument('--table',type=Path,required=True);p.add_argument('--goal1',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();tab=json.loads(a.table.read_text());ray=json.loads(a.goal1.read_text());rec={int(x['index']):x for x in ray['records'] if x.get('meshXYZ')};lm={i:np.asarray(rec[i]['meshXYZ'],float) for i in rec}; brow=[70,63,105,336,293,334]; right=lm[263]-lm[33]; eye=float(np.linalg.norm(right));right/=eye;eye_mid=(lm[33]+lm[263])*.5;up=eye_mid-lm[152];up/=max(np.linalg.norm(up),1e-12);peak=max(tab['rows'],key=lambda x:x['browMotionNorm']); disp=np.asarray(peak['landmarks'],float); targets={};
 for i in brow: targets[str(i)]=(lm[i]+disp[i,0]*eye*right-disp[i,1]*eye*up).tolist()
 out={'sourceTable':str(a.table),'peakFrame':peak['frame'],'peakBrowMotionNorm':peak['browMotionNorm'],'peakEyelidMotionNorm':peak['eyelidMotionNorm'],'interocularDistance':eye,'landmarkTargets':targets,'depthComponent':'unmeasured_2d_only','coordinateFrame':'Tripo eye-axis and eye-midpoint-to-chin up'};a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(out,indent=2)+'\n')
if __name__=='__main__':main()
