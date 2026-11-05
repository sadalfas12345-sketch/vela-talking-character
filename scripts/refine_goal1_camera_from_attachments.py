"""Refine a discovered camera from stable 3D facial attachments."""
import json, math, sys
from pathlib import Path
import numpy as np

def unit(v):
    v=np.asarray(v,float); n=np.linalg.norm(v); return v/max(n,1e-12)
def main():
    if len(sys.argv)<4: raise SystemExit('Usage: python refine_goal1_camera_from_attachments.py camera.json raycast.json output.json')
    camera_path, ray_path, out = map(lambda p:Path(p).resolve(),sys.argv[-3:])
    cam=json.loads(camera_path.read_text()); ray=json.loads(ray_path.read_text())
    points={r['index']:np.asarray(r['meshXYZ'],float) for r in ray['records'] if r.get('frontSurface') and r.get('meshXYZ')}
    required=[33,263,1,152]
    if any(i not in points for i in required): raise SystemExit('Required stable facial attachments are unavailable')
    left,right,nose,chin=[points[i] for i in required]
    eye_mid=(left+right)/2; x=unit(right-left); down=unit(chin-eye_mid); raw=unit(nose-eye_mid)
    forward=unit(np.cross(x,down));
    if np.dot(forward,raw)<0: forward=-forward
    up=unit(np.cross(forward,x))
    target=eye_mid*0.35+nose*0.45+chin*0.20
    old_loc=np.asarray(cam['cameraLocation'],float); old_target=np.asarray(cam['target'],float); old_view=unit(old_target-old_loc)
    old_right=unit(np.cross(old_view,np.array([0,0,1.0])))
    if np.linalg.norm(old_right)<1e-5: old_right=unit(np.cross(old_view,np.array([0,1.0,0])))
    old_up=unit(np.cross(old_right,old_view))
    yaw=math.degrees(math.atan2(np.dot(old_view,x), max(1e-9,np.dot(old_view,-forward))))
    pitch=math.degrees(math.asin(max(-1,min(1,np.dot(old_view,up)))))
    roll=math.degrees(math.atan2(np.dot(old_right,up),np.dot(old_right,x)))
    distance=float(np.linalg.norm(old_loc-old_target))
    ipd=float(np.linalg.norm(right-left)); face_height=float(np.linalg.norm(chin-eye_mid))
    corrected={**cam,'target':target.tolist(),'cameraLocation':(target+forward*distance).tolist(),'orthoScale':max(ipd*3.5,face_height*1.25),'cameraBasis':{'right':x.tolist(),'up':up.tolist(),'forward':forward.tolist()},'selectionMethod':cam.get('selectionMethod','')+'; 3D stable-landmark orientation refinement','refinement':{'method':'3D eye-axis, nose-forward, chin-up frame from accepted attachments','yawBeforeDegrees':yaw,'pitchBeforeDegrees':pitch,'rollBeforeDegrees':roll,'yawAfterDegrees':0.0,'pitchAfterDegrees':0.0,'rollAfterDegrees':0.0,'interocularWorldUnits':ipd,'eyeToChinWorldUnits':face_height}}
    out.write_text(json.dumps(corrected,indent=2)+'\n')
    print(json.dumps(corrected['refinement']))
if __name__=='__main__': main()
