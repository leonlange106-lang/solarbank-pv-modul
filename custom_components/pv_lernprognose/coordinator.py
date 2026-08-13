"""Abtastung, Lernen, Simulation.

Ein einziger Coordinator, der im Minutentakt laeuft. Der Ablauf je Takt:

  1. Anlagenkennwerte aus dem Geraet nachfuehren (kennwerte.py)
  2. Messwerte lesen und in einen Ringpuffer legen
  3. aus dem Ringpuffer bestimmen, ob dieser Moment KLAR (keine Wolke) und
     UNZENSIERT (keine Abregelung) ist
  4. die Schaetzer fuettern - die Tagesform nur mit klaren, unzensierten
     Momenten, die uebrigen mit allem, was fuer sie gueltig ist
  5. mit dem aktuellen Lernstand die Vorwaertssimulation rechnen
  6. Ergebnis fuer die Entities bereitstellen

Die Zensurerkennung ist der Grund, warum niemand den 08.08.2026 von Hand
ausschliessen muss. Sie kennt zwei Muster:

  - Der SOC steht am oberen Anschlag. Dann drosselt die Nulleinspeisung
    die PV auf die Hauslast, und die Messung zeigt nicht mehr das
    Dargebot.
  - Die Leistung steht still, waehrend die Sonne weiterwandert. Genau das
    Muster des Drosselungstests: sechs Stunden konstant 798 W, waehrend
    die geometrische Erwartung sich um ein Vielfaches aendert. Kein
    Naturvorgang sieht so aus.
"""

from __future__ import annotations

import datetime as dt
import logging
from collections import deque
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from . import robust
from .const import (
    ABTASTUNG_S,
    CONF_AZIMUT,
    CONF_NEIGUNG,
    DEFAULT_AZIMUT,
    DEFAULT_NEIGUNG,
    FENSTER_HAUSLAST_TAGE,
    KLARHEIT_FENSTER_MIN,
    KLARHEIT_SCHWELLE,
    MIN_POA_W,
    MIN_PV_W,
    MIN_SONNENHOEHE,
    QUELLE_DROSSELUNG_W,
    QUELLE_ENTLADEENERGIE_KWH,
    QUELLE_FS_HEUTE_KWH,
    QUELLE_FS_MORGEN_KWH,
    QUELLE_FS_REST_KWH,
    QUELLE_HAUSLAST_W,
    QUELLE_LADEENERGIE_KWH,
    QUELLE_PV_W,
    QUELLE_SOC,
    QUELLE_ZIEL_SOC,
    SPEICHERN_S,
    STORE_KEY,
    STORE_VERSION,
    TRUEBUNG_MAX,
    TRUEBUNG_MIN,
    ZENSUR_FLACH_MIN,
    ZENSUR_FLACH_STREUUNG,
    ZENSUR_GEOMETRIE_HUB,
    ZENSUR_SOC_ABSTAND,
)
from .kennwerte import Anlage, lies_zahl
from .modell import Umgebung, formuliere, klarleistung, simuliere
from .schaetzer import Lernstand, azimut_fach
from .sonne import klarhimmel_poa, sonnenauf_und_untergang, sonnenstand

_LOGGER = logging.getLogger(__name__)

PUFFER_LAENGE = max(ZENSUR_FLACH_MIN, KLARHEIT_FENSTER_MIN) * 60 // ABTASTUNG_S + 2


class LernprognoseCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Haelt Lernstand und Prognose."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name="PV Lernprognose",
            update_interval=dt.timedelta(seconds=ABTASTUNG_S),
        )
        self.entry = entry
        self.anlage = Anlage()
        self.lernstand = Lernstand()
        self._store: Store = Store(hass, STORE_VERSION, STORE_KEY)
        self._puffer: deque[tuple[dt.datetime, float, float]] = deque(
            maxlen=PUFFER_LAENGE
        )
        self._zuletzt_gespeichert: dt.datetime | None = None
        self._letzter_takt: dt.datetime | None = None
        self._geom_tag: str | None = None
        self._geom_gesamt: float = 0.0
        self._geom_stunde: int | None = None

        self.breite = hass.config.latitude
        self.laenge = hass.config.longitude
        self.neigung = float(entry.options.get(
            CONF_NEIGUNG, entry.data.get(CONF_NEIGUNG, DEFAULT_NEIGUNG)
        ))
        self.modul_azimut = float(entry.options.get(
            CONF_AZIMUT, entry.data.get(CONF_AZIMUT, DEFAULT_AZIMUT)
        ))

    # ------------------------------------------------------------------
    # Persistenz
    # ------------------------------------------------------------------
    async def async_laden(self) -> None:
        gespeichert = await self._store.async_load()
        if gespeichert:
            self.lernstand.aus_dict(gespeichert)
            _LOGGER.info(
                "Lernstand geladen: Hauslast %d Tage, Tagesform %d Tage, "
                "Pegel %d Tage, Wirkungsgrad %d Tage",
                len(self.lernstand.hauslast.tage),
                len(self.lernstand.form.tage),
                len(self.lernstand.pegel.tage),
                len(self.lernstand.eta.tage),
            )
        else:
            _LOGGER.info(
                "Kein Lernstand vorhanden. Alle Schaetzer starten mit ihrem "
                "begruendeten Startwert und weisen das als gelernt=false aus."
            )
            await self._bootstrap_hauslast()

    async def async_speichern(self) -> None:
        await self._store.async_save(self.lernstand.zu_dict())
        self._zuletzt_gespeichert = dt_util.utcnow()

    async def _bootstrap_hauslast(self) -> None:
        """Kaltstarthilfe: Stundenmittel der Hauslast aus der Langzeitstatistik.

        Bewusst als Notbehelf gekennzeichnet. Die Langzeitstatistik liefert
        Stundenmittel, nicht Stundenmediane - ein Reglertest schlaegt darin
        also durch. Solange zu wenige Tage vorliegen, gilt ohnehin der
        Startwert; sobald genug eigene Tage da sind, verdraengen die
        gemessenen Mediane die Bootstrap-Tage aus dem Fenster.
        """
        try:
            from homeassistant.components.recorder import get_instance
            from homeassistant.components.recorder.statistics import (
                statistics_during_period,
            )
        except ImportError:  # pragma: no cover
            return

        quelle = None
        for kandidat in QUELLE_HAUSLAST_W:
            if self.hass.states.get(kandidat) is not None:
                quelle = kandidat
                break
        if quelle is None:
            return

        ende = dt_util.utcnow()
        start = ende - dt.timedelta(days=FENSTER_HAUSLAST_TAGE)
        try:
            roh = await get_instance(self.hass).async_add_executor_job(
                lambda: statistics_during_period(
                    self.hass, start, ende, {quelle}, "hour", None, {"mean"}
                )
            )
        except Exception as exc:  # noqa: BLE001 - darf das Setup nie kippen
            _LOGGER.debug("Bootstrap der Hauslast nicht moeglich: %s", exc)
            return

        reihen = roh.get(quelle) or []
        zeitzone = dt_util.get_time_zone(self.hass.config.time_zone)
        gesammelt: dict[str, dict[str, float]] = {}
        for eintrag in reihen:
            mittel = eintrag.get("mean")
            if mittel is None:
                continue
            beginn = eintrag.get("start")
            if isinstance(beginn, (int, float)):
                zeit = dt.datetime.fromtimestamp(beginn, dt.timezone.utc)
            else:
                zeit = beginn
            if zeit is None:
                continue
            lokal = zeit.astimezone(zeitzone)
            if not (0.0 <= float(mittel) <= 30000.0):
                continue
            gesammelt.setdefault(lokal.date().isoformat(), {})[
                str(lokal.hour)
            ] = round(float(mittel), 1)

        # Nur Tage uebernehmen, die weitgehend vollstaendig sind.
        uebernommen = {t: p for t, p in gesammelt.items() if len(p) >= 20}
        if not uebernommen:
            return
        self.lernstand.hauslast.tage.update(uebernommen)
        self.lernstand.hauslast.bootstrap_tage |= set(uebernommen)
        self.lernstand.bootstrap = {
            "hauslast_quelle": quelle,
            "hauslast_tage": len(uebernommen),
            "hauslast_verfahren": "Stundenmittel aus der Langzeitstatistik",
            "hinweis": (
                "Vorbelegte Tage gehen in den Wert ein, zaehlen aber nicht "
                "fuer die Aussage `gelernt` - sie sind Stundenmittel, keine "
                "Stundenmediane, und ein Reglertest schlaegt darin durch."
            ),
        }
        _LOGGER.info(
            "Hauslast aus %d Tagen Langzeitstatistik von %s vorbelegt. Diese "
            "Tage zaehlen nicht fuer `gelernt`.",
            len(uebernommen), quelle,
        )

    # ------------------------------------------------------------------
    # Takt
    # ------------------------------------------------------------------
    async def _async_update_data(self) -> dict[str, Any]:
        jetzt = dt_util.now()
        jetzt_utc = jetzt.astimezone(dt.timezone.utc)
        zeitzone = jetzt.tzinfo

        self.anlage.aktualisiere(self.hass)

        pv_w, _ = lies_zahl(self.hass, QUELLE_PV_W)
        soc, _ = lies_zahl(self.hass, QUELLE_SOC)
        hauslast_w, hauslast_quelle = lies_zahl(self.hass, QUELLE_HAUSLAST_W)
        lade_kwh, _ = lies_zahl(self.hass, QUELLE_LADEENERGIE_KWH)
        entlade_kwh, _ = lies_zahl(self.hass, QUELLE_ENTLADEENERGIE_KWH)
        drosselung_w, _ = lies_zahl(self.hass, QUELLE_DROSSELUNG_W)
        fs_heute, _ = lies_zahl(self.hass, QUELLE_FS_HEUTE_KWH)
        fs_rest, _ = lies_zahl(self.hass, QUELLE_FS_REST_KWH)
        fs_morgen, _ = lies_zahl(self.hass, QUELLE_FS_MORGEN_KWH)
        ziel_soc, _ = lies_zahl(self.hass, QUELLE_ZIEL_SOC)

        stand = sonnenstand(jetzt_utc, self.breite, self.laenge)
        poa = klarhimmel_poa(stand, jetzt_utc, self.neigung, self.modul_azimut)

        # --- Lernstand auswerten (vor dem Fuettern, damit die Geometrie
        #     des laufenden Takts mit demselben Stand gerechnet wird) ----
        heute = jetzt.date()
        gain, gain_gelernt, form, _tage_je_fach, _proben = (
            self.lernstand.form.gain_und_form(heute)
        )
        form_jetzt, form_direkt = self.lernstand.form.form_bei(form, stand.azimut)
        geometrie = poa * form_jetzt            # W/m2, ohne Gain
        p_klar = gain * geometrie               # W

        # --- Puffer -------------------------------------------------------
        if pv_w is not None:
            self._puffer.append((jetzt, pv_w, poa))

        klar = self._ist_klar()
        zensiert = self._ist_zensiert(soc, drosselung_w)

        # --- Schaetzer fuettern -------------------------------------------
        if hauslast_w is not None:
            self.lernstand.hauslast.probe(jetzt, hauslast_w)

        if (
            not zensiert
            and klar
            and pv_w is not None
            and pv_w >= MIN_PV_W
            and poa >= MIN_POA_W
            and stand.hoehe >= MIN_SONNENHOEHE
        ):
            self.lernstand.form.probe(jetzt, stand.azimut, pv_w, poa)

        self._pegel_takt(jetzt, pv_w, geometrie, zensiert,
                         fs_heute, stand.hoehe, form)

        self.lernstand.eta.probe(
            jetzt, soc, lade_kwh, entlade_kwh, self.anlage.kapazitaet.wert
        )

        self._letzter_takt = jetzt

        # --- Truebung -----------------------------------------------------
        truebung_live = self._truebung_live(p_klar, zensiert)
        truebung_prognose, truebung_quelle = self._truebung_prognose(
            jetzt_utc, zeitzone, fs_rest, gain, form
        )
        truebung_morgen = self._truebung_morgen(jetzt, zeitzone, fs_morgen, gain, form)

        # --- Simulation ---------------------------------------------------
        pegel_info = self.lernstand.pegel.wert(heute)
        eta_info = self.lernstand.eta.wert(heute)
        werktag_profil, werktag_n, werktag_eigen = self.lernstand.hauslast.profil(
            heute, False
        )
        we_profil, we_n, we_eigen = self.lernstand.hauslast.profil(heute, True)

        umgebung = Umgebung(
            breite=self.breite,
            laenge=self.laenge,
            neigung=self.neigung,
            modul_azimut=self.modul_azimut,
            kapazitaet_kwh=self.anlage.kapazitaet.wert,
            ac_grenze_w=self.anlage.ac_grenze.wert,
            max_ladeleistung_w=self.anlage.max_ladeleistung.wert,
            soc_max=self.anlage.soc_max.wert,
            soc_min=self.anlage.soc_min.wert,
            eta=eta_info["eta"],
            gain=gain,
            form=form,
            hauslast_werktag=werktag_profil,
            hauslast_wochenende=we_profil,
            truebung_live=truebung_live,
            truebung_prognose=truebung_prognose,
            truebung_prognose_morgen=truebung_morgen,
        )

        text = "Prognose nicht moeglich"
        lauf = None
        if soc is not None:
            lauf = simuliere(umgebung, jetzt, soc, zeitzone, ziel_soc)
            text = formuliere(lauf, jetzt, soc, umgebung, zeitzone)

        # --- Speichern ----------------------------------------------------
        if (
            self._zuletzt_gespeichert is None
            or (dt_util.utcnow() - self._zuletzt_gespeichert).total_seconds()
            >= SPEICHERN_S
        ):
            self.lernstand.aufraeumen(heute)
            await self.async_speichern()

        return {
            "jetzt": jetzt,
            "soc": soc,
            "pv_w": pv_w,
            "hauslast_w": hauslast_w,
            "hauslast_quelle": hauslast_quelle,
            "sonnenhoehe": round(stand.hoehe, 2),
            "sonnenazimut": round(stand.azimut, 2),
            "poa": round(poa, 1),
            "p_klar": round(p_klar, 1),
            "form_jetzt": round(form_jetzt, 3),
            "form_direkt_gemessen": form_direkt,
            "klar": klar,
            "zensiert": zensiert,
            "truebung_live": truebung_live,
            "truebung_prognose": truebung_prognose,
            "truebung_quelle": truebung_quelle,
            "gain": gain,
            "gain_gelernt": gain_gelernt,
            "text": text,
            "lauf": lauf,
            "ziel_soc": ziel_soc,
            "hauslast_info": {
                "werktag": [round(x, 1) for x in werktag_profil],
                "wochenende": [round(x, 1) for x in we_profil],
                "stichprobe_werktag": werktag_n,
                "stichprobe_wochenende": we_n,
                "selbst_gemessen_werktag": werktag_eigen,
                "selbst_gemessen_wochenende": we_eigen,
            },
            "pegel_info": pegel_info,
            "eta_info": eta_info,
            "form_info": self.lernstand.form.wert(heute, stand.azimut),
            "hauslast_wert": self.lernstand.hauslast.wert(
                heute, jetzt.weekday() >= 5
            ),
        }

    # ------------------------------------------------------------------
    # Klarheit und Zensur
    # ------------------------------------------------------------------
    def _ist_klar(self) -> bool:
        """Stand die Sonne in den letzten Minuten frei?

        Kriterium ist die Abweichung der gemessenen Leistung von ihrer
        eigenen Ausgleichsgeraden. Ueber eine Viertelstunde ist die
        Klarhimmelkurve nahezu linear; was daneben liegt, ist Bewoelkung.
        """
        n = KLARHEIT_FENSTER_MIN * 60 // ABTASTUNG_S
        if len(self._puffer) < n:
            return False
        letzte = list(self._puffer)[-n:]
        # Luecken im Puffer (Neustart, Sensorausfall) entwerten das Fenster.
        spanne = (letzte[-1][0] - letzte[0][0]).total_seconds()
        if spanne > KLARHEIT_FENSTER_MIN * 60 * 1.6:
            return False
        werte = [w for _, w, _ in letzte]
        streuung = robust.entrendete_streuung(werte)
        return streuung is not None and streuung <= KLARHEIT_SCHWELLE

    def _ist_zensiert(self, soc: float | None, drosselung_w: float | None) -> bool:
        """Ist die Messung gerade durch Regelung verfaelscht?"""
        # 1) Speicher am oberen Anschlag -> die Nulleinspeisung drosselt.
        if soc is not None and soc >= self.anlage.soc_max.wert - ZENSUR_SOC_ABSTAND:
            return True

        # 2) Ein anderer Teil der Anlage meldet aktive Drosselung.
        if drosselung_w is not None and drosselung_w > 20.0:
            return True

        # 3) Die Leistung steht still, waehrend die Geometrie sich bewegt.
        #    Das Muster des Drosselungstests vom 08.08.2026.
        n = ZENSUR_FLACH_MIN * 60 // ABTASTUNG_S
        if len(self._puffer) >= n:
            letzte = list(self._puffer)[-n:]
            spanne = (letzte[-1][0] - letzte[0][0]).total_seconds()
            if spanne <= ZENSUR_FLACH_MIN * 60 * 1.6:
                leistung = [w for _, w, _ in letzte]
                geometrie = [p for _, _, p in letzte]
                if min(leistung) > MIN_PV_W and max(geometrie) > MIN_POA_W:
                    streuung = robust.entrendete_streuung(leistung)
                    hub = abs(geometrie[-1] - geometrie[0]) / max(
                        max(geometrie), 1e-9
                    )
                    if (
                        streuung is not None
                        and streuung <= ZENSUR_FLACH_STREUUNG
                        and hub >= ZENSUR_GEOMETRIE_HUB
                    ):
                        return True
        return False

    # ------------------------------------------------------------------
    # Truebung
    # ------------------------------------------------------------------
    def _truebung_live(self, p_klar: float, zensiert: bool) -> float | None:
        """Bewoelkungsindex aus der aktuellen Messung.

        Nur wenn die Erwartung gross genug ist, um ein Verhaeltnis zu
        tragen, und nur wenn nicht abgeregelt wird. Ohne die Zensurpruefung
        wuerde bei vollem Speicher die gedrosselte Leistung als Bewoelkung
        gelesen - und die Prognose fuer den Rest des Tages entsprechend
        heruntergezogen. Genau der Fehler, an dem das alte k litt, nur mit
        anderer Ursache.
        """
        if zensiert or p_klar < 120.0 or len(self._puffer) < 5:
            return None
        letzte = list(self._puffer)[-5:]
        mittel = sum(w for _, w, _ in letzte) / len(letzte)
        wert = mittel / p_klar
        return min(max(wert, TRUEBUNG_MIN), TRUEBUNG_MAX)

    def _geometrie_tagessumme(
        self, tag: dt.date, form: dict[int, float]
    ) -> float:
        """Integral von POA mal Tagesform ueber einen ganzen Tag, in Wh/m2.

        Bewusst ohne Systemgain: so kuerzt der Gain sich im Pegel exakt
        heraus (siehe Pegelschaetzer).
        """
        summe = 0.0
        basis = dt.datetime(tag.year, tag.month, tag.day, tzinfo=dt.timezone.utc)
        for i in range(96):
            t = basis + dt.timedelta(minutes=(i + 0.5) * 15)
            s = sonnenstand(t, self.breite, self.laenge)
            if s.hoehe <= 0.0:
                continue
            p = klarhimmel_poa(s, t, self.neigung, self.modul_azimut)
            fach = azimut_fach(s.azimut)
            f = form.get(fach, 1.0) if fach is not None else 1.0
            summe += p * f * 0.25
        return summe

    def _pegel_takt(
        self,
        jetzt: dt.datetime,
        pv_w: float | None,
        geometrie: float,
        zensiert: bool,
        fs_heute: float | None,
        sonnenhoehe: float,
        form: dict[int, float],
    ) -> None:
        tag = jetzt.date().isoformat()
        if self.lernstand.pegel.heute != tag:
            self.lernstand.pegel.tag_abschliessen()
            gesamt = self._geometrie_tagessumme(jetzt.date(), form)
            self.lernstand.pegel.neuer_tag(tag, gesamt)
            self._geom_tag = tag
            self._geom_gesamt = gesamt
            self._geom_stunde = jetzt.hour
        elif self._geom_stunde != jetzt.hour:
            # Die Tagesform kann sich im Lauf des Tages verfeinern. Einmal
            # je Stunde nachziehen genuegt.
            gesamt = self._geometrie_tagessumme(jetzt.date(), form)
            self.lernstand.pegel.e_klar_gesamt = gesamt
            self._geom_gesamt = gesamt
            self._geom_stunde = jetzt.hour

        if pv_w is not None:
            sekunden = float(ABTASTUNG_S)
            if self._letzter_takt is not None:
                gemessen = (jetzt - self._letzter_takt).total_seconds()
                # Nach einem Neustart klafft eine Luecke. Nicht hochrechnen.
                if 0 < gemessen <= ABTASTUNG_S * 3:
                    sekunden = gemessen
            self.lernstand.pegel.probe(jetzt, pv_w, geometrie, sekunden, zensiert)

        if fs_heute is not None and sonnenhoehe > 0.0:
            self.lernstand.pegel.merke_prognose(fs_heute)

    def _truebung_prognose(
        self,
        jetzt_utc: dt.datetime,
        zeitzone: dt.tzinfo,
        fs_rest: float | None,
        gain: float,
        form: dict[int, float],
    ) -> tuple[float, str]:
        """Bewoelkungsindex fuer den Rest des Tages aus Forecast.Solar.

        Der gelernte Pegel korrigiert dabei den systematischen Bias der
        API. Ist noch nichts gelernt, gilt der Startwert 1.30 aus dem
        Backtest - und der Pegelsensor sagt, dass es ein Startwert ist.
        """
        pegel = self.lernstand.pegel.wert(jetzt_utc.date())["pegel"]
        if fs_rest is None or fs_rest <= 0.0:
            return 1.0, "keine Prognose, Klarhimmel angenommen"

        # Klarhimmelerwartung fuer den Rest des Tages, geometrisch.
        summe = 0.0
        t = jetzt_utc
        lokal_heute = jetzt_utc.astimezone(zeitzone).date()
        for i in range(96):
            mitte = t + dt.timedelta(minutes=(i + 0.5) * 15)
            if mitte.astimezone(zeitzone).date() != lokal_heute:
                break
            s = sonnenstand(mitte, self.breite, self.laenge)
            if s.hoehe <= 0.0:
                continue
            p = klarhimmel_poa(s, mitte, self.neigung, self.modul_azimut)
            fach = azimut_fach(s.azimut)
            f = form.get(fach, 1.0) if fach is not None else 1.0
            summe += gain * p * f * 0.25
        if summe < 50.0:
            return 1.0, "Resttag zu kurz"
        wert = pegel * fs_rest * 1000.0 / summe
        return min(max(wert, TRUEBUNG_MIN), TRUEBUNG_MAX), "Forecast.Solar mal Pegel"

    def _truebung_morgen(
        self,
        jetzt: dt.datetime,
        zeitzone: dt.tzinfo,
        fs_morgen: float | None,
        gain: float,
        form: dict[int, float],
    ) -> float:
        pegel = self.lernstand.pegel.wert(jetzt.date())["pegel"]
        if fs_morgen is None or fs_morgen <= 0.0:
            return 1.0
        morgen = jetzt.date() + dt.timedelta(days=1)
        summe = gain * self._geometrie_tagessumme(morgen, form)
        if summe < 50.0:
            return 1.0
        wert = pegel * fs_morgen * 1000.0 / summe
        return min(max(wert, TRUEBUNG_MIN), TRUEBUNG_MAX)

    # ------------------------------------------------------------------
    def sonnenzeiten(self, tag: dt.date) -> tuple[dt.datetime | None, dt.datetime | None]:
        return sonnenauf_und_untergang(tag, self.breite, self.laenge)
