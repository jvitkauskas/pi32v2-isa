#!/bin/sh
# SPDX-FileCopyrightText: 2026 Julius Vitkauskas
# SPDX-License-Identifier: MIT-0
# Build the Rust blink: RUSTC, a rustc built against the pi32v2-llvm fork (README.md), with any recent cargo;
# core built from source for the JSON target, clang for the start-up code and the shim, ld.lld to link, fm1app.py
# for the .fwsc package.
#   RUSTC=.../stage1/bin/rustc build.sh LLVM_BIN_DIR OUTDIR [--features autotest]
set -eu
bin=$(cd "$1" && pwd); out=$(mkdir -p "$2" && cd "$2" && pwd); shift 2
here=$(cd "$(dirname "$0")" && pwd)
isa=${PI32V2_ISA:-$here/../..}
"$bin/clang" --target=pi32v2 -mcpu=ac791n -O2 -c "$isa/examples/fm1-blink/crt0.S" -o "$out/crt0.o"
"$bin/clang" --target=pi32v2 -mcpu=ac791n -O2 -ffreestanding -c "$here/shim.c" -o "$out/shim.o"
python3 "$here/make_frame.py" "$here/assets/ferris.png" "$out/frame.bin"
# the toolchain package's builtins (compiler-rt and the __sync_* functions read-modify-write atomics call), if there
rt=$(ls "$bin"/../lib/clang/*/lib/pi32v2/libclang_rt.builtins.a 2>/dev/null | head -1 || true)
cd "$here"
PATH="$bin:$PATH" RUSTFLAGS="-C link-arg=-T$isa/examples/fm1-blink/fm1.ld -C link-arg=$out/crt0.o -C link-arg=$out/shim.o${rt:+ -C link-arg=$rt}" \
  FM1_FRAME="$out/frame.bin" RUSTC_BOOTSTRAP=1 RUSTC="${RUSTC:?set RUSTC to the pi32v2 rustc}" cargo build --release --target "$here/pi32v2-none.json" \
  -Zbuild-std=core,compiler_builtins -Zbuild-std-features=compiler-builtins-mem -Zjson-target-spec \
  --target-dir "$out/target" "$@"
cp "$out/target/pi32v2-none/release/blink" "$out/blink.elf"
python3 "$isa/tools/hwtest/fm1app.py" "$out/blink.fwsc" --from-elf "$out/blink.elf"
