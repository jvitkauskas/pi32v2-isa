# Hardware runs

What was run on the chip, in order. Every run has its own folder with a README (method, what was written to the
unit, results) and its raw results; the instruction table cites them as `hw/...` in its notes. The units: one
M-VAVE FM-1 (AC791N) throughout, and an SMK-37 Pro for the bootloader. Backups of the whole flash were taken
before every write and stay with the owner; no flash image, RAM dump or vendor firmware is in this repository.

## Instruction semantics (code run from RAM, nothing written to flash)

| Run | What it established |
| --- | --- |
| [fm1-2026-10-24](fm1-2026-10-24/README.md) | The harness on a real chip; ALU, logic, shifts, constants, moves and their flags. Analysis: [report-p](report-p.md), [report-q](report-q.md), [report-r](report-r.md), [report-s](report-s.md) |
| [fm1-2026-10-24-v2](fm1-2026-10-24-v2/README.md) | Memory, the stack, branches |
| [fm1-2026-10-24-v3](fm1-2026-10-24-v3/README.md) | `if (...) {` blocks, loops, table branches, parallel pairs (`#`) |
| [fm1-2026-10-24-v4](fm1-2026-10-24-v4/README.md) | Control flow, returns, special-register writes |
| [fm1-2026-10-24-v5](fm1-2026-10-24-v5/README.md) | Return selection, block aliases, handlers in RAM. Analysis: [report5-b](report5-b.md), [report5-d](report5-d.md), [report5-k](report5-k.md), [report5-m](report5-m.md) |

## The chip as a system (test applications installed in the application area)

| Run | What it established |
| --- | --- |
| [fm1-2026-10-24-app](fm1-2026-10-24-app/README.md) | What survives a reset in RAM; the application harness |
| [fm1-2026-10-24-app2](fm1-2026-10-24-app2/README.md) | Exception and interrupt handlers, the watchdog, interrupt delivery |
| [fm1-2026-10-24-app3](fm1-2026-10-24-app3/README.md) | Waits, nested software interrupts, starting the second core |
| [fm1-2026-10-24-app4](fm1-2026-10-24-app4/README.md) | The second core's boot, events, shared memory ([docs/CPU1.md](../docs/CPU1.md)) |

## The open toolchain

| Run | What it established |
| --- | --- |
| [fm1-2026-10-25-blink](fm1-2026-10-25-blink/README.md) | An application from clang and `ld.lld` alone: start-up code, a timer interrupt in C |
| [fm1-2026-10-25-cgtest](fm1-2026-10-25-cgtest/README.md) | The LLVM code generator's first code on the chip |
| [fm1-2026-10-25-ctest](fm1-2026-10-25-ctest/README.md) | C from the LLVM target's clang, with compiler-rt |
| [fm1-2026-10-25-ctest2](fm1-2026-10-25-ctest2/README.md) | The size-tuned code generator and the hardware FPU, at -O2 and -Os |
| [fm1-2026-10-25-open-firmware](fm1-2026-10-25-open-firmware/README.md) | m-bootloader 1.2 (FM-1 and SMK-37 Pro) and fm1-base built with the LLVM toolchain |
| [fm1-2026-10-25-felucca](fm1-2026-10-25-felucca/README.md) | Felucca and SLOOP built with the LLVM toolchain; the if-block fault it found (a call inside a block) and its fix; the code-size changes |
| [fm1-2026-10-25-rust](fm1-2026-10-25-rust/README.md) | Rust: an interrupt-driven blink and a picture on the screen, from rustc with the pi32v2 patch on the fork's LLVM |
