#!/usr/bin/env python3
import argparse
import struct
import sys


def main():
    ap = argparse.ArgumentParser(
        description="Dump fixed-size command tables of a vendor HAL (pairs of u64 per entry)."
    )
    ap.add_argument("path")
    ap.add_argument(
        "--table",
        action="append",
        default=None,
        metavar="OFFSET:COUNT",
        help="table file offset and entry count, repeatable (default: 0x200A8:26 0x20248:25)",
    )
    args = ap.parse_args()
    data = open(args.path, "rb").read()
    tables = args.table or ["0x200A8:26", "0x20248:25"]
    for spec in tables:
        base_s, count_s = spec.split(":")
        base, count = int(base_s, 0), int(count_s, 0)
        print(f"# table @0x{base:x} entries={count}")
        for i in range(count):
            off = base + i * 16
            if off + 16 > len(data):
                print(f"  [{i:2d}] 0x{off:x} <out of file>")
                break
            a, b = struct.unpack_from("<QQ", data, off)
            lo, hi = b & 0xFFFFFFFF, b >> 32
            print(
                "  [%2d] 0x%06x  q0=0x%-10x q1=0x%-18x  q1.lo=0x%x q1.hi=0x%x"
                % (i, off, a, b, lo, hi)
            )


if __name__ == "__main__":
    main()
