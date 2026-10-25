#!/bin/sh
# SPDX-FileCopyrightText: 2026 Julius Vitkauskas
# SPDX-License-Identifier: MIT-0
# Build the blink application with the open toolchain only: clang (C and the start-up), ld.lld, and this repo's
# fm1app.py for the .fwsc package.   examples/fm1-blink/build.sh LLVM_BIN_DIR OUTDIR [-DAUTOTEST]
set -eu
bin=$1 out=$2; shift 2
here=$(dirname "$0")
mkdir -p "$out"
"$bin/clang" --target=pi32v2 -O2 -c "$here/crt0.S" -o "$out/crt0.o"
"$bin/clang" --target=pi32v2 -O2 -ffreestanding "$@" -c "$here/blink.c" -o "$out/blink.o"
"$bin/ld.lld" -T "$here/fm1.ld" "$out/crt0.o" "$out/blink.o" -o "$out/blink.elf"
python3 "$here/../../tools/hwtest/fm1app.py" "$out/blink.fwsc" --from-elf "$out/blink.elf"
