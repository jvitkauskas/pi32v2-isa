<!-- SPDX-FileCopyrightText: 2026 Julius Vitkauskas -->
<!-- SPDX-License-Identifier: CC0-1.0 -->

# Region D implementation report

Worktree `/root/.t3/projects/pi32v2-isa-wt/d`, branch `iter/d`. All committed instruction additions have first words in F000–FFFF. Existing entries were not changed.

## Entries and validation

Added 110 instruction forms; every one was checked with `oracle confirm ... --write` and is confirmed. No guessed entries remain.

Coverage before: **32 / 2671** decodable first words. Coverage after: **2013 of 2671**. This metric probes zero following words; it does not count all operand layouts or second-word instruction variants.

The additions include 25 floating-point arithmetic/conversion forms at f53f, 10 floating-point long branch forms, 10 integer long register branches, 10 compact immediate branches, 10 long immediate branches, two register-AND branches, long call/gotoss/npc load forms, and scalar parallel forms.

Checks: `python3 -m pi32v2isa check`; `python3 -m unittest discover -s tests` (18 passed, 2 optional live tests skipped when the external toolchain environment is unset). The explicit confirmation runs used the external toolchain.

All added IDs:

- branches: `beq.ri`, `bne.ri`, `bge.ri`, `blt.ri`, `bgt.ri`, `ble.ri`, `bges.ri`, `blts.ri`, `bgts.ri`, `bles.ri`, `beq.and.rr`, `bne.and.rr`, `beq.ri.l`, `bne.ri.l`, `bge.ri.l`, `blt.ri.l`, `bgt.ri.l`, `ble.ri.l`, `bges.ri.l`, `blts.ri.l`, `bgts.ri.l`, `bles.ri.l`, `beq.rr.l`, `bne.rr.l`, `bge.rr.l`, `blt.rr.l`, `bgt.rr.l`, `ble.rr.l`, `bges.rr.l`, `blts.rr.l`, `bgts.rr.l`, `bles.rr.l`, `bfeq.rr.l`, `bfune.rr.l`, `bfuge.rr.l`, `bflt.rr.l`, `bfugt.rr.l`, `bfle.rr.l`, `bfge.rr.l`, `bfult.rr.l`, `bfgt.rr.l`, `bfule.rr.l`, `call.xl`, `gotoss.xl`.
- floating-point: `add.f.rrr.p`, `sub.f.rrr.p`, `mul.f.rrr.p`, `div.f.rrr.p`, `fcmp.rr.p`, `fmin.rrr.p`, `fmax.rrr.p`, `madd.f.rrr.p`, `msub.f.rrr.p`, `ftoi.even.rr.p`, `ftoi.trunc.rr.p`, `ftoi.ceil.rr.p`, `ftoi.floor.rr.p`, `ftou.even.rr.p`, `ftou.trunc.rr.p`, `ftou.ceil.rr.p`, `ftou.floor.rr.p`, `ftof.even.rr.p`, `ftof.trunc.rr.p`, `ftof.ceil.rr.p`, `ftof.floor.rr.p`, `itof.rr.p`, `utof.rr.p`, `ftof.half.rr.p`, `ftof.full.rr.p`.
- constants: `li.low16.p`, `li.high16.p`, `li.byte.p`, `li.s16.p`, `li.modimm.p`.
- moves: `mov.r_sr.p`, `mov.sr_r.p`, `mov.l_l.p`, `mov.l_h.p`, `mov.h_l.p`, `mov.h_h.p`.
- arithmetic: `popcnt.r_pair.p`, `rev8.rr.p`, `rev16.rr.p`, `revs.rr.p`, `popcnt.rr.p`, `add.brev.rr.p`, `clz.rr.p`, `cls.rr.p`, `zcmp.rr.p`, `sub.rrr.p`, `addc.rrr.p`, `subc.rrr.p`, `bic.rrr.p`, `div.u.rrr.p`, `div.s.rrr.p`, `add.s14.rri.p`, `lsl.rri.p`, `shl3.rri.p`, `lsr.rri.p`, `shr3.rri.p`, `add.modimm.rri.p`, `lsl.pair.i.p`, `lsl.pair.r.p`, `shl3.pair.i.p`, `shl3.pair.r.p`, `lsr.pair.i.p`, `lsr.pair.r.p`, `shr3.pair.i.p`, `shr3.pair.r.p`.
- memory: `ld.w.npc`.

## Confirmation dependencies outside this region

