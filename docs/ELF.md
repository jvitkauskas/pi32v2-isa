# ELF object files

What JieLi's assembler writes (relocatable objects) and what JieLi's linker does with them, as observed with the
oracle ([ORACLE.md](ORACLE.md); source id `oracle`). The repo's assembler (`pi32v2isa/asm.py`, writer in
`pi32v2isa/elf.py`) produces the same layout: of 307 objects (the 11 FM-1 `.S` files, 268 outputs of JieLi's
`clang -S` for 31 C files in nine compile modes, and 28 test snippets) it wrote the same bytes as JieLi's
assembler in all 307; two further snippets differ only by an assembler bug JieLi's has
([ASSEMBLER.md](ASSEMBLER.md)), and JieLi's own assembler refuses 11 more files (`-fPIC` output with
`r1 = sym@PI32V2GOT  #`). Evidence is reproducible with `python3 -m pi32v2isa oracle asmcompare FILE` (objects) and `oracle linkcompare FILE`
(objects linked with JieLi's `ld`).

## 1. Header

- ELF32, little-endian, `EI_VERSION` 1, `EI_OSABI` 0 (System V), ABI version 0, `e_type` `ET_REL`,
  `e_machine` 0xF1 (241), `e_version` 1, `e_entry` 0, no program headers, `e_ehsize` 52, `e_shentsize` 40.
- `e_flags` is 0 in every object seen: assembly and C, `-mcpu=r1` to `r5`, with and without `-mfprev1` and
  `-minstrev3`. The linker ignores the flags too (it ignored 0x1234 in a patched object) and writes 0.
- `e_shstrndx` is 1: the section name table is the same section as the symbol string table.
- Only `.o` files from `clang -c` are plain ELF. With `-flto` the file is LLVM bitcode, which is not covered
  here.

## 2. File layout and sections

File order: the header (52 bytes), the contents of the user sections in the order they were created (each at
its alignment), `.symtab` (4-aligned), the `.rela` sections (4-aligned), `.strtab`, then the section header
table (4-aligned, after the last byte).

Section header order differs from the file order:

| Index | Section |
| --- | --- |
| 0 | the null section |
| 1 | `.strtab` (type `SHT_STRTAB`; also the section name table) |
| 2.. | the user sections in the order the source first switched to them, each followed at once by its `.rela<name>` section if it has relocations |
| last | `.symtab` |

- `.text` is always section 2, even when empty, because the assembler starts in it; it is the only section
  created implicitly. `.data` and `.bss` exist only if the source uses them.
- `.rela<name>` is `SHT_RELA`, `sh_flags` 0, `sh_link` the `.symtab` index, `sh_info` the index of the section
  it patches, `sh_addralign` 4, `sh_entsize` 12. Only RELA is used, never REL.
- `.symtab`: `sh_link` 1 (`.strtab`), `sh_info` the number of local symbols including the null symbol,
  `sh_addralign` 4, `sh_entsize` 16.
- `sh_addralign` of a user section is 1, or 2 for `.text`; each alignment directive (`.align`, `.balign`,
  `.p2align`) raises it to the largest boundary asked for in that section.
- Flags and types: `.text` `AX` (`PROGBITS`), `.data` `WA`, `.bss` `WA` (`NOBITS`), `.rodata` `A`, `.init`
  and `.fini` `AX`. For any other name `.section NAME` with no flags gives flags 0 and `PROGBITS` (`.text.foo`
  gets no flags; a name starting `.note` gets `SHT_NOTE`). `.section NAME,"flags",@type,args` sets them: `a`
  alloc, `w` write, `x` exec, `M` merge, `S` strings, `T` TLS; types `progbits`, `nobits`, `note`,
  `init_array`, `fini_array`, `preinit_array`. A mergeable section's `sh_entsize` is the fourth argument
  (`.rodata.str1.1,"aMS",@progbits,1` has `sh_entsize` 1). `.ident "x"` creates `.comment` (`MS`, entsize 1,
  contents: a NUL, then each string and its NUL).
- A `NOBITS` section occupies no file bytes; its `sh_size` counts the space reserved. Only zeros may be
  assembled into it (JieLi refuses `.byte 1` in `.bss`; `.long 0` is accepted).

## 3. String table

One table serves both section names and symbol names (and `sh_name` of every section points into it). It starts
with a NUL. Strings are laid out sorted by their **reversed** spelling, largest first, and a string that ends
the previous string in that order shares its bytes (`.text.crt0` lives inside `.rela.text.crt0`). The
layout is strange but deterministic (it reproduces every table seen), for example:

```
00 .text 00 fm1_cstart 00 _start 00 _ustack_top 00 _sstack_top 00 .strtab 00 .symtab 00 .rela.text.crt0 00
```

(reversed: `txet.`, `tratsc_1mf`, `trats_`, `pot_kcatsu_`, `pot_kcatss_`, `batrts.`, `batmys.`, `0trc.txet.alere.`, in
descending order.)

## 4. Symbols

- Entry 0 is the null symbol. Each `.file "name"` in the source adds a `STT_FILE` symbol (local, `SHN_ABS`,
  value 0) named by the argument as written, in order, before all other symbols.
- Then the local symbols sorted by name (byte order), then the global and weak ones (together, also sorted by
  name). There are **no section symbols**.
- Symbols not in the table: assembler temporaries (names starting `.L`) are dropped unless a relocation names
  them (then they appear as ordinary locals: `.Lswitch.table`); the anonymous labels made for `.` and for
  numeric labels `1:` are named `.Ltmp<n>` (n counts from 0 in creation order, shared by both) and follow the same rule.
- Undefined symbols appear if a relocation uses them or they were declared `.globl`/`.weak`; they are global
  (weak if declared so), `SHN_UNDEF`, size 0.
- `st_info`: `STB_LOCAL`, `STB_GLOBAL` (`.globl`), `STB_WEAK` (`.weak`); `st_other` 1/2/3 for
  `.internal`/`.hidden`/`.protected`. `.type NAME,@function|@object|@notype` (also `%function`, `STT_FUNC`)
  sets `STT_FUNC`/`STT_OBJECT`/`STT_NOTYPE`; labels have `STT_NOTYPE` unless typed. `.size NAME,expr` sets `st_size` (an expression such as
  `.-NAME` is evaluated at the end).
- `.set`/`.equ` to a constant gives a `SHN_ABS` local symbol of that value (global if declared); to an
  expression with a label (`.set A, L+4`) gives a symbol in L's section with value L+4 (an alias): it takes the
  type and size of the symbol it names.
- `.comm NAME,size,align` gives a global `STT_OBJECT` symbol, `SHN_COMMON`, `st_value` the alignment,
  `st_size` the size. After `.local NAME` the same directive allocates in `.bss` instead (local `STT_OBJECT`
  symbol with the size, the section aligned). `.lcomm NAME,size` allocates in `.bss` the same way.

## 5. Relocations

- Entries are `Elf32_Rela`: `r_offset`, `r_info` (symbol << 8 | type), `r_addend` (signed). The bytes being
  patched hold zero in the object.
- `r_offset` is the address of the **first word** of the instruction (or of the data item), whatever field is
  patched. The relocation names the symbol itself, never a section symbol: a reference to a local label of
  another section uses that label, addend 0, with the label kept in `.symtab`.
- The addend is the constant part of the expression (`sym+4` gives +4, `sym-8` gives -8, `4+sym` gives +4).
  Only `symbol`, `symbol + constant` and `symbol - constant` can be relocated; JieLi's assembler turns other
  expressions with symbols into nonsense (`.long ext-.` gives the symbol with the `-.` lost), or refuses them.
- Where a relocation is **not** needed: a branch (`goto`, `call`, the conditional branches) to a label defined
  in the same section is resolved by the assembler, unless the label is weak. A label in another section, an
  undefined symbol or a weak symbol gets the long form of the instruction and a relocation. Loads of a symbol
  (`r1 = sym`) always get one, even for a label of the same section.

| Type | Name | Used for | Patched bytes (instruction words w0 w1 w2 from `r_offset`, little-endian) | Value |
| --- | --- | --- | --- | --- |
| 0 | `R_PI32V2_NONE` | | | |
| 1 | `R_PI32V2_LONG_JUMP_17M2` | the 32-bit conditional branches with a 16-bit offset: `ifeq goto` and its family, `dbnz.r`, `beq.and.rr`, `bne.and.rr` (field `n`) | all of w1, signed | (S + A - (P + 4)) / 2 |
| 2 | `R_PI32V2_LONG_JUMP_23M2` | `call.l`, `goto.l` (field `n`, letters `ps`) | low 6 bits of w0 (high part), all of w1 (low 16 bits); signed 22 bits | (S + A - (P + 4)) / 2 |
| 3 | `R_PI32V2_EXTEND_JUMP_17M2` | the 48-bit compare-and-branch forms (`beq.ri.l`... `bfule.rr.l`, the mask branches) | all of w2, signed | (S + A - (P + 6)) / 2 |
| 4 | `R_PI32V2_EXTEND_CALL_32M2` | `gotoss.xl`, `call.xl` | bits 15..1 of w1 (low 15 bits) and all of w2 (high 16 bits); bit 0 of w1 (the `gotoss`/`call` selector) is kept | (S + A - (P + 6)) / 2, 31 bits, not range-checked |
| 5 | `R_PI32V2_MOV_ABS32` | `li.u32`, `li.sr_u32`: `r1 = sym`, `psr = sym` | w1 (low half) and w2 (high half) | S + A |
| 6 | `R_PI32V2_ABS8` | `.byte sym` | 1 byte | S + A + in-place value (signed); both S + A and the sum must fit signed 8 bits ([LINKER.md](LINKER.md) §3) |
| 7 | `R_PI32V2_ABS16` | `.short sym` | 2 bytes | S + A + in-place value (signed); both S + A and the sum must fit signed 16 bits |
| 8 | `R_PI32V2_ABS32` | `.long`/`.int`/`.4byte sym` | 4 bytes | S + A + in-place value |
| 9 | `R_PI32V2_GOT` | `r1 = sym@PI32V2GOT` (what `-fPIC` code uses) | as 5 | as 5 in a static link |
| 10 | `R_PI32V2_GOTFUNCDESC` | `r1 = sym@PI32V2GOTFUNCDESC` | as 5 | as 5 in a static link |
| 11 | `R_PI32V2_FUNCDESC` | `.long sym@GOT` and any other `@variant` on a `.long` | 4 bytes | as 8, but the sum must stay in the signed 32-bit range |
| 12 | `R_PI32V2_FUNCDESCVALUE` | not written by the assembler | 4 bytes | as 11 |
| 13 | `R_PI32V2_REL32` | not written by the assembler | 4 bytes | as 11 (not PC-relative in a static link) |
| 14 | `R_PI32V2_MOV_ABS16` | not written by the assembler | w1 | S + A, -32768..32767 |
| 15, 16 | `R_PI32V2_GOT16`, `R_PI32V2_GOTFUNCDESC16` | not written by the assembler | w1 | as 14 |

P is `r_offset`. The offset of a branch is counted from the **end** of the instruction (P+4, or P+6 for the
48-bit forms) and divided by 2; this matches objdump, which prints the branch offset from the end. A relocation
with a variant on a data directive is the plain data type (`.short x@GOT` is 7), except `.long` which gets 11.
Names and numbers are those of JieLi's `objdump -r` (readelf shows them as unrecognised) and its linker; the linker accepts
exactly types 0 to 16 (17 and above abort it).

### Which operands take a symbol

Only these (everything else with a symbol gives "immediate out of range" or "a register is expected"):
`rN = sym` and `srN = sym` (type 5), `call`/`goto` (2), the `ifeq`-family, `dbnz` and `if ((rA & rB) ...)`
branches (1), the compare-and-branch forms against a register or number (3), `gotoss` (4), and the data
directives (6, 7, 8, 11). A symbol operand never relaxes into `call.xl`.

### Branch reach

The assembler picks the smallest form that fits, growing instructions until nothing changes. The reach of
a form is the table field's range (offsets in bytes, from the end of the instruction):

| Family | Forms, smallest first | Reach |
| --- | --- | --- |
| `goto L` | `goto.s`, `goto.l` | -2048..2046; -4194304..4194302 |
| `call L` | `call.s`, `call.l` | -256..254; -4194304..4194302 |
| `if (r0..r7 ==/!= 0) goto L` | `beqz`/`bnez`, `beq.ri`/`bne.ri`, `beq.ri.l`/`bne.ri.l` | -256..254; -512..510; -65536..65534 |
| `if (rA op rB) goto L` (all conditions, `if`, `ifs`, `iff`) | `*.rr`, `*.rr.l` | -512..510; -65536..65534 |
| `if (rN op imm) goto L` | `*.ri`, `*.ri.l` (the immediate chooses the minimum, then the distance) | as above |
| `ifeq goto L` family, `dbnz`, `if ((rA & rB) == 0)` | one 32-bit form | -65536..65534 |
| `if ((r & mask) == 0) goto L` | `beq.and.ri` (single-bit mask), else `beq.and.rm.l` (48-bit) | -512..510; -65536..65534 |
| `gotoss L` | `gotoss.xl` only | |

Out of range for the largest form, JieLi's assembler fails. A number instead of a label is the displacement from the
end of the instruction (`goto 100`), and `.` is the start of the instruction (`goto .` is -2).

## 6. What the linker checks

Observed with JieLi's `ld` (GNU ld 2.26.51 with the `elf32-pi32v2` backend; default script when none is given: text at
0x50000), by patching good objects field by field:

