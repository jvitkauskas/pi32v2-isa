# FM-1, 2026-10-27: fm1-base with JieLi's Bluetooth libraries, from the drop-in

fm1-base's template (upstream e35f7e2, Bluetooth MIDI on the SDK AC79NN V1.2.1 `btctrler.a`/`btstack.a`, LLVM 4
bitcode) built by its own `tools/build.py template` with `JIELI_TOOLCHAIN` the drop-in package
([DROPIN.md](../../docs/DROPIN.md)) of the fork's branch `pi32v2-dropin`; the reference is the same tree built with
JieLi's toolchain 20260730.1 (app 215 356 bytes). Installed with M-Flasher (backups before every write), restarted
from download mode, then from the desktop (BlueZ): scan, connect, read the services, disconnect, scan again; the
unit's own log read over USB-MIDI (`F0 7D 4C 47 F7`).

| | JieLi's build | drop-in, fork 21dfa6ef1 | drop-in, with word-aligned locals |
| --- | --- | --- | --- |
| App | 215 356 B | 209 320 B | 209 372 B |
| Boots, USB-MIDI `TEMPLATE FM-1` | yes | yes | yes |
| Advertises `FM-1` with the BLE-MIDI service | yes | yes | yes |
| Connect, services resolved | yes | link up, then a connection timeout | yes |
| Disconnect, advertising again, no reset | yes | the chip resets at the connection | yes |
| The unit's log (connect, MTU, CCC, connection update, terminate) | | | line for line JieLi's build's |

The reset: exception 1 in fm1-base's `q_put` (its OS shim's task queue) at a word load from `0x01C32D0E`. The
controller's `hci_send_event_cmd_complete` builds the event in a packed local (`alloca %struct.hci_event, align
1`) and `h4_controller_send_packet` posts an HCI event to the host task as `(size + 3) / 4` ints, the packet
itself as their array; here a 22-byte Command Complete, six words. JieLi's frame puts the event at `sp+4`, the
fork's put it at `sp+6` (the padding under it), and a misaligned word load resets the chip ([GAPS.md](../../docs/GAPS.md)).
The fork now word-aligns every local of a word or more (`PI32V2AlignAllocas`); the event is at `sp+4`.

Not exercised: MIDI notes over Bluetooth, pairing, a phone.
