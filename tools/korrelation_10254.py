"""Ist 10254/10255 dieselbe Groesse wie 10008/10009, nur mit umgekehrtem Vorzeichen?

Die Vorzeichenumkehr ist trivial zu sehen. Die IDENTITAET ist es nicht: eine
Einzelmessung belegt sie nie, weil 10008 und 10254 in derselben Sekunde um
zweistellige Prozentbetraege auseinanderliegen koennen, wenn sie aus
verschiedenen Abfragezyklen stammen.

Dieses Skript umgeht das Problem: tools/rohdaten/pv4_tag.jsonl haelt beide
Registerpaare je Messpunkt im SELBEN Zyklus. Damit ist die Frage eine
Regression, keine Stichprobe.

Entscheidungsregel, analog zum Nachweis fuer 10205:
  Steigung -1,00 und r ~ 1  ->  dieselbe Groesse, Vorzeichen invertiert
  Steigung deutlich ungleich -1  ->  eine ANDERE Groesse, etwa AC-seitig
                                     vor Wandlungsverlust

Rein lesend, arbeitet nur auf aufgezeichneten Daten.
"""
from __future__ import annotations

import json
import pathlib
import statistics

HERE = pathlib.Path(__file__).parent
DATA = HERE / "rohdaten" / "pv4_tag.jsonl"


def i32(hi: int, lo: int) -> int:
    """Big-Endian INT32 aus zwei Registern, registers[0] = High-Word."""
    raw = (hi << 16) | lo
    return raw - 0x100000000 if raw & 0x80000000 else raw


def pearson(xs: list[float], ys: list[float]) -> float:
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    return sxy / (sxx * syy) ** 0.5 if sxx and syy else float("nan")


def regress(xs: list[float], ys: list[float]) -> tuple[float, float]:
    """Kleinste Quadrate, y = a*x + b."""
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    sxx = sum((x - mx) ** 2 for x in xs)
    a = sxy / sxx
    return a, my - a * mx


def bericht(titel: str, xs: list[float], ys: list[float]) -> None:
    if len(xs) < 10:
        print(f"\n{titel}: nur {len(xs)} Punkte, uebersprungen")
        return
    r = pearson(xs, ys)
    a, b = regress(xs, ys)
    # Residuen gegen die Hypothese "exakt invertiert"
    res = [y - (-x) for x, y in zip(xs, ys)]
    absres = [abs(v) for v in res]
    print(f"\n{titel}  (n = {len(xs)})")
    print(f"  Wertebereich 10008 : {min(xs):8.0f} .. {max(xs):8.0f} W")
    print(f"  Wertebereich 10254 : {min(ys):8.0f} .. {max(ys):8.0f} W")
    print(f"  Korrelation r      : {r:+.5f}")
    print(f"  Steigung           : {a:+.4f}   (Hypothese: -1,0000)")
    print(f"  Achsenabschnitt    : {b:+.1f} W")
    print(f"  Residuum |10254 + 10008|:")
    print(f"      Median {statistics.median(absres):6.1f} W"
          f"   Mittel {statistics.fmean(absres):6.1f} W"
          f"   max {max(absres):6.1f} W")
    exakt = sum(1 for v in res if v == 0)
    print(f"  exakt deckungsgleich: {exakt} von {len(res)}"
          f"  ({100 * exakt / len(res):.1f} %)")


def main() -> int:
    x_all: list[float] = []
    y_all: list[float] = []
    x_laden: list[float] = []
    y_laden: list[float] = []
    x_entladen: list[float] = []
    y_entladen: list[float] = []
    fehlend = 0

    with DATA.open(encoding="utf-8") as fh:
        for zeile in fh:
            satz = json.loads(zeile)
            if not satz.get("ok"):
                continue
            regs = satz.get("regs") or {}
            try:
                bat = i32(regs["10008"], regs["10009"])
                chg = i32(regs["10254"], regs["10255"])
            except KeyError:
                fehlend += 1
                continue
            x_all.append(bat)
            y_all.append(chg)
            if bat < 0:               # negativ = laden, laut Registerkarte
                x_laden.append(bat)
                y_laden.append(chg)
            elif bat > 0:
                x_entladen.append(bat)
                y_entladen.append(chg)

    print(f"Datei: {DATA.name}")
    print(f"verwertbare Messpunkte: {len(x_all)}   ohne beide Paare: {fehlend}")

    bericht("ALLE PUNKTE", x_all, y_all)
    bericht("NUR LADEN (10008 < 0)", x_laden, y_laden)
    bericht("NUR ENTLADEN (10008 > 0)", x_entladen, y_entladen)

    ruhe = sum(1 for v in x_all if v == 0)
    print(f"\nPunkte mit 10008 = 0: {ruhe}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
