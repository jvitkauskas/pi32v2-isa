# What JieLi's compiler emits

This document records which table entries JieLi's `clang` chooses for which C constructs, and what that says
about what the instructions do. It is the input a future compiler backend needs, and the evidence behind most
entries' `summary` text. Source id: `compiler` ([SOURCES.md](SOURCES.md)); one entry also cites `ac79-sdk`.

Method: C in, objdump out, nothing else. `python3 -m pi32v2isa oracle cc FILE.c --flag=-O2`
([ORACLE.md](ORACLE.md)); the listing is matched with the table. The compiler reports itself as clang 4.0.1
(`-target pi32v2 -mcpu=r3`, toolchain 20260730.1), an old base: no `__builtin_clrsb`, no
`__builtin_bitreverse32`, no `__builtin_rotateleft32`, and C vector types are scalarised. Everything below was
seen at -O2 unless another level is named; -Os gives the same instructions with less unrolling, and -O0 adds
stack spills, the 32-bit `.l` branches and many `#` pairs. `--feature fprev1` and `--feature instrev3` changed
nothing in the code chosen (apart from the operand order of commutative float ops with `-ffast-math`).

Compiler-side facts an assembler or backend may find useful, from the compiler's own `-mllvm -help-hidden`
listing: it has switches `-pi32v2-enable-rep-memop` (inline `memcpy`/`memset` with `rep`),
`-pi32v2-div-expand` (division by a constant as a multiply), `-pi32v2-enable-simd`, `-pi32v2-always-use-itblock`,
`-pi32v2-parallel-pack`, `-pi32v2-sched-type`, `-pi32v2-tbb-max-disp`/`-pi32v2-tbh-max-disp`,
`-pi32v2-large-program`, `-pi32v2-fixed-r15`, `-pi32v2-indexed-ldst`. Of these only `rep-memop`, `div-expand` and
`tbb-max-disp=0` changed the code of the tests below; `enable-simd` and `always-use-itblock` did not.

## 1. Constructs and the entries they become

`r` is a register; `P` a register pair `r(2n+1)_r(2n)`; "(s)" signed, "(u)" unsigned operand type.

### Shifts and rotates

| C | Entry (id) | Evidence |
| --- | --- | --- |
| `a << b`, int or unsigned | `lsl.rr` (`r0 <<= r1`), `lsl.rrr` when rd differs | `r0 <<= r1`; `r2 = r0 << r1` |
| `a >> b`, unsigned | `lsr.rr`, `lsr.rrr` | `r0 >>= r1` |
| `a >> b`, signed | `asr.rr`, `asr.rrr` (arithmetic) | `r0 >>>= r1`; `r0 = r2 >>> r1` |
| `a << 5`, `a >> 5` (u), `a >> 5` (s) | `lsl.rri`, `lsr.rri`, `asr.rri` (counts 1..32, r0..r7); `.l` forms for r8+ | `r0 = r0 >>> 5`; `r6 = r11 >>> 2` |
| `(a >> 5) \| (a << 27)`, `(a >> 16) \| (a << 16)` | `ror.rri`: rotate right by n | `r0 = r0 <> 5` |
| `(a << b) \| (a >> (32 - b))` | `rsub.modimm.rri` (`r1 = 0x20 - r1`) then `ror.rrr` | `r0 = r0 <> r1`: `<>` rotates right; `(a >> n) \| (a << (32 - n))` is `ror.rrr` directly |
| `long long << n`, `>> n` (u/s) | `lsl.pair.i/.r`, `lsr.pair.i/.r`, `asr.pair.i/.r` (counts 1..64) | `r1_r0 >>>= 40`, `r1_r0 <<= r2` |
| `(a << 5) \| (a >> 59)`, `(a >> n) \| (a << (64 - n))` on 64-bit | `ror.pi` (`r1_r0 <>= 59`), `ror.pr` (`r1_r0 <>= r2`): rotate right | |
| `(unsigned)(ll >> 5)` | `lsr.pair.i` then use r0 | low word of the pair is the even register |
| `a >> 31` (s) sign mask, `(long long)a` | `asr.rri` by 31 | `r1 = r0 >>> 31` |