- Required: `e_machine` 0xF1. Ignored: `e_flags`, `EI_OSABI`, ABI version, the `sh_flags`/`sh_addralign`/`sh_entsize`
  of `.text`, symbol types, `e_shstrndx` 0, `.symtab`'s `sh_info` 0, the string table's layout.
- Refused ("file not recognized: Bad value"): a `.symtab` `sh_info` beyond the symbol count, a `.rela` section
  whose `sh_info` names a section of the wrong type, a `.rela` with `sh_entsize` 0.
- Branch and `MOV` relocations (1 to 5) **overwrite** the field (the in-place value is ignored); data
  relocations (6 to 8, 11 to 13) add the in-place value, read as signed. The objects contain zeros, so RELA
  with zeros is right. (Ranges corrected after linking tests in round 3; [LINKER.md](LINKER.md) §3.)
- Errors: "relocation truncated to fit: R_PI32V2_LONG_JUMP_23M2 against symbol `x`" when the offset does not fit;
  "relocation unaligned" for an odd branch displacement; "undefined reference to `x`". A weak undefined
  symbol resolves to 0.
- `--defsym=name=value` supplies an undefined symbol. Linking the repo's objects and JieLi's for the same
  source gives identical loaded sections (`oracle linkcompare`).

Examples (P = 0x1000): `call ext` with ext = 0x1004 patches to `80 ea 00 00`; with ext = 0x1000, `bf ea fe ff`;
`r1 = ext` with ext = 0x12345678 patches to `c1 ff 78 56 34 12`.
