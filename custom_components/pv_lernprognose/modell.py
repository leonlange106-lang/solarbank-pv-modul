"""Vorwaertssimulation des Speichers.

Das alte Modell rechnete die kuenftige Erzeugung als `cos^EXPONENT` um
einen von Forecast.Solar gemeldeten Spitzenzeitpunkt und korrigierte den
Pegel mit einem Faktor k aus der aktuellen Messung. docs/PROGNOSE.md hat
gezeigt, warum das nicht traegt: die reale Kurve ist ein Plateau mit einer
Verschattungskerbe zwischen 12:30 und 15:30, keine symmetrische Glocke,
und k las die Kerbe als Bewoelkung und rechnete sie auf den ganzen
Resttag hoch.

Hier wird stattdessen gerechnet

    P(t) = Systemgain * POA_klar(t) * Tagesform(Azimut(t)) * Truebung(t)

  Systemgain   gelernt, W je W/m2 - enthaelt Modulflaeche, Wirkungsgrad
               und den bifazialen Mehrertrag
  POA_klar     reine Geometrie, keine freien Parameter
  Tagesform    gelernt je Sonnenazimut - enthaelt die Verschattung und
               wandert mit dem Sonnenlauf durch die Jahreszeiten
  Truebung     der einzige tagesaktuelle Faktor: Bewoelkung

Damit misst die Truebung endlich das, wofuer k gedacht war. Die
Verschattung steckt bereits in der Form, also kann die Truebung sie nicht
mehr mit Bewoelkung verwechseln.

Tag und Nacht sind nicht mehr zwei getrennte Zweige, sondern ein
durchgehender Lauf ueber 24 Stunden. Nachts ist POA null, damit ist die
Erzeugung null, und die Bilanz entlaedt von selbst.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

from .const import (
    SCHRITT_MIN,
    TRUEBUNG_MAX,
    TRUEBUNG_MIN,
    TRUEBUNG_TAU_MIN,
)
from .sonne import klarhimmel_poa, sonnenstand


@dataclass
class Umgebung:
    """Alles, was die Simulation ueber Anlage und Standort wissen muss."""

    breite: float
    laenge: float
    neigung: float
    modul_azimut: float

    kapazitaet_kwh: float
    ac_grenze_w: float
    max_ladeleistung_w: float
    soc_max: float
    soc_min: float

    eta: float
    gain: float
    form: dict[int, float]
    hauslast_werktag: list[float]
    hauslast_wochenende: list[float]

    # Truebung
    truebung_live: float | None      # aus der aktuellen Messung
    truebung_prognose: float         # aus Forecast.Solar mal Pegel, heute
    truebung_prognose_morgen: float  # dasselbe fuer morgen


@dataclass
class Lauf:
    """Ergebnis einer Vorwaertssimulation."""

    bahn: list[tuple[dt.datetime, float]] = field(default_factory=list)
    soc_max: float = 0.0
    t_soc_max: dt.datetime | None = None
    t_voll: dt.datetime | None = None
    t_leer: dt.datetime | None = None
    t_ziel: dt.datetime | None = None
    ertrag_rest_kwh: float = 0.0
    klar_rest_kwh: float = 0.0
    soc_bei_sonnenaufgang: float | None = None
    naechster_aufgang: dt.datetime | None = None


def _hauslast(umgebung: Umgebung, zeit_lokal: dt.datetime) -> float:
    profil = (
        umgebung.hauslast_wochenende
        if zeit_lokal.weekday() >= 5
        else umgebung.hauslast_werktag
    )
    return profil[zeit_lokal.hour]


def _form_bei(form: dict[int, float], azimut: float) -> float:
    from .schaetzer import azimut_fach

    fach = azimut_fach(azimut)
    if fach is None or not form:
        return 1.0
    if fach in form:
        return form[fach]
    links = max((f for f in form if f < fach), default=None)
    rechts = min((f for f in form if f > fach), default=None)
    if links is not None and rechts is not None:
        anteil = (fach - links) / (rechts - links)
        return form[links] * (1 - anteil) + form[rechts] * anteil
    if links is not None:
        return form[links]
    if rechts is not None:
        return form[rechts]
    return 1.0


def klarleistung(
    umgebung: Umgebung, zeit_utc: dt.datetime
) -> tuple[float, float, float]:
    """Klarhimmelerwartung einschliesslich Verschattung.

    Gibt (Leistung in W, POA in W/m2, Sonnenazimut) zurueck.
    """
    stand = sonnenstand(zeit_utc, umgebung.breite, umgebung.laenge)
    if stand.hoehe <= 0.0:
        return 0.0, 0.0, stand.azimut
    poa = klarhimmel_poa(stand, zeit_utc, umgebung.neigung, umgebung.modul_azimut)
    form = _form_bei(umgebung.form, stand.azimut)
    return umgebung.gain * poa * form, poa, stand.azimut


def _truebung(umgebung: Umgebung, jetzt: dt.datetime, t: dt.datetime) -> float:
    """Truebung fuer einen Zeitpunkt in der Zukunft.

    Die Live-Messung sagt ueber die naechste Viertelstunde viel und ueber
    den Abend fast nichts. Deshalb faellt ihr Gewicht exponentiell ab und
    die Wettervorhersage uebernimmt. Die Halbwertszeit ist ein
    Meta-Parameter und der am schwaechsten belegte des Verfahrens.
    """
    basis = (
        umgebung.truebung_prognose
        if t.date() == jetzt.date()
        else umgebung.truebung_prognose_morgen
    )
    if umgebung.truebung_live is None:
        return min(max(basis, TRUEBUNG_MIN), TRUEBUNG_MAX)
    minuten = max((t - jetzt).total_seconds() / 60.0, 0.0)
    gewicht = 0.5 ** (minuten / TRUEBUNG_TAU_MIN)
    wert = basis + (umgebung.truebung_live - basis) * gewicht
    return min(max(wert, TRUEBUNG_MIN), TRUEBUNG_MAX)


def simuliere(
    umgebung: Umgebung,
    jetzt: dt.datetime,
    soc: float,
    zeitzone: dt.tzinfo,
    ziel_soc: float | None = None,
    stunden: float = 24.0,
) -> Lauf:
    """Rechnet den Speicher von jetzt an vorwaerts.

    `jetzt` und alle Zeiten in `Lauf` sind zeitzonenbehaftet.
    """
    lauf = Lauf()
    kap = max(umgebung.kapazitaet_kwh, 0.1)
    oben = umgebung.soc_max / 100.0 * kap
    unten = umgebung.soc_min / 100.0 * kap
    kwh = min(max(soc / 100.0 * kap, 0.0), oben)

    schritt_h = SCHRITT_MIN / 60.0
    schritte = int(stunden * 60 / SCHRITT_MIN)

    lauf.soc_max = kwh / kap * 100.0
    lauf.t_soc_max = jetzt
    lauf.bahn.append((jetzt, round(kwh / kap * 100.0, 1)))

    if soc >= umgebung.soc_max - 0.01:
        lauf.t_voll = jetzt
    if ziel_soc is not None and soc >= ziel_soc:
        lauf.t_ziel = jetzt

    voriger_stand_hoehe = None

    for i in range(schritte):
        mitte = jetzt + dt.timedelta(minutes=(i + 0.5) * SCHRITT_MIN)
        ende = jetzt + dt.timedelta(minutes=(i + 1) * SCHRITT_MIN)
        mitte_utc = mitte.astimezone(dt.timezone.utc)

        p_klar, poa, _azimut = klarleistung(umgebung, mitte_utc)
        c = _truebung(umgebung, jetzt, mitte)
        p_pv = p_klar * c

        lauf.klar_rest_kwh += p_klar * schritt_h / 1000.0
        lauf.ertrag_rest_kwh += p_pv * schritt_h / 1000.0

        last = _hauslast(umgebung, mitte.astimezone(zeitzone))
        # Das System liefert hoechstens seine AC-Grenze ins Haus; was
        # darueber hinaus gebraucht wird, kommt aus dem Netz.
        ac_ausgang = min(last, umgebung.ac_grenze_w)
        netto = p_pv - ac_ausgang

        if netto > 0.0:
            laden = min(netto, umgebung.max_ladeleistung_w)
            kwh += laden * schritt_h / 1000.0 * umgebung.eta
        else:
            entladen = min(-netto, umgebung.ac_grenze_w)
            kwh -= entladen * schritt_h / 1000.0 / umgebung.eta

        kwh = min(max(kwh, unten), oben)
        prozent = kwh / kap * 100.0
        lauf.bahn.append((ende, round(prozent, 1)))

        if kwh > lauf.soc_max / 100.0 * kap + 1e-9:
            lauf.soc_max = prozent
            lauf.t_soc_max = ende
        if lauf.t_voll is None and kwh >= oben - 1e-6:
            lauf.t_voll = ende
        if lauf.t_leer is None and kwh <= unten + 1e-6 and p_pv < 20.0:
            lauf.t_leer = ende
        if ziel_soc is not None and lauf.t_ziel is None and prozent >= ziel_soc:
            lauf.t_ziel = ende

        # Sonnenaufgang: erster Schritt mit nennenswerter Klarhimmelleistung
        # nach einer Phase ohne.
        if lauf.naechster_aufgang is None:
            if voriger_stand_hoehe is not None and voriger_stand_hoehe <= 0 and p_klar > 10.0:
                lauf.naechster_aufgang = ende
                lauf.soc_bei_sonnenaufgang = prozent
        voriger_stand_hoehe = p_klar if p_klar > 10.0 else 0.0

    return lauf


def _dauer(von: dt.datetime, bis: dt.datetime) -> str:
    minuten = max(int(round((bis - von).total_seconds() / 60.0)), 0)
    return f"{minuten // 60}:{minuten % 60:02d} h"


def formuliere(
    lauf: Lauf,
    jetzt: dt.datetime,
    soc: float,
    umgebung: Umgebung,
    zeitzone: dt.tzinfo,
) -> str:
    """Der Sensortext.

    Wortlaut und Faelle absichtlich identisch zum bisherigen Sensor, damit
    der Umbau von sensor.nulleinspeisung_speicher_prognose ein reiner
    Logiktausch ist und Dashboards unveraendert bleiben.
    """
    def uhr(t: dt.datetime) -> str:
        return t.astimezone(zeitzone).strftime("%H:%M")

    if soc >= umgebung.soc_max - 0.01:
        return "Speicher voll"

    tagmodus = lauf.klar_rest_kwh > 0.15

    if tagmodus:
        if lauf.t_voll is not None:
            return f"voll um {uhr(lauf.t_voll)} ({_dauer(jetzt, lauf.t_voll)})"
        if lauf.t_soc_max is not None and lauf.soc_max > soc + 0.5:
            return (
                f"heute nur ca. {int(round(lauf.soc_max))} %, "
                f"Hoechststand gegen {uhr(lauf.t_soc_max)}"
            )

    if soc <= umgebung.soc_min + 0.01:
        return "Untergrenze erreicht"

    if lauf.t_leer is not None:
        t = lauf.t_leer.astimezone(zeitzone)
        morgen = "morgen " if t.date() != jetzt.astimezone(zeitzone).date() else ""
        return f"leer um {morgen}{uhr(lauf.t_leer)} ({_dauer(jetzt, lauf.t_leer)})"

    if lauf.soc_bei_sonnenaufgang is not None:
        return (
            "reicht bis Sonnenaufgang "
            f"(dann ca. {int(round(lauf.soc_bei_sonnenaufgang))} %)"
        )
    return f"reicht durch (ca. {int(round(lauf.bahn[-1][1]))} % in 24 h)"
