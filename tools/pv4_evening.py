"""Abendlanglauf: PV4 und unbestimmte Register identifizieren.

NUR LESEND. Baut ausschliesslich Function Code 4 (Read Input Registers).
Die Framing-Funktion akzeptiert keinen anderen Funktionscode - ein Schreibzugriff
ist konstruktiv unmoeglich, nicht bloss unterlassen.

Methode: Das Geraet liefert seine eigene Gegenprobe. Register 10002 ist die
Gesamt-PV-Leistung. Die drei bestaetigten Straenge stehen in 10167..10172.
    resid = pv_total - (U1*I1 + U2*I2 + U3*I3)
Dieser Restwert IST die Leistung von Strang 4. Gegen ihn wird jedes unbestimmte
Register korreliert.

Robustheit: Faellt die Verbindung aus (Steckdosenumzug), wird der Fehler als
Datensatz protokolliert und nach RETRY_PAUSE Sekunden erneut versucht. Der Lauf
bricht dadurch nicht ab. Die Ausgabedatei wird angehaengt, ein Neustart verliert
also nichts.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import socket
import struct
import sys
import time

FC_READ_INPUT = 4
MAX_REGS_PER_REQUEST = 32
INTER_BLOCK_PAUSE = 0.20
RETRY_PAUSE = 300.0

# Adresse:Anzahl - jede Kombination ist im Scanlog als erfolgreich belegt.
# Bloecke, die dennoch eine Modbus-Ausnahme liefern, werden uebersprungen.
BLOCKS: list[tuple[int, int]] = [
    # Diese beiden MUESSEN unmittelbar aufeinander folgen. Der Restwert ist eine
    # Differenz grosser Zahlen; jede Sekunde Versatz zwischen der Gesamtleistung
    # und den Straengen geht voll in das Rauschen ein. Mit 1,2 s Abstand schwankte
    # der Restwert um +-70 W, mit 0,2 s deutlich weniger.
    (10002, 2),    # pv_power gesamt (INT32) - die Referenz
    (10144, 32),   # 10144-10175: 10156 und die Straenge 10167-10172
    (10008, 2),    # Batterieleistung (INT32, negativ = laden)
    (10010, 2),    # load_power (INT32)
    (10012, 2),    # Netzleistung (INT32)
    (10014, 1),    # SOC
    (10040, 32),   # 10040-10071: SOC-Bytefeld, Geraetezeit, Betriebsmodus
    (10112, 32),   # 10112-10143: Firmware, Geraeteinfo-Unbestimmte
    (10183, 1),
    (10187, 1),
    (10199, 1),
    (10202, 1),
    (10205, 1),    # Hauptkandidat Strang 4
    (10208, 32),   # 10208-10239: AC-Block, Netzspannung, Frequenz, Unbestimmte
    # Als Block, nicht einzeln: bei Einzellesungen erwischt man nur die
    # Highwords, und 10252/10254 sind dann nicht aufloesbar. Falls das Geraet
    # die Kombination ablehnt, greifen die Einzellesungen darunter.
    (10250, 8),
    (10250, 1),
    (10252, 1),
    (10254, 1),
    (10256, 1),
    (10262, 2),
    (10264, 2),
]


class ModbusException(Exception):
    def __init__(self, code: int) -> None:
        super().__init__(f"Modbus-Ausnahme {code}")
        self.code = code


class ReadOnlyModbus:
    """Minimaler Modbus-TCP-Client. Kann ausschliesslich lesen."""

    def __init__(self, host: str, port: int, unit: int, timeout: float) -> None:
        self.host = host
        self.port = port
        self.unit = unit
        self.timeout = timeout
        self.sock: socket.socket | None = None
        self._tid = 0

    def connect(self) -> None:
        self.close()
        self.sock = socket.create_connection((self.host, self.port), self.timeout)
        self.sock.settimeout(self.timeout)

    def close(self) -> None:
        if self.sock is not None:
            try:
                self.sock.close()
            except OSError:
                pass
            self.sock = None

    def read(self, addr: int, count: int) -> list[int]:
        """Liest count Register ab addr. Wirft bei Ausnahme oder Transportfehler."""
        if not 1 <= count <= MAX_REGS_PER_REQUEST:
            raise ValueError(f"count {count} ausserhalb 1..{MAX_REGS_PER_REQUEST}")
        if self.sock is None:
            raise ConnectionError("nicht verbunden")

        self._tid = (self._tid + 1) & 0xFFFF
        pdu = struct.pack(">BHH", FC_READ_INPUT, addr, count)
        mbap = struct.pack(">HHHB", self._tid, 0, len(pdu) + 1, self.unit)
        self.sock.sendall(mbap + pdu)

        head = self._recv_exact(7)
        length = struct.unpack(">H", head[4:6])[0]
        body = self._recv_exact(length - 1)

        fc = body[0]
        if fc & 0x80:
            raise ModbusException(body[1])
        nbytes = body[1]
        payload = body[2 : 2 + nbytes]
        return [
            struct.unpack(">H", payload[i : i + 2])[0]
            for i in range(0, len(payload), 2)
        ]

    def _recv_exact(self, n: int) -> bytes:
        assert self.sock is not None
        buf = b""
        while len(buf) < n:
            chunk = self.sock.recv(n - len(buf))
            if not chunk:
                raise ConnectionError("Gegenstelle hat geschlossen")
            buf += chunk
        return buf


def to_int32(hi: int, lo: int) -> int:
    v = ((hi & 0xFFFF) << 16) | (lo & 0xFFFF)
    return v - 0x100000000 if v & 0x80000000 else v


def to_int16(v: int) -> int:
    """Die Strangstroeme sind vorzeichenbehaftet.

    Kurz vor dem Erloeschen liefert das Geraet kleine negative Werte, gemessen
    am 11.08.2026 ab 19:28: Register 10168 = 65528, also -0,08 A. Ohne
    Vorzeichenbehandlung werden daraus 655,28 A und Phantomleistungen von ueber
    20 kW - 20 von 292 Messpunkten waren so verdorben. Die Rohwerte in `regs`
    bleiben davon unberuehrt, alte Laeufe lassen sich also neu ausrechnen.
    """
    v &= 0xFFFF
    return v - 0x10000 if v & 0x8000 else v


def sample(client: ReadOnlyModbus) -> dict[int, int]:
    """Liest alle Bloecke. Bloecke mit Modbus-Ausnahme werden uebersprungen,
    Transportfehler werden nach oben gereicht (loesen Wiederanlauf aus)."""
    regs: dict[int, int] = {}
    for addr, count in BLOCKS:
        try:
            words = client.read(addr, count)
        except ModbusException:
            continue
        for i, w in enumerate(words):
            regs[addr + i] = w
        time.sleep(INTER_BLOCK_PAUSE)
    return regs


def derive(regs: dict[int, int]) -> dict[str, float | None]:
    """Rechnet die Straenge und den Restwert aus. None, wenn Register fehlen."""
    need = (10002, 10003, 10167, 10168, 10169, 10170, 10171, 10172)
    if any(a not in regs for a in need):
        return {"pv_total": None, "pv1": None, "pv2": None, "pv3": None, "resid": None}

    pv_total = float(to_int32(regs[10002], regs[10003]))
    pv1 = regs[10167] / 10.0 * to_int16(regs[10168]) / 100.0
    pv2 = regs[10169] / 10.0 * to_int16(regs[10170]) / 100.0
    pv3 = regs[10171] / 10.0 * to_int16(regs[10172]) / 100.0
    return {
        "pv_total": round(pv_total, 1),
        "pv1": round(pv1, 1),
        "pv2": round(pv2, 1),
        "pv3": round(pv3, 1),
        "resid": round(pv_total - (pv1 + pv2 + pv3), 1),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Abendlanglauf PV4, nur lesend")
    ap.add_argument("--host", default="192.168.178.86")
    ap.add_argument("--port", type=int, default=502)
    ap.add_argument("--unit", type=int, default=1)
    ap.add_argument("--timeout", type=float, default=5.0)
    ap.add_argument("--interval", type=float, default=30.0)
    ap.add_argument("--out", default="pv4_evening.jsonl")
    ap.add_argument(
        "--until",
        default="23:30",
        help="Ortszeit HH:MM, bis zu der gemessen wird",
    )
    args = ap.parse_args()

    hh, mm = (int(x) for x in args.until.split(":"))
    now = dt.datetime.now()
    end = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
    if end <= now:
        end += dt.timedelta(days=1)

    client = ReadOnlyModbus(args.host, args.port, args.unit, args.timeout)
    out = open(args.out, "a", encoding="utf-8")
    n_ok = n_err = 0

    print(
        f"Start {now:%H:%M:%S}, Ende {end:%H:%M:%S}, Takt {args.interval:.0f}s",
        flush=True,
    )

    while dt.datetime.now() < end:
        t0 = time.time()
        stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        rec: dict = {"t": stamp, "ok": False, "err": None}
        try:
            if client.sock is None:
                client.connect()
            regs = sample(client)
            rec.update(derive(regs))
            rec["ok"] = True
            rec["regs"] = regs
            n_ok += 1
            print(
                f"{stamp}  gesamt={rec['pv_total']:>7}  "
                f"pv1={rec['pv1']:>6} pv2={rec['pv2']:>6} pv3={rec['pv3']:>6}  "
                f"REST={rec['resid']:>7}  10205={regs.get(10205)}  10156={regs.get(10156)}",
                flush=True,
            )
        except Exception as exc:  # Verbindung weg, Timeout, Reset
            rec["err"] = f"{type(exc).__name__}: {exc}"
            n_err += 1
            client.close()
            print(f"{stamp}  FEHLER {rec['err']} - warte {RETRY_PAUSE:.0f}s", flush=True)
            out.write(json.dumps(rec, ensure_ascii=False) + "\n")
            out.flush()
            time.sleep(RETRY_PAUSE)
            continue

        out.write(json.dumps(rec, ensure_ascii=False) + "\n")
        out.flush()

        rest = args.interval - (time.time() - t0)
        if rest > 0:
            time.sleep(rest)

    client.close()
    out.close()
    print(f"Fertig. {n_ok} Messpunkte, {n_err} Fehler.", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
