/* SPDX-FileCopyrightText: 2026 Julius Vitkauskas */
/* SPDX-License-Identifier: MIT */
/* Hardware probe (../README.md): misaligned accesses, divide by zero with EMU_CON armed,
 * rep counts and more. An m-apps app (see ../README.md): it installs its own vector-1 handler that records EMU_MSG,
 * DBG_MSG, reti/rete/retx and how many marker instructions after the probed one ran before the exception, then
 * resumes after the markers. Every result is one app_log() line. */
#include "app.h"
#include <stdint.h>

#define VECTOR_1 (*(volatile uint32_t *)0x01c7fe04u)
#define EMU_CON (*(volatile uint32_t *)0x01eef0d0u)
#define EMU_MSG (*(volatile uint32_t *)0x01eef0d4u)
#define DBG_MSG (*(volatile uint32_t *)0x01eee244u)
#define DBG_MSG_CLR (*(volatile uint32_t *)0x01eee248u)

struct trap {
    uint32_t count, emu, dbg, reti, rete, retx, r8;
};
volatile struct trap probe_trap;
volatile uint32_t probe_resume;
volatile uint32_t probe_result[4];

/* Vector 1. The frame: psr at sp+0, r0..r15 from sp+4, rets at sp+68. An exception nobody expects goes to the
 * kit's crash report. */
__asm__(
    ".section .text.probe_vec1,\"ax\",@progbits\n"
    ".globl probe_vec1\n"
    "probe_vec1:\n"
    "  [--sp] = {rets, r15-r0}\n"
    "  r0 = psr\n"
    "  [--sp] = {r0}\n"
    "  r1 = probe_trap\n"
    "  r2 = [r1+0]\n"
    "  r2 = r2 + 1\n"
    "  [r1+0] = r2\n"
    "  r2 = 0x01EEF0D4\n"
    "  r3 = [r2+0]\n"
    "  [r1+4] = r3\n"
    "  r2 = 0x01EEE244\n"
    "  r3 = [r2+0]\n"
    "  [r1+8] = r3\n"
    "  r3 = reti\n"
    "  [r1+12] = r3\n"
    "  r3 = rete\n"
    "  [r1+16] = r3\n"
    "  r3 = retx\n"
    "  [r1+20] = r3\n"
    "  r3 = [sp+36]\n"
    "  [r1+24] = r3\n"
    "  r2 = 0x01EEF0D4\n"
    "  r3 = -1\n"
    "  [r2+0] = r3\n"
    "  r2 = 0x01EEE248\n"
    "  [r2+0] = r3\n"
    "  r2 = probe_resume\n"
    "  r3 = [r2+0]\n"
    "  if (r3 == 0) goto probe_vec1_continue\n"
    "  reti = r3\n"
    "  r3 = 0\n"
    "  [r2+0] = r3\n"
    "  {r0} = [sp++]\n"
    "  psr = r0\n"
    "  {rets, r15-r0} = [sp++]\n"
    "  csync\n"
    "  rti\n"
    /* No resume address: count it and go back to reti, up to 8 times, then the kit's crash report. */
    "probe_vec1_continue:\n"
    "  r2 = probe_trap\n"
    "  r3 = [r2+0]\n"
    "  r2 = 8\n"
    "  if (r3 >= r2) goto probe_vec1_unexpected\n"
    "  {r0} = [sp++]\n"
    "  psr = r0\n"
    "  {rets, r15-r0} = [sp++]\n"
    "  csync\n"
    "  rti\n"
    "probe_vec1_unexpected:\n"
    "  goto app_crash\n");

/* A probe: r0 = address, r1 = value, r2 = second value. The probed instruction is at <name>_insn, followed by
 * twelve marker increments of r8; the handler resumes at <name>_resume. Results: r8, r9 (a loaded word or a
 * quotient), r10/r11 (a pair). */
#define PROBE(name, insn) \
    ".section .text." #name ",\"ax\",@progbits\n" \
    ".globl " #name "\n" \
    #name ":\n" \
    "  [--sp] = {rets, r15-r4}\n" \
    "  r8 = 0\n" \
    "  r9 = 0x5EED5EED\n" \
    "  r10 = r1\n" \
    "  r11 = r2\n" \
    "  r4 = " #name "_resume\n" \
    "  r5 = probe_resume\n" \
    "  [r5+0] = r4\n" \
    "  csync\n" \
    ".globl " #name "_insn\n" \
    #name "_insn:\n" \
    "  " insn "\n" \
    "  r8 = r8 + 1\n  r8 = r8 + 1\n  r8 = r8 + 1\n  r8 = r8 + 1\n" \
    "  r8 = r8 + 1\n  r8 = r8 + 1\n  r8 = r8 + 1\n  r8 = r8 + 1\n" \
    "  r8 = r8 + 1\n  r8 = r8 + 1\n  r8 = r8 + 1\n  r8 = r8 + 1\n" \
    #name "_resume:\n" \
    "  r5 = probe_resume\n" \
    "  r4 = 0\n" \
    "  [r5+0] = r4\n" \
    "  r5 = probe_result\n" \
    "  [r5+0] = r8\n" \
    "  [r5+4] = r9\n" \
    "  [r5+8] = r10\n" \
    "  [r5+12] = r11\n" \
    "  {pc, r15-r4} = [sp++]\n"

