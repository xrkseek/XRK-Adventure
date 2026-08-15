from PIL import Image
from rembg import remove, new_session
im=Image.open("assets/characters/yumumu/refs/_rembg_f1.png")
# check if truly transparent
px=im.load(); tr=sum(1 for y in range(im.height) for x in range(im.width) if px[x,y][3]<8)
print("transparent", tr, "size", im.size)
# try isnet on original cell
import sys; sys.path.insert(0,"tools")
from pixel_cook import split_frames
cell=split_frames(Image.open("assets/characters/yumumu/raw/idle_ai.png"),16)[0]
session=new_session("isnet-general-use")
out=remove(cell, session=session)
out.save("assets/characters/yumumu/refs/_rembg_isnet_f1.png")
px=out.load(); n=sum(1 for y in range(out.height) for x in range(out.width) if px[x,y][3]>128)
print("isnet opaque", n)
