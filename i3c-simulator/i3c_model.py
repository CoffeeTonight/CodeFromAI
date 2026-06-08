#!/usr/bin/env python3
"""
I3C Protocol Model + Simulator (Educational)
Models MIPI I3C SDR basics: START/STOP, 7-bit addressing, ACK/NACK,
Broadcast & Direct CCC, simplified Dynamic Address Assignment (DAA),
Private Transfers, and IBI (In-Band Interrupt) events.

Generates:
- Signal events for waveform rendering (SDA/SCL)
- Rich transaction records with human interpretations
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple, Any
import time
import random

# =============================================================================
# Timing constants (abstract units, ~10ns per tick for visualization)
# =============================================================================
TICK = 1
BIT_PERIOD = 80          # full SCL period
HALF_BIT = BIT_PERIOD // 2
QUARTER_BIT = BIT_PERIOD // 4
START_HOLD = 30
STOP_SETUP = 30
IDLE_GAP = 120

# =============================================================================
# Data structures
# =============================================================================
@dataclass
class SignalEvent:
    t: int          # absolute simulation time
    sda: int        # 0 or 1
    scl: int        # 0 or 1
    note: str = ""  # optional label like "START", "ACK", "DATA[0]"

@dataclass
class Transaction:
    id: int
    bus_id: int
    start_t: int
    end_t: int
    kind: str                    # "START", "CCC_BCAST", "DAA", "PRIVATE_WR", "PRIVATE_RD", "IBI", "STOP"
    addr: Optional[int] = None   # 7-bit address (0x7E for broadcast)
    rnw: Optional[int] = None    # 0=write, 1=read
    data: List[int] = field(default_factory=list)  # bytes on wire (after address)
    ccc_code: Optional[int] = None
    details: str = ""
    interpretation: str = ""
    participants: List[str] = field(default_factory=list)

@dataclass
class I3CTargetSpec:
    """Static description of an I3C or legacy I2C device."""
    name: str
    pid: int            # 48-bit provisional ID (for I3C devices)
    bcr: int            # Bus Characteristics Register
    dcr: int            # Device Characteristics Register
    static_addr: Optional[int] = None  # for legacy I2C or SETDASA
    supports_ibi: bool = True
    is_i3c: bool = True

# Common I3C CCC codes (subset)
CCC = {
    "ENEC":   0x00,   # Enable Events (incl IBI)
    "DISEC":  0x01,   # Disable Events
    "ENTAS0": 0x02,
    "RSTDAA": 0x06,   # Reset Dynamic Address Assignment
    "ENTDAA": 0x07,   # Enter DAA
    "SETDASA":0x06,   # Actually overlaps in some docs; we use 0x87 for direct SETDASA variant
    "SETNEWDA":0x88,  # Direct
    "GETBCR": 0x2A,   # Direct
    "GETDCR": 0x2B,
    "GETPID": 0x2C,
    "SETMWL": 0x09,   # Set Max Write Length (broadcast)
    "SETMRL": 0x0A,
}

# =============================================================================
# I3C Bus (physical layer + transaction log)
# =============================================================================
class I3CBus:
    def __init__(self, bus_id: int, name: str = ""):
        self.bus_id = bus_id
        self.name = name or f"I3C-{bus_id}"
        self.events: List[SignalEvent] = []
        self.transactions: List[Transaction] = []
        self.current_t: int = 0
        self.sda: int = 1
        self.scl: int = 1
        self._tx_counter = 0
        self._last_event_t = 0

    # --- Low-level signal driving ---
    def _emit(self, sda: Optional[int] = None, scl: Optional[int] = None, note: str = ""):
        if sda is not None:
            self.sda = 1 if sda else 0
        if scl is not None:
            self.scl = 1 if scl else 0
        ev = SignalEvent(self.current_t, self.sda, self.scl, note)
        self.events.append(ev)
        self._last_event_t = self.current_t

    def advance(self, dt: int):
        self.current_t += dt

    def idle(self, duration: int = IDLE_GAP):
        self._emit(sda=1, scl=1, note="IDLE")
        self.advance(duration)

    def start(self) -> int:
        """Generate START condition. Returns timestamp of the edge."""
        t_start = self.current_t
        self._emit(sda=1, scl=1)
        self.advance(START_HOLD)
        self._emit(sda=0, scl=1, note="START")
        self.advance(QUARTER_BIT)
        return t_start

    def repeated_start(self) -> int:
        self._emit(sda=1, scl=0)
        self.advance(QUARTER_BIT)
        self._emit(sda=1, scl=1)
        self.advance(QUARTER_BIT)
        self._emit(sda=0, scl=1, note="Sr")
        self.advance(QUARTER_BIT)
        return self.current_t

    def stop(self) -> int:
        t = self.current_t
        self._emit(sda=0, scl=0)
        self.advance(QUARTER_BIT)
        self._emit(sda=0, scl=1)
        self.advance(QUARTER_BIT)
        self._emit(sda=1, scl=1, note="STOP")
        self.advance(STOP_SETUP)
        return t

    def clock_out_bit(self, bit: int, note: str = "") -> int:
        """Controller drives a bit (open-drain style for ACK phase too)."""
        t0 = self.current_t
        self._emit(scl=0, sda=bit)
        self.advance(HALF_BIT)
        self._emit(scl=1)
        self.advance(HALF_BIT)
        if note:
            self.events[-1].note = note
        return t0

    def clock_out_byte(self, byte: int, notes: Optional[List[str]] = None) -> List[int]:
        """Drives 8 bits MSB first. Returns list of bit start times."""
        times = []
        for i in range(8):
            bit = (byte >> (7 - i)) & 1
            note = (notes[i] if notes and i < len(notes) else "")
            times.append(self.clock_out_bit(bit, note))
        return times

    def clock_for_read_bit(self, driven_by_target: int, note: str = "") -> int:
        """Controller releases SDA, target drives the bit (for reads + ACKs)."""
        t0 = self.current_t
        self._emit(scl=0, sda=1)  # release
        self.advance(HALF_BIT)
        self._emit(scl=1, sda=driven_by_target)  # sample point
        if note:
            self.events[-1].note = note
        self.advance(HALF_BIT)
        return t0

    def clock_for_read_byte(self, value: int, is_ack_phase: bool = False) -> List[int]:
        """Simulate target driving a full byte (or ACK bit)."""
        times = []
        for i in range(8):
            bit = (value >> (7 - i)) & 1
            times.append(self.clock_for_read_bit(bit))
        # 9th bit = ACK (0) or NACK (1) from target perspective in read
        ack_val = 0 if not is_ack_phase else 0   # for simplicity we mostly ACK
        self.clock_for_read_bit(ack_val, note="ACK" if ack_val == 0 else "NACK")
        return times

    # --- High-level protocol helpers used by Controller ---
    def begin_transaction(self) -> Transaction:
        self._tx_counter += 1
        tx = Transaction(
            id=self._tx_counter,
            bus_id=self.bus_id,
            start_t=self.current_t,
            end_t=self.current_t,
            kind="",
            data=[]
        )
        return tx

    def commit_transaction(self, tx: Transaction, kind: str, **kwargs):
        tx.end_t = self.current_t + 20
        tx.kind = kind
        for k, v in kwargs.items():
            setattr(tx, k, v)
        self.transactions.append(tx)
        return tx

    def get_waveform(self) -> List[Dict[str, Any]]:
        """Return compact list for JSON transport to frontend."""
        return [{"t": e.t, "sda": e.sda, "scl": e.scl, "note": e.note} for e in self.events]

    def get_transactions(self) -> List[Dict[str, Any]]:
        return [
            {
                "id": t.id,
                "bus_id": t.bus_id,
                "start_t": t.start_t,
                "end_t": t.end_t,
                "kind": t.kind,
                "addr": t.addr,
                "rnw": t.rnw,
                "data": t.data,
                "ccc_code": t.ccc_code,
                "details": t.details,
                "interpretation": t.interpretation,
                "participants": t.participants,
            }
            for t in self.transactions
        ]

# =============================================================================
# I3C Controller (Master)
# =============================================================================
class I3CController:
    def __init__(self, bus: I3CBus, name: str = "I3C Controller"):
        self.bus = bus
        self.name = name
        self.dynamic_addrs: Dict[int, I3CTargetSpec] = {}   # DA -> spec
        self.next_da = 0x08
        self.time_offset = 0  # for interleaving buses

    def _sync_time(self):
        """Make controller's view of time follow the bus."""
        if self.bus.current_t > self.time_offset:
            self.time_offset = self.bus.current_t

    def reset_bus(self):
        self.bus.idle(80)
        # Many controllers toggle SCL a few times or just rely on STOP
        self.bus.stop()
        self.bus.idle(200)

    def broadcast_ccc(self, ccc_code: int, data: Optional[List[int]] = None, label: str = "") -> Transaction:
        """Broadcast CCC (address 0x7E + W)."""
        self._sync_time()
        tx = self.bus.begin_transaction()
        tx.addr = 0x7E
        tx.rnw = 0
        tx.ccc_code = ccc_code
        tx.participants = ["BROADCAST"]

        self.bus.start()
        # Address phase + W
        self.bus.clock_out_byte(0x7E << 1 | 0, notes=["ADDR[6]", "ADDR[5]", "ADDR[4]", "ADDR[3]", "ADDR[2]", "ADDR[1]", "ADDR[0]", "W"])
        self.bus.clock_for_read_bit(0, note="ACK")  # targets ACK

        # CCC code
        self.bus.clock_out_byte(ccc_code, notes=[f"CCC[7:0]=0x{ccc_code:02X}"] * 8)
        self.bus.clock_for_read_bit(0, note="ACK")

        tx.data = [ccc_code]
        if data:
            for b in data:
                self.bus.clock_out_byte(b)
                self.bus.clock_for_read_bit(0, note="ACK")
            tx.data.extend(data)

        self.bus.stop()
        tx.interpretation = self._interpret_ccc(ccc_code, data, broadcast=True)
        tx.details = f"BCAST CCC 0x{ccc_code:02X} " + (f"+{len(data)}B data" if data else "")
        self.bus.commit_transaction(tx, "CCC_BCAST", ccc_code=ccc_code)
        self.bus.idle(60)
        return tx

    def direct_ccc(self, da: int, ccc_code: int, write_data: Optional[List[int]] = None,
                   read_len: int = 0, label: str = "") -> Transaction:
        """Direct CCC to a specific dynamic address."""
        self._sync_time()
        tx = self.bus.begin_transaction()
        tx.addr = da
        tx.rnw = 0 if read_len == 0 else 1
        tx.ccc_code = ccc_code

        self.bus.start()
        # 0x7E W + Direct CCC code
        self.bus.clock_out_byte(0x7E << 1 | 0)
        self.bus.clock_for_read_bit(0, note="ACK")

        self.bus.clock_out_byte(ccc_code)
        self.bus.clock_for_read_bit(0, note="ACK")

        # Then repeated start + device addr + RnW
        self.bus.repeated_start()
        addr_byte = (da << 1) | (1 if read_len > 0 else 0)
        self.bus.clock_out_byte(addr_byte)
        self.bus.clock_for_read_bit(0, note="ACK")

        data = []
        if read_len > 0:
            # Target drives data
            for i in range(read_len):
                val = random.randint(0x10, 0xFE) & 0xFF   # simulated sensor data
                self.bus.clock_for_read_byte(val)
                data.append(val)
            tx.rnw = 1
        else:
            if write_data:
                for b in write_data:
                    self.bus.clock_out_byte(b)
                    self.bus.clock_for_read_bit(0, note="ACK")
                data = write_data

        tx.data = data
        self.bus.stop()
        tx.interpretation = self._interpret_direct_ccc(da, ccc_code, data, read_len > 0)
        tx.details = f"Direct 0x{ccc_code:02X} to 0x{da:02X}"
        if data:
            tx.details += f" data={[hex(d) for d in data]}"
        self.bus.commit_transaction(tx, "CCC_DIRECT", addr=da, ccc_code=ccc_code)
        self.bus.idle(50)
        return tx

    def private_write(self, da: int, data: List[int], reg: Optional[int] = None) -> Transaction:
        """I3C Private Write (or I2C style)."""
        self._sync_time()
        tx = self.bus.begin_transaction()
        tx.addr = da
        tx.rnw = 0

        self.bus.start()
        self.bus.clock_out_byte((da << 1) | 0)
        self.bus.clock_for_read_bit(0, note="ACK")

        all_data = []
        if reg is not None:
            self.bus.clock_out_byte(reg)
            self.bus.clock_for_read_bit(0, note="ACK")
            all_data.append(reg)

        for b in data:
            self.bus.clock_out_byte(b)
            self.bus.clock_for_read_bit(0, note="ACK")
            all_data.append(b)

        tx.data = all_data
        self.bus.stop()

        dev_name = self._get_dev_name(da)
        tx.interpretation = f"Private Write to {dev_name} (DA=0x{da:02X}). " \
                            f"{'Reg 0x%02X = ' % reg if reg is not None else ''}{[hex(d) for d in data]}"
        tx.details = f"WR 0x{da:02X} len={len(data)}"
        self.bus.commit_transaction(tx, "PRIVATE_WR", addr=da)
        self.bus.idle(70)
        return tx

    def private_read(self, da: int, length: int, reg: Optional[int] = None) -> Transaction:
        """I3C Private Read."""
        self._sync_time()
        tx = self.bus.begin_transaction()
        tx.addr = da
        tx.rnw = 1

        self.bus.start()
        self.bus.clock_out_byte((da << 1) | 0)
        self.bus.clock_for_read_bit(0, note="ACK")

        if reg is not None:
            self.bus.clock_out_byte(reg)
            self.bus.clock_for_read_bit(0, note="ACK")
            # Repeated start for read
            self.bus.repeated_start()
            self.bus.clock_out_byte((da << 1) | 1)
            self.bus.clock_for_read_bit(0, note="ACK")

        data = []
        for i in range(length):
            val = (0xA0 + i * 7 + (da & 0xF)) & 0xFF   # deterministic fake sensor data
            self.bus.clock_for_read_byte(val)
            data.append(val)

        tx.data = data
        self.bus.stop()

        dev_name = self._get_dev_name(da)
        tx.interpretation = f"Private Read from {dev_name} (DA=0x{da:02X}). " \
                            f"Returned {[hex(d) for d in data]}"
        tx.details = f"RD 0x{da:02X} len={length}"
        self.bus.commit_transaction(tx, "PRIVATE_RD", addr=da)
        self.bus.idle(65)
        return tx

    def perform_daa(self, targets: List[I3CTargetSpec]) -> List[Transaction]:
        """
        Simplified but visually faithful ENTDAA procedure.
        We simulate arbitration by having the lowest PID "win" each round.
        """
        self._sync_time()
        txs = []

        # 1. Disable events during address assignment
        txs.append(self.broadcast_ccc(CCC["DISEC"], label="Disable IBI during DAA"))

        # 2. Reset any previous dynamic addresses
        txs.append(self.broadcast_ccc(CCC["RSTDAA"]))

        # 3. Enter DAA
        tx_daa = self.bus.begin_transaction()
        tx_daa.addr = 0x7E
        tx_daa.ccc_code = CCC["ENTDAA"]
        tx_daa.participants = [t.name for t in targets]

        self.bus.start()
        self.bus.clock_out_byte(0x7E << 1 | 0)
        self.bus.clock_for_read_bit(0, note="ACK")
        self.bus.clock_out_byte(CCC["ENTDAA"])
        self.bus.clock_for_read_bit(0, note="ACK")
        self.bus.stop()
        tx_daa.details = "ENTDAA broadcast"
        tx_daa.interpretation = "Broadcast ENTDAA (0x07). All I3C devices without dynamic address now participate in address assignment arbitration."
        self.bus.commit_transaction(tx_daa, "CCC_BCAST", ccc_code=CCC["ENTDAA"])
        self.bus.idle(40)
        txs.append(tx_daa)

        # 4. For each target (sorted by PID ascending - lowest wins first in I3C)
        sorted_targets = sorted(targets, key=lambda t: t.pid)
        assigned = []

        for spec in sorted_targets:
            tx = self.bus.begin_transaction()
            tx.addr = 0x7E
            tx.kind = "DAA"
            tx.participants = [spec.name]

            # Simulate the long arbitration phase where target drives its ID
            # We show ~ 64 bits of "PID + BCR + DCR + parity" (simplified visually)
            self.bus.start()
            self.bus.clock_out_byte(0x7E << 1 | 1)   # 0x7E + Read for DAA header
            self.bus.clock_for_read_bit(0, note="ACK")

            # Controller clocks while target drives 48-bit PID + 8 BCR + 8 DCR + 1 T-bit (simplified)
            pid_bytes = [(spec.pid >> (40 - i*8)) & 0xFF for i in range(6)]
            bcr = spec.bcr
            dcr = spec.dcr

            id_bits_shown = []
            for b in pid_bytes + [bcr, dcr]:
                self.bus.clock_for_read_byte(b)
                id_bits_shown.append(b)

            # After reading ID, controller assigns next DA
            new_da = self.next_da
            self.next_da += 1

            # Write assigned address (with T-bit parity in real I3C, we simplify)
            self.bus.clock_out_byte(new_da)
            self.bus.clock_for_read_bit(0, note="T-bit/ACK")

            self.bus.stop()

            self.dynamic_addrs[new_da] = spec
            assigned.append((new_da, spec))

            tx.data = pid_bytes + [bcr, dcr, new_da]
            tx.details = f"DAA: {spec.name} PID=0x{spec.pid:012X} -> DA=0x{new_da:02X}"
            tx.interpretation = (f"Dynamic Address Assignment: Device '{spec.name}' (PID 0x{spec.pid:012X}, "
                                 f"BCR=0x{bcr:02X}, DCR=0x{dcr:02X}) won arbitration and was assigned dynamic address 0x{new_da:02X}.")
            self.bus.commit_transaction(tx, "DAA", addr=new_da)
            self.bus.idle(55)
            txs.append(tx)

        # 5. Re-enable events
        txs.append(self.broadcast_ccc(CCC["ENEC"]))

        return txs

    def simulate_ibi(self, da: int, ibi_data: Optional[List[int]] = None) -> Transaction:
        """Simplified IBI: target pulls SDA low during idle, controller responds."""
        self._sync_time()
        tx = self.bus.begin_transaction()
        tx.addr = da
        tx.kind = "IBI"
        tx.participants = [self._get_dev_name(da)]

        # Idle, then target asserts SDA low while SCL high (IBI request)
        self.bus._emit(sda=1, scl=1, note="IDLE")
        self.bus.advance(40)
        self.bus._emit(sda=0, scl=1, note="IBI START")
        self.bus.advance(25)

        # Controller detects and clocks the address + RnW=1 (for IBI) + MDB (mandatory data byte)
        self.bus._emit(scl=0)
        self.bus.advance(HALF_BIT)
        self.bus._emit(scl=1)
        self.bus.advance(20)

        # Address phase for IBI response (controller drives 0x7E or directly ACKs)
        self.bus.start()
        self.bus.clock_out_byte(0x7E << 1 | 1)  # special for IBI in some flows
        self.bus.clock_for_read_bit(0, note="ACK")

        # Target provides its own DA + one status byte (MDB)
        mdb = 0x80 | (da & 0x7F)   # simplified MDB containing address
        self.bus.clock_for_read_byte(mdb)

        extra = []
        if ibi_data:
            for b in ibi_data:
                self.bus.clock_for_read_byte(b)
                extra.append(b)

        self.bus.stop()

        tx.data = [mdb] + extra
        tx.interpretation = (f"In-Band Interrupt (IBI) from {self._get_dev_name(da)} (DA=0x{da:02X}). "
                             f"Mandatory Data Byte=0x{mdb:02X}. Device signaled urgent attention.")
        tx.details = f"IBI from 0x{da:02X}"
        self.bus.commit_transaction(tx, "IBI", addr=da)
        self.bus.idle(90)
        return tx

    # --- Helpers ---
    def _interpret_ccc(self, code: int, data: Optional[List[int]], broadcast: bool) -> str:
        name = {v: k for k, v in CCC.items()}.get(code, f"0x{code:02X}")
        if code == CCC["ENTDAA"]:
            return "ENTDAA: All I3C targets without a dynamic address enter arbitration to receive a unique address from the controller."
        if code == CCC["RSTDAA"]:
            return "RSTDAA: All dynamic addresses are cleared. Devices return to unaddressed state (ready for new DAA)."
        if code == CCC["DISEC"]:
            return "DISEC: In-Band Interrupts and other events are temporarily disabled (used during initialization)."
        if code == CCC["ENEC"]:
            return "ENEC: Re-enable In-Band Interrupts and events after address assignment is complete."
        if code == CCC["SETMWL"]:
            return "SETMWL: Set maximum number of bytes the controller will write in a single private transfer."
        return f"{name} broadcast CCC (0x{code:02X})"

    def _interpret_direct_ccc(self, da: int, code: int, data: List[int], is_read: bool) -> str:
        dev = self._get_dev_name(da)
        name = {v: k for k, v in CCC.items()}.get(code, f"0x{code:02X}")
        if code == CCC["GETPID"]:
            return f"GETPID from {dev}: Controller reads 48-bit Provisional ID for device identification / qualification."
        if code == CCC["GETBCR"]:
            return f"GETBCR from {dev}: Read Bus Characteristics Register (IBI support, speed capabilities, etc)."
        if code == CCC["GETDCR"]:
            return f"GETDCR from {dev}: Read Device Characteristics Register (device type / class)."
        return f"Direct {name} ({'RD' if is_read else 'WR'}) to {dev} (0x{da:02X})"

    def _get_dev_name(self, da: int) -> str:
        spec = self.dynamic_addrs.get(da)
        return spec.name if spec else f"0x{da:02X}"

