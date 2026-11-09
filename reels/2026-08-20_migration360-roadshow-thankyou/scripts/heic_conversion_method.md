# HEIC → JPG conversion method (works on this machine)

`pip install pillow-heif` (installs cleanly, no build tools needed on Win/py3.12), then:

```python
import pillow_heif
from PIL import Image, ImageOps
pillow_heif.register_heif_opener()

img = Image.open(src_heic_path)
img = ImageOps.exif_transpose(img)   # bakes in EXIF orientation rotation
if img.mode != "RGB":
    img = img.convert("RGB")
img.save(dst_jpg_path, "JPEG", quality=92, exif=img.info.get("exif", b""))
```

Python: `C:\Users\AU-0011-PFEC-G\AppData\Local\Programs\Python\Python312\python.exe`. No ffmpeg/ImageMagick needed — pillow-heif (method a) worked first try. Loop this over the remaining 16 Perth HEIC files in `input/perth/`.
