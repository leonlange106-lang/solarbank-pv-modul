"""Minimaler asynchroner Modbus-TCP-Leser.

Bewusst ohne pymodbus. Zwei Gruende:

1. Sicherheit. Diese Klasse kann nur Function Code 4 erzeugen. Ein
   Schreibzugriff ist konstruktiv unmoeglich, nicht bloss unterlassen. Das ist
   die staerkste verfuegbare Zusicherung fuer ein Geraet, das ins Hausnetz
   einspeist.
2. Versionsstabilitaet. Die pymodbus-3.x-Reihe hat den Parameter fuer die
   Unit-ID mehrfach umbenannt (slave, device_id). Eigenes Framing ist gegen
   solche Verschiebungen immun, und das Framing ist gegen dieses Geraet belegt.

Das Geraet validiert die Kombination aus Startadresse UND Count, nicht jede
Adresse einzeln. Bloecke muessen deshalb auf belegten Startadressen aufsetzen.
"""
from __future__ import annotations

import asyncio
import logging
import struct

_LOGGER = logging.getLogger(__name__)

FC_READ_INPUT = 4
MAX_REGS_PER_REQUEST = 32
MBAP_HEADER_LEN = 7


class ModbusError(Exception):
    """Transportfehler oder ungueltige Antwort."""


class ModbusExceptionResponse(ModbusError):
    """Das Geraet hat mit einem Ausnahmecode geantwortet."""

    def __init__(self, code: int) -> None:
        super().__init__(f"Modbus-Ausnahme {code}")
        self.code = code

    @property
    def illegal_address(self) -> bool:
        """Ausnahme 2: Start/Count-Kombination ist ungueltig."""
        return self.code == 2


class SolarbankReader:
    """Haelt eine TCP-Sitzung und liest Registerbloecke. Nur lesend."""

    def __init__(self, host: str, port: int, unit: int, timeout: float) -> None:
        self._host = host
        self._port = port
        self._unit = unit
        self._timeout = timeout
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._tid = 0
        # Serialisiert die eigenen Anfragen. Schuetzt NICHT gegen andere
        # Clients - die offizielle Integration hat ihre eigenen Locks, die
        # prozessintern wirken und uns nicht kennen.
        self._lock = asyncio.Lock()

    @property
    def connected(self) -> bool:
        return self._writer is not None and not self._writer.is_closing()

    async def connect(self) -> None:
        await self.close()
        self._reader, self._writer = await asyncio.wait_for(
            asyncio.open_connection(self._host, self._port), self._timeout
        )

    async def close(self) -> None:
        writer, self._writer, self._reader = self._writer, None, None
        if writer is None:
            return
        try:
            writer.close()
            await writer.wait_closed()
        except (OSError, asyncio.TimeoutError):
            pass

    async def read_block(self, address: int, count: int) -> list[int]:
        """Liest count Register ab address.

        Wirft ModbusExceptionResponse, wenn das Geraet die Kombination ablehnt,
        und ModbusError bei jedem Transportproblem.
        """
        if not 1 <= count <= MAX_REGS_PER_REQUEST:
            raise ValueError(f"count {count} ausserhalb 1..{MAX_REGS_PER_REQUEST}")

        async with self._lock:
            if not self.connected:
                await self.connect()
            try:
                return await asyncio.wait_for(
                    self._request(address, count), self._timeout
                )
            except asyncio.TimeoutError as exc:
                await self.close()
                raise ModbusError(f"Zeitueberschreitung bei {address}:{count}") from exc
            except (OSError, asyncio.IncompleteReadError) as exc:
                await self.close()
                raise ModbusError(f"Transportfehler bei {address}:{count}: {exc}") from exc

    async def _request(self, address: int, count: int) -> list[int]:
        assert self._reader is not None and self._writer is not None

        self._tid = (self._tid + 1) & 0xFFFF
        pdu = struct.pack(">BHH", FC_READ_INPUT, address, count)
        mbap = struct.pack(">HHHB", self._tid, 0, len(pdu) + 1, self._unit)
        self._writer.write(mbap + pdu)
        await self._writer.drain()

        head = await self._reader.readexactly(MBAP_HEADER_LEN)
        length = struct.unpack(">H", head[4:6])[0]
        if length < 2:
            raise ModbusError(f"unplausible Laengenangabe {length}")
        body = await self._reader.readexactly(length - 1)

        if body[0] & 0x80:
            raise ModbusExceptionResponse(body[1])
        if body[0] != FC_READ_INPUT:
            raise ModbusError(f"unerwarteter Funktionscode {body[0]} in der Antwort")

        nbytes = body[1]
        payload = body[2 : 2 + nbytes]
        if len(payload) != count * 2:
            raise ModbusError(f"{len(payload)} Nutzbytes erhalten, {count * 2} erwartet")
        return [struct.unpack_from(">H", payload, i)[0] for i in range(0, nbytes, 2)]


# ---------------------------------------------------------------------------
# Dekodierung. Big-Endian, High-Word zuerst.
# ---------------------------------------------------------------------------

def decode(kind: str, words: list[int]) -> int:
    """Wandelt Rohregister in einen Ganzzahlwert."""
    if kind == "u16":
        return words[0] & 0xFFFF
    if kind == "u16_hi":
        return (words[0] >> 8) & 0xFF
    if kind in ("i32", "u32"):
        value = ((words[0] & 0xFFFF) << 16) | (words[1] & 0xFFFF)
        if kind == "i32" and value & 0x80000000:
            value -= 0x100000000
        return value
    raise ValueError(f"unbekannter Datentyp {kind}")
