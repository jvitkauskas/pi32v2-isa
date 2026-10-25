#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Julius Vitkauskas
# SPDX-License-Identifier: MIT-0
"""Write the app4 two-core case files with this repository's assembler; no device access."""
import json
from pathlib import Path
from app3cases import parts,delay,case
HERE=Path(__file__).resolve().parents[2]/'hw/fm1-2026-10-24-app4'


def write(name,cases):
    (HERE/(name+'.json')).write_text(json.dumps(cases,indent=2)+'\n')


def post(cmd,arg=0,gates=0,payload=0):
    return f'''r7 = 0x1c7ce00
r0 = {cmd}
[r7+4] = r0
r0 = {arg}
[r7+8] = r0
r0 = {gates}
[r7+12] = r0
r0 = {payload}
[r7+24] = r0
r4 = [r7+0]
r4 = r4 + 1
csync
[r7+0] = r4
csync
'''


def wait_ack():
    return '''r0 = 1000000
1:
csync
r1 = [r7+36]
if (r1 == r4) goto 2f
r0 = r0 + -1
if (r0 != 0) goto 1b
2:
'''


def wait_phase():
    return '''r0 = 1000000
1:
csync
r1 = [r7+92]
if (r1 != r4) goto 3f
r1 = [r7+64]
if (r1 != 0) goto 2f
3:
r0 = r0 + -1
if (r0 != 0) goto 1b
2:
'''


def lifecycle():
    calibration = [case('csync', model='app4.preservation') for _ in range(9)]
    for name in ('lifecycle','boot-starts','boot-verified','persistent-cycles'):
        write(name,calibration)
    write('hold-diagnostic',calibration[:2])


def events():
    cs=[]
    for cmd,n,gates in [(5,1,0),(5,1,0x100),(5,1,0x200),(5,1,0x300),
                         (6,1,0),(7,1,0),(8,127,0),(8,127,0x300)]:
        before=post(cmd,n,gates)
        after=wait_ack()+'''r8 = [r7+32]
r9 = [r7+40]
r10 = [r7+68]
r11 = [r7+72]
r12 = [r7+88]
r13 = [r7+64]
r14 = [r7+36]
r15 = [r7+0]
'''
        cs.append(case('csync',before,after,model='app4.peer-event'))
    write('peer-waits',cs)
    cs=[]
    for id in ('csync','sevl','sevg','wfe'):
        before=post(8,127,0)+wait_ack()+'r8 = [r7+36]\n'+post(8,127,0)
        after=wait_ack()+'''r9 = [r7+36]
r10 = [r7+68]
r11 = [r7+72]
r12 = [r7+88]
r13 = [r7+64]
r14 = [r7+36]
r15 = [r7+0]
'''
        cs.append(case(id,before,after,model='app4.peer-event'))
    for event in ('','sevl','sevg'):
        before=post(4,1000000)+'''r6 = 0x10804
r8 = [r6+0]
csync
'''
        after='csync\nr9 = [r6+0]\nwfe\ncsync\nr10 = [r6+0]\nr11 = [r7+64]\n'+wait_ack()+'''r12 = [r7+68]
r13 = [r7+72]
r14 = [r7+36]
r15 = [r7+0]
'''
        cs.append(case('wfe',event+'\n'+before,after,model='app4.peer-event'))
    write('cross-events',cs)


def locks():
    cs=[]
    for locked in (False,True):
        before=post(10)+wait_phase()+'r0 = 0\n[r7+128] = r0'
        after='r0 = 1\n[r7+128] = r0\ncsync\n[r7+20] = r4\n'+delay(10000)+'''r8 = [r7+64]
r0 = 0
[r7+128] = r0
csync
'''+('lockclr\n' if locked else '')+wait_ack()+'''r9 = [r7+64]
r10 = [r7+80]
r14 = [r7+36]
r15 = [r7+0]
'''
        cs.append(case('lockset' if locked else 'csync',before,after,model='app4.lock'))
    for locked in (False,True,True):
        before=post(11,1000,int(locked))+wait_phase()+'''r0 = 0
[r7+128] = r0
csync
'''
        body='[r7+20] = r4\nr8 = 1000\n3:\n'+('lockset\ncsync\n' if locked else '')+'''r2 = [r7+128]
nop
nop
nop
nop
r2 = r2 + 1
[r7+128] = r2
'''+('csync\nlockclr\n' if locked else '')+'''r8 = r8 + -1
if (r8 != 0) goto 3b
'''+wait_ack()+'''r9 = [r7+128]
r10 = [r7+64]
r14 = [r7+36]
r15 = [r7+0]
'''
        cs.append(case('csync',before,body,model='app4.lock'))
    write('locks',cs)


