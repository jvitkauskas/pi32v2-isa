# FM-1, 2026-10-25: Rust

[examples/fm1-blink-rust](../../examples/fm1-blink-rust/README.md) compiled by rustc 1.99.1 with the pi32v2 patch
([jvitkauskas/pi32v2-rust](https://github.com/jvitkauskas/pi32v2-rust)), built against the pi32v2-llvm fork's LLVM
(X86 and PI32V2 targets); `core` and `compiler_builtins` built from source (`-Zbuild-std`) for the JSON target;
the start-up code and `shim.c` by the fork's clang, the link by its `ld.lld`. Installed with M-Flasher over the
application area of the same FM-1 (m-bootloader 1.2 from the LLVM toolchain), after a full backup.

| Build | Result |
| --- | --- |
| The blink alone, `--features autotest` (520-byte application; before the screen was added) | the record at 0x01C7C000: `BLNK`, 300 ticks, 72000008 crystal counts (3.0000003 s at 24 MHz: a period is 60000 counts of TIMER5's 6 MHz with PRD 59999), `RUST`; `TICKS` in `.bss` 300; back in download mode by itself. The interrupt entry in C called the Rust handler every time and returned with `rti` |
| With the picture, normal mode (116484 bytes, 115200 of them the frame) | Ferris and "Hello from Rust" on the screen (owner's check) |

Before installing, the picture build's panel traffic was checked in the simulator (`tools/llvm/sim.py`, TIMER4
advancing a millisecond a read, the SPI always done): SWRESET, SLPOUT, COLMOD 0x55, MADCTL 0x00, INVON, NORON,
CASET and RASET 0..239, RAMWR, then 30 DMA transfers of 3840 bytes with D/C high carrying exactly the 115200 bytes
of the frame, and DISPON. Package hashes and the record: [results.json](results.json).

The generated code was read before the first run: every peripheral address and value of `main`, the interrupt
entry (saves `psr`, `reti`, `rets`, r0..r3), the download-mode marker. No wrong if-block.

The RAM dump and the backups stay on the desktop; they are not committed.
