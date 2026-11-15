# FM-1 hardware run, 2026-11-14: second-word bit 12, and pairs in `if` blocks

Three things that came up when comparing this table with the
[fm1-emu](https://github.com/joakimeriksson/fm1-emu) emulator's decoder and with JieLi's older objdump.

**Unit and access:**
- Julius Vitkauskas's M-VAVE FM-1 (AC791N), flash chip 0x856014, m-bootloader 2.3 with firmware "FM-1 901".
- Driven from download mode with `/opt/m-flasher/m-flasher run-ram`.
- Nothing was written to flash.

## 1. The `x2` dual multiplies with second-word bit 12 set

**The encodings:** first words `E572`/`E573`/`E576`/`E577`/`E57A`/`E57B`/`E57E`/`E57F` and their parallel twins
`F57x`, with second-word bit 12 set.

**What objdump makes of them:**
- JieLi objdump 20250324.1 prints them at `-mcpu=r2`, `r3`, `r4` and with no `-mcpu`, as the `mul2`/`madd.mul2`/
  `msub.mul2` `(usat,x2)`/`(ssat,x2)` text, e.g. `73 f5 6f 3f` = `r3_r2 -= r6.h,r6.h *|* r15.l,r15.l (ssat,x2)  #`.
- 20260730.1 prints `<unknown instruction>`, also with `+instrev3` and `+fprev1`.
- Both releases assemble that text with the bit clear.

**Where they turn up:** fm1-emu's corpora of vendor-objdump listings of FM-1 firmware contain 26 such words.

**Comparing the two releases:** a sweep at `-mcpu=r3` of all 16-bit words, plus every E000-FFFF first word with 32 random second words. It found no other encoding that one release decodes and the other does not.

The other 373 differing probes are renames: 20250324.1 prints `rd op= a,b *|* c,d (usat)` where 20260730.1
prints `rd op= sum(a,b *|* c,d) (u)`.

The table now has them as `mul2.prhrhrhrhe.b12`, `madd.mul2.prhrhrhrhe.b12` and `msub.mul2.prhrhrhrhe.b12`,
plus their `.p` twins. Each has `objdump_releases = ["20250324.1"]` (docs/TABLE-FORMAT.md) and was confirmed with
`oracle confirm --release 20250324.1`: 2741 encodings each, both ways.

```sh
python3 tools/hwtest/gen.py DIR --cases hw/fm1-2026-11-14-bit12/x2b12-cases.json --first-slot 0x01C20000
python3 tools/hwtest/gen.py DIR --wave pair --ids mul2.prhrhrhrhe.b12.p,madd.mul2.prhrhrhrhe.b12.p,msub.mul2.prhrhrhrhe.b12.p,mul2.prhrhrhrhe.p,madd.mul2.prhrhrhrhe.p,msub.mul2.prhrhrhrhe.p --per-entry 8 --seed 7 --first-slot 0x01C28000
```

**Results:** [x2b12.jsonl](x2b12.jsonl), 100 records, both batches, with the calibration `nop`s.

- **Plain forms:** 8 cases per new entry, 2 modes × 4 register sets with random fields and flags. Each case is
  paired with a case of the bit-clear entry with the same values and inputs. All 24 pairs give identical
  registers and psr. 20 of the 48 cases reach a 32-bit clamp.
- **Parallel twins:** 8 cases per twin, new and old, each with a 16-bit load or store as the second
  instruction.
- **Check:** `check.py` holds every case to the mul2 model and matches 13 of 13 entries.

An earlier, independent probe agreed with all of this. It ran 20 x2 encodings and their bit-1-clear `sum.*`
counterparts with 4 register sets each, using an m-apps RAM app in fm1-emu's work: 160 of 160 fit the same model.

## 2. Pair loads and stores ignore second-word bit 12

Twelve `d[...]` entries have second-word bit 12 fixed at 0, and the word with it set decodes as nothing, in
this table and in both objdump releases:

`ld.d.sp.l`, `st.d.sp.l`, `ld.d.l`, `st.d.l`, `ld.d.pre`, `st.d.pre`, `ld.d.prer`, `st.d.prer`, `ld.d.pi.l`,
`st.d.pi.l`, `ld.d.pin.l`, `st.d.pin.l`.

`gen.py`'s memory-case generator made 4 cases for each. Each also ran with bit 12 set, using exact `bytes` with
`"undecoded": true`, a new case key in `gen.py`: the bytes must decode as no entry and carry the entry's field
bits, and `check.py` holds them to the entry's model.

```sh
python3 tools/hwtest/gen.py DIR --cases hw/fm1-2026-11-14-bit12/pairb12-cases.json --first-slot 0x01C20000
```

**Results:** [pairb12.jsonl](pairb12.jsonl), 100 records.

- **Check:** 13 of 13 entries match their models.
- **Variants:** all 48 bit-12 cases give the same registers, scratch words, sp and psr as their bit-clear twin.
  24 of them stored to memory and 40 changed registers.

The chip runs these words as the entries. objdump does not show them, so the table keeps its encodings and
the twelve entries say so in their notes.

[patterns.json](patterns.json) holds the scratch patterns of all four batches (check.py needs them for
record format 2).

## 3. A parallel pair is one unit of an `if` block

Both assemblers count a parallel pair once in the opener's then/else lengths:

- `if (r0 == r1) { r2 = r2 + r5  # ; [r3+0] = r4 }` assembles to `10 e8 00 01` (then = 1);
- with the pair as the else-part, it assembles to `10 e8 00 11` (else = 1);
- JieLi 20260730.1 and the pi32v2 LLVM assembler agree on both.

On the chip, run as an m-apps RAM app (`hwtests/excprobe` group 15 in the fm1-emu work, these exact
encodings), with `r2 = 0` and the word at `[r3]` = 0 before each case:

| Block | Condition | A (`r2 += 1`) | B (store 0x1234) | after the block | other part |
| --- | --- | --- | --- | --- | --- |
| pair as then | false | not run | not run | run | n/a |
| pair as then | true | run | run | run | n/a |
| pair as else | false | run | run | run | not run |
| pair as else | true | not run | not run | run | run |

So the then- and else-lengths count units: one instruction, or one parallel pair. `docs/ISA.md` and the
`if`/`iff`/`ifs` notes now say units. Whether a nested block counts as one unit cannot be written: JieLi's
assembler refuses a `rep` inside an `if` block, and the pi32v2 LLVM assembler refuses a nested `if`.
