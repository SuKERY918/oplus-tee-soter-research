#!/usr/bin/env python3
import argparse
import struct
import sys

MOVN32 = 0x12800000
MOVN64 = 0x92800000
MOVZ32 = 0x52800000
MOVZ64 = 0xD2800000
MASK = 0x7F800000
TARGET = 0xFFFFFFEC


def decode(insn):
    op = insn & MASK
    imm16 = (insn >> 5) & 0xFFFF
    hw = (insn >> 21) & 3
    shift = 16 * hw
    if op in (MOVN32, MOVN64):
        val = (~(imm16 << shift)) & 0xFFFFFFFF
        return val, "MOVN"
    if op in (MOVZ32, MOVZ64):
        val = (imm16 << shift) & 0xFFFFFFFF
        return val, "MOVZ"
    return None, None


def main():
    ap = argparse.ArgumentParser(
        description="Scan an AArch64 binary for the -20 literal (MOVN/MOVZ Wn,#0xFFFFFFEC)."
    )
    ap.add_argument("path")
    ap.add_argument("--value", default="0xffffffec", help="target 32-bit value (default: -20)")
    args = ap.parse_args()
    target = int(args.value, 0) & 0xFFFFFFFF
    data = open(args.path, "rb").read()
    hits = 0
    for off in range(0, len(data) - 4, 4):
        insn = struct.unpack_from("<I", data, off)[0]
        if (insn & MASK) not in (MOVN32, MOVN64, MOVZ32, MOVZ64):
            continue
        val, kind = decode(insn)
        if val != target:
            continue
        hits += 1
        va = off if off < 0x1000 else off - 0x1000
        print("%08x (va~0x%x)  %s  value=0x%08x" % (off, va, kind, val))
    print(f"# {hits} hit(s)", file=sys.stderr)


if __name__ == "__main__":
    main()
