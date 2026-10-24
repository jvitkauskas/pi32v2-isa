#!/bin/sh
# SPDX-FileCopyrightText: 2026 Julius Vitkauskas
# SPDX-License-Identifier: MIT-0
# Run only after a verified backup. DIR contains app.fwsc, reset.bin and reader.bin.
# Reader/reset use 0x01C28000, the flasher's own loader uses 0x01C20000.
set -eu
cd "$1"
mkdir -p /tmp/hw
timeout -k 2 10 lsusb -d 4c4a:8057 > usb-before.log
grep -q 4c4a:8057 usb-before.log
sudo timeout -k 2 120 /opt/m-flasher/m-flasher firmware app.fwsc --yes > install.log 2>&1
echo 0x01C20000 > /tmp/hw/LASTSLOT
echo 0x01C28000 > /tmp/hw/LASTSLOT
sudo timeout -k 2 5 /opt/m-flasher/m-flasher run-ram reset.bin --addr 0x01C28000 > start.log 2>&1 || true
sleep 20
if ! timeout -k 2 10 lsusb -d 4c4a:8057 > usb-after.log || ! grep -q 4c4a:8057 usb-after.log; then
  echo 'NOT IN DOWNLOAD MODE: stop; user recovery required'
  exit 2
fi
# The reset cleared the loaded plug-in; read retained results through a fresh RAM plug-in.
rm -f /tmp/hw/LASTSLOT
echo 0x01C28000 > /tmp/hw/LASTSLOT
sudo timeout -k 2 60 /opt/m-flasher/m-flasher run-ram reader.bin --addr 0x01C28000 --read 0x01C30000:0x4D000 -o ram.bin > read.log 2>&1
echo 'Returned to download mode; retained RAM captured'
