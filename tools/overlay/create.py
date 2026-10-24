#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Julius Vitkauskas
# SPDX-License-Identifier: MIT-0
"""Create a local toolchain overlay; no vendor code or executables are copied."""
import argparse
import json
import os
from pathlib import Path
import shutil


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('output', type=Path, help='new overlay directory (must not exist)')
    p.add_argument('--toolchain', type=Path, default=os.environ.get('PI32V2_TOOLCHAIN'),
                   help='JieLi root; defaults to PI32V2_TOOLCHAIN')
    p.add_argument('--repo', type=Path, required=True, help='pi32v2-isa checkout')
    p.add_argument('--objcopy', default='objcopy', help='GNU objcopy executable')
    p.add_argument('--objdump', help='replacement executable (default: JieLi)')
    p.add_argument('--ld', help='replacement executable (default: JieLi)')
    p.add_argument('--lto-wrapper', help='replacement executable (default: JieLi)')
    p.add_argument('--llvmgold', type=Path, help='replacement LLVMgold.so')
    p.add_argument('--open', action='store_true',
                   help="use this repository's linker and objdump too (python3 -m pi32v2isa ld / objdump)")
    a = p.parse_args()
    if a.toolchain is None:
        p.error('--toolchain or PI32V2_TOOLCHAIN is required')
    stock, repo, out = a.toolchain.resolve(), a.repo.resolve(), a.output.absolute()
    if not (stock / 'common/bin/clang').is_file() or not (repo / 'pi32v2isa/asm.py').is_file():
        p.error('toolchain or repository path is invalid')
    commands = {'clang': str(stock / 'common/bin/clang')}
    out.mkdir(parents=True, exist_ok=False)
    if a.open:      # small wrappers that run the repository's own tools
        tools = out / 'open'
        tools.mkdir()
        for name, sub in (('ld', 'ld'), ('objdump', 'objdump')):
            if getattr(a, name):
                p.error(f'--open and --{name} are exclusive')
            w = tools / name
            w.write_text(f'#!/bin/sh\nPYTHONPATH={repo} exec python3 -m pi32v2isa {sub} "$@"\n')
            w.chmod(0o755)
            setattr(a, name, str(w))
    for name, supplied, default in (
        ('objcopy', a.objcopy, 'objcopy'),
        ('objdump', a.objdump, str(stock / 'common/bin/objdump')),
        ('ld', a.ld, str(stock / 'pi32v2/bin/ld')),
        ('lto-wrapper', a.lto_wrapper, str(stock / 'pi32v2/bin/lto-wrapper')),
    ):
        executable = shutil.which(supplied or default)
        if executable is None:
            p.error(f'executable not found: {supplied or default}')
        commands[name] = str(Path(executable).absolute())
    gold = (a.llvmgold or stock / 'pi32v2/bin/LLVMgold.so').resolve()
    if not gold.is_file():
        p.error(f'plugin not found: {gold}')
    shutil.copyfile(Path(__file__).with_name('dispatch.py'), out / 'dispatch.py')
    (out / 'dispatch.py').chmod(0o755)
    (out / 'overlay.json').write_text(json.dumps({'repo': str(repo), 'commands': commands}, indent=2) + '\n')
    for directory in ('common/bin', 'pi32v2/bin'):
        dest = out / directory
        dest.mkdir(parents=True)
        for name in commands:
            (dest / name).symlink_to('../../dispatch.py')
        (dest / 'LLVMgold.so').symlink_to(gold)
    print(out)


if __name__ == '__main__':
    main()