The assembler sometimes chooses shorter forms owned by B or C. Those forms were defined in temporary tables and independently confirmed before using them to check the D entries. The temporary forms and their examples were not committed. This leaves the checker unchanged and keeps the committed region isolated. After integrating B/C, these dependencies should be available in the ordinary table.

Temporary dependencies:

- C integer register branches: first word `11101cccc000ssss` for condition codes 0,1,2,3,8,9,a,b,c,d; second word `rrrr0--nnnnnnnnn`; signed branch offset `2*n`. All ten passed 1215 probes each.
- C floating-point register branches: the same first words; second word `rrrr10-nnnnnnnnn`. The ten supported condition codes passed 1215 probes each.
- B high-register zero constant: `1101010011000rrr`, where r is `gpr_hi`, prints `{r} = 0  #`; all eight encodings passed.
- B low-register subtraction: `1101111bbaaabddd` prints `{d} = {a} - {b}  #`, all fields `gpr_lo`; all 512 encodings passed.

## Code and table-format change

Added the `shift` operand kind in table.py and codec.py: 5- or 6-bit unsigned shift count whose raw zero prints 32 or 64. This is needed for scalar and register-pair immediate shifts. A unit test covers both widths, their boundaries, and rejection of a four-bit shift field. TABLE-FORMAT.md documents the kind. Existing kinds and oracle.py were not changed.

## Findings for ISA documentation

- Compact immediate branches carry a 10-bit constant split across the first and second words, and a signed nine-bit halfword displacement (-512 through 510 bytes). Equality/inequality and `ifs` comparisons print the constant signed; unsigned relational comparisons print it unsigned. Evidence: f800/f900/fd00 fit and boundary probes; all ten forms confirmed over 2160 probes each.
- Their 48-bit counterparts carry a 12-bit constant in word two and signed halfword displacement in word three (-65536 through 65534 bytes). The same signed/unsigned printing distinction applies. First-word bit 5 is ignored by the disassembler and written zero by the assembler. All ten forms confirmed over 3564 probes each.
- Register-AND branches compare against literal zero and use a signed 16-bit halfword displacement. Registers are in the two low nibbles of the first word.
- Integer register and floating-point long branches use the same condition-code first words at ff40..ff4d. In word two, bit 7 clear selects integer comparison; bits 7..6 = 10 select floating-point comparison. Ten integer and ten floating-point forms confirmed over 1782 probes each.
- Floating-point forms at f53f operate on r0..r15, including conversions printed with `.l`; no new floating-point register names are needed. The 25 added forms cover all 40960 decodable second words in the f53f sweep. The other 24576 second words decode as unknown. Arithmetic, fcmp, min/max, product accumulation, integer conversions, and ftof conversions are present. Exact floating-point formats and fusion/exception behavior are unknown.
- These FPU forms and supported floating-point branches decode and assemble without fprev1, as well as in explicit feature probes. Their confirmations used no feature flag, so they have no fprev1 requirement in the table. This is a tool observation rather than a claim about hardware availability.
- Both popcnt forms require `-minstrev3` for assembly. They are recorded with `requires = ["instrev3"]`; the pair form passed 128 probes and scalar form 256. Objdump prints them regardless of this feature flag.
- Raw zero shift counts mean 32 (single register) or 64 (register pair), rather than zero. Immediate shifts accept 1..32 or 1..64.
- ff80 is a 48-bit signed even 32-bit displacement: the second word contains its low half with bit zero selecting call/gotoss, and the third word the high half. ffa0..ffaf loads from `[npc + displacement]` with the same even displacement order. The meaning/base of npc and the behavior of gotoss remain unknown.

## Oracle/checker limitations and omitted prototypes

No incorrect existing instruction entry was found. The following issues prevented adding otherwise identified layouts without changing the forbidden oracle checking logic:

