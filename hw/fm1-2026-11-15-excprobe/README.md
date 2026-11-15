# FM-1 hardware run, 2026-11-14/15: exceptions, `rep`, PC limits, cycle costs

RAM-app probes of things the single-instruction captures (`hw/fm1-2026-10-24*`) cannot show: what traps, how
late, what the trapping access still does, how many times one `rep` runs, the PC-limit guard, cycle costs, and
some words only fm1-emu's decoder took. They were written while comparing this table with the
[fm1-emu](https://github.com/joakimeriksson/fm1-emu) emulator. fm1-emu's notes and fixes cite them as "2026-11".

**Unit and access:**
- Julius Vitkauskas's M-VAVE FM-1 (AC791N), flash chip 0x856014, m-bootloader 2.3 with firmware "FM-1 901".
- Each run is a RAM app started by `m-flasher run-ram` from download mode: CPU 96 MHz, LSB 48 MHz, code
  and data in SRAM, interrupts off (except group 12). Nothing was written to flash.
- The probes were developed and first run on 2026-11-14. Every group was run again on 2026-11-15 with the
  source in [src/](src/), and those runs are the logs here. They agree with the first runs on every
  line that both have, and groups 13 and 14 read back byte for byte the same.

**The probe:** [src/excprobe.c](src/excprobe.c), an app for [m-apps](https://github.com/jvitkauskas/m-apps)'
kit. It installs its own vector-1 handler. The handler records EMU_MSG, DBG_MSG and `reti`/`rete`/`retx`.
It also counts how many 4-byte marker instructions (`r8 = r8 + 1`) after the probed instruction ran before
the exception was taken. Then it resumes after the markers. A group is chosen at build time:

```sh
make -C m-apps APPS=excprobe excprobe_CFLAGS=-DGROUP=N build/fm1/excprobe.app   # with src/ as apps/excprobe
python3 m-apps/tools/run.py --flasher 'm-flasher' --reader build/fm1/logread.bin build/fm1/excprobe.app
```

Groups 13 and 14 store their results at 0x01C70000. The app then stays resident (`run.py --stay`), and a
run-ram reader copies the results out (12800 and 3520 bytes). [decode.py](decode.py) prints them.

A log line reads `p_<probe> <address>: TRAP n<entries> emu <EMU_MSG> dbg <DBG_MSG> reti+<offset> ... mk
<markers run>`, or `ok mk 12` when nothing trapped and all 12 markers ran. The words after `|` are the
probe's result registers.

## Results

| Group | Log | What it shows |
| --- | --- | --- |
| 1 | [excprobe-g1.log](excprobe-g1.log) | Misaligned accesses always trap (EMU_MSG bit 0; EMU_CON reads 3 and bits 0/1 can't be cleared). Word loads/stores at +1..+3 and halfword at +1/+3 trap; the access still happens, at the **aligned-down** address. Pairs need only 4-byte alignment. The trap is taken 7 markers late (5 or 6 after a pair access). |
| 2 | [excprobe-g2.log](excprobe-g2.log) | Divide by zero: with EMU_CON as found (3), no trap, integer results 0, float 1/0 = 0x7F800000 and 0/0 = 0x7F800001. With EMU_CON bit 2, every integer and float divide by zero traps with EMU_MSG 4, 7 late, the result still written. |
| 3 | [excprobe-g3.log](excprobe-g3.log) | EMU_CON bits 16..20, each alone: which float results trap (EMU_MSG = the bit), 3 markers late. Bit 19 trapped inf + −inf twice, the second time at the instruction itself with its destination not written. |
| 4, 5 | [g4](excprobe-g4.log), [g5](excprobe-g5.log) | One `rep` runs at most 32 times: below 32 it runs `count` times and leaves 0; from 32 up it runs `(count & 31) + 1` times and leaves the register with its low five bits at 31. A count of 0 skips the body. |
| 12 | [excprobe-g12.log](excprobe-g12.log) | TIMER5 (vector 63, period register 300: an interrupt about every 3000 cycles) against `rep` loops (a 30-byte body of about 72 cycles): no interrupt was taken inside a `rep` body (`reti` was always after the body, at the `rep`, or elsewhere in the loop), and every count came out exact. |
| 6, 8–11 | [g6](excprobe-g6.log), [g8](excprobe-g8.log), [g9](excprobe-g9.log), [g10](excprobe-g10.log), [g11](excprobe-g11.log) | PC limits (both windows 0..0x07FFFFFF in this context): narrowing them and calling code outside traps through vector 1 with DBG_MSG 0x1000, 9 instructions late, whatever DBG_EN holds. Later trips still set DBG_MSG bit 12 but raise nothing (fresh addresses, rewritten limits, windows opened and narrowed again), until software writes DBG_CON bit 18 (it reads back 0). Bit 17 alone does not re-arm it. |
| 7 | [excprobe-g7.log](excprobe-g7.log) | Cycle costs from C0_TL_CKCNTL (0x01EEE218), 256 copies a block, 2 cycles of overhead removed: ALU 1, two independent adds 2 (no dual issue), 6-byte constant 1.46, load 2 (3 used at once), store 2, multiply 2, divide 10, float add/multiply 2, float divide 4, taken branch or goto 7.5, untaken 1, call + goto + rts 22.5, push + pop 6, pair load 4. |
| 13 | [excprobe-g13.log](excprobe-g13.log), [excprobe-g13-x2.bin](excprobe-g13-x2.bin), [decoded](excprobe-g13-x2.txt) | 40 `x2` dual-multiply encodings (with and without second-word bit 12, and their bit-1-clear `sum.*` counterparts) on 4 register sets: the "earlier, independent probe" of [fm1-2026-11-14-bit12](../fm1-2026-11-14-bit12/README.md). |
| 14 | [excprobe-g14.log](excprobe-g14.log), [excprobe-g14-x14.bin](excprobe-g14-x14.bin), [decoded](excprobe-g14-x14.txt) | 22 words fm1-emu's decoder took that this table does not have, one run each, then `r2 += 1` and `rts`. `45 00`..`48 00` (fm1-emu's `R = #i` class) change nothing. The `iff (rA_rB op rC_rD) goto` words (`00 e8`..`00 ee` with `01 1e`) raise the illegal-instruction exception (EMU_MSG 2). `50 ec`/`51 ec` with second-word bit 12 load a pair as `ld.d.l` / `ld.d.pre` with the bit clear; the sp-relative `d0 e9`/`d4 e9` also load. `d0 e1 3c 97` set r9_r8 to 0x7FFFFFFF_FFFFFFFF and `d0 e1 9a 79` r7_r6 to 0x71C9C000_00000000 (not explained); `d8 e1` changed nothing. |
| 15 | [excprobe-g15.log](excprobe-g15.log) | A parallel pair inside an `if` block's then- or else-part counts as one unit: both halves run or neither does. |

Not here: the boot ROM reader (`memread`). Its output is JieLi's code and is not published.
