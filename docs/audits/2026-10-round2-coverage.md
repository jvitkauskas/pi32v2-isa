<!-- SPDX-FileCopyrightText: 2026 Julius Vitkauskas -->
<!-- SPDX-License-Identifier: CC0-1.0 -->

# Round 2 encoding audit: agent G

All observations below come from black-box inputs and outputs of JieLi toolchain 20260730.1,
CPU r3, through `pi32v2isa.oracle` [oracle]. No hardware behavior was tested. Existing instruction
encodings, fields and syntax were preserved; additions are under `# ==== round 2: G ====`.

## First-word coverage

Coverage uses a zero second and third word, as `oracle coverage` does. Before → after:

- `0000–1FFF`: 7,200/7,200 → 7,200/7,200.
- `2000–BFFF`: 37,632/37,888 → 37,888/37,888.
- `C000–DFFF`: 2,650/2,650 → 2,650/2,650.
- `E000–EFFF`: 2,500/2,500 → 2,500/2,500.
- `F000–FFFF`: 2,577/2,671 → 2,671/2,671.

Both requested `oracle coverage` commands were run before and after. The other regions were compared
against the same cached first-word sweep. This metric measures matched instruction length, not exact
printed text. In particular it does not expose the existing `FF20–FF2F` problem below.

## Added forms

120 entries (1,017 → 1,137), checked by 277,698 `oracle.confirm` probes with 600 recorded examples.
42 entries use `asm_no_syntax`; all others have a working assembly spelling or an equivalent preferred
form, subject to the recorded assembler exceptions:

- `add.ri.u5`: all 256 encodings of `R += 0..31`; assembly always chooses the equivalent `add.rri`.
- 13 ordinary parallel twins: `add.rrr.l.p`, `sub.modimm.rri.p`, `mul.rrr.p`,
  `or.modimm.rri.p`, `xor.modimm.rri.p`, `and.nmodimm.rri.p`, `or.rrr.p`, `xor.rrr.p`,
  `and.rrr.p`, `lsl.rrr.p`, `shl3.rrr.p`, `lsr.rrr.p`, `shr3.rrr.p`.
  The four apparent missing immediate-shift twins already exist under ids such as `lsl.rri.p`.
- 60 vector comparison forms, the `.p` counterparts of the existing `all`, `any`, `cmp` and signed
  variants, for register and pair operands. Objdump prints no `#` for these F-region words; assembly
  requires the marker, recorded in `asm_syntax`. Thus they are not ordinary printed-syntax twins.
- 24 unnamed vector-condition forms: `all|any|cmp.unknown4to7|unknown14to15.ppp|rrr.v`, with E and F
  forms distinguished by `.p`. Ignored condition bits here mean identical printed text, not equal
  hardware behavior.
- Seven `if.unknown.rr.1` through `.7` entries partition nonzero second-word bits 6..0 at `EA10–EA1F`
  with bit 7 clear. Zero selects the existing AND-test block and is excluded.
- 13 long-branch entries: two modified-immediate mask branches, four unnamed integer-condition
  forms (signed immediate and register), two unnamed modified-immediate forms, the unnamed floating
  conditions at `FF4E/FF4F`, and four floating conditions `!=`, `u==`, `uno`, `ord`.
- `addsub.rhrhi.sat` and `.p`: the sweep found saturated half-register add/subtract immediates at
  `F4A0–F4BF`, requiring second-word bit 1. Probes and confirmation also establish the E counterpart.

The `??` spellings are refused by the assembler. The four named floating branch conditions produce no
instruction for the printed text. `asm_no_syntax` records the lack of a known working spelling and tests
that behavior; it is not an exhaustive proof that no alternative spelling exists, or that the hardware
implements these forms.

## Complete F-region sweep

Every first word `F000–FFFF`, including those whose zero-second-word probe is unknown, was passed to
`oracle.sweep(o, first)`. Each result covers all 65,536 second words with zero third word: 268,435,456
pairs total. Every pair was compared to the table for exact text and length; unknown results must also
agree. The comparison used `codec.decode` and `codec.format` with first-word candidate lists and cached
entry masks/field positions, preserving the codec's decoding rules.

Of the 4,096 first words, 2,703 decode with at least one second word. The oracle decodes 168,351,360
pairs; 167,736,960 match the final table exactly. There are 614,400 residual mismatches (0.365% of
oracle-decodable pairs), all in the ten pre-existing entries below: **61,440 per entry**. There are no
remaining missing encodings or mismatches attributed to a new entry.

The sweep exposed 1,048,576 missing pairs in the saturated half-register immediate family and 147,456
unnamed vector-condition pairs in F. They are covered by the added entries. Other newly found unnamed
floating conditions and modified-immediate variants are also included. Rechecks of all 46 affected F
first words cover 3,014,656 pairs (1,933,312 decodable), with zero mismatches. Auxiliary full second-word
checks of `E538–E53D` and `EA10` cover 458,752 pairs (442,368 decodable), also with zero mismatches.

