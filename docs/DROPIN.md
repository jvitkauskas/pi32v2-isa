<!-- SPDX-FileCopyrightText: 2026 Julius Vitkauskas -->
<!-- SPDX-License-Identifier: CC0-1.0 -->

# A drop-in for JieLi's Linux toolchain

`tools/dropin/make_dropin.sh` builds a directory with the layout and the tool names of JieLi's Linux toolchain
(`/opt/jieli`: `common/bin`, `pi32v2/bin`, `pi32v2/lib`) on the LLVM fork's tools ([LLVM.md](LLVM.md)), so that the
AC79 SDK's own Makefiles build with it. Nothing of JieLi's is read, run or copied to make it; the SDK's Makefiles
and scripts are used unchanged. Facts about JieLi's tools are black-box **[oracle]** (their command lines and output
on the SDK builds, `20260730.1`), the SDK's build files **[sources-in-use]** ([source ids](SOURCES.md)).

## Make and use

```sh
tools/llvm/build_builtins.sh LLVM_BIN LLVM_PROJECT RT          # libclang_rt.builtins-pi32v2.a, libpi32v2.a
tools/dropin/make_dropin.sh [--copy] LLVM_BIN RT /opt/jieli    # OUT must not exist
cd fw-AC79_AIoT_SDK
ulimit -n 8192
make -j6 ac791n_demo_demo_hello TOOL_DIR=/opt/jieli/pi32v2/bin
```

`TOOL_DIR` on make's command line replaces the Makefile's `TOOL_DIR := /opt/jieli/pi32v2/bin` (every other path
in the Makefiles is relative to it: `$(TOOL_DIR)/../lib/r3`, `$(TOOL_DIR)/../include`); no SDK file is edited. A
symlink `/opt/jieli` to the directory works the same, without the argument. The directory finds its own place
from the name each tool is started under, so it can be moved. Without `--copy` the LLVM tools are links to
`LLVM_BIN`; with it they, and clang's headers, are copied into `llvm/` and the directory needs only Python 3.11.

The tools that need translating are one Python script (`common/lib/pi32v2-dropin/jlwrap.py`) started under the
tool's name. `PI32V2_DROPIN_VERBOSE=1` prints each command it runs; `PI32V2_DROPIN_LDFLAGS` adds options to
`ld.lld` (for experiments, such as `--noinhibit-exec`).

## The tools

| JieLi's | What the SDK uses it for | Here |
| --- | --- | --- |
| `pi32v2/bin/clang` (`common/bin/clang`; `clang++`, `cc`, `cxx`) | every C, C++ and `.S` compile to a bitcode object (`-flto -c`, `-MMD -MF`); `-E -P` of `sdk_ld.c`, `sdk_used_list.c`, `section.c`, `download.c`, `isd_config_rule*.c` in the pre-build step (linker script, symbol list, shell script, `.ini` files) | `jlwrap.py` → `llvm/bin/clang`, options below |
| `pi32v2/bin/lto-wrapper` | the link, `lto-wrapper -o sdk.elf @objs.txt LFLAGS` | `jlwrap.py`: `--extra-arguments-from-file`, `--output-version-info`, then `ld` |
| `pi32v2/bin/ld` | run by `lto-wrapper` with `--plugin LLVMgold.so` | `jlwrap.py` → `ld.lld` (its link-time optimizer replaces the plug-in), options below |
| `LLVMgold.so` | JieLi's LTO plug-in | an empty file: only its name is looked up |
| `objdump` | post-build: `-D -print-dbg -mcpu=r3` (listing with source lines), `-section-headers -address-mask=0x1ffffff`, `-t` | `jlwrap.py` → `pi32v2isa objdump` ([OBJDUMP.md](OBJDUMP.md)), with `-print-dbg` done by `llvm-symbolizer` |
| `objsizedump` | post-build: `-lite -skip-zero [-enable-dbg-info]` sorted into `symbol_tbl.txt` and `map.lit`; read by `report_elf_sizes.py` | `jlwrap.py`: the same text from the ELF symbol table and, for the file column, `llvm-symbolizer` |
| `objcopy` | post-build (the Windows script): `-O binary -j SECTION` of five sections | `llvm-objcopy` |
| `lto-ar`, `ar` | `AR` in the Makefiles; no application target runs it | `jlwrap.py` (drops `--plugin`) → `llvm-ar` |
| `nm`, `strip` | not used by the SDK | `llvm-nm`, `llvm-objcopy` as `strip` |
| `llvm-read-version`, `link-version` | the version strings of the libraries (`.sys.version`); not used by the SDK's applications | `jlwrap.py`: the strings of objects and archives; `link-version` writes them as text |
| `llvm-bcrename`, `llvm-link` | building the SDK's libraries | not provided |
| `pi32v2/lib/rN[-large]/lib{c,m,g,compiler-rt}.a`, `pi32v2/include` | the Makefiles name `lib/r3` and `include`; the SDK links its own C library (`include_lib/newlib`) | `libcompiler-rt.a` (and `libcompiler_rt.a`) in each, from compiler-rt's builtins; no C library or headers |

