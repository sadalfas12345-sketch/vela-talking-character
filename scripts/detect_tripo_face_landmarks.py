import argparse, json
from pathlib import Path
import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
p=argparse.ArgumentParser();p.add_argument('image');p.add_argument('model');p.add_argument('out');a=p.parse_args()
img=cv2.imread(a.image); rgb=cv2.cvtColor(img,cv2.COLOR_BGR2RGB)
opts=vision.FaceLandmarkerOptions(base_options=python.BaseOptions(model_asset_path=a.model),running_mode=vision.RunningMode.IMAGE,num_faces=1,output_face_blendshapes=False,output_facial_transformation_matrixes=False)
with vision.FaceLandmarker.create_from_options(opts) as landmarker:
 r=landmarker.detect(mp.Image(image_format=mp.ImageFormat.SRGB,data=rgb))
 if not r.face_landmarks: raise SystemExit('No face detected')
 lm=r.face_landmarks[0]
 data={'image':str(Path(a.image).resolve()),'width':img.shape[1],'height':img.shape[0],'landmarks':[[float(x.x),float(x.y),float(x.z)] for x in lm]}
 Path(a.out).write_text(json.dumps(data,indent=2))
 print('detected',len(lm),'landmarks')
