<!-- SPDX-FileCopyrightText: 2026 Julius Vitkauskas -->
<!-- SPDX-License-Identifier: CC0-1.0 -->

# Building FM-1 firmware with the open assembler

The overlay in [tools/overlay](../tools/overlay/README.md) builds Felucca,
fm1-base's template in all three Bluetooth configurations, and m-bootloader.
It replaces assembly and binary extraction. It still needs JieLi's C compiler,
linker and disassembler; LLVM bitcode and link-time code generation still use
JieLi's tools. These are build comparisons, not hardware execution results.
Evidence below is black-box **[oracle]**, compiler output **[compiler]**, and
project build inputs **[sources-in-use]** ([source ids](SOURCES.md)).

**Normal C builds are not byte-identical to the overlay.** JieLi's direct
`clang -c` output differs from its own `clang -S` followed by assembly. The
open assembler matches JieLi when both read the same assembly. The LTO boot
images/packages are byte-identical because their C compilation and link-time
code generation pass through unchanged; they do not demonstrate replacement
of the LTO assembler.

## Create the overlay

From this repository's root, with Python 3.11+, GNU `cpp`, and GNU `objcopy` on
`PATH`:

```sh
export PI32V2_TOOLCHAIN=/path/to/jieli-linux-toolchains-20260730.1
python3 tools/overlay/create.py /tmp/open-pi32v2 \
    --toolchain "$PI32V2_TOOLCHAIN" --repo "$PWD"
```

`/tmp/open-pi32v2` must not exist. This creates `common/bin/` and `pi32v2/bin/`.
No installation or vendor binary copy is needed. The generated configuration
records absolute paths to the source checkout and original toolchain; keep both
available. Use native Linux builds with `JIELI_DOCKER=0`.

`clang -c` compiles C to temporary assembly with JieLi `clang -S`, keeping
compilation flags, and runs `python3 -m pi32v2isa as`. Felucca also needs this
route for the `.ll` produced by its size pass. `.S` uses GNU `cpp` and the open
assembler; `.s` goes directly to the assembler. `-E`, `-S` and `-emit-llvm`
pass through, as does effective `-flto`, with a notice explaining the bitcode
exception. An assembly failure stops the build; there is no stock fallback.

`objcopy` uses GNU `objcopy -I elf32-little`. JieLi ld's generated ELF files
have a non-power-of-two program-header alignment of `0x500`; GNU binutils 2.44
rejects it. For binary extraction, the wrapper changes only invalid alignment
fields to 1 in a temporary input copy. Segment addresses, sections and the
saved original ELF stay intact. Extraction against stock-produced ELFs is
checked below. Other objcopy operations are passed to GNU without this repair.

`objdump`, `ld`, `lto-wrapper`, and `LLVMgold.so` are explicitly retained from
JieLi. `create.py --objdump EXE --ld EXE --lto-wrapper EXE --llvmgold FILE`
selects replacements independently; the generated JSON and plugin symlink can
also be changed. This overlay includes the tools needed by these projects,
not every utility in the vendor distribution.

## Reproduce the firmware builds

Clone into scratch, including submodules. The examples below are commands from
this repository root; the projects' build scripts select their own directories.
Pillow and fontTools are also needed by the firmware asset generators.

```sh
scratch=/tmp/pi32v2-open-build
mkdir -p "$scratch/results"
git clone --recurse-submodules https://github.com/hugelton/Felucca "$scratch/Felucca"
git clone --recurse-submodules --branch open-ble \
    https://github.com/jvitkauskas/fm1-base "$scratch/fm1-base"
git clone --recurse-submodules https://github.com/jvitkauskas/m-bootloader "$scratch/m-bootloader"
export AC79_SDK=/path/to/fw-AC79_AIoT_SDK
export JIELI_DOCKER=0
```

For each stock/overlay pair, use the **same clone path, source revision, SDK,
flags and generated assets**, and save the first build before cleaning. A
Felucca pair:

```sh
JIELI_TOOLCHAIN="$PI32V2_TOOLCHAIN" "$scratch/Felucca/build.sh"
cp -a "$scratch/Felucca/build" "$scratch/results/felucca-stock"
rm -rf "$scratch/Felucca/build"
JIELI_TOOLCHAIN=/tmp/open-pi32v2 "$scratch/Felucca/build.sh"
cp -a "$scratch/Felucca/build" "$scratch/results/felucca-open"
python3 tools/overlay/compare.py \
    "$scratch/results/felucca-stock" "$scratch/results/felucca-open" --json \
    > "$scratch/results/felucca-comparison.json"
```