`>>>` is the arithmetic (sign-filling) right shift; `>>` is logical. The compiler never uses `<<<`
(`shl3.*`) or `<c>` (`cycc.*`), and no variable shift count above 31 is
ever relied on: it masks (`b & 31` becomes `r1 = r1 & 0x1F` then the shift) or clamps (`ifs (r1 >= 31) { r1 = 31 }`)
itself, and keeps its own `b < 32` test around `b >= 32 ? 0 : a << b`. The hardware result for counts of 32 and
above is therefore not established.

### Loads, stores, extensions

| C | Entry | Evidence |
| --- | --- | --- |
| `*(unsigned char *)p`, `p[5]` | `ld.bu` (`b[r0+5] (u)`) | |
| `*(signed char *)p`, `char` | `ld.bs.l` (always the 32-bit form) | `r0 = b[r0+0] (s)` |
| `*(unsigned short *)p`, `p[5]` | `ld.hu` (`h[r0+10] (u)`, offset in bytes) | |
| `*(short *)p` | `ld.hs.l` | `r0 = h[r0+0] (s)` |
| `*p`, `p[5]` (int) | `ld.w` (`[r0+20]`) | |
| `long long` | `ld.d.l` (`r1_r0 = d[r0+0]`, low word at the lower address); `st.d.l` | |
| `p[i]`, 8/16/32-bit | `ld.bu.idx`/`ld.bs.idx` (`b[r0+r1]`), `ld.hu.idxs`/`ld.hs.idxs` (`h[r0+r1<<1]`), `ld.w.idxs` (`[r0+r1<<2]`) | index is scaled by the access size for h and w, not for b |
| `p[500]`, `p[5000]` | `li.s16 r1 = 500` then `ld.w.idxs` | offsets beyond the immediate form go through an index register |
| `s += *p++` (b/h/w/d) | `ld.bu.pin`, `ld.hs.pin.l`, `ld.w.pin`, `ld.d.pin.l`: load, then add the size to the pointer | `r3 = [r2++=4]`; going down: `d[r0++=-8]` |
| `*d++ = v` | `st.b.pin`, `st.w.pin`: store, then add | `[r0++=4] = r3` |
| `p += stride` in a loop | `ld.w.pi.l` (`r6 = [r5++=r1]`, stride pre-scaled by 4) | |
| `p[0], p[1]` (two words) | `ldm.post1` (`{r2, r1} = [r0+]`: r1 from [r0], r2 from [r0+4], r0 unchanged) | `stm.post1` for stores |
| `(signed char)a`, `(unsigned char)a` | `ext.b0.s`, `ext.b0.u` | `r0 = r0.b0 (u)` |
| `(short)a`, `(unsigned short)a` | `ext.l.s`, `ext.l.u` | `r0 = r0.l (s)` |
| `(a >> 8) & 0xf`, `(a >> 5) & 1` | `uextra.rrii` (`uextra(r0, p:8, l:4)`) | |
| `(a << 20) >> 28`, `(a << 26) >> 26` | `sextra.rrii` (`sextra(r0, p:8, l:4)`) | |
| `(a & ~0xff00) \| ((b & 0xff) << 8)`, `(a & 0xffff) \| (b << 16)` | `insert.rrii` (`r0 <= insert(r1, p:8, l:8)`), preceded by `ext.l.u` | |
| -O0 locals | `ld.w.sp`/`st.w.sp`, `ld.*.sp.l`/`st.*.sp.l`; `ld.d.sp.l`/`st.d.sp.l`; `rmw.add.s12`/`rmw.add.r` for `x += c` through an address | |
| register pressure (r8..r15) | the `.l` forms: `ld.w.l`, `st.w.l`, `ld.bu.l`, `ld.w.sp.l`, `st.w.sp.l`, `ld.w.pin.l`, `lsr.rri.l`, `add.rrr.l`, ... | |

