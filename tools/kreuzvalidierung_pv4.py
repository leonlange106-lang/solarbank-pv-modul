"""Kreuzvalidierung der PV4-Schaetzung V4 = Median(V1..V3).

Die Leistung von Strang 4 ist exakt (Differenz zweier Messgroessen). Spannung
und Strom einzeln sind es nicht - aus einem Produkt lassen sich zwei Faktoren
nicht zurueckgewinnen. Die Integration nimmt deshalb an, dass die MPP-Spannung
aller vier koplanaren Module gleich ist, und setzt V4 = Median(V1,V2,V3).

Dieses Skript beziffert den Fehler dieser Annahme, statt ihn zu behaupten.
Verfahren: fuer jeden bekannten Strang k wird die Spannung aus den beiden
uebrigen geschaetzt und gegen die Messung gehalten. Getrennt ausgewertet nach
unverschatteten Zeiten und dem Verschattungsfenster.

Wichtige Einschraenkung, die das Ergebnis eher zu schlecht als zu gut macht:
Der Schaetzer im Feld bildet den Median aus DREI Werten, die Validierung nur
aus ZWEI (Median von zwei Werten ist deren Mittel). Ein einzelner verschatteter
Nachbar zieht ein Zweiermittel voll mit, den Median aus drei Werten gar nicht.
Der hier gemessene Fehler ist damit eine obere Schranke.

Aufruf:  python tools/kreuzvalidierung_pv4.py [pfad/zu/pv4_tag.jsonl]
"""
from __future__ import annotations

import json
import statistics
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Skalierung wie in const.py
V_SCALE = 0.1
I_SCALE = 0.01

# Registeradressen der drei gemessenen Straenge
STRINGS = ((10167, 10168), (10169, 10170), (10171, 10172))

# Unterhalb dieses Stroms liegt der Arbeitspunkt Richtung Leerlauf und die
# MPP-Annahme traegt nicht mehr. Gleiche Schranke wie MIN_CURRENT_FOR_RATIO,
# aber deutlich hoeher angesetzt: hier geht es um die Gueltigkeit der
# Spannungsgleichheit, nicht um eine Division.
MIN_CURRENT = 2.0

# Verschattung, gleiche Schwelle wie SHADE_ON in const.py
SHADE_ON = 0.60

# Sommerzeit: die Zeitstempel sind UTC, das Fenster des Auftrags ist Ortszeit.
LOCAL_OFFSET = timedelta(hours=2)
WINDOW_LOCAL = (12.5, 15.5)


def i16(word: int) -> int:
    return word - 0x10000 if word & 0x8000 else word


def lade(pfad: Path) -> list[dict]:
    punkte = []
    for zeile in pfad.read_text(encoding="utf-8").splitlines():
        if not zeile.strip():
            continue
        satz = json.loads(zeile)
        if not satz.get("ok"):
            continue
        regs = satz["regs"]
        try:
            volt = [regs[str(v)] * V_SCALE for v, _ in STRINGS]
            amp = [i16(regs[str(a)]) * I_SCALE for _, a in STRINGS]
        except KeyError:
            continue
        stunde = (
            datetime.fromisoformat(satz["t"].replace("Z", "+00:00"))
            .astimezone(timezone(LOCAL_OFFSET))
        )
        punkte.append(
            {
                "zeit": stunde,
                "stunde": stunde.hour + stunde.minute / 60.0,
                "v": volt,
                "i": amp,
                "p": [v * a for v, a in zip(volt, amp)],
                "pv_total": satz["pv_total"],
                "resid": satz["resid"],
            }
        )
    return punkte


def verschattet(punkt: dict) -> bool:
    """Mindestens ein Strang liegt unter SHADE_ON des Medians der uebrigen."""
    for k in range(3):
        andere = [punkt["i"][j] for j in range(3) if j != k]
        referenz = statistics.median(andere)
        if referenz >= 0.5 and punkt["i"][k] / referenz < SHADE_ON:
            return True
    return False


