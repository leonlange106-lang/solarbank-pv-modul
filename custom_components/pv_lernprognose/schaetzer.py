"""Die mitlaufenden Schaetzer.

Jede empirische Groesse der Prognose steckt hier und wird aus der eigenen
Beobachtung gebildet. Gemeinsames Muster aller vier Schaetzer:

  Zweistufiger Median. Erst wird je Tag verdichtet (Median ueber die
  Messpunkte des Tages), dann ueber die Tage (gewichteter Median ueber das
  gleitende Fenster). Zwei Stufen deshalb, weil beide Fehlerarten
  vorkommen: einzelne verrueckte Messpunkte innerhalb eines Tages
  (Reglertest um 14 Uhr) und ganze verrueckte Tage (Drosselungstest am
  08.08.). Ein einstufiger Median ueber alle Punkte wuerde einen langen
  schlechten Tag durchlassen, weil er viele Punkte beisteuert.

  Ausreisserfilter nach MAD vor der zweiten Stufe. Ein Tag, der um mehr
  als 3.5 modifizierte z-Werte abweicht, faellt heraus - ohne dass ihn
  jemand benennt.

  Rezenzgewichtung. Ein Tag von heute wiegt doppelt so viel wie einer von
  vor 14 Tagen. Damit folgen die Schaetzer geaenderten Gewohnheiten und
  der Jahreszeit, statt ueber das ganze Fenster zu mitteln.

  Ehrliche Auskunft. Jeder Schaetzer meldet `gelernt` und `stichprobe`.
  Solange zu wenig vorliegt, liefert er seinen begruendeten Startwert und
  sagt genau das.
"""

from __future__ import annotations

import datetime as dt
import logging
import math
from typing import Any

from . import robust
from .const import (
    AZIMUT_BIN,
    AZIMUT_BIS,
    AZIMUT_VON,
    ETA_MAX,
    ETA_MIN,
    FENSTER_ETA_TAGE,
    FENSTER_FORM_TAGE,
    FENSTER_HAUSLAST_TAGE,
    FENSTER_PEGEL_TAGE,
    FORM_MAX,
    FORM_MIN,
    GAIN_QUANTIL,
    HALBWERTSZEIT_TAGE,
    MIN_FAECHER_GAIN,
    MIN_PROBEN_FORM,
    MIN_TAGE_ETA,
    MIN_TAGE_FORM,
    MIN_TAGE_HAUSLAST,
    MIN_TAGE_PEGEL,
    BEREICH_GAIN,
    START_ETA,
    START_GAIN,
    START_HAUSLAST_W,
    START_PEGEL,
)

_LOGGER = logging.getLogger(__name__)


def _alter_tage(tag: str, heute: dt.date) -> float:
    try:
        d = dt.date.fromisoformat(tag)
    except ValueError:
        return 1e6
    return (heute - d).days


def _im_fenster(tage: dict[str, Any], heute: dt.date, fenster: int) -> dict[str, Any]:
    return {t: v for t, v in tage.items() if 0 <= _alter_tage(t, heute) < fenster}


def _gewicht(tag: str, heute: dt.date) -> float:
    return robust.rezenzgewicht(_alter_tage(tag, heute), HALBWERTSZEIT_TAGE)


