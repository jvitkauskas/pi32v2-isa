# The objdump

`pi32v2isa/objdump.py` prints pi32v2 ELF files the way JieLi's objdump (`common/bin/objdump`, an old LLVM
`llvm-objdump` with changes for pi32v2) does, for the options the FM-1 builds use, so that a build script can call it
instead and parse the same text. It reads the file with `elf.py` and decodes with the instruction table
(`codec.decode` / `codec.format`); it never calls JieLi's tools. They are only used to test it
([section 8](#8-testing)). Facts here are from observing JieLi's objdump on objects and linked files
(source id `oracle`, release `20260730.1`).

```sh
python3 -m pi32v2isa objdump -d firmware.elf                 # what build scripts run: objdump -d ELF
python3 -m pi32v2isa objdump -d -mcpu=r3 -r obj.o            # code with relocation records
python3 -m pi32v2isa objdump -d -j .ram_text -j .c1_text app.elf
python3 -m pi32v2isa objdump -h -t app.elf                   # section headers, symbol table
```

From Python: `objdump.main(["-d", "app.elf"])` writes to `sys.stdout`; `objdump.run_file(objdump.File(path),
opts, table)` returns the text.

## 1. What the FM-1 builds use

| Build script | Calls | What it reads |
| --- | --- | --- |
| Felucca `tools/build.py` (app and loader) | `objdump -d ELF`, `-h ELF`, `-t ELF`, `-d -j .ram_text [-j .c1_text] ELF` | the listing is saved as `felucca.dis` (and read by `tests/target_budget.py`: labels, `addr:  bytes  text`, `goto N <sym+off : addr >`, `< n : 0xN >` lines); `-h` rows `NAME SIZE VMA` (`p[1]`, `p[2]`, `p[3]`); `-t` lines ending in `NAME` (`^addr .*\sNAME$`) |
| fm1-base `tools/build.py` | the same four calls | the same |
| felucca-bsp `examples/hwtest/build.sh` | `objdump -t ELF` | symbol addresses |
| m-bootloader `tools/check_build.py` | `objdump -d ELF` (no `-mcpu`) | `^\s*addr:\s+bytes\s+text` lines of the startup code, and `<boot_main` in a `goto` |

None of them uses `-mcpu`, `-r`, `-D` or `-print-imm-hex`; they are supported (all but the last) because the
brief asked for them. To switch a build over, call `python3 -m pi32v2isa objdump` where it calls
`common/bin/objdump`; the output is the same text on every input tried ([section 8](#8-testing)).

## 2. Options

| Option | Meaning |
| --- | --- |
| `-d`, `-disassemble` | disassemble the executable sections (`SHF_EXECINSTR`, not `NOBITS`, not empty) |
| `-D`, `-disassemble-all` | every section: code as code, data sections as text ([5.5](#55-d-and-data-sections)) |
| `-h`, `-section-headers` | section table |
| `-t` | symbol table |
| `-r` | relocation records (inside `-d`/`-D` after each symbol's code, alone as a list per `.rela` section) |
| `-s` | contents of each section, hex and ASCII |
| `-j NAME`, `-section=NAME` | only these sections (repeat for several); `-h`, `-d`, `-D`, `-s` and `-r` (which matches the `.rela...` section's name) obey it, `-t` does not |
| `-mcpu=r3` (or `r4`), `-mattr=+fprev1` | also decode the floating-point forms ([5.9](#59-cpu-options)) |
| `--chip=ac791n` | not JieLi's: append `; ac791n: resets the chip` (or `does nothing`, `runs as ID`, `gives unpredictable results`) to forms the table's `hw` key marks ([TABLE-FORMAT.md](TABLE-FORMAT.md#hardware-behaviour)); the output is otherwise unchanged |

Anything else (`-print-imm-hex`, `-start-address`, `-stop-address`, `-no-show-raw-insn`, `-no-leading-addr`,
`-source`, `-g`, `-line-numbers`, the Mach-O options) is refused with `objdump: unsupported option` and status 1.
`-mcpu=r1` is refused too (it changes 418 forms, [5.9](#59-cpu-options)). Several files may be given. A file that
cannot be read or is not ELF gives `objdump: 'FILE': ...` on stderr and status 1 (JieLi's stops at the first such file
too).

When several actions are asked, the order is always: file header, disassembly (with `-r` inside it), `-r` alone,
`-h`, `-s`, `-t`.

## 3. The file header

Every file starts with `"\n" + FILE + ":\tfile format ELF32-pi32v2" + "\n\n"`. `FILE` is the argument as given.

## 4. The tables

### 4.1 `-h`

```
Sections:
Idx Name          Size      Address          Type
  0               00000000 0000000000000000 
  2 .text         0000005e 0000000000050000 TEXT DATA 
```

Rows are `"%3d %-13s %08x %016x %s"`: the number, the name (longer names push the rest right), `sh_size`
(also for `NOBITS`), `sh_addr`, and the type words. Without `-j` the number is the section index and every
section is listed, including number 0; with `-j` only the chosen sections are listed and the numbers count from 0.
The type words are the concatenation of `"TEXT "` when the section has `SHF_EXECINSTR`, `"DATA "` when it is
`PROGBITS` with `SHF_ALLOC` or `SHF_WRITE`, and `"BSS"` when it is `NOBITS` with `SHF_ALLOC` or `SHF_WRITE`; so
`TEXT DATA ` (with the trailing space), `DATA `, `BSS` (no space), or nothing (a trailing space after the
address). `.rodata` is `DATA `; `.note`, `.init_array`, `.strtab`, `.symtab` and `.rela.*` show nothing.

### 4.2 `-t`

```
SYMBOL TABLE:
00000000         *UND*		 00000000 
01c08000 l    d  .data		 00000000 .data
00000000 l    df *ABS*		 00000000 build/fm1_cpu1.o
0207bf14 l       .text		 00000020 NOISE_TAPS
000000ec g     F .text		 00000008 addr
00000008  w      .text		 00000000 w1
```

Every symbol, in table order (the null symbol first). A line is
`"%08x" ADDR " " GLOB WEAK "   " DEBUG FILEFUNC " " SECTION "\t\t " "%08x" SIZE " " NAME`:

- GLOB is blank for `NOTYPE`, else `g` for a global or weak symbol and `l` for a local one. WEAK is `w` for weak.
  DEBUG is `d` for `SECTION` and `FILE` symbols. FILEFUNC is `f` for `FILE`, `F` for `FUNC`, else blank (no letter
  for objects).
- SECTION is the section's name, `*UND*` (index 0 and the reserved indices other than `ABS`/`COMMON`), `*ABS*`,
  or `*COM*` for index `COMMON` or type `COMMON`. ADDR and SIZE are `st_value` and `st_size`, with these
  exceptions: an undefined symbol (index 0) prints address 0 (and its size, 0 for type `COMMON`); a `COMMON`
  index prints the size as the address and the value as the size; type `COMMON` in a section prints the size as the
  address and size 0.
- A `SECTION` symbol is printed with its section's name whatever its table name is; a symbol with
  `st_other` visibility hidden gets `.hidden ` in front of the name (protected and internal print nothing).
- A section index that names no section (`5`..`0xFEFF` beyond the section count, `0xFFFF`) makes JieLi's objdump stop
  with `invalid section index` in `-t`, `-d` and `-D`; this one does the same.

### 4.3 `-r` alone

```
RELOCATION RECORDS FOR [.rela.text]:
0000001a R_PI32V2_LONG_JUMP_23M2 Unknown
<blank line>
```

One block per `SHT_RELA` section (all of them, in section order): `"%08x NAME Unknown"` with the offset in the
patched section and the type's name, always followed by the word `Unknown` (the symbol is not printed). Names:
types 0-16 are `R_PI32V2_NONE`, `LONG_JUMP_17M2`, `LONG_JUMP_23M2`, `EXTEND_JUMP_17M2`, `EXTEND_CALL_32M2`,
`MOV_ABS32`, `ABS8`, `ABS16`, `ABS32`, `GOT`, `GOTFUNCDESC`, `FUNCDESC`, `FUNCDESCVALUE`, `REL32`, `MOV_ABS16`,
`GOT16`, `GOTFUNCDESC16`; any other type prints `Unknown`.

### 4.4 `-s`

```
Contents of section .text:
 1c0a800 04884645 4c554343 412d4c4f 41444552  ..FELUCCA-LOADER
```

For every section except number 0 and the empty ones: `" %04x "` (the address, at least 4 digits) then the bytes in
groups of four, padded to 35 columns, two spaces, and the printable ASCII (`.` otherwise); 16 bytes a line. A `BSS`
section (see 4.1) prints `<skipping contents of bss section at [START, END)>` instead; other `NOBITS` sections print
the file's bytes at their offset.

## 5. Disassembly

### 5.1 Sections, symbols and labels

`Disassembly of section NAME:` for each section (in section order) with code to show (empty and, without `-D`,
`NOBITS` sections are skipped). The section is cut into blocks by its symbols:

- The symbols of the section are those with its index, except `SECTION` symbols, empty names and names that
  start with `.L`. They are sorted by (address, name); a symbol that shares its address with a later one in this
  order is not a label. If none is at the section's start, one named after the section is added there
  (`.text:`). A symbol below the section's address (the linker's `__bss_start` before `.bss`) makes no block.
  For type `COMMON` the "address" is `st_size`, as in `-t`.
- A block runs to the next symbol or the section's end. The label line is `NAME:`; every label but the first of
  the section is preceded by a blank line, and every code or hex-dump block is followed by one, so blocks are
  separated by two blank lines and the section ends with one.
- A block of an `OBJECT` symbol is printed as a hex dump ([5.4](#54-data-in-code-and-jump-tables)) unless `-D`.
- Blocks are independent: an instruction that starts in one block may extend into the next, which then starts
  decoding at its own symbol.

### 5.2 An instruction line

```
       4:    14 e8 00 11       \tif (r4 == r1) {
```

`"%8x:    "` (address, colon, four spaces), the bytes as `"%02x "` each padded to 18 columns, a tab, the text
(from the table: `codec.format`). Exceptions to the table's text: the word loads `ld.w`, `ld.w.pi`, `ld.w.pin`
keep a space at the end (`r1 = [r1+0] `), as JieLi's do.

An address that is not an instruction: `"%8x:    "` + bytes padded to 18 + a space + `<unknown instruction>` (no tab).
How many bytes it takes: a word that does not match any form takes 2 bytes; if the form its first word announces
(2 bytes below `E000`, 6 for `FF00`-`FFEF`, else 4) does not fit before the end of the section it takes 1; if not
even one word fits, the length of the last instruction printed is used again (it is shared by all blocks and
sections and is the entry size after a jump table), and the bytes shown are taken from the file, past the
section's end if need be.

### 5.3 Branch and constant annotations

The forms with a branch offset (`goto`, `call`, every `if (...) goto`, `ifeq goto`, `dbnz`, `gotoss`; not
`goto r1` and not `ifs2ns goto`) and the forms `li.s16`, `li.s16.p`, `li.u32` (`r1 = 0x12345678` as a 16- or 32-bit
constant; not the special-register loads) end with ` <SYMBOL+0xOFFSET : ADDRESS >`:

- ADDRESS is, for a branch, the address after the instruction plus the printed offset; for a constant its value
  (negative values sign-extended to 64 bits); then the lowest bit is cleared. It is printed in 64 bits (`ffffffffffffff1e`).
- SYMBOL is the symbol with the greatest address at or below ADDRESS (comparing unsigned), ties as in 5.1 (the last by
  name). In a relocatable object only the symbols of the same section count, including the section-named one at its
  start; in a linked file all symbols of the file count (not the null symbol, not `SECTION` symbols, not names starting
  `.L`; `FILE` and absolute symbols do).
- `OFFSET` is `+0x` and the upper-case hex difference, left out when 0. A relocation is not looked at: an unrelocated
  `call 0` in an object is `<f+0x1E : 1e >`.

The listing's `goto 2 <_start+0x4 : 4 >` is therefore the target address and the nearest label; the first number is the
table's own text.

### 5.4 Data in code and jump tables

- A block of an `OBJECT` symbol (not with `-D`): rows of up to 8 bytes `"%8x:\t"`, then `" %02x"` for each byte padded to
  33 columns, then the printable ASCII. No `Size` is changed by it.
- The compiler's jump tables are marked by local symbols named `.GJTIS...` (a table of bytes), `.GJTIE...` (its end)
  and `.GJTI` followed by any other letter (`.GJTIL...`: halfwords). The block of a table symbol has the label line and
  then one row per entry: `"%8x:    "`, the bytes as `"%02x"` joined by a space, five spaces and `< VALUE : 0xHEX >`
  (little-endian unsigned, hex upper-case): `      1c:    03     < 3 : 0x3 >`. A halfword table whose last entry crosses the
  end of the block still prints it whole. The `.GJTIE` symbol starts a block with no label line and none of the
  usual blank lines; the code goes on from there. Tables print no blank line after them and no relocation records
  ([5.6](#56-relocations-in-disassembly)). A table row sets the "last length" of 5.2 to its own.

### 5.5 `-D` and data sections

With `-D` the sections without `SHF_EXECINSTR` are listed too (all but the null one and empty ones, including
`.strtab` and `.symtab`). Executable sections are disassembled whatever their symbols are (an `OBJECT` symbol no longer
makes a hex dump), a `NOBITS` executable section from the bytes in the file. A section that is `DATA` (see 4.1) is
printed four bytes a row: `"%8x:    "`, the bytes as `"%02x "` padded to 16, and the bytes in double quotes: printable
characters as they are (including `"` and `\`), NUL as `\0`, 8, 9, 10, 13 as `\b \t \n \r`, and any other byte as
`\x` and its low four bits as two hex digits (`0x7f` is `\x0f`, `0x80` is `\x00`, `0x10` is `\x00`). There is no blank line
after such a block. Other sections (not code or data, or `NOBITS`) get only their label lines.

### 5.6 Relocations in disassembly

With `-r`, after the blank line that ends a code or hex-dump block, the records are printed whose offset is below a
limit; they are taken in the table's order and the first at or past the limit stops the list. The limit is the end of
the block plus the length of its last instruction (`block_end + size`); for a hex dump it is the end of the block
plus one. A record for the next block's first instruction is therefore printed after the previous block, and the
records of a table block are printed after the code that follows it. Each line is `"\t\t\t%08x:  NAME\tUnknown"`;
the names are those of 4.3. Records left over at the end of the section are not printed.

### 5.7 Blocks and parallel pairs

Two things print differently from the table text:

- **Parallel pairs.** The first instruction of a pair is a form with a first word in `C000`-`DFFF` or `F000`-`F7FF`
  (the table's `.p` twins; also the vector compares `all`/`any`/`cmp ... (v)` there, which print no `#`). The next
  instruction printed (an unknown word does not count) is the second half: its line has the usual tabs (one, plus one
  per open block) and then a tab and a space, or two spaces when an `if` block is open: `\t\t ` at the top level,
  `\t\t\t ` in a `rep`, `\t\t  ` in an `if`. The state goes on across labels and sections.
- **Blocks.** `rep` (a table entry with `body`) and `if`/`ifs`/`iff` (`block`) openers print the table text. The body is
  indented one more tab per open block (one `rep` and one `if` at most: a new `rep` replaces the open `rep`, a new
  `if` replaces the open `if`; both can be open, the `if` inside). Brace lines are `31 spaces + \t + "}"`, or `"} else {"`.
  They are added to the last instruction's text, so a branch annotation follows them: `\t}` ... ` <sym+0x4 : 8 >`.
  - A `rep`'s body length is its field's value in bytes; every printed instruction (second halves of pairs too)
    counts its length; it ends at the first instruction that brings the count to 0 or below. An unknown word does not count.
  - An `if` block counts instructions (a parallel pair as one, the second half is not counted): the then-part
    `t + 1`, the else-part `e` (the opener's `block` fields); `} else {` follows the then-part's last
    instruction when the else-part is not empty, `}` follows the last one.
  - The closing of a pair is added to its second half (after the second half's text), with 32 spaces instead of the
    tab; a `rep` closes on the first half already, with the tab.
  - A `rep` opener that ends another `rep` loses its ` {`: `rep 6 r10` then `\t} {`.
  - If the instruction that completes an `if` body is a compare-and-branch (`beq.rr`, `bne.ri`, `bge.rr.l`, `bfeq.rr`...) or a
    vector compare (`cmps ... (v)`), the block is not closed and stays open, indenting everything after it, until the next
    `if` opener replaces it. The exception is the instruction that directly follows and starts a pair (a first half other than
    a vector compare): it closes the block then (before its second half), in the then-part with a `} else {`
    if there is an else-part. This is the only effect of these forms (`NO_CLOSE`, `NO_FLUSH` in the code).

The compiler's code and the assembler's blocks (non-nested, shapes as the table says) are the common case and
are exact; the rest was found with random instruction streams ([section 8](#8-testing)).

### 5.8 Instruction text

The table's `syntax` is what objdump prints (that was how the table was confirmed), so the text is
`codec.format(insn, values)`; the first matching entry in table order is used (entries that need a CPU option are
skipped without it, 5.9).

### 5.9 CPU options

With no `-mcpu` the 91 floating-point forms (`(f)` arithmetic and conversions, `fcmp`, `iff` compares and branches) and
six others (`copex`, and the `shiftr` forms with a mode) read as `<unknown instruction>`. `-mcpu=r2` adds those six;
`-mcpu=r3` and `-mcpu=r4` add all of them; `-mattr=+fprev1` adds the 91 floating-point forms only. `-minstrev1`..`3`
change nothing. `-mcpu=r1` removes 418 forms and adds 38 (not implemented); an unknown CPU name is a warning
in JieLi's and an error here. The lists are `FPU_IDS` and `R2_IDS` in `objdump.py` (found by decoding every table
example with and without each option).

## 6. Using it in a build

Replace the tool, nothing else:

```python
OBJDUMP = [sys.executable, "-m", "pi32v2isa", "objdump"]      # was toolchain/common/bin/objdump
dis = subprocess.check_output([*OBJDUMP, "-d", elf], text=True)
```

It takes 2 to 4 seconds of CPU time for Felucca's 566 KB firmware (JieLi's takes 0.1 s). Nothing needs the toolchain.

## 7. Known differences

- The options in section 2 that are refused; `-mcpu=r1`; archives, ELF64 and big-endian files.
- JieLi's tool prints the part of its output that came before an error (a bad symbol index); this one prints
  nothing for the file.
- Block bookkeeping beyond 5.7 (a block left open, nested openers inside a stuck block, `rep` bodies that start in the
  middle of an instruction) was matched on random streams but not derived: of 400 random instruction streams 2 differ
  (a `rep` opener that closes a block when it is the second half of a pair prints its `} {` with the tab in one, and in
  in the other a stuck `if` block ends after a chain of pairs where JieLi's closes it one instruction earlier).
- `<unknown instruction>` depends on the table: a form JieLi decodes and the table lacks would show as unknown
  ([GAPS.md](GAPS.md)). None was found in the compiler's output, the FM-1 sources and the random streams.

## 8. Testing

```sh
python3 -m pi32v2isa oracle objdumpcompare FILE...  [-d] [-mcpu=r3] [-j SECTION] ...
python3 -m unittest tests.test_objdump
```

`objdumpcompare` runs JieLi's objdump and this one on each file with the same options and compares the text line by
line; with no options it runs the standard sets (`-d`, `-d -mcpu=r3`, `-d -r`, `-D`, `-h`, `-t`, `-r`, `-s`) and prints
one line per file and set (`identical` or the number of differing lines with the first few). `--show N` shows
more of them. The unit tests check the exact text on a built-in object and on hand-made ELF files; with the
toolchain present they also compare compiled code, a linked executable and random streams.

Results (2026-10-24, toolchain 20260730.1):

| Input | Option sets | Result |
| --- | --- | --- |
| 191 objects: the 11 FM-1 `.S` files assembled with JieLi's clang (m-bootloader 2, Felucca 4, felucca-bsp 5), the 50 files of `tests/corpus` at -O0/-O2/-Os (150), the 30 `tests/asm` snippets | the 8 standard sets | 1528 comparisons, all identical |
| Felucca app (`felucca.elf`, 566 KB; `felucca.o` 1.1 MB) and update loader, built as `tools/build.py` does | the 8 sets, `-d -j .ram_text -j .c1_text`, `-h -j .text` | identical (`-d`: 124 409 lines) |
| m-bootloader: `uboot.elf` (FM-1, SMK37), `installer.elf`, `loader.elf` (LTO and `--relax`) | the same | identical |
| 81 executables linked with JieLi's `ld` from the objects above (the `-O2` corpus files and the `.S` objects) | `-d`, `-d -mcpu=r3`, `-D`, `-h`, `-t`, `-s`, `-d -r` | identical |
| random objects: 400 instruction streams (table forms with random fields and noise, pairs, blocks, jump-table symbols, relocations), 180 well-formed `if`-block streams, 52 symbol tables with every type, binding, visibility and section index, 30 relocation tables with every type | `-d -mcpu=r3 -r`, `-d -r`, `-D`; the symbol and relocation ones `-t -h -r -s -d -r` | all identical except 2 of the 400 streams (section 7) |

fm1-base's own build needs JieLi's AC79 SDK (`uboot.boot`), which is not available here, so its executable was not
produced; it calls the same four commands on code the BSP objects above cover.
