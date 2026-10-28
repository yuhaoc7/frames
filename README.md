# frames

Photo portfolio built from an SD card. `tools/build.py` groups frames into series by capture-time gaps (>3h), drops any frame with a face (macOS Vision, `tools/faces.swift`), and exports web images + `docs/data.js`. Series titles/covers live in `tools/titles.json`.

```bash
python3 tools/build.py "/Volumes/NO NAME/DCIM"
```

Served by GitHub Pages from `/docs`.

For an edited batch, use `tools/detect_faces.swift` on both `Originals/*.JPG`
and the available `Edited/*.jpg`, then visually review every frame. Store the
complete classification locally as `Processing/face-review.json`; do not reuse
the old `faces.txt` cache for a new batch. `tools/import_edited.py` validates the
review, keeps original backups, separates portraits into the batch's local
`Faces/` folder, and appends only reviewed edits to the existing gallery:

```bash
python3 tools/import_edited.py /path/to/batch --review /path/to/batch/Processing/face-review.json
# Inspect the plan, then add --apply to organize local photos and export web assets.
```

Exports retain the existing 2400/900 px sizes and quality 86. Full-resolution
photos, RAW files, face classifications and film comparison sheets stay outside
the repository. Commit and push the reviewed `docs/` and tooling changes to
`origin/main` to publish. Series dates follow the camera's EXIF clock.
