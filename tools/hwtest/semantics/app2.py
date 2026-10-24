# SPDX-FileCopyrightText: 2026 Julius Vitkauskas
# SPDX-License-Identifier: MIT-0
"""Visible register/scratch effects of the app2 recording-handler environment.

The handlers preserve GPRs/flags and resume after the probe. This does not model the bare opcode as a nop.
Vector/cause/count observations and temporal masking assertions are checked separately by appverify.py.
"""


def trap(R, f, o, st):
    mem = {}
    if st.rec['id'] in ('bkpt', 'hbkpt'):
        # Debug entries use the current case stack. The exit overwrites the upper 64 bytes of the frame.
        mem = {st.sp-72:f, st.sp-68:R[0]}
    return {'regs':{}, 'flags':f, 'mem':mem}


MODELS = {'app2.trap':trap}
