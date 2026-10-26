#!/bin/sh
# SPDX-FileCopyrightText: 2026 Julius Vitkauskas
# SPDX-License-Identifier: MIT-0
# What the AC79 SDK's post-build script runs on the linked ELF, with a toolchain directory's tools, written to
# OUTDIR: the listing with source lines, the section table, the symbol listings, the section images and the
# application image they make (text, data, dynamic data, RAM data, cache RAM data, in that order).
#
#   tools/dropin/postbuild.sh TOOL_DIR ELF OUTDIR       TOOL_DIR is JieLi's pi32v2/bin or the drop-in's
#
# The SDK's own Linux script runs these commands from the wrong directory and then hands the packaging to a
# remote service (host-client) or to Windows programs (isd_download.exe, fw_add.exe, ufw_maker.exe): none of
# that is available, so the firmware packages are not made here.
set -eu
[ $# -eq 3 ] || { sed -n '9,10p' "$0" | sed 's/^# \{0,1\}//'; exit 2; }
tool=$1 elf=$2 out=$3
mkdir -p "$out"
"$tool/objdump" -D -print-dbg -mcpu=r3 "$elf" > "$out/sdk.lst"
"$tool/objdump" -section-headers -address-mask=0x1ffffff "$elf" > "$out/headers.txt"
"$tool/objdump" -t "$elf" > "$out/symtab.txt"
"$tool/objsizedump" -lite -skip-zero -enable-dbg-info "$elf" | sort -k 1 > "$out/symbol_tbl.txt"
"$tool/objsizedump" -lite -skip-zero "$elf" | sort -k 1 > "$out/map.lit"
for s in text data dynamic_data ram0_data cache_ram_data; do
  "$tool/objcopy" -O binary -j ".$s" "$elf" "$out/$s.bin"
done
cat "$out/text.bin" "$out/data.bin" "$out/dynamic_data.bin" "$out/ram0_data.bin" "$out/cache_ram_data.bin" > "$out/app.bin"
ls -l "$out/app.bin"
