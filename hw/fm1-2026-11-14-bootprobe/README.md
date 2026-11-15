# FM-1 hardware run, 2026-11-14: the application's entry state, under both bootloaders

What an FM-1 application finds when its bootloader calls it: the registers, the boot object `r0` points
at, the clocks, the flash controller, the debug registers. It also times instruction blocks running from
flash. An emulator that starts an application directly has to set up the same things. This came up while
comparing [fm1-emu](https://github.com/joakimeriksson/fm1-emu) with the chip.

**Unit:** Julius Vitkauskas's M-VAVE FM-1 (AC791N), flash chip 0x856014, chip key 0x980F.

**The probe:** [src/](src/), a flash-resident application, built with [src/build.sh](src/build.sh) and
packed by [tools/hwtest/fm1app.py](../../tools/hwtest/fm1app.py).
- Its entry ([src/crt0.S](src/crt0.S)) saves r0..r15 and every special register before anything else runs.
- [src/bootprobe.c](src/bootprobe.c) then records:
  - the retained area and vectors;
  - 64 bytes at `r0`;
  - the clock, ANA/PLL, SFC/SFCENC, corex2 and debug registers.
- It times 16 blocks of 256 copies each, cold and then warm, with C0_TL_CKCNTL. Then it asks for download
  mode.
- A run-ram reader reads the record back from 0x01C7C000 (2 KiB).
- [decode.py](decode.py) prints the record ([decoded.txt](decoded.txt): both records, with the differences
  marked).

**Sequence:**
1. A full flash backup.
2. The probe installed as the application with m-bootloader 2.3 in place, and run:
   [record-m-bootloader-2.3.bin](record-m-bootloader-2.3.bin).
3. M-VAVE's stock `uboot.boot` from firmware 015 installed in the boot area (`m-flasher bootloader --stock`),
   and run: [record-stock-uboot-015.bin](record-stock-uboot-015.bin). The stock loader accepted an
   application area holding only `app_area_head` and `app.bin`.
4. The backup restored and verified. The unit is back on m-bootloader and "FM-1 901".

## Results

| At entry | stock `uboot.boot` (015) | m-bootloader 2.3 |
| --- | --- | --- |
| `r0` | 0x01C7FE08 | 0x01C7FE08 |
| boot object at `r0` | 0x01C7FE20, 0x4000, 0x02000000, chip key 0x980F, trim 0xF80A, then 8 bytes of 0xFF (a blank MAC/CRC) | identical |
| `r1` | 0x02000120 (the entry) | 0x02000120 |
| `psr`, `icfg` | 0, 0x02050500 | 0, 0x02050500 |
| `sp`, `ssp`, `usp` | 0x01C05E70, 0x01C05C40, 0x01C01114 | 0x01C0A7B8, 0x01C09800, 0x01C01114 |
| `reti`, `rets`, `rete`, `retx` | 0x01C02036, 0x01C0528E, 0, 0 | 0x01C02070, 0x01C02DEE, 0, 0 |
| other registers | the loader's scratch | the loader's scratch |
| clocks | CLK_CON2 = 6 (360 MHz); SYS_DIV 0x00010200; PLL 0x45400203 / 0x3F503026, PLL2 0x0940022B / 0x0750310C | identical |
| SFC 0x40200 | CON 0x809803B5, BAUD 1, CODE 0x965D, BASE 0x4000 | identical |
| SFCENC CON | 1 (the other registers read 0: write-only) | identical |
| EMU_CON, DBG_EN, PC limits | 3, 0, both 0..0x07FFFFFF | identical |
| download-mode marker at 0x01C7FD80 | cleared | cleared |
| vector 1 (0x01C7FE04) | 0x01E0024E, a boot-ROM routine that saves state and spins | identical |

Apart from stack and return addresses, nothing an application can read tells the two loaders apart.

**Timing from flash, at 360 MHz:** cycles for 256 copies.
- **Warm:** a block costs what it does from RAM ([fm1-2026-11-15-excprobe](../fm1-2026-11-15-excprobe/README.md),
  group 7). A load from flash that hits the cache costs 1 cycle, half a RAM load.
- **Cold:** about 480 extra cycles per 64 bytes of code.

| Block | cold | warm |
| --- | --- | --- |
| nop | 4128 | 258 |
| two independent adds | 12098 | 514 |
| load | 7881 | 514 |
| load from flash, cache hit | 7857 | 258 |
| divide | 8078 | 2553 |
| taken branch | 4129 | 1971 |
| call + goto + rts | 12142 | 5861 |
