#!/bin/sh
# SPDX-FileCopyrightText: 2026 Julius Vitkauskas
# SPDX-License-Identifier: MIT-0
# Assemble a directory with the layout and tool names of JieLi's Linux toolchain (/opt/jieli: common/bin,
# pi32v2/bin, pi32v2/lib, ...) on the LLVM fork's tools, so that the AC79 SDK's Makefiles build with it.
#
#   tools/dropin/make_dropin.sh [--copy] LLVM_BIN RUNTIME_DIR OUT_DIR
#
# LLVM_BIN     the fork's bin directory (clang, ld.lld, llvm-ar, llvm-nm, llvm-objcopy, llvm-symbolizer)
# RUNTIME_DIR the output of tools/llvm/build_builtins.sh (libclang_rt.builtins-pi32v2.a, libpi32v2.a)
# OUT_DIR      must not exist
# --copy       copy the LLVM binaries and clang's headers into OUT_DIR/llvm instead of linking to them, so that
#              the directory can be moved (or packed) alone; it then needs only Python 3.11+
#
# Nothing of JieLi's toolchain is read or copied. docs/DROPIN.md says what each tool is.
set -eu
copy=0
if [ "${1:-}" = "--copy" ]; then copy=1; shift; fi
[ $# -eq 3 ] || { sed -n '4,13p' "$0" | sed 's/^# \{0,1\}//'; exit 2; }
llvm=$(cd "$1" && pwd) rt=$(cd "$2" && pwd) out=$3
here=$(cd "$(dirname "$0")" && pwd)
repo=$(cd "$here/../.." && pwd)
[ ! -e "$out" ] || { echo "make_dropin: $out exists" >&2; exit 1; }
for f in clang ld.lld llvm-ar llvm-nm llvm-objcopy llvm-symbolizer llvm-readobj llvm-objdump; do
  [ -x "$llvm/$f" ] || { echo "make_dropin: $llvm/$f missing" >&2; exit 1; }
done
for f in libclang_rt.builtins-pi32v2.a libpi32v2.a; do
  [ -f "$rt/$f" ] || { echo "make_dropin: $rt/$f missing (tools/llvm/build_builtins.sh)" >&2; exit 1; }
done
mkdir -p "$out"
out=$(cd "$out" && pwd)
mkdir -p "$out/llvm/bin" "$out/common/bin" "$out/common/lib/pi32v2-dropin" "$out/common/include" \
  "$out/pi32v2/bin" "$out/pi32v2/lib" "$out/pi32v2/include"

# the fork's tools (the driver finds its headers next to the real binary, or in llvm/lib/clang when copied)
for f in clang ld.lld llvm-ar llvm-nm llvm-objcopy llvm-symbolizer llvm-readobj llvm-objdump llvm-mc \
         llvm-size llvm-ranlib llvm-strings llvm-addr2line llvm-readelf; do
  [ -x "$llvm/$f" ] || continue
  if [ $copy = 1 ]; then
    cp -L "$llvm/$f" "$out/llvm/bin/$f"
  else
    ln -s "$(readlink -f "$llvm/$f")" "$out/llvm/bin/$f"
  fi
done
ln -s clang "$out/llvm/bin/clang++"
if [ $copy = 1 ]; then
  resource=$("$llvm/clang" -print-resource-dir)
  mkdir -p "$out/llvm/lib/clang"
  cp -a "$resource" "$out/llvm/lib/clang/"
  # clang finds its resource directory from the binary's place: llvm/bin/../lib/clang/<version>
fi

# the Python tools: the wrapper script, and pi32v2isa with its table for objdump
install -m 755 "$here/jlwrap.py" "$out/common/lib/pi32v2-dropin/jlwrap.py"
mkdir -p "$out/common/lib/pi32v2-isa/isa"
cp -a "$repo/pi32v2isa" "$out/common/lib/pi32v2-isa/pi32v2isa"
find "$out/common/lib/pi32v2-isa" -name __pycache__ -prune -exec rm -rf {} +
cp "$repo/isa/pi32v2.toml" "$out/common/lib/pi32v2-isa/isa/"

# the runtime: what ld appends, and under the names JieLi's lib directories use
cp "$rt/libclang_rt.builtins-pi32v2.a" "$rt/libpi32v2.a" "$out/pi32v2/lib/"
for d in . r1 r1-large r2 r2-large r3 r3-large r4 r4-large r5 r5-large; do
  mkdir -p "$out/pi32v2/lib/$d"
  [ "$d" = . ] && dir=. || dir=$d
  cp "$rt/libclang_rt.builtins-pi32v2.a" "$out/pi32v2/lib/$dir/libcompiler-rt.a"
  ln -sf libcompiler-rt.a "$out/pi32v2/lib/$dir/libcompiler_rt.a"
done

# common/bin: the Python tools by name, and the LLVM ones
for t in clang ar lto-ar lto-wrapper objdump objsizedump llvm-read-version link-version; do
  ln -s ../lib/pi32v2-dropin/jlwrap.py "$out/common/bin/$t"
done
ln -s ../../llvm/bin/llvm-ar "$out/common/bin/llvm-ar"
ln -s ../../llvm/bin/llvm-objcopy "$out/common/bin/objcopy"
# JieLi's gold plugin: ld.lld has the link-time optimizer built in; the file only has to exist
: > "$out/common/bin/LLVMgold.so"

# pi32v2/bin as JieLi's: links to common/bin, and the tools of the target
for t in LLVMgold.so ar clang link-version lto-ar lto-wrapper objcopy objdump objsizedump; do
  ln -s "../../common/bin/$t" "$out/pi32v2/bin/$t"
done
ln -s clang "$out/pi32v2/bin/clang++"
for t in cc cxx ld; do
  ln -s ../../common/lib/pi32v2-dropin/jlwrap.py "$out/pi32v2/bin/$t"
done
ln -s ../../llvm/bin/llvm-nm "$out/pi32v2/bin/nm"
ln -s ../../llvm/bin/llvm-objcopy "$out/pi32v2/bin/strip"

cat > "$out/VERSION" <<EOF
pi32v2 drop-in toolchain (docs/DROPIN.md)
pi32v2-isa: $(git -C "$repo" rev-parse HEAD 2>/dev/null || echo unknown)
$("$llvm/clang" --version | head -1)
ld.lld: $("$llvm/ld.lld" --version)
EOF
echo "$out"
