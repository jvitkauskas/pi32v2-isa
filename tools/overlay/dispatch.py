#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Julius Vitkauskas
# SPDX-License-Identifier: MIT-0
"""Dispatch overlay tools. Only clang compilation changes; linking stays explicit."""
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import struct
import sys
import tempfile


class OverlayError(Exception):
    pass


def record(kind, **details):
    path = os.environ.get('PI32V2_OVERLAY_LOG')
    if path:
        data = (json.dumps(dict(kind=kind, cwd=os.getcwd(), **details)) + '\n').encode()
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
        try:
            os.write(fd, data)
        finally:
            os.close(fd)


def run(command, **kwargs):
    result = subprocess.run(command, **kwargs)
    if result.returncode:
        raise SystemExit(result.returncode)


def expand_response(args, depth=0):
    if depth > 16:
        raise OverlayError('response files nested too deeply')
    result = []
    for arg in args:
        result.extend(expand_response(shlex.split(Path(arg[1:]).read_text()), depth + 1)
                      if arg.startswith('@') else [arg])
    return result


def compile_object(config, original):
    args = expand_response(original)
    clang = config['commands']['clang']
    lto = False
    for arg in args:
        if arg == '-fno-lto':
            lto = False
        elif arg == '-flto' or arg.startswith('-flto='):
            lto = True
    if lto or '-c' not in args or any(f in args for f in ('-E', '-S', '-emit-llvm', '-###', '--version')):
        record('passthrough', lto=lto, args=original)
        if lto:
            print('pi32v2 overlay: LTO passes through to JieLi (bitcode bypasses the open assembler)', file=sys.stderr)
        os.execv(clang, [clang, *original])
    # Keep flag values distinct from source names; do not mistake -include x.c for an input.
    values = {'-o', '-x', '-target', '--target', '-mcpu', '-I', '-D', '-U', '-isystem', '-iquote',
              '-idirafter', '-include', '-imacros', '-isysroot', '--sysroot', '-MF', '-MT', '-MQ',
              '-Xclang', '-Xassembler', '-mllvm', '-resource-dir', '-B'}
    inputs, rest, includes, cpp_flags = [], [], [], []
    output, language = None, None
    i = 0
    while i < len(args):
        arg = args[i]
        if arg in values:
            if i + 1 == len(args):
                raise OverlayError(f'missing argument after {arg}')
            value = args[i + 1]
            if arg == '-o':
                output = value
            else:
                rest.extend((arg, value))
            if arg == '-x':
                language = value
            if arg == '-I':
                includes.append(value)
            if arg in {'-I', '-D', '-U', '-isystem', '-iquote', '-idirafter', '-include', '-imacros'}:
                cpp_flags.extend((arg, value))
            i += 2
            continue
        if arg.startswith('-o') and len(arg) > 2:
            output = arg[2:]
        elif not arg.startswith('-'):
            inputs.append(arg)
        elif arg != '-c':
            rest.append(arg)
            if arg.startswith(('-I', '-D', '-U')):
                cpp_flags.append(arg)
                if arg.startswith('-I'):
                    includes.append(arg[2:])
            elif arg in ('-nostdinc', '-undef', '-pthread'):
                cpp_flags.append(arg)
        i += 1
    if len(inputs) != 1:
        raise OverlayError('open assembly requires exactly one input per -c invocation')
    source = inputs[0]
    suffix = Path(source).suffix
    output = output or Path(source).stem + '.o'
    if suffix not in ('.c', '.s', '.S', '.ll', '.bc') and language not in ('c', 'assembler', 'assembler-with-cpp', 'ir'):
        raise OverlayError(f'unsupported input: {source}; use -E/-S for explicit compiler passthrough')
    env = dict(os.environ)
    env['PYTHONPATH'] = config['repo'] + os.pathsep + env.get('PYTHONPATH', '')
    with tempfile.TemporaryDirectory(prefix='pi32v2-overlay-') as tmp:
        assembly = Path(tmp) / 'input.s'
        if suffix == '.S' or language == 'assembler-with-cpp':
            with assembly.open('w') as stream:
                run(['cpp', '-P', '-x', 'assembler-with-cpp', *cpp_flags, source], stdout=stream)
            kind = 'cpp-as'
        elif suffix == '.s' or language == 'assembler':
            shutil.copyfile(source, assembly)
            kind = 'as'
        else:
            # Preserve dependency files and their original object target despite the temporary -o.
            if any(f in args for f in ('-MD', '-MMD')):
                if '-MF' not in args and not any(a.startswith('-MF') for a in args):
                    rest += ['-MF', str(Path(output).with_suffix('.d'))]
                if not any(a.startswith(('-MT', '-MQ')) for a in args):
                    rest += ['-MT', output]
            run([clang, *rest, '-S', source, '-o', str(assembly)])
            kind = 'cc-as'
        saved = None
        if os.environ.get('PI32V2_OVERLAY_SAVE_ASM'):
            root = Path(os.environ['PI32V2_OVERLAY_SAVE_ASM'])
            obj = Path(output).absolute()
            # Normal build outputs retain their relative directory; external ones use a path hash.
            try:
                relative = obj.relative_to(Path.cwd())
            except ValueError:
                relative = Path(hashlib.sha256(str(obj).encode()).hexdigest()[:16]) / obj.name
            saved = root / relative.with_suffix('.s')
            saved.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(assembly, saved)
        command = ['python3', '-m', 'pi32v2isa', 'as', str(assembly), '-o', output]
        for directory in [str(Path(source).absolute().parent), *includes]:
            command += ['-I', directory]
        record(kind, source=source, output=output, assembly=str(saved) if saved else None, args=original)
        run(command, env=env)