No `npc`-relative load (`ld.w.npc`) appeared in any test, with or without `-fPIC`: constants are `li.*`
immediates, tables are reached through an address loaded with `li.u32` (relocation `MOV_ABS32`) or, with
`-fPIC`, through `r15` (below). Nothing was seen of the byte/halfword `ld.*.pi` forms either.

### Constants

`li.u8` 0..255; `li.neg5` -32..-1; `li.s16` -32768..32767 outside those; `li.modimm` for 12-bit modified
immediates (0xFF00FF, 0x8000, 0x10000, 0x3F800000, 0x80000000); `li.u32` otherwise and for every symbol address
(relocation `R_PI32V2_MOV_ABS32`); `li.zero_pair` for a 64-bit zero; `li.zero_hi` for 0 into r8..r15. Immediate
ALU forms: `add.rri` (0..31), `add.ri.neg7` (-128..-1, destination = source), `add.s14.rri`, `add.modimm.rri`,
`sub.modimm.rri`, `rsub.modimm.rri` (`-a`, `c - a`), `and.modimm.rri`, `and.nmodimm.rri` (`a & 0xFFFF00FF`),
`xor.modimm.rri`, `mul.modimm.rri`; single-bit masks are `or.bit`, `xor.bit`, `and.invbit`
(`a & 0x7FFFFFFF` is `and.invbit`, so is float `fabsf`; float negate is `xor.bit` 31). `a * 8` is a shift,
`a * 10` is `mul.modimm.rri`, a non-modified-immediate multiplier is loaded into a register first.

### Arithmetic, logic, bit counting

| C | Entry | Evidence |
| --- | --- | --- |
| `a + b`, `a - b`, `a * b` | `add.rr`/`add.rrr`, `sub.rrr`, `mul.rr`/`mul.rrr` | `sub.rrr r0 = r1 - r0` (first operand minus second) |
| `a & b`, `a \| b`, `a ^ b`, `~a`, `a & ~b` | `and.rr`/`or.rr`/`xor.rr` (+ `.rrr`), `not.rr`, `bic.rrr` | |
| `a & (1 << n)`, `a \| (1 << n)`, `a ^ (1 << n)`, `a & ~(1 << n)` | `and.bit.rrr`, `or.bit.rrr`, `xor.bit.rrr`, `and.invbit.rrr` | |
| `a < 0 ? -a : a` | `abs.rr` | |
| `a > b ? a : b`, `a < b ? a : b` | `smax.rrr`/`smin.rrr` (int), `umax.rrr`/`umin.rrr` (unsigned) | a clamp is `smin`/`smax` inside an `ifs` block |
| `a / b` | `div.s.rrr`, `div.u.rrr` (quotient only) | |
| `a % b` | `div.*`, then `mul.rr`, `sub.rrr` | there is no remainder instruction in use |
| `a / 10` with `-mllvm -pi32v2-div-expand` | `li.u32 magic`, `mul.s.prr`/`mul.u.prr`, shift of the high register | `r1_r0 = r0 * r1`, then `r1 >> 3` |
| `(long long)a * b` | `mul.s.prr` (`r1_r0 = r1 * r0 (s)`); `mul.u.prr` for unsigned | high word in the odd register |
| `acc + (long long)a * b`, `acc - ...` | `madd.s.prr`/`madd.u.prr`, `msub.s.prr`/`msub.u.prr` | `r1_r0 += r3 * r2 (s)` |
| `u64 * u64` | `mul.u.prr` + two `mul.rrr`/`mul.rr` cross products + `add` | |
| 64-bit `/`, `%`, doubles, `sqrtf`, `fmaf`, `rintf`, `lrintf`, `memcpy` (not inlined) | calls: `__divdi3`, `__udivdi3`, `__moddi3`, `__umoddi3`, `__adddf3`, `__muldf3`, `__divdf3`, `__floatsidf`, `__fixdfsi`, `__extendsfdf2`, `__truncdfsf2`, `__ltdf2`, `__floatdisf`, `__fixsfdi`, `sqrtf`, `sqrt`, `fmaf`, `rintf`, `lrintf` | doubles are soft-float |
| `__builtin_clz`, `__builtin_pi32v2_clz` | `clz.rr` | `clz(0)` is 32 |
| `__builtin_clzll` | two `clz.rr` and an `if (r1 != 32)` block | |
| `__builtin_ctz`, `__builtin_ffs` | `(x - 1) & ~x` (`add.s14.rri`, `bic.rrr`), `clz.rr`, `rsub` | no ctz instruction |
| `__builtin_bswap32`, `__builtin_pi32v2_rev8` | `rev8.rr`; `bswap16` = `rev8` then `>> 16`; `bswap64` = two `rev8` and a swap | |
| `__builtin_pi32v2_cls`, `_popcount`, `_zcmp` | `cls.rr`, `popcnt.rr`, `sgn.rr` | the only way to get them |
| `__builtin_popcount`, `parity` | software (shift/mask/`mul` by 0x1010101) | even with `--feature instrev3` |
| saturating `a > 32767 ? 32767 : ...` | compares and `smax`/`smin`, never `usat`/`ssat` or the saturating adds | |

