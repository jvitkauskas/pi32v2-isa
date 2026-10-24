#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Julius Vitkauskas
# SPDX-License-Identifier: MIT-0
"""Write the app3 case programs, using only this repository's assembler/table."""
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]/'tools/hwtest'))
import gen
from pi32v2isa.oracle import read_exec
T = gen.table.load()
HERE = Path(__file__).resolve().parents[2]/'hw/fm1-2026-10-24-app3'


def parts(text):
    obj = gen.asm.assemble_source('.text\n'+text+'\n', 'app3-case.S')
    data = next(s['data'] for s in read_exec(obj)['sections'] if s['name']=='.text')
    out = []
    while data:
        i, v, size = gen.codec.decode(T, data)
        out.append({'id':i.id, 'values':v})
        data = data[size:]
    return out


def delay(n=1000000):
    return f'r0 = {n}\n1:\nr0 = r0 + -1\nif (r0 != 0) goto 1b\n'


def case(id, before='', after='', values=None, model='app3.temporal'):
    return dict(id=id, values=values or {}, **{'in':[0x12340000+i*0x101 for i in range(16)]},
                flags=5, force=True, model=model, before=parts(before), after=parts(after))


def write(name, cases):
    (HERE/(name+'.json')).write_text(json.dumps(cases, indent=2)+'\n')


def events():
    cs=[]
    for id, count, event, irq in [('wfe',1,'',False),('wfe',128,'',False),
            ('wfe',128,'sevl',False),('wfe',128,'sevg',False),('wfe',1,'',True),
            ('idle',1,'',True),('wfe',128,'',True)]:
        n=len(cs)
        before=f'''cli
r6 = 0x10900
r0 = 0x4000
[r6+0] = r0
r0 = 0
[r6+4] = r0
r0 = {60000 if irq else 0x7fffffff}
[r6+8] = r0
r5 = 0x1eef11c
r0 = {0x70000000 if irq else 0}
[r5+0] = r0
r0 = 0x4019
[r6+0] = r0
r7 = {0x1c7c104+n*256}
r0 = 0x300
icfg = r0
r8 = [r6+4]
'''+event+'\n'+('wfe\n'*(count-1))
        after='r9 = [r6+4]\nr10 = [r7+0]\nr11 = icfg\ncli\nr0 = 0x4000\n[r6+0] = r0'
        cs.append(case(id,before,after))
    for n, bit8 in enumerate((False,True),7):
        before=f'r7 = {0x1c7c104+n*256}\nr8 = [r7+0]\n'
        before+= 'r0 = 0x200\nicfg = r0' if bit8 else 'cli'
        after=delay(10000)+'r9 = [r7+0]\nr0 = 0x300\nicfg = r0\n'+delay(10000)+'r10 = [r7+0]\nr11 = icfg'
        cs.append(case('swi',before,after,{'n':7 if bit8 else 0}))
    write('events',cs)


def nesting():
    cs=[]
    for n,(outer,child,gate) in enumerate([(3,7,0),(3,7,1),(3,7,2),(3,7,3),(3,3,1),(7,3,1),(0,7,1),(7,0,1),(3,7,1)]):
        j=0x1c7c100+n*256
        before=f"""cli
r7 = {j}
r0 = {gate}
[r7+112] = r0
r6 = 0x1eef13c
r0 = {(outer*2+1)|((child*2+1)<<4)}
[r6+0] = r0
r0 = 0x300
icfg = r0
r8 = [r7+4]
"""
        after=delay(10000)+'r9 = [r7+4]\nr10 = [r7+120]\nr11 = [r7+124]'
        cs.append(case('swi',before,after,{'n':0},'app3.nesting'))
    write('nesting',cs)


