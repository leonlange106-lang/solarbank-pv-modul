"""Sonnenstand und geometrische Klarhimmelerwartung.

Dieses Modul enthaelt keine einzige empirische Groesse. Es liefert allein
die Geometrie: wo steht die Sonne, und wieviel Strahlung faellt daraus
rechnerisch auf die Modulebene, wenn nichts im Weg ist und der Himmel klar
ist. Das Ergebnis ist die Bezugsgroesse, gegen die alles Gelernte gemessen
wird.

Warum eigene Rechnung und nicht sun.sun: sun.sun liefert nur Auf- und
Untergang sowie die aktuelle Hoehe, aber keinen Azimut in die Zukunft. Die
Vorwaertssimulation braucht Sonnenstand und Einstrahlung fuer jeden
Viertelstundenschritt bis Sonnenuntergang.

Die absolute Hoehe der gerechneten Einstrahlung ist bewusst unkritisch.
Sie wird durch den gelernten Systemgain wegnormiert. Was zaehlt, ist
ausschliesslich der Verlauf ueber den Tag und ueber die Jahreszeit - und
der folgt aus Geometrie, nicht aus Kalibrierung.
"""

from __future__ import annotations

import datetime as dt
import math
from dataclasses import dataclass

from .const import (
    ALBEDO,
    ATMOSPHAERE_TAU,
    DIFFUSANTEIL_KLAR,
    SOLARKONSTANTE,
)


@dataclass(frozen=True, slots=True)
class Sonnenstand:
    """Hoehe und Azimut in Grad. Azimut im Uhrzeigersinn von Nord."""

    hoehe: float
    azimut: float


def _bruchteil_jahr(zeit: dt.datetime) -> float:
    """Jahreswinkel in Radiant, NOAA-Konvention."""
    tage_im_jahr = 366 if _schaltjahr(zeit.year) else 365
    n = zeit.timetuple().tm_yday
    return 2.0 * math.pi / tage_im_jahr * (n - 1 + (zeit.hour - 12) / 24.0)


def _schaltjahr(jahr: int) -> bool:
    return jahr % 4 == 0 and (jahr % 100 != 0 or jahr % 400 == 0)


def _zeitgleichung_und_deklination(zeit: dt.datetime) -> tuple[float, float]:
    """Zeitgleichung in Minuten und Deklination in Radiant (NOAA)."""
    g = _bruchteil_jahr(zeit)
    eqtime = 229.18 * (
        0.000075
        + 0.001868 * math.cos(g)
        - 0.032077 * math.sin(g)
        - 0.014615 * math.cos(2 * g)
        - 0.040849 * math.sin(2 * g)
    )
    decl = (
        0.006918
        - 0.399912 * math.cos(g)
        + 0.070257 * math.sin(g)
        - 0.006758 * math.cos(2 * g)
        + 0.000907 * math.sin(2 * g)
        - 0.002697 * math.cos(3 * g)
        + 0.001480 * math.sin(3 * g)
    )
    return eqtime, decl


def sonnenstand(zeit_utc: dt.datetime, breite: float, laenge: float) -> Sonnenstand:
    """Sonnenhoehe und -azimut zu einem UTC-Zeitpunkt.

    `zeit_utc` muss zeitzonenbehaftet und in UTC sein.
    """
    eqtime, decl = _zeitgleichung_und_deklination(zeit_utc)

    minuten_utc = (
        zeit_utc.hour * 60.0 + zeit_utc.minute + zeit_utc.second / 60.0
    )
    # Wahre Ortszeit in Minuten. `laenge` positiv nach Osten.
    wahre_zeit = minuten_utc + eqtime + 4.0 * laenge
    stundenwinkel = math.radians(wahre_zeit / 4.0 - 180.0)

    b = math.radians(breite)
    cos_zenit = (
        math.sin(b) * math.sin(decl)
        + math.cos(b) * math.cos(decl) * math.cos(stundenwinkel)
    )
    cos_zenit = max(-1.0, min(1.0, cos_zenit))
    zenit = math.acos(cos_zenit)
    hoehe = 90.0 - math.degrees(zenit)

    sin_zenit = math.sin(zenit)
    if sin_zenit < 1e-6:
        return Sonnenstand(hoehe=hoehe, azimut=180.0)

    cos_az = (math.sin(decl) - math.sin(b) * cos_zenit) / (math.cos(b) * sin_zenit)
    cos_az = max(-1.0, min(1.0, cos_az))
    azimut = math.degrees(math.acos(cos_az))
    # Vormittags (Stundenwinkel negativ) steht die Sonne im Osten.
    if stundenwinkel > 0:
        azimut = 360.0 - azimut

    return Sonnenstand(hoehe=hoehe, azimut=azimut)


