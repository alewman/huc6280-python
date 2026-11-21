<!-- SPDX-License-Identifier: MIT -->
# Notices

huc6280-python is MIT licensed ([LICENSE](LICENSE)). It contains one piece ported from
permissively licensed code, whose notice follows.

## MAME: the HuCard mirroring in `src/huc6280/harness.py` (`bank_offsets`)

Ported from MAME 0.285 `src/devices/bus/pce/pce_slot.cpp`, `rom_map_setup`
(`license:BSD-3-Clause`, `copyright-holders:Fabio Priuli`), on 2026-11-19.

    Copyright (c) Fabio Priuli and the MAME team.

    Redistribution and use in source and binary forms, with or without modification, are
    permitted provided that the following conditions are met:

    1. Redistributions of source code must retain the above copyright notice, this list of
       conditions and the following disclaimer.
    2. Redistributions in binary form must reproduce the above copyright notice, this list of
       conditions and the following disclaimer in the documentation and/or other materials
       provided with the distribution.
    3. Neither the name of the copyright holder nor the names of its contributors may be used
       to endorse or promote products derived from this software without specific prior
       written permission.

    THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY
    EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF
    MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
    COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
    EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
    SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
    HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR
    TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
    SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

## Facts cited from permissive sources (no code taken)

Comments cite MAME 0.285 `src/devices/cpu/h6280/h6280.cpp` (`license:BSD-3-Clause`,
`copyright-holders:Bryan McPhail`) for what it does (zero-page pointer wrap, `TSB`/`TRB` Z, `TMA`
with several bits, the 7-cycle entry) and ares (ISC, ares team, Near et al) for its interrupt
sequence. No code of either is in the core.