def azimut_fach(azimut: float) -> int | None:
    """Ordnet einen Sonnenazimut seinem Fach zu. None ausserhalb des Bereichs."""
    if azimut < AZIMUT_VON or azimut >= AZIMUT_BIS:
        return None
    return int((azimut - AZIMUT_VON) // AZIMUT_BIN)


def fach_azimut(fach: int) -> float:
    """Mitte eines Fachs in Grad."""
    return AZIMUT_VON + (fach + 0.5) * AZIMUT_BIN


class Hauslastschaetzer:
    """Rollierendes robustes Stundenprofil, getrennt nach Werktag und Wochenende.

    Warum getrennt: das Verbrauchsmuster am Samstagvormittag hat mit dem am
    Dienstagvormittag wenig zu tun. Warum nicht je Wochentag einzeln: bei
    28 Tagen Fenster blieben je Wochentag vier Werte - zu wenig fuer einen
    Median, der einen einzelnen Waschtag ueberstehen soll.
    """

    def __init__(self) -> None:
        # tag -> stunde(str) -> Median der Sekundenmesswerte dieses Tages
        self.tage: dict[str, dict[str, float]] = {}
        self.heute: str | None = None
        self.laufend: dict[str, list[float]] = {}
        # Tage, die beim Kaltstart aus der Langzeitstatistik vorbelegt
        # wurden. Sie sind Stundenmittel, keine Stundenmediane - ein
        # Reglertest schlaegt darin durch. Sie gehen deshalb in den WERT
        # ein (besser als nichts), zaehlen aber NICHT fuer die Aussage
        # "gelernt". Diese Aussage ist eine Behauptung ueber die eigene
        # Beobachtung, und die faengt bei null an.
        self.bootstrap_tage: set[str] = set()

    # -- Aufnahme ----------------------------------------------------------
    def probe(self, jetzt: dt.datetime, watt: float) -> None:
        tag = jetzt.date().isoformat()
        if self.heute != tag:
            self.tag_abschliessen()
            self.heute = tag
            self.laufend = {}
        if watt < 0.0 or watt > 30000.0:
            return
        self.laufend.setdefault(str(jetzt.hour), []).append(watt)

    def tag_abschliessen(self) -> None:
        if self.heute is None or not self.laufend:
            return
        verdichtet: dict[str, float] = {}
        for stunde, werte in self.laufend.items():
            # Mindestens ein Drittel der Stunde muss beobachtet sein, sonst
            # ist der Stundenmedian ein Zufallsausschnitt.
            if len(werte) < 20:
                continue
            m = robust.median(werte)
            if m is not None:
                verdichtet[stunde] = round(m, 1)
        if verdichtet:
            self.tage[self.heute] = verdichtet

    # -- Auswertung --------------------------------------------------------
    def _fenster(self, heute: dt.date) -> dict[str, dict[str, float]]:
        alle = dict(self.tage)
        # Der laufende Tag zaehlt bereits mit, soweit verdichtbar.
        if self.heute and self.laufend:
            teil = {
                s: round(robust.median(w), 1)
                for s, w in self.laufend.items()
                if len(w) >= 20 and robust.median(w) is not None
            }
            if teil:
                alle[self.heute] = teil
        return _im_fenster(alle, heute, FENSTER_HAUSLAST_TAGE)

    def profil(
        self, heute: dt.date, wochenende: bool
    ) -> tuple[list[float], list[int], list[int]]:
        """24 Stundenwerte in W, Stichprobe je Stunde, davon selbst gemessen.

        Der Wert nutzt alles, was da ist - auch vorbelegte Tage. Die dritte
        Rueckgabe zaehlt nur die selbst beobachteten Tage und entscheidet
        allein darueber, ob die Stunde als gelernt gilt.
        """
        fenster = self._fenster(heute)
        werte: list[float] = []
        n: list[int] = []
        n_eigen: list[int] = []
        for stunde in range(24):
            paare: list[tuple[float, float]] = []
            eigen = 0
            for tag, profil in fenster.items():
                try:
                    ist_we = dt.date.fromisoformat(tag).weekday() >= 5
                except ValueError:
                    continue
                if ist_we != wochenende:
                    continue
                v = profil.get(str(stunde))
                if v is not None:
                    paare.append((v, _gewicht(tag, heute)))
                    if tag not in self.bootstrap_tage:
                        eigen += 1
            n.append(len(paare))
            n_eigen.append(eigen)
            if len(paare) >= MIN_TAGE_HAUSLAST:
                m = robust.robuster_gewichteter_median(paare)
                werte.append(m if m is not None else float(START_HAUSLAST_W[stunde]))
            else:
                werte.append(float(START_HAUSLAST_W[stunde]))
        return werte, n, n_eigen

    def wert(self, heute: dt.date, wochenende: bool) -> dict[str, Any]:
        werte, n, n_eigen = self.profil(heute, wochenende)
        gelernte_stunden = sum(1 for x in n_eigen if x >= MIN_TAGE_HAUSLAST)
        return {
            "profil": [round(x, 1) for x in werte],
            "stichprobe": n,
            "stichprobe_selbst_gemessen": n_eigen,
            "gelernte_stunden": gelernte_stunden,
            "gelernt": gelernte_stunden >= 24,
            "tagessumme_kwh": round(sum(werte) / 1000.0, 2),
        }

    def zu_dict(self) -> dict[str, Any]:
        return {
            "tage": self.tage,
            "heute": self.heute,
            "laufend": self.laufend,
            "bootstrap_tage": sorted(self.bootstrap_tage),
        }

    def aus_dict(self, d: dict[str, Any]) -> None:
        self.tage = dict(d.get("tage") or {})
        self.heute = d.get("heute")
        self.laufend = {k: list(v) for k, v in (d.get("laufend") or {}).items()}
        self.bootstrap_tage = set(d.get("bootstrap_tage") or [])

    def aufraeumen(self, heute: dt.date) -> None:
        self.tage = _im_fenster(self.tage, heute, FENSTER_HAUSLAST_TAGE)


class Formschaetzer:
    """Die gelernte Tageskurve - der Kern des Verfahrens.

    Ersetzt `cos^EXPONENT`. Statt einer symmetrischen Glocke wird das
    Verhaeltnis der gemessenen Leistung zur geometrischen
    Klarhimmelerwartung gelernt, und zwar je Sonnenazimut.

    Warum Azimut und nicht Uhrzeit: ein Baum oder Dachvorsprung steht fest
    im Raum. Er verschattet immer dann, wenn die Sonne in seiner Richtung
    steht - unabhaengig vom Datum. Ueber Uhrzeit indiziert wuerde die Kurve
    jeden Monat neu gelernt werden muessen; ueber Azimut indiziert wandert
    sie von selbst mit dem Sonnenlauf mit.

    Die verbleibende Abhaengigkeit ist die Sonnenhoehe: dasselbe Hindernis
    verschattet bei flacher Wintersonne staerker als bei hoher
    Sommersonne. Das faengt die Rezenzgewichtung ab - der Schaetzer folgt
    der Jahreszeit mit etwa zwei bis drei Wochen Nachlauf. Eine zweite
    Indexachse ueber die Hoehe waere physikalisch sauberer, wuerde die
    Stichprobe je Fach aber so ausduennen, dass nichts mehr eingeschwungen
    ist.

    Gespeichert wird das ROHE Verhaeltnis r = P_gemessen / POA_klar in
    W je W/m2, nicht der normierte Formwert. Damit sind Systemgain und
    Form entkoppelt: der Gain ist das obere Quantil ueber alle Faecher
    (das unverschattete Plateau), die Form ist jedes Fach relativ dazu.
    """

    def __init__(self) -> None:
        # tag -> fach(str) -> Median von r an diesem Tag in diesem Fach
        self.tage: dict[str, dict[str, float]] = {}
        self.proben: dict[str, dict[str, int]] = {}
        self.heute: str | None = None
        self.laufend: dict[str, list[float]] = {}

    def probe(self, jetzt: dt.datetime, azimut: float, pv_w: float, poa: float) -> None:
        """Ein klarer, unzensierter Messpunkt."""
        fach = azimut_fach(azimut)
        if fach is None or poa <= 0.0:
            return
        tag = jetzt.date().isoformat()
        if self.heute != tag:
            self.tag_abschliessen()
            self.heute = tag
            self.laufend = {}
        self.laufend.setdefault(str(fach), []).append(pv_w / poa)

    def tag_abschliessen(self) -> None:
        if self.heute is None or not self.laufend:
            return
        verdichtet: dict[str, float] = {}
        anzahl: dict[str, int] = {}
        for fach, werte in self.laufend.items():
            if len(werte) < 2:
                continue
            m = robust.median(werte)
            if m is not None and m > 0.0:
                verdichtet[fach] = round(m, 4)
                anzahl[fach] = len(werte)
        if verdichtet:
            self.tage[self.heute] = verdichtet
            self.proben[self.heute] = anzahl

    # -- Auswertung --------------------------------------------------------
    def _fenster(self, heute: dt.date) -> tuple[dict[str, dict[str, float]], dict[str, dict[str, int]]]:
        alle = dict(self.tage)
        anzahl = dict(self.proben)
        if self.heute and self.laufend:
            teil = {}
            teil_n = {}
            for fach, werte in self.laufend.items():
                if len(werte) < 2:
                    continue
                m = robust.median(werte)
                if m is not None and m > 0.0:
                    teil[fach] = round(m, 4)
                    teil_n[fach] = len(werte)
            if teil:
                alle[self.heute] = teil
                anzahl[self.heute] = teil_n
        return (
            _im_fenster(alle, heute, FENSTER_FORM_TAGE),
            _im_fenster(anzahl, heute, FENSTER_FORM_TAGE),
        )

    def _rohwerte(self, heute: dt.date) -> tuple[dict[int, float], dict[int, int], dict[int, int]]:
        """Je Fach: gewichteter Median von r, Anzahl Tage, Anzahl Einzelproben."""
        fenster, anzahl = self._fenster(heute)
        gesammelt: dict[int, list[tuple[float, float]]] = {}
        proben: dict[int, int] = {}
        for tag, faecher in fenster.items():
            g = _gewicht(tag, heute)
            for fach_s, r in faecher.items():
                fach = int(fach_s)
                gesammelt.setdefault(fach, []).append((r, g))
                proben[fach] = proben.get(fach, 0) + anzahl.get(tag, {}).get(fach_s, 1)

        roh: dict[int, float] = {}
        tage_je_fach: dict[int, int] = {}
        for fach, paare in gesammelt.items():
            tage_je_fach[fach] = len(paare)
            m = robust.robuster_gewichteter_median(paare)
            if m is not None and m > 0.0:
                roh[fach] = m
        return roh, tage_je_fach, proben

    def gain_und_form(
        self, heute: dt.date
    ) -> tuple[float, bool, dict[int, float], dict[int, int], dict[int, int]]:
        """Systemgain in W/(W/m2) und Formkurve je Fach.

        Der Gain ist das obere Quantil ueber die belegten Faecher: die
        Faecher darueber sind unverschattet, alles darunter ist Schatten.
        Die Form ist jedes Fach geteilt durch den Gain, geklammert auf
        einen physikalisch moeglichen Durchlassgrad.
        """
        roh, tage_je_fach, proben = self._rohwerte(heute)
        belastbar = {
            f: r
            for f, r in roh.items()
            if tage_je_fach.get(f, 0) >= MIN_TAGE_FORM
            and proben.get(f, 0) >= MIN_PROBEN_FORM
        }

        if len(belastbar) >= MIN_FAECHER_GAIN:
            g = robust.quantil(sorted(belastbar.values()), GAIN_QUANTIL)
            gain_gelernt = True
        else:
            g = None
            gain_gelernt = False

        if g is None or not (BEREICH_GAIN[0] <= g <= BEREICH_GAIN[1]):
            g = START_GAIN
            gain_gelernt = False

        form = {
            f: min(max(r / g, FORM_MIN), FORM_MAX) for f, r in belastbar.items()
        }
        return g, gain_gelernt, form, tage_je_fach, proben

    def form_bei(self, form: dict[int, float], azimut: float) -> tuple[float, bool]:
        """Formwert fuer einen Azimut, mit linearer Interpolation.

        Ist das Fach nicht gelernt, wird zwischen den naechsten gelernten
        Nachbarn interpoliert. Gibt es keine, ist die Form 1.0 - also
        "keine Verschattung bekannt", was der ehrliche Rueckfall ist.
        """
        fach = azimut_fach(azimut)
        if fach is None or not form:
            return 1.0, False
        if fach in form:
            return form[fach], True

        links = max((f for f in form if f < fach), default=None)
        rechts = min((f for f in form if f > fach), default=None)
        if links is not None and rechts is not None:
            anteil = (fach - links) / (rechts - links)
            return form[links] * (1 - anteil) + form[rechts] * anteil, False
        if links is not None:
            return form[links], False
        if rechts is not None:
            return form[rechts], False
        return 1.0, False

    def wert(self, heute: dt.date, azimut_jetzt: float | None) -> dict[str, Any]:
        g, gain_gelernt, form, tage_je_fach, proben = self.gain_und_form(heute)
        jetzt_wert, jetzt_direkt = (
            self.form_bei(form, azimut_jetzt) if azimut_jetzt is not None else (1.0, False)
        )
        return {
            "gain": round(g, 4),
            "gain_gelernt": gain_gelernt,
            "kurve": {
                f"{fach_azimut(f):.1f}": round(v, 3) for f, v in sorted(form.items())
            },
            "stichprobe_tage": {
                f"{fach_azimut(f):.1f}": n for f, n in sorted(tage_je_fach.items())
            },
            "stichprobe_proben": sum(proben.values()),
            "faecher_gelernt": len(form),
            "gelernt": gain_gelernt and len(form) >= MIN_FAECHER_GAIN,
            "jetzt": round(jetzt_wert, 3),
            "jetzt_direkt_gemessen": jetzt_direkt,
        }

    def zu_dict(self) -> dict[str, Any]:
        return {
            "tage": self.tage,
            "proben": self.proben,
            "heute": self.heute,
            "laufend": {k: [round(x, 4) for x in v] for k, v in self.laufend.items()},
        }

    def aus_dict(self, d: dict[str, Any]) -> None:
        self.tage = dict(d.get("tage") or {})
        self.proben = dict(d.get("proben") or {})
        self.heute = d.get("heute")
        self.laufend = {k: list(v) for k, v in (d.get("laufend") or {}).items()}

    def aufraeumen(self, heute: dt.date) -> None:
        self.tage = _im_fenster(self.tage, heute, FENSTER_FORM_TAGE)
        self.proben = _im_fenster(self.proben, heute, FENSTER_FORM_TAGE)


class Pegelschaetzer:
    """Rollierender Pegelfaktor gegen Forecast.Solar.

    Verglichen werden nicht Energien, sondern zwei Truebungsindizes
    desselben Tages:

      c_gemessen  = Summe der gemessenen Leistung / Summe der
                    Klarhimmelerwartung, beides nur ueber unzensierte
                    Zeitraeume
      c_prognose  = Tagesprognose von Forecast.Solar / Klarhimmelertrag
                    des ganzen Tages

      Pegel = c_gemessen / c_prognose

    Beide Klarhimmelgroessen werden in rein GEOMETRISCHEN Einheiten
    gefuehrt (POA mal Tagesform, also W/m2), nicht in Watt. Damit kuerzt
    sich der gelernte Systemgain exakt heraus:

      Pegel = E_gemessen * G_gesamt / (G_offen * E_prognose)

    Der Pegel bleibt also richtig, auch wenn der Gain sich mitten am Tag
    noch einschwingt.

    Der Umweg ueber Indizes loest das Zensurproblem: sobald der Speicher
    voll ist, drosselt die Nulleinspeisung die PV, und der gemessene
    Tagesertrag ist nur noch eine Untergrenze. Ein Verhaeltnis aus
    Tagesenergien waere dadurch systematisch zu klein. Der Index dagegen
    wird nur ueber die Zeitraeume gebildet, in denen die Messung ehrlich
    ist, und mit dem passenden Ausschnitt der Klarhimmelerwartung
    verglichen.

    Faengt damit automatisch ein: bifazialen Mehrertrag (Forecast.Solar
    rechnet nur die Vorderseite), den Konservatismus der API, falsch
    eingetragene Neigung und Azimut, und die saisonale Drift.
    """

    def __init__(self) -> None:
        self.tage: dict[str, float] = {}
        self.heute: str | None = None
        # Tagesbilanz, laufend
        self.e_gemessen: float = 0.0    # Wh
        self.e_klar_offen: float = 0.0  # Wh, nur unzensierte Abschnitte
        self.e_klar_gesamt: float = 0.0  # Wh, ganzer Tag
        self.fs_prognose_kwh: float = 0.0

    def neuer_tag(self, tag: str, e_klar_gesamt_wh: float) -> None:
        self.heute = tag
        self.e_gemessen = 0.0
        self.e_klar_offen = 0.0
        self.e_klar_gesamt = e_klar_gesamt_wh
        self.fs_prognose_kwh = 0.0

    def probe(
        self,
        jetzt: dt.datetime,
        p_gemessen_w: float,
        geometrie: float,
        sekunden: float,
        zensiert: bool,
    ) -> None:
        """`geometrie` ist POA mal Tagesform in W/m2, ohne Systemgain."""
        if zensiert or geometrie <= 0.0:
            return
        self.e_gemessen += p_gemessen_w * sekunden / 3600.0
        self.e_klar_offen += geometrie * sekunden / 3600.0

    def merke_prognose(self, kwh: float) -> None:
        """Tagesprognose von Forecast.Solar.

        Wird nur bei Sonne ueber dem Horizont aufgerufen; damit steht am
        Tagesende der letzte am Tag gueltige Wert und nicht der bereits
        auf den Folgetag umgesprungene.
        """
        if kwh > 0.0:
            self.fs_prognose_kwh = kwh

    def tag_abschliessen(self) -> None:
        """Verdichtet den laufenden Tag zu einem Pegelwert.

        Verworfen wird der Tag, wenn zu wenig davon unzensiert beobachtet
        wurde. Unter 35 Prozent des Klarhimmelertrags ist der gemessene
        Index ein Zufallsausschnitt - meist der Vormittag, der bei dieser
        Anlage systematisch besser laeuft als der verschattete Nachmittag.
        """
        if self.heute is None:
            return
        if self.e_klar_gesamt <= 0.0 or self.fs_prognose_kwh <= 0.0:
            return
        if self.e_klar_offen / self.e_klar_gesamt < 0.35:
            _LOGGER.debug(
                "Pegel: %s verworfen, nur %.0f%% des Tages unzensiert beobachtet",
                self.heute, 100.0 * self.e_klar_offen / self.e_klar_gesamt,
            )
            return
        c_gemessen = self.e_gemessen / self.e_klar_offen
        c_prognose = self.fs_prognose_kwh * 1000.0 / self.e_klar_gesamt
        if c_prognose <= 0.0 or c_gemessen <= 0.0:
            return
        pegel = c_gemessen / c_prognose
        # Weite physikalische Klammer. Alles ausserhalb ist ein Defekt,
        # kein Wetter.
        if not (0.3 <= pegel <= 4.0):
            return
        self.tage[self.heute] = round(pegel, 4)

    def wert(self, heute: dt.date) -> dict[str, Any]:
        fenster = _im_fenster(self.tage, heute, FENSTER_PEGEL_TAGE)
        paare = [(v, _gewicht(t, heute)) for t, v in fenster.items()]
        gelernt = len(paare) >= MIN_TAGE_PEGEL
        if gelernt:
            m = robust.robuster_gewichteter_median(paare)
            pegel = m if m is not None else START_PEGEL
        else:
            pegel = START_PEGEL
        werte = sorted(v for _, v in fenster.items())
        return {
            "pegel": round(pegel, 3),
            "gelernt": gelernt,
            "stichprobe": len(paare),
            "spanne": [round(werte[0], 3), round(werte[-1], 3)] if werte else None,
            "einzelwerte": {t: round(v, 3) for t, v in sorted(fenster.items())},
        }

    def zu_dict(self) -> dict[str, Any]:
        return {
            "tage": self.tage,
            "heute": self.heute,
            "e_gemessen": round(self.e_gemessen, 2),
            "e_klar_offen": round(self.e_klar_offen, 2),
            "e_klar_gesamt": round(self.e_klar_gesamt, 2),
            "fs_prognose_kwh": self.fs_prognose_kwh,
        }

    def aus_dict(self, d: dict[str, Any]) -> None:
        self.tage = dict(d.get("tage") or {})
        self.heute = d.get("heute")
        self.e_gemessen = float(d.get("e_gemessen") or 0.0)
        self.e_klar_offen = float(d.get("e_klar_offen") or 0.0)
        self.e_klar_gesamt = float(d.get("e_klar_gesamt") or 0.0)
        self.fs_prognose_kwh = float(d.get("fs_prognose_kwh") or 0.0)

    def aufraeumen(self, heute: dt.date) -> None:
        self.tage = _im_fenster(self.tage, heute, FENSTER_PEGEL_TAGE)


class Wirkungsgradschaetzer:
    """Speicherwirkungsgrad aus der Tagesenergiebilanz.

    Ueber einen Tag gilt

        dSOC/100 * Kapazitaet = eta * E_laden - E_entladen / eta

    mit den kumulierten Zaehlern des Geraets. Nach eta aufgeloest:

        eta = (d + sqrt(d^2 + 4*a*b)) / (2*a)

    mit a = E_laden, b = E_entladen, d = dSOC/100 * Kapazitaet.

    Der symmetrische Ansatz (gleicher Wirkungsgrad in beide Richtungen)
    ist noetig, weil eine Tagesbilanz nur eine Gleichung liefert. Was
    dabei herauskommt, ist die Wurzel des Umlaufwirkungsgrads - genau die
    Groesse, die die Vorwaertssimulation braucht.

    Bemerkenswert: das Ergebnis haengt an der gelesenen Kapazitaet. Wird
    der Speicher aufgeruestet, waechst die Kapazitaet mit, und der
    Wirkungsgrad bleibt richtig. Waere die Kapazitaet fest, wuerde ein
    Umbau sich als scheinbare Wirkungsgradaenderung tarnen.
    """

    def __init__(self) -> None:
        self.tage: dict[str, float] = {}
        self.heute: str | None = None
        self.soc_start: float | None = None
        self.lade_start: float | None = None
        self.entlade_start: float | None = None
        self.soc_zuletzt: float | None = None
        self.lade_zuletzt: float | None = None
        self.entlade_zuletzt: float | None = None

    def probe(
        self,
        jetzt: dt.datetime,
        soc: float | None,
        lade_kwh: float | None,
        entlade_kwh: float | None,
        kapazitaet: float,
    ) -> None:
        tag = jetzt.date().isoformat()
        if self.heute != tag:
            self.tag_abschliessen(kapazitaet)
            self.heute = tag
            self.soc_start = soc
            self.lade_start = lade_kwh
            self.entlade_start = entlade_kwh
        if soc is not None:
            self.soc_zuletzt = soc
            if self.soc_start is None:
                self.soc_start = soc
        if lade_kwh is not None:
            # Zaehlerruecksetzung (total_increasing): Tag neu anfangen.
            if self.lade_start is not None and lade_kwh < self.lade_start - 0.01:
                self.lade_start = lade_kwh
                self.entlade_start = entlade_kwh
                self.soc_start = soc
            self.lade_zuletzt = lade_kwh
            if self.lade_start is None:
                self.lade_start = lade_kwh
        if entlade_kwh is not None:
            self.entlade_zuletzt = entlade_kwh
            if self.entlade_start is None:
                self.entlade_start = entlade_kwh

    def tag_abschliessen(self, kapazitaet: float) -> None:
        if self.heute is None:
            return
        if None in (
            self.soc_start, self.soc_zuletzt,
            self.lade_start, self.lade_zuletzt,
            self.entlade_start, self.entlade_zuletzt,
        ):
            return
        a = self.lade_zuletzt - self.lade_start
        b = self.entlade_zuletzt - self.entlade_start
        d = (self.soc_zuletzt - self.soc_start) / 100.0 * kapazitaet
        # Ein Tag mit wenig Umsatz traegt keine Information: der Fehler in
        # dSOC (Aufloesung 1 Prozentpunkt = 51 Wh) dominiert dann.
        if a < 1.0 or b < 0.3:
            return
        wurzel = d * d + 4.0 * a * b
        if wurzel < 0.0 or a <= 0.0:
            return
        eta = (d + math.sqrt(wurzel)) / (2.0 * a)
        if not (ETA_MIN <= eta <= ETA_MAX):
            return
        self.tage[self.heute] = round(eta, 4)

    def wert(self, heute: dt.date) -> dict[str, Any]:
        fenster = _im_fenster(self.tage, heute, FENSTER_ETA_TAGE)
        paare = [(v, _gewicht(t, heute)) for t, v in fenster.items()]
        gelernt = len(paare) >= MIN_TAGE_ETA
        if gelernt:
            m = robust.robuster_gewichteter_median(paare)
            eta = m if m is not None else START_ETA
        else:
            eta = START_ETA
        return {
            "eta": round(min(max(eta, ETA_MIN), ETA_MAX), 4),
            "umlauf": round(min(max(eta, ETA_MIN), ETA_MAX) ** 2, 4),
            "gelernt": gelernt,
            "stichprobe": len(paare),
            "einzelwerte": {t: round(v, 4) for t, v in sorted(fenster.items())},
        }

    def zu_dict(self) -> dict[str, Any]:
        return {
            "tage": self.tage,
            "heute": self.heute,
            "soc_start": self.soc_start,
            "lade_start": self.lade_start,
            "entlade_start": self.entlade_start,
            "soc_zuletzt": self.soc_zuletzt,
            "lade_zuletzt": self.lade_zuletzt,
            "entlade_zuletzt": self.entlade_zuletzt,
        }

    def aus_dict(self, d: dict[str, Any]) -> None:
        self.tage = dict(d.get("tage") or {})
        self.heute = d.get("heute")
        self.soc_start = d.get("soc_start")
        self.lade_start = d.get("lade_start")
        self.entlade_start = d.get("entlade_start")
        self.soc_zuletzt = d.get("soc_zuletzt")
        self.lade_zuletzt = d.get("lade_zuletzt")
        self.entlade_zuletzt = d.get("entlade_zuletzt")

    def aufraeumen(self, heute: dt.date) -> None:
        self.tage = _im_fenster(self.tage, heute, FENSTER_ETA_TAGE)


class Lernstand:
    """Alle Schaetzer zusammen, als eine serialisierbare Einheit."""

    def __init__(self) -> None:
        self.hauslast = Hauslastschaetzer()
        self.form = Formschaetzer()
        self.pegel = Pegelschaetzer()
        self.eta = Wirkungsgradschaetzer()
        self.bootstrap: dict[str, Any] = {}

    def zu_dict(self) -> dict[str, Any]:
        return {
            "hauslast": self.hauslast.zu_dict(),
            "form": self.form.zu_dict(),
            "pegel": self.pegel.zu_dict(),
            "eta": self.eta.zu_dict(),
            "bootstrap": self.bootstrap,
        }

    def aus_dict(self, d: dict[str, Any] | None) -> None:
        if not d:
            return
        self.hauslast.aus_dict(d.get("hauslast") or {})
        self.form.aus_dict(d.get("form") or {})
        self.pegel.aus_dict(d.get("pegel") or {})
        self.eta.aus_dict(d.get("eta") or {})
        self.bootstrap = dict(d.get("bootstrap") or {})

    def aufraeumen(self, heute: dt.date) -> None:
        self.hauslast.aufraeumen(heute)
        self.form.aufraeumen(heute)
        self.pegel.aufraeumen(heute)
        self.eta.aufraeumen(heute)
