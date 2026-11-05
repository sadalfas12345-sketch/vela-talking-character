"""Create old-versus-refined camera comparison panels."""
from pathlib import Path
from PIL import Image, ImageDraw
import sys

def main():
    if len(sys.argv)<4: raise SystemExit('Usage: python make_goal1_camera_comparison.py old.png refined.png output.png')
    old, refined, out=map(lambda p:Path(p).resolve(),sys.argv[-3:])
    a=Image.open(old).convert('RGB'); b=Image.open(refined).convert('RGB'); panel=Image.new('RGB',(a.width*2,a.height+32),'black'); panel.paste(a,(0,32)); panel.paste(b,(a.width,32)); d=ImageDraw.Draw(panel); d.text((10,8),'Original selected camera',fill='white'); d.text((a.width+10,8),'3D-refined camera',fill='white'); panel.save(out)
if __name__=='__main__': main()
