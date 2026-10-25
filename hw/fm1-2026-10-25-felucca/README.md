# FM-1, 2026-10-25: Felucca from the LLVM toolchain

Felucca (the community firmware) built from one source tree with JieLi's toolchain and with the LLVM fork
(through the same JieLi-shaped directory as `hw/fm1-2026-10-25-open-firmware`), installed with M-Flasher on the
FM-1 with the LLVM build of m-bootloader 1.2.

| Build | Result |
| --- | --- |
| LLVM, fork 454be609a | boots, keys and sound work, the screen stays dark |
| JieLi's toolchain, same source | everything works, screen included (owner's check) |
| LLVM, fork 8cfa7af09 (the if-block fix) | everything works, screen included (owner's check) |

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

Both units got m-bootloader 1.2 rebuilt with fork 8cfa7af09 (FM-1 payload 13284 bytes, SMK-37 14340 of 14368),
through M-Flasher's boot-area write (the units' configuration kept, CRC32 verified): both boot to their firmware
(the FM-1 to the LLVM Felucca above), the menu and the startup keys into download mode (FM-1 REC, SMK-37 SEQ REC)
work (owner's check).