The post-build script (`cpu/wl82/tools/download.sh`, made from `download.c`) cannot finish on Linux with JieLi's
tools either: it runs its commands from the wrong directory, calls `/opt/utils/strip-ini` and hands the packaging to
a service (`host-client`); the firmware packages come from Windows programs. `tools/dropin/postbuild.sh TOOL_DIR
ELF OUT` runs the commands that work (listing, section table, symbol listings, section images, `app.bin`).

## Options of JieLi's clang

| Option | Here |
| --- | --- |
| `-target pi32v2 -mcpu=r3 -Oz -g -flto -fms-extensions -femulated-tls -ffunction-sections -fdata-sections -w` and the rest | passed on; `-integrated-as` is accepted |
| `-mfprev1` | `-Xclang -target-feature -Xclang +fprev1` (`-mcpu=r3` has it already) |
| `-fallow-pointer-null` | `-fno-delete-null-pointer-checks`: a load or store at address 0 stays |
| `-fprefer-gnu-section` | passed on: the fork's clang has the option. A `section` attribute written on a function definition replaces the section an active `#pragma code_seg` gave it; without the option the pragma wins, with a warning. Nothing else changes (below) |
| `-mllvm -pi32v2-large-program=true` | passed on: calls between flash and RAM code are the 6-byte `call.xl` (the 4-byte call reaches 4 MiB) |
| (default C standard) | `-std=gnu11` for C files without `-std`: clang 4's default; the fork's is gnu17 |
| `-g` | `-gdwarf-4` added: the SDK's libraries carry DWARF 4, one version in the program |
| (errors in C) | `implicit-function-declaration`, `implicit-int`, `int-conversion`, `incompatible-(function-)pointer-types`, `return-mismatch` are warnings again: the SDK's sources have them |

### `-fprefer-gnu-section`

Black box, JieLi's clang with and without the option (`-fms-extensions`, `-S`, section of every function and
variable; 5 test files of 10 to 25 definitions):

- **Variables:** no difference. `data_seg`, `bss_seg` and `const_seg` name the section of what follows; a
  `section` attribute on a variable always wins (also over `__declspec(allocate)`, with and without the option).
- **Functions, without the option:** an active `#pragma code_seg` decides, and a `section` attribute on the
  function definition is ignored with `-Wsection` ("section does not match previous declaration"), also inside
  `code_seg(push, ...)`. This is stock clang's behaviour, and the fork's.
- **Functions, with the option:** the `section` attribute of the definition wins, with no warning. An attribute
  on an earlier declaration, or on a redeclaration before the definition, does not (the pragma's section stays,
  warning kept); a function outside any pragma is not affected.