- Long scalar addition (`f0b4`, low second-word nibble 0), multiplication (`f1f0`, nibble 0), and OR/XOR/AND (`f190`, nibbles 0/1/2) decode as three-register expressions. The assembler selects shorter compound assignments such as `r8 += r0  #`, `r0 *= r0  #`, or `r0 |= r0  #` for some inputs. The checker compares spellings after number normalization and does not equate compound assignments or commuted operands. Prototype confirmations reported 888, 496, and 120/120/120 alternative-encoding disagreements over 4096 probes each, respectively. These five prototypes were omitted. Four register-count shift prototypes at f1c8 were also omitted: their low nibbles 0/1/2/3 print << / <<< / >> / >>> respectively, and the assembler selects compound shifts at da00/da08/da80/da88 for overlapping register operands. For example, r0 = r0 << r0 # assembles to 00 da and decodes as r0 <<= r0 #; the triple-left-shift prototype reported 64 such disagreements over 4096 probes. Immediate and register-pair shift forms were successfully confirmed and retained. Their first/second patterns are `f0b4 / ddddbbbbaaaa0000`, `f1f0 / ddddbbbbaaaa0000`, and `f190 / ddddbbbbaaaa0000` (OR), `...0001` (XOR), and `...0010` (AND).
- At ff44..ff47 with second-word bits 7..6 = 10, objdump prints floating-point conditions `!=`, `u==`, `uno`, `ord`. `oracle encode` reports "assembler output did not match the input" for these printed forms, at both short and long offsets. These four conditions were omitted. At ff4e/ff4f the printed condition is `??`.
- ff00/ff20 immediate condition codes 4,5,6,7,e,f print `??`; no meaning or round-trippable syntax was inferred.
- Modified-immediate scalar forms (f0a0, f0f0, f140, f150, f160/f170, f1e0) have duplicate zero constants for raw immediate values 000/100/200/300. OR/XOR/AND/subtract/multiply can canonicalize those to a different encoding of the same form, which the current checker does not accept. f170 prints the complement of the existing modified-immediate expansion and would need a minimal complement kind. These were left for a separate alias/format treatment. The f0e0 modified-immediate add form did confirm: its aliases assemble to the separately represented signed-14-bit add form.
- ff60/ff61 use a modified-immediate mask plus long branch displacement. They share the duplicate-zero issue. There is also an observed short zero-mask problem: `if ((r0 & 0) == 0) goto 0` assembles to `50 e8 00 00`, which decodes as a mask of 1. Thus the short encoding is not a faithful zero-mask round trip.

## Remaining coverage

Remaining first-word counts by area: `f000-f3ff`: 169, `f400-f7ff`: 469, `ff00-ffbf`: 20.

The uncompleted DSP/vector families at f400..f57f require further half-register/lane and modifier layout work. Other residual scalar forms include saturation, bitfield insertion/extraction, pair arithmetic/division/multiply, and mixed shifts. The complete shape counts below are the final zero-following-word coverage output. Extra forms whose zero second word is unknown (such as the four unsupported floating-point conditions) are described above and are not separate additions to this count.

