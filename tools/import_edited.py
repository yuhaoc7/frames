"""Append a reviewed, locally edited batch to the existing Frames gallery.

Dry-run by default. --apply organizes private photos locally and writes web assets;
it never commits or pushes. Requires a complete, visually reviewed face-review.json.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
from datetime import datetime

from PIL import Image, ImageOps


def photo_id(path):
    match = re.match(r"^(DSCF\d+)(?:_|$)", path.stem)
    if not match:
        raise ValueError(f"Unrecognized frame name: {path.name}")
    return match[1]


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def preserve_copy(src, dst):
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        if digest(src) != digest(dst):
            raise ValueError(f"Conflicting private backup: {dst}")
    else:
        shutil.copy2(src, dst)
        if digest(src) != digest(dst):
            raise ValueError(f"Private backup verification failed: {dst}")


def export(path, identifier, out):
    with Image.open(path) as source:
        e = source.getexif()
        x = e.get_ifd(0x8769)
        time = datetime.strptime(x.get(36867) or e.get(306), "%Y:%m:%d %H:%M:%S")
        im = ImageOps.exif_transpose(source).convert("RGB")
        shutter = x.get(33434)
        shutter = f"1/{round(1 / float(shutter))}" if shutter and shutter < 1 else f"{shutter}s"
        metadata = {
            "id": identifier, "w": im.width, "h": im.height,
            "time": time.isoformat(), "model": e.get(272, ""),
            "exif": f'{float(x[37386]):g}mm · ƒ/{float(x[33437]):g} · {shutter} · ISO {int(x.get(34855) or 0)}',
        }
        colors = im.resize((64, 64)).quantize(5).convert("RGB").getcolors()
        metadata["palette"] = ["#%02x%02x%02x" % c for _, c in sorted(colors, reverse=True)]
        for size, suffix in ((2400, "l"), (900, "s")):
            target = out / "img" / f"{identifier}_{suffix}.jpg"
            if target.exists():
                raise ValueError(f"Refusing to overwrite an existing web image: {target}")
            target.parent.mkdir(parents=True, exist_ok=True)
            small = im.copy()
            small.thumbnail((size, size), Image.Resampling.LANCZOS)
            # Web files intentionally contain no EXIF/GPS or camera serial metadata.
            small.save(target, quality=86, progressive=True)
    return metadata


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("batch", type=Path)
    parser.add_argument("--review", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    batch = args.batch.resolve()
    repo = Path(__file__).resolve().parents[1]
    review = json.loads(args.review.read_text())
    originals = sorted((batch / "Originals").glob("*.JPG"))
    ids = {photo_id(p) for p in originals}
    reviewed = set(review["reviewed_ids"])
    faces = set(review["face_ids"])
    public = set(review["public_ids"])
    if not ids or ids != reviewed or faces & public or faces | public != ids:
        raise ValueError("Review must classify every original exactly once")
    if Path(review["batch"]).resolve() != batch:
        raise ValueError("Review belongs to a different batch")
    # Verify the review never silently drops a face found by Vision.
    detection = json.loads((batch / "Processing" / "face-detection.json").read_text())
    detected = {photo_id(Path(row["path"])) for row in detection if row["faces"]}
    scanned = {Path(row["path"]).resolve() for row in detection}
    if not detected <= faces or not {p.resolve() for p in originals} <= scanned:
        raise ValueError("Incomplete detection coverage or a detected face was not excluded")
    edited = sorted((batch / "Edited").glob("*.jpg"))
    if any(photo_id(p) not in ids or p.resolve() not in scanned for p in edited):
        raise ValueError("Unreviewed edited image")
    to_publish = [p for p in edited if photo_id(p) in public]
    to_private = [p for p in edited if photo_id(p) in faces]
    data_file = repo / "docs" / "data.js"
    text = data_file.read_text()
    if not text.startswith("window.SHOOTS = "):
        raise ValueError("Unrecognized gallery data format")
    data = json.loads(text[len("window.SHOOTS = "):].rstrip().rstrip(";"))
    existing = {p["id"] for group in data for p in group["photos"]}
    if existing & faces:
        raise ValueError("Reviewed face IDs already in gallery; resolve explicitly before publishing")
    to_publish = [p for p in to_publish if photo_id(p) not in existing]
    plan = {"source_frames": len(ids), "private_source_frames": len(faces),
            "move_edited_to_faces": [p.name for p in to_private],
            "publish": [photo_id(p) for p in to_publish],
            "missing_edits_not_recreated": sorted(ids - {photo_id(p) for p in edited} -
                {photo_id(p) for p in (batch / "Faces" / "Edited").glob("*.jpg")})}
    print(json.dumps(plan, indent=2))
    if not args.apply:
        return
    # Preserve original backups. Put private copies and existing edited portraits together.
    private = batch / "Faces"
    for identifier in sorted(faces):
        for extension in ("JPG", "RAF"):
            src = batch / "Originals" / f"{identifier}.{extension}"
            if not src.is_file():
                raise ValueError(f"Missing original: {src}")
            preserve_copy(src, private / "Originals" / src.name)
    for src in to_private:
        dst = private / "Edited" / src.name
        preserve_copy(src, dst)
        src.unlink()
    for src in sorted(batch.glob("DSCF*_AllFilmSimulations")):
        if photo_id(src) in faces:
            dst = private / src.name
            if dst.exists():
                raise ValueError(f"Private simulation folder already exists: {dst}")
            shutil.move(str(src), str(dst))
    (private / "face-review.json").write_text(json.dumps(review, ensure_ascii=False, indent=2))
    photos = sorted([export(p, photo_id(p), repo / "docs") for p in to_publish], key=lambda p: p["time"])
    groups = []
    for photo in photos:
        if not groups or (datetime.fromisoformat(photo["time"]) - datetime.fromisoformat(groups[-1][-1]["time"])).total_seconds() > 10800:
            groups.append([])
        groups[-1].append(photo)
    names = json.loads((repo / "tools" / "titles.json").read_text())
    keys = {group["key"] for group in data}
    for group in groups:
        key = datetime.fromisoformat(group[0]["time"]).strftime("%Y%m%d-%H%M")
        if key in keys:
            raise ValueError(f"Existing series key {key}; merge deliberately instead")
        meta = names.get(key, {})
        data.append({"key": key, "title": meta.get("title", f"Series {len(data) + 1:02d}"),
                     "cover": meta.get("cover"), "start": group[0]["time"], "end": group[-1]["time"], "photos": group})
        keys.add(key)
    data_file.write_text("window.SHOOTS = " + json.dumps(data, ensure_ascii=False, indent=1) + ";")
    (batch / "Processing" / "publish-manifest.json").write_text(json.dumps(plan, indent=2))


if __name__ == "__main__":
    main()
