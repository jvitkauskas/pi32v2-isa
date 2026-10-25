#!/bin/sh
# SPDX-FileCopyrightText: 2026 Julius Vitkauskas
# SPDX-License-Identifier: MIT-0
# Build compiler-rt's generic builtins (soft floating point, 64-bit multiply and divide, ...) for pi32v2 with the
# LLVM PI32V2 target: libclang_rt.builtins-pi32v2.a in OUTDIR; and this repo's runtime (tools/llvm/runtime: the
# __sync_* functions): libpi32v2.a.
#   tools/llvm/build_builtins.sh LLVM_BIN_DIR LLVM_PROJECT_DIR OUTDIR [-O2]
set -eu
bin=$1 src=$2/compiler-rt/lib/builtins out=$3 opt=${4:--O2}
mkdir -p "$out"
srcs=$(python3 -c "
import re, sys
s = open(sys.argv[1]).read()
print(' '.join(x for x in re.search(r'set\(GENERIC_SOURCES(.*?)\)', s, re.S).group(1).split() if x.endswith('.c')))
" "$src/CMakeLists.txt")
for f in $srcs; do
  "$bin/clang" --target=pi32v2 "$opt" -ffreestanding -fno-builtin -c "$src/$f" -o "$out/$(basename "$f" .c).o"
done
rm -f "$out/libclang_rt.builtins-pi32v2.a"
"$bin/llvm-ar" rcs "$out/libclang_rt.builtins-pi32v2.a" "$out"/*.o
here=$(dirname "$0")
mkdir -p "$out/rt"
for f in "$here"/runtime/*.c; do
  "$bin/clang" --target=pi32v2 "$opt" -ffreestanding -c "$f" -o "$out/rt/$(basename "$f" .c).o"
done
rm -f "$out/libpi32v2.a"
"$bin/llvm-ar" rcs "$out/libpi32v2.a" "$out"/rt/*.o
echo "$out/libclang_rt.builtins-pi32v2.a $out/libpi32v2.a"
