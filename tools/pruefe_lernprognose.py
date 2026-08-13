"""Pruefstand fuer custom_components/pv_lernprognose.

Faehrt die reinen Rechenmodule der Integration gegen dieselben Daten, mit
denen docs/PROGNOSE.md erstellt wurde (09.-12.08.2026), und prueft drei
Dinge:

  1. Geometrie. Stimmen Sonnenauf-/-untergang und der Zeitpunkt des
     Sonnenhoechststands mit den astronomisch gerechneten Werten aus dem
     Backtest ueberein?

  2. Lernen der Tagesform. Findet der Formschaetzer die in Abschnitt 4b
     quantifizierte Verschattung wieder - Delle 12:30 bis 15:30, Erholung
     ab 16 Uhr - ohne dass ihm jemand sagt, wo sie liegt?

  3. Prognosefehler. Wie schlaegt sich die Vorwaertssimulation gegen die
     tatsaechliche SOC-Bahn, verglichen mit den Zahlen aus Abschnitt 7?

Lauf: python tools/pruefe_lernprognose.py

READ-ONLY. Beruehrt Home Assistant nicht. Home Assistant muss nicht
installiert sein - die geladenen Module haengen bewusst nicht davon ab.
"""

from __future__ import annotations

import datetime as dt
import importlib.util
import json
import math
import pathlib
import statistics as st
import sys
import types

HIER = pathlib.Path(__file__).resolve().parent
PAKET = HIER.parent / "custom_components" / "pv_lernprognose"
CACHE_5MIN = HIER / "prognose_daten_5min.json"

TZ = dt.timezone(dt.timedelta(hours=2))   # CEST, im ganzen Fenster gueltig


# --------------------------------------------------------------------------
# Module laden, ohne das Paket-__init__ (das braucht Home Assistant)
# --------------------------------------------------------------------------
def _lade_paket() -> dict[str, types.ModuleType]:
    schale = types.ModuleType("pvlp")
    schale.__path__ = [str(PAKET)]  # type: ignore[attr-defined]
    sys.modules["pvlp"] = schale
    module: dict[str, types.ModuleType] = {}
    for name in ("const", "robust", "sonne", "schaetzer", "modell"):
        spec = importlib.util.spec_from_file_location(
            f"pvlp.{name}", PAKET / f"{name}.py"
        )
        assert spec and spec.loader
        mod = importlib.util.module_from_spec(spec)
        sys.modules[f"pvlp.{name}"] = mod
        spec.loader.exec_module(mod)
        module[name] = mod
    return module


M = _lade_paket()
const, robust, sonne, schaetzer, modell = (
    M["const"], M["robust"], M["sonne"], M["schaetzer"], M["modell"]
)

BREITE, LAENGE = 51.6739, 7.8150
NEIGUNG, AZIMUT = const.DEFAULT_NEIGUNG, const.DEFAULT_AZIMUT


# --------------------------------------------------------------------------
def lade_daten() -> dict:
    with CACHE_5MIN.open(encoding="utf-8") as f:
        return json.load(f)


def reihe(fein: dict, tag: str, art: str) -> list[tuple[dt.datetime, float]]:
    d = dt.date.fromisoformat(tag)
    basis = dt.datetime(d.year, d.month, d.day, fein["_start_stunde"], tzinfo=TZ)
    schritt = dt.timedelta(minutes=fein["_schritt_min"])
    raus = []
    for bi, block in enumerate(fein["tage"][tag][art]):
        for wi, v in enumerate(block):
            raus.append((basis + (bi * 12 + wi) * schritt, float(v)))
    return raus


def kopf(text: str) -> None:
    print()
    print(text)
    print("-" * len(text))


