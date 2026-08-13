"""Physikalische Kernrechnungen, die mehr als eine Plattform braucht.

Reine Funktionen ohne Home-Assistant-Bezug. Die Abregelungsschwelle stand
vorher nur im Binaersensor; seit es die theoretische Leistung gibt, braucht
sensor.py dieselbe Entscheidung. Zwei Kopien derselben Schwelle waeren ein
Fehler, der erst auffiele, wenn jemand nur eine davon aendert - deshalb hier
an genau einer Stelle.
"""
from __future__ import annotations

from .const import (
    CELL_OVER_AMBIENT,
    CURTAIL_VOC_FRACTION,
    MIN_CURRENT_FOR_RATIO,
    MODULE_TEMP_COEFF,
    MODULE_VOC_STC,
    MODULE_WP,
    REFERENZ_NAHE_ANTEIL,
)


def unshaded_reference(werte: list[float]) -> tuple[float, int]:
    """Unverschattete Strangleistung und wieviele Straenge sie tragen.

    Mittel aller Straenge, die innerhalb von REFERENZ_NAHE_ANTEIL des besten
    liegen. Liegt nur einer nah am besten, ist das Ergebnis genau dieser eine -
    der Fall, in dem der Schatten drei Straenge deckt und die Referenz nicht
    verwaessert werden darf.

    Der zweite Rueckgabewert ist der Vertrauensindikator: bei 4 liegen alle
    vier eng beieinander, dann ist entweder nichts verschattet oder alles.
    """
    bester = max(werte)
    nahe = [w for w in werte if w >= REFERENZ_NAHE_ANTEIL * bester]
    return sum(nahe) / len(nahe), len(nahe)


def klarhimmel_erwartung(poa_w_m2: float, module: int = 4) -> float:
    """Was die Anlage bei dieser Einstrahlung unter STC liefern wuerde, in W.

    Reine Geometrie mal Datenblatt-Nennleistung. Keine gelernte Groesse, damit
    die Aussage nicht am Lernstand der Prognose haengt. Der reale Ertrag liegt
    systematisch darunter (Temperatur, Einfallswinkel, Verschmutzung) - die
    Groesse taugt deshalb als Groessenordnung, nicht als Sollwert.
    """
    return module * MODULE_WP * poa_w_m2 / 1000.0


def curtail_threshold(ambient: float) -> float:
    """Spannungsschwelle in V, ab der der Arbeitspunkt Richtung Leerlauf laeuft.

    Die Zelltemperatur wird aus der Aussentemperatur geschaetzt und nicht aus
    der Spannung zurueckgerechnet: Letzteres waere zirkulaer, weil genau die
    Spannung gegen diese Schwelle geprueft wird.
    """
    cell = ambient + CELL_OVER_AMBIENT
    voc = MODULE_VOC_STC * (1.0 - MODULE_TEMP_COEFF * (cell - 25.0))
    return CURTAIL_VOC_FRACTION * voc


def is_curtailed(
    voltages: list[float | None],
    currents: list[float | None],
    ambient: float | None,
) -> bool | None:
    """Drosselt der Wechselrichter gerade alle Tracker gleichzeitig?

    Verlangt, dass ALLE Straenge oberhalb der Schwelle liegen. Ein einzelner
    verschatteter Strang loest das nicht aus - der faehrt zwar auch hoehere
    Spannung, aber seine Nachbarn nicht.

    `None` heisst **nicht entscheidbar** und ist ausdruecklich nicht `False`.
    Wer eine Rechnung darauf stuetzt, muss selbst entscheiden, ob er das
    Risiko eingeht; die theoretische Leistung tut es nicht.
    """
    if ambient is None:
        return None
    if any(v is None for v in voltages) or any(c is None for c in currents):
        return None

    threshold = curtail_threshold(ambient)
    # Nachts steht die Spannung ohne Last ebenfalls hoch. Ohne einen
    # Mindeststrom auf mindestens einem Strang waere jede Nacht eine
    # gemeldete Abregelung.
    producing = any(c >= MIN_CURRENT_FOR_RATIO for c in currents if c is not None)
    return producing and all(v >= threshold for v in voltages if v is not None)