### 64-bit arithmetic and the flags

| C | Entries | Evidence |
| --- | --- | --- |
| `s64 + s64` | `add.rrr` (low), `addc.rrr` (high: `r5 = r3 + r1 + c`) | |
| `s64 - s64`, `-a` | `sub.rrr`/`rsub.modimm.rri` (low), `subc.rrr` (high: `r5 = r1 - r3 - !c`) | |
| `a < b`, `a >= b` (64-bit) | `sub.rrr`, `subc.rrr`, `mov.r_sr rN = psr`, then bit tests with `if (...&...) {` blocks and `sextra`/`uextra` | see below |
| `a == b` (64-bit) | `xor`, `xor`, `or`, `beqz`/`bnez` | no flags |
| 32-bit carry-out `(a + b) < a` | an unsigned compare (`if (r2 >= r1) { r0 = 0 }`), not the flags | the flags are only used for 64-bit |

What the flags are, from the compiler's own 64-bit compares (all via `psr`, special register 5):

- `add`/`sub`/`addc`/`subc` leave the carry in bit 1 of `psr`. After a subtract chain `a - b`, bit 1 is set when
  there was no borrow, so unsigned `a < b` is "bit 1 clear" (`if ((r1 & 0x2) == 0)`) and `a >= b` is bit 1 set.
  `addc` adds that bit; `subc` subtracts its complement (`!c`), which is why the chain `sub` then `subc` works.
- Bits 0 and 3 of `psr` are the other two arithmetic flags: signed `a < b` is `psr[3] ^ psr[0]` (`uextra(p:3)`
  xor bit 0), signed `a >= b` its complement. These are the sign and overflow flags in some order; which is which
  is not established. A signed `<=` also needs "result is zero", which the compiler gets from `lo | hi`, not from
  a flag, so bit 2 (the likely zero flag) is not confirmed either.
- The instructions that set them, by adjacency to `addc`/`subc`/`mov.r_sr psr` in compiler output, are
  `add.rrr`, `add.rr`, `add.rri`, `add.s14.rri`, `sub.rrr`, `rsub.modimm.rri`, `addc.rrr`, `subc.rrr`. Whether
  logic, shift or load instructions also write them is not known.
- The flag branches `ifeq`..`ifle` (`bc.*`), `cc = 0/1` (`cc.set`) and `fcmp` are never emitted. The AC79 SDK's
  spin lock is inline asm `testset b[%0]` then `ifeq goto 1b` (retry while eq) [ac79-sdk].

### Comparisons and branches

The three families of condition words are: `if` = unsigned compare (for `==`/`!=` no difference), `ifs` =
signed compare, `iff` = floating-point compare. `if (r0 < r1)` is unsigned; `ifs (r0 < r1)` signed. Compare
with a constant: `if.eq/ne` take a signed 12-bit constant (sign-extended to 32 bits, so `a == 0xffffffff` is
`if (r1 == -1)`); `if.lt/le/gt/ge` take an unsigned 12-bit constant (0..4095); `ifs.*` a signed 12-bit constant;
larger modified-immediate constants (16384, 65536, 131072) use the `*.modimm` forms.