# --------------------------------------------------------------------------
# 1. Geometrie
# --------------------------------------------------------------------------
def pruefe_geometrie(fein: dict) -> None:
    kopf("1. Geometrie gegen die Werte aus docs/PROGNOSE.md Abschnitt 1")
    erwartet = {
        "2026-08-09": ("06:03", "21:05", "13:34"),
        "2026-08-10": ("06:05", "21:03", "13:34"),
        "2026-08-11": ("06:06", "21:01", "13:34"),
        "2026-08-12": ("06:08", "20:59", "13:34"),
    }
    print("Tag         auf    soll   unter  soll   Mittag soll   max.Abw.")
    schlimmster = 0.0
    for tag in sorted(fein["tage"]):
        d = dt.date.fromisoformat(tag)
        auf, unter = sonne.sonnenauf_und_untergang(d, BREITE, LAENGE)
        assert auf and unter
        auf_l, unter_l = auf.astimezone(TZ), unter.astimezone(TZ)
        mittag = auf_l + (unter_l - auf_l) / 2
        soll_auf, soll_unter, soll_mittag = erwartet[tag]

        def abw(ist: dt.datetime, soll: str) -> float:
            h, m = (int(x) for x in soll.split(":"))
            ziel = ist.replace(hour=h, minute=m, second=0, microsecond=0)
            return abs((ist - ziel).total_seconds()) / 60.0

        a = max(abw(auf_l, soll_auf), abw(unter_l, soll_unter), abw(mittag, soll_mittag))
        schlimmster = max(schlimmster, a)
        print(
            f"{tag}  {auf_l:%H:%M}  {soll_auf}  {unter_l:%H:%M}  {soll_unter}  "
            f"{mittag:%H:%M}  {soll_mittag}  {a:4.1f} min"
        )
    urteil = "OK" if schlimmster <= 2.0 else "ABWEICHUNG"
    print(f"\n{urteil}: groesste Abweichung {schlimmster:.1f} min")


# --------------------------------------------------------------------------
# 2. Lernen der Tagesform
# --------------------------------------------------------------------------
def _fuettere(fein: dict) -> schaetzer.Lernstand:
    """Faehrt die 5-Minuten-Historie durch die Schaetzer, wie es der
    Coordinator im Betrieb taete - einschliesslich Klarheits- und
    Zensurpruefung."""
    stand = schaetzer.Lernstand()
    puffer: list[tuple[dt.datetime, float, float]] = []

    for tag in sorted(fein["tage"]):
        pv = reihe(fein, tag, "pv")
        soc = dict(reihe(fein, tag, "soc"))
        puffer.clear()
        for zeit, watt in pv:
            zeit_utc = zeit.astimezone(dt.timezone.utc)
            stand_sonne = sonne.sonnenstand(zeit_utc, BREITE, LAENGE)
            poa = sonne.klarhimmel_poa(stand_sonne, zeit_utc, NEIGUNG, AZIMUT)
            puffer.append((zeit, watt, poa))
            if len(puffer) > 8:
                puffer.pop(0)

            # Klarheit: drei Punkte a 5 min statt 15 Punkte a 1 min
            werte = [w for _, w, _ in puffer[-4:]]
            streuung = robust.entrendete_streuung(werte)
            klar = streuung is not None and streuung <= const.KLARHEIT_SCHWELLE

            # Zensur: SOC am Anschlag oder Leistung steht still
            s = soc.get(zeit)
            zensiert = s is not None and s >= 99.0
            if not zensiert and len(puffer) >= 7:
                lang = [w for _, w, _ in puffer]
                geo = [p for _, _, p in puffer]
                fl = robust.entrendete_streuung(lang)
                hub = abs(geo[-1] - geo[0]) / max(max(geo), 1e-9)
                if (
                    min(lang) > const.MIN_PV_W
                    and fl is not None
                    and fl <= const.ZENSUR_FLACH_STREUUNG
                    and hub >= const.ZENSUR_GEOMETRIE_HUB
                ):
                    zensiert = True

            if (
                klar
                and not zensiert
                and watt >= const.MIN_PV_W
                and poa >= const.MIN_POA_W
                and stand_sonne.hoehe >= const.MIN_SONNENHOEHE
            ):
                stand.form.probe(zeit, stand_sonne.azimut, watt, poa)
        stand.form.tag_abschliessen()
        stand.form.heute = None
        stand.form.laufend = {}
    return stand