def kennzahlen(fehler: list[float]) -> dict:
    if not fehler:
        return {"n": 0}
    betrag = sorted(abs(f) for f in fehler)
    n = len(betrag)
    return {
        "n": n,
        "median": betrag[n // 2],
        "p90": betrag[int(n * 0.90)],
        "p95": betrag[int(n * 0.95)],
        "max": betrag[-1],
        "mittel": sum(betrag) / n,
        "bias": sum(fehler) / n,
    }


def zeile(titel: str, k: dict) -> str:
    if not k["n"]:
        return f"{titel:<34} keine Messpunkte"
    return (
        f"{titel:<34} n={k['n']:>5}  "
        f"Median {k['median']:5.2f} %  p90 {k['p90']:5.2f} %  "
        f"p95 {k['p95']:5.2f} %  max {k['max']:6.2f} %  "
        f"Bias {k['bias']:+5.2f} %"
    )


def main() -> int:
    pfad = Path(sys.argv[1]) if len(sys.argv) > 1 else (
        Path(__file__).resolve().parent / "rohdaten" / "pv4_tag.jsonl"
    )
    punkte = lade(pfad)
    if not punkte:
        print(f"keine verwertbaren Messpunkte in {pfad}")
        return 1

    unter_last = [p for p in punkte if min(p["i"]) >= MIN_CURRENT]

    gruppen: dict[str, list[float]] = {
        "alle unter Last": [],
        "ohne Verschattung": [],
        "mit Verschattung": [],
        "Fenster 12:30-15:30": [],
        "ausserhalb des Fensters": [],
        # Der entscheidende Schnitt. Ist ein NACHBAR verschattet, zieht das
        # Zweiermittel der Validierung voll mit, waehrend der Median aus drei
        # Werten im Feld den Ausreisser verwirft - dieser Fehler ist ein
        # Artefakt der Validierung. Ist der ZIELSTRANG selbst verschattet,
        # hilft kein Median: dann ist die Annahme gleicher Spannung schlicht
        # falsch, und genau dieser Fall trifft PV4.
        "Zielstrang selbst verschattet": [],
        "nur Nachbar verschattet": [],
    }
    # Fehler des geschaetzten Stroms, getrennt gefuehrt: er ist nicht einfach
    # das Negative des Spannungsfehlers, sondern V_wahr/V_schaetz - 1.
    strom_fehler: dict[str, list[float]] = {k: [] for k in gruppen}

    for p in unter_last:
        im_fenster = WINDOW_LOCAL[0] <= p["stunde"] < WINDOW_LOCAL[1]
        schatten = verschattet(p)
        # Welche Straenge sind einzeln verschattet
        schattig = []
        for k in range(3):
            andere = [p["i"][j] for j in range(3) if j != k]
            referenz = statistics.median(andere)
            schattig.append(referenz >= 0.5 and p["i"][k] / referenz < SHADE_ON)

        for k in range(3):
            gemessen = p["v"][k]
            if gemessen <= 0:
                continue
            schaetzung = statistics.median([p["v"][j] for j in range(3) if j != k])
            rel = (schaetzung - gemessen) / gemessen * 100.0
            rel_i = (gemessen / schaetzung - 1.0) * 100.0 if schaetzung > 0 else 0.0

            ziele = ["alle unter Last"]
            ziele.append("mit Verschattung" if schatten else "ohne Verschattung")
            ziele.append(
                "Fenster 12:30-15:30" if im_fenster else "ausserhalb des Fensters"
            )
            if schattig[k]:
                ziele.append("Zielstrang selbst verschattet")
            elif schatten:
                ziele.append("nur Nachbar verschattet")
            for ziel in ziele:
                gruppen[ziel].append(rel)
                strom_fehler[ziel].append(rel_i)

    print(f"Datei:            {pfad}")
    print(f"Messpunkte:       {len(punkte)} gesamt, {len(unter_last)} unter Last "
          f"(alle drei Straenge >= {MIN_CURRENT} A)")
    if unter_last:
        print(f"Zeitraum:         {unter_last[0]['zeit']:%H:%M} bis "
              f"{unter_last[-1]['zeit']:%H:%M} Ortszeit")
    print()
    print("Relativer Fehler der geschaetzten Spannung "
          "(Median der uebrigen gegen Messung)")
    print("-" * 100)
    for titel, werte in gruppen.items():
        print(zeile(titel, kennzahlen(werte)))
    print()
    print("Daraus folgender relativer Fehler des geschaetzten Stroms "
          "(I = P / V, P ist exakt)")
    print("-" * 100)
    for titel, werte in strom_fehler.items():
        print(zeile(titel, kennzahlen(werte)))

    # Wie viel des Tages faellt ueberhaupt in verschattete Phasen
    schatten_punkte = [p for p in unter_last if verschattet(p)]
    if unter_last:
        print()
        print(f"Verschattete Messpunkte unter Last: {len(schatten_punkte)} von "
              f"{len(unter_last)} ({len(schatten_punkte)/len(unter_last)*100:.1f} %)")
        if schatten_punkte:
            print(f"davon im Fenster 12:30-15:30:       "
                  f"{sum(1 for p in schatten_punkte if WINDOW_LOCAL[0] <= p['stunde'] < WINDOW_LOCAL[1])}")
            print(f"Verschattung zeitlich von {min(p['zeit'] for p in schatten_punkte):%H:%M} "
                  f"bis {max(p['zeit'] for p in schatten_punkte):%H:%M} Ortszeit")

    # Gegenprobe: taugt der Leistungsanteil als Verschattungsmass fuer PV4?
    # Er braucht keine Spannungsannahme und muss deshalb sauber bleiben.
    print()
    print("Gegenprobe Leistungsanteil (braucht keine Spannungsannahme)")
    print("-" * 100)
    anteile = []
    for p in unter_last:
        median_p = statistics.median(p["p"])
        if median_p > 10:
            anteile.append(p["resid"] / median_p)
    if anteile:
        anteile.sort()
        print(f"P4 / Median(P1..P3):  n={len(anteile)}  "
              f"min {anteile[0]:.2f}  p05 {anteile[int(len(anteile)*0.05)]:.2f}  "
              f"Median {anteile[len(anteile)//2]:.2f}  "
              f"p95 {anteile[int(len(anteile)*0.95)]:.2f}  max {anteile[-1]:.2f}")

    # Ist der Leistungsanteil dem Stromanteil als Verschattungsmass
    # gleichwertig? Wenn ja, wird PV4 nach demselben Maßstab bewertet wie
    # PV1-3, obwohl es eine andere Groesse benutzt. Wenn nein, sind die vier
    # Module im Dashboard nicht vergleichbar und das muss in die Doku.
    print()
    print("Gleichwertigkeit der beiden Verschattungsmasse an PV1-3")
    print("-" * 100)
    einig = uneinig = 0
    abweichung: list[float] = []
    for p in unter_last:
        for k in range(3):
            i_andere = [p["i"][j] for j in range(3) if j != k]
            p_andere = [p["p"][j] for j in range(3) if j != k]
            i_ref = statistics.median(i_andere)
            p_ref = statistics.median(p_andere)
            if i_ref < 0.5 or p_ref < 15.0:
                continue
            i_anteil = p["i"][k] / i_ref
            p_anteil = p["p"][k] / p_ref
            abweichung.append((p_anteil - i_anteil) * 100.0)
            if (i_anteil < SHADE_ON) == (p_anteil < SHADE_ON):
                einig += 1
            else:
                uneinig += 1
    gesamt = einig + uneinig
    if gesamt:
        print(f"Verschattungsurteil identisch: {einig} von {gesamt} "
              f"({einig/gesamt*100:.2f} %), abweichend {uneinig}")
        k = kennzahlen(abweichung)
        print(f"Differenz Leistungsanteil minus Stromanteil: "
              f"Median {k['median']:.2f} Prozentpunkte, p95 {k['p95']:.2f}, "
              f"max {k['max']:.2f}, Bias {k['bias']:+.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
