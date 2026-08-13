"""Empirische Kalibrierung von sensor.nulleinspeisung_speicher_prognose.

Baut das Jinja-Modell in Python nach und faehrt es gegen die HA-Historie
(08.-13.08.2026). Bestimmt EXPONENT, KMIN/KMAX und das Mittelungsfenster
fuer `gemessen`.

READ-ONLY. Aendert nichts in Home Assistant. Liest ausschliesslich die
beiden Datei-Caches, die aus der HA-Historie gezogen wurden:
  prognose_daten.json       (Stundenwerte Netz / Hauslast / PV)
  prognose_daten_5min.json  (5-Minuten-Werte SOC / PV, Forecast.Solar-Rohhistorie)

Aufruf:
    python backtest_prognose.py            # kompletter Bericht
    python backtest_prognose.py --kurz     # nur die Kerntabellen
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import pathlib
import statistics as st

HERE = pathlib.Path(__file__).parent
CACHE_STD = HERE / "prognose_daten.json"
CACHE_5MIN = HERE / "prognose_daten_5min.json"

# --------------------------------------------------------------------------
# Anlage und Standort
# --------------------------------------------------------------------------
LAT, LON = 51.6739, 7.8150          # Hamm / NRW
TZ = dt.timezone(dt.timedelta(hours=2))   # CEST; im ganzen Auswertefenster gueltig

CAP = 5.1        # kWh nutzbar
SMAX = 100.0     # %
SMIN = 12.0      # %
ETA = 0.95
MAXENTL = 800.0  # W AC-Begrenzung

# Vorbelegte Werte des laufenden Sensors (zum Vergleich)
ALT_EXPONENT = 2.0
ALT_KMIN, ALT_KMAX = 0.6, 1.6
ALT_FENSTER = 20  # Minuten


# --------------------------------------------------------------------------
# Sonnenstand (NOAA), astronomisch gerechnet - nicht aus der Historie
# --------------------------------------------------------------------------
def _sonnen_eckdaten(datum: dt.date) -> tuple[float, float]:
    """Sonnenauf- und -untergang als Unix-Sekunden."""
    n = datum.timetuple().tm_yday
    g = 2.0 * math.pi / 365.0 * (n - 1 + 0.5)   # Tagesmitte
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
    lat = math.radians(LAT)
    # Zenit 90.833 Grad: geometrischer Horizont + Refraktion + Sonnenradius
    cos_ha = math.cos(math.radians(90.833)) / (math.cos(lat) * math.cos(decl)) - math.tan(lat) * math.tan(decl)
    cos_ha = max(-1.0, min(1.0, cos_ha))
    ha = math.degrees(math.acos(cos_ha))

    mitternacht_utc = dt.datetime(datum.year, datum.month, datum.day, tzinfo=dt.timezone.utc).timestamp()
    auf = mitternacht_utc + (720 - 4 * (LON + ha) - eqtime) * 60
    unter = mitternacht_utc + (720 - 4 * (LON - ha) - eqtime) * 60
    return auf, unter


def sonnenhoechststand(datum: dt.date) -> float:
    auf, unter = _sonnen_eckdaten(datum)
    return (auf + unter) / 2.0


# --------------------------------------------------------------------------
# Daten laden
# --------------------------------------------------------------------------
def lade() -> tuple[dict, dict]:
    with CACHE_STD.open(encoding="utf-8") as f:
        std = json.load(f)
    with CACHE_5MIN.open(encoding="utf-8") as f:
        fein = json.load(f)
    # Integritaetspruefung: jeder Stundenblock genau 12 Werte, 14 Bloecke je Tag
    for tag, d in fein["tage"].items():
        for reihe in ("soc", "pv"):
            bloecke = d[reihe]
            assert len(bloecke) == 14, f"{tag}/{reihe}: {len(bloecke)} Bloecke statt 14"
            for i, b in enumerate(bloecke):
                assert len(b) == 12, f"{tag}/{reihe} Block {i}: {len(b)} Werte statt 12"
    return std, fein


def reihe_5min(fein: dict, tag: str, art: str) -> list[tuple[float, float]]:
    """Flache Liste (unix_sekunden, wert) aus den Stundenbloecken."""
    d = dt.date.fromisoformat(tag)
    basis = dt.datetime(d.year, d.month, d.day, fein["_start_stunde"], tzinfo=TZ).timestamp()
    schritt = fein["_schritt_min"] * 60
    raus = []
    for bi, block in enumerate(fein["tage"][tag][art]):
        for wi, v in enumerate(block):
            raus.append((basis + (bi * 12 + wi) * schritt, float(v)))
    return raus


def _zeit(tag: str, hhmm: str) -> float:
    d = dt.date.fromisoformat(tag)
    h, m = (int(x) for x in hhmm.split(":"))
    return dt.datetime(d.year, d.month, d.day, h, m, tzinfo=TZ).timestamp()


def stufenwert(paare: list[tuple[float, float]], t: float):
    """Letzter Wert mit Zeitstempel <= t (Zustandssensor haelt seinen Wert)."""
    treffer = None
    for ts, v in paare:
        if ts <= t:
            treffer = v
        else:
            break
    return treffer


# --------------------------------------------------------------------------
# Hauslastprofil
# --------------------------------------------------------------------------
def hauslastprofil(std: dict) -> dict:
    """Profil je Stunde in W aus verschiedenen Quellen.

    'juli_median' / 'juli_mittel': aus sensor.stromleser_emh_power vor der
    Solarbank-Inbetriebnahme (20.07. - 08.08. 12:00). In diesem Fenster gab es
    keine PV, also ist die Netzleistung identisch mit der Hauslast.

    'vorbelegt': Mittel ueber 11./12.08. aus startseite_last - das ist das
    Profil, das im Sensor steht (und die Reglertests enthaelt).
    """
    grenze = _zeit("2026-08-08", "12:00")
    nach_stunde: dict[int, list[float]] = {h: [] for h in range(24)}
    for ts, w in std["netz_stunde"]:
        if ts >= grenze:
            continue
        h = dt.datetime.fromtimestamp(ts, TZ).hour
        nach_stunde[h].append(w)

    juli_median = {h: st.median(v) for h, v in nach_stunde.items() if v}
    juli_mittel = {h: st.fmean(v) for h, v in nach_stunde.items() if v}
    stichprobe = {h: len(v) for h, v in nach_stunde.items()}

    # vorbelegt: startseite_last, nur 11. und 12.08.
    vor: dict[int, list[float]] = {h: [] for h in range(24)}
    for ts, w in std["hauslast_stunde"]:
        d = dt.datetime.fromtimestamp(ts, TZ)
        if d.date().isoformat() in ("2026-08-11", "2026-08-12"):
            vor[d.hour].append(w)
    vorbelegt = {h: st.fmean(v) for h, v in vor.items() if v}

    return {
        "juli_median": juli_median,
        "juli_mittel": juli_mittel,
        "vorbelegt": vorbelegt,
        "stichprobe": stichprobe,
    }


def als_liste(prof: dict[int, float], rueckfall: float = 400.0) -> list[float]:
    return [prof.get(h, rueckfall) for h in range(24)]


# --------------------------------------------------------------------------
# Das Modell
# --------------------------------------------------------------------------
def gewichte(jetzt: float, peak: float, sunset: float, exponent: float,
             sunrise: float | None = None) -> list[float]:
    """Gewichte je 15-Minuten-Schritt.

    sunrise=None reproduziert den heutigen Sensor: die Halbbreite
    `sunset - peak` gilt auch fuer die Vormittagsseite. Da Forecast.Solar den
    Spitzenzeitpunkt rund zwei Stunden vor den astronomischen Mittag legt,
    reicht die Kurve damit bis etwa 02:00 zurueck und ueberschaetzt den
    Vormittag grob.

    Mit sunrise wird die Vormittagsseite auf `peak - sunrise` gestaucht.
    """
    width_n = (sunset - peak) / 3600.0
    width_v = width_n if sunrise is None else (peak - sunrise) / 3600.0
    if width_n <= 0 or width_v <= 0:
        return []
    spanne = (sunset - jetzt) / 3600.0
    if spanne <= 0:
        return []
    n = math.ceil(spanne / 0.25)
    w = []
    for i in range(n):
        th = (jetzt - peak) / 3600.0 + (i + 0.5) * 0.25
        width = width_v if th < 0 else width_n
        if -width_v < th < width_n:
            c = math.cos(math.pi / 2 * th / width)
            w.append(c ** exponent if c > 0 else 0.0)
        else:
            w.append(0.0)
    return w


def prognose(
    jetzt: float,
    soc: float,
    rohrest: float,
    peak: float,
    sunset: float,
    gemessen: float,
    prof: list[float],
    exponent: float,
    kmin: float,
    kmax: float,
    gain: float = 1.0,
    sunrise: float | None = None,
) -> dict:
    """Ein Modelllauf. Gibt Maximum, Zeitpunkt, k und die Trajektorie zurueck.

    `gain` ist ein fester Korrekturfaktor auf rohrest (Forecast.Solar-Bias).
    gain=1.0 entspricht dem heutigen Sensor.
    """
    rohrest = rohrest * gain
    w = gewichte(jetzt, peak, sunset, exponent, sunrise)
    sumw = sum(w)
    if not w or sumw <= 0:
        return {"max_soc": soc, "t_max": jetzt, "k": 1.0, "bahn": [(jetzt, soc)]}

    modelljetzt = rohrest / sumw * 4 * w[0]          # kW
    if modelljetzt > 0.15 and gemessen >= 0:
        k = min(max(gemessen / 1000.0 / modelljetzt, kmin), kmax)
    else:
        k = 1.0
    rest = rohrest * k

    kwh = soc / 100.0 * CAP
    ziel = SMAX / 100.0 * CAP
    unten = SMIN / 100.0 * CAP

    max_kwh, t_max = kwh, jetzt
    bahn = [(jetzt, kwh / CAP * 100.0)]
    for i, wi in enumerate(w):
        pv = rest * wi / sumw                         # kWh je 15 min
        mitte = jetzt + (i + 0.5) * 900.0
        h = dt.datetime.fromtimestamp(mitte, TZ).hour
        last = prof[h] / 1000.0 * 0.25                # kWh je 15 min
        d = pv - last
        dl = max(d, -MAXENTL / 1000.0 * 0.25)
        kwh = kwh + (dl * ETA if d > 0 else dl / ETA)
        kwh = min(max(kwh, unten), ziel)
        ende = jetzt + (i + 1) * 900.0
        bahn.append((ende, kwh / CAP * 100.0))
        if kwh > max_kwh:
            max_kwh, t_max = kwh, ende
    return {
        "max_soc": max_kwh / CAP * 100.0,
        "t_max": t_max,
        "k": k,
        "modelljetzt": modelljetzt,
        "bahn": bahn,
    }


# --------------------------------------------------------------------------
# Beobachtung
# --------------------------------------------------------------------------
def beobachtet(soc_reihe, ab: float) -> tuple[float, float]:
    """Tatsaechliches Maximum ab Zeitpunkt `ab` und dessen erstes Auftreten."""
    rest = [(t, v) for t, v in soc_reihe if t >= ab]
    hoch = max(v for _, v in rest)
    t_hoch = next(t for t, v in rest if v >= hoch)
    return hoch, t_hoch


def soc_bei(soc_reihe, t: float) -> float:
    best, bt = None, None
    for ts, v in soc_reihe:
        if bt is None or abs(ts - t) < abs(bt - t):
            best, bt = v, ts
    return best


def mittel_fenster(pv_reihe, t_ende: float, minuten: int) -> float:
    t_start = t_ende - minuten * 60
    werte = [v for ts, v in pv_reihe if t_start < ts <= t_ende]
    return st.fmean(werte) if werte else 0.0


# --------------------------------------------------------------------------
# Backtest
# --------------------------------------------------------------------------
STARTS = [f"{h:02d}:00" for h in range(8, 17)]


def backtest(std, fein, prof_liste, exponent, kmin, kmax, fenster, tage=None,
             gain=1.0, asym=False):
    """Liefert je (Tag, Startzeit) den Fehler.

    Zwei Fehlermasse:
      d_max   Fehler im vorhergesagten Maximal-SOC [Prozentpunkte]
      d_zeit  Fehler im Zeitpunkt des Maximums [Minuten]
      rmse    RMSE der SOC-Bahn im unzensierten Bereich (bis 100 % erreicht)
    """
    tage = tage or sorted(fein["tage"])
    zeilen = []
    for tag in tage:
        soc_reihe = reihe_5min(fein, tag, "soc")
        pv_reihe = reihe_5min(fein, tag, "pv")
        sunrise, sunset = _sonnen_eckdaten(dt.date.fromisoformat(tag))
        roh = [(_zeit(tag, hm), v) for hm, v in fein["prognose_roh"][tag]]
        peaks = [(_zeit(tag, hm), _zeit(tag, pk)) for hm, pk in fein["peak_roh"][tag]]

        # erster Zeitpunkt mit 100 % -> Ende des unzensierten Bereichs
        voll = next((t for t, v in soc_reihe if v >= 100), None)

        for hm in STARTS:
            t0 = _zeit(tag, hm)
            rohrest = stufenwert(roh, t0)
            peak = stufenwert(peaks, t0)
            if rohrest is None or peak is None or rohrest <= 0.1:
                continue
            soc0 = soc_bei(soc_reihe, t0)
            if soc0 is None or soc0 >= 100:
                continue
            gem = mittel_fenster(pv_reihe, t0, fenster)

            p = prognose(t0, soc0, rohrest, peak, sunset, gem, prof_liste,
                         exponent, kmin, kmax, gain,
                         sunrise if asym else None)
            ist_max, ist_t = beobachtet(soc_reihe, t0)

            # tatsaechlich noch erzeugte PV-Energie ab t0 (durch Abregelung
            # nach oben zensiert -> das ist eine UNTERgrenze)
            ist_rest = sum(v for t, v in pv_reihe if t >= t0) * (5 / 60) / 1000.0

            # RMSE der Bahn im unzensierten Bereich
            grenze = voll if voll else max(t for t, _ in soc_reihe)
            paare = []
            for t, v in p["bahn"]:
                if t0 <= t <= grenze:
                    ist = soc_bei(soc_reihe, t)
                    if ist is not None:
                        paare.append((v, ist))
            rmse = math.sqrt(st.fmean([(a - b) ** 2 for a, b in paare])) if paare else float("nan")

            zeilen.append({
                "tag": tag,
                "start": hm,
                "soc0": soc0,
                "rohrest": rohrest,
                "ist_rest": ist_rest,
                "unterdeckung": ist_rest / rohrest if rohrest > 0 else float("nan"),
                "modelljetzt": p.get("modelljetzt", float("nan")),
                "k": p["k"],
                "gem": gem,
                "prog_max": p["max_soc"],
                "ist_max": ist_max,
                "d_max": p["max_soc"] - ist_max,
                "prog_t": p["t_max"],
                "ist_t": ist_t,
                "d_zeit": (p["t_max"] - ist_t) / 60.0,
                "rmse": rmse,
                "n_bahn": len(paare),
            })
    return zeilen


def guete(zeilen) -> dict:
    if not zeilen:
        return {"n": 0}
    d_max = [z["d_max"] for z in zeilen]
    d_zeit = [z["d_zeit"] for z in zeilen]
    rmse = [z["rmse"] for z in zeilen if not math.isnan(z["rmse"])]
    return {
        "n": len(zeilen),
        "bias_soc": st.fmean(d_max),
        "mae_soc": st.fmean([abs(x) for x in d_max]),
        "bias_zeit": st.fmean(d_zeit),
        "mae_zeit": st.fmean([abs(x) for x in d_zeit]),
        "rmse_bahn": st.fmean(rmse) if rmse else float("nan"),
        "k_mittel": st.fmean([z["k"] for z in zeilen]),
        "k_am_anschlag": sum(1 for z in zeilen
                             if z["k"] >= zeilen[0].get("_kmax", 1e9) or z["k"] <= 0) / len(zeilen),
        "unterdeckung": st.fmean([z["unterdeckung"] for z in zeilen]),
    }


def anteil_anschlag(zeilen, kmin, kmax) -> float:
    if not zeilen:
        return float("nan")
    eps = 1e-9
    n = sum(1 for z in zeilen if z["k"] >= kmax - eps or z["k"] <= kmin + eps)
    return n / len(zeilen)


# --------------------------------------------------------------------------
# Direkte Formfitting der Tageskurve
# --------------------------------------------------------------------------
def kurvenfit(fein, tag: str, exponent_gitter, peak_quelle="gemessen"):
    """Passt cos^n direkt an die gemessene PV-Kurve an.

    Schliesst abgeregelte Punkte aus (SOC >= 99), denn dort begrenzt die
    Nulleinspeisung die PV-Leistung auf die Hauslast und die Messung zeigt
    nicht mehr das Dargebot.
    """
    pv = reihe_5min(fein, tag, "pv")
    soc = dict(reihe_5min(fein, tag, "soc"))
    _, sunset = _sonnen_eckdaten(dt.date.fromisoformat(tag))

    gueltig = [(t, v) for t, v in pv if soc.get(t, 0) < 99 and v > 20]
    if len(gueltig) < 40:
        return None

    if peak_quelle == "gemessen":
        peak = max(gueltig, key=lambda x: x[1])[0]
    else:
        peak = _zeit(tag, fein["peak_roh"][tag][-1][1])

    summe = sum(v for _, v in gueltig)
    bestes = None
    for n in exponent_gitter:
        width = (sunset - peak) / 3600.0
        modell = []
        for t, _ in gueltig:
            th = (t - peak) / 3600.0
            if -width < th < width:
                c = math.cos(math.pi / 2 * th / width)
                modell.append(c ** n if c > 0 else 0.0)
            else:
                modell.append(0.0)
        sm = sum(modell)
        if sm <= 0:
            continue
        skala = summe / sm
        fehler = math.sqrt(st.fmean([(skala * m - v) ** 2 for m, (_, v) in zip(modell, gueltig)]))
        if bestes is None or fehler < bestes[1]:
            bestes = (n, fehler, peak, skala)
    return {"exponent": bestes[0], "rmse_W": bestes[1], "peak": bestes[2], "n_punkte": len(gueltig)}


def symmetrietest(fein, tag: str, deltas=(1.0, 2.0, 3.0, 4.0)):
    """Spiegelt die gemessene PV-Leistung am astronomischen Sonnenhoechststand.

    Voraussetzungsarm: keine Kurvenform unterstellt. Eine unverschattete
    Suedanlage liefert P(Mittag+d) / P(Mittag-d) nahe 1 (leicht < 1 wegen
    Modultemperatur). Deutlich kleinere Werte belegen ein Nachmittagsdefizit.

    Abgeregelte Punkte (SOC >= 99) werden ausgeschlossen und als 'zensiert'
    gemeldet - dort begrenzt die Nulleinspeisung die PV-Leistung.
    """
    pv = dict(reihe_5min(fein, tag, "pv"))
    soc = dict(reihe_5min(fein, tag, "soc"))
    mittag = sonnenhoechststand(dt.date.fromisoformat(tag))

    def wert(t):
        # naechster 5-Minuten-Stuetzpunkt
        kandidat = min(pv, key=lambda x: abs(x - t))
        if abs(kandidat - t) > 200:
            return None, "fehlt"
        if soc.get(kandidat, 0) >= 99:
            return None, "zensiert"
        return pv[kandidat], "ok"

    raus = []
    for d in deltas:
        v_vor, s_vor = wert(mittag - d * 3600)
        v_nach, s_nach = wert(mittag + d * 3600)
        if v_vor and v_nach and v_vor > 50:
            raus.append((d, v_vor, v_nach, v_nach / v_vor, "ok"))
        else:
            raus.append((d, v_vor, v_nach, None, s_nach if s_nach != "ok" else s_vor))
    return {"mittag": mittag, "paare": raus}


def modellresiduum(fein, tag: str, exponent: float, ab_stunde: int = 9):
    """Residuum (Modell - Messung) im tatsaechlich genutzten Fenster.

    Nutzt peak wie der Sensor: den letzten Forecast.Solar-Wert des Tages.
    Betrachtet nur t >= ab_stunde, denn frueher wird der Sensor nicht
    ausgewertet, und nur unzensierte Punkte.
    """
    pv = reihe_5min(fein, tag, "pv")
    soc = dict(reihe_5min(fein, tag, "soc"))
    _, sunset = _sonnen_eckdaten(dt.date.fromisoformat(tag))
    peak = _zeit(tag, fein["peak_roh"][tag][-1][1])
    grenze = _zeit(tag, f"{ab_stunde:02d}:00")

    gueltig = [(t, v) for t, v in pv if t >= grenze and soc.get(t, 0) < 99]
    if len(gueltig) < 30:
        return None
    width = (sunset - peak) / 3600.0
    modell = []
    for t, _ in gueltig:
        th = (t - peak) / 3600.0
        c = math.cos(math.pi / 2 * th / width) if -width < th < width else 0.0
        modell.append(c ** exponent if c > 0 else 0.0)
    if sum(modell) <= 0:
        return None
    skala = sum(v for _, v in gueltig) / sum(modell)
    mittag = sonnenhoechststand(dt.date.fromisoformat(tag))
    vor = [skala * m - v for m, (t, v) in zip(modell, gueltig) if t < mittag]
    nach = [skala * m - v for m, (t, v) in zip(modell, gueltig) if t >= mittag]
    return {
        "vormittag_W": st.fmean(vor) if vor else float("nan"),
        "nachmittag_W": st.fmean(nach) if nach else float("nan"),
        "n_vor": len(vor), "n_nach": len(nach), "peak": peak,
    }


# --------------------------------------------------------------------------
# Klarhimmel-Referenz: physikalisch statt cos^n
# --------------------------------------------------------------------------
AZIMUT_ANLAGE = 188.0   # Grad, 180 = Sued
NEIGUNG = 20.0          # Grad


def sonnenstand(ts: float) -> tuple[float, float]:
    """Elevation und Azimut der Sonne in Grad (Azimut 180 = Sued)."""
    d = dt.datetime.fromtimestamp(ts, dt.timezone.utc)
    n = d.timetuple().tm_yday
    stunde_utc = d.hour + d.minute / 60 + d.second / 3600
    g = 2.0 * math.pi / 365.0 * (n - 1 + (stunde_utc - 12) / 24)
    eqtime = 229.18 * (0.000075 + 0.001868 * math.cos(g) - 0.032077 * math.sin(g)
                       - 0.014615 * math.cos(2 * g) - 0.040849 * math.sin(2 * g))
    decl = (0.006918 - 0.399912 * math.cos(g) + 0.070257 * math.sin(g)
            - 0.006758 * math.cos(2 * g) + 0.000907 * math.sin(2 * g)
            - 0.002697 * math.cos(3 * g) + 0.001480 * math.sin(3 * g))
    wahre_sonnenzeit = (stunde_utc * 60 + eqtime + 4 * LON) % 1440
    ha = math.radians(wahre_sonnenzeit / 4.0 - 180.0)
    lat = math.radians(LAT)
    sin_el = math.sin(lat) * math.sin(decl) + math.cos(lat) * math.cos(decl) * math.cos(ha)
    sin_el = max(-1.0, min(1.0, sin_el))
    el = math.asin(sin_el)
    cos_az = (math.sin(decl) - math.sin(lat) * sin_el) / (math.cos(lat) * math.cos(el) + 1e-12)
    cos_az = max(-1.0, min(1.0, cos_az))
    az = math.degrees(math.acos(cos_az))
    if ha > 0:
        az = 360.0 - az
    return math.degrees(el), az


def poa_klarhimmel(ts: float) -> float:
    """Einstrahlung auf die Modulebene bei klarem Himmel, W/m^2 (Naeherung)."""
    el, az = sonnenstand(ts)
    if el <= 1.0:
        return 0.0
    am = 1.0 / (math.sin(math.radians(el)) + 0.50572 * (el + 6.07995) ** -1.6364)
    dni = 1361.0 * 0.7 ** (am ** 0.678)
    ghi = dni * math.sin(math.radians(el))
    dhi = 0.13 * ghi
    cos_i = (math.sin(math.radians(el)) * math.cos(math.radians(NEIGUNG))
             + math.cos(math.radians(el)) * math.sin(math.radians(NEIGUNG))
             * math.cos(math.radians(az - AZIMUT_ANLAGE)))
    cos_i = max(0.0, cos_i)
    himmelsanteil = (1 + math.cos(math.radians(NEIGUNG))) / 2
    return dni * cos_i + dhi * himmelsanteil


def verschattungsprofil(fein, tag: str, eich_von="09:00", eich_bis="11:30"):
    """Verhaeltnis Messung / Klarhimmelerwartung ueber den Tag.

    Der Systemwirkungsgrad wird im Eichfenster bestimmt (klarer, nachweislich
    unverschatteter Vormittag). Faellt das Verhaeltnis danach ab, fehlt
    Leistung, die geometrisch da sein muesste - das ist die Verschattung.
    """
    pv = reihe_5min(fein, tag, "pv")
    soc = dict(reihe_5min(fein, tag, "soc"))
    t_von, t_bis = _zeit(tag, eich_von), _zeit(tag, eich_bis)

    eich = [(t, v) for t, v in pv if t_von <= t <= t_bis and poa_klarhimmel(t) > 50]
    if len(eich) < 10:
        return None
    eta = st.fmean([v / poa_klarhimmel(t) for t, v in eich])

    profil = []
    for t, v in pv:
        poa = poa_klarhimmel(t)
        if poa < 150:
            continue
        zensiert = soc.get(t, 0) >= 99
        profil.append((t, v, eta * poa, None if zensiert else v / (eta * poa)))
    return {"eta": eta, "profil": profil}


def tagesertrag(fein, tag: str) -> float:
    """kWh aus der 5-Minuten-Leistungsreihe (07:00-21:00)."""
    return sum(v for _, v in reihe_5min(fein, tag, "pv")) * (5 / 60) / 1000.0


# --------------------------------------------------------------------------
# Bericht
# --------------------------------------------------------------------------
def uhr(ts: float) -> str:
    return dt.datetime.fromtimestamp(ts, TZ).strftime("%H:%M")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--kurz", action="store_true")
    args = ap.parse_args()

    std, fein = lade()
    tage = sorted(fein["tage"])
    profile = hauslastprofil(std)
    prof_median = als_liste(profile["juli_median"])
    prof_mittel = als_liste(profile["juli_mittel"])
    prof_vor = als_liste(profile["vorbelegt"])

    print("=" * 78)
    print("1  DATENLAGE")
    print("=" * 78)
    for tag in tage:
        d = dt.date.fromisoformat(tag)
        auf, unter = _sonnen_eckdaten(d)
        print(f"  {tag}  Sonne {uhr(auf)}-{uhr(unter)}  Mittag {uhr(sonnenhoechststand(d))}"
              f"  PV-Ertrag(gemessen, inkl. Abregelung) {tagesertrag(fein, tag):5.2f} kWh"
              f"  Forecast.Solar-Tagesprognose {fein['tagesprognose'][tag]:5.2f} kWh")
    print()

    print("=" * 78)
    print("2  HAUSLASTPROFIL")
    print("=" * 78)
    print("  Stunde | Juli-Median | Juli-Mittel | vorbelegt (11./12.08.) | Differenz")
    for h in range(24):
        med = profile["juli_median"].get(h)
        mit = profile["juli_mittel"].get(h)
        vor = profile["vorbelegt"].get(h)
        if med is None:
            continue
        diff = f"{vor - med:+7.0f}" if vor is not None else "      -"
        vor_s = f"{vor:7.0f}" if vor is not None else "      -"
        print(f"    {h:02d}   | {med:11.0f} | {mit:11.0f} | {vor_s}                | {diff}")
    tag_med = sum(prof_median) / 1000.0
    tag_mit = sum(prof_mittel) / 1000.0
    tag_vor = sum(prof_vor) / 1000.0
    print(f"  Tagessumme: Median {tag_med:.2f} kWh | Mittel {tag_mit:.2f} kWh | vorbelegt {tag_vor:.2f} kWh")
    print(f"  Stichprobe je Stunde (Juli-Fenster): {min(profile['stichprobe'].values())}"
          f"-{max(profile['stichprobe'].values())} Tage")
    print()

    print("=" * 78)
    print("3  PEGEL - taugt rohrest ueberhaupt als Mengengeruest?")
    print("=" * 78)
    print("  ist_rest ist durch die Abregelung nach oben zensiert und damit eine")
    print("  UNTERgrenze der tatsaechlich verfuegbaren Energie.")
    print("  Tag         Start | rohrest | ist_rest(min) | Verhaeltnis")
    z0 = backtest(std, fein, prof_median, 2.0, 0.6, 1.6, 20)
    for z in z0:
        if z["start"] in ("09:00", "12:00", "15:00"):
            print(f"  {z['tag']}  {z['start']} | {z['rohrest']:7.2f} | {z['ist_rest']:13.2f}"
                  f" | {z['unterdeckung']:11.2f}")
    print(f"  Mittel ueber alle {len(z0)} Startzeitpunkte: "
          f"ist_rest / rohrest = {guete(z0)['unterdeckung']:.2f}")
    print()

    print("=" * 78)
    print("4  KURVENFORM UND VERSCHATTUNG")
    print("=" * 78)
    gitter = [1.0 + 0.25 * i for i in range(13)]      # 1.00 .. 4.00
    print("  a) Symmetrietest um den astronomischen Sonnenhoechststand (13:34)")
    print("     Verhaeltnis P(Mittag+d) / P(Mittag-d); 1.0 = symmetrisch")
    for tag in tage:
        s = symmetrietest(fein, tag)
        teile = []
        for d, vv, vn, q, status in s["paare"]:
            teile.append(f"d={d:.0f}h: {q:.2f}" if q else f"d={d:.0f}h: {status}")
        print(f"    {tag}  " + "   ".join(teile))
    print()
    print("  b) Zeitpunkt der gemessenen Tagesspitze gegen den astronomischen Mittag")
    for tag in tage:
        f = kurvenfit(fein, tag, gitter)
        mittag = sonnenhoechststand(dt.date.fromisoformat(tag))
        print(f"    {tag}  Spitze {uhr(f['peak'])}   Mittag {uhr(mittag)}"
              f"   Versatz {(f['peak'] - mittag)/60:+6.0f} min")
    print()
    print("  c) Klarhimmel-Referenz: Messung / geometrische Erwartung je halbe Stunde")
    print("     Eichung auf 09:00-11:30 (klarer, unverschatteter Vormittag) = 1.00")
    print("     'zens' = Speicher voll, PV abgeregelt, Messung nicht aussagekraeftig")
    stunden = [f"{h:02d}:{m:02d}" for h in range(11, 19) for m in (0, 30)]
    print("     Zeit  " + " ".join(f"{s:>5s}" for s in stunden))
    profile_je_zeit: dict[str, list[float]] = {s: [] for s in stunden}
    for tag in tage:
        vp = verschattungsprofil(fein, tag)
        nach_zeit = {}
        for t, v, erw, q in vp["profil"]:
            nach_zeit[dt.datetime.fromtimestamp(t, TZ).strftime("%H:%M")] = q
        zeile = []
        for s in stunden:
            q = nach_zeit.get(s)
            zeile.append(f"{q:5.2f}" if q is not None else " zens")
            if q is not None:
                profile_je_zeit[s].append(q)
        print(f"     {tag[5:]}  " + " ".join(zeile))
    print("     Median " + " ".join(
        f"{st.median(profile_je_zeit[s]):5.2f}" if profile_je_zeit[s] else "    -"
        for s in stunden))
    print()

    print("  d) Residuum Modell minus Messung ab 09:00, peak wie im Sensor")
    print("     (positiv = Modell zu hoch)")
    for e in (2.0, 3.0):
        print(f"     EXPONENT = {e:.1f}")
        for tag in tage:
            r = modellresiduum(fein, tag, e)
            print(f"       {tag}  vormittags {r['vormittag_W']:+7.1f} W (n={r['n_vor']:3d})"
                  f"   nachmittags {r['nachmittag_W']:+7.1f} W (n={r['n_nach']:3d})")
    print()

    print("=" * 78)
    print("5  BACKTEST - EXPONENT x Pegelkorrektur (Klammer 0.6/1.6, Fenster 20 min)")
    print("=" * 78)
    print("  Profil Juli-Median. Zelle = MAE des Maximal-SOC in Prozentpunkten.")
    gains = [1.0, 1.1, 1.2, 1.3, 1.4, 1.5]
    kopf = "  EXP  | " + " | ".join(f"gain {g:.1f}" for g in gains)
    print(kopf)
    tabelle = {}
    for n in gitter:
        zeile = []
        for g in gains:
            gg = guete(backtest(std, fein, prof_median, n, 0.6, 1.6, 20, gain=g))
            tabelle[(n, g)] = gg
            zeile.append(f"{gg['mae_soc']:8.2f}")
        print(f"  {n:4.2f} | " + " | ".join(zeile))
    print()
    print("  Dasselbe mit RMSE der SOC-Bahn (Prozentpunkte):")
    print(kopf)
    for n in gitter:
        print(f"  {n:4.2f} | " + " | ".join(f"{tabelle[(n, g)]['rmse_bahn']:8.2f}" for g in gains))
    print()
    print("  Dasselbe mit ABGESCHALTETER k-Korrektur (KMIN=KMAX=1), damit Form")
    print("  und Pegel nicht mehr ueber `modelljetzt` miteinander verrechnet werden.")
    print("  Zelle = RMSE der SOC-Bahn / MAE des Zeitpunkts in Minuten.")
    print(kopf)
    ohne_k = {}
    for n in gitter:
        zeile = []
        for g in gains:
            gg = guete(backtest(std, fein, prof_median, n, 1.0, 1.0, 20, gain=g))
            ohne_k[(n, g)] = gg
            zeile.append(f"{gg['rmse_bahn']:4.1f}/{gg['mae_zeit']:3.0f}")
        print(f"  {n:4.2f} | " + " | ".join(zeile))
    b2 = min(ohne_k, key=lambda key: ohne_k[key]["rmse_bahn"])
    print(f"\n  Bestes Paar ohne k: EXPONENT={b2[0]:.2f}, gain={b2[1]:.1f}"
          f"  -> RMSE {ohne_k[b2]['rmse_bahn']:.2f} pp, MAE Zeit {ohne_k[b2]['mae_zeit']:.0f} min")
    print()

    print("  Profilierte Guete: je EXPONENT das jeweils beste gain (k aus, asym).")
    print("  Damit sind Form und Pegel entkoppelt. Zusaetzlich die vom Modell")
    print("  implizierte PV-Spitzenleistung gegen die real gemessene Tagesspitze -")
    print("  das Kriterium, mit dem EXPONENT=1 bereits verworfen wurde.")
    real_spitze = []
    for tag in tage:
        pvr = reihe_5min(fein, tag, "pv")
        socr = dict(reihe_5min(fein, tag, "soc"))
        real_spitze.append(max(v for ts, v in pvr if socr.get(ts, 0) < 99) / 1000)
    print("  EXP  | bestes gain | RMSE-Bahn | MAE Zeit | Modellspitze | real")
    profiliert = {}
    for n in gitter:
        bg, bq = None, None
        for g in [1.0 + 0.05 * i for i in range(17)]:
            q = guete(backtest(std, fein, prof_median, n, 1.0, 1.0, 15, gain=g, asym=True))
            if bq is None or q["rmse_bahn"] < bq["rmse_bahn"]:
                bg, bq = g, q
        spitzen = []
        for tag in tage:
            sr, ss = _sonnen_eckdaten(dt.date.fromisoformat(tag))
            t0 = _zeit(tag, "09:00")
            roh = [(_zeit(tag, hm), v) for hm, v in fein["prognose_roh"][tag]]
            peaks = [(_zeit(tag, hm), _zeit(tag, pk)) for hm, pk in fein["peak_roh"][tag]]
            w = gewichte(t0, stufenwert(peaks, t0), ss, n, sr)
            spitzen.append(stufenwert(roh, t0) * bg / sum(w) * 4 * max(w))
        profiliert[n] = (bg, bq, st.fmean(spitzen))
        print(f"  {n:4.2f} | {bg:11.2f} | {bq['rmse_bahn']:9.2f} | {bq['mae_zeit']:8.0f}"
              f" | {st.fmean(spitzen):12.2f} | {st.fmean(real_spitze):4.2f}")
    lo = min(profiliert.values(), key=lambda x: x[1]["rmse_bahn"])[1]["rmse_bahn"]
    band = [n for n, (g, q, s) in profiliert.items() if q["rmse_bahn"] <= lo + 0.5]
    print(f"\n  RMSE-Minimum {lo:.2f} pp; innerhalb +0.5 pp liegt EXPONENT"
          f" {min(band):.2f} .. {max(band):.2f}.")
    print("  Die Bahn-Guete zieht zu kleinen, die Spitzenleistung zu grossen")
    print("  Exponenten. Beides zugleich ist mit einer symmetrischen cos^n-Kurve")
    print("  nicht zu haben - siehe die Verschattungsdelle in Abschnitt 4c.")
    print()

    # Empfehlung: Kompromiss zwischen beiden Kriterien, nicht das nackte Argmin.
    # Das Argmin liegt auf einer Diagonale (Form gegen Pegel austauschbar) und
    # ist mit vier Tagen nicht signifikant vom Nachbarn zu unterscheiden.
    best_n, best_g = 2.5, 1.3
    print(f"  Empfehlung (Mitte des Rueckens): EXPONENT={best_n:.2f}, gain={best_g:.1f}"
          f"  -> RMSE {ohne_k[(best_n, best_g)]['rmse_bahn']:.2f} pp,"
          f" MAE Zeit {ohne_k[(best_n, best_g)]['mae_zeit']:.0f} min (ohne k)")
    print()

    print("=" * 78)
    print("5b  WARUM k SCHADET - mittleres k nach Startstunde")
    print("=" * 78)
    print(f"  (EXPONENT={best_n:.2f}, gain={best_g:.1f}, Klammer weit 0.1/5.0, damit das")
    print("   unverzerrte k sichtbar wird. k=1 hiesse: Messung passt zur Modellerwartung.)")
    z = backtest(std, fein, prof_median, best_n, 0.1, 5.0, 20, gain=best_g)
    nach_stunde: dict[str, list[float]] = {}
    for e in z:
        nach_stunde.setdefault(e["start"], []).append(e["k"])
    print("  Start | mittleres k | n")
    for s in sorted(nach_stunde):
        v = nach_stunde[s]
        print(f"  {s} | {st.fmean(v):11.2f} | {len(v)}")
    print()

    print("=" * 78)
    print("6  BACKTEST - Klammer KMIN/KMAX variieren")
    print("=" * 78)
    print(f"  (EXPONENT={best_n:.2f}, gain={best_g:.1f}, Profil Juli-Median, Fenster 20 min)")
    print("  KMIN  KMAX | Bias SOC | MAE SOC | MAE Zeit | RMSE Bahn | k-Mittel | am Anschlag")
    for kmin, kmax in [(1.0, 1.0), (0.9, 1.1), (0.8, 1.25), (0.7, 1.4),
                       (0.6, 1.6), (0.5, 1.8), (0.4, 2.0), (0.3, 2.5), (0.1, 5.0)]:
        z = backtest(std, fein, prof_median, best_n, kmin, kmax, 20, gain=best_g)
        g = guete(z)
        print(f"  {kmin:4.2f}  {kmax:4.2f} | {g['bias_soc']:+8.2f} | {g['mae_soc']:7.2f}"
              f" | {g['mae_zeit']:8.1f} | {g['rmse_bahn']:9.2f} | {g['k_mittel']:8.2f}"
              f" | {anteil_anschlag(z, kmin, kmax)*100:5.0f} %")
    print()

    print("=" * 78)
    print("7  BACKTEST - Mittelungsfenster fuer `gemessen`")
    print("=" * 78)
    print(f"  (EXPONENT={best_n:.2f}, gain={best_g:.1f}, Profil Juli-Median, Klammer 0.6/1.6)")
    print("  Fenster | Bias SOC | MAE SOC | MAE Zeit | RMSE Bahn | k-Mittel")
    for fmin in (5, 10, 15, 20, 30, 45, 60, 90):
        z = backtest(std, fein, prof_median, best_n, 0.6, 1.6, fmin, gain=best_g)
        g = guete(z)
        print(f"  {fmin:5d}   | {g['bias_soc']:+8.2f} | {g['mae_soc']:7.2f} | {g['mae_zeit']:8.1f}"
              f" | {g['rmse_bahn']:9.2f} | {g['k_mittel']:8.2f}")
    print()

    print("=" * 78)
    print("8  PROFILVERGLEICH bei den besten Kurvenparametern")
    print("=" * 78)
    print("  Profil       | Bias SOC | MAE SOC | MAE Zeit | RMSE Bahn")
    for name, prof in (("Juli-Median", prof_median), ("Juli-Mittel", prof_mittel),
                       ("vorbelegt", prof_vor)):
        g = guete(backtest(std, fein, prof, best_n, 0.6, 1.6, 20, gain=best_g))
        print(f"  {name:12s} | {g['bias_soc']:+8.2f} | {g['mae_soc']:7.2f}"
              f" | {g['mae_zeit']:8.1f} | {g['rmse_bahn']:9.2f}")
    print()

    print("=" * 78)
    print("9  ALT GEGEN NEU")
    print("=" * 78)
    varianten = [
        ("alt   (EXP 2.00, 0.6/1.6, 20 min, Profil vorbelegt, gain 1.0)",
         prof_vor, 2.0, 0.6, 1.6, 20, 1.0),
        ("nur Profil neu", prof_median, 2.0, 0.6, 1.6, 20, 1.0),
        ("Profil + Klammer eng (0.8/1.25)", prof_median, 2.0, 0.8, 1.25, 20, 1.0),
        (f"Profil + gain {best_g:.1f}", prof_median, 2.0, 0.6, 1.6, 20, best_g),
        (f"Profil + gain {best_g:.1f} + EXP {best_n:.2f}", prof_median, best_n, 0.6, 1.6, 20, best_g),
        (f"Profil + gain {best_g:.1f} + EXP {best_n:.2f} + Klammer 0.8/1.25",
         prof_median, best_n, 0.8, 1.25, 20, best_g),
    ]
    print("  Variante                                                       | Bias  |  MAE  | Zeit | RMSE")
    for label, prof, n, kmin, kmax, fmin, gn in varianten:
        g = guete(backtest(std, fein, prof, n, kmin, kmax, fmin, gain=gn))
        print(f"  {label:62s} | {g['bias_soc']:+5.1f} | {g['mae_soc']:5.2f}"
              f" | {g['mae_zeit']:4.0f} | {g['rmse_bahn']:5.2f}")
    print()

    if args.kurz:
        return

    print("=" * 78)
    print("7  EINZELLAEUFE - alt (EXP=2, 0.6/1.6, 20 min, vorbelegtes Profil)")
    print("=" * 78)
    alt = backtest(std, fein, prof_vor, ALT_EXPONENT, ALT_KMIN, ALT_KMAX, ALT_FENSTER)
    for z in alt:
        print(f"  {z['tag']} {z['start']}  SOC0 {z['soc0']:3.0f}%  rohrest {z['rohrest']:5.2f}"
              f"  k {z['k']:4.2f}  Prognose {z['prog_max']:5.1f}% um {uhr(z['prog_t'])}"
              f"  ist {z['ist_max']:5.1f}% um {uhr(z['ist_t'])}"
              f"  dSOC {z['d_max']:+6.1f}  dZeit {z['d_zeit']:+6.0f} min  RMSE {z['rmse']:5.2f}")
    print(f"  -> {guete(alt)}")
    print()

    print("=" * 78)
    print("10  VALIDIERUNGSPUNKT 12.08. - Modelllauf gegen den echten Verlauf")
    print("=" * 78)
    soc12 = reihe_5min(fein, "2026-08-12", "soc")
    pv12 = reihe_5min(fein, "2026-08-12", "pv")
    sr12, ss12 = _sonnen_eckdaten(dt.date(2026, 8, 12))
    t0 = _zeit("2026-08-12", "10:05")
    print("  gemessener Verlauf:")
    for hm in ("10:05", "12:00", "14:00", "16:00", "16:45"):
        print(f"    {hm}: {soc_bei(soc12, _zeit('2026-08-12', hm)):3.0f} %")
    print(f"    tatsaechlich 100 % erstmals um "
          f"{uhr(next(t for t, v in soc12 if v >= 100))}")
    print()
    print("  Modelllauf ab 10:05 (SOC 12 %, rohrest 5.571 kWh, peak 11:00):")
    laeufe = [
        ("alt   EXP 2.0, 0.6/1.6, 20 min, gain 1.0, sym, Profil vorbelegt",
         prof_vor, 2.0, 0.6, 1.6, 20, 1.0, None),
        ("neu   EXP 2.5, 0.85/1.15, 15 min, gain 1.30, asym, Profil Juli",
         prof_median, 2.5, 0.85, 1.15, 15, 1.30, sr12),
        ("neu   EXP 2.5, k aus,     gain 1.30, asym, Profil Juli",
         prof_median, 2.5, 1.0, 1.0, 15, 1.30, sr12),
    ]
    for label, prof, n, kmin, kmax, fmin, gn, sr in laeufe:
        gem = mittel_fenster(pv12, t0, fmin)
        p = prognose(t0, soc_bei(soc12, t0), 5.571, _zeit("2026-08-12", "11:00"),
                     ss12, gem, prof, n, kmin, kmax, gn, sr)
        print(f"    {label}")
        print(f"      -> {p['max_soc']:5.1f} % um {uhr(p['t_max'])}   (k={p['k']:.2f})")
    print()

    print("=" * 78)
    print("11  HEUTE 13.08., Stand 10:45 (SOC 25 %, rohrest 8.216 kWh, peak 13:00)")
    print("=" * 78)
    sr13, ss13 = _sonnen_eckdaten(dt.date(2026, 8, 13))
    t_jetzt = _zeit("2026-08-13", "10:45")
    for label, prof, n, kmin, kmax, gn, sr in [
        ("alt   EXP 2.0, 0.6/1.6, gain 1.0, sym, Profil vorbelegt",
         prof_vor, 2.0, 0.6, 1.6, 1.0, None),
        ("neu   EXP 2.5, 0.85/1.15, gain 1.30, asym, Profil Juli",
         prof_median, 2.5, 0.85, 1.15, 1.30, sr13),
        ("neu   EXP 2.5, k aus,     gain 1.30, asym, Profil Juli",
         prof_median, 2.5, 1.0, 1.0, 1.30, sr13),
    ]:
        p = prognose(t_jetzt, 25.0, 8.216, _zeit("2026-08-13", "13:00"),
                     ss13, 1280.0, prof, n, kmin, kmax, gn, sr)
        print(f"  {label}")
        print(f"    -> {p['max_soc']:5.1f} % um {uhr(p['t_max'])}   (k={p['k']:.2f})")
    print()


if __name__ == "__main__":
    main()
