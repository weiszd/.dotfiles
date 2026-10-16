# .dotfiles

Portable terminal customizations: bash settings, editor configs, and helper scripts.

## Contents

- **bashrc_custom** — sourceable bash customizations (history, editor, aliases)
- **inputrc** — readline config (history search, home/end keys)
- **gitconfig** — git user identity and credential helper
- **bin/mc-wrapper.sh** — Midnight Commander directory-follow wrapper
- **bin/herdr-fkey-fix.py** — makes F1–F4 work inside [herdr](https://herdr.dev) on Windows Terminal (WSL); obsolete for herdr ≥ 0.9.4
- **bin/herdr-machines** — curses table editor for herdr's saved SSH machine list (reorder, rename, enable/disable, duplicate)
- **bin/herdr-sidebar** — switch herdr sidebar layout variants and hot-reload
- **config/herdr/** — herdr `config.toml` plus the sidebar layout variants it is built from
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

## herdr sidebar layout

`config/herdr/config.toml` is generated: `variants/base.toml` (theme, keys, general
UI) concatenated with one sidebar variant. Switch live with

```bash
herdr-sidebar bb    # current favourite: colored host + bold workspace / chat title / dim agent+state
herdr-sidebar b     # same, plain first line
herdr-sidebar b0    # b without blank-row gaps
herdr-sidebar a     # hostname header line, then location, then chat title
herdr-sidebar c     # chat title first, attention-priority order
```

The agent rows color the `machine` token per host (Local red, VH 1 blue,
VH 2 sky, PVE orange, NASA mauve, NOTS green, TACC yellow, H10 teal) by
`starts_with` rules on the saved machine label. Edit a variant, rerun the
switcher; it validates with `herdr config check` and restores the previous
config on failure. On native Windows there is no symlink deploy: copy
`config/herdr/config.toml` to `%APPDATA%\herdr\config.toml` by hand.

## herdr machine list editor

```bash
herdr-machines          # Up/Down move, K/J reorder, Enter/F2 rename, Space enable,
                        # a/Ins add, c duplicate, d/Del delete, r reachability, w save, q quit
```

Edits `~/.local/state/herdr/client/endpoints.json` per user with a timestamped
backup on each save. `HERDR_ENDPOINTS=<path>` overrides the location; Windows
needs `pip install windows-curses`. Also installed cluster-wide on Voltron at
`/gpfs0/apps/common/bin/herdr-machines`.

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
