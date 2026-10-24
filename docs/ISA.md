# pi32v2 instruction set

This is the prose half of the reference. Encodings are in [isa/pi32v2.toml](../isa/pi32v2.toml); this
document explains the concepts and names table entries by `id`. Each statement cites its source in square
brackets ([SOURCES.md](SOURCES.md)). **Pending** marks a section with nothing confirmed yet.

## 1. Overview

- 32-bit, little-endian; ELF machine number `0xF1` (241) [kagaimiq-jielie].
- JieLi derived it from Analog Devices' Blackfin DSP core, and it keeps Blackfin traits such as parallel
  instruction issue and an algebraic assembly syntax [kagaimiq-jielie, sstic2026].
- Instructions are 16, 32 or 48 bits long. The first 16-bit word identifies the instruction and its
  operand format, and so its length [kagaimiq-jielie, sstic2026].
- The AC791N in the M-VAVE FM-1 is built for with `-mcpu=r3` and the `fprev1` FPU [sources-in-use].

## 2. Registers

### General registers

`r0`..`r15`, 32 bits each [kagaimiq-jielie]. Two consecutive registers form a 64-bit pair, written
high-then-low as `r1_r0`, `r3_r2` and so on; pairs replace pi32's dedicated `macc` register for 64-bit
results such as multiply-accumulate [kagaimiq-jielie].

### Special registers

Sixteen special-register numbers `sr0`..`sr15` [kagaimiq-jielie]; the names are the ones JieLi's objdump
prints, which its assembler also accepts as `sr<n>` [oracle]:

| Number | Name | Purpose |
| --- | --- | --- |
| `sr0` | `reti` | return address from an interrupt |
| `sr1` | `rete` | return address from emulation (debug) mode |
| `sr2` | `retx` | return address from an exception |
| `sr3` | `rets` | return address from a subroutine call |
| `sr5` | `psr` | processor status |
| `sr4` | (none) | not yet known; printed `sr4` |
| `sr6` | `cnum` | not yet known |
| `sr7` | `uspn` | not yet known [oracle] |
| `sr8` | `sspn` | not yet known [oracle] |
| `sr9` | `icfgn` | not yet known [oracle] |
| `sr10` | `icfgs` | not yet known [oracle] |
| `sr11` | `icfg` | interrupt configuration |
| `sr12` | `usp` | user-mode stack pointer |
| `sr13` | `ssp` | supervisor-mode stack pointer |
| `sr14` | `sp` | the current stack pointer |
| `sr15` | `pc` | program counter |

The names of `sr7`..`sr10` suggest copies of `usp`, `ssp` and `icfg`; what they do is not known. Unlike
pi32, `sp` is its own register and `r15` is a general register [kagaimiq-jielie]. Special registers are read
and written with `mov.r_sr` and `mov.sr_r`, loaded with `li.sr_u32`, and pushed and popped with `push.srl`,
`pop.srl` (`sr0`..`sr5`) and `push.srmask` (any).

Some loads address memory relative to `npc` (`r1 = [npc + r2]`, `ld.w.npc`) [oracle]; what `npc` holds is
not yet known.

There is also a condition flag, `cc`, set directly by `cc = 0` / `cc = 1` [kagaimiq-jielie]. **Pending:**
which instructions set and test it.

## 3. Assembly syntax

JieLi's tools use Blackfin-style algebraic syntax rather than mnemonics: an assignment describes the
operation. From the open FM-1 projects' assembly [sources-in-use]:

```asm
r3 = 0x1C07F00
[r1 + 0] = r2
sp = r0
[--sp] = {r3-r0}
{psr, rets, reti} = [sp++]
call fm1_cstart
rti
```

In order: load a constant, store a word, write a special register, push a register range (written high to
low), pop special registers, call, return from interrupt. The table's `syntax` strings use the same notation,
spelled as JieLi's objdump prints it ([TABLE-FORMAT.md](TABLE-FORMAT.md#syntax)).

Spellings found so far [oracle]:

- objdump writes no spaces inside brackets (`[r1+0]`); the assembler accepts them (`[r1 + 0]`).
- A negative offset is written `[r4+-11]`; the assembler refuses `[r4-11]`.
- `[sp]` has no offset when it is 0, but `[r1+0]` keeps it.
- Byte and halfword loads end in `(u)` (zero-extended) or `(s)`; the assembler accepts the line without it.
- Constants print in decimal, except `li.modimm`'s, which print in hex.
- A branch prints its offset followed by the target as `<symbol+offset : address >`.
- Parallel issue: objdump prints two spaces and `#` after the instruction (`r0 = r1 + r2  #`); the assembler
  takes `r0 = r1 + r2 #`. Writing a second instruction after the `#` (`... # r3 = r4`) was refused with
  "invalid parallel-B instruction" in the cases tried.
- Blocks: `rep` and `if (...) {` open a block that objdump prints indented, closed by a `}` line that takes no
  bytes. The assembler wants `rep r1 {` / `rep 3 {`, body, `}`, and works out the body's length itself.
- Halves and lanes: `r1.l` and `r1.h` are a register's low and high 16 bits; `r1.b0`..`r1.b3` its bytes.
  Pair operands such as `r2,r3` must name registers of one 64-bit pair (`r2,r5` is refused).
- Modifiers in parentheses after an operation: `(u)`/`(s)` unsigned/signed, `(usat)`/`(ssat)` saturating,
  `(uavg)`/`(savg)`, `(rnd,...)`, `(x2)`, `(v)` (vector), `(f)` (floating point).

**Pending:** the assembler's comment syntax (the projects run their `.S` files through the C preprocessor
and use C comments), directives, and how parallel issue is written (reported as `ins1 # ins2`
[kagaimiq-jielie]; objdump prints a trailing `#` on such 16-bit words [oracle]).

## 4. Encoding

- Instruction words are 16 bits, stored little-endian, and fetched one at a time [sstic2026].
- The table writes each word most significant bit first ([TABLE-FORMAT.md](TABLE-FORMAT.md)).
- The first word decides the length [oracle, from decoding all 65536 words]:
  - `0000`..`DFFF`: a 16-bit instruction (or no instruction). In `C000`..`DFFF`, 2650 words are the
    instruction at the same low 13 bits in `0000`..`1FFF`, printed with a trailing `#` (parallel issue);
    the other 5542 are not instructions. Control instructions such as `nop` have no `#` form.
  - `E000`..`FFFF`: the first word of a 32-bit instruction, except 99 words in `FF00`..`FFEF` that begin a
    48-bit one. Words in this range that begin neither are not instructions. 774 of the 32-bit first words
    also print with `#`.
- The same holds for 32-bit forms: an instruction whose first word is in `E000`..`E7FF` has, for 228 forms, a
  parallel twin with first-word bit 12 set (`F000`..`F7FF`), printed with `  #`. `E800`..`EFFF` (branches,
  blocks) have none; `F800`..`FFFF` hold other instructions.
- Extra words hold immediates and operands. A 32-bit constant in a 48-bit instruction is stored low half
  first (`li.u32`, `li.sr_u32`).
- Small immediates are often split across the word, and offsets are scaled by the access size (words by 4,
  branch targets by 2); each entry's `fields` gives the exact layout.
- Every decodable word is in the table; see [GAPS.md](GAPS.md) for the few forms with no assembler syntax.

## 5. Instruction groups

The table's `group` keys. Counts are entries (forms) as of the first merge (1017 entries; the table has
grown since, see `python3 -m pi32v2isa stats`); a parallel twin counts as its own entry:

| Group | Entries | What is in it |
| --- | --- | --- |
| dsp | 360 | half-register and lane arithmetic, saturating and averaging adds, packed multiplies, `all`/`any`/`cmp` vector compares |
| branches | 137 | `goto`/`call` near and far, compare-and-branch against zero, a number or a register, flag branches (`ifeq goto`), decrement-and-branch, bit tests, `if (...) {` blocks |
| memory | 132 | loads and stores: word, halfword, byte; register + offset, `sp` + offset, register + register (optionally shifted), pre- and post-increment, `npc`-relative, read-modify-write |
| arithmetic | 72 | add, subtract (also reversed), with carry, `+=` and three-operand forms, divide, count leading zeros/sign, popcount, byte reversal |
| multiply | 58 | 32- and 64-bit multiplies and multiply-accumulates, including memory operands |
| shifts | 52 | `<<`, `>>`, `<<<`, `>>>` by a number or a register, on registers and pairs |
| logic | 29 | and, or, xor, not, bit clear, with registers and modified immediates |
| stack | 27 | push and pop of ranges, masks and special registers |
| moves | 26 | general, special, half-register and pair moves, `sp`/`usp`/`ssp`/`uspn`/`sspn` |
| fpu | 50 | single-precision add, sub, mul, div, multiply-add/sub, compare, min/max, conversions with four roundings, and their twins |
| control | 24 | `nop`, `idle`, interrupts on/off, `swi`, `syscall`, `bkpt`, locks and events, `rep`, `trigger` |
| bitops | 20 | bit insert/extract, bit set/clear/toggle |
| constants | 19 | the constant loads, from 16-bit `li.u8` to 48-bit `li.u32` |
| returns, cache, jumps | 11 | `rts`/`rti`/`rtx`/`rte`, cache maintenance, jumps through a register |

