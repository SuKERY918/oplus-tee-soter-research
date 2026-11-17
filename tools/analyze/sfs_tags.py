#!/usr/bin/env python3
import argparse
import os
import re

PRINTABLE = re.compile(rb"[\x20-\x7e]{3,}")


def head_strings(data, start=0x20, end=0x120, want=2):
    parts = [m.group().decode("latin-1") for m in PRINTABLE.finditer(data[:end], start)]
    return parts[:want]


def main():
    ap = argparse.ArgumentParser(
        description="Best-effort dump of KeyMint/keystore SFS slot files (name + logical tag)."
    )
    ap.add_argument("dir", help="path to a persist SFS slot directory")
    ap.add_argument("--offset", type=lambda s: int(s, 0), default=0x20, help="start of header text")
    args = ap.parse_args()
    if not os.path.isdir(args.dir):
        raise SystemExit(f"not a directory: {args.dir}")
    for fn in sorted(os.listdir(args.dir)):
        if fn.endswith(".bak") or fn == "vTable":
            continue
        fp = os.path.join(args.dir, fn)
        if not os.path.isfile(fp):
            continue
        data = open(fp, "rb").read()
        parts = head_strings(data, args.offset)
        name = parts[0] if parts else "-"
        tag = parts[1] if len(parts) > 1 else "-"
        print("%-44s %6d  name=%-40s tag=%s" % (fn, len(data), name, tag))


if __name__ == "__main__":
    main()
