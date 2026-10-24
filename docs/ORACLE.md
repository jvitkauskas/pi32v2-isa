# The oracle

JieLi's Linux toolchain is freely downloadable and can assemble and disassemble pi32v2. It is used here as a
black box: give it input, record its output, and compare that with what this repo's table says.

## Toolchain versions

| Release | SHA-256 of the `.tar.xz` | Notes |
| --- | --- | --- |
| `20250324.1` | `f686586bcfb45e0f0bb27fd2b39c7a7f313cb4f0e88a66a14da621ffa8225958` | used by m-bootloader |
| `20260730.1` | `a1545cddbc451a06bac43eb5cd96d831470c42a97c5c0b1f98879a20fc7647bd` | current as of 2026-10; rebuilt `clang`, `LLVMgold.so`, `objdump`, `objcopy` and `llvm-read-version`, everything else identical |

```sh
python3 -m pi32v2isa oracle fetch               # download, check the SHA-256, unpack under oracle/
```

It comes from `https://jl-update.oss-cn-shenzhen.aliyuncs.com/jieli-linux-toolchains-<release>.tar.xz`
(`https://pkgman.jieliapp.com/s/linux-toolchain` redirects to the current one). `oracle/` is git-ignored; never
commit the toolchain. `--release` picks another release; `PI32V2_TOOLCHAIN` points at one unpacked elsewhere.

## Two directions

```sh
python3 -m pi32v2isa oracle decode 80 00 c5 00         # what JieLi's objdump makes of these bytes
python3 -m pi32v2isa oracle encode "rts" "call r5"     # what JieLi's assembler makes of these lines
```

- **Decode** assembles the bytes as `.byte` data with the toolchain's clang and runs
  `objdump -d -mcpu=r3` on the object.
