# Sources

Every entry in the instruction table names its sources by the ids below. Facts may be taken from any of them;
wording, tables, code and figures may not (see [AGENTS.md](../AGENTS.md)).

| id | Source | Licence | Notes |
| --- | --- | --- | --- |
| `kagaimiq-jielie` | kagaimiq, *jielie*: [pi32v2 notes](https://kagaimiq.github.io/jielie/cpu/pi32v2.html) ([repo](https://github.com/kagaimiq/jielie)) | none stated | Register model and an opcode-bit table for many 16-bit and some 32/48-bit instructions. No licence, so facts only. |
| `kagaimiq-ghidra` | Andrey Grigoryev (kagaimiq), [ghidra-jieli](https://github.com/kagaimiq/ghidra-jieli) | Apache-2.0 | Ghidra SLEIGH module; pi32v2 marked "very early stage". |
| `virtualabs-ghidra` | Damien Cauquil (virtualabs, Quarkslab), [ghidra-jieli fork](https://github.com/virtualabs/ghidra-jieli) | Apache-2.0 | Extends kagaimiq's module with group 6/7 instructions, parallel execution and if/then/else blocks. |
| `sstic2026` | D. Cauquil, *Rétro-ingénierie d'un micrologiciel pour architecture Pi32v2*, [SSTIC 2026](https://www.sstic.org/media/SSTIC2026/SSTIC-actes/retro-ingenierie-micrologiciel-pi32v2/SSTIC2026-Article-retro-ingenierie-micrologiciel-pi32v2-cauquil.pdf) ([slides](https://www.sstic.org/media/SSTIC2026/SSTIC-actes/retro-ingenierie-micrologiciel-pi32v2/SSTIC2026-Slides-retro-ingenierie-micrologiciel-pi32v2-cauquil.pdf)) | none stated | Method and instruction formats; states some instructions are not fully determined. Cite, do not quote. |
| `oracle` | Black-box observation of JieLi's toolchain ([ORACLE.md](ORACLE.md)) | n/a | Each observation is recorded as an example on the entry, with the toolchain version. |
| `compiler` | Black-box observation of which instructions JieLi's clang emits for C code (`oracle cc`) | n/a | Evidence of meaning and of the ABI; record the C, the flags and the instructions in the entry's notes or the doc. |
| `m-bootloader-spec` | Julius Vitkauskas, [m-bootloader SPEC.md](https://github.com/jvitkauskas/m-bootloader/blob/main/docs/SPEC.md) | MIT | Calling-convention and boot facts established while writing the bootloader. |
| `sources-in-use` | Assembly in open FM-1 projects: m-bootloader (MIT), Felucca (GPL-3.0), fm1-base (MPL-2.0) | see project | Shows which syntax and instructions real code needs; not evidence of encodings. |
| `ac79-sdk` | JieLi AC79 AIoT SDK C headers, local checkout `/tmp/jl_sdk/fw-AC79_AIoT_SDK` | Apache-2.0 | Header attribute conventions only: `include_lib/driver/cpu/wl82/asm/irq.h`, `include_lib/btctrler/adapter/include/interrupt.h`, `include_lib/system/generic/typedef.h`. Independently probed with `compiler`; no SDK libraries inspected or SDK code copied. |
