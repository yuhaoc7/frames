# frames

Photo portfolio built from an SD card. `tools/build.py` groups frames into series by capture-time gaps (>3h), drops any frame with a face (macOS Vision, `tools/faces.swift`), and exports web images + `docs/data.js`. Series titles/covers live in `tools/titles.json`.

```bash
python3 tools/build.py "/Volumes/NO NAME/DCIM"
```

Served by GitHub Pages from `/docs`.