# =============================================================================
# Top-level SoC Scenario
# =============================================================================
def build_soc_scenario() -> Dict[str, Any]:
    """
    One host SoC with two independent I3C controllers/buses.
    Bus 0: Primary sensor bus (Temp + IMU legacy-style)
    Bus 1: Secondary bus (Pressure sensor + simple actuator)
    Shows: DAA on both, private transfers, cross-bus data movement, one IBI.
    """
    random.seed(42)  # reproducible "sensor" data

    # --- Define devices ---
    targets_bus0 = [
        I3CTargetSpec(
            name="TempSensor",
            pid=0x123456789ABC,
            bcr=0x01,   # IBI capable, SDR only for demo
            dcr=0xC3,   # made-up device class "temperature"
            static_addr=0x48,
            supports_ibi=True,
            is_i3c=True
        ),
        I3CTargetSpec(
            name="IMU_Accel",
            pid=0xAABBCCDDEEFF,
            bcr=0x00,   # legacy friendly
            dcr=0x92,
            static_addr=0x68,
            supports_ibi=False,
            is_i3c=False   # treated as I2C legacy for part of sim
        ),
    ]

    targets_bus1 = [
        I3CTargetSpec(
            name="PressureSensor",
            pid=0x5566778899AA,
            bcr=0x03,
            dcr=0xA1,
            static_addr=0x76,
            supports_ibi=True,
            is_i3c=True
        ),
        I3CTargetSpec(
            name="ActuatorCtrl",
            pid=0x112233445566,
            bcr=0x01,
            dcr=0x55,
            static_addr=None,
            supports_ibi=True,
            is_i3c=True
        ),
    ]

    # --- Create buses and controllers ---
    bus0 = I3CBus(0, "I3C Bus 0 (Sensors)")
    bus1 = I3CBus(1, "I3C Bus 1 (Peripherals)")

    ctrl0 = I3CController(bus0, "I3C Controller 0")
    ctrl1 = I3CController(bus1, "I3C Controller 1")

    all_transactions: List[Dict[str, Any]] = []
    all_waveforms: Dict[int, List[Dict[str, Any]]] = {}

    # Give each bus a little initial idle
    bus0.idle(50)
    bus1.idle(30)

    # ========== BUS 0 INITIALIZATION ==========
    print("[Bus0] Starting DAA for 2 devices...")
    daa_txs0 = ctrl0.perform_daa(targets_bus0)
    for t in daa_txs0:
        all_transactions.append(t.__dict__ if not isinstance(t, dict) else t)

    # After DAA, we know:
    #   TempSensor -> 0x08
    #   IMU_Accel  -> 0x09   (even though legacy, controller used SETDASA-like path in real life; we simplified)

    # Get device info via direct CCC (common after DAA)
    ctrl0.direct_ccc(0x08, CCC["GETPID"], read_len=6)
    ctrl0.direct_ccc(0x08, CCC["GETBCR"], read_len=1)
    ctrl0.direct_ccc(0x09, CCC["GETDCR"], read_len=1)

    # Private transfers on Bus 0
    # Write configuration to temperature sensor
    ctrl0.private_write(0x08, [0x01, 0xC0], reg=0x02)   # config reg 0x02 <- 0xC0

    # Read temperature (2 bytes)
    temp_data = ctrl0.private_read(0x08, 2, reg=0x00)

    # Read IMU data (simulating legacy I2C device)
    ctrl0.private_read(0x09, 6, reg=0x3B)   # typical accel data start reg

    # ========== BUS 1 INITIALIZATION ==========
    print("[Bus1] Starting DAA for 2 devices...")
    daa_txs1 = ctrl1.perform_daa(targets_bus1)
    for t in daa_txs1:
        all_transactions.append(t.__dict__ if not isinstance(t, dict) else t)

    # Bus 1 devices:
    #   PressureSensor -> 0x08
    #   ActuatorCtrl   -> 0x09

    ctrl1.direct_ccc(0x08, CCC["GETPID"], read_len=6)
    ctrl1.broadcast_ccc(CCC["SETMWL"], data=[0x00, 0x40])  # max write 64 bytes

    # Write to pressure sensor (set ODR / mode)
    ctrl1.private_write(0x08, [0x55, 0xAA], reg=0x10)

    # ========== CROSS-BUS COMMUNICATION (Host mediated) ==========
    # Host reads temp from Bus0, then writes the value into ActuatorCtrl on Bus1 as "setpoint"
    print("[Host] Cross-bus data movement: TempSensor -> ActuatorCtrl")

    # We already have temp_data from earlier read. Simulate host using it.
    # For demo, create a new transaction that "forwards" representative data.
    host_temp_reading = temp_data.data if temp_data and temp_data.data else [0x1A, 0x45]
    setpoint = host_temp_reading[0]   # use first byte as example setpoint

    # Write to actuator on bus 1
    ctrl1.private_write(0x09, [0x20, setpoint], reg=0x05)   # "desired temp" register

    # Record a synthetic "Host Bridge" transaction for the UI (not real bus traffic)
    bridge_tx = Transaction(
        id=9999,
        bus_id=-1,   # special marker
        start_t=bus0.current_t - 200,
        end_t=bus1.current_t,
        kind="HOST_BRIDGE",
        details=f"Host read 0x{host_temp_reading[0]:02X}{host_temp_reading[1]:02X} from Bus0/TempSensor → wrote 0x{setpoint:02X} to Bus1/ActuatorCtrl",
        interpretation="The SoC host processor read temperature data over I3C Bus 0 and forwarded a control setpoint to an actuator controller attached to I3C Bus 1. This demonstrates typical sensor-to-actuator data flow across multiple I3C domains inside one chip.",
        participants=["Host CPU", "TempSensor@Bus0", "ActuatorCtrl@Bus1"]
    )
    all_transactions.append(bridge_tx.__dict__)

    # ========== IBI on Bus 0 ==========
    print("[Bus0] Simulating In-Band Interrupt from TempSensor...")
    ctrl0.simulate_ibi(0x08, ibi_data=[0xE0])   # status byte indicating "temp alert"

    # Final small activity on both buses
    ctrl0.private_read(0x08, 2, reg=0x00)   # poll temp again
    ctrl1.private_write(0x09, [0x00], reg=0x07)  # actuator disarm or status

    # Collect final state
    all_waveforms[0] = bus0.get_waveform()
    all_waveforms[1] = bus1.get_waveform()

    # Merge transactions (they were appended in order)
    final_txs = []
    for tx in bus0.transactions + bus1.transactions:
        final_txs.append({
            "id": tx.id,
            "bus_id": tx.bus_id,
            "start_t": tx.start_t,
            "end_t": tx.end_t,
            "kind": tx.kind,
            "addr": tx.addr,
            "rnw": tx.rnw,
            "data": tx.data,
            "ccc_code": tx.ccc_code,
            "details": tx.details,
            "interpretation": tx.interpretation,
            "participants": tx.participants,
        })
    # Add the synthetic bridge transaction
    final_txs.append({
        "id": bridge_tx.id,
        "bus_id": bridge_tx.bus_id,
        "start_t": bridge_tx.start_t,
        "end_t": bridge_tx.end_t,
        "kind": bridge_tx.kind,
        "addr": bridge_tx.addr,
        "rnw": bridge_tx.rnw,
        "data": bridge_tx.data,
        "ccc_code": bridge_tx.ccc_code,
        "details": bridge_tx.details,
        "interpretation": bridge_tx.interpretation,
        "participants": bridge_tx.participants,
    })

    # Sort by start time for nice timeline
    final_txs.sort(key=lambda x: (x["start_t"], x["bus_id"] if x["bus_id"] >= 0 else 999))

    # Renumber for UI
    for i, tx in enumerate(final_txs):
        tx["id"] = i + 1

    # Global simulation info
    max_t = max(bus0.current_t, bus1.current_t)

    result = {
        "meta": {
            "title": "I3C Dual-Bus SoC Simulation",
            "description": "One host SoC with two independent I3C controllers. Demonstrates bus initialization (DAA), private transfers, CCC commands, In-Band Interrupt, and host-mediated communication between buses.",
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "max_t": max_t,
            "buses": [
                {"id": 0, "name": bus0.name, "controller": "I3C Controller 0"},
                {"id": 1, "name": bus1.name, "controller": "I3C Controller 1"},
            ],
            "devices": {
                0: [{"da": da, "name": spec.name, "pid": f"0x{spec.pid:012X}", "is_i3c": spec.is_i3c}
                    for da, spec in ctrl0.dynamic_addrs.items()],
                1: [{"da": da, "name": spec.name, "pid": f"0x{spec.pid:012X}", "is_i3c": spec.is_i3c}
                    for da, spec in ctrl1.dynamic_addrs.items()],
            }
        },
        "waveforms": all_waveforms,
        "transactions": final_txs,
    }
    return result

if __name__ == "__main__":
    # Quick smoke test when run directly
    trace = build_soc_scenario()
    print(f"\nSimulation complete.")
    print(f"  Max time: {trace['meta']['max_t']}")
    print(f"  Transactions: {len(trace['transactions'])}")
    print(f"  Bus0 waveform points: {len(trace['waveforms'][0])}")
    print(f"  Bus1 waveform points: {len(trace['waveforms'][1])}")
    # Print a few tx for sanity
    for tx in trace['transactions'][:3]:
        print(f"  TX{tx['id']}: {tx['kind']} on bus {tx['bus_id']} - {tx['details']}")