`compare.py` exits 1 when any file differs (expected for the normal comparison)
or when no products exist. It checks every `.o`, `.elf`, `.bin`, `.fwsc` and
`.boot`, reports missing files, and provides sizes, SHA-256 values, first
differences and unequal-byte counts in JSON.

Repeat the same save/clean/build sequence for each fm1-base invocation:

```sh
JIELI_TOOLCHAIN="$PI32V2_TOOLCHAIN" python3 "$scratch/fm1-base/tools/build.py" "$scratch/fm1-base/template"
JIELI_TOOLCHAIN="$PI32V2_TOOLCHAIN" python3 "$scratch/fm1-base/tools/build.py" "$scratch/fm1-base/template" --open-ble
JIELI_TOOLCHAIN="$PI32V2_TOOLCHAIN" python3 "$scratch/fm1-base/tools/build.py" "$scratch/fm1-base/template" --no-ble
```

Save and remove `fm1-base/template/build/` between variants and between tools;
repeat each command with `JIELI_TOOLCHAIN=/tmp/open-pi32v2`. The normal/default
Bluetooth build links SDK bitcode libraries. The open-BLE build uses the
repository's pinned NimBLE/TinyCrypt sources and open controller; USB omits BLE.
All three package the SDK's `uboot.boot`, `cfg_tool.bin` and `cfg/eq_cfg_hw.bin`.

For m-bootloader, replace the symlink in the scratch clone between clean builds:

```sh
ln -s "$PI32V2_TOOLCHAIN" "$scratch/m-bootloader/toolchain"
make -C "$scratch/m-bootloader" -j4
cp -a "$scratch/m-bootloader/build" "$scratch/results/mboot-stock"
rm -rf "$scratch/m-bootloader/build"
ln -sfn /tmp/open-pi32v2 "$scratch/m-bootloader/toolchain"
make -C "$scratch/m-bootloader" -j4
cp -a "$scratch/m-bootloader/build" "$scratch/results/mboot-open"
```

The boot and installer C objects use LTO; the two MFLR flash loaders do not.
Assembly entry files use the open assembler in both cases.

## Revisions and SDKs tested (2026-10-24)

- JieLi Linux toolchain `20260730.1`, the release pinned in [ORACLE.md](ORACLE.md).
- Felucca `63f88ec18b71c6ed4371d03d6f04dd93f4193ad3`, engines submodule
  `c46e0086f69bdc26df1cd144dca9e683cc4531dd`.
- fm1-base `open-ble`, `b891b19f8b68db46aab6ddcb1274fbbf54693fa7`, BSP
  `62a01ca7affe8de73707e309b57e98f1734c8b2d`; NimBLE is vendored in that revision.
- m-bootloader `64b74d009e6d21fe85ca60754b7c01d438214804`.
- GNU objcopy 2.44, native Linux x86-64. No firmware source edits or system-wide
  installations were made.

Felucca, open-BLE and USB used the supplied SDK checkout tagged
`AC79NN_SDK_V1.2.14_2026-10-13`. Its `uboot.boot` and `eq_cfg_hw.bin` differ
from the projects' V1.2.1 hashes; both stock and overlay warn, and both use the
same files. Default fm1-base with that SDK fails to link even with the stock
toolchain: five undefined references to `usr_timeout_del`. It was retried with
an independent scratch checkout of `AC79NN_SDK_V1.2.1_2023-12-13`
(`b02c8c9354c077238ccbf764e36eff53782e1c16`); both builds then succeed, with all
three package-file hashes accepted. No stub or firmware workaround was used.
To obtain that tested SDK without altering an existing checkout:

```sh
git clone --depth 1 --single-branch --branch AC79NN_SDK_V1.2.1_2023-12-13 \
    https://gitee.com/Jieli-Tech/fw-AC79_AIoT_SDK.git "$scratch/ac79-v1.2.1"
export AC79_SDK="$scratch/ac79-v1.2.1"
```

## Byte comparison results

Counts include every generated file with the five suffixes above, including
section binaries and fm1-base's copied variant-named application binaries.
They exclude copied SDK libraries (`.a`), generated assets, maps and listings.
Each row compares clean builds in the same absolute project directory.

