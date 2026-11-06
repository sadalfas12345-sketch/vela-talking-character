import argparse,json
from pathlib import Path
import cv2,numpy as np,mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

def main():
 p=argparse.ArgumentParser();p.add_argument('--video',type=Path,required=True);p.add_argument('--model',type=Path,default=Path('models/face_landmarker.task'));p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 cap=cv2.VideoCapture(str(a.video));fps=cap.get(cv2.CAP_PROP_FPS) or 30;raw=[];frames=[]
 opts=vision.FaceLandmarkerOptions(base_options=python.BaseOptions(model_asset_path=str(a.model.resolve())),running_mode=vision.RunningMode.IMAGE,num_faces=1,output_face_blendshapes=False,output_facial_transformation_matrixes=False)
 with vision.FaceLandmarker.create_from_options(opts) as detector:
  while True:
   ok,bgr=cap.read()
   if not ok:break
   frame=len(raw);raw.append(bgr);r=detector.detect(mp.Image(image_format=mp.ImageFormat.SRGB,data=cv2.cvtColor(bgr,cv2.COLOR_BGR2RGB)))
   reason='valid'
   if len(r.face_landmarks)!=1: reason='face_count_'+str(len(r.face_landmarks));lm=None
   else:
    allp=np.asarray([[x.x,x.y,x.z] for x in r.face_landmarks[0]],float)
    if len(allp)<468: reason='landmark_count_'+str(len(allp));lm=None
    elif not np.isfinite(allp[:468]).all(): reason='nonfinite_coordinates';lm=None
    else:lm=allp[:468]
   frames.append({'frame':frame,'timestampSeconds':frame/fps,'valid':lm is not None,'reason':reason,'landmarks':lm.tolist() if lm is not None else None})
 valid=[np.asarray(x['landmarks'],float) for x in frames if x['valid']];neutral=np.median(np.asarray(valid[:min(8,len(valid))]),axis=0);stable=[33,263,1,152];ref=neutral[stable,:2];aligned=[];errors=[];raw_valid=[]
 for x in frames:
  if not x['valid']:continue
  lm=np.asarray(x['landmarks'],float);M,_=cv2.estimateAffinePartial2D(lm[stable,:2].astype(np.float32),ref.astype(np.float32),method=cv2.LMEDS);xy=np.c_[lm[:,:2],np.ones(468)]@M.T if M is not None else lm[:,:2];aligned.append(xy);raw_valid.append(x['frame'])
 aligned=np.asarray(aligned);eye=float(np.linalg.norm(ref[0]-ref[1]));neutral_xy=neutral[:,:2];jitter=float(np.sqrt(np.mean(np.sum((aligned[:min(8,len(aligned))]-neutral_xy)**2,axis=2)))/eye);jumps=np.linalg.norm(np.diff(aligned,axis=0),axis=2)/eye;max_jump=float(jumps.max()) if jumps.size else 0.;coverage=len(valid)/max(len(frames),1);score=(5 if coverage>=.98 else 0)+(5 if len(valid)>=.98*len(frames) else 0)+(5 if jitter<=.005 else 0)+(5 if max_jump<=.02 else 0);a.output.mkdir(parents=True,exist_ok=True);(a.output/'video_landmarks.json').write_text(json.dumps({'landmark_ids':list(range(468)),'fps':fps,'decoded_frames':len(frames),'valid_frames':len(valid),'coverage':coverage,'neutral_reference_frames':raw_valid[:min(8,len(raw_valid))],'interocularPixels':eye,'neutralRmsJitterNormalized':jitter,'maxInterframeJumpNormalized':max_jump,'score':score,'pass':score>=16 and coverage>=.98,'frames':frames},separators=(',',':')))
 for name,pos in [('neutral',0),('peak',int(np.argmax([np.mean(np.linalg.norm(np.asarray(x['landmarks'])[ [70,63,105,336,293,334],:2]-neutral[[70,63,105,336,293,334],:2],axis=1)) if x['valid'] else -1 for x in frames]))),('middle',len(frames)//2)]:
  if pos>=len(raw) or not frames[pos]['valid']:continue
  img=raw[pos].copy();pts=np.asarray(frames[pos]['landmarks'])[:468,:2];h,w=img.shape[:2]
  for i,(x,y) in enumerate(pts):
   px,py=int(x*w),int(y*h);cv2.circle(img,(px,py),2,(0,255,0),-1)
   if i in [33,263,70,63,105,336,293,334]:cv2.putText(img,str(i),(px+3,py-3),cv2.FONT_HERSHEY_SIMPLEX,.35,(0,255,255),1)
  cv2.imwrite(str(a.output/f'{name}-468-overlay.png'),img)
main()
