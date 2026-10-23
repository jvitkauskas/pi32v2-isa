# Instruction table format

`isa/pi32v2.toml` is a TOML file with `format = 1` and one `[[insn]]` table per instruction form. An
instruction form is one encoding with one operand layout: `r1 = r2` and `r1 = [r2]` are different forms.

## Entry

```toml
[[insn]]
id = "call.r"                       # unique and stable; other documents refer to it
syntax = "call {x}"                 # JieLi's assembly syntax; {letter} is an operand field
encoding = ["000000001100xxxx"]     # one string per 16-bit word, see below
fields = { x = "gpr" }              # field letter -> operand kind
group = "control"                   # optional: a heading for docs/ISA.md
requires = []                       # CPU features needed, e.g. ["fprev1"]
summary = "Call the subroutine at the address in a register."
status = "documented"               # guessed | documented | confirmed
sources = ["kagaimiq-jielie"]       # ids from docs/SOURCES.md
notes = "Syntax spelling not yet checked against the oracle."   # optional

[[insn.example]]                    # optional; zero or more
bytes = "c5 00"                     # hex, in memory order
text = "call r5"                    # what the oracle printed or accepted
origin = "oracle:objdump:20260730.1"
```

## Encoding strings

- Each string is one 16-bit instruction word, written most significant bit first. Words are listed in
  memory order. Each word is stored little-endian (low byte first).
- Characters: `0` and `1` are fixed bits; `-` is a bit the decoder ignores and the assembler writes as `0`;
  a lowercase letter is a bit of the operand field with that letter.
- A field's bits are concatenated in the order they appear, across words, most significant first. A field
  may be split.

## Operand kinds

| Kind | Width | Meaning | Printed as |
| --- | --- | --- | --- |
| `gpr` | 4 | `r0`..`r15` | `r5` |
| `gpr_lo` | 3 | `r0`..`r7` | `r5` |
| `gpr_hi` | 3 | `r8`..`r15` (field value + 8) | `r13` |
| `pair` | 3 | 64-bit register pair `r(2n+1)_r(2n)` | `r3_r2` |
| `uimm` | any | unsigned immediate | `12` |
| `simm` | any | two's-complement immediate | `-4` |

New kinds are added here and in `pi32v2isa/table.py` together.

## Status

| Status | Meaning | Needs |
| --- | --- | --- |
| `guessed` | Inferred; no source states it | a `notes` line on how it was inferred |
| `documented` | A cited source states it | at least one `sources` id other than `oracle` |
| `confirmed` | Checked against the oracle | `oracle` in `sources` and examples covering every field ([ORACLE.md](ORACLE.md)) |

## Checks

`python3 -m pi32v2isa check` rejects a table where:

- an `id` repeats, or a required key is missing;
- an encoding word is not 16 characters, or uses a letter not listed in `fields` (or lists one it doesn't use);
- a field's width doesn't fit its kind;
- a `{letter}` in `syntax` isn't a field, or a field never appears in `syntax`;
- a `status`, kind or source id is unknown;
- two entries' encodings overlap (some bit pattern matches both);
- an example's bytes don't decode to its own entry.
