# fm1-blink-rust: Rust on the FM-1

[fm1-blink](../fm1-blink/) in Rust (`no_std`), with a picture: Ferris on the screen with "Hello from Rust", and
the PLAY LED blinking once a second, timed by a 100 Hz TIMER5 interrupt; holding PLAY for two seconds puts the unit
in USB download mode. The `autotest` feature counts 300 ticks instead, writes `BLNK`, the tick count, the crystal
count TIMER4 measured over them, the port A outputs and `RUST` to 0x01C7C000, and goes to download mode by itself
(`tools/hwtest/runapp.sh` reads the record back).

A proof of concept: it needs the patched rustc of [jvitkauskas/pi32v2-rust](https://github.com/jvitkauskas/pi32v2-rust)
(Rust 1.99.1) built against the [pi32v2-llvm](https://github.com/jvitkauskas/pi32v2-llvm) fork's LLVM. On the FM-1
([hw/fm1-2026-10-25-rust](../../hw/fm1-2026-10-25-rust/README.md)) the `autotest` build counted 300 interrupts in
72000008 crystal counts (3.00000 s at 24 MHz), and the picture showed.

| File | What |
| --- | --- |
| `src/main.rs` | GPIO, the LED shift registers, the PLAY key, TIMER5 and its handler's work, download mode |
| `src/lcd.rs` | the ST7789 panel on SPI1: set-up, and the picture sent from flash through a RAM buffer by DMA |
| `make_frame.py`, `assets/ferris.png` | the picture: Ferris ([rustacean.net](https://rustacean.net/), CC0, by Karen Rustad Tölva) and the text (Pillow's Aileron, CC0) on a 240x240 frame, as RGB565; `build.sh` runs it (needs Pillow) |
| `shim.c` | what Rust cannot say on pi32v2 yet: the interrupt entry (`__attribute__((interrupt))`, which calls Rust) and `cli`, `csync`, the `icfg` write |
| `pi32v2-none.json` | the target specification (`"arch": "pi32v2"`, the LLVM data layout, `ld.lld`) |
| `build.sh` | the build: clang for `fm1-blink`'s start-up code and the shim, cargo with `-Zbuild-std`, `ld.lld` with `fm1-blink`'s linker script, `fm1app.py` for the package |
| `rustc/rustc-1.99.1-pi32v2.patch` | the patch to rustc 1.99.1 (MIT OR Apache-2.0, rustc's licence), the commit of the `pi32v2` branch of [pi32v2-rust](https://github.com/jvitkauskas/pi32v2-rust) |

## The patched rustc

The patch adds three things to rustc (62 lines):
- pi32v2 to the LLVM targets rustc initializes (`compiler/rustc_llvm`);
- the C calling convention for `"arch": "pi32v2"` JSON targets (`compiler/rustc_target/src/callconv/pi32v2.rs`),
  as clang lowers it for the target: aggregates by reference to a copy, results through a hidden pointer, scalars
  directly with integers widened to 32 bits ([docs/ABI.md](../../docs/ABI.md));
- the dispatch to it.

Rust's own calling convention between Rust functions needs no change.

```sh
# LLVM from the fork, with the host's backend too (rustc builds build scripts for the host)
cmake -G Ninja -S pi32v2-llvm/llvm -B build-rust -DCMAKE_BUILD_TYPE=Release \
  -DLLVM_TARGETS_TO_BUILD=X86 -DLLVM_EXPERIMENTAL_TARGETS_TO_BUILD=PI32V2 \
  -DLLVM_INCLUDE_TESTS=OFF -DLLVM_INCLUDE_EXAMPLES=OFF -DLLVM_INCLUDE_BENCHMARKS=OFF \
  -DCMAKE_INSTALL_PREFIX=$PWD/llvm-rust
ninja -C build-rust install

# rustc 1.99.1 (it uses LLVM 23, as the fork), patched: the fork's branch, or the source tarball and the patch
git clone --depth 1 --branch pi32v2 https://github.com/jvitkauskas/pi32v2-rust.git rustc-1.99.1-src
#   or: curl -LO https://static.rust-lang.org/dist/rustc-1.99.1-src.tar.xz && tar xJf rustc-1.99.1-src.tar.xz
#       (cd rustc-1.99.1-src && patch -p1 < .../examples/fm1-blink-rust/rustc/rustc-1.99.1-pi32v2.patch)
cd rustc-1.99.1-src
cat > bootstrap.toml <<EOF
change-id = "ignore"
[llvm]
download-ci-llvm = false
[build]
extended = false
docs = false
[rust]
channel = "dev"
[target.x86_64-unknown-linux-gnu]
llvm-config = "$PWD/../llvm-rust/bin/llvm-config"
EOF
./x.py build --stage 1 library      # about 6 minutes on 8 cores after LLVM; build/host/stage1/bin/rustc
```

## Building the example

Any recent cargo works with that rustc (`RUSTC_BOOTSTRAP=1` lets it use the `-Z` options):

```sh
RUSTC=.../rustc-1.99.1-src/build/host/stage1/bin/rustc examples/fm1-blink-rust/build.sh LLVM_BIN_DIR OUT
RUSTC=... examples/fm1-blink-rust/build.sh LLVM_BIN_DIR OUT --features autotest
```

`LLVM_BIN_DIR` holds the fork's `clang` and `ld.lld` (the toolchain package's `bin`). The result is `OUT/blink.fwsc`
for M-Flasher (take a backup first).

## Limits

- No inline `asm!` or `global_asm!`: rustc supports them per architecture, and pi32v2 is not one of its
  architectures yet (assembly goes in `.S` or C files, as `shim.c`).
- No interrupt ABI in Rust: a C (or assembly) entry calls Rust.
- Only `core` (and `alloc`, with an allocator): bare-metal `no_std`, as usual for embedded Rust.
- Read-modify-write atomics become calls to the `__sync_*` functions of the toolchain's runtime, as in C; loads
  and stores are plain.
