#!/bin/bash
launchctl bootout gui/$(id -u)/com.frames.sd-import 2>/dev/null
rm -f "$HOME/Library/LaunchAgents/com.frames.sd-import.plist" "$HOME/.local/bin/sd-import.sh"
echo "Removed (imported photos are kept)."