__asm__(
    PROBE(p_ldw, "r9 = [r0+0]")
    PROBE(p_ldhu, "r9 = h[r0+0] (u)")
    PROBE(p_ldhs, "r9 = h[r0+0] (s)")
    PROBE(p_ldbu, "r9 = b[r0+0] (u)")
    PROBE(p_stw, "[r0+0] = r1")
    PROBE(p_sth, "h[r0+0] = r1")
    PROBE(p_ldd, "r11_r10 = d[r0+0]")
    PROBE(p_std, "d[r0+0] = r11_r10")
    PROBE(p_divs, "r9 = r1 / r2 (s)")
    PROBE(p_divu, "r9 = r1 / r2 (u)")
    PROBE(p_divsp, "r11_r10 = r11_r10 / r0 (s)")
    PROBE(p_divup, "r11_r10 = r11_r10 / r0 (u)")
    PROBE(p_divf, "r9 = r1 / r2 (f)")
    PROBE(p_addf, "r9 = r1 + r2 (f)"));

/* rep with the count in r0: r5 counts the body's runs; r6 is the count register afterwards. */
__asm__(
    ".section .text.p_rep,\"ax\",@progbits\n"
    ".globl p_rep\n"
    "p_rep:\n"
    "  [--sp] = {rets, r15-r4}\n"
    "  r5 = 0\n"
    "  r6 = r0\n"
    "  rep r6 {\n"
    "    r5 = r5 + 1\n"
    "  }\n"
    "  r4 = probe_result\n"
    "  [r4+0] = r5\n"
    "  [r4+4] = r6\n"
    "  {pc, r15-r4} = [sp++]\n");


/* H6: a marker function copied outside the PC-limit windows, called from p_pcl (r0 = its address). */
__asm__(
    ".section .text.p_far_tmpl,\"ax\",@progbits\n"
    ".globl p_far_tmpl, p_far_tmpl_end\n"
    "p_far_tmpl:\n"
    "  r8 = r8 + 1\n  r8 = r8 + 1\n  r8 = r8 + 1\n  r8 = r8 + 1\n"
    "  r8 = r8 + 1\n  r8 = r8 + 1\n  r8 = r8 + 1\n  r8 = r8 + 1\n"
    "  r8 = r8 + 1\n  r8 = r8 + 1\n  r8 = r8 + 1\n  r8 = r8 + 1\n"
    "  rts\n"
    "p_far_tmpl_end:\n"
    ".section .text.p_pcl,\"ax\",@progbits\n"
    ".globl p_pcl, p_pcl_call\n"
    "p_pcl:\n"
    "  [--sp] = {rets, r15-r4}\n"
    "  r8 = 0\n"
    "  r4 = p_pcl_resume\n"
    "  r5 = probe_resume\n"
    "  [r5+0] = r4\n"
    "  csync\n"
    "p_pcl_call:\n"
    "  call r0\n"
    "p_pcl_resume:\n"
    "  r5 = probe_resume\n"
    "  r4 = 0\n"
    "  [r5+0] = r4\n"
    "  r5 = probe_result\n"
    "  [r5+0] = r8\n"
    "  {pc, r15-r4} = [sp++]\n");

/* H7: 256 copies of an instruction between two reads of the core's cycle counter (C0_TL_CKCNTL). r0 = a RAM
 * word's address, r1 = a nonzero divisor; returns cycles in probe_result[0]. */
#define TIMED(name, setup, insn) \
    ".section .text." #name ",\"ax\",@progbits\n" \
    ".globl " #name "\n" \
    #name ":\n" \
    "  [--sp] = {rets, r15-r4}\n" \
    "  r4 = 3\n  r5 = 5\n  r6 = 7\n  r7 = r1\n  r9 = r0\n" \
    setup \
    "  r12 = 0x01EEE218\n" \
    "  csync\n" \
    "  r13 = [r12+0]\n" \
    "  .rept 256\n" \
    "  " insn "\n" \
    "  .endr\n" \
    "  r14 = [r12+0]\n" \
    "  r14 = r14 - r13\n" \
    "  r12 = probe_result\n" \
    "  [r12+0] = r14\n" \
    "  {pc, r15-r4} = [sp++]\n"

__asm__(
    TIMED(c_none, "", "")
    TIMED(c_nop, "", "nop")
    TIMED(c_add_dep, "", "r4 = r4 + 1")
    TIMED(c_add_indep, "", "r4 = r5 + r6\n  r10 = r5 + r6")
    TIMED(c_mov32, "", "r4 = 0x12345678")
    TIMED(c_ld, "", "r4 = [r9+0]")
    TIMED(c_ld_use, "", "r4 = [r9+0]\n  r5 = r4 + 1")
    TIMED(c_st, "", "[r9+0] = r4")
    TIMED(c_mul, "", "r4 = r5 * r6")
    TIMED(c_div, "", "r4 = r5 / r7 (s)")
    TIMED(c_fadd, "  r5 = 0x3f800000\n  r6 = 0x40000000\n", "r4 = r5 + r6 (f)")
    TIMED(c_fmul, "  r5 = 0x3f800000\n  r6 = 0x40000000\n", "r4 = r5 * r6 (f)")
    TIMED(c_fdiv, "  r5 = 0x3f800000\n  r6 = 0x40000000\n", "r4 = r5 / r6 (f)")
    TIMED(c_mul64, "", "r11_r10 = r5 * r6 (s)")
    TIMED(c_goto, "", "goto 1f\n  1:")
    TIMED(c_br_nt, "", "if (r4 == 0) goto 1f\n  1:")
    TIMED(c_br_t, "", "if (r4 != 0) goto 1f\n  1:")
    TIMED(c_call, "", "call 2f\n  goto 3f\n  2: rts\n  3:")
    TIMED(c_push1, "", "[--sp] = {r4}\n  {r4} = [sp++]")
    TIMED(c_ldd, "", "r11_r10 = d[r9+0]"));


