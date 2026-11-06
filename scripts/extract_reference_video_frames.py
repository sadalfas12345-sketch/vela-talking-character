import cv2,sys
from pathlib import Path
video=Path(sys.argv[1]); out=Path(sys.argv[2]); out.mkdir(parents=True,exist_ok=True)
cap=cv2.VideoCapture(str(video)); count=int(cap.get(cv2.CAP_PROP_FRAME_COUNT)); fps=cap.get(cv2.CAP_PROP_FPS) or 30; duration=count/fps
for name,t in [('start',0.0),('early',duration*.25),('middle',duration*.5),('late',duration*.75),('end',max(duration-.1,0))]:
 cap.set(cv2.CAP_PROP_POS_MSEC,t*1000); ok,frame=cap.read()
 if ok: cv2.imwrite(str(out/f'{name}.png'),frame)
print({'frames':count,'fps':fps,'duration':duration,'output':str(out)})