| Build | Objects | ELFs | Firmware/section files | Identical to normal | Different from normal |
| --- | ---: | ---: | ---: | ---: | ---: |
| Felucca | 7 | 2 | 8 | 5 | 12 |
| fm1-base default BLE, SDK V1.2.1 | 15 | 2 | 7 | 13 | 11 |
| fm1-base open BLE | 80 | 2 | 8 | 19 | 71 |
| fm1-base USB (`--no-ble`) | 6 | 2 | 8 | 5 | 11 |
| m-bootloader, both boards and loader slots | 32 | 6 | 11 | 35 | 14 |
| **Total** | **140** | **14** | **42** | **77** | **119** |

Object differences: Felucca 2/7; default BLE 2/15; open BLE 61/80; USB 2/6;
m-bootloader 10/32. Every assembly-source object is identical to normal. The
unchanged LLVM bitcode objects number eight for default BLE and sixteen for
m-bootloader. In m-bootloader, four ELFs, both `.boot` images, four `.bin`
files and all three `.fwsc` packages are identical. Its two non-LTO loader
ELFs and binaries differ. Neither Felucca nor any fm1-base variant produces
an application or package identical to a normal build.

Selected product lengths in bytes (normal → open):

| Product | Normal | Open |
| --- | ---: | ---: |
| Felucca `felucca.bin` | 511124 | 509488 |
| Felucca `loader/ota.bin` | 6934 | 6928 |
| Felucca `felucca.fwsc` | 610090 | 610084 |
| fm1-base default `template.bin` | 215356 | 215316 |
| fm1-base default `template.fwsc` | 610136 | 610128 |
| fm1-base open BLE `template.bin` | 199792 | 199468 |
| fm1-base open BLE `template-open.fwsc` | 610136 | 610128 |
| fm1-base USB `template.bin` | 80172 | 80116 |
| fm1-base USB `template-usb.fwsc` | 610136 | 610128 |
| All fm1-base variants `loader/ota.bin` | 6980 | 6972 |
| m-bootloader FM-1 `uboot.boot` | 12936 | 12936 |
| m-bootloader SMK37 `uboot.boot` | 14000 | 14000 |
| m-bootloader slot A `mflr-loader-a.bin` | 5908 | 5900 |
| m-bootloader slot B `mflr-loader-b.bin` | 5912 | 5900 |

The firmware build scripts' image/RAM, section-placement, startup and packaging
checks all passed for the successful pairs. No firmware was installed or run
on hardware.

## Localizing the differences

A minimal independently written **[compiler]** probe demonstrates the two
compiler paths:

```c
int bump(int x) { return x + 1; }
```

At `-target pi32v2 -mcpu=r3 -Os`, JieLi `clang -c` emits `.text` bytes
`c0 21 80 00`. JieLi `clang -S` prints `r0 += 1` followed by `rts`; assembling
that text with **either** assembler emits `08 81 80 00`. This explains why an
assembler that matches JieLi on text cannot promise identical direct C objects.
The observed equivalence here concerns the operation/compiler choice; there
was no hardware or status-flag equivalence test.

