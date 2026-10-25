# Using the LLVM toolchain

The pi32v2 toolchain is the LLVM fork ([LLVM.md](LLVM.md)) built as one package: `clang`, `ld.lld` and LLVM's
binary tools for the PI32V2 target only, statically linked, with compiler-rt's builtins and this repo's runtime.
Nothing of JieLi's is needed to build firmware with it.

## Building the package

```sh
git clone --branch pi32v2 https://github.com/jvitkauskas/pi32v2-llvm.git LLVM
tools/llvm/package.sh LLVM BUILD /opt/pi32v2-llvm       # about an hour on 8 cores; PREFIX.tar.xz next to PREFIX
```

It needs CMake, Ninja, a C++ compiler and Python 3; ccache and `ld.lld` are used when present. The tarball unpacks
anywhere: the tools find their headers and libraries relative to themselves. `PREFIX/VERSION` names the commits
it was built from.

| In the package | What |
| --- | --- |
| `bin/clang`, `bin/pi32v2-clang` | C compiler and assembler; the target is `pi32v2` by default |
| `bin/ld.lld`, `bin/pi32v2-ld` | the linker (JieLi's relocations, [LINKER.md](LINKER.md) section 3) |
| `bin/llvm-objdump`, `bin/pi32v2-objdump`, `llvm-readelf`, `llvm-nm`, `llvm-size`, `llvm-objcopy`, `llvm-ar`, `llvm-mc`, ... | binary tools |
| `lib/clang/23/lib/pi32v2/libclang_rt.builtins.a` | compiler-rt's builtins (soft float, 64-bit divide, ...) and the `__sync_*` atomics; the driver links it |
| `lib/clang/23/include` | clang's own headers (`stdint.h`, `stdarg.h`, ...) |

There is no C library yet: firmware brings its own start-up code and linker script, and links with
`-nostartfiles -nolibc`.

## Compiling

```sh
pi32v2-clang -mcpu=ac791n -Os -ffreestanding -c main.c -o main.o
pi32v2-clang -mcpu=ac791n -c crt0.S -o crt0.o                      # assembly goes through the preprocessor
pi32v2-clang -mcpu=ac791n -nostartfiles -nolibc -T app.ld crt0.o main.o -o app.elf
```

- `-mcpu`: `generic` (no floating point unit), `r3` (JieLi's name for the AC79 core: the single-precision FPU)
  or `ac791n` (the FM-1's chip: as `r3`). Without it the compiler uses no float instructions, as JieLi's does.
- The C conventions are JieLi's ([ABI.md](ABI.md)), so objects mix with code built by JieLi's compiler.
- `__attribute__((interrupt))` makes an interrupt handler (saves what it uses, returns with `rti`); JieLi's
  `__builtin_pi32v2_*` (`cli`, `sti`, `csync`, `lockset`, `clz`, `uextra`, ...) are there
  ([COMPILER.md](COMPILER.md) section 3). `__builtin_pi32v2_popcount` is computed in software: the AC791N runs
  the `popcnt` instruction as a nop.
- Atomics: `__atomic_*`/`__sync_*` up to 32 bits; read-modify-write operations mask interrupts and take the
  shared core lock.
- The assembler takes JieLi's syntax ([ASSEMBLER.md](ASSEMBLER.md)); `pi32v2-objdump -d` prints it.

## An FM-1 application

`examples/fm1-blink` is a complete one: start-up code, a linker script for m-bootloader's layout (code from
0x02000120 in the flash window, data and stacks in RAM), a timer interrupt handled in C. To make the `.fwsc`
package M-Flasher installs:

```sh
examples/fm1-blink/build.sh PREFIX/bin OUT                   # OUT/blink.fwsc
python3 tools/hwtest/fm1app.py app.fwsc --from-elf app.elf   # any application linked at 0x02000120
```

Before installing anything, take a backup with M-Flasher (`m-flasher backup`); `m-flasher restore` puts it back.
