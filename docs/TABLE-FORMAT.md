# Instruction table format

`isa/pi32v2.toml` is a TOML file with `format = 1` and one `[[insn]]` table per instruction form. An
instruction form is one encoding with one operand layout: `r1 = r2` and `r1 = [r2]` are different forms.

## Entry

```toml
[[insn]]
id = "ld.w.sp"                      # unique and stable; other documents refer to it
syntax = "{r} = [sp{+n}]"           # JieLi's assembly syntax, see below
encoding = ["001ooooo00p0rrrr"]     # one string per 16-bit word, see below
fields = { r = "gpr", n = { kind = "uimm", letters = "po", scale = 4 } }
group = "memory"                    # optional: a heading for docs/ISA.md
requires = []                       # CPU features needed, e.g. ["fprev1"]
summary = "Load a word from the stack at sp plus 0..252."
status = "confirmed"                # guessed | documented | confirmed
sources = ["oracle"]                # ids from docs/SOURCES.md
notes = "objdump omits the offset when it is 0 ([sp])."   # optional
asm_rejects = []                    # optional: texts objdump prints that JieLi's assembler refuses

[[insn.example]]                    # optional; zero or more
bytes = "2d 31"                     # hex, in memory order
text = "r13 = [sp+196]"             # what the oracle printed and accepted
origin = "oracle:objdump+clang:20260730.1"
```

## Naming ids

Ids are lowercase words joined by dots: the operation first, then what distinguishes this form from others
with the same operation. Follow the existing entries:

| Pattern | Examples |
| --- | --- |
| loads and stores: `ld`/`st`, size `w`/`h`/`b`, `u`/`s` for a load's extension, then the addressing | `ld.w`, `st.b`, `ld.bu`, `ld.w.sp` |
| addressing suffixes: none = register + offset, `.sp` = sp + offset, `.pi` = post-increment by a register (`[r1++=r2]`), `.pin` = post-increment by a number (`[r1++=4]`) | `ld.hu.pi`, `st.w.pin` |
| arithmetic and logic: `add`, `sub`, `mul`, `and`, `or`, `xor`, `not`, `lsl` (`<<`), `lsr` (`>>`), then operand shape: `.rrr` (`r1 = r2 op r3`), `.rr` (`r1 op= r2`), `.rri` (`r1 = r2 op n`), `.ri` (`r1 op= n`) | `add.rrr`, `xor.ri` |
| constants and moves: `li.` + range, `mov.` + operands | `li.u8`, `mov.r_sr` |
| branches: `b` + condition + `z` when against zero, `goto.`/`call.` + reach | `beqz`, `goto.s`, `call.l` |
| stack: `push.`/`pop.` + what | `push.rl`, `pop.srl` |
| parallel-issue (`#`) twin of an entry: the entry's id + `.p` | `add.rrr.p` |

When an operation's meaning is not known, name it after what objdump prints (`<<<` is `shl3`, not a guess
at "rotate"), and say so in `notes`. A name says what the instruction is, never where it was found.

## Encoding strings

- Each string is one 16-bit instruction word, written most significant bit first. Words are listed in
  memory order. Each word is stored little-endian (low byte first).
- Characters: `0` and `1` are fixed bits; `-` is a bit the decoder ignores and the assembler writes as `0`;
  a lowercase letter is a bit of an operand field.
- Bits with the same letter are read in the order they appear, across words, most significant first.

## Fields

`fields` maps each operand name (a lowercase letter used in `syntax`) to its kind, either as a plain string
or as an inline table:

| Key | Default | Meaning |
| --- | --- | --- |
| `kind` | (required) | an operand kind, below |
| `letters` | the field's own name | the encoding letters that hold it, most significant part first: `letters = "po"` puts the `p` bits above the `o` bits |
| `values` | (none) | `enum` only: the text printed for each raw value, a list of exactly 2^width strings |
| `invert` | false | `modimm` only: print the bitwise complement of the modified immediate |
| `decimal` | false | `modimm` only: print as an unsigned 32-bit decimal instead of hex |
| `lead` | (none) | `rmask` only: a name printed first, before the registers (`{rets, r3-r0}`; just `{rets}` when the mask is empty) |
| `zero_as` | (none) | `uimm` only: the number printed for the raw value 0 (a shift amount where 0 means 32) |
| `scale` | 1 | `uimm`/`simm` only: the printed number is the raw value (sign-extended for `simm`) times `scale`, plus `add` |
| `add` | 0 | `uimm`/`simm` only |

