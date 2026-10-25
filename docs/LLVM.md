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
| Code generator (`llc`): integers, memory, branches, calls, frames, varargs | first version: the tests below |
| Shorter forms, as JieLi's assembler picks them (`MCTargetDesc/PI32V2CompressGen.inc`) | written, not yet built |
| `clang`: target info (type sizes, `__PI32V2__`), ABI (aggregates by pointer, sret) | written, building |
| Linker (`ld.lld`), relocations as JieLi's `ld` ([LINKER.md](LINKER.md) section 3) | written, not yet built |
| `llvm-objdump` branch targets as symbols | not yet |
| Floating point (library calls), atomics, `byval`, a frame pointer for dynamic stack | not yet |

## Building

```sh
git clone --depth 1 --branch llvmorg-23.1.4 https://github.com/llvm/llvm-project.git   # then the pi32v2 branch
python3 tools/llvm/gen_td.py LLVM/llvm/lib/Target/PI32V2 --tests LLVM/llvm/test/MC   # after a table change
cmake -G Ninja LLVM/llvm -DCMAKE_BUILD_TYPE=Release -DLLVM_ENABLE_ASSERTIONS=ON \
      -DLLVM_TARGETS_TO_BUILD="" -DLLVM_EXPERIMENTAL_TARGETS_TO_BUILD=PI32V2
ninja llvm-mc llvm-objdump llvm-readobj llc   # add -DLLVM_ENABLE_PROJECTS="clang;lld" for clang and ld.lld
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
llvm-lit LLVM/llvm/test/MC/PI32V2 LLVM/llvm/test/MC/Disassembler/PI32V2
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

## The code generator

It follows JieLi's C convention ([ABI.md](ABI.md)): arguments are words of one stream, `r0`..`r3` and then at
`sp`; results in `r0` and `r1`; `r4`..`r15` preserved. A frame is what JieLi's compiler makes: one push of `rets`
and the saved registers (`[--sp] = {rets, r15-r4}`), `sp += -n`, and the matching pop into `pc`, which returns; a
function that saves nothing returns with `rts`. Stack slots use the `[sp+n]` forms. A variadic function first
pushes the argument registers its named arguments left unused, so they continue the stack arguments. Clang passes
every aggregate as a pointer to a copy and returns one through a hidden pointer in `r0`.

The code generator uses the general forms of the table (`tools/llvm/codegen_flags.py` says which, and what LLVM
must know about them: loads, stores, branches, calls, `psr`); the emitter then puts each in the shortest form
JieLi's assembler would choose for its line. Branches start short and grow by relaxation.

## Testing compiled code

- `tools/llvm/sim.py`: a simulator whose instructions are the models fitted to the FM-1 (`tools/hwtest/semantics`,
  which agree with every hardware result in `hw/`); control flow is its own, parallel pairs follow the hardware's
  rules, library helpers are done in Python.
- `tools/llvm/cgtest.py`: 255 calls of functions in LLVM IR (`cgtest.ll`), compiled by `llc`, with results computed
  in Python; `build` makes a test application for the FM-1 (`tools/hwtest/app/cgdriver.S`), `check` compares its
  results. `sim.py OUTDIR` runs the same calls in the simulator: all 255 agree (2026-10-25).
- `tools/llvm/ctest.py`: `ctest.c` compiled by JieLi's clang and by ours, both run in the simulator on the same
  inputs, the results compared. JieLi's build runs completely (748 calls).
