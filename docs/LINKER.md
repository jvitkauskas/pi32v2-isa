# The linker

`pi32v2isa/ld.py` (script parser in `pi32v2isa/ldscript.py`) links the relocatable objects of [ELF.md](ELF.md) into an
executable, the way JieLi's `ld` (GNU ld 2.26.51 with the `elf32-pi32v2` backend) does for the FM-1 projects. Facts
here come from linking small test objects and the FM-1 projects with JieLi's `ld` and comparing (source id `oracle`,
[ORACLE.md](ORACLE.md)); nothing was read from the toolchain's binaries or from GNU source.

```sh
python3 -m pi32v2isa ld [options] objects... -o OUT
python3 -m pi32v2isa ld --gc-sections -e _start -T app.ld -Map app.map crt0.o main.o -o app.elf
```

Options (GNU ld's spelling): `-o`, `-T SCRIPT` (repeatable), `-e SYM|ADDR`, `--gc-sections`, `-Map FILE`,
`--defsym=NAME=EXPR`, `-u SYM`, `-L DIR`, `-lNAME` (archives `libNAME.a`), `-Ttext=ADDR` (changes the default
script's start), `--start-group`/`--end-group`, `--allow-multiple-definition`, `--noinhibit-exec`,
`--print-gc-sections`. `--relax`, `-O`, `-static`, `-z ...`, `-m ...`, `--plugin ...` and other options are accepted and ignored
(`--relax` changes nothing in JieLi's `ld` either: linking the same objects with and without it gave identical files).
Not supported: `-r`, shared objects, REL relocations, LTO bitcode (the plugin), `PHDRS`, `VERSION`, `OVERLAY`,
`INCLUDE`, `CONSTRUCTORS`. Exit status is 1 and no file is written if there are errors.

## 1. Validation

`python3 -m pi32v2isa oracle ldcompare -- <ld arguments>` links with JieLi's `ld` and with this linker and compares
the loaded sections (addresses, types, contents), symbols (name, value, size, binding, type, section), entry point,
program headers, section headers, symbol order and string table; it prints the differences by category and also compares
`objcopy -O binary -j SECTION` (JieLi's objcopy; stock GNU objcopy 2.44 refuses these files: "program header with
invalid alignment", their `p_align` is 0x500) for every loaded section.

On 2026-10-24, with the 20260730.1 toolchain, **all 13 links of the FM-1 projects, and 4 more Felucca app variants, are byte-for-byte identical files**
(not just loaded contents):

| Project | Links |
| --- | --- |
| m-bootloader (non-LTO objects; the boot and installer scripts' size `ASSERT`s relaxed, see below) | boot and installer for `fm1` and `smk37` (4), flash loader A and B (2) |
| Felucca | update loader, app (variants not counted in the 13: `FELUCCA_CPU2=0`, the IR size pass, OTA/CDC/UAC options, plain) |
| fm1-base (branch open-ble) | loader, app with `--open-ble` (78 objects, 1700 symbols), app with `--no-ble`, bsp hwtest (2) |

Further evidence: the complete fm1-base `tools/build.py template --open-ble` and `--no-ble` builds were run with
this linker in place of `pi32v2/bin/ld`; `template.bin`, `ota.bin`, `text.bin`, `data.bin`, `ramtext.bin` and the
`.fwsc` packages equal the ones built with JieLi's `ld`. The 6 scripts (`app.ld`, `app_wifi.ld`, `loader.ld`, ...) were
also cross-linked with every project's objects, with and without `--gc-sections`: identical, or both linkers fail.
m-bootloader's boot and installer need LTO to fit their `ASSERT`s (non-LTO objects are larger); the comparison
relaxes the two constants in a copy of the script, and both linkers refuse the original with the same message.
Not testable: the LTO and closed-library builds (fm1-base `ble`/`wifi`).

`tests/test_ld.py` has unit tests (a built-in link, relocations, script features) and a live class that runs
`ldcompare` on nine scripts, on random relocation values of types 1 to 8, and on the objcopy output.
A random differential test (random objects and scripts with orphans, gc, merge sections, fills, regions, `AT>`) was used
while developing: of the last 150 seeds, 85 gave identical files; the others differ only in the exotic cases of
section 7.

## 2. Linker-script subset

Parsed: `ENTRY`, `MEMORY` (attributes `rwx!`), `SECTIONS` with output sections `name [addr] [(NOLOAD)] : [AT(e)] [ALIGN(e)]
[SUBALIGN(e)] { ... } [> region] [AT> region] [: phdr] [=fill]`, top-level and in-section assignments (`= += -= *= /= <<= >>= &= |= ^=`),
`PROVIDE`, `PROVIDE_HIDDEN`, `HIDDEN`, `ASSERT` (between output sections or at top level), `EXTERN`, `INPUT`, `GROUP`, `SEARCH_DIR`,
`OUTPUT_FORMAT`/`OUTPUT_ARCH` (ignored), `/DISCARD/`. In a section body: input statements `file(sections)` with `KEEP`,
`EXCLUDE_FILE` (inside the parentheses), `SORT`, `SORT_BY_NAME`, `SORT_BY_ALIGNMENT`, `COMMON`, glob patterns; `BYTE SHORT LONG QUAD SQUAD`; `FILL`; `.`
assignments. Expressions: C operators and `?:`, numbers with `K`/`M`, and `ABSOLUTE ADDR ALIGN ALIGNOF BLOCK DEFINED LENGTH LOADADDR LOG2CEIL
MAX MIN NEXT ORIGIN SEGMENT_START SIZEOF SIZEOF_HEADERS CONSTANT DATA_SEGMENT_*`. Names do not contain `-`; `A-B` is a
subtraction. (`~` inside a name is a name character in JieLi's lexer: `~0` is an undefined symbol there; here it is
the operator.) A prefix `EXCLUDE_FILE (x) *(sec)` is parsed and ignored, as JieLi's does.

Built-in default script (no `-T`): `ENTRY(_start)`, text at 0x50000 (`-Ttext=` moves it), the usual sections in the usual order
(`.text.unlikely .text.exit .text.startup .text.hot` before `.text`), then `. = ALIGN(0x500) + (. & 0x4ff)` before the
data sections, `_edata`, `__bss_start`, `_end` (plus `etext`, `edata`, `end`... only if referenced), `.comment` at address 0.

### Placement

- Input sections go to the first statement (script order) that matches; within one statement in file order, then section order.
- An output section's start is aligned to its largest input alignment unless the script gives an address. An address given
  in the script is used as it is (the first input then pads inside the section); this also holds for `ALIGN` alone.
- `> region` places at the region's current pointer, no region at the location counter; with a `MEMORY` command and no
  `>`, the first region the section's flags fit. "region `r' overflowed by N bytes" is an error. A section of size 0 does not move
  the location counter.
- Load address: `AT(e)`; `AT> r` takes region `r`'s pointer (not aligned) and advances it by the size; a later section in the same
  VMA region without `AT` follows in that load region (this is what puts `.bss` after `.data` in Felucca: `.bss` gets
  `.data`'s load end, without the VMA alignment padding); otherwise the offset VMA-LMA of the section before it in the
  region is kept (`vma + (lma_prev - vma_prev)`), else LMA = VMA.
- Fill: `=expr` and `FILL(expr)`: a plain hex number is the pattern (its digits, padded to whole bytes: `0x90` is one byte,
  `0x1234` two, `0xdeadbeef` four), any other expression a 32-bit big-endian value; the pattern restarts at the start of
  every gap and the statement in force at the gap is used.
- Inside an output section a number assigned to `.` is an offset from the section start; `. = ALIGN(x)` aligns the address.
- Orphans (input sections no statement names) get an output section of their own name, placed after the last section of
  their class: text after `.text`; read-only data after `.rodata` else `.text`; data after `.data` else `.rodata` else
  `.text`; bss after `.bss`, else after the last allocated section; later ones follow earlier orphans of the class; symbol
  assignments right after the anchor stay in front of the orphan, `. =` assignments do not. An orphan with the name of an
  output section already in the script joins it at the end (this is how the common symbols reach a script's `.bss`
  that does not list `COMMON`); `COMMON` becomes `.bss`. Orphans take the anchor's region. Non-allocated sections go last.

### Which output sections exist

Size 0 sections are not written, except that one with `. = ALIGN(number)` in its body is (flags `W` only, type
PROGBITS, if it has no input; this is how fm1-base's empty `.ble_trace` shows up). Flags are the OR of the live input sections'
flags; `.text` is never writable; a `.text`, `.data` or `.bss` whose body starts with an assignment starts from
AX / WA / WA; an output made only of `SHF_MERGE` sections of one entry size keeps `M`, `S` and `sh_entsize` (else not). A
section with no input that only moves the counter is `NOBITS` `WA`; `NOLOAD` makes it `NOBITS`. Type is `NOBITS` only if
every input is. `sh_addralign` is the largest input alignment.

## 3. Relocations

`S` symbol value, `A` addend, `P` address of the first word of the instruction, all in 32 bits. Every rule was fitted
and then checked with random values against JieLi's `ld` (`tests/test_ld.py`, 8 values per type) and with the boundaries.

| Type | Rule |
| --- | --- |
| 1 `LONG_JUMP_17M2` | `d = S+A-(P+4)`; error "relocation unaligned" if odd (then also "truncated"); `v = d/2` must be in -32768..32767; the whole second halfword is **replaced** by `v & 0xffff` |
| 2 `LONG_JUMP_23M2` | as 1 with 22 bits (-2097152..2097151); the low 6 bits of the first halfword become `v>>16 & 0x3f` (the upper 10 are kept), the second halfword `v & 0xffff` |
| 3 `EXTEND_JUMP_17M2` | `d = S+A-(P+6)`, 16 bits, replaces the third halfword |
| 4 `EXTEND_CALL_32M2` | `d = S+A-(P+6)`, must be even; no range check; bits 15..1 of the second halfword become `v & 0x7fff` (bit 0 kept), the third halfword `v>>15 & 0xffff` |
| 5, 9, 10 `MOV_ABS32`, `GOT`, `GOTFUNCDESC` | `v = (S+A) mod 2^32`; second halfword `v & 0xffff`, third `v>>16`; no check |
| 6, 7 `ABS8`, `ABS16` | `r = signed32(S+A)`, `i` = the in-place value read as signed; error unless both `r` and `r+i` are in -2^n..2^n-1 (n = 8 or 16); stores `(r+i) mod 2^n` |
| 8 `ABS32` | `(in-place + S + A) mod 2^32`, never an error |
| 11, 12, 13 `FUNCDESC`, `FUNCDESCVALUE`, `REL32` | like 8, but an error if `signed32(S+A) + signed32(in-place)` leaves the signed 32-bit range; (13 is not PC-relative) |
| 14, 15, 16 `MOV_ABS16`, `GOT16`, `GOTFUNCDESC16` | `signed32(S+A)` must fit signed 16 bits (-32768..32767), replaces the second halfword. ELF.md says -32768..65535; the test against `ld` gives 32767 as the largest |
| 0 | ignored; 17 and above abort the link |

Undefined weak symbols are 0. An undefined symbol is "undefined reference to `x'" (all are reported). A symbol from the
script is absolute or relative to a section like any other. Sections that are merged (below) give their symbols the new
offset: a relocation `sym+A` into a merged string section uses the symbol's new address, then adds `A`.

## 4. Garbage collection

Roots: the entry symbol (`-e` or `ENTRY`; **not** `_start` unless it is named: a custom script without `ENTRY` and without
`-e` keeps nothing), `-u`/`EXTERN` symbols, `KEEP` sections, non-allocated sections, `INIT_ARRAY`-type sections. Reachability
follows relocations. A common symbol is kept with its object's whole `COMMON` section: one referenced symbol keeps
all of that object's commons. With `--gc-sections`, a symbol the script defines inside an output section and refers to
from outside any output section (or only dead code refers to) is written as a local symbol (fm1-base's `_ble_dma_start`...
in `ASSERT`s).

## 5. Merged sections (`SHF_MERGE`)

`.rodata.str1.1`, `.rodata.cstN` and the like are merged inside the output section, across files: identical entries are
stored once, in the first section that has them, in order of appearance. For strings in a section whose alignment is
not above the entry size, a string that ends another is stored inside it: the strings are sorted by their reversed
spelling and each one that ends the next in that order is merged into it (this decides which string the empty string
shares with). A merged string section's size is rounded up to its alignment (constants are not padded). Local symbols
whose name starts `.L` in a merge section are dropped.

## 6. The output file

ELF32, little-endian, `ET_EXEC`, machine 0xf1, flags 0, no `PT_PHDR`.

- Section headers: the output sections in script order (empty ones omitted), then `.shstrtab`, `.symtab`, `.strtab`.
  File order: contents, `.symtab`, `.strtab`, `.shstrtab`, section headers.
- Program headers: all `PT_LOAD`, `p_align` 0x500. Allocated sections are ordered by load address; a new segment starts
  when VMA-LMA differs from the previous section's, or when `ALIGN(previous end) < page(start)`, or the first writable
  section of a segment (or a loaded one after a `NOBITS` one) lies on another page than the previous end, where
  `page(x) = x & ~0x4ff` (0x500 is not a power of two; JieLi's `ld` masks anyway, and 0x4ff-masked arithmetic is what the
  observed boundaries fit). `p_flags` is R plus W and X if any section is. If the first section's file offset is below 0x500
  and its address is not lower than that, the first segment starts at file offset 0 and holds the file and program headers.
- File offsets: the next offset is the smallest one at or after the end of the file contents, congruent to the address mod 0x500,
  where a distance is taken mod 2^32 first (`vma 0x10` gives 0x110, not 0x510). Later sections of a segment sit at their address
  distance from the first; a `NOBITS` one right after loaded ones at the end of the contents. Sections outside every segment
  follow all contents; an empty `NOBITS` one has offset 0. With no program headers `e_phoff` and `e_phentsize` are 0.
- Symbol table: null, one `STT_SECTION` per output section, then for each input file, in the order of its first section in the
  output, its `STT_FILE` symbol (the object's own, else one named by the path as given, when the file has local symbols)
  and its local symbols in the file's order (those in dropped sections are not written), then the script's local symbols (after
  an unnamed `STT_FILE` if there was a file symbol), then global symbols **in the order of the linker's hash table**:
  `h = 0; for each byte c: h = (h + c + (c<<17)) mod 2^32; h ^= h>>2; then h = h + len + (len<<17); h ^= h>>2`; bucket
  `h mod 4051`; buckets in increasing order, and inside one bucket the symbol created last first. A symbol is created when
  an object mentions it, or when the first script assignment that can be computed defines it (an expression that
  uses `ADDR`/`SIZEOF`/`LOADADDR` outside a section, or a symbol that is not yet defined, is computed one pass later). This
  reproduced 1769, 1708 and 685-symbol tables exactly.
- Script symbols: absolute or in a section. A value built from `.` outside any section belongs to the output section before
  it, or the one after it if `.` was assigned in between, skipping empty ones (`_edata = .` after `. = ALIGN(..)` goes to
  the next section). Inside a section, a plain number is an offset from the section's start. Combining values: plain
  numbers and sizes (`SIZEOF`) give numbers; an address and a size give an address; an address and a plain number, or two
  addresses, give a number; `.` and `ALIGN()` with a number or size stay relative to the section; two addresses (or an
  address and a size) work on offsets from their sections. `HIDDEN` symbols are written local.
- `.strtab` and `.shstrtab`: strings in order of first use; a string that ends another is stored inside it (found by the same
  reversed sort as in section 5). The assembler's objects use a differently ordered table (ELF.md section 3).
- Entry: `-e`, else `ENTRY`, else the symbol `start`, else the start of `.text`, else 0. A named entry that is not found is a warning
  "cannot find entry symbol X; defaulting to ..." and the start of `.text`.
- Overlap check: allocated sections whose address ranges overlap are an error (two that start at the same address are fine
  if one is `NOBITS`); the same for the load addresses of loaded ones.
- COMMON: an object that declares common symbols gets a section named `COMMON`, filled in hash order, owned by the object with
  the largest declaration of a symbol; a definition of the same name keeps the common's size and `STT_OBJECT`.

## 7. Differences from JieLi's `ld`

- `-Map` is a simpler file (memory configuration, `LOAD` lines, output and input sections with sizes), enough for the checks
  fm1-base's `tools/build.py` makes. Messages are close to JieLi's but not the same text; no "In function" lines.
- Archives are read without the index (`ranlib`); JieLi's `ld` refuses an archive that has none.
- Exotic situations where the files differ (found by the random test, not by any FM-1 link): an empty section that is
  kept or dropped (the rule for `. = ALIGN(number)` is a fit, not an explanation), where `.` goes after an empty
  kept section, a section both in a script with `AT()` and ties of equal load addresses, flags of an output section that
  contains garbage-collected input of mixed kinds, relocations in `NOLOAD` sections (JieLi applies them, this linker skips
  them), LMA overlaps after `AT` chains.
- Not implemented: see the list under Options; `INCLUDE`; hidden/internal visibility beyond `HIDDEN`; version scripts;
  `--sort-common`; `-r`; TLS; a symbol named `~x` in scripts.
