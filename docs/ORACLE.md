# The oracle

JieLi's Linux toolchain is freely downloadable and can assemble and disassemble pi32v2. It is used here as a
black box: give it input, record its output, and compare that with what this repo's table says.

## Toolchain versions

| Release | SHA-256 of the `.tar.xz` | Notes |
| --- | --- | --- |
| `20250324.1` | `f686586bcfb45e0f0bb27fd2b39c7a7f313cb4f0e88a66a14da621ffa8225958` | used by m-bootloader |
| `20260730.1` | `a1545cddbc451a06bac43eb5cd96d831470c42a97c5c0b1f98879a20fc7647bd` | current as of 2026-10; rebuilt `clang`, `LLVMgold.so`, `objdump`, `objcopy` and `llvm-read-version`, everything else identical |

Download from `https://jl-update.oss-cn-shenzhen.aliyuncs.com/jieli-linux-toolchains-<release>.tar.xz`
(`https://pkgman.jieliapp.com/s/linux-toolchain` redirects to the current one). Unpack it outside this repo, or
under `oracle/`, which git ignores. Never commit it.

## Two directions

- **Decode:** put the bytes in an object file (assemble a `.short 0x0080` style listing with the toolchain's
  clang) and run `common/bin/objdump -d -mcpu=r3` on it. The printed text is what the bytes mean to JieLi's
  disassembler.
- **Encode:** assemble text with `common/bin/clang -target pi32v2 -mcpu=r3 -c` (add `-mfprev1` for FPU
  instructions) and read the bytes back.

Both are needed: the disassembler may print the same text for different encodings, and the assembler may
pick one encoding of several.

## Recording an observation

Add an example to the entry (see [TABLE-FORMAT.md](TABLE-FORMAT.md)):

```toml
[[insn.example]]
bytes = "80 00"
text = "rts"
origin = "oracle:objdump:20260730.1"
```

An entry becomes `confirmed` when its examples cover every field of its encoding (each field at least at
two values, including its extremes where that matters).

## Rules

- Black box only: inputs and outputs. Do not extract tables or strings from the toolchain's binaries.
- The oracle can be wrong or inconsistent (the SSTIC paper reports such cases). When it is, record what it
  did and say so in the entry's `notes`.
