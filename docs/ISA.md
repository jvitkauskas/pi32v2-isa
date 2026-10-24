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

| Number | Name | Purpose | Seen on the FM-1 (hw/fm1-2026-10-24-v2) |
| --- | --- | --- | --- |
| `sr0` | `reti` | return address from an interrupt | a ROM address that is constant within one batch of cases and differs between batches (`0x01E00368`, `0x01E00E72`, `0x01E0168E`, `0x01E01674`, `0x01E01718`) |
| `sr1` | `rete` | return address from emulation (debug) mode | 0 |
| `sr2` | `retx` | return address from an exception | 0 |
| `sr3` | `rets` | return address from a subroutine call | what was written to it, cut to bits 26..1: bit 0 and bits 31..27 read back as 0 |
| `sr4` | (none) | not yet known; printed `sr4` | 0 |
| `sr5` | `psr` | processor status | the flags N Z C V in bits 3..0, the rest 0; pushing it (not reading it) clears the flags |
| `sr6` | `cnum` | not yet known (core number?) | 0 |
| `sr7` | `uspn` | not yet known [oracle] | 0 |
| `sr8` | `sspn` | not yet known [oracle] | 0 |
| `sr9` | `icfgn` | not yet known [oracle] | 0 |
| `sr10` | `icfgs` | not yet known [oracle] | 0 |
| `sr11` | `icfg` | interrupt configuration | `0x01090700`, always |
| `sr12` | `usp` | user-mode stack pointer | a RAM address just above `ssp`, constant within a batch, differing between batches (`0x01C0117C`, `0x01C01180`, `0x01C011A0`) |
| `sr13` | `ssp` | supervisor-mode stack pointer | `0x01C00E00`, always |
| `sr14` | `sp` | the current stack pointer | the current sp (a push stores its value from before the decrement) |
| `sr15` | `pc` | program counter | the address of the instruction reading it (a push of `pc` stores the push's own address) |

None of the sixteen counts while a batch runs. `reti` and `usp` look like the state of the boot ROM's context when the
batch's command arrived (the runner is called from the ROM's download handler); that is a reading of the data, not
tested. The cut on `rets` was seen when popping (`pop.rets_rl`) and in the runner's own write; whether `pc`, `reti` and the
others are cut the same way was not tested. The names of `sr7`..`sr10` suggest copies of `usp`, `ssp` and `icfg`; they
read 0 whenever tried, and what they do is not known. Unlike
pi32, `sp` is its own register and `r15` is a general register [kagaimiq-jielie]. Special registers are read
and written with `mov.r_sr` and `mov.sr_r`, loaded with `li.sr_u32`, and pushed and popped with `push.srl`,
`pop.srl` (`sr0`..`sr5`) and `push.srmask` (any). A push stores the lowest-numbered register at the lowest address.

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
- Parallel issue: objdump prints two spaces and `#` after the first instruction of a pair
  (`r0 = r1 + r2  #`); the second follows on the next line. The assembler takes `r0 = r1 + r2 #` and then
  the second instruction on its own line; the first may be any ALU, move, multiply, divide, float or
  bit-field form with a `.p` twin, the second must be a 16-bit load or store on `r0`..`r7` with a short
  offset ("invalid parallel-B instruction" otherwise) [oracle]. The pair issues together: the second reads
  registers as they were before the first writes them [compiler] ([COMPILER.md](COMPILER.md)).
- Blocks: `rep` and `if (...) {` open a block that objdump prints indented, closed by a `}` line that takes no
  bytes. The assembler wants `rep r1 {` / `rep 3 {`, body, `}`, and works out the body's length itself.
- Halves and lanes: `r1.l` and `r1.h` are a register's low and high 16 bits; `r1.b0`..`r1.b3` its bytes.
  Pair operands such as `r2,r3` must name registers of one 64-bit pair (`r2,r5` is refused).
- Modifiers in parentheses after an operation: `(u)`/`(s)` unsigned/signed, `(usat)`/`(ssat)` saturating,
  `(uavg)`/`(savg)`, `(rnd,...)`, `(x2)`, `(v)` (vector), `(f)` (floating point).

Comments are `/* */`, `//`, `;`, and `#` at the start of a line; there is no statement separator; directives
are listed in [ASSEMBLER.md](ASSEMBLER.md) (there is no `.word`, `.half` or `.hword`). **Pending:** how
parallel issue is written (reported as `ins1 # ins2`
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

Known so far [oracle, compiler; evidence in [COMPILER.md](COMPILER.md)]:

- Branch offsets are relative to the end of the branch instruction.
- `if (cond) {` blocks are predication: the following 1..4 instructions run only if the condition holds,
  optionally followed by `} else {` and 0..3 more that run otherwise. The shape is in the opener's second
  word, bits 15..14 (then-count - 1) and 13..12 (else-count); objdump shows it only by where it prints `}`.
- Flags: `add`/`sub` set the carry in `psr` bit 1 (set when there is no borrow); `addc` adds it, `subc`
  subtracts its complement; a signed `<` tests `psr` bit 3 xor bit 0.
- `if` compares are unsigned, `ifs` signed (no difference for `==`, `!=`), `iff` floating point; the `u`
  floating conditions are also true when an operand is NaN.

- `rep` repeats the block after it: `rep r1 {` takes the count from a register, `rep 3 {` from a number
  (1..32); the body is 2..32 bytes (1..16 words).
- The closing `}` of a block takes no bytes; a `rep` body's length is in the `rep` word, an `if` block's
  shape in the opener's second word (above).
- Shift amounts run 1..32 (1..64 for pairs); a zero amount field means 32 (64).
- The vector compares `all`/`any`/`cmp(...) (v)` in F000..F7FF print without the `#` other twins carry.
- `.pin` post-increment steps by the access size only (±4, ±2, ±1), the sign picked by one bit.

**Pending:** which `psr` bits are sign, overflow and zero, and which instructions write the flags; `rep`
hardware loops (`rep` takes a count register and covers the following
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

[ELF.md](ELF.md) documents the object format: e_machine `0xF1` [kagaimiq-jielie], `e_flags` 0, RELA
relocations naming the symbol itself, the relocation types 1..8 the assembler emits (`LONG_JUMP_23M2` = 2,
`MOV_ABS32` = 5, `ABS32` = 8, ...) with the bits each patches, and the conventions JieLi's linker checks
[oracle]. The repo's assembler writes these objects ([ASSEMBLER.md](ASSEMBLER.md)).
