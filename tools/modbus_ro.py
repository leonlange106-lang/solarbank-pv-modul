"""Read-only Modbus TCP client for the Anker SOLIX Solarbank 4 E5000 Pro.

HARD SAFETY CONSTRAINT
----------------------
Only function codes 1, 2, 3 and 4 are implemented. There is no code path in
this file that can emit FC 5, 6, 15 or 16. _request() raises on any other
function code before a single byte reaches the socket.

Every request/response pair is appended to a JSONL log so nothing is lost.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import socket
import struct
import sys
import time
from datetime import datetime, timezone

ALLOWED_FC = (1, 2, 3, 4)          # read coils, read discrete, read holding, read input
MAX_REGS_PER_REQUEST = 32          # per the operator's brief
INTER_BLOCK_PAUSE = 0.20           # seconds, per the operator's brief

HERE = pathlib.Path(__file__).parent
LOG_PATH = HERE / "scan_log.jsonl"

EXCEPTION_NAMES = {
    1: "IllegalFunction",
    2: "IllegalDataAddress",
    3: "IllegalDataValue",
    4: "SlaveDeviceFailure",
    5: "Acknowledge",
    6: "SlaveDeviceBusy",
    8: "MemoryParityError",
    10: "GatewayPathUnavailable",
    11: "GatewayTargetFailedToRespond",
}


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class ReadOnlyModbusTCP:
    """Minimal Modbus TCP master restricted to read function codes."""

    def __init__(self, host: str, port: int = 502, timeout: float = 4.0,
                 log_path: pathlib.Path = LOG_PATH):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.log_path = log_path
        self.sock: socket.socket | None = None
        self._tid = 0

    # -- connection ------------------------------------------------------
    def connect(self) -> None:
        self.sock = socket.create_connection((self.host, self.port), self.timeout)
        self.sock.settimeout(self.timeout)

    def close(self) -> None:
        if self.sock is not None:
            try:
                self.sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            self.sock.close()
            self.sock = None

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *exc):
        self.close()
        return False

    # -- logging ---------------------------------------------------------
    def _log(self, rec: dict) -> None:
        with self.log_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, separators=(",", ":")) + "\n")

    # -- core ------------------------------------------------------------
    def _request(self, unit: int, fc: int, addr: int, count: int) -> dict:
        """Issue one read request. Returns a result dict; never raises on
        protocol-level errors (exception responses are results, not failures)."""
        if fc not in ALLOWED_FC:
            raise ValueError(
                f"BLOCKED: function code {fc} is not a read function. "
                f"Only {ALLOWED_FC} are permitted by this tool."
            )
        if count < 1 or count > MAX_REGS_PER_REQUEST:
            raise ValueError(f"count {count} outside 1..{MAX_REGS_PER_REQUEST}")
        if not (0 <= addr <= 0xFFFF):
            raise ValueError(f"address {addr} outside 0..65535")

        self._tid = (self._tid + 1) & 0xFFFF
        pdu = struct.pack(">BHH", fc, addr, count)
        mbap = struct.pack(">HHHB", self._tid, 0, len(pdu) + 1, unit)
        rec: dict = {"ts": _now(), "unit": unit, "fc": fc, "addr": addr,
                     "count": count, "ok": False, "raw": None,
                     "exc": None, "err": None}
        try:
            if self.sock is None:
                raise ConnectionError("not connected")
            self.sock.sendall(mbap + pdu)
            header = self._recv_exact(7)
            _tid, _pid, length, _unit = struct.unpack(">HHHB", header)
            body = self._recv_exact(length - 1)
            resp_fc = body[0]
            if resp_fc & 0x80:
                rec["exc"] = body[1]
                rec["err"] = EXCEPTION_NAMES.get(body[1], f"Exception{body[1]}")
            else:
                byte_count = body[1]
                data = body[2:2 + byte_count]
                if fc in (3, 4):
                    rec["raw"] = list(struct.unpack(f">{byte_count // 2}H", data))
                else:  # coils / discrete inputs -> bit list
                    bits = []
                    for byte in data:
                        for b in range(8):
                            bits.append((byte >> b) & 1)
                    rec["raw"] = bits[:count]
                rec["ok"] = True
        except Exception as e:  # noqa: BLE001 - transport failures are results too
            rec["err"] = f"{type(e).__name__}: {e}"
        self._log(rec)
        return rec

    def _recv_exact(self, n: int) -> bytes:
        buf = b""
        while len(buf) < n:
            chunk = self.sock.recv(n - len(buf))
            if not chunk:
                raise ConnectionError("peer closed connection")
            buf += chunk
        return buf

    # -- public reads ----------------------------------------------------
    def read(self, unit: int, fc: int, addr: int, count: int = 1) -> dict:
        return self._request(unit, fc, addr, count)

    def sweep(self, unit: int, fc: int, start: int, end: int,
              block: int = MAX_REGS_PER_REQUEST, pause: float = INTER_BLOCK_PAUSE,
              progress: bool = True) -> list[dict]:
        """Read [start, end] inclusive in blocks, pausing between blocks."""
        out = []
        addr = start
        while addr <= end:
            n = min(block, end - addr + 1)
            rec = self._request(unit, fc, addr, n)
            out.append(rec)
            if progress:
                if rec["ok"]:
                    tag = "OK "
                elif rec["exc"] is not None:
                    tag = f"EX{rec['exc']}"
                else:
                    tag = "ERR"
                line = f"  u{unit} fc{fc} {addr:>6}+{n:<3} {tag} "
                line += "" if not rec["ok"] else str(rec["raw"])
                print(line[:150], flush=True)
            if rec["err"] and rec["exc"] is None:
                # transport-level failure: reconnect once before continuing
                self.close()
                time.sleep(1.0)
                try:
                    self.connect()
                except OSError as e:
                    print(f"  reconnect failed: {e}", flush=True)
                    break
            addr += n
            time.sleep(pause)
        return out


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def cmd_probe(args, c: ReadOnlyModbusTCP) -> None:
    """Single read of one known register (battery_soc @ 10014, FC04)."""
    rec = c.read(args.unit, 4, 10014, 1)
    print(json.dumps(rec, indent=2))


def cmd_units(args, c: ReadOnlyModbusTCP) -> None:
    """Probe a list of unit IDs against a known-good register."""
    for unit in args.units:
        rec = c.read(unit, 4, 10014, 1)
        status = ("OK " + str(rec["raw"])) if rec["ok"] else (rec["err"] or "?")
        print(f"  unit {unit:>3}: {status}", flush=True)
        time.sleep(args.pause)


def cmd_scan(args, c: ReadOnlyModbusTCP) -> None:
    for fc in args.fc:
        print(f"--- unit {args.unit}  FC{fc}  {args.start}..{args.end} ---", flush=True)
        c.sweep(args.unit, fc, args.start, args.end,
                block=args.block, pause=args.pause)


def cmd_map(args, c: ReadOnlyModbusTCP) -> None:
    """Two-phase map: coarse block sweep, then single-register refinement of
    the boundaries between responsive and non-responsive blocks.

    A Modbus exception 2 applies to the whole requested span, so a coarse
    block that fails may still contain valid registers at its edges.
    """
    for fc in args.fc:
        print(f"=== unit {args.unit} FC{fc} {args.start}..{args.end} (coarse, "
              f"block={args.block}) ===", flush=True)
        coarse = c.sweep(args.unit, fc, args.start, args.end,
                         block=args.block, pause=args.pause, progress=args.verbose)

        good = [r for r in coarse if r["ok"]]
        print(f"  coarse: {len(good)}/{len(coarse)} blocks answered", flush=True)
        for r in good:
            print(f"    VALID {r['addr']}..{r['addr']+r['count']-1}", flush=True)

        # refine: any failing block that touches a succeeding block
        ok_flags = [r["ok"] for r in coarse]
        refine: list[tuple[int, int]] = []
        for i, r in enumerate(coarse):
            if r["ok"]:
                continue
            prev_ok = i > 0 and ok_flags[i - 1]
            next_ok = i + 1 < len(coarse) and ok_flags[i + 1]
            if prev_ok or next_ok:
                refine.append((r["addr"], r["addr"] + r["count"] - 1))

        if not refine:
            print("  no boundary blocks to refine", flush=True)
            continue
        print(f"  refining {len(refine)} boundary block(s) register-by-register",
              flush=True)
        for lo, hi in refine:
            for a in range(lo, hi + 1):
                rec = c.read(args.unit, fc, a, 1)
                if rec["ok"]:
                    print(f"    {a:>6}  {rec['raw'][0]}", flush=True)
                time.sleep(args.pause)


def cmd_watch(args, c: ReadOnlyModbusTCP) -> None:
    """Sample the same blocks repeatedly so values can be correlated over time
    with Home Assistant entity history (plausibility testing)."""
    blocks = []
    for spec in args.blocks:
        a, _, n = spec.partition(":")
        blocks.append((int(a), int(n or 1)))
    for i in range(args.samples):
        row: dict = {"t": _now()}
        for addr, n in blocks:
            rec = c.read(args.unit, args.fc, addr, n)
            if rec["ok"]:
                for j, v in enumerate(rec["raw"]):
                    row[str(addr + j)] = v
            time.sleep(args.pause)
        print(json.dumps(row, separators=(",", ":")), flush=True)
        if i + 1 < args.samples:
            time.sleep(args.interval)


def main() -> int:
    p = argparse.ArgumentParser(description="Read-only Modbus TCP scanner (FC 1-4 only)")
    p.add_argument("--host", default="192.168.178.86")
    p.add_argument("--port", type=int, default=502)
    p.add_argument("--timeout", type=float, default=4.0)
    p.add_argument("--pause", type=float, default=INTER_BLOCK_PAUSE)
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("probe")
    sp.add_argument("--unit", type=int, default=1)
    sp.set_defaults(func=cmd_probe)

    su = sub.add_parser("units")
    su.add_argument("--units", type=int, nargs="+",
                    default=[0, 1, 2, 3, 4, 5, 16, 32, 100, 200, 246, 247])
    su.set_defaults(func=cmd_units)

    sc = sub.add_parser("scan")
    sc.add_argument("--unit", type=int, default=1)
    sc.add_argument("--fc", type=int, nargs="+", default=[4])
    sc.add_argument("--start", type=int, required=True)
    sc.add_argument("--end", type=int, required=True)
    sc.add_argument("--block", type=int, default=MAX_REGS_PER_REQUEST)
    sc.set_defaults(func=cmd_scan)

    sm = sub.add_parser("map")
    sm.add_argument("--unit", type=int, default=1)
    sm.add_argument("--fc", type=int, nargs="+", default=[4])
    sm.add_argument("--start", type=int, required=True)
    sm.add_argument("--end", type=int, required=True)
    sm.add_argument("--block", type=int, default=MAX_REGS_PER_REQUEST)
    sm.add_argument("--verbose", action="store_true")
    sm.set_defaults(func=cmd_map)

    sw = sub.add_parser("watch")
    sw.add_argument("--unit", type=int, default=1)
    sw.add_argument("--fc", type=int, default=4)
    sw.add_argument("--blocks", nargs="+", required=True,
                    help="ADDR:COUNT, e.g. 10144:32 10208:32")
    sw.add_argument("--interval", type=float, default=10.0)
    sw.add_argument("--samples", type=int, default=12)
    sw.set_defaults(func=cmd_watch)

    args = p.parse_args()
    _fc = getattr(args, "fc", [])
    for fc in ([_fc] if isinstance(_fc, int) else _fc):
        if fc not in ALLOWED_FC:
            print(f"REFUSED: function code {fc} is not read-only.", file=sys.stderr)
            return 2

    c = ReadOnlyModbusTCP(args.host, args.port, args.timeout)
    try:
        c.connect()
    except OSError as e:
        print(f"connect failed: {e}", file=sys.stderr)
        return 1
    try:
        args.func(args, c)
    finally:
        c.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