The 48-bit check sampled 23 third words (zero, each single bit, `1234`, `5555`, `7FFF`, `A5A5`, `FFFE`,
`FFFF`) across all 99 first words beginning 48-bit forms. Second words include extrema, single-field
bit probes and irregular patterns: 57,983 probes, 54,671 decodable. After fixes to new entries, the only
mismatches are 207 per existing entry listed below, 2,070 total.

Scratch evidence is retained under `/tmp/g/`:

- `sweeps/ffff.pkl.gz`-style files: complete oracle outputs, one file per first word; E-vector and EA10
  auxiliary sweeps are also present.
- `compare-initial/`, `compare-corrected/`, `compare-extra/`, `compare-final-summary.json`,
  `thirds-summary.json`: counts and byte/text evidence. The final summary uses corrected results for the
  46 changed F first words and initial results elsewhere.
- `coverage-before-*`, `coverage-after-*`, `coverage-all.json`: coverage evidence.
- `confirm-cache/`, `confirm*.log`: per-entry confirmation results and representative preferences.

## Existing entries requiring correction

First-word bit 5 in `FF00–FF2F` selects the immediate interpretation. Clear means signed 12-bit;
set means a 12-bit modified immediate printed in decimal. The ten existing entries encode this bit as
`-` and treat both as signed 12-bit:

`beq.ri.l`, `bne.ri.l`, `bge.ri.l`, `blt.ri.l`, `bgt.ri.l`, `ble.ri.l`,
`bges.ri.l`, `blts.ri.l`, `bgts.ri.l`, `bles.ri.l`.

Evidence (third word zero):

- `00 ff ff 0f 00 00`: `if (r0 == -1) goto 0`.
- `20 ff ff 0f 00 00`: `if (r0 == 510) goto 0`; the table says `-1`.
- `20 ff 01 01 00 00`: `if (r0 == 65537) goto 0`; the table says `257`.
- `2a ff ff 0f 00 00`: `ifs (r0 >= 510) goto 0`; the table says `-1`.

They were preserved as required by the task. A follow-up should split each entry into signed and
modified-immediate forms. New unnamed-condition entries already distinguish the two layouts.

The cached first-word sweep also differs on 16 `rep` opener texts (`0321–0330`) because its four-byte
padding is shorter than the repetition body. All 16 match exactly when decoded with 34-byte padding,
as confirmation already uses. These are context artifacts, not additional encoding errors.

## Checker, format and tool findings

- `Insn.asm_no_syntax` (boolean): full confirmation still checks every decode probe, and requires every
  printed text to yield an error or no instruction. Recorded examples use
  `oracle:objdump+clang-reject:<release>`; the example regression also verifies rejection. The table
  checker rejects incompatible `asm_syntax`, `asm_wrong` or `asm_rejects` settings. Documentation is in
  `TABLE-FORMAT.md` and `ORACLE.md`; unit tests cover loading, validation, failed decoding and a future
  assembler that starts accepting the text.
- Confirmation now accepts an entry whose assembler always chooses an equivalent table entry. This
  permits `add.ri.u5`; a unit test also checks that a different operand is still rejected.
- Parallel `or R,0`, `xor R,0`, and `and R,0xFFFFFFFF` spellings assemble correctly. The last may select
  the non-inverted modified-immediate form. They do not inherit the non-parallel entries' `asm_wrong`.
- With zero mask and a short target, the mask-branch assembler chooses the single-bit-mask form testing
  bit 0 (`60 ff 00 00 00 00` prints mask zero, but its text assembles to `50 e8 00 00`, which prints mask
  one). The two new entries list the observed texts in `asm_wrong`; the note describes the general
  limitation. Zero masks with long targets select an equivalent encoding correctly.
- The existing `asm_wrong` confirmation branch only checks for different bytes; it can also accept a
  correct alternate encoding as a supposed misassembly. This was noticed when checking the new inverted
  parallel AND form, whose correct alternate encoding must not be annotated `asm_wrong`.

## Findings for other documentation

`GAPS.md` can remove the first-word encoding holes and replace the incomplete second-word statement
with the full F-region results and the preserved entry errors. `ISA.md` should update entry counts,
mention the vector forms' missing printed parallel marker, and avoid describing bit 5 of the long
immediate branches as ignored. Neither file was edited in this task. All `confirmed` claims here cover
encoding and tool syntax only; unnamed conditions and floating comparisons still need hardware work.

## Validation

- `python3 -m pi32v2isa check`: **1,137 entries, 0 problems**.
- `python3 -m unittest discover -s tests`: **OK**, 34 tests, one optional full-table confirmation test
  skipped; the live example regressions ran with the specified toolchain.
- All 120 new entries passed confirmation (277,698 probes); all 1,137 entries are marked confirmed.
- The entire pre-existing table prefix is byte-for-byte unchanged.
- `git diff --check`: clean.