/* rep under interrupts: TIMER5 (vector 63) counts its entries and where reti pointed. p_ri(count, outer): r6 =
 * count, the body (~72 cycles: seven divides and r5 += 1) in a rep; with outer != 0 the compiler's
 * `if (r6 != 0) goto` re-enters the rep. Results: r5 (body runs), r6. */
volatile uint32_t irq_rec[8]; /* count, last reti, in body, at rep word, other */
__asm__(
    ".section .text.probe_vec63,\"ax\",@progbits\n"
    ".globl probe_vec63\n"
    "probe_vec63:\n"
    "  [--sp] = {rets, r15-r0}\n"
    "  r0 = psr\n"
    "  [--sp] = {r0}\n"
    "  r1 = irq_rec\n"
    "  r2 = [r1+0]\n  r2 = r2 + 1\n  [r1+0] = r2\n"
    "  r3 = reti\n  [r1+4] = r3\n"
    "  r4 = p_ri_body\n"
    "  if (r3 < r4) goto probe_vec63_out\n"
    "  r4 = p_ri_body_end\n"
    "  if (r3 >= r4) goto probe_vec63_out\n"
    "  r2 = [r1+8]\n  r2 = r2 + 1\n  [r1+8] = r2\n"
    "  goto probe_vec63_ack\n"
    "probe_vec63_out:\n"
    "  r4 = p_ri_rep\n"
    "  if (r3 != r4) goto probe_vec63_other\n"
    "  r2 = [r1+12]\n  r2 = r2 + 1\n  [r1+12] = r2\n"
    "  goto probe_vec63_ack\n"
    "probe_vec63_other:\n"
    "  r2 = [r1+16]\n  r2 = r2 + 1\n  [r1+16] = r2\n"
    "probe_vec63_ack:\n"
    "  r2 = 0x10900\n  r3 = [r2+0]\n  r4 = 0x4000\n  r3 = r3 | r4\n  [r2+0] = r3\n"
    "  {r0} = [sp++]\n"
    "  psr = r0\n"
    "  {rets, r15-r0} = [sp++]\n"
    "  csync\n"
    "  rti\n"
    ".section .text.p_ri,\"ax\",@progbits\n"
    ".globl p_ri, p_ri_rep, p_ri_body, p_ri_body_end\n"
    "p_ri:\n"
    "  [--sp] = {rets, r15-r4}\n"
    "  r5 = 0\n  r6 = r0\n  r7 = 1000000\n  r8 = 7\n  r9 = r1\n"
    "p_ri_rep:\n"
    "  rep r6 {\n"
    "p_ri_body:\n"
    "    r4 = r7 / r8 (s)\n    r4 = r7 / r8 (s)\n    r4 = r7 / r8 (s)\n    r4 = r7 / r8 (s)\n"
    "    r4 = r7 / r8 (s)\n    r4 = r7 / r8 (s)\n    r4 = r7 / r8 (s)\n"
    "    r5 = r5 + 1\n"
    "  }\n"
    "p_ri_body_end:\n"
    "  if (r9 == 0) goto p_ri_done\n"
    "  if (r6 != 0) goto p_ri_rep\n"
    "p_ri_done:\n"
    "  r4 = probe_result\n"
    "  [r4+0] = r5\n"
    "  [r4+4] = r6\n"
    "  {pc, r15-r4} = [sp++]\n");
extern void p_ri(uint32_t, uint32_t);
extern void probe_vec63(void);


/* One instruction from RAM with every register given: gen_state points at {in[16], psr_in, out[16], psr_out};
 * gen_slot holds the instruction, a nop (a parallel twin's partner) and rts. A trap resumes at p_gen_after. */
volatile uint32_t *volatile gen_state;
uint16_t gen_slot[8] __attribute__((aligned(4)));
__asm__(
    ".section .text.p_gen,\"ax\",@progbits\n"
    ".globl p_gen, p_gen_after\n"
    "p_gen:\n"
    "  [--sp] = {rets, r15-r4}\n"
    "  r1 = p_gen_after\n"
    "  r2 = probe_resume\n"
    "  [r2+0] = r1\n"
    "  r1 = gen_state\n"
    "  r0 = [r1+0]\n"
    "  r1 = [r0+64]\n"
    "  psr = r1\n"
    "  r15 = [r0+60]\n  r14 = [r0+56]\n  r13 = [r0+52]\n  r12 = [r0+48]\n"
    "  r11 = [r0+44]\n  r10 = [r0+40]\n  r9 = [r0+36]\n  r8 = [r0+32]\n"
    "  r7 = [r0+28]\n  r6 = [r0+24]\n  r5 = [r0+20]\n  r4 = [r0+16]\n"
    "  r3 = [r0+12]\n  r2 = [r0+8]\n  r1 = [r0+4]\n  r0 = [r0+0]\n"
    "  call gen_slot\n"
    "p_gen_after:\n"
    "  [--sp] = {r0}\n"
    "  r0 = psr\n"
    "  [--sp] = {r0}\n"
    "  r0 = gen_state\n"
    "  r0 = [r0+0]\n"
    "  [r0+72] = r1\n  [r0+76] = r2\n  [r0+80] = r3\n  [r0+84] = r4\n"
    "  [r0+88] = r5\n  [r0+92] = r6\n  [r0+96] = r7\n  [r0+100] = r8\n"
    "  [r0+104] = r9\n  [r0+108] = r10\n  [r0+112] = r11\n  [r0+116] = r12\n"
    "  [r0+120] = r13\n  [r0+124] = r14\n  [r0+128] = r15\n"
    "  {r1} = [sp++]\n"
    "  [r0+132] = r1\n"
    "  {r1} = [sp++]\n"
    "  [r0+68] = r1\n"
    "  r1 = probe_resume\n  r2 = 0\n  [r1+0] = r2\n"
    "  {pc, r15-r4} = [sp++]\n");