def gelernte_lage(
    stand: schaetzer.Lernstand, heute: dt.date
) -> tuple[float, dict[int, float], int, int]:
    """Systemgain und Formkurve, wie sie aus den vier Tagen hervorgehen.

    Die Betriebsschwellen (MIN_TAGE_FORM = 4 Tage und MIN_PROBEN_FORM = 8
    Proben je Fach) sind bei genau vier Tagen 5-Minuten-Rohdaten nur
    teilweise erfuellt. Im Betrieb tastet der Coordinator jede Minute ab
    und erreicht sie an einem einzigen klaren Tag. Fuer den Pruefstand
    wird deshalb mit drei Proben je Fach gerechnet - sonst misst man den
    Rueckfall auf die Startwerte statt das Verfahren.
    """
    roh, tage_je_fach, proben = stand.form._rohwerte(heute)
    belegt = {f: r for f, r in roh.items() if proben.get(f, 0) >= 3}
    if len(belegt) < 5:
        return const.START_GAIN, {}, 0, len(belegt)
    gain = robust.quantil(sorted(belegt.values()), const.GAIN_QUANTIL)
    form = {
        f: min(max(r / gain, const.FORM_MIN), const.FORM_MAX)
        for f, r in belegt.items()
    }
    streng = sum(
        1
        for f in belegt
        if tage_je_fach.get(f, 0) >= const.MIN_TAGE_FORM
        and proben.get(f, 0) >= const.MIN_PROBEN_FORM
    )
    return gain, form, streng, len(belegt)


def pruefe_form(fein: dict, stand: schaetzer.Lernstand) -> None:
    kopf("2. Gelernte Tagesform gegen die Messung aus Abschnitt 4b")
    heute = dt.date(2026, 8, 12)
    gain, form, streng, belegt_n = gelernte_lage(stand, heute)
    if not form:
        print("zu wenige belegte Faecher - Pruefung nicht moeglich")
        return

    print(f"Systemgain (0.90-Quantil ueber {belegt_n} Faecher): "
          f"{gain:.3f} W je W/m2")
    print(f"Faecher, die die Betriebsschwelle schon erfuellen: "
          f"{streng} von {belegt_n}")

    tagesertrag = 0.0
    basis = dt.datetime(2026, 8, 11, tzinfo=dt.timezone.utc)
    for i in range(96):
        t = basis + dt.timedelta(minutes=(i + 0.5) * 15)
        sst = sonne.sonnenstand(t, BREITE, LAENGE)
        if sst.hoehe <= 0:
            continue
        pp = sonne.klarhimmel_poa(sst, t, NEIGUNG, AZIMUT)
        ff = form.get(schaetzer.azimut_fach(sst.azimut), 1.0)
        tagesertrag += gain * pp * ff * 0.25 / 1000.0
    print(f"\nKlarhimmel-Tagesertrag mit Verschattung: {tagesertrag:.2f} kWh")
    print("docs/PROGNOSE.md Abschnitt 2 kam auf voellig anderem Weg auf 12.0 kWh\n")

    gemessen = {
        "11:00": 0.97, "11:30": 0.90, "12:00": 0.84, "12:30": 0.71,
        "13:00": 0.64, "13:30": 0.65, "14:00": 0.62, "14:30": 0.60,
        "15:00": 0.62, "15:30": 0.77, "16:00": 0.87, "16:30": 0.93,
    }
    print("Zeit    Azimut  gelernt  Abschnitt 4b  Diff")
    fehler = []
    for hhmm, soll in gemessen.items():
        h, m = (int(x) for x in hhmm.split(":"))
        t = dt.datetime(2026, 8, 11, h, m, tzinfo=TZ).astimezone(dt.timezone.utc)
        az = sonne.sonnenstand(t, BREITE, LAENGE).azimut
        fach = schaetzer.azimut_fach(az)
        if fach is None:
            continue
        wert = form.get(fach)
        if wert is None:
            links = max((f for f in form if f < fach), default=None)
            rechts = min((f for f in form if f > fach), default=None)
            if links is None or rechts is None:
                print(f"{hhmm}   {az:6.1f}   --       {soll:.2f}          (nicht belegt)")
                continue
            anteil = (fach - links) / (rechts - links)
            wert = form[links] * (1 - anteil) + form[rechts] * anteil
        fehler.append(abs(wert - soll))
        print(f"{hhmm}   {az:6.1f}   {wert:.2f}     {soll:.2f}          {wert - soll:+.2f}")

    if fehler:
        print(f"\nmittlere absolute Abweichung {st.fmean(fehler):.3f}")
        delle = [form.get(schaetzer.azimut_fach(
            sonne.sonnenstand(
                dt.datetime(2026, 8, 11, h, m, tzinfo=TZ).astimezone(dt.timezone.utc),
                BREITE, LAENGE).azimut)) for h, m in ((13, 0), (14, 0), (15, 0))]
        frei = [form.get(schaetzer.azimut_fach(
            sonne.sonnenstand(
                dt.datetime(2026, 8, 11, h, m, tzinfo=TZ).astimezone(dt.timezone.utc),
                BREITE, LAENGE).azimut)) for h, m in ((10, 0), (11, 0))]
        delle = [x for x in delle if x]
        frei = [x for x in frei if x]
        if delle and frei:
            print(
                f"Delle (13-15 Uhr) {st.fmean(delle):.2f} gegen "
                f"frei (10-11 Uhr) {st.fmean(frei):.2f} -> "
                f"{'Verschattung gefunden' if st.fmean(delle) < st.fmean(frei) - 0.15 else 'KEINE Delle erkannt'}"
            )
    return


