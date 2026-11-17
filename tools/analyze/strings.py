#!/usr/bin/env python3
import argparse
import re
import sys


def scan(data: bytes, minlen: int, utf16: bool):
    if utf16:
        pat = re.compile(("(?:[\\x20-\\x7e]\\x00){%d,}" % minlen).encode())
    else:
        pat = re.compile(("[\\x20-\\x7e]{%d,}" % minlen).encode())
    for m in pat.finditer(data):
        raw = m.group()
        s = raw.decode("utf-16-le", "replace") if utf16 else raw.decode("latin-1")
        yield m.start(), s


def main():
    ap = argparse.ArgumentParser(description="Extract ASCII or UTF-16LE strings with file offsets.")
    ap.add_argument("path")
    ap.add_argument("minlen", nargs="?", type=int, default=4)
    ap.add_argument("--utf16", action="store_true", help="scan UTF-16LE instead of ASCII")
    ap.add_argument("-o", "--output", help="write to file instead of stdout")
    args = ap.parse_args()
    data = open(args.path, "rb").read()
    out = open(args.output, "w", encoding="utf-8") if args.output else sys.stdout
    n = 0
    for off, s in scan(data, args.minlen, args.utf16):
        out.write("%08x  %s\n" % (off, s))
        n += 1
    if args.output:
        out.close()
    print(f"{n} strings", file=sys.stderr)


if __name__ == "__main__":
    main()
