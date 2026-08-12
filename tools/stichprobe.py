"""Gegenprobe zum Nachtsweep: antworten nachts negative Adressen unter Produktion?

Der Nachtlauf hat 63 528 Adressen einzeln geprueft und null Treffer gemeldet.
Er lief jedoch bei Dunkelheit. Falls ein PV4-Register nur unter Produktion
ueberhaupt antwortet, haette er es uebersehen. Diese Stichprobe prueft 500
zufaellig gezogene, nachts negative Adressen erneut - jetzt bei laufender
Einspeisung.

POSITIVKONTROLLE: Alle 50 Adressen wird ein bekannt gueltiges Register
mitgelesen. Ohne das waeren 500 Fehlschlaege nicht von einer stillen
Verbindungsstoerung zu unterscheiden. Faellt eine Kontrolle aus, ist der
Lauf ungueltig.

READ-ONLY, ausschliesslich FC04 mit count=1.
Aufruf:  python stichprobe.py
"""
from __future__ import annotations

import json
import pathlib
import random
import sys
import time

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE))
import jaeger_lib as J  # noqa: E402

PROGRESS = HERE / "fullsweep_progress.jsonl"
OUT = HERE / "stichprobe_result.jsonl"

N_SAMPLE = 500
SEED = 20260812          # feste Saat -> der Lauf ist wiederholbar
CONTROL_EVERY = 50

# Register, die nachweislich EINZELN mit count=1 lesbar sind (PV4-SUCHE.md §2).
#
# KORREKTUR nach dem Lauf vom 12.08. 08:53: Urspruenglich standen hier auch
# 10173-10175, weil sie "gueltig, aber konstant null" sind - das Muster eines
# leeren PV4-Feldes. Das war falsch. Diese drei sind laut Start-/Count-
# Validierung des Geraets ausschliesslich INNERHALB eines Blocks lesbar, nie
# einzeln, und liefern bei count=1 zwangslaeufig Exception 2. Als Kontrolle
# fuer einen count=1-Lauf sind sie damit untauglich.
#
# 10167/10171/10172 sind einzeln lesbar UND bewegen sich unter Produktion.
# Sie belegen damit nicht nur "Verbindung steht", sondern auch "Geraet
# speist gerade ein" - genau die Bedingung, die diese Gegenprobe braucht.
CONTROLS = [10002, 10014, 10156, 10167, 10171, 10172]


def load_negatives() -> list[int]:
    """Adressen, die im Nachtlauf NICHT mit ok=True geantwortet haben."""
    neg: list[int] = []
    with PROGRESS.open(encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue          # abgeschnittene Zeile nach hartem Abbruch
            if d.get("ok") is True:
                continue
            a = d.get("a")
            if isinstance(a, int):
                neg.append(a)
    return neg


def main() -> None:
    neg = load_negatives()
    J.log(f"Nachtlauf: {len(neg)} negativ getestete Adressen als Grundgesamtheit")
    if len(neg) < N_SAMPLE:
        raise SystemExit(f"Zu wenig Daten: nur {len(neg)} negative Adressen.")

    rng = random.Random(SEED)
    sample = sorted(rng.sample(neg, N_SAMPLE))
    J.log(f"Stichprobe: {N_SAMPLE} Adressen, Saat {SEED}, "
          f"Spanne {sample[0]}-{sample[-1]}")
    J.log(f"geschaetzte Dauer: "
          f"{(N_SAMPLE + N_SAMPLE // CONTROL_EVERY) * 0.40 / 60:.1f} min")

    out = OUT.open("w", encoding="utf-8")
    J.acquire(max_wait=180.0)

    n_hit = n_exc = n_other = 0
    n_ctrl_ok = n_ctrl_fail = 0
    hits: list[tuple[int, int]] = []
    t0 = time.time()

    for k, a in enumerate(sample):
        # Positivkontrolle einstreuen, damit ein Verbindungsverlust auffaellt
        if k % CONTROL_EVERY == 0:
            ca = CONTROLS[(k // CONTROL_EVERY) % len(CONTROLS)]
            crec = J.rd(1, 4, ca, 1)
            if crec["ok"]:
                n_ctrl_ok += 1
                out.write(json.dumps({"kind": "control", "addr": ca,
                                      "ok": True, "v": crec["raw"][0]}) + "\n")
            else:
                n_ctrl_fail += 1
                J.log(f"  KONTROLLE FEHLGESCHLAGEN bei {ca}: "
                      f"exc={crec['exc']} err={crec['err']}")
                out.write(json.dumps({"kind": "control", "addr": ca,
                                      "ok": False, "exc": crec["exc"],
                                      "err": crec["err"]}) + "\n")
            out.flush()
            time.sleep(J.PAUSE)

        rec = J.rd(1, 4, a, 1)
        if rec["ok"]:
            v = rec["raw"][0]
            n_hit += 1
            hits.append((a, v))
            J.log(f"    NEUER TREFFER {a} = {v}  (nachts negativ!)")
            out.write(json.dumps({"kind": "probe", "addr": a, "ok": True,
                                  "v": v}) + "\n")
        elif rec["exc"] is not None:
            n_exc += 1
            out.write(json.dumps({"kind": "probe", "addr": a,
                                  "exc": rec["exc"]}) + "\n")
        else:
            n_other += 1
            out.write(json.dumps({"kind": "probe", "addr": a,
                                  "err": rec["err"]}) + "\n")
        out.flush()

        if (k + 1) % 100 == 0:
            J.log(f"  [{k+1}/{N_SAMPLE}] {n_hit} Treffer, {n_exc} Exception, "
                  f"{n_other} sonstige | Kontrollen {n_ctrl_ok} ok / "
                  f"{n_ctrl_fail} fehlgeschlagen")

        time.sleep(J.PAUSE)

    dt = time.time() - t0
    J.log("=" * 60)
    J.log(f"STICHPROBE FERTIG in {dt/60:.1f} min")
    J.log(f"  geprueft:            {N_SAMPLE}")
    J.log(f"  neue Treffer:        {n_hit}")
    J.log(f"  Modbus-Ausnahme:     {n_exc}")
    J.log(f"  sonstige:            {n_other}")
    J.log(f"  Positivkontrollen:   {n_ctrl_ok} ok, {n_ctrl_fail} fehlgeschlagen")
    if n_ctrl_fail:
        J.log("  ACHTUNG: Kontrolle fehlgeschlagen - Lauf NICHT belastbar.")
    elif n_hit == 0:
        J.log("  ERGEBNIS: Nullbefund bestaetigt sich unter Produktion.")
    else:
        J.log(f"  ERGEBNIS: {n_hit} Adressen antworten nur unter Produktion:")
        for a, v in hits:
            J.log(f"      {a} = {v}")
    out.close()


if __name__ == "__main__":
    main()