Several operations have more than one encoding. JieLi's assembler picks the shortest that fits: a constant
goes to `li.u8`, `li.neg5` or `li.zero_hi` if it can, then `li.s16` or `li.modimm`, and only then `li.u32`;
`call`/`goto` take the 16-bit form when the target is near and the 32-bit one for symbols; `r1 = r1 + r2`
becomes `r1 += r2` where that form exists.

## 6. Execution model

Known so far [oracle]:

- `rep` repeats the block after it: `rep r1 {` takes the count from a register, `rep 3 {` from a number
  (1..32); the body is 2..32 bytes (1..16 words).
- `if (cond) {` makes the following block conditional; the closing `}` takes no bytes, so the block's extent is
  not encoded in the `if` word itself as far as objdump shows. Compare-and-branch forms jump instead.
- Shift amounts run 1..32 (1..64 for pairs); a zero amount field means 32 (64).
- The vector compares `all`/`any`/`cmp(...) (v)` in F000..F7FF print without the `#` other twins carry.
- `.pin` post-increment steps by the access size only (±4, ±2, ±1), the sign picked by one bit.

**Pending:** what a branch offset is relative to (objdump prints the same offset at any address), parallel
issue, `rep` hardware loops (`rep` takes a count register and covers the following
instruction words [kagaimiq-jielie]), if/then/else blocks [virtualabs-ghidra], flags, delay slots if any.

## 7. Interrupts, exceptions and modes

**Pending.** Known so far: separate return registers for interrupts, exceptions and emulation (`reti`,
`retx`, `rete`), and user and supervisor stack pointers (`usp`, `ssp`) [kagaimiq-jielie]. Firmware switches
`sp` between them and saves `psr`, `rets` and `reti` on entry to a handler [sources-in-use].

## 8. CPU variants and features

**Pending.** The toolchain ships pi32v2 libraries for CPU models `r1`..`r5`, each also as a "large" build
[oracle]. Features to pin down: `fprev1` (the FPU), SIMD, the instruction revisions and newer CPU models
([GAPS.md](GAPS.md)).

Observed with the assembler [oracle]: `popcnt`, `sum(...)` and the halfword memory multiply-accumulates need
`-minstrev3` (28 entries have `requires = ["instrev3"]`); objdump decodes them without it. The FPU forms
assemble and decode without `-mfprev1`; whether the hardware needs `fprev1` for them is not known.

## 9. Calling convention

[ABI.md](ABI.md) documents the C ABI JieLi's compiler implements, from compiled examples [compiler]. In
short: the first four argument words go in `r0`..`r3` (64-bit values in a register pair or split between
`r3` and the stack), the rest on the stack; results in `r0` (`r1_r0` for 64-bit); structs are passed by
pointer to a copy and returned through a hidden pointer; `r4`..`r15` are preserved by the callee; the stack
is 4-byte aligned; a call saves its return address in `rets` [m-bootloader-spec]. `double` arithmetic goes
through helper functions (software); `float` uses the FPU instructions.

## 10. ELF object files

e_machine `0xF1` [kagaimiq-jielie]; objdump calls the format `ELF32-pi32v2` [oracle].

Relocations seen in the FM-1 objects [oracle]:

| Type | Used by |
| --- | --- |
| `R_PI32V2_MOV_ABS32` | `li.u32`, `li.sr_u32` with a symbol: the 32-bit constant |
| `R_PI32V2_LONG_JUMP_23M2` | `call.l`, `goto.l` with a symbol: the 22-bit offset, in units of 2 |

**Pending:** the other relocation types, their numbers and exact fields, section flags and symbol conventions,
which the assembler needs to write objects JieLi's linker accepts.
