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

Sixteen special-register numbers `sr0`..`sr15`, some with names [kagaimiq-jielie]:

| Number | Name | Purpose |
| --- | --- | --- |
| `sr0` | `reti` | return address from an interrupt |
| `sr1` | `rete` | return address from emulation (debug) mode |
| `sr2` | `retx` | return address from an exception |
| `sr3` | `rets` | return address from a subroutine call |
| `sr5` | `psr` | processor status |
| `sr6` | `cnum` | not yet known |
| `sr11` | `icfg` | interrupt configuration |
| `sr12` | `usp` | user-mode stack pointer |
| `sr13` | `ssp` | supervisor-mode stack pointer |
| `sr14` | `sp` | the current stack pointer |
| `sr15` | `pc` | program counter |

`sr4` and `sr7`..`sr10` have no known name. Unlike pi32, `sp` is its own register and `r15` is a general
register [kagaimiq-jielie].

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
low), pop special registers, call, return from interrupt. The table's `syntax` strings use the same notation.

**Pending:** the assembler's comment syntax (the projects run their `.S` files through the C preprocessor
and use C comments), directives, the exact spelling accepted for each form, and how parallel issue is
written (reported as `ins1 # ins2` [kagaimiq-jielie]).

## 4. Encoding

- Instruction words are 16 bits, stored little-endian, and fetched one at a time [sstic2026].
- The table writes each word most significant bit first ([TABLE-FORMAT.md](TABLE-FORMAT.md)).
- **Pending:** the instruction groups (the SSTIC paper numbers them; groups 6 and 7 hold the harder
  ones), how the first word selects a 32- or 48-bit length, and where immediates sit in the extra words.

## 5. Execution model

**Pending:** parallel issue, `rep` hardware loops (`rep` takes a count register and covers the following
instruction words [kagaimiq-jielie]), if/then/else blocks [virtualabs-ghidra], flags, delay slots if any.

## 6. Interrupts, exceptions and modes

**Pending.** Known so far: separate return registers for interrupts, exceptions and emulation (`reti`,
`retx`, `rete`), and user and supervisor stack pointers (`usp`, `ssp`) [kagaimiq-jielie]. Firmware switches
`sp` between them and saves `psr`, `rets` and `reti` on entry to a handler [sources-in-use].

## 7. CPU variants and features

**Pending.** The toolchain ships pi32v2 libraries for CPU models `r1`..`r5`, each also as a "large" build
[oracle]. Features to pin down: `fprev1` (the FPU), SIMD, the instruction revisions and newer CPU models
([GAPS.md](GAPS.md)).

## 8. Calling convention

The first two argument words are passed in `r0` and `r1` and the result is returned in `r0`; a call saves
its return address in `rets` [m-bootloader-spec]. **Pending:** the remaining argument registers, which
registers a function must preserve, stack alignment, 64-bit and floating-point values.

## 9. ELF object files

**Pending.** e_machine `0xF1` [kagaimiq-jielie]. The relocation types, section flags and symbol conventions
JieLi's linker expects are needed for the assembler to write objects that linker accepts.
