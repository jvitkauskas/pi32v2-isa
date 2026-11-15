#!/bin/sh
# SPDX-FileCopyrightText: 2026 Julius Vitkauskas
# SPDX-License-Identifier: MIT-0
# Build the boot probe package: src/build.sh OUTDIR (TOOLCHAIN: JieLi's pi32v2 clang and ld.lld, e.g. the
# oracle release's common/bin; run from anywhere inside this repository)
set -eu
here=$(cd "$(dirname "$0")" && pwd)
repo=$(git -C "$here" rev-parse --show-toplevel)
bin=${TOOLCHAIN:?set TOOLCHAIN to the directory holding clang and ld.lld}
out=$1
mkdir -p "$out"
"$bin/clang" --target=pi32v2 -mcpu=r3 -O2 -c "$here/crt0.S" -o "$out/crt0.o"
"$bin/clang" --target=pi32v2 -mcpu=r3 -O2 -ffreestanding -Wall -Werror -c "$here/bootprobe.c" -o "$out/bootprobe.o"
"$bin/ld.lld" -T "$here/fm1.ld" "$out/crt0.o" "$out/bootprobe.o" -o "$out/bootprobe.elf"
python3 "$repo/tools/hwtest/fm1app.py" "$out/bootprobe.fwsc" --from-elf "$out/bootprobe.elf"
