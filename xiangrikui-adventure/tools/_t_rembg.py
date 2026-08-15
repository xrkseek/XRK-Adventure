from pathlib import Path
from PIL import Image
from rembg import remove
import sys
sys.path.insert(0,"tools")
from pixel_cook import split_frames
im=Image.open("assets/characters/yumumu/raw/idle_ai.png").convert("RGBA")
fs=split_frames(im,16)
print("frames", len(fs), fs[0].size)
# test one frame
out=remove(fs[0])
out.save("assets/characters/yumumu/refs/_rembg_f1.png")
print("rembg f1", out.size, "alpha", out.mode)
# count opaque
px=out.load(); n=sum(1 for y in range(out.height) for x in range(out.width) if px[x,y][3]>128)
print("opaque", n)
