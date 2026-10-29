# SMK-37 Pro, 2026-10-29: SLOOP Pro from the size-optimized fork

SLOOP Pro 2.8.3 (isod89/sloop-pro 0b9b7d2, the SMK-37 Pro package, identity `SMK-37 Pro_900`) built by its own
`tools/build.py` with `JIELI_TOOLCHAIN` the drop-in package ([DROPIN.md](../../docs/DROPIN.md)) of the fork's
branch `size-int` (6e5cbfedb): the code-size work (instruction selection, register allocation for the 2-byte
encodings, post-RA recoloring, inliner policy) on top of `pi32v2-dropin`. No source change for this firmware.

| | JieLi's toolchain 20260730.1 | the fork |
| --- | ---: | ---: |
| App image | 599 112 B | 587 228 B (-2.0 %) |
| Code (FUNC symbols) | 236 674 B | 223 942 B (-5.4 %) |
| Package | 651 224 B | 650 880 B |

Installed with M-Flasher on the SMK-37 Pro (stock 016, m-bootloader 1.2; a full backup first; only the app area
0x04000-0x9CFFF written, the calibration untouched), restarted from download mode: it enumerates on USB-MIDI (as
`Felucca`, SLOOP Pro's USB name), sends its sequencer's notes over MIDI, no reset in a 60 s watch, and the owner
played it: it plays fine.

Not measured: timing against JieLi's build of the same source (the package is on the desktop for an A/B).
