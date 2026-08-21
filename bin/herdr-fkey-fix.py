#!/usr/bin/env python3
"""
herdr-fkey-fix.py - make F1-F4 survive the trip through herdr on Windows Terminal.

Background
----------
herdr's client negotiates keyboard enhancement with the outer terminal. Once that
is active, Windows Terminal encodes F1-F4 as CSI P/Q/R/S ("ESC [ P" and friends),
which collide with real CSI control functions (ESC [ P is delete-character,
ESC [ S is scroll-up). herdr's input parser swallows the colliding ones, so those
keys never reach the pane. Which of the four get lost varies by terminal but is
stable on a given one; on Windows Terminal it is F1, F2 and F4, while F3 survives.

Upstream: herdr issues #818 / #1809 / #2705. Fix PRs #2378 / #2578 were still
unmerged as of herdr 0.8.2 - once they ship, run this with --revert.

The workaround
--------------
Bind the affected keys in Windows Terminal to sendInput actions emitting the
VT220 forms (ESC [ 11~ .. ESC [ 14~). Windows Terminal resolves keybindings
*before* protocol encoding, so these literal bytes go out regardless of which
keyboard mode is active. herdr parses the VT220 forms correctly and normalizes
them back to ESC O P .. ESC O S for the pane, which is exactly what terminfo
kf1..kf4 specify - so ncurses apps such as mc see ordinary function keys.

Scope
-----
Windows Terminal settings live on the Windows side, shared by every WSL distro on
that machine. Running this in a second distro on the same machine is a no-op.
It is other *Windows machines* that need it.

Usage
-----
  ./herdr-fkey-fix.py --dry-run          # show what would change
  ./herdr-fkey-fix.py                    # apply (default keys: f1,f2,f4)
  ./herdr-fkey-fix.py --keys f1,f2,f3,f4 # if F3 is dropped on this machine too
  ./herdr-fkey-fix.py --revert           # remove the entries again
  ./herdr-fkey-fix.py --file /path/to/settings.json    # explicit target
"""

import argparse
import datetime
import glob
import json
import os
import shutil
import sys

# Written into the JSON as text: backslash + u001b, six characters. Built with
# chr(92) so no literal control byte can end up in this source file.
ESC_JSON = chr(92) + "u001b"

SEQ = {"f1": "[11~", "f2": "[12~", "f3": "[13~", "f4": "[14~"}
ID_FOR = {k: "User.herdrF" + k[1:] for k in SEQ}
DEFAULT_KEYS = ["f1", "f2", "f4"]

PACKAGES = [
    "Microsoft.WindowsTerminal_8wekyb3d8bbwe",
    "Microsoft.WindowsTerminalPreview_8wekyb3d8bbwe",
    "Microsoft.WindowsTerminalCanary_8wekyb3d8bbwe",
]


# --------------------------------------------------------------------------
# locating settings.json
# --------------------------------------------------------------------------