def cores():
    cs=[]
    for cmd,id in [(1,'csync'),(2,'csync'),(3,'csync'),(4,'wfe'),(5,'csync'),(5,'sevl'),(5,'sevg'),(6,'csync')]:
        before=f"""cli
r7 = 0x1c7ce00
r8 = [r7+0]
r9 = [r7+28]
r6 = 0x10800
r0 = 0x4000
[r6+0] = r0
r0 = 0
[r6+4] = r0
r0 = 0x7fffffff
[r6+8] = r0
r0 = 0x4019
[r6+0] = r0
r0 = {cmd}
[r7+4] = r0
csync
"""
        if cmd in (5,6):before+=delay(10000)
        before+='r14 = [r7+32]\nr12 = [r6+4]\ncsync'
        after='csync\nr13 = [r6+4]\nr10 = [r7+8]\n'+delay(2000000)+'csync\nr11 = [r7+8]\nr15 = [r7+36]\nr0 = 0x4000\n[r6+0] = r0'
        cs.append(case(id,before,after,model='app3.core'))
    write('cores',cs)


def synchronized():
    cs=[]
    for id,count,event,irq,gates in [('csync',1,'',False,0),('wfe',128,'',False,0),
            ('wfe',128,'sevl',False,0),('wfe',128,'sevg',False,0),
            ('wfe',1,'',True,0x300),('idle',1,'',True,0x300),
            ('wfe',128,'',True,0x200),('wfe',128,'',True,0x100),('idle',1,'',True,0)]:
        n=len(cs)
        before=f"""cli
r6 = 0x10800
r5 = 0x10900
r0 = 0x4000
[r6+0] = r0
[r5+0] = r0
r0 = 0
[r6+4] = r0
[r5+4] = r0
r0 = 0x7fffffff
[r6+8] = r0
r0 = 60000
[r5+8] = r0
r4 = 0x1eef11c
r0 = {0x70000000 if irq else 0}
[r4+0] = r0
r0 = 0x4019
[r6+0] = r0
"""
        if irq:before+='[r5+0] = r0\n'
        before+=f'r7 = {0x1c7c104+n*256}\nr0 = {gates}\nicfg = r0\n'+event+'\ncsync\nr8 = [r6+4]\ncsync\n'+('wfe\n'*(count-1))
        after='csync\n'+('nop\n'*32)+'r9 = [r6+4]\nr10 = [r7+0]\nr11 = [r5+0]\ncli\nr0 = 0x4000\n[r6+0] = r0\n[r5+0] = r0'
        cs.append(case(id,before,after))
    write('synchronized',cs)


def core_sequence():
    before="""cli
r7 = 0x1c7ce00
r8 = [r7+0]
r9 = [r7+28]
r6 = 0x10800
r0 = 0x4000
[r6+0] = r0
r0 = 0
[r6+4] = r0
r0 = 0x7fffffff
[r6+8] = r0
r0 = 0x4019
[r6+0] = r0
"""
    for cmd in (1,2,3):
        before+=f'r0 = {cmd}\n[r7+4] = r0\ncsync\n'+delay(10000)+f'csync\nr0 = [r7+8]\n[r7+{36+cmd*4}] = r0\n'
    before+='r0 = 4\n[r7+4] = r0\ncsync\nr12 = [r6+4]\n[r7+52] = r12\ncsync'
    after='csync\nr13 = [r6+4]\n[r7+56] = r13\nr10 = [r7+8]\n[r7+60] = r10\n'+delay(2000000)+'csync\nr11 = [r7+8]\n'
    for cmd,reg,event in [(5,12,''),(6,13,''),(8,14,'sevl'),(9,15,'sevg')]:
        after+=f'r0 = {cmd}\n[r7+4] = r0\ncsync\n'+event+'\n'+delay(10000)+f'csync\nr{reg} = [r7+8]\n'
    after+='r0 = 0x4000\n[r6+0] = r0'
    write('core-sequence',[case('wfe',before,after,model='app3.core-sequence')])


def copex():
    cs=[]
    old=json.loads((HERE.parent/'fm1-2026-10-24-v5/copex-history.json').read_text())[0]
    for mode in (None,14,15,15,14,14,15,None):
        c=dict(old)
        c['before']=parts(('' if mode is None else f'r1_r0 = copex(r5_r4) ({mode})\n')+'r0 = 0x13579bdf\nr1 = 0x12569ade')
        c['after']=parts('nop\n'*32)
        c['model']='app3.copex'
        cs.append(c)
    write('copex-app',cs)
    write('copex-repeat',cs)


if __name__=='__main__':
    events()
    nesting()
    cores()
    write('cores-restart',json.loads((HERE/'cores.json').read_text()))
    synchronized()
    core_sequence()
    copex()