def copy_binary(executable, args):
    """GNU BFD refuses JieLi's non-power-of-two segment alignment (0x500).

    Binary extraction needs addresses and contents, not segment alignment. Fix
    only invalid p_align fields in a temporary input; retain the actual ELF.
    """
    binary = any(args[i:i + 2] == ['-O', 'binary'] for i in range(len(args))) or '--output-target=binary' in args
    if not binary:
        os.execv(executable, [executable, '-I', 'elf32-little', *args])
    # Parse objcopy's option operands so an existing file named by -j/-O is
    # never mistaken for the input. Unknown option forms go to GNU unchanged.
    operands = {'-I', '-O', '-B', '-F', '-j', '-R', '-N', '-K', '-L', '-G', '-W',
                '--input-target', '--output-target', '--binary-architecture', '--target',
                '--only-section', '--remove-section', '--strip-symbol', '--keep-symbol',
                '--localize-symbol', '--globalize-symbol', '--weaken-symbol',
                '--set-section-alignment', '--set-section-flags', '--rename-section',
                '--change-addresses', '--change-section-address', '--change-section-lma',
                '--change-section-vma', '--gap-fill', '--pad-to'}
    positionals, skip = [], False
    for i, arg in enumerate(args):
        if skip:
            skip = False
        elif arg in operands:
            skip = True
        elif not arg.startswith('-'):
            positionals.append(i)
    if len(positionals) != 2:
        os.execv(executable, [executable, '-I', 'elf32-little', *args])
    index = positionals[0]
    data = bytearray(Path(args[index]).read_bytes())
    changed = 0
    if data[:6] == b'\x7fELF\x01\x01' and len(data) >= 52:
        offset = struct.unpack_from('<I', data, 28)[0]
        size, count = struct.unpack_from('<HH', data, 42)
        if size >= 32 and offset + size * count <= len(data):
            for n in range(count):
                at = offset + size * n + 28
                align = struct.unpack_from('<I', data, at)[0]
                if align and align & (align - 1):
                    struct.pack_into('<I', data, at, 1)
                    changed += 1
    if not changed:
        os.execv(executable, [executable, '-I', 'elf32-little', *args])
    with tempfile.TemporaryDirectory(prefix='pi32v2-objcopy-') as tmp:
        path = Path(tmp) / 'input.elf'
        path.write_bytes(data)
        args = list(args)
        original = args[index]
        args[index] = str(path)
        record('objcopy-alignment', source=original, segments=changed)
        run([executable, '-I', 'elf32-little', *args])


def main():
    config = json.loads(Path(__file__).resolve().with_name('overlay.json').read_text())
    tool = Path(sys.argv[0]).name
    args = sys.argv[1:]
    if tool == 'clang':
        compile_object(config, args)
        return
    executable = config['commands'][tool]
    if tool == 'objcopy':
        record(tool, args=['-I', 'elf32-little', *args])
        copy_binary(executable, args)
        return
    record(tool, args=args)
    os.execv(executable, [executable, *args])


if __name__ == '__main__':
    try:
        main()
    except (OverlayError, OSError) as error:
        print(f'pi32v2 overlay: {error}', file=sys.stderr)
        sys.exit(1)
