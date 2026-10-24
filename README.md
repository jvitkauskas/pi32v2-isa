# pi32v2-isa

An open reference for the **pi32v2** instruction set (JieLi's CPU core, used in the AC791N and other JieLi
chips), with a machine-readable instruction table and an assembler and disassembler built from it.

The first target is the core in the M-VAVE FM-1 (AC791N, `-mcpu=r3` with the `fprev1` FPU). The goal is to
build firmware for it without JieLi's closed tools: this repo covers the ISA, assembly and disassembly; a
linker and a compiler backend are later, separate projects that use this reference.

> Unofficial: not affiliated with JieLi. Everything here comes from public sources and from observing how
> JieLi's freely downloadable toolchain behaves; see [docs/SOURCES.md](docs/SOURCES.md).

## What is here

| Path | What |
| --- | --- |
| [docs/ISA.md](docs/ISA.md) | The ISA reference: registers, instruction formats, syntax, execution model, ELF object format |
| [isa/pi32v2.toml](isa/pi32v2.toml) | The instruction table: one entry per instruction form, with encoding, syntax, status and sources |
| [docs/TABLE-FORMAT.md](docs/TABLE-FORMAT.md) | The table's format |
| [docs/ASSEMBLER.md](docs/ASSEMBLER.md) | The assembler: usage, syntax, directives, how it picks encodings, differences from JieLi's |
| [docs/ELF.md](docs/ELF.md) | The object files: sections, symbols, every relocation type, what JieLi's linker checks |
| [docs/GAPS.md](docs/GAPS.md) | What is known to exist but is not documented yet |
| [docs/SOURCES.md](docs/SOURCES.md) | Where each fact comes from, and the sources' licences |
| [docs/ORACLE.md](docs/ORACLE.md) | How JieLi's toolchain is used as a black-box test oracle |
| [AGENTS.md](AGENTS.md) | Rules for anyone (person or agent) amending the reference |
| `pi32v2isa/` | Python package: table loader and checker, disassembler, assembler (`python3 -m pi32v2isa as`) and ELF writer |

## Status

The table holds every instruction form JieLi's objdump decodes, all confirmed against JieLi's toolchain
(encoding and syntax). The disassembler reads the FM-1 projects' assembly and JieLi's compiler output
exactly as JieLi's objdump does. The assembler writes the objects JieLi's does (byte for byte on the FM-1
sources and on JieLi's compiler output) and JieLi's linker accepts them ([docs/ASSEMBLER.md](docs/ASSEMBLER.md),
[docs/ELF.md](docs/ELF.md)). The C ABI is in [docs/ABI.md](docs/ABI.md); what instructions do is documented
as far as the syntax and the compiler show it ([docs/COMPILER.md](docs/COMPILER.md)).
[docs/GAPS.md](docs/GAPS.md) lists what comes next.

## Use

Python 3.11 or later, no dependencies.

```sh
python3 -m pi32v2isa check                 # validate the table
python3 -m pi32v2isa disasm 80 00 01 00    # decode bytes (hex)
python3 -m pi32v2isa as boot.S -o boot.o   # assemble (.S goes through cpp; docs/ASSEMBLER.md)
python3 -m pi32v2isa oracle fetch          # get JieLi's toolchain, for checking entries (docs/ORACLE.md)
python3 -m pi32v2isa oracle sweep          # see what the toolchain makes of every 16-bit word
python3 -m pi32v2isa oracle confirm        # check entries against it
python3 -m pi32v2isa oracle cc file.c      # what JieLi's compiler makes of some C
python3 -m pi32v2isa oracle asmcompare boot.S   # our assembler against JieLi's, object by object
python3 -m unittest discover -s tests      # run the tests
```

## Licence

Code is [MIT-0](LICENSES/MIT-0.txt). Documentation and the instruction table are
[CC0-1.0](LICENSES/CC0-1.0.txt). Each file's licence is given by its SPDX header or by
[REUSE.toml](REUSE.toml).
