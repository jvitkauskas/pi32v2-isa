/* SPDX-FileCopyrightText: 2026 Julius Vitkauskas */
/* SPDX-License-Identifier: MIT */
/* Boot probe (../README.md): installed as the application in flash, started by whichever
 * bootloader is installed. crt0.S has recorded the registers at entry; this adds the memory and registers the
 * loader left, times instruction blocks running from flash (XIP) cold and warm, and asks for download mode.
 * The host reads REC .. REC+0x800 back with a run-ram reader.
 *
 * REC layout (bytes):
 *   +0 "BRPB"  +4 starts  +8 r0..r15  +72 sp ssp usp psr icfg rets reti rete retx  +108 cycle counter at entry
 *   +112 EMU_CON +116 EMU_MSG +120 DBG_MSG +124 DBG_EN
 *   +0x100 0x01C7FD80..0x01C7FE80 (retained area, vectors 0..23, boot object, flash header copy)
 *   +0x200 64 bytes at r0 (when r0 is in RAM)
 *   +0x240 clock 0x10000..0x1003F   +0x280 SFC 0x40200..0x4020F   +0x290 SFCENC 0x40300..0x40317
 *   +0x2C0 ANA 0x11900..0x119FF   +0x3C0 corex2 0x1EEE000..0x1EEE01F   +0x3E0 0x1EEE340..0x1EEE35F
 *   +0x400 timing: per block, cold then warm cycles (C0_TL_CKCNTL), 256 copies each
 *   +0x600 PC limits 0x1EEE380..0x1EEE38F */
#include <stdint.h>
#define REC 0x01C7C000u
#define W(a) (*(volatile uint32_t *)(uintptr_t)(a))

#define TIMED(name, setup, insn) \
    ".section .text." #name ",\"ax\",@progbits\n" \
    ".globl " #name "\n" \
    #name ":\n" \
    "  [--sp] = {rets, r15-r4}\n" \
    "  r4 = 3\n  r5 = 5\n  r6 = 7\n  r7 = 3\n  r9 = r0\n" \
    setup \
    "  r12 = 0x01EEE218\n" \
    "  csync\n" \
    "  r13 = [r12+0]\n" \
    "  .rept 256\n" \
    "  " insn "\n" \
    "  .endr\n" \
    "  r14 = [r12+0]\n" \
    "  r0 = r14 - r13\n" \
    "  {pc, r15-r4} = [sp++]\n"

__asm__(
    TIMED(x_none, "", "")
    TIMED(x_nop, "", "nop")
    TIMED(x_add_dep, "", "r4 = r4 + 1")
    TIMED(x_add_indep, "", "r4 = r5 + r6\n  r10 = r5 + r6")
    TIMED(x_mov32, "", "r4 = 0x12345678")
    TIMED(x_ld, "", "r4 = [r9+0]")
    TIMED(x_ld_use, "", "r4 = [r9+0]\n  r5 = r4 + 1")
    TIMED(x_st, "", "[r9+0] = r4")
    TIMED(x_mul, "", "r4 = r5 * r6")
    TIMED(x_div, "", "r4 = r5 / r7 (s)")
    TIMED(x_fadd, "  r5 = 0x3f800000\n  r6 = 0x40000000\n", "r4 = r5 + r6 (f)")
    TIMED(x_fdiv, "  r5 = 0x3f800000\n  r6 = 0x40000000\n", "r4 = r5 / r6 (f)")
    TIMED(x_goto, "", "goto 1f\n  1:")
    TIMED(x_br_nt, "", "if (r4 == 0) goto 1f\n  1:")
    TIMED(x_br_t, "", "if (r4 != 0) goto 1f\n  1:")
    TIMED(x_call, "", "call 2f\n  goto 3f\n  2: rts\n  3:")
    TIMED(x_ldx, "", "r4 = [r9+0]"));

typedef uint32_t timed_fn(uint32_t);
extern timed_fn x_none, x_nop, x_add_dep, x_add_indep, x_mov32, x_ld, x_ld_use, x_st, x_mul, x_div, x_fadd, x_fdiv,
    x_goto, x_br_nt, x_br_t, x_call, x_ldx;
static timed_fn *const blocks[] = {x_none, x_nop, x_add_dep, x_add_indep, x_mov32, x_ld, x_ld_use, x_st, x_mul,
                                   x_div, x_fadd, x_fdiv, x_goto, x_br_nt, x_br_t, x_call, x_ldx};
static volatile uint32_t word;
static const uint32_t xip_word = 1;

static void copy(uint32_t to, uint32_t from, uint32_t bytes) {
    for (uint32_t i = 0; i < bytes; i += 4)
        W(to+i) = W(from+i);
}

int main(void) {
    W(REC+4) = W(REC+4)+1;
    W(REC+112) = W(0x01EEF0D0u);
    W(REC+116) = W(0x01EEF0D4u);
    W(REC+120) = W(0x01EEE244u);
    W(REC+124) = W(0x01EEE340u);
    copy(REC+0x100, 0x01C7FD80u, 0x100);
    uint32_t r0 = W(REC+8);
    if (r0 >= 0x01C00000u && r0 < 0x01C80000u-0x40)
        copy(REC+0x200, r0 & ~3u, 0x40);
    copy(REC+0x240, 0x10000u, 0x40);
    copy(REC+0x280, 0x40200u, 0x10);
    copy(REC+0x290, 0x40300u, 0x18);
    copy(REC+0x2C0, 0x11900u, 0x100);
    copy(REC+0x3C0, 0x1EEE000u, 0x20);
    copy(REC+0x3E0, 0x1EEE340u, 0x20);
    copy(REC+0x600, 0x1EEE380u, 0x10);
    /* the cycle counter only counts with DBG_CON bits 0..2 set in this context */
    uint32_t dbg_con = W(0x1EEE344u);
    W(0x1EEE344u) = dbg_con | 7u;
    __asm__ volatile("csync");
    for (unsigned i = 0; i < sizeof blocks/sizeof blocks[0]; ++i) {
        uint32_t a = i == 16 ? (uint32_t)(uintptr_t)&xip_word : (uint32_t)(uintptr_t)&word;
        W(REC+0x400+8*i) = blocks[i](a);
        W(REC+0x404+8*i) = blocks[i](a);
    }
    /* download mode at the next reset: "usb_update_mode" + NUL at 0x01C7FD80, then a software reset */
    W(0x1EEE344u) = dbg_con;
    W(0x01C7FD80u) = 0x5f627375u;
    W(0x01C7FD84u) = 0x61647075u;
    W(0x01C7FD88u) = 0x6d5f6574u;
    W(0x01C7FD8Cu) = 0x0065646fu;
    __asm__ volatile("csync");
    W(0x10000u) |= 0x10u;
    for (;;)
        ;
}
