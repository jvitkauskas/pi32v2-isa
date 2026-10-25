# SPDX-FileCopyrightText: 2026 Julius Vitkauskas
# SPDX-License-Identifier: MIT-0
"""CPU0 visible state in the app4 lifecycle calibration; peer protocol checked separately."""

def preservation(R,f,o,st):
    return {'regs':{},'flags':f}

MODELS={'app4.preservation':preservation}
