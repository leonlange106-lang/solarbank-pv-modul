"""Prueft die Abregelungssperre an der reinen Funktion, ohne Home Assistant.

Echte Abregelung laesst sich nicht provozieren: sie tritt bei SOC 100 % auf,
und ein Schreibzugriff auf den Wechselrichter ist ausgeschlossen. Also wird
die Entscheidungsfunktion selbst geprueft - sie ist der einzige Ort, an dem
die Sperre faellt.
"""
import sys
import types
from pathlib import Path

REPO = Path(r"C:\Users\User\solarbank-pv-modul")
sys.path.insert(0, str(REPO / "custom_components"))

# physik.py importiert relativ aus .const - als Paket laden.
pkg = types.ModuleType("solarbank_pv")
pkg.__path__ = [str(REPO / "custom_components" / "solarbank_pv")]
sys.modules["solarbank_pv"] = pkg

from solarbank_pv.physik import curtail_threshold, is_curtailed  # noqa: E402
from solarbank_pv.const import MIN_CURRENT_FOR_RATIO  # noqa: E402

fehler = 0


def pruefe(name, ist, soll):
    global fehler
    ok = ist == soll
    if not ok:
        fehler += 1
    print(f"  [{'ok ' if ok else 'FEHL'}] {name}: {ist!r} (erwartet {soll!r})")


AMBIENT = 30.9          # Aussentemperatur zur Laufzeit der Gegenprobe
schwelle = curtail_threshold(AMBIENT)
print(f"Schwelle bei {AMBIENT} °C Aussentemperatur: {schwelle:.1f} V")
print("Live gemeldet von binary_sensor.pv_abregelung_erkannt: 33.9 V")
pruefe("Schwelle trifft die Live-Anzeige", round(schwelle, 1), 33.9)

print("\nNormalbetrieb (MPP, Spannungen unter der Schwelle):")
pruefe(
    "kein Alarm",
    is_curtailed([29.0, 33.4, 30.7], [13.7, 1.2, 11.1], AMBIENT),
    False,
)

print("\nAbregelung (ALLE Spannungen ueber der Schwelle, Strom fliesst):")
pruefe(
    "Alarm",
    is_curtailed([34.5, 34.8, 34.6], [2.0, 2.1, 1.9], AMBIENT),
    True,
)

print("\nEin einzelner verschatteter Strang faehrt auch hoehere Spannung:")
pruefe(
    "kein Alarm, weil nicht ALLE ueber der Schwelle",
    is_curtailed([34.5, 30.0, 30.2], [2.0, 12.0, 11.5], AMBIENT),
    False,
)

print("\nNacht: Leerlaufspannung hoch, aber kein Strom:")
pruefe(
    "kein Alarm",
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
print(f"  0 °C: {kalt:.2f} V | 35 °C: {warm:.2f} V")
pruefe("Schwelle faellt mit steigender Temperatur", kalt > warm, True)
pruefe(
    "dieselben 34.5 V sind bei 0 °C KEINE Abregelung",
    is_curtailed([34.5, 34.8, 34.6], [2.0, 2.1, 1.9], 0.0),
    False,
)

print()
if fehler:
    print(f"FEHLGESCHLAGEN: {fehler} Pruefung(en)")
    sys.exit(1)
print("Alle Pruefungen bestanden.")
