# .dotfiles

Portable terminal customizations: bash settings, editor configs, and helper scripts.

## Contents

- **bashrc_custom** — sourceable bash customizations (history, editor, aliases)
- **inputrc** — readline config (history search, home/end keys)
- **gitconfig** — git user identity and credential helper
- **bin/mc-wrapper.sh** — Midnight Commander directory-follow wrapper
- **bin/herdr-fkey-fix.py** — makes F1–F4 work inside [herdr](https://herdr.dev) on Windows Terminal (WSL)
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

## Function keys in herdr (Windows Terminal + WSL)

Inside [herdr](https://herdr.dev), F1/F2/F4 are silently dropped while F3 and
F5–F12 work — which breaks F4 (edit) in Midnight Commander. herdr negotiates
keyboard enhancement with the outer terminal, after which Windows Terminal
encodes F1–F4 as `CSI P/Q/R/S`; those collide with real CSI control functions
(`ESC [ P` is delete-character, `ESC [ S` is scroll-up) and herdr's input parser
swallows them. `ESC [ R` (F3) happens to survive.

`bin/herdr-fkey-fix.py` binds the affected keys in Windows Terminal to
`sendInput` actions emitting the VT220 forms (`ESC [ 11~`–`ESC [ 14~`). Windows
Terminal resolves keybindings *before* protocol encoding, so those literal bytes
go out regardless of keyboard mode; herdr parses them and normalizes them back to
`ESC O P`–`ESC O S`, which is what terminfo `kf1`–`kf4` specify.

```bash
./bin/herdr-fkey-fix.py --list      # find every Windows Terminal settings.json
./bin/herdr-fkey-fix.py --dry-run   # preview
./bin/herdr-fkey-fix.py             # apply (f1,f2,f4)
./bin/herdr-fkey-fix.py --revert    # undo
```

Idempotent, backs up each file, and validates the JSON before writing. Windows
Terminal settings are shared by every WSL distro on a machine, so this is a
per-Windows-machine fix, not a per-distro one.

Upstream bug: herdr issues
[#818](https://github.com/herdrdev/herdr/issues/818),
[#1809](https://github.com/herdrdev/herdr/issues/1809),
[#2705](https://github.com/herdrdev/herdr/issues/2705); fix PRs
[#2378](https://github.com/herdrdev/herdr/pull/2378) and
[#2578](https://github.com/herdrdev/herdr/pull/2578) were unmerged as of herdr
0.8.2. Run `--revert` once they ship.