Across the 50 files of `tests/corpus/` at -O0, -O2 and -Os (150 objects; JieLi `clang -c` against JieLi
`clang -S` assembled by the open assembler, which is the same as JieLi's assembler on that text), 16473
instructions use the same table entry and every other one falls in one of two kinds **[compiler]**:

| Kind | Examples (count) |
| --- | --- |
| An equivalent form chosen differently | `add.rr` for `add.rrr` (364), `add.ri.u5` for `add.rri` (96), the twins `add.rr.p` for `add.rrr.p` (95), signed 12-bit compares `if*.ri.s12` for `if*.ri.modimm` (~165), `rmw.add.s12` for `rmw.add.modimm` (60), sometimes a 32-bit form where a 16-bit one fits (`ld.w.sp.l`, `li.modimm`) |
| A branch of another size | `goto.l` for `goto.s` (175), long compare-and-branch forms (`bgts.ri.l`, `bges.rr.l`, ...) for short ones; offsets after them shift accordingly |

The second kind is decided by the compiler's code generator and does not appear in the `-S` text, so no
assembler that reads text can reproduce `clang -c` objects in general. The open toolchain therefore aims at
identity with JieLi's assembler on the same text, which holds for every firmware product above.

For each build, retain the actual compiler/preprocessor output:

```sh
export PI32V2_OVERLAY_LOG="$scratch/overlay.jsonl"
export PI32V2_OVERLAY_SAVE_ASM="$scratch/assembly"
```

These optional diagnostics must be absolute paths. The JSONL identifies C/IR
compilation, GNU preprocessing, LTO passthrough and every retained vendor tool.
Run, from this repository root:

```sh
python3 -m pi32v2isa oracle asmcompare "$scratch/assembly/build/felucca.s"
# For fm1-base the saved paths begin template/build/; for .incbin/.include,
# supply the original source/include directories with -I.
```

The comparison also used a control build in which each saved assembly input
was assembled by JieLi instead of the open assembler, retaining the same
compiler-to-text route, linker and extraction. This separates direct-compiler
code generation from assembly and downstream packaging. Full byte comparisons
and raw reassembly counts are given with the final verification below.

## Fixes exposed by the full builds

These are Python assembler/writer fixes, not instruction-table changes. Minimal
original probes and the real saved sources were checked with `oracle
asmcompare`; regression checks are in `tests/test_asm.py`.

- Compiler output `r1 = (ext + 4294967295)` crashed while serializing the
  signed ELF32 relocation addend. The writer now retains the low 32 bits as
  a signed addend (`-1`); `2147483648` similarly becomes `-2147483648`.
- The default BLE context switch uses `[r0] = r2`. A bare general-register
  address is accepted as offset zero when the original spelling has no
  matcher. Existing bare-address instructions such as `flushinv [r2]`
  retain their own syntax.
- The open-BLE link layer prints `r3 = r0 - 0xFFFFFFFF`. The assembler
  incorrectly shortened it to a two-byte addition by wrapping the negated
  constant. It now retains the four-byte subtraction JieLi emits; the related
  `-0xFFFFFFFE` case retains JieLi's four-byte addition. This removed all
  differences in `ble_open_ble_ble_link.o` when comparing the same `.s`.

The initial mismatch in that last object affected three functions and shifted
branches, relocations, symbol offsets and downstream files; those were
consequences of the shorter alias, not separate encoding-table failures.

## Final verification and remaining vendor behavior

- **116/116** non-bitcode objects are byte-identical when the recorded `.s`
  inputs are assembled by JieLi and compared to the overlay's actual objects:
  7 Felucca, 7 default BLE, 80 open BLE, 6 USB and 16 m-bootloader. This covers
  94 C/IR outputs and 22 preprocessed assembly units, with no missing objects.
  `oracle asmcompare` also reports identical for the large Felucca and open-BLE
  unity sources, the corrected BLE link layer, and the minimal fix probes.
- The complete compiler-to-text control builds match **195/196** saved files
  byte for byte, including **all 42 firmware/section files**. The exception is
  default BLE's `template.elf`: the first control differs in four bytes, all
  inside `.debug_line`. Repeating that identical control changes the ELF length
  from 1504792 to 1504796 bytes: `.debug_line` grows by one byte, with consequent
  `.debug_info` references, local `.Lline_table_start*` symbol values and file
  layout changes. All input objects and all allocated sections, addresses and
  firmware products remain identical. This demonstrates nondeterministic
  vendor LTO debug output; the assembler comparison is unaffected. No bytes
  were normalized or stripped for the reported raw file counts.
- All **23** binary-extraction invocations were repeated using stock-generated
  ELFs as inputs to the GNU wrapper: each extracted file is byte-identical to
  the stock objcopy output. The temporary alignment repair therefore adds no
  firmware differences in these builds.
- The instruction checker reports **1147 entries, 0 problems**. The complete
  repository unit suite, including live oracle checks, passes **75 tests**
  (**1 skipped**) with `PI32V2_TOOLCHAIN` set. Eight additional wrapper smoke checks cover spaces in
  paths, dependency targets, response files, GNU cpp macros, and `-E`, `-S`,
  LLVM-IR and LTO passthrough.

The remaining direct-build differences are thus localized to the vendor
compiler's object-versus-text path and, for the closed BLE ELF, its LTO debug
metadata. Replacing the C compiler, ld, objdump and LTO machinery remains future
work. LTO and existing SDK libraries are explicitly outside the open assembler
claim. Debug assembly remains subject to the limits in [ASSEMBLER.md](ASSEMBLER.md).

Scratch evidence for this run is under `/tmp/j/`: `results/PROJECT/stock`,
`overlay`, and `roundtrip`; `PROJECT-comparison.json`; the initial
`PROJECT-roundtrip-comparison.json`; `assembly/`; `assembly-audit.json`;
`*-trace.jsonl`; `*-status.json`; and build/test logs. The first default BLE
control is retained as `results/fm1-default/roundtrip-first`. These scratch files
are not part of the repository or a permanent downloadable corpus. The committed
comparison script regenerates the byte comparisons from saved build trees.
