# pi32v2-isa

An open reference for the **pi32v2** instruction set (JieLi's CPU core, used in the AC791N and other JieLi
chips): a machine-readable instruction table, an assembler, disassembler, linker and objdump built from it, and
the generators and checks for an LLVM backend, so that firmware for these chips can be built without JieLi's
closed tools.

The first target is the core in the M-VAVE FM-1 (AC791N, `-mcpu=r3` with the `fprev1` FPU); the M-VAVE SMK-37
Pro uses the same chip family.

> Unofficial: not affiliated with JieLi or M-VAVE. Everything here comes from public sources and from observing
> how JieLi's freely downloadable toolchain and the chip behave; see [docs/SOURCES.md](docs/SOURCES.md). No
> JieLi code, binaries or firmware are in this repository.

## What works

- **The instruction table** holds every instruction form JieLi's objdump decodes, each confirmed against JieLi's
  toolchain (encoding and syntax); 1079 of its 1165 forms are also confirmed on the chip ([hw/](hw/README.md)).
- **This repository's assembler, linker and objdump** write and read the files JieLi's do, byte for byte: the
  FM-1 firmwares build identically with them in place of JieLi's ([docs/BUILDING-OPEN.md](docs/BUILDING-OPEN.md)).
- **An LLVM toolchain** (clang and `ld.lld` from the fork
  [jvitkauskas/pi32v2-llvm](https://github.com/jvitkauskas/pi32v2-llvm), its tables generated from here) builds
  the community firmwares from source with nothing of JieLi's, and they run on the hardware:

  | Firmware | Size with LLVM (with JieLi's toolchain) | On the hardware |
  | --- | --- | --- |
  | m-bootloader 1.2, FM-1 / SMK-37 Pro (`-Oz`, slot 14368 bytes) | 13168 / 14200 (12936 / 14000) | both units: boot, menu, download mode, wipe |
  | fm1-base (template, no BLE) | 79908 (80172) | FM-1 |
  | Felucca | 508672 (511124) | FM-1: screen, keys, sound |
  | SLOOP 2.8.1 (Felucca's groovebox fork, both cores) | 563688 (567564) | FM-1: screen, keys, sound, patterns |

  Its output is checked against JieLi's compiler in a simulator on every change ([docs/LLVM.md](docs/LLVM.md)).

## Start here

| If you want to | Read |
| --- | --- |
| build firmware for the FM-1 with the open toolchain | [docs/TOOLCHAIN.md](docs/TOOLCHAIN.md), then [examples/fm1-blink](examples/fm1-blink/), the C conventions in [docs/ABI.md](docs/ABI.md) |
| build an existing FM-1 firmware without JieLi's assembler and linker | [docs/BUILDING-OPEN.md](docs/BUILDING-OPEN.md) |
| work on the LLVM backend | [docs/LLVM.md](docs/LLVM.md), [docs/COMPILER.md](docs/COMPILER.md) (what JieLi's compiler emits), [tools/llvm/](tools/llvm/) |
| look up an instruction | [docs/ISA.md](docs/ISA.md), the table [isa/pi32v2.toml](isa/pi32v2.toml) ([format](docs/TABLE-FORMAT.md)), `python3 -m pi32v2isa disasm` |
| use the assembler, linker or objdump | [docs/ASSEMBLER.md](docs/ASSEMBLER.md), [docs/LINKER.md](docs/LINKER.md), [docs/OBJDUMP.md](docs/OBJDUMP.md), [docs/ELF.md](docs/ELF.md) |
| know how a fact was established, or add one | [docs/SOURCES.md](docs/SOURCES.md), [docs/ORACLE.md](docs/ORACLE.md), [hw/](hw/README.md), [AGENTS.md](AGENTS.md) |
| know what is still open | [docs/GAPS.md](docs/GAPS.md) |
| use the second core | [docs/CPU1.md](docs/CPU1.md) |

## Repository map

| Path | What |
| --- | --- |
| `isa/pi32v2.toml` | The instruction table: one entry per instruction form, with encoding, syntax, semantics notes, status and sources |
| `pi32v2isa/` | Python package: table loader and checker, disassembler, assembler, ELF writer and reader, linker, objdump, oracle drivers |
| `docs/` | The reference and the tools' manuals (above) |
| `tools/llvm/` | The LLVM backend's generators (TableGen, assembler and compression tables), its differential test, a simulator, the runtime (`__sync_*`) and the packaging |
| `tools/hwtest/` | The hardware test harness: test images run in RAM or installed as applications, and their analysis |
| `hw/` | The hardware runs and their results ([index](hw/README.md)) |
| `examples/fm1-blink/` | An FM-1 application built with clang and `ld.lld` alone: start-up code, linker script, a timer interrupt in C |
| `tests/` | Unit tests |

## Use

Python 3.11 or later, no dependencies.

```sh
python3 -m pi32v2isa check                 # validate the table
python3 -m pi32v2isa disasm 80 00 01 00    # decode bytes (hex)
python3 -m pi32v2isa as boot.S -o boot.o   # assemble (.S goes through cpp; docs/ASSEMBLER.md)
python3 -m pi32v2isa ld -T app.ld a.o b.o -o app.elf   # link (docs/LINKER.md)
python3 -m pi32v2isa objdump -d app.elf    # list, headers, symbols, relocations like JieLi's objdump (docs/OBJDUMP.md)
python3 -m unittest discover -s tests      # run the tests
```

Checking entries against JieLi's toolchain (it is downloaded, never committed; [docs/ORACLE.md](docs/ORACLE.md)):

```sh
python3 -m pi32v2isa oracle fetch          # get JieLi's toolchain
python3 -m pi32v2isa oracle sweep          # see what it makes of every 16-bit word
python3 -m pi32v2isa oracle confirm        # check entries against it
python3 -m pi32v2isa oracle cc file.c      # what JieLi's compiler makes of some C
python3 -m pi32v2isa oracle asmcompare boot.S        # our assembler against JieLi's, object by object
python3 -m pi32v2isa oracle objdumpcompare app.elf   # our objdump against JieLi's, line by line
```

## Licence

Code is [MIT-0](LICENSES/MIT-0.txt). Documentation and the instruction table are
[CC0-1.0](LICENSES/CC0-1.0.txt). Each file's licence is given by its SPDX header or by
[REUSE.toml](REUSE.toml). The LLVM fork is under LLVM's licence (Apache-2.0 with LLVM exceptions).
