#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Julius Vitkauskas
# SPDX-License-Identifier: MIT-0
"""Build an FM-1 application package (.fwsc) from assembly sources, with this repository's assembler and linker.

    python3 tools/hwtest/fm1app.py OUT.fwsc SOURCE.S... [--key 0x980F] [--identity FM-1_901] [--ram 0x01C78000]
    python3 tools/hwtest/fm1app.py OUT.bin SOURCE.S... --plugin 0x01C20000

The sources are run through cpp, assembled and linked: .entry, .text and .rodata at 0x02000120 (the flash
window, where m-bootloader calls the application), .data and .bss in RAM from --ram (the application copies
.data itself: app_data_load, app_data_start, app_data_end; nothing does it for it). The entry symbol is the
first byte of .entry.

The package holds one file, flash.bin: an empty boot area (M-Flasher does not write it unless asked to) and an
application area at 0x4000 with the records m-bootloader and M-Flasher look for (m-bootloader docs/SPEC.md
§5.4): app_area_head (attribute 83, the entry address) and app.bin (attribute 82, CRC16 over its plain bytes)
at area offset 0x120, encrypted with the unit key (§5.1). No region records: the application keeps nothing in
flash. M-Flasher refuses a package that does not decrypt with the connected unit's key.

OUT.bin (app.bin) and OUT.elf are written beside the package.

With --plugin ADDR everything is linked at ADDR instead, as a flat RAM image for m-flasher run-ram (a download-mode
plug-in, its entry at the first byte), and no package is made.
"""
import argparse
import struct
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent))
from pi32v2isa import asm, ld  # noqa: E402
from pi32v2isa.oracle import read_exec  # noqa: E402

FLASH_WINDOW = 0x02000000
BOOT_AREA = 0x4000
APP_AT = 0x120                 # app.bin's offset in the area; the entry is FLASH_WINDOW + APP_AT
SECTOR = 0x1000
APP_MAX = 0x8F000 - APP_AT     # the stock firmware extent ends at 0x93000 (SPEC §5.5)


def crc16(data, crc=0):
    """CRC16/XMODEM (SPEC §5.1)."""
    for b in data:
        crc ^= b << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021 if crc & 0x8000 else crc << 1) & 0xFFFF
    return crc


def enc(data, key):
    """JieLi's ENC stream transform, its own inverse: one state step per byte (SPEC §5.1)."""
    out = bytearray(data)
    for i in range(len(out)):
        out[i] ^= key & 0xFF
        key = ((key << 1) ^ (0x1021 if key & 0x8000 else 0)) & 0xFFFF
    return bytes(out)


def area_crypt(data, key):
    """The application area's transform: ENC per 32-byte line, key XOR (offset >> 2) (SPEC §5.1)."""
    return b"".join(enc(data[q:q + 32], key ^ ((q >> 2) & 0xFFFF)) for q in range(0, len(data), 32))


def record(name, address, length, attribute, data_crc=0xFFFF):
    """A 32-byte file record (SPEC §5.2), plain."""
    body = struct.pack("<HIIBBH16s", data_crc, address, length, attribute, 0xFF, 0,
                       name.encode().ljust(16, b"\0"))
    return struct.pack("<H", crc16(body)) + body


def flash_image(app, entry, key):
    """flash.bin: erased boot area, then the encrypted application area, padded to whole sectors."""
    if len(app) > APP_MAX:
        raise SystemExit(f"app.bin is {len(app)} bytes, at most {APP_MAX}")
    if not 0 <= entry - FLASH_WINDOW - APP_AT < len(app):
        raise SystemExit(f"entry {entry:#x} is not inside app.bin")
    files = record("app.bin", APP_AT, len(app), 0x82, crc16(app))
    area = bytearray(b"\xFF" * APP_AT) + app
    area[32:32 + len(files)] = files
    area[0:32] = record("app_area_head", entry, len(area), 0x83, crc16(area[32:]))
    area += b"\xFF" * (-(BOOT_AREA + len(area)) % SECTOR)
    return b"\xFF" * BOOT_AREA + area_crypt(bytes(area), key)


