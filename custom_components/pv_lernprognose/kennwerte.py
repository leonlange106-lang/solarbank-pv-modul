"""Anlagenkennwerte aus dem Geraet statt aus einer Konstanten.

Bisher standen Kapazitaet, AC-Grenze und Ladeleistung als Zahlen im
Jinja-Template. Wird die Anlage umgebaut - Erweiterungsakku, Wieland-Dose
mit 2500 W statt 800 W - rechnet die Prognose danach mit einer Grenze, die
es nicht mehr gibt, und niemand merkt es, weil die Zahl plausibel aussieht.

Deshalb wird jeder dieser Werte gelesen. Drei Sicherungen dagegen, dass ein
Ausfall der Quelle die Prognose kippt:

  1. Quellenkette. Faellt die offizielle Integration aus, greift der
     eigene Modbus-Sensor.
  2. Plausibilitaetsbereich. Ein Wert ausserhalb gilt als ungelesen. Das
     faengt den Fall ab, der bis zum 13.08.2026 real bestand: Register
     10250 wurde als u16 statt u32 dekodiert und lieferte dauerhaft 0,0.
  3. Letzter guter Wert. Ist gerade nichts lesbar, wird der zuletzt
     plausible Wert gehalten - und das im Attribut ausgewiesen.

Erst wenn noch nie ein gueltiger Wert gelesen wurde, greift der
Ersatzwert aus const.py. Auch das steht im Attribut.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from homeassistant.core import HomeAssistant

from .const import (
    BEREICH_AC_GRENZE_W,
    BEREICH_KAPAZITAET_KWH,
    BEREICH_MAX_LADELEISTUNG_W,
    BEREICH_SOC_MAX,
    BEREICH_SOC_MIN,
    ERSATZ_AC_GRENZE_W,
    ERSATZ_KAPAZITAET_KWH,
    ERSATZ_MAX_LADELEISTUNG_W,
    ERSATZ_SOC_MAX,
    ERSATZ_SOC_MIN,
    QUELLE_AC_GRENZE_W,
    QUELLE_KAPAZITAET_KWH,
    QUELLE_MAX_LADELEISTUNG_W,
    QUELLE_SOC_MAX,
    QUELLE_SOC_MIN,
)

_LOGGER = logging.getLogger(__name__)

UNGUELTIG = ("unknown", "unavailable", "none", "")


def lies_zahl(hass: HomeAssistant, kette: tuple[str, ...]) -> tuple[float | None, str | None]:
    """Erste lesbare Zahl aus einer Entity-Kette. Gibt (Wert, Quelle) zurueck."""
    for entity_id in kette:
        zustand = hass.states.get(entity_id)
        if zustand is None or zustand.state.lower() in UNGUELTIG:
            continue
        try:
            return float(zustand.state), entity_id
        except (TypeError, ValueError):
            continue
    return None, None


@dataclass
class Kennwert:
    """Ein Anlagenkennwert mit Herkunft und Guete."""

    name: str
    kette: tuple[str, ...]
    bereich: tuple[float, float]
    ersatz: float
    einheit: str

    wert: float = 0.0
    quelle: str | None = None
    zustand: str = "ersatzwert"   # gelesen | gehalten | ersatzwert
    letzte_gute_quelle: str | None = None
    verworfen: int = 0

    def __post_init__(self) -> None:
        self.wert = self.ersatz

    def aktualisiere(self, hass: HomeAssistant) -> None:
        roh, quelle = lies_zahl(hass, self.kette)
        if roh is None:
            self._halten("keine Quelle lesbar")
            return
        unten, oben = self.bereich
        if not (unten <= roh <= oben):
            self.verworfen += 1
            if self.verworfen in (1, 10, 100):
                _LOGGER.warning(
                    "%s: %s liefert %.3f %s, ausserhalb des Erwartungsbereichs "
                    "%.1f bis %.1f. Wert wird verworfen, es gilt weiter %.3f (%s).",
                    self.name, quelle, roh, self.einheit,
                    unten, oben, self.wert, self.zustand,
                )
            self._halten(f"{quelle} unplausibel")
            return

        if self.quelle is not None and self.wert > 0 and quelle == self.quelle:
            if abs(roh - self.wert) / max(self.wert, 1e-9) > 0.02:
                _LOGGER.info(
                    "%s hat sich geaendert: %.3f -> %.3f %s (Quelle %s). "
                    "Die Prognose rechnet ab sofort mit dem neuen Wert.",
                    self.name, self.wert, roh, self.einheit, quelle,
                )
        self.wert = roh
        self.quelle = quelle
        self.letzte_gute_quelle = quelle
        self.zustand = "gelesen"
        self.verworfen = 0

    def _halten(self, grund: str) -> None:
        if self.letzte_gute_quelle is not None:
            self.zustand = "gehalten"
            self.quelle = self.letzte_gute_quelle
        else:
            self.zustand = "ersatzwert"
            self.quelle = None
            self.wert = self.ersatz
        self._grund = grund

    @property
    def gelesen(self) -> bool:
        return self.zustand == "gelesen"

    def als_attribut(self) -> dict[str, Any]:
        return {
            "wert": round(self.wert, 3),
            "einheit": self.einheit,
            "zustand": self.zustand,
            "quelle": self.quelle,
        }


@dataclass
class Anlage:
    """Alle Kennwerte der Anlage, laufend aus dem Geraet nachgefuehrt."""

    kapazitaet: Kennwert = field(default_factory=lambda: Kennwert(
        name="Speicherkapazitaet",
        kette=QUELLE_KAPAZITAET_KWH,
        bereich=BEREICH_KAPAZITAET_KWH,
        ersatz=ERSATZ_KAPAZITAET_KWH,
        einheit="kWh",
    ))
    ac_grenze: Kennwert = field(default_factory=lambda: Kennwert(
        name="AC-Ausgangsgrenze",
        kette=QUELLE_AC_GRENZE_W,
        bereich=BEREICH_AC_GRENZE_W,
        ersatz=ERSATZ_AC_GRENZE_W,
        einheit="W",
    ))
    max_ladeleistung: Kennwert = field(default_factory=lambda: Kennwert(
        name="maximale Ladeleistung",
        kette=QUELLE_MAX_LADELEISTUNG_W,
        bereich=BEREICH_MAX_LADELEISTUNG_W,
        ersatz=ERSATZ_MAX_LADELEISTUNG_W,
        einheit="W",
    ))
    soc_max: Kennwert = field(default_factory=lambda: Kennwert(
        name="Ladeobergrenze",
        kette=QUELLE_SOC_MAX,
        bereich=BEREICH_SOC_MAX,
        ersatz=ERSATZ_SOC_MAX,
        einheit="%",
    ))
    soc_min: Kennwert = field(default_factory=lambda: Kennwert(
        name="SOC-Untergrenze",
        kette=QUELLE_SOC_MIN,
        bereich=BEREICH_SOC_MIN,
        ersatz=ERSATZ_SOC_MIN,
        einheit="%",
    ))

    def aktualisiere(self, hass: HomeAssistant) -> None:
        for kennwert in self.alle():
            kennwert.aktualisiere(hass)

    def alle(self) -> list[Kennwert]:
        return [
            self.kapazitaet,
            self.ac_grenze,
            self.max_ladeleistung,
            self.soc_max,
            self.soc_min,
        ]

    @property
    def zustand(self) -> str:
        zustaende = {k.zustand for k in self.alle()}
        if zustaende == {"gelesen"}:
            return "vollstaendig gelesen"
        if "ersatzwert" in zustaende:
            return "teils Ersatzwerte"
        return "teils gehalten"

    def als_attribute(self) -> dict[str, Any]:
        return {
            "speicherkapazitaet": self.kapazitaet.als_attribut(),
            "ac_ausgangsgrenze": self.ac_grenze.als_attribut(),
            "max_ladeleistung": self.max_ladeleistung.als_attribut(),
            "ladeobergrenze": self.soc_max.als_attribut(),
            "soc_untergrenze": self.soc_min.als_attribut(),
            "hinweis": (
                "Kapazitaet, AC-Grenze, Ladeleistung und Ladeobergrenze werden "
                "aus dem Geraet gelesen. Ein Umbau (Erweiterungsakku, "
                "Wieland-Dose) wirkt ohne Codeaenderung. Die SOC-Untergrenze "
                "ist eine Betreibereinstellung, kein Messwert."
            ),
        }
