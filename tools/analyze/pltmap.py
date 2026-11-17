#!/usr/bin/env python3
import argparse
import struct
import sys

PT_LOAD = 1
PT_DYNAMIC = 2
DT_NULL = 0
DT_STRTAB = 5
DT_SYMTAB = 6
DT_SYMENT = 11
DT_JMPREL = 23
DT_PLTRELSZ = 2
DT_PLTREL = 20


def phdrs(data):
    e_phoff = struct.unpack_from("<Q", data, 0x20)[0]
    e_phentsize = struct.unpack_from("<H", data, 0x36)[0]
    e_phnum = struct.unpack_from("<H", data, 0x38)[0]
    out = []
    for i in range(e_phnum):
        off = e_phoff + i * e_phentsize
        p_type, _flags, p_offset, p_vaddr, _paddr, p_filesz, p_memsz, _align = struct.unpack_from(
            "<IIQQQQQQ", data, off
        )
        out.append((p_type, p_offset, p_vaddr, p_filesz, p_memsz))
    return out


def main():
    ap = argparse.ArgumentParser(
        description="Resolve imported symbols and PLT stub addresses of an AArch64 ELF (static/dynamic)."
    )
    ap.add_argument("path")
    args = ap.parse_args()
    data = open(args.path, "rb").read()
    ph = phdrs(data)

    def va2off(va):
        for t, off, vaddr, filesz, _memsz in ph:
            if t == PT_LOAD and vaddr <= va < vaddr + filesz:
                return va - vaddr + off
        raise SystemExit(f"va 0x{va:x} not in any PT_LOAD")

    dyn = None
    for t, off, vaddr, filesz, _memsz in ph:
        if t == PT_DYNAMIC:
            dyn = (off, filesz)
    if not dyn:
        raise SystemExit("no PT_DYNAMIC: not a dynamic ELF")
    off, filesz = dyn
    tags = {}
    for i in range(filesz // 16):
        tag, val = struct.unpack_from("<qQ", data, off + i * 16)
        if tag == DT_NULL:
            break
        tags.setdefault(tag, val)

    symtab = tags.get(DT_SYMTAB)
    strtab = tags.get(DT_STRTAB)
    syment = tags.get(DT_SYMENT, 24)
    if not symtab or not strtab:
        raise SystemExit("missing DT_SYMTAB/DT_STRTAB")

    def sym_name(idx):
        so = va2off(symtab) + idx * syment
        name_off = struct.unpack_from("<I", data, so)[0]
        if name_off == 0:
            return "?"
        b = va2off(strtab) + name_off
        e = data.find(b"\0", b)
        return data[b:e].decode("latin-1")

    jmprel = tags.get(DT_JMPREL)
    pltrelsz = tags.get(DT_PLTRELSZ, 0)
    got = {}
    if jmprel:
        for i in range(pltrelsz // 24):
            ro = va2off(jmprel) + i * 24
            r_offset, r_info, r_addend = struct.unpack_from("<QQq", data, ro)
            got[r_offset] = (sym_name(r_info >> 32), r_info & 0xFFFFFFFF, r_addend)

    print(f"# imports: {len(got)}")
    for g in sorted(got):
        name, typ, add = got[g]
        print("got=0x%x  %-28s type=%d addend=0x%x" % (g, name, typ, add))

    code = None
    for t, o, vaddr, filesz, _m in ph:
        if t == PT_LOAD and filesz > 0x1000:
            code = (o, vaddr, filesz)
    if not code:
        return
    o, vaddr, filesz = code
    print("\n# PLT stubs (adrp x16 / ldr x17,[x16,#imm] / add x16,x16,#imm / br x17)")
    for i in range(0, filesz - 16, 4):
        try:
            w0, w1, w2, w3 = struct.unpack_from("<IIII", data, o + i)
        except struct.error:
            break
        if (w0 & 0x9F00001F) != 0x90000010:
            continue
        if (w1 & 0xFFC00000) != 0xF9400000 or (w1 & 0x1F) != 17 or ((w1 >> 5) & 31) != 16:
            continue
        if (w2 & 0xFFC00000) != 0x91000000 or (w2 & 0x1F) != 16 or ((w2 >> 5) & 31) != 16:
            continue
        if w3 != 0xD61F0220:
            continue
        va = vaddr + i
        imm = (((w0 >> 5) & 0x7FFFF) << 2 | ((w0 >> 29) & 3)) << 12
        if imm & (1 << 32):
            imm -= 1 << 33
        page = (va & ~0xFFF) + imm
        ldr_imm = ((w1 >> 10) & 0xFFF) * 8
        g = page + ldr_imm
        name = got.get(g, ("<not a jump slot>", 0, 0))[0]
        print("stub va=0x%x  got=0x%x  %s" % (va, g, name))


if __name__ == "__main__":
    main()