```text
2013 of 2671 decodable words covered; missing shapes:
    32  4  11110001011.....  R = R & N  #
    32  4  1111010001.....0  r1_r0 = R,R +|+ R,R (usat)  #
    32  4  1111010001.....1  r1_r0 = R,R +|+ R,R (ssat)  #
    32  4  11110100100.....  R.l = R.l + N  #
    32  4  1111010011.....0  R = R.l,R.l +|+ N (usat)  #
    32  4  1111010011.....1  R = R.l,R.l +|+ N (ssat)  #
    32  4  1111010110.....0  R = R.l * N (usat)  #
    32  4  1111010110.....1  R = R.l * N (ssat)  #
    32  4  1111010111.....0  r1_r0 = R.l,R.l *|* N (usat)  #
    32  4  1111010111.....1  r1_r0 = R.l,R.l *|* N (ssat)  #
    16  4  111100001010....  R = N - R  #
    16  4  111100001111....  R = R - N  #
    16  4  111100010100....  R = R | N  #
    16  4  111100010101....  R = R ^ N  #
    16  4  111100011010....  R <= insert(R, p:N, l:N)  #
    16  4  111100011011....  R = uextra(R, p:N, l:N)  #
    16  4  111100011110....  R = R * N  #
    12  6  1111111100.0.1..  if (R ?? N) goto N
     8  4  1111010100000...  R.l = R.l + R.l  #
     6  6  111111110100.1..  if (R ?? R) goto N
     4  4  11110000011110..  R = sat16(R) (u)  #
     4  4  11110100000000..  R = align8(R, R)  #
     4  4  11110100000010..  r1_r0 = unpackb(R) (u)  #
     4  4  11110100000011..  r1_r0 = mts0(R, R)  #
     4  4  11110100000101..  R.l = R.l >< R  #
     4  4  11110100000111..  R = R >< R (v)  #
     4  4  1111010000111..0  R = R + R (usat)  #
     4  4  1111010000111..1  R = R + R (ssat)  #
     2  4  111101000000010.  R = pack(R.l, R.l)  #
     2  4  111101000001001.  R.l = R.l << R  #
     2  4  111101000001100.  R = R << N (v)  #
     2  4  111101000001101.  R = R << R (v)  #
     2  4  111101000010001.  R.l = negs(R.l)  #
     2  4  11110100001001.0  R.l = umax(R.l, R.l)  #
     2  4  11110100001001.1  R.l = umin(R.l, R.l)  #
     2  4  111101000010100.  R = abs(R) (v)  #
     2  4  111101000010101.  R = negs(R) (v)  #
     2  4  11110100001011.0  R = umax(R, R) (v)  #
     2  4  11110100001011.1  R = umin(R, R) (v)  #
     2  4  111101000011000.  R = abs(R)  #
     2  4  111101000011001.  R = negs(R)  #
     2  4  11110100001101.0  R = umax(R, R)  #
     2  4  11110100001101.1  R = umin(R, R)  #
     1  4  1111000001110100  R.l = sat8(R.l) (u)  #
     1  4  1111000010110100  R = R + R  #
     1  4  1111000110010000  R = R | R  #
     1  4  1111000110010100  R = R | (N << R)  #
     1  4  1111000110011000  R <= insert(R, p:R[N:N], l:R[N:N])  #
     1  4  1111000110011100  R = uextra(R, p:R[N:N], l:R[N:N])  #
     1  4  1111000111000100  R = R <> N  #
     1  4  1111000111001000  R = R << R  #
     1  4  1111000111001100  R = R <> R  #
     1  4  1111000111010010  R = r1_r0 >> N (up)  #
     1  4  1111000111010011  R = r1_r0 >> R (up)  #
     1  4  1111000111010100  r1_r0 <>= N  #
     1  4  1111000111011100  r1_r0 <>= R  #
     1  4  1111000111011110  R = r1_r0 >> N (u)  #
     1  4  1111000111011111  R = r1_r0 >> R (u)  #
     1  4  1111000111110000  R = R * R  #
     1  4  1111000111110110  r1_r0 = r1_r0 / R (u)  #
     1  4  1111000111111000  r1_r0 = R * R (u)  #
     1  4  1111000111111100  r1_r0 += R * R (u)  #
     1  4  1111000111111110  r1_r0 -= R * R (u)  #
     1  4  1111000111111111  r1_r0 = copex(r1_r0) (N)  #
     1  4  1111010000000110  R = packb(r1_r0) (usat)  #
     1  4  1111010000010000  R.l = R.l << N  #
     1  4  1111010000010001  R = R >> N (vb)  #
     1  4  1111010000100000  r1_r0 += abs(R -|-|-|- R) (usat)  #
     1  4  1111010000100001  R.l = abs(R.l)  #
     1  4  1111010100001000  R.l = R.l + R.l (usat)  #
     1  4  1111010100001001  R.l = R.l + R.l (ssat)  #
     1  4  1111010100001010  R.l = R.l + R.l (usat,x2)  #
     1  4  1111010100001011  R.l = R.l + R.l (ssat,x2)  #
     1  4  1111010100001100  R.l = R.l + R.l (uavg)  #
     1  4  1111010100001101  R.l = R.l + R.l (savg)  #
     1  4  1111010100001110  R.l = R.l + R.l (rnd,uavg)  #
     1  4  1111010100001111  R.l = R.l + R.l (rnd,savg)  #
     1  4  1111010100010000  R = R.l,R.l +|+ R.l,R.l (usat)  #
     1  4  1111010100010001  R = R.l,R.l +|+ R.l,R.l (ssat)  #
     1  4  1111010100010010  R = R.l,R.l +|+ R.l,R.l (usat,x2)  #
     1  4  1111010100010011  R = R.l,R.l +|+ R.l,R.l (ssat,x2)  #
     1  4  1111010100010100  R = R.l,R.l +|+ R.l,R.h (usat)  #
     1  4  1111010100010101  R = R.l,R.l +|+ R.l,R.h (ssat)  #
     1  4  1111010100010110  R = R.l,R.l +|+ R.l,R.h (usat,x2)  #
     1  4  1111010100010111  R = R.l,R.l +|+ R.l,R.h (ssat,x2)  #
     1  4  1111010100011000  R = R.l,R.l +|+ R.h,R.l (usat)  #
     1  4  1111010100011001  R = R.l,R.l +|+ R.h,R.l (ssat)  #
     1  4  1111010100011010  R = R.l,R.l +|+ R.h,R.l (usat,x2)  #
     1  4  1111010100011011  R = R.l,R.l +|+ R.h,R.l (ssat,x2)  #
     1  4  1111010100011100  R = R.l,R.l +|+ R.h,R.h (usat)  #
     1  4  1111010100011101  R = R.l,R.l +|+ R.h,R.h (ssat)  #
     1  4  1111010100011110  R = R.l,R.l +|+ R.h,R.h (usat,x2)  #
     1  4  1111010100011111  R = R.l,R.l +|+ R.h,R.h (ssat,x2)  #
     1  4  1111010100100000  R = R.l,R.l +|+ R.l,R.l (uavg)  #
     1  4  1111010100100001  R = R.l,R.l +|+ R.l,R.l (savg)  #
     1  4  1111010100100010  R = R.l,R.l +|+ R.l,R.l (rnd,uavg)  #
     1  4  1111010100100011  R = R.l,R.l +|+ R.l,R.l (rnd,savg)  #
     1  4  1111010100100100  R = R.l,R.l +|+ R.l,R.h (uavg)  #
     1  4  1111010100100101  R = R.l,R.l +|+ R.l,R.h (savg)  #
     1  4  1111010100100110  R = R.l,R.l +|+ R.l,R.h (rnd,uavg)  #
     1  4  1111010100100111  R = R.l,R.l +|+ R.l,R.h (rnd,savg)  #
     1  4  1111010100101000  R = R.l,R.l +|+ R.h,R.l (uavg)  #
     1  4  1111010100101001  R = R.l,R.l +|+ R.h,R.l (savg)  #
     1  4  1111010100101010  R = R.l,R.l +|+ R.h,R.l (rnd,uavg)  #
     1  4  1111010100101011  R = R.l,R.l +|+ R.h,R.l (rnd,savg)  #
     1  4  1111010100101100  R = R.l,R.l +|+ R.h,R.h (uavg)  #
     1  4  1111010100101101  R = R.l,R.l +|+ R.h,R.h (savg)  #
     1  4  1111010100101110  R = R.l,R.l +|+ R.h,R.h (rnd,uavg)  #
     1  4  1111010100101111  R = R.l,R.l +|+ R.h,R.h (rnd,savg)  #
     1  4  1111010100110000  r1_r0 = r1_r0 +|+|+|+ r1_r0 (usat)  #
     1  4  1111010100110001  r1_r0 = r1_r0 +|+|+|+ r1_r0 (ssat)  #
     1  4  1111010100110010  r1_r0 = r1_r0 +|+|+|+ r1_r0 (usat,x2)  #
     1  4  1111010100110011  r1_r0 = r1_r0 +|+|+|+ r1_r0 (ssat,x2)  #
     1  4  1111010100110100  r1_r0 = r1_r0 +|+|+|+ r1_r0 (uavg)  #
     1  4  1111010100110101  r1_r0 = r1_r0 +|+|+|+ r1_r0 (savg)  #
     1  4  1111010100110110  r1_r0 = r1_r0 +|+|+|+ r1_r0 (rnd,uavg)  #
     1  4  1111010100110111  r1_r0 = r1_r0 +|+|+|+ r1_r0 (rnd,savg)  #
     1  4  1111010100111000  r1_r0 = all(r1_r0 == r1_r0) (v)
     1  4  1111010100111001  R = all(R == R) (v)
     1  4  1111010100111010  r1_r0 = any(r1_r0 == r1_r0) (v)
     1  4  1111010100111011  R = any(R == R) (v)
     1  4  1111010100111100  r1_r0 = cmp(r1_r0 == r1_r0) (v)
     1  4  1111010100111101  R = cmp(R == R) (v)
     1  4  1111010101000000  R.l = R.l * R.l (usat)  #
     1  4  1111010101000001  R.l = R.l * R.l (ssat)  #
     1  4  1111010101000010  R.l = R.l * R.l (usat,x2)  #
     1  4  1111010101000011  R.l = R.l * R.l (ssat,x2)  #
     1  4  1111010101001000  R.l += R.l * R.l (usat)  #
     1  4  1111010101001001  R.l += R.l * R.l (ssat)  #
     1  4  1111010101001010  R.l += R.l * R.l (usat,x2)  #
     1  4  1111010101001011  R.l += R.l * R.l (ssat,x2)  #
     1  4  1111010101001100  R.l -= R.l * R.l (usat)  #
     1  4  1111010101001101  R.l -= R.l * R.l (ssat)  #
     1  4  1111010101001110  R.l -= R.l * R.l (usat,x2)  #
     1  4  1111010101001111  R.l -= R.l * R.l (ssat,x2)  #
     1  4  1111010101010000  R = R.l * R.l (usat)  #
     1  4  1111010101010001  R = R.l * R.l (ssat)  #
     1  4  1111010101010010  R = R.l * R.l (usat,x2)  #
     1  4  1111010101010011  R = R.l * R.l (ssat,x2)  #
     1  4  1111010101011000  R += R.l * R.l (usat)  #
     1  4  1111010101011001  R += R.l * R.l (ssat)  #
     1  4  1111010101011010  R += R.l * R.l (usat,x2)  #
     1  4  1111010101011011  R += R.l * R.l (ssat,x2)  #
     1  4  1111010101011100  R -= R.l * R.l (usat)  #
     1  4  1111010101011101  R -= R.l * R.l (ssat)  #
     1  4  1111010101011110  R -= R.l * R.l (usat,x2)  #
     1  4  1111010101011111  R -= R.l * R.l (ssat,x2)  #
     1  4  1111010101100000  R = R.l,R.l *|* R.l,R.l (usat)  #
     1  4  1111010101100001  R = R.l,R.l *|* R.l,R.l (ssat)  #
     1  4  1111010101100010  R = R.l,R.l *|* R.l,R.l (usat,x2)  #
     1  4  1111010101100011  R = R.l,R.l *|* R.l,R.l (ssat,x2)  #
     1  4  1111010101100100  R = R.l,R.l *|* R.l,R.h (usat)  #
     1  4  1111010101100101  R = R.l,R.l *|* R.l,R.h (ssat)  #
     1  4  1111010101100110  R = R.l,R.l *|* R.l,R.h (usat,x2)  #
     1  4  1111010101100111  R = R.l,R.l *|* R.l,R.h (ssat,x2)  #
     1  4  1111010101101000  R = R.l,R.l *|* R.h,R.l (usat)  #
     1  4  1111010101101001  R = R.l,R.l *|* R.h,R.l (ssat)  #
     1  4  1111010101101010  R = R.l,R.l *|* R.h,R.l (usat,x2)  #
     1  4  1111010101101011  R = R.l,R.l *|* R.h,R.l (ssat,x2)  #
     1  4  1111010101101100  R = R.l,R.l *|* R.h,R.h (usat)  #
     1  4  1111010101101101  R = R.l,R.l *|* R.h,R.h (ssat)  #
     1  4  1111010101101110  R = R.l,R.l *|* R.h,R.h (usat,x2)  #
     1  4  1111010101101111  R = R.l,R.l *|* R.h,R.h (ssat,x2)  #
     1  4  1111010101110000  r1_r0 = R.l,R.l *|* R.l,R.l (usat)  #
     1  4  1111010101110001  r1_r0 = R.l,R.l *|* R.l,R.l (ssat)  #
     1  4  1111010101110010  r1_r0 = R.l,R.l *|* R.l,R.l (usat,x2)  #
     1  4  1111010101110011  r1_r0 = R.l,R.l *|* R.l,R.l (ssat,x2)  #
     1  4  1111010101110100  r1_r0 = R.l,R.l *|* R.l,R.h (usat)  #
     1  4  1111010101110101  r1_r0 = R.l,R.l *|* R.l,R.h (ssat)  #
     1  4  1111010101110110  r1_r0 = R.l,R.l *|* R.l,R.h (usat,x2)  #
     1  4  1111010101110111  r1_r0 = R.l,R.l *|* R.l,R.h (ssat,x2)  #
     1  4  1111010101111000  r1_r0 = R.l,R.l *|* R.h,R.l (usat)  #
     1  4  1111010101111001  r1_r0 = R.l,R.l *|* R.h,R.l (ssat)  #
     1  4  1111010101111010  r1_r0 = R.l,R.l *|* R.h,R.l (usat,x2)  #
     1  4  1111010101111011  r1_r0 = R.l,R.l *|* R.h,R.l (ssat,x2)  #
     1  4  1111010101111100  r1_r0 = R.l,R.l *|* R.h,R.h (usat)  #
     1  4  1111010101111101  r1_r0 = R.l,R.l *|* R.h,R.h (ssat)  #
     1  4  1111010101111110  r1_r0 = R.l,R.l *|* R.h,R.h (usat,x2)  #
     1  4  1111010101111111  r1_r0 = R.l,R.l *|* R.h,R.h (ssat,x2)  #
     1  6  1111111101100000  if ((R & N) == N) goto N
     1  6  1111111101100001  if ((R & N) != N) goto N
```
