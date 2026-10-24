<!-- SPDX-FileCopyrightText: 2026 Julius Vitkauskas -->
<!-- SPDX-License-Identifier: CC0-1.0 -->

# Open assembler toolchain overlay

Create a directory accepted by the FM-1 projects as `JIELI_TOOLCHAIN`:

```sh
export PI32V2_TOOLCHAIN=/path/to/jieli-linux-toolchains-20260730.1
python3 tools/overlay/create.py /tmp/open-pi32v2 \
    --toolchain "$PI32V2_TOOLCHAIN" --repo "$PWD"
export JIELI_TOOLCHAIN=/tmp/open-pi32v2
export JIELI_DOCKER=0
```

The output must be a new directory. Python 3.11+, GNU `cpp` and GNU `objcopy`
are required on `PATH`. The source checkout and original toolchain stay in
place: the overlay contains Python wrappers, a JSON configuration and symlinks,
with no copied vendor executables. Paths containing spaces work. The wrappers
preserve the calling project's working directory and use the configured
checkout through `PYTHONPATH`; no package installation is necessary. Run native
Linux builds; the projects' default Docker mounts do not include the checkout,
Python or host GNU tools.

Both `common/bin/` and `pi32v2/bin/` contain:

- `clang`: `-c` on C or LLVM IR (`.ll`/`.bc`, needed by Felucca's size pass)
  becomes JieLi `clang -S` with the same compilation flags, followed by
  `python3 -m pi32v2isa as`. Uppercase `.S` runs GNU `cpp -P -x
  assembler-with-cpp` with the include/define flags first; lowercase `.s` is
  assembled directly. One source per compilation is supported, with `-o`
  optional. Response files are expanded. Compiler dependency files retain
  their original object target. Assembler include paths retain the source
  directory and `-I` directories.
- `objcopy`: GNU `objcopy -I elf32-little ...`, retaining all caller arguments.
  For binary extraction only, a temporary ELF copy replaces non-power-of-two
  program-header alignments with 1: JieLi ld emits `0x500`, which GNU binutils
  2.44 refuses. Sections, segment addresses and the original ELF stay intact.
  This workaround is recorded as `objcopy-alignment` in the audit log.
- `objdump`, `ld`, `lto-wrapper`: explicit JieLi passthrough executables.
- `LLVMgold.so`: symlink to JieLi's plugin.

`-E`, `-S`, `-emit-llvm`, compiler queries and link-driver invocations pass
through. Effective `-flto`/`-flto=...` passes through unchanged and prints a
notice: LLVM bitcode cannot use the open assembler. Code generated during LTO
linking still uses JieLi's backend and assembler. The overlay never silently
falls back after an open assembler error. Debug directives remain subject to
[the assembler's limits](../../docs/ASSEMBLER.md).

Replace individual tools when creating a new overlay:

```sh
python3 tools/overlay/create.py /tmp/open-pi32v2-next \
    --repo "$PWD" --objdump /path/to/replacement-objdump \
    --ld /path/to/replacement-ld --lto-wrapper /path/to/replacement-wrapper \
    --llvmgold /path/to/replacement/LLVMgold.so --objcopy /usr/bin/objcopy
```

Each replacement is one executable path (a small launcher can supply arguments).
The generated `overlay.json` also makes these choices visible and editable;
`LLVMgold.so` is a symlink and can be replaced separately.

For an audit trail, set `PI32V2_OVERLAY_LOG` to an absolute JSONL filename and
`PI32V2_OVERLAY_SAVE_ASM` to an absolute scratch directory. The log records the
working directory, routing, source, output and arguments for each invocation.
Saved assembly follows the object's path relative to the calling directory;
outputs outside that directory receive a path hash. Keep these diagnostics
outside the checkout. See [BUILDING-OPEN.md](../../docs/BUILDING-OPEN.md) for
firmware comparisons and reproduction steps.

Compare saved build directories (exit 1 means differences or no products):

```sh
python3 tools/overlay/compare.py /tmp/reference-build /tmp/open-build
python3 tools/overlay/compare.py /tmp/reference-build /tmp/open-build --json > /tmp/comparison.json
```

The comparison covers every `.o`, `.elf`, `.bin`, `.fwsc` and `.boot`, including
missing files. JSON includes exact byte sizes, SHA-256 values, first differing
byte and the number of unequal bytes at matching offsets (not an edit distance).
