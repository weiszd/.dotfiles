#!/usr/bin/env bash
set -euo pipefail

DOTFILES_DIR="$(cd "$(dirname "$0")" && pwd)"
TIMESTAMP=$(date +%Y%m%d%H%M%S)

backup_and_link() {
    local src="$1"
    local dest="$2"

    mkdir -p "$(dirname "$dest")"

    if [ -e "$dest" ] || [ -L "$dest" ]; then
        if [ -L "$dest" ] && [ "$(readlink "$dest")" = "$src" ]; then
            echo "  skip (already linked): $dest"
            return
        fi
        mv "$dest" "${dest}.bak.${TIMESTAMP}"
        echo "  backed up: $dest -> ${dest}.bak.${TIMESTAMP}"
    fi

    ln -s "$src" "$dest"
    echo "  linked: $dest -> $src"
}

echo "Deploying dotfiles from $DOTFILES_DIR"
echo

# Config files
echo "Config files:"
backup_and_link "$DOTFILES_DIR/inputrc"    "$HOME/.inputrc"
backup_and_link "$DOTFILES_DIR/gitconfig"  "$HOME/.gitconfig"

# Midnight Commander
echo
echo "Midnight Commander:"
for f in ini mc.keymap menu hotlist panels.ini; do
    backup_and_link "$DOTFILES_DIR/config/mc/$f" "$HOME/.config/mc/$f"
done

# micro editor
echo
echo "micro editor:"
for f in settings.json bindings.json; do
    backup_and_link "$DOTFILES_DIR/config/micro/$f" "$HOME/.config/micro/$f"
done

# bin
echo
echo "Scripts:"
backup_and_link "$DOTFILES_DIR/bin/mc-wrapper.sh"      "$HOME/bin/mc-wrapper.sh"
backup_and_link "$DOTFILES_DIR/bin/herdr-fkey-fix.py"  "$HOME/bin/herdr-fkey-fix.py"

# bashrc_custom — print instructions, don't symlink
echo
echo "---"
echo "To activate bash customizations, add this line to your ~/.bashrc:"
echo
echo "  source \"$DOTFILES_DIR/bashrc_custom\""
echo
echo "Done."