- **Encode** assembles the lines with `clang -target pi32v2 -mcpu=r3 -c` and reads the bytes back.
- `--feature fprev1` adds `-mfprev1` to both (an entry's `requires` does this automatically).

Both are needed: the disassembler may print the same text for different encodings, and the assembler may
pick one encoding of several.

## Finding a form's layout

```sh
python3 -m pi32v2isa oracle sweep                  # objdump's reading of all 65536 16-bit words, by shape
python3 -m pi32v2isa oracle sweep e064             # the same for every second word after first word e064
python3 -m pi32v2isa oracle vary "r{x} = [sp+{n}]" x=0..15 n=0,4,8,16,128   # assemble variants, show bits
python3 -m pi32v2isa oracle fit 'r(\d+) = \[r(\d+)\+(-?\d+)\]'              # which bits carry each operand
python3 -m pi32v2isa oracle fit '(\w+) = r(\d+)' e064                          # same, over second words
```

`sweep` groups the decoded words by shape (registers become `R`, numbers `N`) and prints the bits common to
every word of a shape. It takes about a second and is the quickest way to see what a region of the encoding
space holds, including which first words begin 32- or 48-bit instructions (the length column). `vary`
assembles one line with different operands and prints each result's words in binary, which shows where each
operand's bits go. `fit` takes a regex whose groups are the operands, over a sweep: for each bit it shows
how flipping it changes each operand (a register field shows +1, +2, +4, +8; a signed offset's top bit a
negative weight), and whether the words form a complete pattern or have holes where other shapes sit
(`--split MASK` groups the words by some bits first). All three only feed the oracle input and read its
output.

```sh
python3 -m pi32v2isa oracle coverage 0000-1fff     # what objdump decodes there that the table does not, by shape
```

## Confirming entries

```sh
python3 -m pi32v2isa oracle confirm                 # check every entry not yet confirmed
python3 -m pi32v2isa oracle confirm mov.rr --write  # check one, and record it if it passes
```

For each entry, `confirm` encodes field values with the table and checks that JieLi's objdump prints the
table's text for those bytes and that JieLi's assembler turns that text back into the same bytes. It tries
every combination of field values when there are at most 4096, else each field's extremes, a middle value,
every single bit and three irregular values (so a wide constant does not also fit a shorter form). Each probe
is followed by two `nop`s, so a probe objdump reads as longer shows up as a mismatch instead of
desynchronising the rest.

These cases are not mismatches:

- **The assembler prefers another form.** `call 0` assembles to the 16-bit `call.s`, not `call.l`. When the
  bytes the assembler gives decode, with this table, to another entry that means the same, `confirm`
  accepts it and says which entries it preferred. "Means the same" is: numbers compared by 32-bit value
  (`0xFF` and `255`), `x op= y` equal to `x = x op y`, and the operands of `+ * | ^ &` in either order. The
  assembler may always prefer another entry: decoding still checks every probed encoding against objdump,
  and assembly must give an equivalent, fully decoded instruction for every accepted text.
- **Another encoding of the same entry.** A modified immediate has several raw values for some numbers
  (0 is raw `000`, `100`, `200` and `300`); the assembler picks one, which is no mismatch.
- **The assembler refuses a text objdump prints.** objdump prints an empty register list as `{}`, which the
  assembler rejects. An entry lists such texts in `asm_rejects`, and `confirm` checks they really are refused.
  A field whose values the assembler only partly accepts says so with `asm_range`.
- **No known assembler syntax for an entry.** `asm_no_syntax = true` requires every probed printed text
  to produce an assembler error or no instruction. `confirm` still checks every decode probe and records
  examples with origin `oracle:objdump+clang-reject:<release>`; the example regression checks rejection too.
  This records tool behavior (for example `??` conditions), not hardware validity or an exhaustive proof
  that no alternative spelling exists.
- **The assembler gets it wrong.** JieLi's assembler turns `r0 = r0 | 0x0` into `r0 |= 1`. An entry lists
  such texts in `asm_wrong`; `confirm` checks they are still mis-assembled, so a fixed toolchain shows up.

With `--write`, a passing entry becomes `confirmed`, gains the `oracle` source, and gets a few examples: all
fields at their minimum, each field alone at its maximum (so swapped fields would show), all at maximum.

```toml
[[insn.example]]
bytes = "0f 16"
text = "r15 = r0"
origin = "oracle:objdump+clang:20260730.1"
```

Block openers (`if (...) {`, `rep`) are assembled with a body and a closing `}`: a single `nop`; for an
entry with `body`, as many `nop`s as that field says; for an entry with `block`, a then-part and an
`} else {` part of as many `nop`s as its fields say. Their decode probes are padded past the longest body so
the next probe never falls inside it. objdump prints an `if` opener the same whatever its shape, so for
those fields only the assembler direction checks the bits.

## Regression tests

`python3 -m unittest discover -s tests` re-checks every confirmed entry's recorded examples against the
toolchain both ways (under a minute, when the toolchain is present). `PI32V2_LIVE_ALL=1` also re-runs the
full `confirm` of every entry, which takes about an hour.

## Asking the compiler

```sh
python3 -m pi32v2isa oracle cc probe.c --flag=-O2     # objdump -d -r of what JieLi's clang makes of it
```

Which instruction the compiler picks for a C operation is evidence of what the instruction does (it uses
`>>>` for a signed `>>`, so `>>>` shifts arithmetically) and of the calling convention. Source id
`compiler`.

## Checking real code

```sh
python3 -m pi32v2isa oracle compare build/*.o
```

`compare` disassembles each object's code sections with the table and with JieLi's objdump and reports every
instruction where they differ. It needs a stock `readelf` and `objcopy` (GNU binutils). On 2026-10-23 the
assembly of m-bootloader, Felucca and felucca-bsp (11 objects, assembled with JieLi's clang) gave 674
identical instructions and 2 data words objdump does not decode either. On 2026-10-24 the 50 C files in
`tests/corpus/`, compiled by JieLi's clang at -O0, -O2 and -Os (150 objects), gave 17586 identical
instructions and 80 jump-table entries (which objdump prints as `< n : 0xN >`, data); the unit tests repeat
this when the toolchain is present.

## Checking the assembler

```sh
python3 -m pi32v2isa oracle asmcompare FILE.S -I include [-D NAME]   # also .s and .c files
python3 -m pi32v2isa oracle linkcompare FILE.S -I include
```

`asmcompare` assembles the file with JieLi's `clang` and with this repo's assembler (`.S` goes through the system
`cpp` first, so both read the same text; `.c` is compiled to assembly by JieLi's clang) and compares the two
objects: header, then each section's type, flags, alignment, entry size, size, contents and relocations, then the
symbols. It prints nothing but "identical" when they agree. `linkcompare` links both objects with JieLi's `ld`
(undefined symbols get `--defsym` values) and compares the loaded sections. The assembler and its checks are
described in [ASSEMBLER.md](ASSEMBLER.md); the object format they establish is in [ELF.md](ELF.md).

## Checking the objdump

```sh
python3 -m pi32v2isa oracle objdumpcompare FILE... [-d -D -h -t -r -s -j SECTION -mcpu=r3]
```

`objdumpcompare` runs JieLi's objdump and this repo's ([OBJDUMP.md](OBJDUMP.md)) on each file with the same options
and compares the output line by line. Without options it runs the standard sets (`-d`, `-d -mcpu=r3`, `-d -r`, `-D`,
`-h`, `-t`, `-r`, `-s`). It prints one line per file and set: `identical`, or the number of differing places and the
first few (`--show N` for more).

## Checking the linker

```sh
python3 -m pi32v2isa oracle ldcompare -- --gc-sections -e _start -T app.ld crt0.o main.o
```

Everything after `--` is `ld`'s command line (without `-o`). `ldcompare` links with JieLi's `ld` and with
`pi32v2isa ld` and prints the differences by category: `contents` (loaded sections' addresses, types and bytes, and
`objcopy -O binary -j` of each, run with JieLi's objcopy because stock GNU objcopy refuses these files), `symbols`,
`entry`, `phdrs`, `layout` (section headers, symbol order, string table). `--cwd DIR` links in a directory. It exits 1 on
any difference. [LINKER.md](LINKER.md) lists what was checked.

## Rules

- Black box only: inputs and outputs. Do not extract tables or strings from the toolchain's binaries.
- The oracle can be wrong or inconsistent (the SSTIC paper reports such cases). When it is, record what it
  did and say so in the entry's `notes`.
- The disassembler and the assembler don't always spell things alike: objdump prints `[r1+0] = r2` where the
  FM-1 sources write `[r1 + 0] = r2`. The table's `syntax` follows objdump; an assembler must also accept the
  spaced form.