# --------------------------------------------------------------------------
# 2b. Pegel gegen Forecast.Solar, in der Metrik des Schaetzers
# --------------------------------------------------------------------------
def pruefe_pegel(fein: dict, stand: schaetzer.Lernstand) -> float:
    kopf("2b. Pegelfaktor in der Metrik des Pegelschaetzers")
    print(
        "Der Wert 1.30 aus docs/PROGNOSE.md ist ist_rest/rohrest - und\n"
        "ist_rest ist durch die Abregelung nach oben zensiert, also eine\n"
        "Untergrenze. Der Schaetzer misst anders: er vergleicht zwei\n"
        "Truebungsindizes und nutzt nur unzensierte Abschnitte. In dieser\n"
        "Metrik faellt der Wert hoeher aus. Genau deshalb muss der Startwert\n"
        "in derselben Metrik hergeleitet werden.\n"
    )
    heute = dt.date(2026, 8, 12)
    gain, form, _s, _b = gelernte_lage(stand, heute)

    def geometrie_tag(tag: dt.date) -> float:
        summe = 0.0
        basis = dt.datetime(tag.year, tag.month, tag.day, tzinfo=dt.timezone.utc)
        for i in range(96):
            t = basis + dt.timedelta(minutes=(i + 0.5) * 15)
            s = sonne.sonnenstand(t, BREITE, LAENGE)
            if s.hoehe <= 0:
                continue
            p = sonne.klarhimmel_poa(s, t, NEIGUNG, AZIMUT)
            fach = schaetzer.azimut_fach(s.azimut)
            f = form.get(fach, 1.0) if fach is not None else 1.0
            summe += p * f * 0.25
        return summe

    print("Tag         E_gem   G_offen  G_gesamt  offen%  E_FS    Pegel")
    werte = []
    for tag in sorted(fein["tage"]):
        d = dt.date.fromisoformat(tag)
        pv = reihe(fein, tag, "pv")
        soc = dict(reihe(fein, tag, "soc"))
        g_gesamt = geometrie_tag(d)
        e_gem = 0.0
        g_offen = 0.0
        puffer: list[tuple[dt.datetime, float, float]] = []
        for zeit, watt in pv:
            zu = zeit.astimezone(dt.timezone.utc)
            s = sonne.sonnenstand(zu, BREITE, LAENGE)
            if s.hoehe <= 0:
                continue
            p = sonne.klarhimmel_poa(s, zu, NEIGUNG, AZIMUT)
            f = form.get(schaetzer.azimut_fach(s.azimut), 1.0)
            geo = p * f
            puffer.append((zeit, watt, p))
            if len(puffer) > 7:
                puffer.pop(0)
            sv = soc.get(zeit)
            zensiert = sv is not None and sv >= 99.0
            if not zensiert and len(puffer) >= 7:
                lang = [w for _, w, _ in puffer]
                geo_p = [q for _, _, q in puffer]
                fl = robust.entrendete_streuung(lang)
                hub = abs(geo_p[-1] - geo_p[0]) / max(max(geo_p), 1e-9)
                if (min(lang) > const.MIN_PV_W and fl is not None
                        and fl <= const.ZENSUR_FLACH_STREUUNG
                        and hub >= const.ZENSUR_GEOMETRIE_HUB):
                    zensiert = True
            if zensiert or geo <= 0:
                continue
            e_gem += watt * 5 / 60.0
            g_offen += geo * 5 / 60.0

        e_fs = fein["tagesprognose"][tag] * 1000.0
        anteil = g_offen / g_gesamt if g_gesamt else 0.0
        if anteil < 0.35 or e_fs <= 0:
            print(f"{tag}  {e_gem:7.0f} {g_offen:8.0f} {g_gesamt:9.0f} "
                  f"{100*anteil:6.0f}%  {e_fs/1000:5.2f}   verworfen")
            continue
        pegel = e_gem * g_gesamt / (g_offen * e_fs)
        werte.append(pegel)
        print(f"{tag}  {e_gem:7.0f} {g_offen:8.0f} {g_gesamt:9.0f} "
              f"{100*anteil:6.0f}%  {e_fs/1000:5.2f}  {pegel:6.3f}")

    if not werte:
        print("\nkeine verwertbaren Tage")
        return const.START_PEGEL
    m = robust.median(werte)
    print(f"\nMedian ueber {len(werte)} Tage: {m:.3f}   "
          f"Spanne {min(werte):.3f} bis {max(werte):.3f}")
    print(f"aktuell in const.py hinterlegter Startwert: {const.START_PEGEL}")
    if abs(m - const.START_PEGEL) / m > 0.08:
        print(f"-> START_PEGEL sollte auf {m:.2f} gesetzt werden")
    else:
        print("-> Startwert passt")
    return m