| C | Entry | Evidence |
| --- | --- | --- |
| `if (a < b)` (int) around a few instructions | `ifs.ge.rr` etc. as a block (the *inverse* condition guards the code that is skipped, or the true condition guards the code kept) | `ifs (r5 >= r4) goto` / `ifs (r0 >= r1) { r2 = r3 }` |
| same, unsigned | `if.lt.rr`, `if.ge.rr`, ... | |
| `a == b`, `a != b` | `if.eq.rr`, `if.ne.rr`; against constants `if.eq.ri.s12`, `if.ne.ri.s12` | |
| `a < 10` (unsigned), `a > 10`, `a < 4095` | `if.gt.ri.s12` with 9, `if.lt.ri.s12` with 11, `if.le.ri.s12` with 4094 | the block guards the code to run (or skip) with the inverse test and the constant moved by one |
| `a & 4`, `a & b`, `!(a & b)` | `if.ne.and.rm`, `if.eq.and.rr`, ... (against zero) | |
| float `a < b` etc. | `iff.lt.rr`, `iff.le.rr`, `iff.gt.rr`, `iff.ge.rr`, `iff.eq.rr`; negations `iff.uge.rr`, `iff.ugt.rr`, `iff.ule.rr`, `iff.ult.rr`, `iff.une.rr` | `u` means "also true if unordered": `!(a < b)` is `iff (r0 u>= r1)` |
| `isnan`, `isunordered` | `bfgt.rr` then `bfugt.rr` (two branches) | `iff (r1 > r1)` never holds; `iff (r1 u> r1)` holds only for NaN |
| loop and `if` tests that jump | `bne.rr`, `bges.rr`/`blts.rr`, `bge.rr`, `bles.rr`, `bgts.ri`/`blts.ri`/`bgt.ri`/`bne.ri`, `bne.and.rr`, `beqz`, `bnez` | `ifs (r1 < 1) goto exit`, `if (r4 != r6) goto top` |
| `-O0` the same, any distance | `bges.rr.l`, `bne.rr.l`, `blts.ri.l`, ... (32/48-bit forms, ±64 KiB) | |
| `for (i = 0; i < n; i++)` counted loop, body not using the end | `dbnz.r`: `if (--r1 != 0) goto top`, guarded by `ifs (r1 < 1) goto exit` | |
| `while (a > 5) ...` | `blts.ri` entry test, `bgts.ri` back edge | |

Branch offsets are relative to the end of the branch instruction: a `beqz` at 0x148 (2 bytes) printing
`goto 2` targets 0x14c; `dbnz.r` at 0xc (4 bytes) with `-8` targets 0x8. Offsets are in bytes, even.

### `if (...) {` blocks (predicated execution)

The compiler uses blocks for short conditional code instead of branching, at every level (at -O0 mostly for
comparison results and `?:`): everything between `{` and `}` executes only if the condition holds, and an
optional `} else {` part executes if it does not. Blocks hold ordinary instructions of any length, including `call.l`, `goto.l`, `rts` and loads/stores:

```
b1:  mov.rr  r2 = r0
     li.u8   r0 = 7
     if.eq.rr  if (r2 == r1) {      ; return f(a) if a == b, else 7
        mov.rr  r0 = r2
        call.l  call f
     }
     pop.pc  pc = [sp++]
a4:  if.ne.ri.s12  if (r0 != 0) {   ; if (a == 0) return 5; return f(a)
        goto.l  goto f
     } else {
        li.u8   r0 = 5
     }
     rts
```

