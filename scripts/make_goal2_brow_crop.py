from pathlib import Path
from PIL import Image, ImageDraw
import sys

old,new,out=map(lambda p:Path(p).resolve(),sys.argv[-3:])
a=Image.open(old).convert('RGB').crop((150,170,500,310)).resize((700,280))
b=Image.open(new).convert('RGB').crop((150,170,500,310)).resize((700,280))
panel=Image.new('RGB',(700,560),'black')
panel.paste(a,(0,0)); panel.paste(b,(0,280))
d=ImageDraw.Draw(panel); d.text((8,8),'Neutral',fill='yellow'); d.text((8,288),'100% browInnerUp',fill='yellow')
panel.save(out)