The fork's clang has the option now (`-fprefer-gnu-section`, `-fno-prefer-gnu-section`): the attribute written on
the declarator replaces the implicit one of `code_seg`. For the SDK's builds this decides nothing yet: of the five
sources with these pragmas (`effects_adj.c`, `mem_heap.c`, `custom_cfg.c`, `flfft_core_pi32v2.c`,
`sdram_re_trim.c`) three have them compiled out (`MEDIA_SUPPORT_MS_EXTENSIONS`, `#if 0`, a comment),
`mem_heap.c` is in no application, and `sdram_re_trim.c` needs `CONFIG_SDRAM_RE_TRIM_ENABLE`; none of them has a
function with a `section` attribute and a pragma. The 52 symbols of `effects_adj.c` and `flfft_core_pi32v2.c` that
`demo_audio` keeps are in the same output section in JieLi's ELF and the drop-in's; `mem_heap.c` and
`sdram_re_trim.c` (enabled by hand) give the same section for every function and variable in both compilers,
except the string literals of `str_literal_override` ([below](#known-differences)). The `btmesh` and `wolfssl` sources
that have pragmas are in JieLi's prebuilt libraries.

## Options of JieLi's ld

| Option | Here |
| --- | --- |
| `--plugin FILE` | dropped |
| `--plugin-opt=mcpu=r3` | passed on (`ld.lld` takes it) |
| `--plugin-opt=save-temps` | `--save-temps` |
| `--plugin-opt=-enable-ipra=true`, `-global-merge-on-const`, `-emulated-tls`, `-pi32v2-large-program=true` | `-mllvm=...` |
| `--plugin-opt=-inline-max-allocated-size=32` | `-mllvm=-inline-max-stacksize=32` |
| `--plugin-opt=-used-symbol-file=F` | `--undefined-glob=NAME` for each name in F: the names (tables found by their section) must be kept and their archive members taken; a name nothing defines is not an error |
| `--plugin-opt=-inline-threshold=5` | dropped: the fork's cost model sets the thresholds for size (`adjustInliningThreshold` takes 40 off; with a base under 40 the threshold stops at 0) |
| `--plugin-opt=-mattr=+fprev1` | dropped: part of `mcpu=r3` |
| `--plugin-opt=-pi32v2-always-use-itblock=false`, `-pi32v2-merge-max-offset=4096`, `-pi32v2-enable-simd=true`, `-pi32v2-enable-rep-memop`, `-inline-normal-into-special-section=true`, `-dont-used-symbol-list=...` | dropped: not in the fork's code generator (their effect on size is below) |
| `--plugin-opt=-enable-movable-region=true`, `-movable-region-*` | dropped, with a warning when a map file lists code (`section.txt` of the apps with `CONFIG_*_CODE_MOVABLE`): that code stays where the linker script puts it |
| `-T SCRIPT` | passed on unchanged: the fork's LTO puts data in `.data`, `.bss` and `.rodata`, as JieLi's does, which is what the SDK's scripts place |
| `-M=FILE` | `-Map=FILE` (the map is lld's, much longer; nothing in the SDK reads it) |
| `--start-group` inside `--start-group` | the outer pair only: `ld.lld` refuses nested groups |
| the archives (`.a`) | the members GNU ld would load, as objects, in its order, then the archives: GNU ld scans each archive until nothing more is taken, group by group, and links the members in the order it took them, which is the order of the tables the scripts collect (`*(.initcall)`, `*(.sys_event.*)`); `ld.lld` takes a symbol from the first archive that has it and orders by its own. The symbols come from the archives' own symbol tables and `llvm-nm`, the scripts' `EXTERN` and `ENTRY`. For `hello` this is the same 99 members in the same order as JieLi's link map (JieLi's has seven more, taken for what its code generator asked for: `memcpy` and the soft-float helpers, which `ld.lld` takes the same way). `PI32V2_DROPIN_NATIVE_ARCHIVES=1` leaves it to `ld.lld`, with the C library moved to the end of its group |
| (end of line) | `libclang_rt.builtins-pi32v2.a` and `libpi32v2.a`: soft float, 64-bit divide, `__sync_*` |

## Builds (2026-10-27)

The 14 applications of the SDK `AC79NN_SDK_V1.2.14_2026-10-13` (commit `5fa84a9b2f72`, `make ac791n_...`) build with
JieLi's toolchain `20260730.1` (clean, `-j6`: 4 s for `demo_hello`, 97 s for `demo_DevKitBoard`), and all 14 link
with this drop-in on the fork's branch `pi32v2-dropin` (5 s for `demo_hello`, 72 s for `demo_DevKitBoard`). The
post-build step stops where it does with JieLi's tools (`strip-ini`, `host-client`). Sizes in bytes, the
allocated sections of the linked ELF:

| Application | JieLi | Drop-in | |
| --- | ---: | ---: | --- |
| `demo_hello` | 260 568 | 265 068 | +1.7 % |
| `demo_ble` | 408 208 | 417 204 | +2.2 % |
| `demo_video` | 499 120 | 506 196 | +1.4 % |
| `demo_uvc` | 855 748 | 874 796 | +2.2 % |
| `demo_ui` | 1 827 900 | 1 837 096 | +0.5 % |
| `scan_box` | 1 336 704 | 1 351 396 | +1.1 % |
| `demo_edr` | 735 542 | 744 264 | +1.2 % |
| `demo_audio` | 2 106 106 | 2 162 332 | +2.7 % |
| `demo_DevKitBoard` | 3 927 218 | 3 983 804 | +1.4 % |
| `demo_wifi` | 863 984 | 881 806 | +2.1 % |
| `demo_wifi_ext` | 1 099 580 | 1 113 332 | +1.3 % |
| `wifi_camera` | 2 097 828 | 2 121 028 | +1.1 % |
| `wifi_ipc` | 1 522 300 | 1 535 128 | +0.8 % |
| `wifi_story_machine` | 4 143 194 | 4 193 916 | +1.2 % |

None of them has been run on hardware (fm1-base's Bluetooth build has: [hw run](../hw/fm1-2026-10-27-dropin-ble/README.md)). Every application is 0.5 to 2.7 % larger. Objects of 32 bytes or more that
JieLi's build has and the drop-in's does not come to 0 to 1.2 KB per application; most are statics the fork's
global merge puts in a merged block, the others are on paths the fork's optimizer proves dead (`wifi_camera`'s
1 KB `RalinkRate` is read only for ioctl command 36, and the one ioctl entry, `rt28xx_ap_ioctl`, is called with
command 35809 alone: inlined there, the switch keeps that case; JieLi's LLVM 4 does not propagate that far).

For `demo_hello` the same 99 archive members are linked, in the same order, and every sized object is in the same
section as in JieLi's build. The post-build commands give the same section headers (except the sizes), the same
symbol table text, and `objcopy -O binary` the same bytes of the same ELF; on JieLi's own ELF the listing, section
table, symbol table and section images are byte for byte JieLi's (listing: 188 of 190 000 lines differ, the source
line of a few instructions; `symbol_tbl.txt`: the file of 35 of 992 symbols). Neither toolchain gives the same ELF
twice: one byte of `.text` differs (the build time).

What it took on the fork's side, beyond reading JieLi's bitcode ([LLVM.md](LLVM.md#jielis-bitcode)):

- **Braces in inline assembly.** The SDK's `flfft_core_pi32v2.c` writes `rep %1 { ... iff(...) { ... } }` and
  `if(%1 < 0){ ... }` in `asm` strings. Stock clang turns `{`, `|` and `}` of an asm string into `$(`, `$|` and
  `$)`, LLVM's dialect markers, and the asm printer eats them. JieLi's clang leaves them as written
  ([audit](audits/2026-10-sdk-inline-asm.md#round-3-the-four-applications-that-stopped-in-the-assembler-2026-10-27)),
  and so does the fork's for pi32v2 (`NoAsmVariants`, the hook other targets with no dialects use).
- **A missing return.** The Wi-Fi libraries' `wf_mem_init` has no return when `CONFIG_WIFI_USE_TLSF_MEM` is 0, and
  the Ralink driver's probe tests its status; a branch on that undefined value is undefined behaviour to today's
  optimizer, which removed the driver (270 KB of `demo_wifi`). The fork returns a frozen value there instead.
- **`always_inline_when_const_args`.** JieLi's attribute, on `Init_LwIP` among others: inlined wherever every
  argument is a constant. `demo_wifi_ext` links only when the cases its constant calls do not take are gone.
- **Address 0.** The SDK's `-fallow-pointer-null` comes in its bitcode as `"allow-nullptr-deref"`, read as
  `null_pointer_is_valid`.
- **Word-aligned locals.** The Bluetooth controller builds HCI events in packed (`align 1`) locals and posts them to
  the host task as ints; JieLi's frame layout happens to put them on a word, LLVM's did not, and a misaligned word
  load resets the chip at the first connection ([hw run](../hw/fm1-2026-10-27-dropin-ble/README.md)). Every local of
  a word or more is word-aligned (JieLi's compiler packs them: a `char[5]` at `sp+3`).

## Known differences

What differs from JieLi's output, with the cause:

- **Link-time code generation is the fork's.** Sizes differ a little (below), local names get other numbers,
  other functions are inlined.
- **Library functions stay global.** LLVM's link-time optimizer keeps symbols named like library functions
  (`malloc`, `printf`, `fopen`, ...) external; JieLi's `-dont-used-symbol-list` let it drop them.
  Their callees stay too, so some code the reference drops is present (and its references must resolve).
- **No movable regions.** See above.
- **`#pragma str_literal_override`.** JieLi's clang accepts `#pragma str_literal_override(".sec")` (the one-argument
  form only; `()`, `push` and `pop` make it fail): string literals after it go to `.sec` (flags `aMS`), the first use
  of a text deciding. The fork's clang ignores it. The SDK uses it in `sdram_re_trim.c`, which is compiled out unless
  `CONFIG_SDRAM_RE_TRIM_ENABLE` is defined (no application of the SDK does).
- **`__declspec(allocate)` with `__attribute__((section))`** on one variable: JieLi's clang takes the attribute, the
  fork's the declspec. The SDK has no `__declspec(allocate)`.
- **`make -jN` and the pre-build step.** The SDK's Makefiles run `pre_build` (linker script, symbol list) in parallel
  with the link when the objects are up to date, so the link can read the previous application's files; clean first
  (`make clean_ac791n_...`) when switching applications. This is the same with JieLi's toolchain.
- **ld.lld warnings.** `address (0x2000120) of section .text is not a multiple of alignment (64)`: the script's
  address is explicit, as with GNU ld, which aligns inside the section from the real address; so does `ld.lld`.
- **`.map` and `.lst` details.** The map is lld's; the listing's source lines agree with JieLi's for 99.8 % of the
  instructions (the others differ by a line number).
- **ELF details.** Program headers are page-aligned (0x1000, JieLi's 0x500), an empty `.bss` is `PROGBITS`;
  `objcopy -O binary` of a section gives the same bytes.
