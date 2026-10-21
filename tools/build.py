"""Scan an SD card, group photos into shoots by capture-time gaps, export web images + data.js."""
import glob, json, os, subprocess, sys
from datetime import datetime
from PIL import Image, ImageOps

SRC = sys.argv[1] if len(sys.argv) > 1 else "/Volumes/NO NAME/DCIM"
OUT = os.path.join(os.path.dirname(__file__), "..", "docs")
GAP_HOURS = 3      # a new shoot starts after this much silence
MIN_SHOOT = 3      # smaller groups go to "Fragments"

def exif(path):
    im = Image.open(path); e = im.getexif(); x = e.get_ifd(0x8769)
    t = datetime.strptime(x.get(36867) or e.get(306), "%Y:%m:%d %H:%M:%S")
    s = x.get(33434)
    return im, {
        "time": t, "model": e.get(272, ""),
        "shutter": f"1/{round(1/float(s))}" if s and s < 1 else f"{s}s",
        "f": f"ƒ/{float(x.get(33437)):g}", "iso": int(x.get(34855) or 0),
        "focal": f"{float(x.get(37386)):g}mm",
    }

photos = []
for p in sorted(glob.glob(os.path.join(SRC, "**", "*.JPG"), recursive=True)):
    try: im, m = exif(p)
    except Exception as err: print("skip", p, err); continue
    m["src"], m["im"] = p, im
    photos.append(m)
photos.sort(key=lambda m: m["time"])

# drop any frame where macOS Vision finds a face (cached in faces.txt)
FACES = os.path.join(os.path.dirname(__file__), "faces.txt")
if not os.path.exists(FACES):
    out = subprocess.run(["swift", os.path.join(os.path.dirname(__file__), "faces.swift")] + [m["src"] for m in photos],
                         capture_output=True, text=True).stdout
    open(FACES, "w").write(out)
faces = {os.path.splitext(l.strip())[0] for l in open(FACES) if l.strip()}
photos = [m for m in photos if os.path.splitext(os.path.basename(m["src"]))[0] not in faces]

groups, cur = [], []
for m in photos:
    if cur and (m["time"] - cur[-1]["time"]).total_seconds() > GAP_HOURS * 3600:
        groups.append(cur); cur = []
    cur.append(m)
if cur: groups.append(cur)
shoots = [g for g in groups if len(g) >= MIN_SHOOT]
frag = [m for g in groups if len(g) < MIN_SHOOT for m in g]

names = {}
try: names = json.load(open(os.path.join(os.path.dirname(__file__), "titles.json")))
except FileNotFoundError: pass

os.makedirs(os.path.join(OUT, "img"), exist_ok=True)
def export(m):
    name = os.path.splitext(os.path.basename(m["src"]))[0]
    im = ImageOps.exif_transpose(m["im"]).convert("RGB")
    for size, suf in ((2400, "l"), (900, "s")):
        dst = os.path.join(OUT, "img", f"{name}_{suf}.jpg")
        if not os.path.exists(dst):
            c = im.copy(); c.thumbnail((size, size), Image.LANCZOS); c.save(dst, quality=86, progressive=True)
    pal = im.resize((64, 64)).quantize(5).convert("RGB").getcolors()
    pal = ["#%02x%02x%02x" % c for _, c in sorted(pal, reverse=True)]
    return {"id": name, "palette": pal, "w": im.width, "h": im.height, "time": m["time"].isoformat(),
            "exif": f'{m["focal"]} · {m["f"]} · {m["shutter"]} · ISO {m["iso"]}', "model": m["model"]}

data = []
for i, g in enumerate(shoots + ([frag] if frag else [])):
    key = g[0]["time"].strftime("%Y%m%d-%H%M") if g is not frag else "fragments"
    meta = names.get(key, {})
    data.append({"key": key, "title": meta.get("title", "Fragments" if g is frag else f"Series {i+1:02d}"),
                 "cover": meta.get("cover"),
                 "start": g[0]["time"].isoformat(), "end": g[-1]["time"].isoformat(),
                 "photos": [export(m) for m in g]})
    print(key, len(g))
open(os.path.join(OUT, "data.js"), "w").write("window.SHOOTS = " + json.dumps(data, ensure_ascii=False, indent=1) + ";")