# --------------------------------------------------------------------------
# 3. Prognosefehler
# --------------------------------------------------------------------------
def pruefe_prognose(fein: dict, stand: schaetzer.Lernstand, pegel: float) -> None:
    kopf("3. Vorwaertssimulation gegen die tatsaechliche SOC-Bahn")
    heute = dt.date(2026, 8, 12)
    gain, form, _s, _b = gelernte_lage(stand, heute)

    profil = [float(x) for x in const.START_HAUSLAST_W]
    tagesprognose = fein.get("tagesprognose") or {}

    zeilen = []
    for tag in sorted(fein["tage"]):
        soc_reihe = reihe(fein, tag, "soc")
        pv_reihe = reihe(fein, tag, "pv")
        soc_map = dict(soc_reihe)
        voll = next((t for t, v in soc_reihe if v >= 100), None)
        roh_fs = [
            (dt.datetime.combine(dt.date.fromisoformat(tag),
                                 dt.time(*map(int, hm.split(":"))), TZ), v)
            for hm, v in fein["prognose_roh"][tag]
        ]

        for stunde in range(8, 17):
            t0 = dt.datetime.combine(
                dt.date.fromisoformat(tag), dt.time(stunde, 0), TZ
            )
            soc0 = soc_map.get(t0)
            if soc0 is None or soc0 >= 100:
                continue
            fs_rest = None
            for ts, v in roh_fs:
                if ts <= t0:
                    fs_rest = v
            if not fs_rest or fs_rest <= 0.1:
                continue

            # Truebung des Resttags aus Forecast.Solar mal gelerntem Pegel.
            # Der Pegel ist hier der Startwert - genau die Lage am ersten
            # Betriebstag.
            summe = 0.0
            for i in range(96):
                mitte = (t0 + dt.timedelta(minutes=(i + 0.5) * 15))
                if mitte.date() != t0.date():
                    break
                mu = mitte.astimezone(dt.timezone.utc)
                s = sonne.sonnenstand(mu, BREITE, LAENGE)
                if s.hoehe <= 0:
                    continue
                p = sonne.klarhimmel_poa(s, mu, NEIGUNG, AZIMUT)
                fach = schaetzer.azimut_fach(s.azimut)
                f = form.get(fach, 1.0) if fach is not None else 1.0
                summe += gain * p * f * 0.25
            if summe < 50:
                continue
            truebung = min(max(
                pegel * fs_rest * 1000.0 / summe,
                const.TRUEBUNG_MIN), const.TRUEBUNG_MAX)

            # Live-Truebung aus dem 15-Minuten-Mittel vor t0
            fenster = [v for t, v in pv_reihe if t0 - dt.timedelta(minutes=15) < t <= t0]
            live = None
            mu0 = t0.astimezone(dt.timezone.utc)
            s0 = sonne.sonnenstand(mu0, BREITE, LAENGE)
            p0 = sonne.klarhimmel_poa(s0, mu0, NEIGUNG, AZIMUT)
            f0 = form.get(schaetzer.azimut_fach(s0.azimut), 1.0)
            klar0 = gain * p0 * f0
            if fenster and klar0 > 120:
                live = min(max(st.fmean(fenster) / klar0,
                               const.TRUEBUNG_MIN), const.TRUEBUNG_MAX)

            umgebung = modell.Umgebung(
                breite=BREITE, laenge=LAENGE, neigung=NEIGUNG, modul_azimut=AZIMUT,
                kapazitaet_kwh=5.1, ac_grenze_w=800.0, max_ladeleistung_w=3000.0,
                soc_max=100.0, soc_min=12.0,
                eta=const.START_ETA, gain=gain, form=form,
                hauslast_werktag=profil, hauslast_wochenende=profil,
                truebung_live=live, truebung_prognose=truebung,
                truebung_prognose_morgen=truebung,
            )
            lauf = modell.simuliere(umgebung, t0, soc0, TZ, stunden=12.0)

            ist_max = max(v for t, v in soc_reihe if t >= t0)
            ist_t = next(t for t, v in soc_reihe if t >= t0 and v >= ist_max)
            grenze = voll or max(t for t, _ in soc_reihe)
            paare = []
            for t, v in lauf.bahn:
                if t0 <= t <= grenze:
                    naechst = min(soc_reihe, key=lambda p: abs(p[0] - t))
                    paare.append((v, naechst[1]))
            rmse = math.sqrt(st.fmean([(a - b) ** 2 for a, b in paare])) if paare else float("nan")
            t_max = lauf.t_soc_max or t0
            zeilen.append({
                "tag": tag, "start": f"{stunde:02d}:00",
                "d_max": lauf.soc_max - ist_max,
                "d_zeit": (t_max - ist_t).total_seconds() / 60.0,
                "rmse": rmse, "truebung": truebung, "live": live,
            })

    if not zeilen:
        print("keine auswertbaren Laeufe")
        return

    d_max = [z["d_max"] for z in zeilen]
    d_zeit = [z["d_zeit"] for z in zeilen]
    rmse = [z["rmse"] for z in zeilen if not math.isnan(z["rmse"])]
    print(f"n = {len(zeilen)} Laeufe (4 Tage x stuendliche Startzeitpunkte)\n")
    print("Konfiguration                                   Bias    MAE   Zeit   RMSE")
    print("alt   EXP 2.0 / 0.6-1.6 / 20 min / Profil alt   -28.6  28.64    95   17.2")
    print("empf. aus docs/PROGNOSE.md Abschnitt 7           -7.7   7.72    43    7.3")
    print(
        f"neu   Lernprognose (Form und Pegel gelernt)     "
        f"{st.fmean(d_max):6.1f} {st.fmean([abs(x) for x in d_max]):6.2f} "
        f"{st.fmean([abs(x) for x in d_zeit]):5.0f} "
        f"{st.fmean(rmse) if rmse else float('nan'):6.1f}"
    )
    print(
        "\nHinweis: Der Maximal-SOC ist auf allen vier Tagen zensiert (der "
        "Speicher\nwurde jedes Mal voll). Aussagekraeftig ist der RMSE der "
        "SOC-Bahn."
    )

    print("\nje Tag:")
    for tag in sorted({z["tag"] for z in zeilen}):
        teil = [z for z in zeilen if z["tag"] == tag]
        print(
            f"  {tag}  n={len(teil):2d}  Bias {st.fmean([z['d_max'] for z in teil]):6.1f} pp"
            f"  RMSE {st.fmean([z['rmse'] for z in teil if not math.isnan(z['rmse'])]):5.1f} pp"
            f"  Truebung {st.fmean([z['truebung'] for z in teil]):.2f}"
        )


# --------------------------------------------------------------------------
def main() -> None:
    fein = lade_daten()
    pruefe_geometrie(fein)
    stand = _fuettere(fein)
    pruefe_form(fein, stand)
    pegel = pruefe_pegel(fein, stand)
    pruefe_prognose(fein, stand, pegel)
    print()


if __name__ == "__main__":
    main()
