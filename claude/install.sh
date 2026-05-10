#!/bin/bash
# Install lecture-notes slash commands into ~/.claude/commands/
# Replaces {{LECTURE_NOTES_PATH}} with the absolute path to this clone.
set -e

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CMD_SRC="$REPO_ROOT/claude/commands"
CMD_DEST="$HOME/.claude/commands"

if [ ! -d "$CMD_SRC" ]; then
    echo "Error: $CMD_SRC not found. Run from a lecture-notes clone."
    exit 1
fi

mkdir -p "$CMD_DEST"

for src in "$CMD_SRC"/*.md; do
    name="$(basename "$src")"
    dest="$CMD_DEST/$name"
    if [ -e "$dest" ]; then
        echo "Skipping $name (already exists at $dest)"
        continue
    fi
    sed "s|{{LECTURE_NOTES_PATH}}|$REPO_ROOT|g" "$src" > "$dest"
    echo "Installed: $dest"
done

echo ""
echo "Done. In Claude Code, the /lecture and /lecture-stop slash commands are now available."
