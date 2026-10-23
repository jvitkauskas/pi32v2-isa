# Working on pi32v2-isa

These rules apply to people and agents alike. They keep the reference trustworthy and its licence clean.

## The table is the source of truth

- Instruction encodings live in `isa/pi32v2.toml`, not in prose. `docs/ISA.md` explains concepts (formats,
  registers, execution model) and refers to table entries by `id`; it does not repeat encodings.
- The assembler, disassembler and tests read the table. A change to an encoding is a change to the table, made
  in the same commit as any code or test it affects.
- Run `python3 -m pi32v2isa check` and `python3 -m unittest discover -s tests` before committing.

## Every fact has a source and a status

- Each entry lists its `sources` (ids from `docs/SOURCES.md`) and a `status`:
  - `guessed`: inferred, not seen in any source or observation;
  - `documented`: stated by a cited source, not yet checked against the oracle;
  - `confirmed`: encoding and syntax checked against the oracle; the entry's examples are the evidence.
    Behaviour is not covered (`docs/TABLE-FORMAT.md`).
- Use `python3 -m pi32v2isa oracle confirm <id> --write` to confirm an entry. An example with
  `origin = "oracle:..."` must be bytes and text the oracle actually decoded and assembled; never write one by
  hand from the entry's own pattern.
- When a new finding contradicts an entry, fix the entry, keep the old claim in the commit message, and add an
  example that shows the difference.
- Something known to exist but not understood goes in `docs/GAPS.md`, not in the table as a guess.

## Clean-room and licence rules

- Use facts from the sources; never copy their wording, tables, code or figures. Write entries and prose in
  this repo's own words and format.
- No Apache-2.0 or unlicensed material goes into the repo verbatim. `docs/SOURCES.md` lists each source's
  licence.
- JieLi's toolchain is used only as a black box: give it input, record its output (`docs/ORACLE.md`). Do not
  extract tables or strings from its binaries.
- Never commit JieLi's toolchain, SDK libraries or binaries, or any vendor firmware. Refer to them by name,
  version and SHA-256.

## Licences and headers

- Code: MIT-0. Documentation and the instruction table: CC0-1.0.
- New source files start with `SPDX-FileCopyrightText` and `SPDX-License-Identifier` lines. Files that
  cannot carry a header are covered by `REUSE.toml`.
