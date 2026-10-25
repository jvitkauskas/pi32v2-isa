# SPDX-FileCopyrightText: 2026 Julius Vitkauskas
# SPDX-License-Identifier: MIT-0
"""What the LLVM code generator must know about the table forms it uses (gen_td.py adds it to the records).

Every other instruction keeps the defaults of PI32V2InstrFormats.td (has side effects, no memory access): only
the assembler and disassembler use those. The table says what the syntax is; this says what LLVM's passes need
to move, delete or schedule an instruction. psr (N Z C V) is clobbered by every ALU form listed here, which is
what the hardware runs showed for the arithmetic ones (docs/COMPILER.md) and safe for the rest.
"""

ALU = """add.rrr.l sub.rrr.l and.rrr or.rrr xor.rrr lsl.rrr lsr.rrr asr.rrr lsl.rri.l lsr.rri.l asr.rri.l mul.rrr
div.u.rrr div.s.rrr add.s14.rri and.modimm.rri or.modimm.rri xor.modimm.rri sub.modimm.rri add.modimm.rri
rsub.modimm.rri mul.u.prr mul.s.prr mul.modimm.rri clz.rr rev8.rr ror.rri ror.rrr uextra.rrii sextra.rrii""".split()
MOVES = "mov.rr mov.pair li.s16 li.u32 li.modimm add.r_sp_i.l".split()
LOADS = "ld.w.l ld.bu.l ld.bs.l ld.hu.l ld.hs.l ld.w.sp.l ld.bu.sp.l ld.bs.sp.l ld.hu.sp.l ld.hs.sp.l".split()
STORES = "st.w.l st.b.l st.h.l st.w.sp.l st.b.sp.l st.h.sp.l".split()
BRANCHES = [f"{c}.{k}{l}" for c in ("beq", "bne", "bge", "blt", "bgt", "ble", "bges", "blts", "bgts", "bles")
            for k in ("rr", "ri") for l in ("", ".l")]
# float compares (iff): the ten conditions the hardware runs confirmed, in both lengths (bfne, bfueq, bfuno and
# bford reset the unit, docs/ISA.md); psr is unchanged
BRANCHES += [f"bf{c}.rr{l}" for c in ("eq", "une", "uge", "lt", "ugt", "le", "ge", "ult", "gt", "ule")
             for l in ("", ".l")]
# float arithmetic and conversions in general registers: psr survives (hardware runs)
FLOAT = "add.f.rrr sub.f.rrr mul.f.rrr div.f.rrr itof.rr utof.rr ftoi.trunc.rr ftou.trunc.rr".split()


def flags():
    """{table id: [TableGen let statements]}"""
    out = {}
    for i in ALU:
        out[i] = ["let hasSideEffects = 0;", "let Defs = [PSR];"]
    out["addc.rrr"] = ["let hasSideEffects = 0;", "let Defs = [PSR];", "let Uses = [PSR];"]
    out["subc.rrr"] = ["let hasSideEffects = 0;", "let Defs = [PSR];", "let Uses = [PSR];"]
    for i in FLOAT:
        out[i] = ["let hasSideEffects = 0;"]
    for i in MOVES:
        out[i] = ["let hasSideEffects = 0;", "let isMoveImm = 1;" if i.startswith("li.") else
                  "let isMoveReg = 1;" if i.startswith("mov.") else "let Uses = [SP];"]
    out["li.s16"] += ["let isReMaterializable = 1;", "let isAsCheapAsAMove = 1;"]
    for i in LOADS:
        out[i] = ["let hasSideEffects = 0;", "let mayLoad = 1;"] + (["let Uses = [SP];"] if ".sp." in i else [])
    for i in STORES:
        out[i] = ["let hasSideEffects = 0;", "let mayStore = 1;"] + (["let Uses = [SP];"] if ".sp." in i else [])
    for i in BRANCHES:
        out[i] = ["let hasSideEffects = 0;", "let isBranch = 1;", "let isTerminator = 1;"]
    for i in ("goto.s", "goto.l"):
        out[i] = ["let hasSideEffects = 0;", "let isBranch = 1;", "let isTerminator = 1;", "let isBarrier = 1;"]
    out["goto.r"] = ["let isBranch = 1;", "let isIndirectBranch = 1;", "let isTerminator = 1;",
                     "let isBarrier = 1;"]
    for i in ("call.s", "call.l", "call.r"):
        out[i] = ["let isCall = 1;", "let Defs = [RETS];", "let Uses = [SP];"]
    out["rts"] = ["let isReturn = 1;", "let isTerminator = 1;", "let isBarrier = 1;", "let Uses = [RETS];"]
    out["pop.pc_rmask"] = ["let isReturn = 1;", "let isTerminator = 1;", "let isBarrier = 1;", "let mayLoad = 1;",
                           "let Uses = [SP];", "let Defs = [SP];"]
    out["push.rets_rmask"] = ["let mayStore = 1;", "let Uses = [SP, RETS];", "let Defs = [SP];"]
    out["push.rmask"] = ["let mayStore = 1;", "let Uses = [SP];", "let Defs = [SP];"]
    out["pop.rmask"] = ["let mayLoad = 1;", "let Uses = [SP];", "let Defs = [SP];"]
    out["pop.rets_rmask"] = ["let mayLoad = 1;", "let Uses = [SP];", "let Defs = [SP, RETS];"]
    out["push.srl"] = ["let mayStore = 1;", "let Uses = [SP, PSR, RETI];", "let Defs = [SP];"]
    out["pop.srl"] = ["let mayLoad = 1;", "let Uses = [SP];", "let Defs = [SP, PSR, RETI];"]
    out["add.sp_i.l"] = ["let Uses = [SP];", "let Defs = [SP];"]
    out["add.sp_i"] = ["let Uses = [SP];", "let Defs = [SP];"]
    return out