def barriers():
    cs=[]
    for fence in (False,True):
        before='r7 = 0x1c7ce00\nr0 = 0\n[r7+160] = r0\n[r7+20] = r0\n'+post(12,1000,int(fence))+wait_phase()
        after='[r7+20] = r4\nr8 = 1\nr9 = 1000\n4:\n[r7+128] = r8\n'+('csync\n' if fence else '')+'''[r7+160] = r8
5:
csync
r1 = [r7+84]
if (r1 != r8) goto 5b
r8 = r8 + 1
if (r8 <= r9) goto 4b
'''+wait_ack()+'''r10 = [r7+80]
r11 = [r7+84]
r12 = [r7+64]
r14 = [r7+36]
r15 = [r7+0]
'''
        cs.append(case('csync',before,after,model='app4.ordering'))
    for fence in (False,True):
        before='r7 = 0x1c7ce00\nr0 = 0\n[r7+20] = r0\n'+post(13,1000,int(fence))+wait_phase()
        after='r8 = 1\nr9 = 1000\nr10 = 0\n4:\ncsync\nr1 = [r7+64]\nif (r1 != r8) goto 4b\nr0 = 0\n[r7+128] = r0\n[r7+160] = r0\ncsync\n[r7+20] = r8\ncsync\nr0 = 1\n[r7+128] = r0\n'+('csync\n' if fence else '')+'''r11 = [r7+160]
5:
csync
r1 = [r7+84]
if (r1 != r8) goto 5b
r12 = [r7+80]
if (r11 != 0) goto 6f
if (r12 != 0) goto 6f
r10 = r10 + 1
6:
r8 = r8 + 1
if (r8 <= r9) goto 4b
'''+wait_ack()+'''r9 = [r7+84]
r14 = [r7+36]
r15 = [r7+0]
'''
        cs.append(case('csync',before,after,model='app4.ordering'))
    write('ordering',cs)


def idle_events():
    for event in range(3):

        before='''cli
    r6 = 0x10900
    r0 = 0x4000
    [r6+0] = r0
    r0 = 0
    [r6+4] = r0
    r0 = 60000
    [r6+8] = r0
    r5 = 0x1eef11c
    r0 = 0x70000000
    [r5+0] = r0
    r0 = 0x4019
    [r6+0] = r0
    '''+post(14,10000,event)+'''r0 = 0x300
    icfg = r0
    r6 = 0x10804
    r8 = [r6+0]
    csync
    '''
        after='''csync
    r9 = [r6+0]
    '''+('nop\n'*32)+'''r5 = 0x1c7c104
    r10 = [r5+0]
    cli
    r5 = 0x10900
    r0 = 0x4000
    [r5+0] = r0
    '''+wait_ack()+'''r12 = [r7+68]
    r13 = [r7+72]
    r14 = [r7+36]
    r15 = [r7+0]
    '''
        write('idle-main-'+('control','local','global')[event],[case('idle',before,after,model='app4.peer-event')])
    for gates in (0,0x300):
        for event in ('csync','sevl','sevg'):
            before=post(15,0,gates)+wait_phase()+delay(10000)
            after=wait_ack()+'''r8 = [r7+64]
    r9 = [r7+68]
    r10 = [r7+72]
    r14 = [r7+36]
    r15 = [r7+0]
    '''
            write(f'idle-peer-{gates:x}-{event}',[case(event,before,after,model='app4.peer-event')])


def isolated():
    groups = {
        "cross-events": ("cross-control", "cross-local", "cross-global", "cross-wait",
                         "cross-delayed", "cross-delayed-local", "cross-delayed-global"),
        "locks": ("lock-control", "lock-protected", "counter-unlocked", "counter-locked", "counter-repeat"),
        "ordering": ("mp-unfenced", "mp-fenced", "sb-unfenced", "sb-fenced"),
    }
    for group, names in groups.items():
        for name, c in zip(names, json.loads((HERE/(group+".json")).read_text())):
            write(name, [c])


if __name__=='__main__':
    lifecycle()
    events()
    locks()
    barriers()
    idle_events()
    isolated()
