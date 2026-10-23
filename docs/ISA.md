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
- Extra words hold immediates and operands. A 32-bit constant in a 48-bit instruction is stored low half
  first (`li.u32`, `li.sr_u32`).
- Small immediates are often split across the word, and offsets are scaled by the access size (words by 4,
  branch targets by 2); each entry's `fields` gives the exact layout.
- **Pending:** the SSTIC paper's group numbering, and most of the 16-bit map: about 1000 distinct shapes
  decode, of which the table so far has the ones the FM-1 sources need ([GAPS.md](GAPS.md)).

## 5. Instruction groups

The table's `group` keys, with the entries in each so far:

| Group | Entries |
| --- | --- |
| control | `nop`, `idle`, `csync`, `cli`, `sti`, `trigger` |
| returns | `rts`, `rti`, `rtx`, `rte` |
| jumps (through a register) | `call.r`, `goto.r` |
| branches | `beqz`, `bnez`, `goto.s`, `goto.l`, `call.s`, `call.l` |
| moves | `mov.rr`, `mov.r_sr`, `mov.sr_r`, `mov.sp_usp`, `mov.sp_ssp`, `mov.usp_sp`, `mov.ssp_sp`, `cc.set` |
| constants | `li.u8`, `li.neg5`, `li.zero_hi`, `li.s16`, `li.modimm`, `li.u32`, `li.sr_u32`, `or.bit` |
| memory | `ld.w`, `st.w`, `ld.w.sp`, `st.w.sp`, `ld.bu`, `st.b` |
| stack | `push.rl`, `pop.rl`, `push.rets_rl`, `pop.rets_rl`, `pop.pc_rl`, `push.srl`, `pop.srl`, `push.rmask`, `push.srmask` |

Several operations have more than one encoding. JieLi's assembler picks the shortest that fits: a constant
goes to `li.u8`, `li.neg5` or `li.zero_hi` if it can, then `li.s16` or `li.modimm`, and only then `li.u32`;
`call`/`goto` take the 16-bit form when the target is near and the 32-bit one for symbols.

## 6. Execution model

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

## 9. Calling convention

The first two argument words are passed in `r0` and `r1` and the result is returned in `r0`; a call saves
its return address in `rets` [m-bootloader-spec]. **Pending:** the remaining argument registers, which
registers a function must preserve, stack alignment, 64-bit and floating-point values.

## 10. ELF object files

e_machine `0xF1` [kagaimiq-jielie]; objdump calls the format `ELF32-pi32v2` [oracle].

Relocations seen in the FM-1 objects [oracle]:

| Type | Used by |
| --- | --- |
| `R_PI32V2_MOV_ABS32` | `li.u32`, `li.sr_u32` with a symbol: the 32-bit constant |
| `R_PI32V2_LONG_JUMP_23M2` | `call.l`, `goto.l` with a symbol: the 22-bit offset, in units of 2 |

**Pending:** the other relocation types, their numbers and exact fields, section flags and symbol conventions,
which the assembler needs to write objects JieLi's linker accepts.