extern void p_gen(void);
#include "x2_cases.h"
#include "x14_cases.h"


/* if-blocks whose then- or else-part is a parallel pair: p_ifp(a, b, which). r2 counts A, the word at ifp_mem
 * is B's store, r6 runs after the block, r9 counts the other part. Results: r2, ifp_mem, r6, r9. */
volatile uint32_t ifp_mem;
__asm__(
    ".section .text.p_ifp,\"ax\",@progbits\n"
    ".globl p_ifp\n"
    "p_ifp:\n"
    "  [--sp] = {rets, r15-r4}\n"
    "  r10 = r2\n"
    "  r2 = 0\n  r3 = ifp_mem\n  r4 = 0x1234\n  r5 = 1\n  r6 = 0\n  r9 = 0\n  r7 = 0\n  [r3+0] = r7\n"
    "  if (r2 != 0) goto p_ifp_x\n"
    "  r7 = 1\n"
    "  if (r10 == r7) goto p_ifp_else\n"
    "  if (r0 == r1) {\n"
    "    r2 = r2 + r5  #\n"
    "    [r3+0] = r4\n"
    "  }\n"
    "  r6 = r6 + r5\n"
    "  goto p_ifp_done\n"
    "p_ifp_else:\n"
    "  if (r0 == r1) {\n"
    "    r9 = r9 + r5\n"
    "  } else {\n"
    "    r2 = r2 + r5  #\n"
    "    [r3+0] = r4\n"
    "  }\n"
    "  r6 = r6 + r5\n"
    "p_ifp_done:\n"
    "p_ifp_x:\n"
    "  r7 = probe_result\n"
    "  [r7+0] = r2\n"
    "  r8 = [r3+0]\n"
    "  [r7+4] = r8\n"
    "  [r7+8] = r6\n"
    "  [r7+12] = r9\n"
    "  {pc, r15-r4} = [sp++]\n");
extern void p_ifp(uint32_t, uint32_t, uint32_t);

typedef void probe_fn(uint32_t, uint32_t, uint32_t);
extern probe_fn p_ldw, p_ldhu, p_ldhs, p_ldbu, p_stw, p_sth, p_ldd, p_std, p_divs, p_divu, p_divsp, p_divup, p_divf,
    p_addf;
extern char p_ldw_insn[], p_ldhu_insn[], p_ldhs_insn[], p_ldbu_insn[], p_stw_insn[], p_sth_insn[], p_ldd_insn[],
    p_std_insn[], p_divs_insn[], p_divu_insn[], p_divsp_insn[], p_divup_insn[], p_divf_insn[], p_addf_insn[];
extern void p_rep(uint32_t);
extern void probe_vec1(void);

static uint8_t buffer[64] __attribute__((aligned(8)));

static void fill(void) {
    for (unsigned i = 0; i < sizeof buffer; ++i)
        buffer[i] = (uint8_t)(0x10+i);
}

static void run(const char *name, probe_fn *f, const char *insn, uint32_t a, uint32_t b, uint32_t c) {
    probe_trap.count = probe_trap.emu = probe_trap.dbg = probe_trap.reti = probe_trap.rete = probe_trap.retx =
        probe_trap.r8 = 0;
    EMU_MSG = 0xffffffffu;
    DBG_MSG_CLR = 0xffffffffu;
    sync_cpu();
    f(a, b, c);
    uint32_t at = (uint32_t)(uintptr_t)insn;
    if (probe_trap.count)
        app_log("%s %x: TRAP n%u emu %x dbg %x reti+%x rete %x retx %x mk %u | %x %x %x", name, (unsigned)a,
                (unsigned)probe_trap.count, (unsigned)probe_trap.emu, (unsigned)probe_trap.dbg,
                (unsigned)(probe_trap.reti-at), (unsigned)probe_trap.rete, (unsigned)probe_trap.retx,
                (unsigned)probe_trap.r8, (unsigned)probe_result[1], (unsigned)probe_result[2],
                (unsigned)probe_result[3]);
    else
        app_log("%s %x: ok mk %u | %x %x %x", name, (unsigned)a, (unsigned)probe_result[0],
                (unsigned)probe_result[1], (unsigned)probe_result[2], (unsigned)probe_result[3]);
}

static void dump(const char *what) {
    const uint32_t *w = (const uint32_t *)buffer;
    app_log("  %s mem %08x %08x %08x %08x", what, (unsigned)w[0], (unsigned)w[1], (unsigned)w[2], (unsigned)w[3]);
}

#define RUN(f, a, b, c) run(#f, f, f##_insn, (uint32_t)(a), (uint32_t)(b), (uint32_t)(c))