def klarhimmel_poa(
    stand: Sonnenstand,
    zeit_utc: dt.datetime,
    neigung: float,
    modul_azimut: float,
) -> float:
    """Klarhimmel-Einstrahlung auf die Modulebene in W/m2.

    Meinel fuer den Direktstrahl, fester Diffusanteil, isotrope
    Transposition, Bodenreflexion mit Standardalbedo. Bewusst schlank:
    jede Verfeinerung wuerde am Ergebnis nichts aendern, weil der gelernte
    Systemgain und die gelernte Tagesform den Rest tragen.

    Die Rueckseite der bifazialen Module wird NICHT gerechnet. Ihr Beitrag
    steckt vollstaendig im gelernten Systemgain.
    """
    if stand.hoehe <= 0.0:
        return 0.0

    sin_h = math.sin(math.radians(stand.hoehe))
    if sin_h <= 0.0:
        return 0.0

    # Luftmasse nach Kasten/Young. Bleibt auch bei sehr flacher Sonne endlich.
    luftmasse = 1.0 / (
        sin_h + 0.50572 * (stand.hoehe + 6.07995) ** -1.6364
    )

    tage_im_jahr = 366 if _schaltjahr(zeit_utc.year) else 365
    n = zeit_utc.timetuple().tm_yday
    e0 = SOLARKONSTANTE * (
        1.0 + 0.033 * math.cos(2.0 * math.pi * n / tage_im_jahr)
    )

    dni = e0 * ATMOSPHAERE_TAU ** (luftmasse**0.678)
    dhi = DIFFUSANTEIL_KLAR * dni * sin_h          # auf die Horizontale
    ghi = dni * sin_h + dhi

    b = math.radians(neigung)
    cos_einfall = sin_h * math.cos(b) + math.cos(
        math.radians(stand.hoehe)
    ) * math.sin(b) * math.cos(math.radians(stand.azimut - modul_azimut))

    direkt = dni * max(cos_einfall, 0.0)
    diffus = dhi * (1.0 + math.cos(b)) / 2.0
    boden = ghi * ALBEDO * (1.0 - math.cos(b)) / 2.0
    return direkt + diffus + boden


def tageslauf(
    tag: dt.date,
    breite: float,
    laenge: float,
    neigung: float,
    modul_azimut: float,
    schritt_min: int = 15,
) -> list[tuple[dt.datetime, Sonnenstand, float]]:
    """Der ganze Tag in Schritten: Zeitpunkt, Sonnenstand, Klarhimmel-POA.

    Zeitpunkte sind UTC und markieren jeweils die Mitte des Intervalls.
    """
    raus: list[tuple[dt.datetime, Sonnenstand, float]] = []
    basis = dt.datetime(tag.year, tag.month, tag.day, tzinfo=dt.timezone.utc)
    schritte = (24 * 60) // schritt_min
    for i in range(schritte):
        t = basis + dt.timedelta(minutes=(i + 0.5) * schritt_min)
        stand = sonnenstand(t, breite, laenge)
        poa = klarhimmel_poa(stand, t, neigung, modul_azimut)
        raus.append((t, stand, poa))
    return raus


def sonnenauf_und_untergang(
    tag: dt.date, breite: float, laenge: float
) -> tuple[dt.datetime | None, dt.datetime | None]:
    """Auf- und Untergang als UTC-Zeitpunkte, astronomisch gerechnet.

    Zenitwinkel 90.833 Grad: geometrischer Horizont plus Refraktion plus
    scheinbarer Sonnenradius. Gibt (None, None) bei Polartag oder -nacht.
    """
    mittag = dt.datetime(tag.year, tag.month, tag.day, 12, tzinfo=dt.timezone.utc)
    eqtime, decl = _zeitgleichung_und_deklination(mittag)
    b = math.radians(breite)

    nenner = math.cos(b) * math.cos(decl)
    if abs(nenner) < 1e-9:
        return None, None
    cos_ha = math.cos(math.radians(90.833)) / nenner - math.tan(b) * math.tan(decl)
    if cos_ha > 1.0 or cos_ha < -1.0:
        return None, None
    ha = math.degrees(math.acos(cos_ha))

    mitternacht = dt.datetime(tag.year, tag.month, tag.day, tzinfo=dt.timezone.utc)
    auf = mitternacht + dt.timedelta(minutes=720 - 4 * (laenge + ha) - eqtime)
    unter = mitternacht + dt.timedelta(minutes=720 - 4 * (laenge - ha) - eqtime)
    return auf, unter
