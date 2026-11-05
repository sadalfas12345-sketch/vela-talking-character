from pathlib import Path
from PIL import Image, ImageChops, ImageEnhance
import sys
old, new, out = map(lambda p: Path(p).resolve(), sys.argv[-3:])
diff = ImageChops.difference(Image.open(old).convert('RGB'), Image.open(new).convert('RGB'))
ImageEnhance.Contrast(diff).enhance(8).save(out)
