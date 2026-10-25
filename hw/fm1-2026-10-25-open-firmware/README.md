# FM-1 and SMK-37, 2026-10-25: m-bootloader and fm1-base from the LLVM toolchain

Both built with the LLVM fork's clang and ld.lld (fork 3a1abdee0), nothing of JieLi's in the build: a
JieLi-toolchain-shaped directory whose `pi32v2/bin/clang` and `ld` are ours (JieLi-only flags and LTO-plugin
options dropped), `common/bin/objcopy` llvm-objcopy and `common/bin/objdump` this repo's (the builds parse its
text).

## m-bootloader 1.2 (64b74d0)

`make` with `CLANG`, `LINK` (ld.lld; LTO in the linker) and `OBJCOPY` overridden; the project's own checks
(`check_build.py`, `bankcb.py check`) pass.

| | FM-1 | SMK-37 Pro |
| --- | --- | --- |
| Payload (slot 14368 bytes; JieLi's build) | 13284 (12920) | 14336 (13984) |
| Boot to the firmware | yes, 755 ms to USB (JieLi's build of the same source 731 ms) | yes (USB after ~33 s, the same with JieLi's build and the stock bootloader: the firmware's first descriptor replies time out after a reset from download mode) |
| Menu and display | yes | yes |
| Startup key into download mode | REC | SEQ REC |
| Download mode from the running firmware, full flash read | yes, CRC32 matches | yes, CRC32 matches; factory calibration and its copy found |
| WIPE USER DATA | erases VM [BA000,DA000) and BTIF [EC000,ED000), as FM-1 016's table declares; all erased to FF; boot, app, SEQ64 (18 sectors of data) and the rest byte-identical | erases [9D000,C1000) (VM and BTIF, adjacent); all FF; boot, app, USRTRIM calibration (`trimdat`), USRFLASH presets, USR byte-identical |

Wipe method: a full image before, the wipe from the menu, the startup key held through the restart into download
mode (so the firmware does not rewrite its records), a full image after, compared sector by sector. A first FM-1 run
that let the firmware boot in between showed the firmware recreating its VM and BTIF records (bits 0 -> 1 there:
the erase had happened).

Not exercised: the update path (M-UPGRADE packages), BOOT ANYWAY.

## fm1-base template (no Bluetooth)

`tools/build.py template --no-ble` with `JIELI_TOOLCHAIN` pointing at the directory above: all of the build's checks
pass; app 80132 bytes (JieLi's compiler: 80172). Installed with M-Flasher on the FM-1 (with the m-bootloader above):
starts, enumerates as `TEMPLATE FM-1` (fm1-base) with its USB-MIDI port; screen, keys and sound work (checked by
the owner).

Backups were taken before every write; the RAM and flash images stay on the desktop.
