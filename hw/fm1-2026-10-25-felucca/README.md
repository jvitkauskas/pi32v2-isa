# FM-1, 2026-10-25: Felucca from the LLVM toolchain

Felucca (the community firmware) built from one source tree with JieLi's toolchain and with the LLVM fork
(through the same JieLi-shaped directory as `hw/fm1-2026-10-25-open-firmware`), installed with M-Flasher on the
FM-1 with the LLVM build of m-bootloader 1.2.

| Build | Result |
| --- | --- |
| LLVM, fork 5aa75b1a8 | boots, keys and sound work, the screen stays dark |
| JieLi's toolchain, same source | everything works, screen included (owner's check) |
| LLVM, fork 44f74b6b8 (the if-block fix) | everything works, screen included (owner's check) |

The cause, found in the simulator (`tools/llvm/sim.py`, both builds' `fm1_main` traced with the flash routines
stubbed, the SPI and port writes logged): the panel set-up walks a table of commands and data counts, and the
LLVM target had made

```
if (r5 != 0) {         ; the count of data bytes
    r0 = r6
    r1 = r5
    call lcd_data
} else {
    r5 = 0
}
```

The call returns to the else part's instruction, which runs: the count became 0 after every command with data,
and from COLMOD on the panel was sent the table's data bytes as commands. JieLi's compiler puts a call only last
in a block (docs/COMPILER.md, if blocks); the LLVM target does so now, uses the 32-bit `goto` in blocks as JieLi's
does, and no longer gave a then part ending in a goto the length of the following code as an else part. With the
fix the panel commands of the start-up (SWRESET ... NORON, the clear, DISPON, the splash) are those of JieLi's
build. The simulator now stops at a call before a block's end, and at a jump out of a block before its last
instruction; with it the differential test (`tools/llvm/ctest.py`) finds the old compiler's fault in `f_tail`.

Block shapes (then part at most 4, else part at most 3, a call only last) in the builds: JieLi's Felucca 2614
blocks, none wrong; LLVM before the fix 2640, 92 wrong; after 2550, none; m-bootloader 1.2 and its loaders rebuilt
with the fix, none.

Backups were taken before every write; images stay on the desktop.

## m-bootloader 1.2 rebuilt with the fix

Both units got m-bootloader 1.2 rebuilt with fork 44f74b6b8 (FM-1 payload 13284 bytes, SMK-37 14340 of 14368),
through M-Flasher's boot-area write (the units' configuration kept, CRC32 verified): both boot to their firmware
(the FM-1 to the LLVM Felucca above), the menu and the startup keys into download mode (FM-1 REC, SMK-37 SEQ REC)
work (owner's check).

## Size changes (fork f51981486)

More 16-bit forms, shared bases for neighbouring peripheral registers, and-not with a modified immediate, loop
rotation at -Oz. m-bootloader 1.2: FM-1 13284 -> 13168 bytes, SMK-37 14340 -> 14200 (slot 14368); Felucca 511028
-> 508672; fm1-base 80132 -> 79908. ctest 1200/1200 at -O2, -Os and -Oz; no wrong if-block in any of the builds;
Felucca's start-up panel commands those of JieLi's build in the simulator. On the FM-1 (bootloader and Felucca):
menu, REC startup key, Felucca's screen, keys and sound work (owner's check). The SMK-37 bootloader is built, not
yet installed.

## SLOOP (Felucca's groovebox fork, two cores)

SLOOP 2.8.1 (github.com/isod89/sloop-fm1, d893642) built with fork f51981486 through the same directory: app image
563688 bytes (JieLi's toolchain, same source: 567564), update loader 8504 (8156); the build's own checks pass, the
same list as with JieLi's (the second core's loop in RAM among them); no wrong if-block (1687 blocks). In the
simulator `lcd_init` sends the same panel traffic as JieLi's build (one more write of the SPI baud register, the
source's two). On the FM-1 with the LLVM m-bootloader: screen, keys, sound and playing patterns work (owner's
check).
