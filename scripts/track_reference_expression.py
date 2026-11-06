"""Track MediaPipe face landmarks in a reference video and remove 2D head motion."""
import argparse,json
from pathlib import Path
import cv2,numpy as np,mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

def main():
 p=argparse.ArgumentParser();p.add_argument('--video',type=Path,required=True);p.add_argument('--model',type=Path,default=Path('models/face_landmarker.task'));p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 cap=cv2.VideoCapture(str(a.video)); fps=cap.get(cv2.CAP_PROP_FPS) or 30; frames=[]; opts=vision.FaceLandmarkerOptions(base_options=python.BaseOptions(model_asset_path=str(a.model.resolve())),running_mode=vision.RunningMode.IMAGE,num_faces=1,output_face_blendshapes=False,output_facial_transformation_matrixes=False)
 with vision.FaceLandmarker.create_from_options(opts) as detector:
  while True:
   ok,bgr=cap.read()
   if not ok:break
   rgb=cv2.cvtColor(bgr,cv2.COLOR_BGR2RGB); r=detector.detect(mp.Image(image_format=mp.ImageFormat.SRGB,data=rgb))
   if not r.face_landmarks: frames.append(None);continue
   frames.append(np.asarray([[x.x,x.y,x.z] for x in r.face_landmarks[0]],float))
 valid=[x for x in frames if x is not None]
 if not valid: raise RuntimeError('No face landmarks detected')
 neutral=np.median(np.asarray(valid[:max(1,min(8,len(valid)))]),axis=0); stable=[33,263,1,152]; ref=neutral[stable,:2]; rows=[]
 for fi,lm in enumerate(frames):
  if lm is None:continue
  src=lm[stable,:2]; M,_=cv2.estimateAffinePartial2D(src.astype(np.float32),ref.astype(np.float32),method=cv2.LMEDS)
  xy=np.c_[lm[:,:2],np.ones(len(lm))]@M.T if M is not None else lm[:,:2]
  ipd=float(np.linalg.norm(ref[0]-ref[1])); disp=(xy-neutral[:,:2])/max(ipd,1e-9)
  brow=float(np.mean(np.linalg.norm(disp[[70,63,105,336,293,334]],axis=1))); eyelid=float(np.mean(np.linalg.norm(disp[[159,145,386,374]],axis=1)))
  rows.append({'frame':fi,'timeSeconds':fi/fps,'landmarks':disp.tolist(),'browMotionNorm':brow,'eyelidMotionNorm':eyelid,'headAlignment':'similarity_2d_stable_eyes_nose_chin'})
 peak=max(rows,key=lambda x:x['browMotionNorm']); out={'video':str(a.video),'fps':fps,'frameCount':len(frames),'neutralFrameRange':[0,min(7,len(frames)-1)],'peakByBrowMotion':peak['frame'],'peakBrowMotionNorm':peak['browMotionNorm'],'peakEyelidMotionNorm':peak['eyelidMotionNorm'],'rows':rows};a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(out)+'\n')
if __name__=='__main__':main()
