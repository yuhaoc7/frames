#!/bin/bash
# Copy new photos/videos from any mounted camera card (a volume with DCIM/) into a fresh folder.
# A file counts as "already imported" by name+size, recorded in $DEST/.imported.
# (Not mtime: FAT cards store local time, so every mtime shifts an hour when DST changes.)
DEST="${DEST:-$HOME/Pictures/SD Imports}"
DRY=${DRY:-0}
mkdir -p "$DEST"; LOG="$DEST/.import.log"; SEEN="$DEST/.imported"; touch "$SEEN"
# migrate old name|size|mtime records
grep -q '|.*|' "$SEEN" && cut -d'|' -f1,2 "$SEEN" | sort -u > "$SEEN.tmp" && mv "$SEEN.tmp" "$SEEN"

for vol in /Volumes/*; do
  [ -d "$vol/DCIM" ] || continue
  dir="$DEST/$(date +%Y-%m-%d_%H%M)"; n=0
  while IFS= read -r -d '' f; do
    key="$(basename "$f")|$(stat -f '%z' "$f")"
    grep -qxF "$key" "$SEEN" && continue
    n=$((n+1))
    [ "$DRY" = 1 ] && continue
    mkdir -p "$dir" && cp -p "$f" "$dir/" && echo "$key" >> "$SEEN"
  done < <(find "$vol/DCIM" -type f ! -name '._*' \( -iname '*.jpg' -o -iname '*.raf' -o -iname '*.heic' -o -iname '*.mov' -o -iname '*.mp4' -o -iname '*.dng' -o -iname '*.arw' -o -iname '*.cr3' -o -iname '*.nef' \) -print0)
  [ "$DRY" = 1 ] && { echo "$vol: $n new files (dry run)"; continue; }
  echo "$(date '+%F %T') $vol: $n new" >> "$LOG"
  if [ $n -gt 0 ]; then
    osascript -e "display notification \"$n 个新文件 → $(basename "$dir")\" with title \"SD 导入完成\""
    open "$dir"
  fi
done
