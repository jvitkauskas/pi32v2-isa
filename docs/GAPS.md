# Gaps

What is known to exist but is not documented yet, roughly in the order it matters for FM-1 firmware. When a
gap is closed, move the facts into the table or [ISA.md](ISA.md) and delete the line here.

## Done: the FM-1's own assembly

Every instruction in the assembly of m-bootloader, Felucca and felucca-bsp is in the table and confirmed:
`oracle compare` reads all 674 of them exactly as JieLi's objdump does ([ORACLE.md](ORACLE.md)).

## Needed for compiled code

- **The rest of the 16-bit map.** `oracle sweep` shows about 1000 distinct shapes; the table has the ones the
  FM-1 assembly uses. Next: arithmetic and logic (`R = R + R`, `R += N`, shifts, `R &= N`, `R ^= N`),
  halfword loads and stores (`h[...]`), post-increment addressing (`[R++=R]`, `[R++=N]`), extensions
  (`R = R.b0 (s)`), the other compare-and-branch forms.
- **The 32-bit forms**: compare-and-branch with two registers and decrement-and-branch (`if (r0 == r1) goto`,
  `if (--r0 != 0) goto`; first words `e800`..`ea7f`), the other `e06x` first words next to `li.modimm`, the pops matching `push.rmask` and
  `push.srmask`, multiplies, and everything else whose first word is in `E000`..`FFFF`.
- **The FPU (`fprev1`).** No public source describes it. Felucca and fm1-base compile with `-mfprev1`.
- **Parallel issue** (`#`): which pairs are allowed, and what the 32-bit `#` forms are.
- **`rep` loops and if/then/else blocks.**
- **Branch offsets:** what they are relative to (ISA.md §6).
- **Flags:** which instructions set and test `cc`.
- **The calling convention** beyond the first two arguments (ISA.md §9).
- **ELF:** the other relocation types, their numbers and fields, section flags, symbol conventions (ISA.md §10).

## Known to exist, not needed yet

- SIMD instructions.
- Instruction revisions and newer CPU models, and which instructions each needs.
- The other CPU models `r1`, `r2`, `r4`, `r5` and how they differ from `r3`.
- What `trigger`, `cnum` and the special registers `sr4`, `uspn`, `sspn`, `icfgn` and `icfgs` do.
