# LLVM backend

An LLVM target for pi32v2 (`-triple=pi32v2`), on LLVM 23.1.4, in a fork of llvm-project (branch `pi32v2`,
not published yet). Its instruction descriptions and assembler tables are generated from this repo's table
and assembler by `tools/llvm/`, so the table stays the one source. This page says what exists, how it is built
and how it is checked.

## Status

| Part | State |
| --- | --- |
| Triple, ELF machine 241, relocations 0..16 ([ELF.md](ELF.md)) | done |
| Instructions: 1165 table forms, 4230 LLVM instructions (enum fields expanded) | done, generated |
| Disassembler, printer (JieLi's objdump syntax) | done: every table example |
| Code emitter, fixups, branch relaxation, ELF writer | done |
| Assembler (`llvm-mc`), JieLi's syntax and choices | done: the corpus below |
| `llvm-objdump` branch targets as symbols | not yet |
| Linker (`ld.lld`) | not yet ([LINKER.md](LINKER.md) has the relocation rules) |
| Code generator (`llc`, `clang`) | not yet: next |

## Building

```sh
git clone --depth 1 --branch llvmorg-23.1.4 https://github.com/llvm/llvm-project.git   # then the pi32v2 branch
python3 tools/llvm/gen_td.py LLVM/llvm/lib/Target/PI32V2 --tests LLVM/llvm/test/MC   # after a table change
cmake -G Ninja LLVM/llvm -DCMAKE_BUILD_TYPE=Release -DLLVM_ENABLE_ASSERTIONS=ON \
      -DLLVM_TARGETS_TO_BUILD="" -DLLVM_EXPERIMENTAL_TARGETS_TO_BUILD=PI32V2
ninja llvm-mc llvm-objdump llvm-readobj
```

The generated files are committed in the LLVM tree, each with a header naming the generator: `PI32V2InstrGen.td`
(operands and instructions), `PI32V2OperandsGen.inc` (their decoders, encoders and printers),
`AsmParser/PI32V2ParserGen.inc` (the assembler's templates), `MCTargetDesc/PI32V2FixupsGen.inc` (where an
expression goes in each instruction) and `MCTargetDesc/PI32V2RelaxGen.inc` (branch relaxation). Regenerate them
after any change to `isa/pi32v2.toml` or `pi32v2isa/asm.py`.

## How the table maps to LLVM

- **Instructions.** One TableGen instruction per form and combination of `enum` values (the value's text is part
  of the assembly string, its bits fixed). The encoding is `Inst` of 16, 32 or 48 bits, the first word in the
  high bits; the emitter writes the words in order, each little-endian. A `-` bit is left unset.
- **Operands.** `gpr`, `gpr_lo`, `gpr_hi`, `pair` and `sr` are register classes; every other field is an
  immediate operand holding the value the syntax shows (scaled, a bit's value, a modified immediate's 32 bits),
  register lists their raw field. A form whose syntax starts `{x} =` defines x; `{x} op= ...` reads and writes
  it (a tied operand). That is what the syntax says, not a semantics; the code generator adds what it needs.
- **Assembler.** JieLi's syntax has no mnemonic first, and an operand can only be found by knowing the form
  (`[--sp]` is not an expression). So the parser does what `pi32v2isa/asm.py` does: the line in canonical form,
  matched against one template per way of writing each form (its aliases included), the readings that fit
  sorted as `asm.py` sorts them (size, alias, tie, table order). The templates are generated from `asm.py`'s
  matchers, so both assemblers accept the same lines. Expressions follow `asm.py`'s grammar.
- **Branches** start in their smallest form and grow by relaxation to the next form that matches the same line,
  until the target is in reach or the form has a relocation. A branch to any non-weak label of the same section
  (global or not, an alias of one too) is resolved by the assembler, as JieLi's is.
- **Blocks.** `rep ... {` takes its body's length in bytes from labels around the body; `if (...) {` takes the
  instruction counts of its two parts from symbols set at the closing `}`. Both are resolved by the assembler.

## Checks

```sh
python3 tools/llvm/check_mc.py BUILD/bin     # every example: disassembly, re-encoding, assembly
python3 tools/llvm/check_objs.py BUILD/bin   # objects of tests/asm and of the C corpus (JieLi's clang -S)
ninja check-llvm-mc-pi32v2                   # or: llvm-lit llvm/test/MC/PI32V2 llvm/test/MC/Disassembler/PI32V2
```

As of 2026-10-25: all 6093 examples disassemble to their text and re-encode to their bytes; all 5478 assemble
to `asm.py`'s bytes; `llvm-mc`'s objects have the same sections, contents, relocations and symbol values as
`asm.py`'s (which are JieLi's, [ELF.md](ELF.md)) for 179 of 180 files: `tests/asm/*.s` and the 50 C files of
`tests/corpus` at -O0, -O2 and -Os. The one difference is `tests/asm/secnames.s`: for section names such as
`.data.rel` and `.eh_frame` without flags, LLVM's generic ELF parser gives other default flags than JieLi's.

## Known differences from JieLi's assembler

- Default flags of sections named without flags (above).
- `@` relocation variants (`sym@PI32V2GOT`) are not parsed yet.
- The object layout (section and symbol order, string table) is LLVM's; the checks compare contents, not layout.
- `--chip ac791n` warnings (the table's `hw` key) are not given yet; the feature `ac791n` exists for them.