`letters` handles split fields: `li.u32` keeps a constant's low half in its second word and the high half in
its third, so its encoding uses `i` then `j` and the field says `letters = "ji"`.

## Syntax

- `{x}` is field `x`.
- `{+x}` prints `+` and the value, or nothing when the value is 0 (`[sp]`, `[sp+4]`).
- `{{` and `}}` are literal braces (`[--sp] = {{{l}}}` prints `[--sp] = {r3-r0}`).
- The text follows JieLi's **objdump**. The assembler accepts more spellings (`[r1 + 0]`, `b[r4+4]` without
  `(u)`); an assembler written from this table must accept those too.

## Operand kinds

| Kind | Width | Meaning | Printed as |
| --- | --- | --- | --- |
| `gpr` | 4 | `r0`..`r15` | `r5` |
| `gpr_lo` | 3 | `r0`..`r7` | `r5` |
| `gpr_hi` | 3 | `r8`..`r15` (field value + 8) | `r13` |
| `pair` | 3 | 64-bit register pair `r(2n+1)_r(2n)` | `r3_r2` |
| `sr` | 4 | special register by number ([ISA.md](ISA.md) §2) | `reti`, `sr4`, `sp` |
| `uimm` | any | unsigned number | `252` |
| `simm` | any | two's-complement number | `-11` |
| `bit` | 5 | a bit number, printed as the bit's value | `16384` |
| `modimm` | 12 | modified immediate: bits 11..10 = 0 repeats byte `XY` as `XY`, `00XY00XY`, `XY00XY00` or `XYXYXYXY` (bits 9..8); otherwise `1` + bits 6..0, rotated right by bits 11..7. Printed in hex | `0x10000` |
| `enum` | any | one of a fixed set of words or suffixes, chosen by the raw value from the field's `values` list (`".l"`/`".h"`, `"usat"`/`"ssat"`) | `.h` |
| `rlist4` | 4 | register range: 0..3 is `r3` down to `r<n>`, 4..15 is `r<n>` down to `r4` | `r3, r2`, `r6-r4` |
| `rmask` | 16 | set of general registers, bit n = `rn` | `r11-r8, r3-r0` |
| `srmask` | any | set of special registers, bit n = special register n | `psr, rets, reti` |

Register lists are printed highest first; in `rlist4` and `rmask` a run of three or more is written as a
range. An empty `rmask` or `srmask` prints as nothing (`{}`), which JieLi's assembler refuses: such entries
list that text in `asm_rejects`.

New kinds are added here and in `pi32v2isa/table.py` and `pi32v2isa/codec.py` together.

## Status

| Status | Meaning | Needs |
| --- | --- | --- |
| `guessed` | Inferred (from a sweep, or by reasoning); not confirmed, no source states it | a `notes` line on how it was inferred |
| `documented` | A cited source states it | at least one `sources` id other than `oracle` |
| `confirmed` | Checked against the oracle | `oracle` in `sources` and examples covering every field ([ORACLE.md](ORACLE.md)) |

`confirmed` covers the **encoding and the syntax**: JieLi's tools decode and assemble the entry exactly as the
table says. It says nothing about **behaviour**: the `summary` still rests on the other sources (and `notes`
says so where it is an assumption) until it is tested on hardware.

## Checks

`python3 -m pi32v2isa check` rejects a table where:

- an `id` repeats, or a required key is missing;
- an encoding word is not 16 characters, a letter belongs to no field or to two, or a field names a letter
  the encoding doesn't have;
- a field's width doesn't fit its kind, or `scale`/`add` is given for a kind other than `uimm`/`simm`;
- a `{x}` in `syntax` isn't a field, a field never appears in `syntax`, or a brace is unescaped;
- a `status`, kind or source id is unknown;
- two entries' encodings overlap (some bit pattern matches both);
- an example's bytes don't decode to its own entry, or print differently from its `text`.
