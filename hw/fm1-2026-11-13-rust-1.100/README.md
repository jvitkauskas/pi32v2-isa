# FM-1, 2026-11-13: Rust 1.100.0

The [run of 2026-10-25](../fm1-2026-10-25-rust/README.md) again, with the example as it is now (the blink and the
picture in one program) and a newer compiler.

**The build:**
- [examples/fm1-blink-rust](../../examples/fm1-blink-rust/README.md) compiled by rustc 1.100.0 with the pi32v2
  patch: branch `pi32v2` of [jvitkauskas/pi32v2-rust](https://github.com/jvitkauskas/pi32v2-rust) at `3ee95ae`,
  the commit of 1.99.1 moved onto the 1.100.0 tag.
- rustc built against the pi32v2-llvm fork's LLVM at release `pi32v2-23.1.5-5` (X86 and PI32V2 targets).
  Rust 1.100.0 itself uses LLVM 23.1.5.
- The start-up code and `shim.c` by that release's clang, the link by its `ld.lld`. `core` and
  `compiler_builtins` built from source (`-Zbuild-std`).

**Unit and access:**
- The same FM-1: flash chip 0x856014, m-bootloader 2.3 (`7c5ebb9`, built with `pi32v2-23.1.5-5`), firmware
  "FM-1 901" installed before the run.
- A full backup with M-Flasher (loader 1.3) before anything was written. Both packages were installed with
  `m-flasher firmware` over the application area; M-Flasher verified every write against the chip's CRC32.

| Build | Result |
| --- | --- |
| `--features autotest` (116464-byte application) | the record at 0x01C7C000: `BLNK`, 300 ticks, 71999994 crystal counts (2.9999998 s at 24 MHz), port A outputs 0x10, `RUST`; `TICKS` in `.bss` 300; back in download mode by itself (`tools/hwtest/runapp.sh`) |
| Normal mode (116468 bytes, 115200 of them the frame) | Ferris and "Hello from Rust" on the screen (owner's check) |

The 1.99.1 run counted 72000008 crystal counts for the same 300 ticks. Both are 3 s to within a microsecond.

**Checked before installing:**
- In the simulator (`tools/llvm/sim.py`, TIMER4 advancing a millisecond a read, the SPI always done), the panel
  traffic of the normal build was the same as the 1.99.1 build's: the same commands and parameters, then 30 DMA
  transfers with D/C high carrying exactly the 115200 bytes of the frame.
- The generated code differs from 1.99.1's (LLVM 23.1.4 to the fork's 23.1.5-5: post-incremented pointers, for
  one). The download-mode routine was read: it writes the same 16 bytes to 0x01C7FD80 and sets the same bit at
  0x10000.

Package hashes and the record: [results.json](results.json). The RAM dump and the backup stay on the desktop;
they are not committed.