__attribute__((unused)) static void misaligned(void) {
    uint32_t base = (uint32_t)(uintptr_t)buffer;
    for (unsigned off = 0; off < 4; ++off) {
        fill();
        RUN(p_ldw, base+off, 0, 0);
    }
    for (unsigned off = 0; off < 4; ++off) {
        fill();
        RUN(p_ldhu, base+off, 0, 0);
    }
    fill();
    RUN(p_ldhs, base+1, 0, 0);
    fill();
    RUN(p_ldbu, base+3, 0, 0);
    for (unsigned off = 1; off < 4; ++off) {
        fill();
        RUN(p_stw, base+off, 0xa1b2c3d4u, 0);
        dump("stw");
    }
    fill();
    RUN(p_sth, base+1, 0xa1b2c3d4u, 0);
    dump("sth+1");
    for (unsigned off = 0; off <= 4; off += 2) {
        fill();
        RUN(p_ldd, base+off, 0, 0);
    }
    for (unsigned off = 2; off <= 4; off += 2) {
        fill();
        RUN(p_std, base+off, 0xa1b2c3d4u, 0x55667788u);
        dump("std");
    }
}

__attribute__((unused)) static void divides(void) {
    RUN(p_divs, 0, 7, 0);
    RUN(p_divu, 0, 7, 0);
    RUN(p_divsp, 0, 7, 9);
    RUN(p_divup, 0, 7, 9);
    RUN(p_divf, 0, 0x3f800000u, 0);          /* 1.0f / 0.0f */
    RUN(p_divf, 0, 0, 0);                    /* 0.0f / 0.0f */
    RUN(p_addf, 0, 0x7f800000u, 0xff800000u); /* inf + -inf */
}

__attribute__((unused)) static void rep(uint32_t n) {
    app_log("rep %u: start", (unsigned)n);
    p_rep(n);
    app_log("rep %u: body ran %u, count register %08x", (unsigned)n, (unsigned)probe_result[0],
            (unsigned)probe_result[1]);
}


extern void p_pcl(uint32_t);
extern char p_far_tmpl[], p_far_tmpl_end[], p_pcl_call[];
typedef void timed_fn(uint32_t, uint32_t);
extern timed_fn c_none, c_nop, c_add_dep, c_add_indep, c_mov32, c_ld, c_ld_use, c_st, c_mul, c_div, c_fadd, c_fmul,
    c_fdiv, c_mul64, c_goto, c_br_nt, c_br_t, c_call, c_push1, c_ldd;

#define PCL0_H (*(volatile uint32_t *)0x01eee380u)
#define PCL0_L (*(volatile uint32_t *)0x01eee384u)
#define PCL1_H (*(volatile uint32_t *)0x01eee388u)
#define PCL1_L (*(volatile uint32_t *)0x01eee38cu)
#define DBG_EN (*(volatile uint32_t *)0x01eee340u)
#define DBG_CON (*(volatile uint32_t *)0x01eee344u)
#define DBG_WR_EN (*(volatile uint32_t *)0x01eee240u)
#define FAR 0x01c17000u

__attribute__((unused)) static void pcl_at(const char *what, uint32_t far) {
    probe_trap.count = probe_trap.emu = probe_trap.dbg = probe_trap.reti = probe_trap.r8 = 0;
    EMU_MSG = 0xffffffffu;
    DBG_MSG_CLR = 0xffffffffu;
    sync_cpu();
    p_pcl(far);
    app_log("%s @%x: n%u emu %x dbg %x reti far+%x mk %u, after: mk %u", what, (unsigned)far, (unsigned)probe_trap.count,
            (unsigned)probe_trap.emu, (unsigned)probe_trap.dbg, (unsigned)(probe_trap.reti-far), (unsigned)probe_trap.r8,
            (unsigned)probe_result[0]);
}
__attribute__((unused)) static void pcl(const char *what) {
    pcl_at(what, FAR);
}
__attribute__((unused)) static void place(uint32_t at) {
    for (const char *p = p_far_tmpl; p < p_far_tmpl_end; ++p)
        ((volatile char *)at)[p-p_far_tmpl] = *p;
    sync_cpu();
}

__attribute__((unused)) static void timed(const char *name, timed_fn *f, uint32_t base) {
    static uint32_t word __attribute__((aligned(8)));
    word = 1;
    f((uint32_t)(uintptr_t)&word, 3);
    uint32_t c = probe_result[0];
    app_log("%s: %u cycles, %u.%02u per (net)", name, (unsigned)c, (unsigned)((c-base)/256),
            (unsigned)(((c-base)%256)*100/256));
}
#define TIMED_RUN(f) timed(#f, f, base)