def windows_roots():
    """Candidate Windows drive mount points, as seen from WSL."""
    roots = []
    try:
        with open("/proc/mounts", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                parts = line.split()
                if len(parts) >= 3 and parts[2] in ("drvfs", "9p", "virtiofs"):
                    mp = parts[1].replace("\\040", " ")
                    if os.path.isdir(os.path.join(mp, "Users")):
                        roots.append(mp)
    except OSError:
        pass
    for guess in ("/mnt/c", "/c", "/media/c"):
        if os.path.isdir(os.path.join(guess, "Users")) and guess not in roots:
            roots.append(guess)
    return roots


def find_settings():
    """Every Windows Terminal settings.json we can see, deduplicated."""
    found = []
    for root in windows_roots():
        for userdir in sorted(glob.glob(os.path.join(root, "Users", "*"))):
            base = os.path.basename(userdir)
            if base.lower() in ("public", "default", "default user", "all users"):
                continue
            local = os.path.join(userdir, "AppData", "Local")
            for pkg in PACKAGES:
                p = os.path.join(local, "Packages", pkg, "LocalState", "settings.json")
                if os.path.isfile(p):
                    found.append(p)
            # unpackaged / portable install
            p = os.path.join(local, "Microsoft", "Windows Terminal", "settings.json")
            if os.path.isfile(p):
                found.append(p)
    seen, out = set(), []
    for p in found:
        rp = os.path.realpath(p)
        if rp not in seen:
            seen.add(rp)
            out.append(p)
    return out


# --------------------------------------------------------------------------
# JSONC handling
# --------------------------------------------------------------------------

def scrub_jsonc(text):
    """Strip comments and trailing commas so json.loads accepts the text.

    Walks character by character and tracks string state, so that "//" inside a
    URL or a "C:\\path" never gets mistaken for a comment.
    """
    out = []
    i, n = 0, len(text)
    in_str = False
    while i < n:
        c = text[i]
        if in_str:
            out.append(c)
            if c == chr(92) and i + 1 < n:      # backslash escape
                out.append(text[i + 1])
                i += 2
                continue
            if c == '"':
                in_str = False
            i += 1
            continue
        if c == '"':
            in_str = True
            out.append(c)
            i += 1
            continue
        if c == "/" and i + 1 < n and text[i + 1] == "/":
            while i < n and text[i] not in ("\n", "\r"):
                i += 1
            continue
        if c == "/" and i + 1 < n and text[i + 1] == "*":
            i += 2
            while i + 1 < n and not (text[i] == "*" and text[i + 1] == "/"):
                i += 1
            i += 2
            continue
        out.append(c)
        i += 1

    # second pass: drop commas that sit directly before a closing bracket
    s = "".join(out)
    res = []
    i, n, in_str = 0, len(s), False
    while i < n:
        c = s[i]
        if in_str:
            res.append(c)
            if c == chr(92) and i + 1 < n:
                res.append(s[i + 1])
                i += 2
                continue
            if c == '"':
                in_str = False
            i += 1
            continue
        if c == '"':
            in_str = True
            res.append(c)
            i += 1
            continue
        if c == ",":
            j = i + 1
            while j < n and s[j] in " \t\r\n":
                j += 1
            if j < n and s[j] in "]}":
                i += 1          # skip this comma
                continue
        res.append(c)
        i += 1
    return "".join(res)


def parse_jsonc(text):
    return json.loads(scrub_jsonc(text))


def newline_of(text):
    return "\r\n" if text.count("\r\n") > text.count("\n") - text.count("\r\n") else "\n"


def skip_insignificant(text, i):
    """Advance past whitespace and comments."""
    n = len(text)
    while i < n:
        if text[i] in " \t\r\n":
            i += 1
        elif text[i] == "/" and i + 1 < n and text[i + 1] == "/":
            while i < n and text[i] not in ("\n", "\r"):
                i += 1
        elif text[i] == "/" and i + 1 < n and text[i + 1] == "*":
            i += 2
            while i + 1 < n and not (text[i] == "*" and text[i + 1] == "/"):
                i += 1
            i += 2
        else:
            break
    return i


def find_key_position(text, key):
    """Index just past the '[' opening the array named `key`, or None."""
    needle = '"' + key + '"'
    i, n = 0, len(text)
    in_str = False
    while i < n:
        c = text[i]
        if in_str:
            if c == chr(92):
                i += 2
                continue
            if c == '"':
                in_str = False
            i += 1
            continue
        if c == '"':
            if text.startswith(needle, i):
                j = skip_insignificant(text, i + len(needle))
                if j < n and text[j] == ":":
                    j = skip_insignificant(text, j + 1)
                    if j < n and text[j] == "[":
                        return j + 1
            in_str = True
            i += 1
            continue
        i += 1
    return None


def array_is_empty(text, after_bracket):
    j = skip_insignificant(text, after_bracket)
    return j < len(text) and text[j] == "]"


def match_object(text, idx):
    """Given an index inside an object, return (start, end) of its braces."""
    # scan backward for the opening brace at depth 0
    depth, i = 0, idx
    while i >= 0:
        c = text[i]
        if c == "}":
            depth += 1
        elif c == "{":
            if depth == 0:
                start = i
                break
            depth -= 1
        i -= 1
    else:
        return None
    # scan forward for its match
    depth, i, n = 0, start, len(text)
    in_str = False
    while i < n:
        c = text[i]
        if in_str:
            if c == chr(92):
                i += 2
                continue
            if c == '"':
                in_str = False
            i += 1
            continue
        if c == '"':
            in_str = True
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return (start, i + 1)
        i += 1
    return None


# --------------------------------------------------------------------------
# building and applying the patch
# --------------------------------------------------------------------------

def action_entry(key, nl, indent="        "):
    i2 = indent + "    "
    i3 = i2 + "    "
    return (
        nl + indent + "{" +
        nl + i2 + '"command":' +
        nl + i2 + "{" +
        nl + i3 + '"action": "sendInput",' +
        nl + i3 + '"input": "' + ESC_JSON + SEQ[key] + '"' +
        nl + i2 + "}," +
        nl + i2 + '"id": "' + ID_FOR[key] + '"' +
        nl + indent + "}"
    )


def binding_entry(key, nl, indent="        "):
    i2 = indent + "    "
    return (
        nl + indent + "{" +
        nl + i2 + '"id": "' + ID_FOR[key] + '",' +
        nl + i2 + '"keys": "' + key + '"' +
        nl + indent + "}"
    )


def ensure_array(text, name, nl):
    """Make sure a top-level array `name` exists; return (text, pos_after_open)."""
    pos = find_key_position(text, name)
    if pos is not None:
        return text, pos
    brace = text.index("{")
    block = nl + '    "' + name + '":' + nl + "    [" + nl + "    ],"
    text = text[:brace + 1] + block + text[brace + 1:]
    return text, find_key_position(text, name)


def patch_text(text, keys):
    nl = newline_of(text)
    for name, builder in (("actions", action_entry), ("keybindings", binding_entry)):
        text, pos = ensure_array(text, name, nl)
        empty = array_is_empty(text, pos)
        chunks = [builder(k, nl) for k in keys]
        block = ",".join(chunks) if empty else ",".join(chunks) + ","
        text = text[:pos] + block + text[pos:]
    return text


def remove_our_entries(text):
    """Delete every object carrying one of our ids, plus its trailing comma."""
    removed = 0
    for ident in sorted(set(ID_FOR.values())):
        needle = '"' + ident + '"'
        while True:
            idx = text.find(needle)
            if idx == -1:
                break
            span = match_object(text, idx)
            if span is None:
                break
            start, end = span
            j = skip_insignificant(text, end)
            if j < len(text) and text[j] == ",":
                end = j + 1
            else:
                # last element: also swallow the comma before it, if any
                k = start - 1
                while k >= 0 and text[k] in " \t\r\n":
                    k -= 1
                if k >= 0 and text[k] == ",":
                    start = k
            text = text[:start] + text[end:]
            removed += 1
    return text, removed


def report(parsed, keys):
    ids = {a.get("id"): a.get("command") for a in parsed.get("actions", [])
           if isinstance(a, dict)}
    lines = []
    for kb in parsed.get("keybindings", []):
        if not isinstance(kb, dict):
            continue
        if str(kb.get("id", "")) in set(ID_FOR.values()):
            cmd = ids.get(kb["id"]) or {}
            val = cmd.get("input", "") if isinstance(cmd, dict) else ""
            hexs = " ".join("%02x" % b for b in val.encode())
            lines.append("      %-3s -> %s" % (kb.get("keys"), hexs))
    return lines


def conflicting_keys(parsed, keys):
    """Existing user bindings on the keys we want, that are not ours."""
    out = []
    ours = set(ID_FOR.values())
    for kb in parsed.get("keybindings", []):
        if isinstance(kb, dict) and str(kb.get("keys", "")).lower() in keys:
            if str(kb.get("id", "")) not in ours:
                out.append(str(kb.get("keys")).lower())
    for a in parsed.get("actions", []):
        if isinstance(a, dict) and str(a.get("keys", "")).lower() in keys:
            if str(a.get("id", "")) not in ours:
                out.append(str(a.get("keys")).lower())
    return sorted(set(out))


def process(path, keys, dry, revert, force, stamp):
    print("=" * 72)
    print(path)
    try:
        raw_bytes = open(path, "rb").read()
    except OSError as e:
        print("  cannot read:", e)
        return False
    bom = raw_bytes.startswith(b"\xef\xbb\xbf")
    text = raw_bytes.decode("utf-8-sig")

    try:
        before = parse_jsonc(text)
    except Exception as e:
        print("  current file is not parseable, refusing to touch it:", e)
        return False

    already = any(i in text for i in ID_FOR.values())

    if revert:
        if not already:
            print("  nothing of ours present, skipped")
            return True
        new, n = remove_our_entries(text)
        print("  removing %d entr%s" % (n, "y" if n == 1 else "ies"))
    else:
        if already:
            print("  already patched:")
            for line in report(before, keys):
                print(line)
            return True
        clash = conflicting_keys(before, keys)
        if clash and not force:
            print("  existing bindings on %s - skipped (use --force to override)"
                  % ", ".join(clash))
            return False
        new = patch_text(text, keys)

    try:
        parsed = parse_jsonc(new)
    except Exception as e:
        print("  !! result would be invalid JSON, nothing written:", e)
        return False

    if dry:
        print("  dry run - would write. Resulting bindings:")
        for line in report(parsed, keys) or ["      (none)"]:
            print(line)
        return True

    bak = path + ".bak-fkeys-" + stamp
    shutil.copy2(path, bak)
    data = new.encode("utf-8")
    if bom:
        data = b"\xef\xbb\xbf" + data
    tmp = path + ".tmp-fkeys"
    with open(tmp, "wb") as fh:
        fh.write(data)
    os.replace(tmp, path)

    check = parse_jsonc(open(path, "rb").read().decode("utf-8-sig"))
    print("  backup:", os.path.basename(bak))
    print("  written OK. Bindings now in effect:")
    for line in report(check, keys) or ["      (none - reverted)"]:
        print(line)
    return True


def main():
    ap = argparse.ArgumentParser(
        description="Remap F1-F4 in Windows Terminal so they survive herdr.")
    ap.add_argument("--keys", default=",".join(DEFAULT_KEYS),
                    help="comma-separated subset of f1,f2,f3,f4 (default: %(default)s)")
    ap.add_argument("--file", action="append", default=[],
                    help="explicit settings.json (repeatable); skips autodiscovery")
    ap.add_argument("--dry-run", action="store_true", help="show changes only")
    ap.add_argument("--revert", action="store_true",
                    help="remove our entries (an actions/keybindings array that "
                         "this script had to create is left in place, empty; "
                         "Windows Terminal treats that as absent)")
    ap.add_argument("--force", action="store_true",
                    help="patch even if those keys are already bound")
    ap.add_argument("--list", action="store_true",
                    help="just list the settings files found")
    args = ap.parse_args()

    keys = [k.strip().lower() for k in args.keys.split(",") if k.strip()]
    bad = [k for k in keys if k not in SEQ]
    if bad:
        sys.exit("unknown key(s): %s (choose from f1,f2,f3,f4)" % ", ".join(bad))
    if not keys and not args.revert:
        sys.exit("no keys selected")

    targets = args.file or find_settings()
    if not targets:
        sys.exit("no Windows Terminal settings.json found. Is this WSL with the "
                 "Windows drive mounted? Pass --file to point at one explicitly.")

    if args.list:
        for p in targets:
            print(p)
        return

    print("Windows Terminal settings files: %d" % len(targets))
    print("keys: %s   mode: %s"
          % (",".join(keys), "revert" if args.revert else
             ("dry-run" if args.dry_run else "apply")))
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    ok = all(process(p, keys, args.dry_run, args.revert, args.force, stamp)
             for p in targets)
    print("=" * 72)
    if not args.dry_run and not args.revert and ok:
        print("Done. Windows Terminal reloads settings.json live; open a herdr pane,")
        print("run 'cat -v' and press F1-F4 - you should see ^[OP ^[OQ ^[OR ^[OS.")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
