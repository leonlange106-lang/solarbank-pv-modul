"""Gemeinsame Basis fuer die Registerjagd.

READ-ONLY. Nutzt ReadOnlyModbusTCP aus modbus_ro.py, das konstruktionsbedingt
nur FC 1-4 senden kann (_request wirft bei allem anderen). Kein FC43.

Zentrale Korrektur gegenueber dem ersten Durchlauf:
Ein TIMEOUT ist eine GUELTIGE ANTWORT ("diese Unit-ID/Adresse antwortet nicht")
und KEIN Verbindungsverlust. Nur echte Transportfehler (RST, FIN, Socketfehler)
loesen eine Neubeschaffung der Verbindung aus.
"""
from __future__ import annotations

import json
import pathlib
import sys
import time

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE))
from modbus_ro import ReadOnlyModbusTCP  # noqa: E402

HOST = "192.168.178.86"
RAW_LOG = HERE / "sweep_log.jsonl"
PAUSE = 0.35              # -> max ~2.8 Anfragen/s, Auflage: <= 3/s
ACQUIRE_INTERVAL = 2.0

# Fehlertexte, die KEIN Verbindungsverlust sind, sondern eine Antwort
_TIMEOUT_MARKERS = ("TimeoutError", "timeout", "timed out")

_client: ReadOnlyModbusTCP | None = None


def log(msg: str) -> None:
    print(f"{time.strftime('%H:%M:%S')} {msg}", flush=True)


def is_timeout(rec: dict) -> bool:
    """Timeout = das Geraet hat schlicht nicht geantwortet. Gueltige Antwort."""
    e = rec.get("err") or ""
    return any(m in e for m in _TIMEOUT_MARKERS)


def acquire(max_wait: float = 7200.0, timeout: float = 5.0) -> ReadOnlyModbusTCP:
    """Warte auf einen freien Verbindungsplatz und halte ihn."""
    global _client
    if _client is not None:
        try:
            _client.close()
        except Exception:
            pass
        _client = None
    t0 = time.time()
    attempt = 0
    while time.time() - t0 < max_wait:
        attempt += 1
        c = ReadOnlyModbusTCP(HOST, 502, timeout=timeout, log_path=RAW_LOG)
        try:
            c.connect()
        except OSError:
            time.sleep(ACQUIRE_INTERVAL)
            continue
        rec = c.read(1, 4, 10014, 1)
        if rec["ok"]:
            log(f"VERBINDUNG ERHALTEN nach {attempt} Versuch(en), "
                f"soc={rec['raw'][0]}")
            _client = c
            return c
        c.close()
        if attempt % 30 == 0:
            log(f"  warte auf freien Platz ({attempt} Versuche, "
                f"{time.time()-t0:.0f}s): {rec['err']}")
        time.sleep(ACQUIRE_INTERVAL)
    raise SystemExit("Kein Verbindungsplatz frei.")


def rd(unit: int, fc: int, addr: int, count: int = 1) -> dict:
    """Lesen. Timeout und Modbus-Ausnahme sind Ergebnisse, kein Fehler.
    Nur echte Transportfehler loesen eine Neubeschaffung aus."""
    global _client
    for _ in range(4):
        rec = _client.read(unit, fc, addr, count)
        if rec["ok"] or rec["exc"] is not None or is_timeout(rec):
            return rec
        log(f"  Transportfehler bei unit{unit} addr{addr}: {rec['err']} "
            f"- warte 30 s und hole die Verbindung neu")
        time.sleep(30)
        acquire()
    return rec


def set_client(c: ReadOnlyModbusTCP) -> None:
    global _client
    _client = c
