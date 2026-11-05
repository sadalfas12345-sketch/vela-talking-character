"""Run MediaPipe on one refined neutral render and save its overlay."""
import json, sys
from pathlib import Path
import cv2, mediapipe as mp
import numpy as np

def main():
    if len(sys.argv)<4: raise SystemExit('Usage: python detect_goal1_refined_camera.py image.png model.task output-dir')
    image_path=Path(sys.argv[-3]).resolve(); model=Path(sys.argv[-2]).resolve(); out=Path(sys.argv[-1]).resolve(); out.mkdir(parents=True,exist_ok=True)
    image=cv2.imread(str(image_path)); rgb=cv2.cvtColor(image,cv2.COLOR_BGR2RGB)
    Base=mp.tasks.BaseOptions; Vision=mp.tasks.vision
    opts=Vision.FaceLandmarkerOptions(base_options=Base(model_asset_path=str(model)),num_faces=1,output_face_blendshapes=False,output_facial_transformation_matrixes=False)
    with Vision.FaceLandmarker.create_from_options(opts) as detector: result=detector.detect(mp.Image(image_format=mp.ImageFormat.SRGB,data=rgb))
    if not result.face_landmarks: raise SystemExit('No face detected')
    lm=np.asarray([[p.x,p.y,p.z] for p in result.face_landmarks[0]],float)
    overlay=image.copy(); pts=lm[:,:2]*np.array([image.shape[1],image.shape[0]])
    for x,y in pts.astype(int): cv2.circle(overlay,(x,y),2,(0,165,255),-1)
    cv2.imwrite(str(out/'frontal-landmarks.png'),overlay)
    (out/'detected-landmarks.json').write_text(json.dumps({'sourceImage':str(image_path),'landmarks':lm.tolist()},indent=2)+'\n')
    print(json.dumps({'detectedLandmarks':len(lm),'output':str(out)}))
if __name__=='__main__': main()
