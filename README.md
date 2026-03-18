# .dotfiles

Portable terminal customizations: bash settings, editor configs, and helper scripts.

## Contents

- **bashrc_custom** — sourceable bash customizations (history, editor, aliases)
- **inputrc** — readline config (history search, home/end keys)
- **gitconfig** — git user identity and credential helper
- **bin/mc-wrapper.sh** — Midnight Commander directory-follow wrapper
- **config/mc/** — Midnight Commander settings, keymap, menu, hotlist, panels
- **config/micro/** — micro editor settings and keybindings

## Install

```bash
./deploy.sh
```

This creates symlinks from your home directory to the repo files. Existing files are backed up with a `.bak.<timestamp>` suffix.

After running, add this line to your `~/.bashrc`:

```bash
source ~/github/.dotfiles/bashrc_custom
```
