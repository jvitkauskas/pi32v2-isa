# The assembler

`pi32v2isa/asm.py` assembles pi32v2 source into an ELF relocatable object ([ELF.md](ELF.md)) that JieLi's `ld`
links. It is driven by the instruction table: every entry's `syntax` (or `asm_syntax`) is turned into a
matcher, and the operands are converted back with the inverse of `codec.operand`. It never calls JieLi's
tools; they are only used to test it ([section 8](#8-testing)).

```sh
python3 -m pi32v2isa as IN.s -o OUT.o                       # preprocessed source
python3 -m pi32v2isa as IN.S -o OUT.o -I include -D BOARD=1   # .S: runs /usr/bin/cpp -P first
python3 -m pi32v2isa as IN.s --cpp -o OUT.o                  # force cpp on any file
```

`-I DIR` also tells `.incbin`/`.include` where to look (they search the source's directory, the `-I` directories
and the current directory). From Python: `asm.assemble_source(text, "x.s", include=[...])` returns the object's
bytes; `asm.Assembler` gives access to the pieces.

## 1. Source layout

- One statement per line (no statement separator: `;` starts a comment). Comments: `/* ... */` (may span lines),
  `// ...`, `; ...`, and `#` as the first character of a line. A `#` after an instruction is the parallel-issue
  marker, not a comment.
- Labels: `name:` (several per line, or before a statement), numeric labels `1:` referred to as `1f`/`1b`. Names are
  made of letters, digits, `_`, `.`, `$` (and `@` for variants). Registers and special-register names cannot be
  symbols (`r1`, `sr4`, `sp`, `psr`...). Names are case sensitive; registers are lower case.
- No line continuation.
- Macros, repetition and conditional assembly are handled before the instruction matcher sees a line:
  `.macro NAME a, b=default` / `.endm` (use `\a`, `\@`, `\()`), `.rept N`, `.irp x,a,b,c`, `.irpc x,abc`,
  `.if`/`.ifdef`/`.ifndef`/`.ifc`/`.ifnc`/`.ifb`/`.ifnb`/`.ifeq`/`.ifne`/`.ifge`/`.ifgt`/`.ifle`/`.iflt` with
  `.elseif`/`.else`/`.endif` (the condition must be a constant when it is read), `.include "file"`.

## 2. Instructions

Every table entry's text is accepted, as objdump prints it (`syntax`), or for the block openers that
differ as the assembler wants it (`asm_syntax`: `rep r1 {`, `rep 3 {`). Beyond that, the spellings
JieLi's assembler takes (found with `oracle encode`):

- White space is free around operators and inside brackets and braces: `[r1 + 4]`, `[ r1+4 ]`, `{ r3 - r0 }`,
  `r1=r2+r3`. (Only between two words does it need a gap: `goto 4`, `rep 3 {`.)
- A negative offset is `[r4+-11]` or `[r4+ -11]`; `[r4-11]` is refused, as it is by JieLi's assembler.
- Byte and halfword loads take `(u)` or leave it off: `r1 = b[r2+4]` is `r1 = b[r2+4] (u)`. Eleven entries require it
  (the unsigned multiply-accumulate forms with halfword operands, `mul4.u`, `sum`).
- `x op= y` and `x = x op y` mean the same wherever either is available (`r1 += r2`, `r1 = r1 + r2`); for the
  commutative operations `x = y op x` too (`r1 = r2 | r1`). `r1 = r1 - 3`, `r1 -= 3` and `r1 += -3` are the same.
- Numbers: decimal, `0x` hex, `0b` binary, leading-zero octal, `10h`, `'c'` character constants; written in any
  base, negative or not: `r1 = 0xFFFFFFFF` is `r1 = -1`. Numbers are 32 bits wide when they go into an operand:
  `0x100000000` is 0. Hex numbers are accepted where JieLi insists on decimal (`if (r1 == 0x0)`).
- Special registers by name (`reti`, `rete`, `retx`, `rets`, `psr`, `cnum`, `uspn`, `sspn`, `icfgn`, `icfgs`,
  `icfg`, `usp`, `ssp`, `sp`, `pc`) or number (`sr0`..`sr15`); pairs `r1_r0`; halves `r1.l`, `r1.h`; bytes `r1.b0`..`r1.b3`.
- Register lists in braces in any order, with or without ranges (`{r3-r0}`, `{r0, r1, r2, r3}`); an empty list is refused.
- A `#` at the end of a line (with or without a space before it) marks the first instruction of a parallel
  pair; the next instruction must be one JieLi's assembler allows as the second half
  ([section 6](#6-blocks-and-parallel-issue)).

### Expressions

Operands that take a number accept an expression: `+ - * / % << >> & | ^ ~ ! && || == != <> < > <= >=`,
parentheses, decimal/hex/binary/octal literals, character constants, symbols, `.` (the address of the current
instruction or data item) and numeric label references. Precedence is LLVM's, which is not C's: `* / % << >>`
bind tightest, then `| & ^ !`, then `+ -`, then comparisons, then `&&`, then `||`; the unary operators `- + ~ !`
bind tighter than all of them. Arithmetic is 64-bit two's complement, `/` and `%` truncate toward zero, `>>` is a
logical shift of the 64-bit value (so `-5 >> 1` is 0x7FFFFFFFFFFFFFFD, whose low 32 bits are -3), a
comparison is 1 or 0, and shifts take their count modulo 64. Division by zero is an error.

An expression is either a constant or `symbol + constant` (relocatable). A difference of two labels of the same
section is a constant. A constant that only involves symbols already `.set` keeps the value they have when the
statement is read (`.set A, 3`, `.byte A`, `.set A, 4`, `.byte A` gives 3 then 4), as in JieLi's assembler. The only
symbolic operands that make a relocation are listed in [ELF.md](ELF.md#which-operands-take-a-symbol); a symbol anywhere else is an
error ("no encoding fits the operands").

A symbol can carry an `@` variant after it: `r1 = sym@PI32V2GOT` (relocation type 9), `r1 = sym@PI32V2GOTFUNCDESC` (10); the
other variants JieLi accepts (`@GOT`, `@PLT`, `@GOTOFF`, `@GOTPCREL`, `@TPOFF`...) change nothing on a register load and
give a different data relocation ([ELF.md](ELF.md#5-relocations)). `PI32V2FUNCDESC` is accepted as well.

## 3. Choosing an encoding

Several entries often match one line (`r1 = 5` matches every constant load). The rules, each checked against JieLi's
assembler with a differential run over the table (92 711 lines: up to 100 field-value combinations of every entry, none of
them differing) and over compiler output:

1. The **shortest** form wins (2, 4 or 6 bytes) among those whose operands fit.
2. Among forms of the same size, a form written as the line is beats one reached through an alias (`r1 = r2 - 3` is
   `sub.modimm.rri`, not `add.s14.rri` with -3), then these preferences hold (`TIE` in `asm.py`):
   `li.s16` over `li.modimm`, `add.s14.rri` over `add.modimm.rri`, `add.rrr` over `add.rr`,
   `pop.srmask`/`push.srmask.c` over the `pc`/`rets` mask forms for a list of just that register,
   `*.ri.l` over its modified-immediate flavour; a parallel (`.p`) form ranks like its base; otherwise table order.
3. Constants: `li.u8` (0..255, `r0`..`r7`), `li.neg5` (-32..-1, `r0`..`r7`), `li.zero_hi` (0, `r8`..`r15`) are 2
   bytes; `li.s16` and `li.modimm` 4; `li.u32` 6. A special register always uses `li.sr_u32`.
4. A symbol in a load is always the 6-byte form with a relocation, even when it is a label of the same section.
5. Branches start at the smallest form and **grow** until nothing changes; the table of reaches is in
   [ELF.md](ELF.md#branch-reach). A target that needs a relocation (other section, undefined, weak) takes the form
   with a relocatable field, the smallest one: `call.l`, `goto.l`, the 32-bit `ifeq` family, the 48-bit compare-and-branch forms.
6. A constant that was not known when its line was read (a later `.equ`, or a label difference) is assembled as the
   6-byte load, with the right value (see section 7).

## 4. Directives

| Directive | Meaning |
| --- | --- |
| `.text` `.data` `.bss` `.rodata` | switch section (a subsection number is ignored) |
| `.section NAME[,"flags"[,@type[,entsize]]]` | switch section; flags `a w x M S T`; see [ELF.md](ELF.md#2-file-layout-and-sections) for defaults |
| `.pushsection`, `.popsection`, `.previous`, `.subsection` | section stack (`.subsection` is ignored) |
| `.globl`/`.global`, `.weak`, `.local`, `.hidden`, `.protected`, `.internal`, `.extern` | symbol binding and visibility |
| `.type S,@function` (or `%function`, `STT_FUNC`, `@object`, `@notype`), `.size S,expr` | symbol type and size |
| `.equ`/`.set`/`.equiv` | symbol = expression |
| `.comm S,size[,align]`, `.lcomm S,size` | common / local common symbols |
| `.byte` `.short` `.long` `.int` `.quad` `.2byte` `.4byte` `.8byte` | data (no `.word`, `.half` or `.hword`: JieLi's has none either) |
| `.float` `.single` `.double` | IEEE constants |
| `.ascii` `.asciz` `.string` | strings (C escapes `\n \t \r \b \f \a \v \\ \" \ooo`; no `\x`) |
| `.space N[,v]` `.skip` `.zero N[,v]` `.fill n[,size[,v]]` | fill (a size of 0 bytes is refused, as by JieLi's) |
| `.align N` `.balign N` `.p2align N` `[,fill[,max skip]]` | align (`.align` and `.balign` count bytes, `.p2align` powers of two); raises the section's alignment |
| `.org OFFSET[,fill]` | advance within the section (offset or `.+N`) |
| `.incbin "file"[,skip[,count]]` | include raw bytes |
| `.uleb128` `.sleb128` | LEB128 numbers |
| `.file "name"`, `.ident "text"` | `STT_FILE` symbol; `.comment` string |
| `.error`, `.warning`, `.abort`, `.end`, `.weakref`, `.line` | as named (`.weakref` and `.line` do nothing) |

Not supported (the oracle's assembler has them): `.cfi_*`, `.loc` and debug sections (so no `-g` output), `.symver`,
`.altmacro`, section groups, `.reloc`, `.quad` of a symbol (JieLi's hangs on it).

## 5. Symbols and relocations

See [ELF.md](ELF.md). In short: labels of the same section are resolved here; others get a relocation against the
symbol itself with the constant as addend; the symbol table has no section symbols and is sorted by name.

## 6. Blocks and parallel issue

- `rep N {` / `rep rN {` ... `}`: the body is 1 to 16 words long and the field that holds its length is filled in
  from it; the count is 1 to 32. An empty body is refused.
- `if (...) {` ... `}` and `if (...) { ... } else { ... }` (`ifs`, `iff` the same way). The table's `block` fields
  (second word, bits 15..12) hold the body sizes in **instructions**: bits 15..14 are the number of
  instructions in the first part minus 1 (1 to 4), bits 13..12 the number in the else part (0 to 3). A parallel pair
  counts as one. The assembler fills them in from the body.
  Branches, calls and labels may stand in the body; another `if` or a `rep` may not.
- A parallel pair is `A #` then `B`, where `A` has a `.p` entry (or is a 32-bit form of E000..E7FF: see below)
  and `B` is a load or store with a simple address: the `ld`/`st` word, halfword and byte forms with an
  offset, `[sp+n]`, or post-increment, and `pc = [sp++]`. Anything else is refused ("invalid parallel-B instruction").

## 7. Differences from JieLi's assembler

Added: `--chip ac791n` warns about every line whose form the table's `hw` key marks on that chip (it resets the
chip, does nothing, runs as another form or is unpredictable; [TABLE-FORMAT.md](TABLE-FORMAT.md#hardware-behaviour)),
and `--chip-errors` makes those lines errors. Without `--chip` nothing changes.


Deliberate, so as not to reproduce its bugs:

- `r = r | 0`, `r = r ^ 0`, `r = r & 0xFFFFFFFF` give the modified-immediate form (the table's `asm_wrong`); JieLi's gives a bit-0
  set/toggle/clear instruction.
- A constant that is defined **after** its use, or any difference of labels, in a load becomes the 6-byte `li.u32`
  with no relocation, like JieLi's, but with the value the right way round (JieLi's swaps the two 16-bit halves).
- Odd branch displacements are an error (JieLi's rounds down silently). Branch numbers are not truncated to 32
  bits (`call 0x1000000000` is an error, JieLi's turns it into `call 0`).
- `ifs2ns goto N (c)` checks the range; JieLi's wraps.
- A symbol difference with a symbol from another section, `ext - .`, and the like are errors, not nonsense relocations.
- `.quad symbol` is an error, not a hang. A non-zero byte in a `NOBITS` section is an error at the end of assembly.
- The operand grammar is a little looser: a space may separate `<`/`=` in `<<=`; hex numbers are accepted where JieLi
  wants a decimal literal; an `x@VARIANT` outside the known set is refused. JieLi refuses `r1 = 5 - 2` ("a register is
  expected"); this one takes it.
- `.Ltmp<n>` numbering of anonymous labels follows JieLi's for the cases tested but is not guaranteed to.

Forms the assembler relies on the table for, which were missing when it was first written and are in the table
now: the `.modimm` flavour of the 48-bit compare-and-branch forms (first-word bit 5), the 48-bit mask branches at
`FF60`/`FF61` (`beq.and.modimm.ri.l`, `bne.and.modimm.ri.l`), the parallel twins of the 32-bit E000..E7FF forms,
and the `if`-block shape fields. Should the table ever lack the twin of a 32-bit E000..E7FF instruction, the
assembler still applies the rule (the same instruction with bit 12 of the first word set).

Entries with `asm_no_syntax` (conditions objdump prints as `??`) are refused, as JieLi's assembler refuses them.
`iff (r != r) {` (`iff.ne.rr.1`..`.6`) is refused like JieLi's ("condition not allowed"); use `iff (r u!= r)`.
A symbol named like a register (a C function `pc`) is accepted in directives and data, as JieLi's does, but not
as an instruction operand.

## 8. Testing

```sh
python3 -m unittest tests.test_asm                           # offline: every example round trip, syntax, directives, ELF
python3 -m pi32v2isa oracle asmcompare FILE.S -I DIR         # needs the toolchain: sections, symbols, relocations
python3 -m pi32v2isa oracle linkcompare FILE.S -I DIR        # the same sources linked with JieLi's ld
```

`asmcompare` assembles a file with JieLi's `clang` and with this assembler and reports every difference in header
fields, sections (type, flags, alignment, entry size, size, contents), relocations and symbols; `.c` files are first
compiled to assembly by JieLi's clang. On 2026-10-24 the 11 FM-1 sources (`m-bootloader/src/*.S`,
`Felucca/firmware/crt0.S` and `hal/*.S`, `felucca-bsp/chip/*.S` and `loader/*.S`), 279 `clang -S` outputs (31 C files
from the same repositories at `-O0`, `-O1`, `-O2`, `-O3`, `-Os`, `-Oz`, with `-ffunction-sections`, `-minstrev3` and
`-fPIC` variants) and 30 snippets (`tests/asm/*.s`: each directive, section kind, relaxation boundary and macro feature)
were assembled by both. Objects are byte for byte identical in 307 cases; JieLi's assembler refuses 11 (`-fPIC` output with
`r1 = sym@PI32V2GOT  #`) and so does this one; two snippets differ only by the late-`.equ` bug above. The sources
linked with JieLi's `ld` give identical loaded sections.
