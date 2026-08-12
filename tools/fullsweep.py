"""Vollstaendiger Einzeladress-Sweep ueber den restlichen Adressraum.

READ-ONLY, ausschliesslich FC04 mit count=1. Kein FC43, kein Schreibzugriff.
Rate: eine Anfrage je 0.35 s -> max ~2.8/s (Auflage: <= 3/s).

WIEDERAUFNAHMEFAEHIG: Nach jeder Adresse wird der Fortschritt in
`fullsweep_progress.jsonl` geschrieben und geflusht. Ein Neustart setzt exakt
dort fort, wo der letzte Lauf stehengeblieben ist. Ein Abbruch kostet also
hoechstens eine Adresse.

Aufruf:  python fullsweep.py
"""
from __future__ import annotations

import json
import pathlib
import time

import jaeger_lib as J

HERE = pathlib.Path(__file__).parent
PROGRESS = HERE / "fullsweep_progress.jsonl"
HITS = HERE / "fullsweep_hits.jsonl"

# Bereits lueckenlos einzeln geprueft (count=1) und daher uebersprungen
DONE_RANGES = [
    (10000, 11000),    # Sweep 11.08. 19:38-19:45
    (32700, 33100),    # Sweep 11.08. 19:45-19:48
    (59900, 60500),    # Sweep 11.08. 19:48-19:52
]
DONE_SINGLES = {0, 100, 500, 1000, 9999}   # Einzelproben des Altscans

# Reihenfolge nach Erfolgsaussicht: erst die Nachbarschaft der bekannten
# Registerinseln, dann der grosse Rest.
ORDER = [
    (11001, 12000),
    (9000, 9999),
    (0, 999),
    (12001, 13000),
    (1000, 8999),
    (13001, 32699),
    (33101, 59899),
    (60501, 65535),
]


def build_worklist() -> list[int]:
    done = set(DONE_SINGLES)
    for lo, hi in DONE_RANGES:
        done.update(range(lo, hi + 1))
    work: list[int] = []
    seen = set()
    for lo, hi in ORDER:
        for a in range(lo, hi + 1):
            if a not in done and a not in seen:
                seen.add(a)
                work.append(a)
    return work


def load_cursor() -> int:
    """Hoechster bereits abgearbeiteter Index + 1."""
    if not PROGRESS.exists():
        return 0
    idx = 0
    for line in PROGRESS.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue          # abgeschnittene letzte Zeile nach hartem Abbruch
        if "i" in d:
            idx = max(idx, d["i"] + 1)
    return idx


def main() -> None:
    work = build_worklist()
    start = load_cursor()
    total = len(work)
    J.log(f"Arbeitsliste: {total} Adressen, Wiederaufnahme ab Index {start}")
    if start >= total:
        J.log("Nichts mehr zu tun - Lauf war bereits vollstaendig.")
        return
    J.log(f"verbleibend: {total-start} Adressen, geschaetzt "
          f"{(total-start)*0.40/3600:.1f} h")

    pf = PROGRESS.open("a", encoding="utf-8")
    hf = HITS.open("a", encoding="utf-8")

    J.acquire()

    n_ok = n_exc = n_other = 0
    t0 = time.time()
    last_report = time.time()

    for i in range(start, total):
        a = work[i]
        rec = J.rd(1, 4, a, 1)
        if rec["ok"]:
            v = rec["raw"][0]
            n_ok += 1
            J.log(f"    TREFFER {a} = {v}")
            hf.write(json.dumps({"addr": a, "value": v,
                                 "t": time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                                    time.gmtime())}) + "\n")
            hf.flush()
            pf.write(json.dumps({"i": i, "a": a, "ok": True, "v": v}) + "\n")
        elif rec["exc"] is not None:
            n_exc += 1
            pf.write(json.dumps({"i": i, "a": a, "exc": rec["exc"]}) + "\n")
        else:
            n_other += 1
            pf.write(json.dumps({"i": i, "a": a, "err": rec["err"]}) + "\n")
        pf.flush()

        if time.time() - last_report >= 300:      # alle 5 min ein Lebenszeichen
            done = i - start + 1
            rate = done / (time.time() - t0)
            rest = (total - 1 - i) / rate if rate > 0 else 0
            J.log(f"  [{i+1}/{total}] Adresse {a} | {n_ok} Treffer, "
                  f"{n_exc} Exception, {n_other} sonstige | "
                  f"{rate:.2f} Adr/s | Rest ~{rest/3600:.1f} h")
            last_report = time.time()

        time.sleep(J.PAUSE)

    J.log(f"FULLSWEEP FERTIG: {n_ok} Treffer, {n_exc} Exception, "
          f"{n_other} sonstige, {total-start} Adressen in "
          f"{(time.time()-t0)/3600:.2f} h")
    pf.close()
    hf.close()


if __name__ == "__main__":
    main()
