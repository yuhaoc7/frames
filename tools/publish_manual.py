"""Replace one gallery series with the exact Keep set from Frames Review.

Uses already-cropped exported JPEGs and original image metadata. Dry-run by default;
--apply writes only this series and its web assets. Never classifies or pushes.
"""
import argparse
from datetime import datetime
import json
from pathlib import Path
import re
from PIL import Image, ImageOps


def frame_id(row):
    match = re.match(r'^(DSCF\d+)(?:_|\.|$)', Path(row['original']).name)
    if not match:
        raise ValueError('Unsupported gallery identifier: ' + row['original'])
    return match[1]


def read_gallery(path):
    text = path.read_text()
    prefix = 'window.SHOOTS = '
    if not text.startswith(prefix):
        raise ValueError('Unknown gallery format')
    return json.loads(text[len(prefix):].rstrip().rstrip(';'))


def prepare(manifest_path, gallery, key):
    manifest = json.loads(manifest_path.read_text())
    rows = manifest['photos']
    if len({r['id'] for r in rows}) != len(rows):
        raise ValueError('Duplicate manual IDs')
    if any(r['status'] not in {'keep','face','delete','pending'} for r in rows):
        raise ValueError('Unknown classification')
    selected = [r for r in rows if r['status'] == 'keep']
    if not selected:
        raise ValueError('No Keep photos; refusing to empty a series')
    ids = [frame_id(r) for r in rows]
    if len(set(ids)) != len(ids):
        raise ValueError('Duplicate frame numbers in manual review')
    exports = {r['id']:r for r in manifest['exported'] if r['status'] == 'keep'}
    if set(exports) != {r['id'] for r in selected}:
        raise ValueError('Keep set does not match exports')
    matching = [g for g in gallery if g['key'] == key]
    if len(matching) != 1:
        raise ValueError('Select exactly one existing series')
    old = matching[0]
    if not {p['id'] for p in old['photos']} <= set(ids):
        raise ValueError('Target series contains frames outside this review')
    other_ids = {p['id'] for g in gallery if g['key'] != key for p in g['photos']}
    if other_ids & set(ids):
        raise ValueError('Frame numbers conflict with another series')
    keep_dir = (manifest_path.parent / 'Keep').resolve()
    prepared = []
    for row in selected:
        export = exports[row['id']]
        path = Path(export['file']).resolve(strict=True)
        if path.parent != keep_dir or export['crop'] != row['crop']:
            raise ValueError('Export path or crop does not match manual review')
        with Image.open(row['path']) as source:
            e = source.getexif()
            x = e.get_ifd(0x8769)
            captured = datetime.strptime(x.get(36867) or e.get(306), '%Y:%m:%d %H:%M:%S')
            width,height = source.size
            if e.get(274,1) in [5,6,7,8]:
                width,height = height,width
            if row['crop']:
                c = row['crop']
                expected = (round((c['x']+c['w'])*width)-round(c['x']*width),
                            round((c['y']+c['h'])*height)-round(c['y']*height))
            else:
                expected = (width,height)
            shutter = x.get(33434)
            shutter = f'1/{round(1/float(shutter))}' if shutter and shutter < 1 else f'{shutter}s'
            metadata = {'id':frame_id(row),'time':captured.isoformat(),'model':e.get(272,''),
                        'exif':f'{float(x[37386]):g}mm · ƒ/{float(x[33437]):g} · {shutter} · ISO {int(x.get(34855) or 0)}'}
        with Image.open(path) as im:
            im.load()
            if im.size != expected:
                raise ValueError(f'Crop dimensions differ for {path.name}: {im.size} vs {expected}')
            metadata.update(w=im.width,h=im.height)
        prepared.append((path,metadata))
    prepared.sort(key=lambda p:p[1]['time'])
    return old, prepared


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest',type=Path)
    parser.add_argument('--series-key',required=True)
    parser.add_argument('--cover')
    parser.add_argument('--apply',action='store_true')
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    data_path = repo/'docs/data.js'
    gallery = read_gallery(data_path)
    old, prepared = prepare(args.manifest.resolve(), gallery, args.series_key)
    keep = {metadata['id'] for _,metadata in prepared}
    cover = args.cover or (old['cover'] if old['cover'] in keep else prepared[-1][1]['id'])
    if cover not in keep:
        raise ValueError('Cover is not in Keep')
    remove = {p['id'] for p in old['photos']} - keep
    plan = {'series':old['title'],'publish':sorted(keep),'remove_from_series':sorted(remove),'cover':cover}
    print(json.dumps(plan,indent=2))
    if not args.apply:
        return
    for path,metadata in prepared:
        with Image.open(path) as source:
            im = ImageOps.exif_transpose(source).convert('RGB')
            icc = source.info.get('icc_profile')
            kwargs = {'icc_profile':icc} if icc else {}
            for size,suffix in [(2400,'l'),(900,'s')]:
                web = im.copy()
                web.thumbnail((size,size),Image.Resampling.LANCZOS)
                dest = repo/'docs/img'/f"{metadata['id']}_{suffix}.jpg"
                web.save(dest,quality=86,progressive=True,**kwargs)
            colors = im.resize((64,64)).quantize(5).convert('RGB').getcolors()
            metadata['palette'] = ['#%02x%02x%02x'%c for _,c in sorted(colors,reverse=True)]
    replacement = dict(old,cover=cover,start=prepared[0][1]['time'],end=prepared[-1][1]['time'],
                       photos=[metadata for _,metadata in prepared])
    gallery = [replacement if g['key']==args.series_key else g for g in gallery]
    data_path.write_text('window.SHOOTS = '+json.dumps(gallery,ensure_ascii=False,indent=1)+';')
    # Remove obsolete web assets as well as index entries. Original files are untouched.
    referenced = {p['id'] for g in gallery for p in g['photos']}
    for identifier in remove-referenced:
        for suffix in ['l','s']:
            path = repo/'docs/img'/f'{identifier}_{suffix}.jpg'
            if path.exists():path.unlink()
    titles_path = repo/'tools/titles.json'
    titles = json.loads(titles_path.read_text())
    titles.setdefault(args.series_key,{})['cover'] = cover
    titles_path.write_text(json.dumps(titles,ensure_ascii=False,indent=1)+'\n')


if __name__ == '__main__':
    main()