#ifndef GROUP
#define GROUP 1
#endif
int app_main(unsigned lsb_mhz) {
    (void)lsb_mhz;
    uint32_t emu_con = EMU_CON, kit_vector = VECTOR_1;
    app_log("EMU_CON=%08x EMU_MSG=%08x DBG_MSG=%08x", (unsigned)emu_con, (unsigned)EMU_MSG, (unsigned)DBG_MSG);
    VECTOR_1 = (uint32_t)(uintptr_t)probe_vec1;
    sync_cpu();

#if GROUP == 1
    app_log("== misaligned, EMU_CON as found");
    misaligned();
    for (unsigned bit = 0; bit < 2; ++bit) {
        EMU_CON = emu_con ^ (1u << bit);
        sync_cpu();
        app_log("== ldw+1 with EMU_CON %x", (unsigned)EMU_CON);
        fill();
        RUN(p_ldw, (uint32_t)(uintptr_t)buffer+1, 0, 0);
    }
    EMU_CON = emu_con;
    sync_cpu();
#elif GROUP == 2
    app_log("== divides, EMU_CON as found");
    divides();
    EMU_CON = emu_con | 4u;
    sync_cpu();
    app_log("== divides, EMU_CON %x", (unsigned)EMU_CON);
    divides();
    EMU_CON = emu_con;
    sync_cpu();
#elif GROUP == 3
    for (unsigned bit = 16; bit <= 20; ++bit) {
        EMU_CON = emu_con | (1u << bit);
        sync_cpu();
        app_log("== float, EMU_CON %x", (unsigned)EMU_CON);
        RUN(p_divf, 0, 0x3f800000u, 0);           /* 1 / 0 */
        RUN(p_divf, 0, 0, 0);                     /* 0 / 0 */
        RUN(p_addf, 0, 0x7f800000u, 0xff800000u); /* inf + -inf */
        RUN(p_addf, 0, 0x7f7fffffu, 0x7f7fffffu); /* overflow */
        RUN(p_divf, 0, 0x00800000u, 0x4b000000u); /* tiny: 2^-126 / 2^23 */
        RUN(p_divf, 0, 0x3f800000u, 0x40400000u); /* inexact: 1 / 3 */
        EMU_CON = emu_con;
        sync_cpu();
    }
#elif GROUP == 4
    app_log("== rep");
    static const uint32_t counts[] = {1, 7, 255, 256, 65535, 65536, 0x01000001u};
    for (unsigned i = 0; i < sizeof counts/sizeof counts[0]; ++i)
        rep(counts[i]);
    VECTOR_1 = kit_vector;
    sync_cpu();
    /* Last: if a count of 0 means 2^32, this runs until the watchdog resets into download mode. */
    rep(0);
#elif GROUP == 5
    app_log("== rep boundaries");
    static const uint32_t counts5[] = {2, 31, 32, 33, 34, 63, 64, 65, 96, 97, 0x7fffffffu, 0x80000000u, 0xffffffffu};
    for (unsigned i = 0; i < sizeof counts5/sizeof counts5[0]; ++i)
        rep(counts5[i]);
#elif GROUP == 6
    app_log("DBG_EN %x DBG_CON %x DBG_WR_EN %x PCL0 %x-%x PCL1 %x-%x", (unsigned)DBG_EN, (unsigned)DBG_CON,
            (unsigned)DBG_WR_EN, (unsigned)PCL0_L, (unsigned)PCL0_H, (unsigned)PCL1_L, (unsigned)PCL1_H);
    for (const char *p = p_far_tmpl; p < p_far_tmpl_end; ++p)
        ((volatile char *)FAR)[p-p_far_tmpl] = *p;
    sync_cpu();
    uint32_t l0 = PCL0_L, h0 = PCL0_H, l1 = PCL1_L, h1 = PCL1_H;
    pcl("no limits");
    /* window 0: the app slot; window 1: the same (no second region) */
    PCL0_L = 0x01c30000u; PCL0_H = 0x01c7f000u;
    PCL1_L = 0x01c30000u; PCL1_H = 0x01c7f000u;
    sync_cpu();
    app_log("set: PCL0 %x-%x PCL1 %x-%x", (unsigned)PCL0_L, (unsigned)PCL0_H, (unsigned)PCL1_L, (unsigned)PCL1_H);
    pcl("limits, DBG_EN as found");
    uint32_t en = DBG_EN;
    DBG_EN = en | (0x3fu << 16) | (0x3u << 4);
    sync_cpu();
    app_log("DBG_EN now %x", (unsigned)DBG_EN);
    pcl("limits, DBG_EN as the SDK");
    DBG_EN = en;
    PCL0_L = l0; PCL0_H = h0; PCL1_L = l1; PCL1_H = h1;
    sync_cpu();
    pcl("limits restored");
#elif GROUP == 8
    for (const char *p = p_far_tmpl; p < p_far_tmpl_end; ++p)
        ((volatile char *)FAR)[p-p_far_tmpl] = *p;
    sync_cpu();
    uint32_t l0 = PCL0_L, h0 = PCL0_H, l1 = PCL1_L, h1 = PCL1_H, en = DBG_EN;
    PCL0_L = 0x01c30000u; PCL0_H = 0x01c7f000u;
    PCL1_L = 0x01c30000u; PCL1_H = 0x01c7f000u;
    sync_cpu();
    static const uint32_t ens[] = {0x3f0030u, 0, 0x3f0030u, 0x30u, 0x3f0000u, 1u << 16, 1u << 17, 1u << 18, 1u << 19,
                                   1u << 20, 1u << 21, 1u << 4, 1u << 5, 0};
    for (unsigned i = 0; i < sizeof ens/sizeof ens[0]; ++i) {
        DBG_EN = ens[i];
        sync_cpu();
        char what[24] = "DBG_EN ";
        unsigned v = (unsigned)DBG_EN, n = 7;
        for (int k = 28; k >= 0; k -= 4)
            what[n++] = "0123456789abcdef"[(v >> k) & 15];
        what[n] = 0;
        app_log("step %u: %s", i, what);
        pcl(what);
    }
    DBG_EN = en;
    PCL0_L = l0; PCL0_H = h0; PCL1_L = l1; PCL1_H = h1;
    sync_cpu();
#elif GROUP == 9
    uint32_t l0 = PCL0_L, h0 = PCL0_H, l1 = PCL1_L, h1 = PCL1_H;
    PCL0_L = 0x01c30000u; PCL0_H = 0x01c7f000u;
    PCL1_L = 0x01c30000u; PCL1_H = 0x01c7f000u;
    sync_cpu();
    for (unsigned i = 0; i < 4; ++i) {
        uint32_t at = FAR+0x400u*i;
        place(at);
        pcl_at("fresh", at);
        pcl_at("again", at);
    }
    /* the first copy once more, after the others may have pushed it out of the cache */
    pcl_at("first again", FAR);
    /* rewrite the first copy (same address, new bytes) */
    place(FAR);
    pcl_at("rewritten", FAR);
    PCL0_L = l0; PCL0_H = h0; PCL1_L = l1; PCL1_H = h1;
    sync_cpu();
#elif GROUP == 10
    uint32_t l0 = PCL0_L, h0 = PCL0_H, l1 = PCL1_L, h1 = PCL1_H;
    place(FAR);
    for (unsigned i = 0; i < 3; ++i) {
        PCL0_L = 0x01c30000u; PCL0_H = 0x01c7f000u;
        PCL1_L = 0x01c30000u; PCL1_H = 0x01c7f000u;
        sync_cpu();
        pcl("limits rewritten");
        app_log("  PCL0 %x-%x PCL1 %x-%x DBG_MSG %x", (unsigned)PCL0_L, (unsigned)PCL0_H, (unsigned)PCL1_L,
                (unsigned)PCL1_H, (unsigned)DBG_MSG);
    }
    for (unsigned i = 0; i < 2; ++i) {
        PCL0_L = l0; PCL0_H = h0; PCL1_L = l1; PCL1_H = h1;
        sync_cpu();
        PCL0_L = 0x01c30000u; PCL0_H = 0x01c7f000u;
        PCL1_L = 0x01c30000u; PCL1_H = 0x01c7f000u;
        sync_cpu();
        pcl("limits opened, then narrowed");
    }
    /* only window 1 narrowed, window 0 still open */
    PCL0_L = l0; PCL0_H = h0;
    sync_cpu();
    pcl("window 0 open, window 1 narrow");
    PCL0_L = l0; PCL0_H = h0; PCL1_L = l1; PCL1_H = h1;
    sync_cpu();
#elif GROUP == 11
    uint32_t l0 = PCL0_L, h0 = PCL0_H, l1 = PCL1_L, h1 = PCL1_H, con = DBG_CON;
    place(FAR);
    PCL0_L = 0x01c30000u; PCL0_H = 0x01c7f000u;
    PCL1_L = 0x01c30000u; PCL1_H = 0x01c7f000u;
    sync_cpu();
    pcl("first");
    app_log("  DBG_CON %x DBG_MSG %x", (unsigned)DBG_CON, (unsigned)DBG_MSG);
    pcl("second, nothing acknowledged");
    static const uint32_t acks[] = {1u << 17, 1u << 18, (1u << 17) | (1u << 18)};
    for (unsigned i = 0; i < 3; ++i) {
        DBG_CON = con | acks[i];
        sync_cpu();
        app_log("  DBG_CON |= %x: reads %x", (unsigned)acks[i], (unsigned)DBG_CON);
        DBG_CON = con;
        sync_cpu();
        pcl("after the ack");
        pcl("once more");
    }
    PCL0_L = l0; PCL0_H = h0; PCL1_L = l1; PCL1_H = h1;
    DBG_CON = con;
    sync_cpu();
#elif GROUP == 12
    volatile uint32_t *vec63 = (volatile uint32_t *)0x01c7fefcu, *icfg7 = (volatile uint32_t *)0x01eef11cu;
    uint32_t old63 = *vec63, oldi7 = *icfg7, oldicfg;
    __asm__ volatile("%0 = icfg" : "=r"(oldicfg));
    *vec63 = (uint32_t)(uintptr_t)probe_vec63;
    *icfg7 = (oldi7 & 0x0fffffffu) | 0x70000000u; /* source 63 on, priority 3 */
    REG(0x10900u) = 0x4000u;
    REG(0x10904u) = 0;
    REG(0x10908u) = 300;
    REG(0x10900u) = 0x4019u;
    sync_cpu();
    __asm__ volatile("r0 = 0x300\n\ticfg = r0\n\tcsync" ::: "r0");
    static const uint32_t cases[][2] = {{31, 0}, {7, 0}, {1000, 1}, {100000, 1}, {0x10000, 1}};
    for (unsigned k = 0; k < sizeof cases/sizeof cases[0]; ++k)
        for (unsigned rep_i = 0; rep_i < 3; ++rep_i) {
            for (unsigned j = 0; j < 8; ++j)
                irq_rec[j] = 0;
            p_ri(cases[k][0], cases[k][1]);
            app_log("rep %u%s: body ran %u, r6 %x | irqs %u: in body %u, at rep %u, other %u, last reti %x",
                    (unsigned)cases[k][0], cases[k][1] ? "+loop" : "", (unsigned)probe_result[0],
                    (unsigned)probe_result[1], (unsigned)irq_rec[0], (unsigned)irq_rec[2], (unsigned)irq_rec[3],
                    (unsigned)irq_rec[4], (unsigned)irq_rec[1]);
        }
    __asm__ volatile("cli\n\tr0 = 0\n\ticfg = r0\n\tcsync" ::: "r0");
    REG(0x10900u) = 0x4000u;
    *icfg7 = oldi7;
    *vec63 = old63;
    __asm__ volatile("icfg = %0\n\tcsync" ::"r"(oldicfg));
    extern char p_ri_rep[], p_ri_body[], p_ri_body_end[];
    app_log("rep at %x, body %x..%x", (unsigned)(uintptr_t)p_ri_rep, (unsigned)(uintptr_t)p_ri_body,
            (unsigned)(uintptr_t)p_ri_body_end);
#elif GROUP == 13
    /* results at 0x01C70000: per case and input set, 20 words: out r0..r15, psr, traps, EMU_MSG, the insn */
    volatile uint32_t *res = (volatile uint32_t *)0x01c70000u;
    static uint32_t st[34];
    gen_state = st;
    unsigned n = 0;
    for (unsigned c = 0; c < sizeof x2_insn/sizeof x2_insn[0]; ++c)
        for (unsigned set = 0; set < sizeof x2_sets/sizeof x2_sets[0]; ++set) {
            gen_slot[0] = (uint16_t)(x2_insn[c][0] | x2_insn[c][1] << 8);
            gen_slot[1] = (uint16_t)(x2_insn[c][2] | x2_insn[c][3] << 8);
            gen_slot[2] = 0x0000; /* nop */
            gen_slot[3] = 0x0080; /* rts */
            sync_cpu();
            for (unsigned k = 0; k < 16; ++k)
                st[k] = x2_sets[set][k];
            st[16] = 0;
            probe_trap.count = probe_trap.emu = 0;
            EMU_MSG = 0xffffffffu;
            sync_cpu();
            p_gen();
            for (unsigned k = 0; k < 17; ++k)
                res[20*n+k] = st[17+k];
            res[20*n+17] = probe_trap.count;
            res[20*n+18] = probe_trap.emu;
            res[20*n+19] = (uint32_t)x2_insn[c][0] | (uint32_t)x2_insn[c][1] << 8 | (uint32_t)x2_insn[c][2] << 16 |
                           (uint32_t)x2_insn[c][3] << 24;
            ++n;
        }
    app_log("x2: %u runs stored at 70000", n);
#elif GROUP == 14
    /* encodings only fm1-emu decodes; slot: insn (4 bytes, 2-byte ones padded with nop), r2 += 1, rts.
     * results at 0x01C70000 as group 13, plus 64 bytes of the scratch area after each run */
    volatile uint32_t *res = (volatile uint32_t *)0x01c70000u;
    static uint32_t st[34];
    gen_state = st;
    unsigned n = 0;
    for (unsigned c = 0; c < sizeof x14_insn/sizeof x14_insn[0]; ++c) {
        for (unsigned k = 0; k < 0x1000; k += 4)
            *(volatile uint32_t *)(0x01c72000u+k) = 0xa5a50000u | k;
        gen_slot[0] = (uint16_t)(x14_insn[c][0] | x14_insn[c][1] << 8);
        gen_slot[1] = (uint16_t)(x14_insn[c][2] | x14_insn[c][3] << 8);
        gen_slot[2] = 0x812a; /* r2 = r2 + 1 */
        gen_slot[3] = 0x0080; /* rts */
        sync_cpu();
        for (unsigned k = 0; k < 16; ++k)
            st[k] = x14_regs[k];
        st[16] = 0;
        probe_trap.count = probe_trap.emu = 0;
        EMU_MSG = 0xffffffffu;
        DBG_MSG_CLR = 0xffffffffu;
        sync_cpu();
        p_gen();
        for (unsigned k = 0; k < 17; ++k)
            res[40*n+k] = st[17+k];
        res[40*n+17] = probe_trap.count;
        res[40*n+18] = probe_trap.emu;
        res[40*n+19] = probe_trap.dbg;
        /* which scratch words changed: up to 10 (address, value) pairs */
        unsigned m = 0;
        for (unsigned k = 0; k < 0x1000 && m < 10; k += 4) {
            uint32_t v = *(volatile uint32_t *)(0x01c72000u+k);
            if (v != (0xa5a50000u | k)) {
                res[40*n+20+2*m] = 0x01c72000u+k;
                res[40*n+21+2*m] = v;
                ++m;
            }
        }
        for (; m < 10; ++m)
            res[40*n+20+2*m] = res[40*n+21+2*m] = 0;
        ++n;
    }
    app_log("x14: %u runs stored at 70000", n);
#elif GROUP == 15
    for (unsigned which = 0; which < 2; ++which)
        for (unsigned cond = 0; cond < 2; ++cond) {
            p_ifp(cond ? 5 : 5, cond ? 5 : 6, which);
            app_log("%s, condition %s: A %u, B stored %x, after %u, other part %u", which ? "pair in else" : "pair in then",
                    cond ? "true" : "false", (unsigned)probe_result[0], (unsigned)probe_result[1],
                    (unsigned)probe_result[2], (unsigned)probe_result[3]);
        }
#elif GROUP == 7
    uint32_t con = DBG_CON;
    app_log("DBG_CON %x, CKCNT %x", (unsigned)con, (unsigned)*(volatile uint32_t *)0x01eee218u);
    DBG_CON = con | 7u;
    sync_cpu();
    c_none(0, 3);
    uint32_t base = probe_result[0];
    app_log("empty: %u cycles", (unsigned)base);
    TIMED_RUN(c_nop);
    TIMED_RUN(c_add_dep);
    TIMED_RUN(c_add_indep);
    TIMED_RUN(c_mov32);
    TIMED_RUN(c_ld);
    TIMED_RUN(c_ld_use);
    TIMED_RUN(c_st);
    TIMED_RUN(c_mul);
    TIMED_RUN(c_div);
    TIMED_RUN(c_fadd);
    TIMED_RUN(c_fmul);
    TIMED_RUN(c_fdiv);
    TIMED_RUN(c_mul64);
    TIMED_RUN(c_goto);
    TIMED_RUN(c_br_nt);
    TIMED_RUN(c_br_t);
    TIMED_RUN(c_call);
    TIMED_RUN(c_push1);
    TIMED_RUN(c_ldd);
    DBG_CON = con;
    sync_cpu();
#endif
    VECTOR_1 = kit_vector;
    sync_cpu();
    return 0;
}
