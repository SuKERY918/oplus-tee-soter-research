#!/usr/bin/env python3
import argparse
import os
import sys

DEFAULT_PATTERNS = {
    "ETQS": bytes.fromhex("45 54 51 53"),
    "FTQS": bytes.fromhex("46 54 51 53"),
    "SOTER": b"SOTER",
    "soter": b"soter",
    "ATTK": b"ATTK",
    "attk": b"attk",
    "RPMB": b"RPMB",
}


def scan_file(path, pats, limit=40):
    try:
        data = open(path, "rb").read()
    except OSError as e:
        print("ERR", path, e)
        return
    hits = []
    for name, pat in pats.items():
        start = 0
        while len(hits) <= 200:
            i = data.find(pat, start)
            if i < 0:
                break
            hits.append((name, i))
            start = i + 1
    if not hits:
        return
    print(f"{path}  {len(data)} bytes")
    for name, off in hits[:limit]:
        print(f"    {name:6s} 0x{off:x}")
    if len(hits) > limit:
        print(f"    ... {len(hits)} hits total")


def main():
    ap = argparse.ArgumentParser(description="Scan files/directories for SOTER / RPMB related magics.")
    ap.add_argument("root")
    ap.add_argument("--add", action="append", default=[], metavar="NAME=HEX", help="add a pattern")
    args = ap.parse_args()
    pats = dict(DEFAULT_PATTERNS)
    for spec in args.add:
        name, hexs = spec.split("=", 1)
        pats[name] = bytes.fromhex(hexs.replace(" ", ""))
    if os.path.isfile(args.root):
        scan_file(args.root, pats)
        return
    for dirpath, _dirs, files in os.walk(args.root):
        for fn in files:
            scan_file(os.path.join(dirpath, fn), pats)


if __name__ == "__main__":
    main()