Instructions inside a block run in order (a later one sees an earlier one's result). The block's shape is in
the *second word's top four bits* of the `if` instruction, which the table currently lists as don't-care:
bits 15..14 are the number of instructions in the then part minus 1 (1..4), bits 13..12 the number in the else
part (0 = none, up to 3). Found by assembling `if (r0 == r1) {` + 1..4 nops + `}`: the high byte of the second
word is `01`, `41`, `81`, `c1`; with an else part it is `11`, `51`, `31`, `b1`, `e1` for then/else counts
1/1, 2/1, 1/3, 3/3, 4/2 (the low nibble is the second register). The assembler refuses 5 instructions in the then
part ("if-clause out of range") and 4 in an else part. An instruction counts once however many words it has (a 48-bit `li.u32` is one). The
`}` takes no bytes.

### Parallel issue (`#`)

The compiler does emit the parallel forms, at -O2 and at -O0: `A #` immediately followed by `B` is issued as one
packet. In every pair seen A is an ALU/FPU/move/extension instruction (16 or 32 bits; `add.rr.p`, `mov.rr.p`,
`mul.rr.p`, `and.modimm.rri.p`, `div.s.rrr.p`, `clz.rr.p`, `uextra.rrii.p`, `li.s16.p`, `itof.rr.p`, ...,
twins of the plain entries) and B is a 16-bit load or store (`ld.w.sp`, `st.w.sp`, `ld.w`, `st.w`, `ld.w.pin`).
B reads the registers as they were before A writes: `and.modimm.rri.p r0 = r0 & 0x7 #` followed by
`st.w.sp [sp+4] = r0` stores the old r0 (the argument), and `add.rr.p r1 += r4 #` followed by `ld.w r4 = [r0+56]`
adds the old r4. Example, from an unrolled sum:

```
add.rr.p   r1 += r3  #
ld.w       r4 = [r0+12]
```

In assembly the pair is two lines, the first ending in `#` (`r1 += r3 #`). The first instruction is always one of
the `.p` twin entries. No `if` block has a `#` form.

What the assembler accepts as a pair (tried directly, not only what the compiler writes): the first line (A)
may be any 16- or 32-bit ALU, move, shift, multiply, divide, float, bit-field, `clz`, `abs`, `smax`, pair
shift or pair multiply instruction that has a `.p` twin, including r8..r15 forms and `r0 = 5`; it refuses a
`#` after `nop`, `goto`, `call`, a load or a store, a 48-bit constant (`r0 = 0x12345678 #`, "invalid
parallel-A instruction"), and a one-line `A # B`. The second line (B) must be one of the 16-bit loads and
stores on r0..r7: `[r+off]` words/halfwords/bytes with the short offsets, `[sp+off]` with the short offset
(`r2 = [sp+400]` is refused), the unsigned byte/halfword loads, and `[r++=±n]` post-increments; it refuses
`nop`, ALU instructions, the 32-bit `.l` loads and stores, `d[...]` pair accesses, `[r+r<<2]` indexed forms,
signed byte/halfword loads, `ldm`/`stm`, `push`, branches, and any base register r8 or above
("invalid parallel-B instruction").

### Hardware loops

`rep` is not used for ordinary loops at any level (counted loops are `dbnz.r`). With
`-mllvm -pi32v2-enable-rep-memop` a `memcpy`/`memset` of a constant size up to 32 elements becomes
`rep.i`: `rep 4 7 { ld.bu.pin r2 = b[r1++=1]; st.b.pin b[r0++=1] = r2 }` (second number = iterations, first =
body length in bytes), `rep 4 6 {` with `ld.w.pin`/`st.w.pin` for 24 aligned bytes, `rep 2 3 {` with only a store
for `memset`. Larger sizes call the library. The register-count `rep` was never emitted.

### Switch statements

| C | Result |
| --- | --- |
| dense `switch` with 6..10 cases calling functions | `bgt.ri` unsigned range check, `tbb [rN]`, a byte table, case bodies. The register holds the case number. Target = address after the `tbb` + 2 * table byte. objdump labels it `.GJTIS`/`.GJTIE`. |
| 8 cases returning constants | no jump table: a clamp (`if.gt.ri.s12`) and `ld.w.idxs` from a table of constants |
| `tbb` table too far for a byte | `-mllvm -pi32v2-tbb-max-disp=0` gives `r0 = r4 << 1`, `tbh [r0]`, a halfword table (target = address after `tbh` + 2 * entry) |

### Floating point (single precision)

| C | Entry | Notes |
| --- | --- | --- |
| `a + b`, `a - b`, `a * b`, `a / b` | `add.f.rrr`, `sub.f.rrr`, `mul.f.rrr`, `div.f.rrr` | `a / 2.0f` becomes `a * 0.5f` (`li.modimm 0x3F000000`) |
| `a * b + c` | `mul.f.rrr` then `add.f.rrr` | `madd.f.rrr`/`msub.f.rrr` never emitted, also not with `-ffast-math -ffp-contract=fast` |
| `-a`, `fabsf(a)`, `copysignf` | `xor.bit` 31, `and.invbit` (clear bit 31), bit ops and an `if` block | no FP instruction |
| `(int)f`, `(unsigned)f` | `ftoi.trunc.rr`, `ftou.trunc.rr` | C casts truncate; `even`, `ceil`, `floor` variants never used by casts |
| `(float)i`, `(float)u` | `itof.rr`, `utof.rr` | |
| `floorf`, `ceilf`, `truncf` | `ftof.floor.rr`, `ftof.ceil.rr`, `ftof.trunc.rr` | `roundf` = add 0.5 with the sign of the input (insert of bit 31) then truncate |
| `rintf`, `nearbyintf`, `lrintf`, `lroundf`, `sqrtf`, `fmaf` | library calls | `ftof.even.rr` is not used |
| `fminf`, `fmaxf` | `fmin.rrr`, `fmax.rrr` | with `-ffast-math`, `a < b ? a : b` too |
| `a < b`, `a <= b`, `a == b`, `a != b`, ... | `iff` blocks / branches on the registers directly | no `fcmp`; `u` forms for the negated tests |
| `float == double` etc., `double` anything | soft-float library calls | |
| `(float)(long long)` | `__floatdisf`, `__fixsfdi` | |

The `(f)` instructions assemble with or without `-mfprev1`; the compiler did not add anything on seeing it.

#### Floating point on the FM-1

Hardware runs in [hw/fm1-2026-10-24](../hw/fm1-2026-10-24) show nearest-even binary32 arithmetic,
gradual underflow and no flushing of subnormal inputs. `madd.f`/`msub.f` round the product before the
add/subtract. Arithmetic NaNs and invalid operations return positive `0x7f800001`, discarding sign/class/
payload. Integer-valued `ftof` keeps NaN sign but makes it quiet with zero payload; half/full conversion
keeps sign and quiet/signalling class, using canonical fractions `0x200`/`1` (half), `0x400000`/`1` (full).
`ftoi`/`ftou` saturate; NaNs choose the endpoint by sign. Min/max prefer a number to NaN; two NaNs copy the
second source unchanged. Opposite signed zeros give -0 for min, +0 for max. `fcmp` and min/max replace low
psr with less 8, equal 6, greater 2, unordered 3; other tested float forms preserve it. None of these cases
trapped; FPU control modes and exception-status registers were not varied or measured.

### Calls, stack and ABI (observed in passing)

- Argument words go in `r0`..`r3`, then on the stack with the fifth word at `[sp]` (read as `[sp+k]` after the
  callee's pushes). A 64-bit argument is two consecutive words, low first, with no pair alignment
  (`f(int a, long long b, int c)`: a = r0, b = r2:r1 (low in r1), c = r3); a 64-bit value that does not fit in
  the remaining registers goes to the stack whole. 64-bit results come back in `r1_r0`, others in `r0`.
- `long long` is held in a pair with the low word in the even register. The stack is only kept 4-byte aligned
  (frames of `sp += -12` and pushes of 12 or 20 bytes occur).
- Prologue `[--sp] = {rets, r5, r4}` (`push.rets_rl`), epilogue `{pc, r5, r4} = [sp++]` (`pop.pc_rl`); a function that
  makes no call just ends with `rts`; leaf-with-call uses `push.rets`/`pop.pc`. `r4`..`r15` are saved by the callee when
  used (`{rets, r15-r4}` once), `r0`..`r3` are scratch (r15 is special with `-fPIC`). Variadic functions spill the unnamed register words
  with `push.rl [--sp] = {r3-r1}`.
- Structs (8 and 12 bytes tried) are passed and returned through a pointer in `r0` (a returned struct's pointer
  comes first and shifts the other arguments to `r1`..).
- A call to another function is `call.l` (relocation `R_PI32V2_LONG_JUMP_23M2`); a tail call is `goto.l`
  (same relocation); through a pointer: `call.r`, tail `goto.r`.
- `-fPIC`: `r15` holds the global-offset base. A global's address is `r0 = r15; r1 = <GOT16>; r0 = [r1+r0]`
  (`ld.w.idx`, relocation `R_PI32V2_GOT16`); a function pointer is a two-word descriptor `{code, r15 value}`
  (`ld.d.l r1_r0`, then `r15 = r1; goto r0`), data holding one has relocation `R_PI32V2_FUNCDESC`; calls to other
  functions save and restore r15 around the call.

ELF relocation numbers seen (from `readelf -r` on the compiler's objects): `LONG_JUMP_23M2` = 2, `MOV_ABS32` =
5, `ABS32` (data pointer) = 8, `FUNCDESC` = 0xB, `GOT16` = 0xF.

## 2. What the compiler never emits

In the tests (about 30 source files at -O0, -O2, -Os and -fPIC):

- the DSP group: lane (`.l`/`.h`/`(v)`) arithmetic, saturating and averaging adds, `all`/`any`/`cmp`/`cmps`,
  the `mem1`/`mem2` multiply-accumulates, `sad4`, `sum`, ... even with `-mllvm -pi32v2-enable-simd`;
- `shl3.*` (`<<<`), `cycc.*` (`<c>`), `shiftr.*`, `add.brev.rr`;
- the flag branches `bc.*`, `cc.set`, `fcmp.rr`, `madd.f.rrr`, `msub.f.rrr`, the `ftoi/ftou` roundings other
  than trunc, `ftof.half/full/even`, `div.s.ppr`/`div.u.ppr`;
- `popcnt.rr` (except through the builtin), the 64-bit `popcnt.r_pair`, `rev16.rr`, `revs.rr`, `cls.rr`,
  `sgn.rr` (builtin only);
- `ld.w.npc`, `ldm.post2`/`ldm.pre*`/`stm.pre*`, `xchg`, `testset`, `lockset`/`lockclr`, `cli`/`sti`, `csync`
  (all but the explicit builtins), `idle`, `swi`, `syscall`, `bkpt`, `callns` and the other secure/non-secure
  entries, the register-count `rep`;
- `ifs2ns`, `gotoss`, `rtns`, `rtss`, `rthw`.

## 3. Builtins

`__builtin_pi32v2_<name>`: `cli`, `sti`, `csync`, `lockset`, `lockclr`, `nop`, `trigger`, `clz`, `cls`,
`popcount`, `rev8`, `zcmp`, `uextra(v, p, l)`, `sextra(v, p, l)`, `flush(addr)`, `flushinv(addr)`,
`iflush(addr)`, `pfetch(addr)` compile to the entry of that name (`flush [r0]`, ...). `swi` and `idle` exist but
are rejected ("cannot compile this builtin function yet"); `smul64`, `umul64`, `insert` are known to the front
end but the back end cannot select them. `__builtin_pi32v2_cli`/`sti` and `__builtin_clz`, `__builtin_bswap*`,
`__builtin_popcount`, `__builtin_ffs`, `__builtin_ctz` also appear in the AC79 SDK's headers [ac79-sdk].
Constant folding by the compiler reveals the intended meaning of `clz` (clz(0) = 32), `cls` (cls(5) = 29,
cls(-6) = 29, cls(0) = 32), `rev8` (byte swap) and `zcmp` (-1, 0, 1: the sign).
