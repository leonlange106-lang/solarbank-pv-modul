"""Entities.

Jede gelernte Groesse bekommt eine eigene Entity, damit man ihr beim
Lernen zusehen kann. Die numerischen tragen `state_class: measurement`
und landen damit in der Langzeitstatistik - man kann also spaeter
nachvollziehen, wie sich der Pegel ueber die Jahreszeiten bewegt hat.

Jede Entity sagt in ihren Attributen, ob ihr Wert gelernt oder ein
Startwert ist (`gelernt`) und auf wievielen Beobachtungen er beruht
(`stichprobe`). Ein Schaetzer, der aus zwei Tagen so tut als wuesste er
Bescheid, waere schlimmer als eine ehrliche Konstante.

Zur Benennung: has_entity_name ist bewusst False und die entity_id wird
explizit gesetzt, wie in solarbank_pv. Sonst stellt Home Assistant den
Geraetenamen voran und erzeugt sensor.pv_lernprognose_pv_lernen_pegel.
Der Anzeigename traegt deshalb KEIN eigenes Praefix: Home Assistant
stellt den Geraetenamen "PV Lernprognose" ohnehin voran, und ein
zweites "PV Lernen" davor las sich doppelt.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    FENSTER_ETA_TAGE,
    FENSTER_FORM_TAGE,
    FENSTER_HAUSLAST_TAGE,
    FENSTER_PEGEL_TAGE,
    HALBWERTSZEIT_TAGE,
    MIN_TAGE_ETA,
    MIN_TAGE_FORM,
    MIN_TAGE_HAUSLAST,
    MIN_TAGE_PEGEL,
    START_ETA,
    START_GAIN,
    START_PEGEL,
)
from .coordinator import LernprognoseCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: LernprognoseCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            PegelSensor(coordinator),
            WirkungsgradSensor(coordinator),
            SystemgainSensor(coordinator),
            TagesformSensor(coordinator),
            TruebungSensor(coordinator),
            KlarhimmelSensor(coordinator),
            HauslastJetztSensor(coordinator),
            LernstandSensor(coordinator),
            KennwerteSensor(coordinator),
            PrognoseSensor(coordinator),
            ZielErreichtSensor(coordinator),
        ]
    )


class Basis(CoordinatorEntity[LernprognoseCoordinator], SensorEntity):
    """Gemeinsame Geraetezuordnung und Identitaet."""

    _attr_has_entity_name = False
    _schluessel = ""
    _anzeigename = ""

    def __init__(self, coordinator: LernprognoseCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_{self._schluessel}"
        self._attr_name = self._anzeigename
        self.entity_id = f"sensor.pv_lernen_{self._schluessel}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.entry.entry_id)},
            name="PV Lernprognose",
            manufacturer="Eigenbau",
            model="Selbstlernende Speicherprognose",
        )

    @property
    def _d(self) -> dict[str, Any]:
        return self.coordinator.data or {}


# --------------------------------------------------------------------------
# Die vier geforderten Schaetzer
# --------------------------------------------------------------------------
class PegelSensor(Basis):
    """Pegelfaktor gegen Forecast.Solar."""

    _schluessel = "pegelfaktor"
    _anzeigename = "Pegelfaktor"
    _attr_icon = "mdi:scale-balance"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 3

    @property
    def native_value(self) -> float | None:
        info = self._d.get("pegel_info")
        return info["pegel"] if info else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        info = self._d.get("pegel_info") or {}
        return {
            "gelernt": info.get("gelernt"),
            "stichprobe": info.get("stichprobe"),
            "spanne": info.get("spanne"),
            "fenster_tage": FENSTER_PEGEL_TAGE,
            "eingeschwungen_ab_tagen": MIN_TAGE_PEGEL,
            "startwert": START_PEGEL,
            "verfahren": (
                "Verhaeltnis zweier Truebungsindizes desselben Tages: gemessen "
                "gegen Forecast.Solar, beides bezogen auf die geometrische "
                "Klarhimmelerwartung. Nur unzensierte Abschnitte gehen ein, "
                "Tage mit unter 35 Prozent unzensierter Beobachtung fallen "
                "heraus. Ueber die Tage gewichteter Median nach MAD-Filter."
            ),
            "einzelwerte": info.get("einzelwerte"),
        }


class WirkungsgradSensor(Basis):
    """Speicherwirkungsgrad aus der Tagesenergiebilanz."""

    _schluessel = "speicherwirkungsgrad"
    _anzeigename = "Speicherwirkungsgrad"
    _attr_icon = "mdi:battery-sync"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 3

    @property
    def native_value(self) -> float | None:
        info = self._d.get("eta_info")
        return info["eta"] if info else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        info = self._d.get("eta_info") or {}
        return {
            "gelernt": info.get("gelernt"),
            "stichprobe": info.get("stichprobe"),
            "umlaufwirkungsgrad": info.get("umlauf"),
            "fenster_tage": FENSTER_ETA_TAGE,
            "eingeschwungen_ab_tagen": MIN_TAGE_ETA,
            "startwert": START_ETA,
            "verfahren": (
                "Je Tag aus dSOC * Kapazitaet = eta * E_laden - E_entladen / eta, "
                "aufgeloest nach eta. Kapazitaet stammt aus dem Geraet, ein "
                "Speicherausbau verfaelscht den Wirkungsgrad daher nicht. Tage "
                "mit unter 1 kWh Ladeumsatz zaehlen nicht, weil dann die "
                "SOC-Aufloesung dominiert."
            ),
            "einzelwerte": info.get("einzelwerte"),
        }


class TagesformSensor(Basis):
    """Gelernte Tagesform am aktuellen Sonnenazimut."""

    _schluessel = "tagesform"
    _anzeigename = "Tagesform"
    _attr_icon = "mdi:weather-sunny-alert"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 3

    @property
    def native_value(self) -> float | None:
        return self._d.get("form_jetzt")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        info = self._d.get("form_info") or {}
        return {
            "gelernt": info.get("gelernt"),
            "faecher_gelernt": info.get("faecher_gelernt"),
            "stichprobe_proben": info.get("stichprobe_proben"),
            "direkt_gemessen": self._d.get("form_direkt_gemessen"),
            "sonnenazimut": self._d.get("sonnenazimut"),
            "sonnenhoehe": self._d.get("sonnenhoehe"),
            "fenster_tage": FENSTER_FORM_TAGE,
            "halbwertszeit_tage": HALBWERTSZEIT_TAGE,
            "eingeschwungen_ab_tagen_je_fach": MIN_TAGE_FORM,
            "verfahren": (
                "Gemessene Leistung geteilt durch geometrische "
                "Klarhimmelerwartung, indiziert nach Sonnenazimut in "
                "5-Grad-Faechern. Nur klare, unzensierte Momente gehen ein. "
                "Enthaelt damit die Verschattung und wandert mit dem "
                "Sonnenlauf durch die Jahreszeiten mit. Ersetzt cos^EXPONENT."
            ),
        }


class HauslastJetztSensor(Basis):
    """Gelernte Hauslast fuer die laufende Stunde."""

    _schluessel = "hauslast"
    _anzeigename = "Hauslast"
    _attr_icon = "mdi:home-lightning-bolt"
    _attr_device_class = SensorDeviceClass.POWER
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 0

    @property
    def native_value(self) -> float | None:
        info = self._d.get("hauslast_wert")
        jetzt = self._d.get("jetzt")
        if not info or jetzt is None:
            return None
        return info["profil"][jetzt.hour]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        info = self._d.get("hauslast_wert") or {}
        jetzt = self._d.get("jetzt")
        return {
            "gelernt": info.get("gelernt"),
            "gelernte_stunden": info.get("gelernte_stunden"),
            "tagestyp": (
                "Wochenende" if jetzt and jetzt.weekday() >= 5 else "Werktag"
            ),
            "tagessumme_kwh": info.get("tagessumme_kwh"),
            "stichprobe_diese_stunde": (
                info["stichprobe"][jetzt.hour] if info and jetzt else None
            ),
            "startwert_herkunft": info.get("startwert_herkunft"),
            "startprofil": info.get("startprofil"),
            "gemessen_jetzt": self._d.get("hauslast_w"),
            "quelle": self._d.get("hauslast_quelle"),
            "fenster_tage": FENSTER_HAUSLAST_TAGE,
            "eingeschwungen_ab_tagen": MIN_TAGE_HAUSLAST,
            "verfahren": (
                "Je Tag und Stunde der Median der Minutenmesswerte, darueber "
                "ein rezenzgewichteter Median ueber das Fenster, getrennt nach "
                "Werktag und Wochenende. Der Median statt des Mittels, weil "
                "das alte Profil an genau dieser Stelle scheiterte: es war das "
                "Mittel aus zwei Tagen mit Reglertests."
            ),
        }


# --------------------------------------------------------------------------
# Abgeleitete Groessen, die das Verfahren sichtbar machen
# --------------------------------------------------------------------------
class SystemgainSensor(Basis):
    """Effektive Anlagenleistung je Einstrahlung."""

    _schluessel = "systemgain"
    _anzeigename = "Systemgain"
    _attr_icon = "mdi:solar-panel-large"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "W/(W/m²)"
    _attr_suggested_display_precision = 3

    @property
    def native_value(self) -> float | None:
        return self._d.get("gain")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        gain = self._d.get("gain")
        return {
            "gelernt": self._d.get("gain_gelernt"),
            "startwert": START_GAIN,
            "entspricht_kwp_wirksam": round(gain, 3) if gain else None,
            "verfahren": (
                "Oberes Quantil (0.90) ueber alle belegten Azimutfaecher des "
                "Verhaeltnisses gemessene Leistung zu Klarhimmel-POA. Die "
                "Faecher darueber sind unverschattet, alles darunter ist "
                "Schatten und landet in der Tagesform. Enthaelt Modulflaeche, "
                "Systemwirkungsgrad und den bifazialen Mehrertrag - genau das, "
                "was Forecast.Solar nicht rechnet."
            ),
        }


class TruebungSensor(Basis):
    """Bewoelkungsindex - der ehemalige Faktor k, jetzt ohne Schattenfehler."""

    _schluessel = "truebung"
    _anzeigename = "Truebung"
    _attr_icon = "mdi:weather-partly-cloudy"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 3

    @property
    def native_value(self) -> float | None:
        live = self._d.get("truebung_live")
        return live if live is not None else self._d.get("truebung_prognose")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "live": self._d.get("truebung_live"),
            "aus_prognose": self._d.get("truebung_prognose"),
            "quelle_prognose": self._d.get("truebung_quelle"),
            "moment_klar": self._d.get("klar"),
            "moment_zensiert": self._d.get("zensiert"),
            "verfahren": (
                "Gemessene Leistung geteilt durch Klarhimmelerwartung "
                "EINSCHLIESSLICH gelernter Verschattung. Damit misst sie "
                "Bewoelkung statt Schatten - der Fehler, an dem das alte k "
                "scheiterte. Fuer die Zukunft blendet sie mit 90 Minuten "
                "Halbwertszeit auf die Wetterprognose ueber."
            ),
        }


class KlarhimmelSensor(Basis):
    """Erwartete Leistung bei klarem Himmel, mit Verschattung."""

    _schluessel = "klarhimmelleistung"
    _anzeigename = "Klarhimmelleistung"
    _attr_icon = "mdi:white-balance-sunny"
    _attr_device_class = SensorDeviceClass.POWER
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 0

    @property
    def native_value(self) -> float | None:
        return self._d.get("p_klar")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "poa_w_m2": self._d.get("poa"),
            "tagesform": self._d.get("form_jetzt"),
            "systemgain": self._d.get("gain"),
            "sonnenhoehe": self._d.get("sonnenhoehe"),
            "sonnenazimut": self._d.get("sonnenazimut"),
            "gemessen": self._d.get("pv_w"),
            "hinweis": (
                "Systemgain mal geometrische POA mal gelernte Tagesform. "
                "Der Vergleich mit `gemessen` ist die Truebung."
            ),
        }


class LernstandSensor(Basis):
    """Sammelanzeige: was ist eingeschwungen, was noch nicht.

    Attributschwer und im Minutentakt veraenderlich - gehoert deshalb in
    die recorder-Ausschlussliste.
    """

    _schluessel = "lernstand"
    _anzeigename = "Lernstand"
    _attr_icon = "mdi:school"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def native_value(self) -> str | None:
        d = self._d
        if not d:
            return None
        fertig = sum(
            1
            for x in (
                (d.get("hauslast_wert") or {}).get("gelernt"),
                (d.get("pegel_info") or {}).get("gelernt"),
                (d.get("form_info") or {}).get("gelernt"),
                (d.get("eta_info") or {}).get("gelernt"),
            )
            if x
        )
        return f"{fertig} von 4 eingeschwungen"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        d = self._d
        hauslast = d.get("hauslast_info") or {}
        form = d.get("form_info") or {}
        return {
            "hauslastprofil_werktag": hauslast.get("werktag"),
            "hauslastprofil_wochenende": hauslast.get("wochenende"),
            "hauslast_stichprobe_werktag": hauslast.get("stichprobe_werktag"),
            "hauslast_stichprobe_wochenende": hauslast.get("stichprobe_wochenende"),
            "tagesform_kurve": form.get("kurve"),
            "tagesform_stichprobe": form.get("stichprobe_tage"),
            "pegel": (d.get("pegel_info") or {}).get("pegel"),
            "pegel_gelernt": (d.get("pegel_info") or {}).get("gelernt"),
            "wirkungsgrad": (d.get("eta_info") or {}).get("eta"),
            "wirkungsgrad_gelernt": (d.get("eta_info") or {}).get("gelernt"),
            "systemgain": d.get("gain"),
            "systemgain_gelernt": d.get("gain_gelernt"),
            "bootstrap": self.coordinator.lernstand.bootstrap or None,
            "meta_parameter": {
                "fenster_tage": {
                    "hauslast": FENSTER_HAUSLAST_TAGE,
                    "pegel": FENSTER_PEGEL_TAGE,
                    "tagesform": FENSTER_FORM_TAGE,
                    "wirkungsgrad": FENSTER_ETA_TAGE,
                },
                "halbwertszeit_tage": HALBWERTSZEIT_TAGE,
            },
        }


class KennwerteSensor(Basis):
    """Anlagenkennwerte, aus dem Geraet gelesen statt fest gesetzt."""

    _schluessel = "anlagenkennwerte"
    _anzeigename = "Anlagenkennwerte"
    _attr_icon = "mdi:tag-check"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def native_value(self) -> str:
        return self.coordinator.anlage.zustand

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return self.coordinator.anlage.als_attribute()


# --------------------------------------------------------------------------
# Die Prognose selbst - additiv, unter neuer ID
# --------------------------------------------------------------------------
class PrognoseSensor(Basis):
    """Neue Speicherprognose.

    Bewusst unter eigener entity_id und NICHT als Ersatz von
    sensor.nulleinspeisung_speicher_prognose. Beide laufen parallel,
    damit sich vergleichen laesst, bevor umgestellt wird. Der Wortlaut
    ist identisch, der Tausch waere danach ein reiner Logiktausch.
    """

    _schluessel = "speicher_prognose"
    _anzeigename = "Speicher Prognose"
    _attr_icon = "mdi:battery-clock"

    @property
    def native_value(self) -> str | None:
        text = self._d.get("text")
        if text is None:
            return None
        return text[:255]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        d = self._d
        lauf = d.get("lauf")
        attrs: dict[str, Any] = {
            "soc": d.get("soc"),
            "truebung": d.get("truebung_live") or d.get("truebung_prognose"),
            "kapazitaet_kwh": self.coordinator.anlage.kapazitaet.wert,
            "ac_grenze_w": self.coordinator.anlage.ac_grenze.wert,
            "max_ladeleistung_w": self.coordinator.anlage.max_ladeleistung.wert,
            "kennwerte_zustand": self.coordinator.anlage.zustand,
            "alle_schaetzer_eingeschwungen": all(
                (
                    (d.get("hauslast_wert") or {}).get("gelernt"),
                    (d.get("pegel_info") or {}).get("gelernt"),
                    (d.get("form_info") or {}).get("gelernt"),
                    (d.get("eta_info") or {}).get("gelernt"),
                )
            ),
        }
        if lauf is not None:
            attrs.update(
                {
                    "soc_max_prognose": round(lauf.soc_max, 1),
                    "zeitpunkt_maximum": _iso(lauf.t_soc_max),
                    "zeitpunkt_voll": _iso(lauf.t_voll),
                    "zeitpunkt_leer": _iso(lauf.t_leer),
                    "ertrag_rest_kwh": round(lauf.ertrag_rest_kwh, 2),
                    "klarhimmel_rest_kwh": round(lauf.klar_rest_kwh, 2),
                    "bahn": [
                        [t.isoformat(timespec="minutes"), v]
                        for t, v in lauf.bahn[:: max(len(lauf.bahn) // 48, 1)]
                    ],
                }
            )
        return attrs


class ZielErreichtSensor(Basis):
    """Zeitpunkt, zu dem das Prioritaetsladungsziel erreicht wird.

    Ebenfalls additiv. Der bestehende
    sensor.prioritaetsladung_ziel_erreicht_um bleibt unangetastet.
    Unterschied zur alten Rechnung: dort wurde die aktuelle Ladeleistung
    linear fortgeschrieben, hier laeuft die volle Simulation - inklusive
    Verschattungsdelle, Hauslast und Abendabfall.
    """

    _schluessel = "ziel_erreicht_um"
    _anzeigename = "Ziel erreicht um"
    _attr_icon = "mdi:clock-fast"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    @property
    def native_value(self) -> dt.datetime | None:
        lauf = self._d.get("lauf")
        return lauf.t_ziel if lauf else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        d = self._d
        return {
            "ziel_soc": d.get("ziel_soc"),
            "soc": d.get("soc"),
            "verfahren": (
                "Vollstaendige Vorwaertssimulation statt linearer "
                "Hochrechnung der aktuellen Ladeleistung."
            ),
        }


def _iso(t: dt.datetime | None) -> str | None:
    return t.isoformat(timespec="minutes") if t else None
