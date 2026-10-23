# Gaps

What is known to exist but is not documented yet, roughly in the order it matters for FM-1 firmware. When a
gap is closed, move the facts into the table or [ISA.md](ISA.md) and delete the line here.

## Needed for the FM-1's own assembly

The `.S` files in m-bootloader, Felucca and fm1-base use about 40 instruction forms [sources-in-use]. Not yet
in the table:

- moves between general and special registers: `sp = rN`, `ssp = rN`, `reti = rN`, `rete = rN`,
  `rN = sp`, `rN = psr`, `icfg = N`, and loading a symbol's address into `sp`, `ssp`, `usp` or `reti`;
- loading a constant or a symbol's address into a general register (`r3 = 0x1C07F00`);
- `[rN + N] = rN` (store with offset);
- register-range and special-register push and pop (`[--sp] = {r3-r0}`, `{psr, rets, reti} = [sp++]`,
  `[--sp] = {sp, ssp, usp, icfg, psr, rets, retx, rete, reti}`);
- `call` and `goto` to a label, with their reach and relocations;
- `trigger`.

## Needed for compiled code

- **The FPU (`fprev1`).** No public source describes it. Felucca and fm1-base compile with `-mfprev1`.
- **The 32- and 48-bit formats:** how the first word selects the length, and where immediates and offsets
  sit in the extra words.
- **Parallel issue** (`ins1 # ins2`): which pairs are allowed and how they are encoded.
- **`rep` loops and if/then/else blocks.**
- **Flags:** which instructions set and test `cc`.
- **The calling convention** beyond the first two arguments (ISA.md §8).
- **ELF:** relocation types, section flags, symbol conventions (ISA.md §9).

## Known to exist, not needed yet

- SIMD instructions.
- Instruction revisions and newer CPU models, and which instructions each needs.
- The other CPU models `r1`, `r2`, `r4`, `r5` and how they differ from `r3`.
