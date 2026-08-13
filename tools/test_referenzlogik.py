"""Prueft die Entscheidungslogik der theoretischen Leistung ohne Home Assistant.

Drei Dinge: die Abregelungssperre, die unverschattete Referenz und die
Blindfleck-Erkennung.

Echte Abregelung laesst sich nicht provozieren - sie tritt bei SOC 100 % auf,
und ein Schreibzugriff auf den Wechselrichter ist ausgeschlossen. Also werden
die reinen Funktionen geprueft; sie sind der einzige Ort, an dem diese
Entscheidungen fallen.

    python tools/test_referenzlogik.py
"""
import sys
import types
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "custom_components"))

# physik.py importiert relativ aus .const - als Paket laden.
pkg = types.ModuleType("solarbank_pv")
pkg.__path__ = [str(REPO / "custom_components" / "solarbank_pv")]
sys.modules["solarbank_pv"] = pkg

from solarbank_pv.const import (  # noqa: E402
    KLARHIMMEL_BLIND_ANTEIL,
    MIN_CURRENT_FOR_RATIO,
    MODULE_WP,
)
from solarbank_pv.physik import (  # noqa: E402
    curtail_threshold,
    is_curtailed,
    klarhimmel_erwartung,
    unshaded_reference,
)

fehler = 0


def pruefe(name, ist, soll):
    global fehler
    ok = ist == soll
    if not ok:
        fehler += 1
    print(f"  [{'ok ' if ok else 'FEHL'}] {name}: {ist!r} (erwartet {soll!r})")


AMBIENT = 30.9  # Aussentemperatur zur Laufzeit der Gegenprobe

print("=== Abregelungssperre ===")
schwelle = curtail_threshold(AMBIENT)
print(f"Schwelle bei {AMBIENT} Grad C: {schwelle:.1f} V")
print("Live gemeldet von binary_sensor.pv_abregelung_erkannt: 33.9 V")
pruefe("Schwelle trifft die Live-Anzeige", round(schwelle, 1), 33.9)

pruefe(
    "Normalbetrieb (MPP, unter der Schwelle) -> kein Alarm",
    is_curtailed([29.0, 33.4, 30.7], [13.7, 1.2, 11.1], AMBIENT),
    False,
)
pruefe(
    "ALLE Spannungen ueber der Schwelle, Strom fliesst -> Alarm",
    is_curtailed([34.5, 34.8, 34.6], [2.0, 2.1, 1.9], AMBIENT),
    True,
)
pruefe(
    "ein einzelner verschatteter Strang -> kein Alarm",
    is_curtailed([34.5, 30.0, 30.2], [2.0, 12.0, 11.5], AMBIENT),
    False,
)
pruefe(
    "Nacht: Leerlaufspannung hoch, kein Strom -> kein Alarm",
    is_curtailed([36.0, 36.1, 36.0], [0.0, 0.0, 0.0], AMBIENT),
    False,
)
pruefe(
    f"Grenzfall knapp unter {MIN_CURRENT_FOR_RATIO} A bleibt Nacht",
    is_curtailed([36.0, 36.1, 36.0], [0.4, 0.4, 0.4], AMBIENT),
    False,
)

print("\nNicht entscheidbar -> None, ausdruecklich nicht False:")
pruefe("Aussentemperatur fehlt", is_curtailed([34.5, 34.8, 34.6], [2.0, 2.1, 1.9], None), None)
pruefe("Strangspannung fehlt", is_curtailed([34.5, None, 34.6], [2.0, 2.1, 1.9], AMBIENT), None)
pruefe("Strangstrom fehlt", is_curtailed([34.5, 34.8, 34.6], [2.0, None, 1.9], AMBIENT), None)

print("\nKaeltere Luft -> hoehere Voc -> hoehere Schwelle:")
kalt, warm = curtail_threshold(0.0), curtail_threshold(35.0)
print(f"  0 Grad C: {kalt:.2f} V | 35 Grad C: {warm:.2f} V")
pruefe("Schwelle faellt mit steigender Temperatur", kalt > warm, True)
pruefe(
    "dieselben 34.5 V sind bei 0 Grad C KEINE Abregelung",
    is_curtailed([34.5, 34.8, 34.6], [2.0, 2.1, 1.9], 0.0),
    False,
)

print("\n=== Unverschattete Referenz: Mittel der Straenge >= 90 % des besten ===")
ref, n = unshaded_reference([400.0, 395.0, 405.0, 398.0])
pruefe("alle vier eng -> Mittel, alle vier tragen", (round(ref, 2), n), (399.5, 4))

ref, n = unshaded_reference([400.0, 50.0, 60.0, 55.0])
pruefe("nur einer unverschattet -> genau dieser, kein Verwaessern", (ref, n), (400.0, 1))

ref, n = unshaded_reference([400.0, 390.0, 60.0, 55.0])
pruefe("zwei unverschattet -> deren Mittel", (round(ref, 1), n), (395.0, 2))

# Der entscheidende Unterschied zum zweithoechsten: deckt der Schatten drei
# Straenge, waere der zweithoechste selbst verschattet. Die Referenz fiele
# zusammen und der Verlust wuerde massiv unterschaetzt - also in Richtung
# "kein Problem", genau die falsche Richtung.
zweithoechster = sorted([400.0, 50.0, 60.0, 55.0], reverse=True)[1]
pruefe("zweithoechster waere hier 60 W statt 400 W", zweithoechster, 60.0)
pruefe("Mittel-Variante irrt dort nicht", unshaded_reference([400.0, 50.0, 60.0, 55.0])[0], 400.0)

print("\n=== Klarhimmelerwartung: Geometrie mal Datenblatt, nichts Gelerntes ===")
pruefe("Modulnennleistung aus Vmp x Imp", round(MODULE_WP, 1), 500.0)
pruefe("bei 1000 W/m2, vier Module", round(klarhimmel_erwartung(1000.0)), 2000)
pruefe("bei 908.4 W/m2 (Live-Messwert 13.08.)", round(klarhimmel_erwartung(908.4)), 1817)

print("\n=== Blindfleck: alle vier gleichzeitig verschattet ===")
print(f"Regel: alle vier tragen die Referenz UND theoretisch < "
      f"{KLARHIMMEL_BLIND_ANTEIL:.0%} der Klarhimmelerwartung -> keine Aussage.")

anteil_live = 1650.0 / klarhimmel_erwartung(908.4)
print(f"  klarer Tag, live gemessen: Anteil {anteil_live:.3f}")
pruefe("klarer Tag liegt weit ueber der Schwelle", anteil_live > KLARHIMMEL_BLIND_ANTEIL, True)

anteil_blind = 330.0 / klarhimmel_erwartung(908.4)
print(f"  alle vier tief:            Anteil {anteil_blind:.3f}")
pruefe("wird als blind erkannt", anteil_blind < KLARHIMMEL_BLIND_ANTEIL, True)

# Tief allein genuegt nicht: sticht ein Strang heraus, gibt es eine
# unverschattete Referenz und das Verfahren ist nicht blind.
_ref, n_traeger = unshaded_reference([400.0, 60.0, 55.0, 58.0])
pruefe("ein Strang sticht heraus -> nicht blind, egal wie tief", n_traeger < 4, True)

print()
if fehler:
    print(f"FEHLGESCHLAGEN: {fehler} Pruefung(en)")
    sys.exit(1)
print("Alle Pruefungen bestanden.")
