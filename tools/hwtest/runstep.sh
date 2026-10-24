#!/bin/sh
# SPDX-FileCopyrightText: 2026 Julius Vitkauskas
# SPDX-License-Identifier: MIT-0
# RAM-only batches on the FM-1 desktop: runstep.sh DIR WAVE. Stop on a hang or stale USB.
set -u
state_dir=${HWTEST_STATE_DIR:-/tmp/hw}
cd "$1" || exit 1
mkdir -p "$state_dir"
sed -n 's/^m-flasher run-ram //p' "run-$2.sh" | while read -r line; do
  eval "set -- $line"
  name=$(basename "$1" .bin)
  if ! timeout -k 2 10 lsusb -d 4c4a:8057 > "$state_dir"/USBSTATUS || ! grep -q 4c4a:8057 "$state_dir"/USBSTATUS; then
    echo "$name: USB NOT READY; stopped before upload"; exit 4
  fi
  slot=$3
  last=$(cat "$state_dir"/LASTSLOT 2>/dev/null || echo 0)
  if test "$((last))" -eq "$((slot))"; then
    echo "$name: SLOT COLLISION; stopped before upload"; exit 5
  fi
  echo "$slot" > "$state_dir"/LASTSLOT
  if sudo timeout -k 2 45 /opt/m-flasher/m-flasher run-ram "$@" > "$name.log" 2>&1; then
    echo "$name: ok"; continue
  fi
  sleep 4
  if ! timeout -k 2 10 lsusb -d 4c4a: > "$state_dir"/USBSTATUS; then
    echo "$name: HANG (USB inspection timed out)"; exit 2
  fi
  if grep -q 4c4a:c755 "$state_dir"/USBSTATUS; then
    echo "$name: RESET"
    rm -f "$state_dir"/LASTSLOT
    sudo timeout -k 2 60 /opt/m-flasher/m-flasher download-mode > "$name.recovery.log" 2>&1 || exit 3
    sleep 3
    timeout -k 2 10 lsusb -d 4c4a:8057 > "$state_dir"/USBSTATUS && grep -q 4c4a:8057 "$state_dir"/USBSTATUS || exit 3
  else
    echo "$name: HANG"; exit 2
  fi
done