def package(flash, identity):
    """A .fwsc holding flash.bin (SPEC §5.6): header and file list ENC FFFF, the identity in 48-byte blocks."""
    off = 0x400
    entry = bytearray(0x50)
    struct.pack_into("<HHHHIII", entry, 0, 0, 0, crc16(flash), 0, off, len(flash), len(flash))
    entry[0x40:0x40 + len("flash.bin")] = b"flash.bin"
    lst = enc(entry, 0xFFFF)
    head = bytearray(0x40)
    struct.pack_into("<HIHHH", head, 2, crc16(lst), off + len(flash), 1, 0x0004, 0x0200)
    head[16:22] = b"AC791N"
    struct.pack_into("<H", head, 0, crc16(head[2:]))
    image = bytearray(b"\xFF" * off)
    image[0:0x40] = enc(head, 0xFFFF)
    image[0x40:0x90] = lst
    image += flash
    if len(identity) > 20 or any((ord(c) + i + 1) & 0xFF == 0x7D for i, c in enumerate(identity)):
        raise SystemExit(f"identity {identity!r}: at most 20 characters, none whose marker would be 7D")
    out = bytearray()
    for i in range(20):
        mark = (ord(identity[i]) + i + 1) & 0xFF if i < len(identity) else 0x7D
        out += image[i * 47:(i + 1) * 47] + bytes([mark])
    return bytes(out + image[20 * 47:])


def build(sources, workdir, ram, plugin=None):
    """Assemble and link; (image bytes, entry address, symbols, ELF path)."""
    objs = []
    for src in sources:
        text = subprocess.run(["cpp", "-P", str(src)], capture_output=True, text=True, check=True).stdout
        o = Path(workdir) / (Path(src).stem + ".o")
        o.write_bytes(asm.assemble_source(text, str(src)))
        objs.append(str(o))
    if plugin is None:
        base, size = FLASH_WINDOW + APP_AT, APP_MAX
        memory = f"""  flash (rx) : ORIGIN = {base:#x}, LENGTH = {size:#x}
  ram (rwx) : ORIGIN = {ram:#x}, LENGTH = {0x01C7C000 - ram:#x}"""
        data = "AT(app_data_load)"
    else:
        base, size = plugin, 0x8000                   # one of the download-mode plug-in slots
        memory = f"  flash (rwx) : ORIGIN = {base:#x}, LENGTH = {size:#x}"
        data, ram = "", None
    script = Path(workdir) / "app.ld"
    script.write_text(f"""ENTRY(app_entry)
MEMORY {{
{memory}
}}
SECTIONS {{
  .entry : {{ KEEP(*(.entry)) }} > flash
  .text : {{ *(.text*) *(.rodata*) }} > flash
  app_data_load = .;
  .data : {data} {{ app_data_start = .; *(.data*) app_data_end = .; }} > {"ram" if ram else "flash"}
  .bss : {{ app_bss_start = .; *(.bss*) app_bss_end = .; }} > {"ram" if ram else "flash"}
}}
""")
    elf = Path(workdir) / "app.elf"
    if ld.main(argparse.Namespace(argv=["-T", str(script), *objs, "-o", str(elf)])):
        raise SystemExit("link failed")
    exe = read_exec(elf.read_bytes())
    syms = {name: value for name, value, *_ in exe["symbols"] if name}
    image = bytearray()
    for sec in exe["sections"]:
        if sec["type"] != 1 or not sec["flags"] & 2 or not sec["data"]:      # PROGBITS, SHF_ALLOC, not empty
            continue
        at = syms["app_data_load"] if sec["name"] == ".data" else sec["addr"]
        if not base <= at < base + size:
            raise SystemExit(f"section {sec['name']} at {at:#x} is outside {base:#x}..{base + size:#x}")
        off = at - base
        image[len(image):off] = b"\xFF" * max(0, off - len(image))
        image[off:off + len(sec["data"])] = sec["data"]
    if syms["app_entry"] != base:
        raise SystemExit(f"app_entry at {syms['app_entry']:#x}, not at {base:#x}")
    return bytes(image), base, syms, elf


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("out", type=Path)
    p.add_argument("sources", type=Path, nargs="+")
    p.add_argument("--key", type=lambda s: int(s, 0), default=0x980F, help="the unit's chip key (FM-1: 0x980F)")
    p.add_argument("--identity", default="FM-1_901", help="the package identity M-Flasher checks the model of")
    p.add_argument("--ram", type=lambda s: int(s, 0), default=0x01C78000, help="where .data and .bss go")
    p.add_argument("--plugin", type=lambda s: int(s, 0), help="a download-mode RAM image linked at this address")
    a = p.parse_args()
    out = a.out
    image, entry, syms, elf = build(a.sources, out.parent, a.ram, a.plugin)
    out.with_suffix(".bin").write_bytes(image)
    elf.replace(out.with_suffix(".elf"))
    if a.plugin is not None:
        print(f"{out.with_suffix('.bin')}: {len(image)} bytes at {entry:#x}")
        return
    out.write_bytes(package(flash_image(image, entry, a.key), a.identity))
    print(f"{out}: app.bin {len(image)} bytes, entry {entry:#x}, key {a.key:#06x}, identity {a.identity}")


if __name__ == "__main__":
    main()
