#!/usr/bin/env python3
import argparse
import struct
import sys
from pathlib import Path


def parse_phdrs(hdr):
    e_phoff = struct.unpack_from("<Q", hdr, 0x20)[0]
    e_phentsize = struct.unpack_from("<H", hdr, 0x36)[0]
    e_phnum = struct.unpack_from("<H", hdr, 0x38)[0]
    out = []
    for i in range(e_phnum):
        off = e_phoff + i * e_phentsize
        p_type, p_flags, p_offset, p_vaddr, p_paddr, p_filesz, p_memsz, p_align = struct.unpack_from(
            "<IIQQQQQQ", hdr, off
        )
        out.append(
            {
                "type": p_type,
                "offset": p_offset,
                "vaddr": p_vaddr,
                "filesz": p_filesz,
                "memsz": p_memsz,
            }
        )
    return out


def build(src_dir: Path, name: str, out_path: Path | None) -> Path:
    parts = {}
    for n in range(9):
        p = src_dir / f"{name}.b{n:02d}"
        if p.exists():
            parts[n] = p.read_bytes()
    if 0 not in parts or parts[0][:4] != b"\x7fELF":
        raise SystemExit(f"{name}.b00 missing or not an ELF header")
    hdr = parts[0]
    phdrs = parse_phdrs(hdr)
    loadable = [p for p in phdrs if p["type"] in (1, 2)]
    size = max(p["offset"] + p["filesz"] for p in loadable)
    buf = bytearray(size)
    for i, ph in enumerate(phdrs):
        if i == 0:
            buf[0 : len(hdr)] = hdr
            continue
        if ph["type"] not in (1, 2) or i not in parts:
            continue
        data = parts[i]
        seg = data[: ph["filesz"]] if ph["filesz"] else data
        buf[ph["offset"] : ph["offset"] + len(seg)] = seg
    out = out_path or (src_dir / f"{name}.bin")
    out.write_bytes(bytes(buf))
    print(f"wrote {out} size=0x{size:x} ({size} bytes)")
    for i, ph in enumerate(phdrs):
        have = "yes" if i in parts else "no"
        print(
            f"  ph{i} type={ph['type']} off=0x{ph['offset']:x} va=0x{ph['vaddr']:x} "
            f"filesz=0x{ph['filesz']:x} part={have}"
        )
    return out


def main():
    ap = argparse.ArgumentParser(description="Rebuild a split-bin TA (b00..b08) into one ELF image.")
    ap.add_argument("src_dir", help="directory containing <name>.b00..b08")
    ap.add_argument("name", help="file prefix, e.g. soter64")
    ap.add_argument("-o", "--output", help="output path (default: <src_dir>/<name>.bin)")
    args = ap.parse_args()
    build(Path(args.src_dir), args.name, Path(args.output) if args.output else None)


if __name__ == "__main__":
    main()
