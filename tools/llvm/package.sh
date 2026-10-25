#!/bin/sh
# SPDX-FileCopyrightText: 2026 Julius Vitkauskas
# SPDX-License-Identifier: MIT-0
# Build the pi32v2 toolchain package: clang, ld.lld and the binary tools of the LLVM fork (only the PI32V2
# target, statically linked, no assertions), compiler-rt's builtins with this repo's runtime folded in, and
# pi32v2- prefixed names, installed in PREFIX and packed as a tarball next to it.
#
#   tools/llvm/package.sh LLVM_PROJECT_DIR BUILD_DIR PREFIX
#
# The result runs on any x86-64 Linux; clang defaults to --target=pi32v2 (also as pi32v2-clang), links with
# ld.lld and finds the builtins itself. There is no C library yet: link firmware with -nostartfiles -nolibc and
# its own start-up code and linker script (examples/fm1-blink).
set -eu
src=$(cd "$1" && pwd) build=$2 prefix=$3
here=$(cd "$(dirname "$0")" && pwd)
tools="llvm-ar;llvm-ranlib;llvm-nm;llvm-objdump;llvm-objcopy;llvm-readobj;llvm-readelf;llvm-size;llvm-strip;llvm-mc;llvm-addr2line;llvm-symbolizer;llvm-strings"
launcher=""
command -v ccache > /dev/null && launcher="-DCMAKE_C_COMPILER_LAUNCHER=ccache -DCMAKE_CXX_COMPILER_LAUNCHER=ccache"
linker=""
command -v ld.lld > /dev/null && linker="-DLLVM_USE_LINKER=lld"
# shellcheck disable=SC2086
cmake -G Ninja -S "$src/llvm" -B "$build" $launcher $linker \
  -DCMAKE_BUILD_TYPE=Release -DLLVM_ENABLE_ASSERTIONS=OFF \
  -DLLVM_TARGETS_TO_BUILD="" -DLLVM_EXPERIMENTAL_TARGETS_TO_BUILD=PI32V2 \
  -DLLVM_ENABLE_PROJECTS="clang;lld" -DLLVM_DEFAULT_TARGET_TRIPLE=pi32v2 \
  -DLLVM_BUILD_STATIC=ON -DLLVM_ENABLE_PLUGINS=OFF -DLLVM_ENABLE_ZLIB=OFF -DLLVM_ENABLE_ZSTD=OFF \
  -DLLVM_ENABLE_LIBXML2=OFF -DLLVM_ENABLE_LIBEDIT=OFF -DLLVM_ENABLE_LIBPFM=OFF \
  -DLLVM_INCLUDE_TESTS=OFF -DLLVM_INCLUDE_EXAMPLES=OFF -DLLVM_INCLUDE_BENCHMARKS=OFF -DLLVM_INCLUDE_DOCS=OFF \
  -DCLANG_ENABLE_ARCMT=OFF -DCLANG_ENABLE_STATIC_ANALYZER=OFF -DCLANG_PLUGIN_SUPPORT=OFF \
  -DLLVM_INSTALL_TOOLCHAIN_ONLY=ON -DLLVM_TOOLCHAIN_TOOLS="$tools" \
  -DLLVM_DISTRIBUTION_COMPONENTS="clang;lld;clang-resource-headers;$tools" \
  -DCMAKE_INSTALL_PREFIX="$prefix"
ninja -C "$build" install-distribution-stripped

# compiler-rt's builtins and the __sync_* runtime in one archive, where the driver looks for it
"$here/build_builtins.sh" "$prefix/bin" "$src" "$build/runtime" > /dev/null
resource=$("$prefix/bin/clang" -print-resource-dir)
mkdir -p "$resource/lib/pi32v2"
rm -f "$resource/lib/pi32v2/libclang_rt.builtins.a"
"$prefix/bin/llvm-ar" rcs "$resource/lib/pi32v2/libclang_rt.builtins.a" "$build/runtime"/*.o "$build/runtime"/rt/*.o

# pi32v2- names (the driver takes the target from the prefix)
for t in clang clang++ ld.lld; do
  ln -sf "$t" "$prefix/bin/pi32v2-$t"
done
for t in $(echo "$tools" | tr ';' ' '); do
  ln -sf "$t" "$prefix/bin/pi32v2-${t#llvm-}"
done
ln -sf ld.lld "$prefix/bin/pi32v2-ld"

version=$(git -C "$src" describe --tags --always 2>/dev/null || echo unknown)
cat > "$prefix/VERSION" <<EOF
pi32v2 LLVM toolchain
llvm-project: $(git -C "$src" rev-parse HEAD 2>/dev/null || echo unknown) ($version)
pi32v2-isa: $(git -C "$here" rev-parse HEAD 2>/dev/null || echo unknown)
$("$prefix/bin/clang" --version | head -1)
EOF
name=$(basename "$prefix")
tar -C "$(dirname "$prefix")" -cJf "$prefix.tar.xz" "$name"
echo "$prefix.tar.xz"
