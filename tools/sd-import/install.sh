#!/bin/bash
# Install sd-import as a launchd agent that runs every time a volume mounts.
set -e
mkdir -p "$HOME/.local/bin" "$HOME/Pictures/SD Imports"
cp "$(dirname "$0")/sd-import.sh" "$HOME/.local/bin/sd-import.sh"; chmod +x "$HOME/.local/bin/sd-import.sh"
P="$HOME/Library/LaunchAgents/com.frames.sd-import.plist"
cat > "$P" <<PL
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.frames.sd-import</string>
  <key>ProgramArguments</key><array><string>$HOME/.local/bin/sd-import.sh</string></array>
  <key>StartOnMount</key><true/>
  <key>StandardErrorPath</key><string>$HOME/Pictures/SD Imports/.import.err</string>
</dict></plist>
PL
launchctl bootout gui/$(id -u)/com.frames.sd-import 2>/dev/null || true
launchctl bootstrap gui/$(id -u) "$P"
echo "Installed. Imports go to ~/Pictures/SD Imports"
