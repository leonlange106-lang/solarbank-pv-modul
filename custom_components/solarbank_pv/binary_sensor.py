"""Binaersensoren: Verschattung je Strang und Abregelung der ganzen Anlage.

Die beiden Zustaende sind physikalisch verschieden und muessen es auch im Code
bleiben:

  Wolke        alle Stroeme fallen gleichzeitig und aehnlich stark,
               die Spannungen bleiben im MPP-Band
  Verschattung EIN Strom bricht ein, dessen Spannung steigt leicht durch Abkuehlung
  Abregelung   die Stroeme fallen und ALLE Spannungen steigen ueber die Schwelle

Deshalb prueft die Verschattung das Verhaeltnis zu den Nachbarstraengen, die
Abregelung dagegen die absolute Spannung gegen 0.92 * Voc(T). Ein einzelner
verschatteter Strang loest die Abregelungserkennung nicht aus, weil sie
verlangt, dass ALLE Straenge gleichzeitig oberhalb der Schwelle liegen.
"""
from __future__ import annotations

import logging
import statistics

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from . import SolarbankData
from .const import (
    CELL_OVER_AMBIENT,
    CONF_OUTDOOR_TEMP,
    DEFAULT_OUTDOOR_TEMP,
    DOMAIN,
    MIN_CURRENT_FOR_RATIO,
    MIN_POWER_FOR_RATIO,
    PV4_SHADE_CONFIRM,
    REGISTERS_BY_KEY,
    SHADE_OFF,
    SHADE_ON,
    STRINGS,
)
from .coordinator import SolarbankGroupCoordinator
from .physik import curtail_threshold, is_curtailed
from .sensor import display_name, other_median, read_value, string_powers

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    data: SolarbankData = hass.data[DOMAIN][entry.entry_id]
    strings = data.coordinators["strings"]
    outdoor = entry.data.get(CONF_OUTDOOR_TEMP, DEFAULT_OUTDOOR_TEMP)

    entities: list[BinarySensorEntity] = [
        ShadedBinarySensor(strings, data, prefix, label, i_key)
        for prefix, label, _v_key, i_key in STRINGS
    ]
    entities.append(String4ShadedBinarySensor(strings, data))
    entities.append(CurtailmentBinarySensor(strings, data, outdoor))
    async_add_entities(entities)


class SolarbankBinaryEntity(CoordinatorEntity[SolarbankGroupCoordinator], BinarySensorEntity):
    """Basis mit Geraetezuordnung und stabiler Identitaet."""

    _attr_has_entity_name = False

    def __init__(
        self,
        coordinator: SolarbankGroupCoordinator,
        data: SolarbankData,
        unique_suffix: str,
        name: str,
    ) -> None:
        super().__init__(coordinator)
        self._attr_device_info = data.device_info
        self._attr_unique_id = f"solarbank_{data.serial_suffix}_{unique_suffix}"
        self._attr_name = name
        # Siehe sensor.py: ohne explizite Zuweisung stellt Home Assistant den
        # Geraetenamen voran und bricht damit die Konvention der Anlage.
        self.entity_id = f"binary_sensor.{slugify(name)}"
        self._attr_entity_registry_enabled_default = True
        self._state: bool | None = None

    def _value(self, key: str) -> float | None:
        if not self.coordinator.data:
            return None
        return read_value(self.coordinator.data, REGISTERS_BY_KEY[key])

    @property
    def is_on(self) -> bool | None:
        return self._state


class ShadedBinarySensor(SolarbankBinaryEntity):
    """Verschattung eines Strangs, mit Hysterese.

    Ohne Hysterese wuerde der Sensor am Rand einer Schattenkante im Sekundentakt
    flattern und den Recorder zumuellen. Er geht deshalb erst unter SHADE_ON an
    und erst ueber SHADE_OFF wieder aus.
    """

    _attr_device_class = "problem"
    _attr_icon = "mdi:weather-cloudy"

    def __init__(self, coordinator, data, prefix, label, i_key) -> None:
        super().__init__(
            coordinator, data, f"{prefix}_shaded", display_name(f"{label} Verschattet")
        )
        self._i_key = i_key
        self._other_keys = [k for _, _, _, k in STRINGS if k != i_key]
        self._ratio: float | None = None

    @callback
    def _handle_coordinator_update(self) -> None:
        own = self._value(self._i_key)
        others = [v for v in (self._value(k) for k in self._other_keys) if v is not None]
        reference = statistics.median(others) if others else None

        if own is None or reference is None or reference < MIN_CURRENT_FOR_RATIO:
            # Nachts oder bei fehlenden Werten ist die Aussage nicht definiert.
            # Unbekannt ist ehrlicher als ein eingefrorenes "nicht verschattet".
            self._ratio = None
            self._state = None
        else:
            ratio = own / reference
            self._ratio = ratio
            if self._state is None:
                self._state = ratio < SHADE_ON
            elif self._state and ratio > SHADE_OFF:
                self._state = False
            elif not self._state and ratio < SHADE_ON:
                self._state = True

        super()._handle_coordinator_update()

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        return {
            "modbus_address": REGISTERS_BY_KEY[self._i_key].address,
            "modbus_function": 4,
            "modbus_datatype": "berechnet",
            "modbus_scale": 1,
            "deutung_sicher": True,
            "stromanteil": None if self._ratio is None else round(self._ratio * 100, 1),
            "schwelle_ein": SHADE_ON,
            "schwelle_aus": SHADE_OFF,
        }


class String4ShadedBinarySensor(SolarbankBinaryEntity):
    """Verschattung von Strang 4, ueber den Leistungsanteil.

    Strang 4 hat keinen gemessenen Strom, also kann er nicht wie PV1-3 ueber
    den Stromanteil geprueft werden. Der naheliegende Ausweg - Strom aus der
    Schaetzspannung zurueckrechnen - ist ausgerechnet hier der falsche: bei
    Verschattung wird die Spannung um rund 9,5 % zu niedrig und der Strom um
    rund 10,5 % zu hoch geschaetzt (const.py, PV4_ERROR_SHADED). Der
    Stromanteil fiele damit zu guenstig aus und die Verschattung wuerde zu
    spaet erkannt - ein blinder Fleck genau an der Stelle, fuer die es den
    Sensor gibt.

    Der Leistungsanteil braucht keine Spannungsannahme: die Leistung von
    Strang 4 ist die Differenz zweier Messgroessen und damit exakt. Dass er
    dem Stromanteil als Verschattungsmass gleichwertig ist, ist an den drei
    gemessenen Straengen belegt - 99,22 % identische Urteile ueber 3075
    Messpunkte (tools/kreuzvalidierung_pv4.py).

    Schwellen und Hysterese sind dieselben wie bei PV1-3, damit alle vier
    Module nach demselben Massstab bewertet werden. Hinzu kommt allein eine
    Bestaetigung ueber PV4_SHADE_CONFIRM Messpunkte, weil P4 als Differenz die
    10-W-Quantisierung der Gesamtleistung erbt - Begruendung und Messwerte
    stehen an der Konstante in const.py.
    """

    _attr_device_class = "problem"
    _attr_icon = "mdi:weather-cloudy"

    def __init__(self, coordinator, data) -> None:
        super().__init__(
            coordinator, data, "pv4_shaded", display_name("Modul 4 Verschattet")
        )
        self._ratio: float | None = None
        self._kandidat: bool | None = None
        self._bestaetigungen = 0

    @callback
    def _handle_coordinator_update(self) -> None:
        werte, _ = (
            string_powers(self.coordinator.data)
            if self.coordinator.data
            else ([None] * 4, False)
        )
        eigen = werte[3]
        referenz = other_median(werte, 3)

        if eigen is None or referenz is None or referenz < MIN_POWER_FOR_RATIO:
            # Nachts oder bei fehlenden Werten ist die Aussage nicht definiert.
            # Unbekannt ist ehrlicher als ein eingefrorenes "nicht verschattet".
            self._ratio = None
            self._state = None
            self._kandidat = None
            self._bestaetigungen = 0
        else:
            ratio = eigen / referenz
            self._ratio = ratio

            if self._state is None:
                # Erste Festlegung sofort, sonst bliebe der Sensor am Morgen
                # unnoetig lange unbekannt.
                self._state = ratio < SHADE_ON
                self._kandidat = None
                self._bestaetigungen = 0
            else:
                ziel = self._state
                if self._state and ratio > SHADE_OFF:
                    ziel = False
                elif not self._state and ratio < SHADE_ON:
                    ziel = True

                if ziel == self._state:
                    self._kandidat = None
                    self._bestaetigungen = 0
                else:
                    if ziel == self._kandidat:
                        self._bestaetigungen += 1
                    else:
                        self._kandidat = ziel
                        self._bestaetigungen = 1
                    if self._bestaetigungen >= PV4_SHADE_CONFIRM:
                        self._state = ziel
                        self._kandidat = None
                        self._bestaetigungen = 0

        super()._handle_coordinator_update()

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        return {
            "modbus_address": "10002 minus 10167..10172",
            "modbus_function": 4,
            "modbus_datatype": "berechnet",
            "modbus_scale": 1,
            # Die Leistung ist exakt, also ist es auch dieses Urteil. Nur die
            # Zuordnung zu einem physischen Modul steht nicht fest - wie schon
            # bei sensor.pv_modul_4_leistung.
            "deutung_sicher": True,
            "leistungsanteil": None if self._ratio is None else round(self._ratio * 100, 1),
            "kennzahl": "Leistungsanteil statt Stromanteil",
            "schwelle_ein": SHADE_ON,
            "schwelle_aus": SHADE_OFF,
            "mindestleistung_referenz_w": MIN_POWER_FOR_RATIO,
            "bestaetigung_messpunkte": PV4_SHADE_CONFIRM,
            "bestaetigung_laeuft": self._bestaetigungen or None,
        }


class CurtailmentBinarySensor(SolarbankBinaryEntity):
    """Abregelung: alle Strangspannungen liegen ueber 0.92 * Voc(T).

    Ein MPP-Tracker faehrt normal bei 0.832 * Voc. Verschiebt der Wechselrichter
    den Arbeitspunkt Richtung Leerlauf, steigt die Spannung und der Strom bricht
    ein. Zwischen Vmp und Schwelle liegen knapp neun Prozentpunkte - genug Luft
    fuer Messrauschen und Vmp-Drift bei schwacher Einstrahlung.

    Die Zelltemperatur wird aus der Aussentemperatur geschaetzt und nicht aus der
    Spannung zurueckgerechnet: Letzteres waere zirkulaer, weil genau die Spannung
    gegen die Schwelle geprueft wird.
    """

    _attr_device_class = "problem"
    _attr_icon = "mdi:transmission-tower-off"

    def __init__(self, coordinator, data, outdoor_entity: str) -> None:
        super().__init__(coordinator, data, "curtailment", "PV Abregelung erkannt")
        self._outdoor_entity = outdoor_entity
        self._threshold: float | None = None

    def _outdoor_temp(self) -> float | None:
        state = self.hass.states.get(self._outdoor_entity)
        if state is None or state.state in ("unknown", "unavailable"):
            return None
        try:
            return float(state.state)
        except ValueError:
            return None

    @callback
    def _handle_coordinator_update(self) -> None:
        ambient = self._outdoor_temp()
        voltages = [self._value(v) for _, _, v, _ in STRINGS]
        currents = [self._value(i) for _, _, _, i in STRINGS]

        # Schwelle und Entscheidung stehen in physik.py, weil sensor.py
        # dieselbe Sperre fuer die theoretische Leistung braucht.
        self._threshold = None if ambient is None else round(curtail_threshold(ambient), 1)
        self._state = is_curtailed(voltages, currents, ambient)

        super()._handle_coordinator_update()

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        return {
            "modbus_address": "10167, 10169, 10171",
            "modbus_function": 4,
            "modbus_datatype": "berechnet",
            "modbus_scale": 1,
            "deutung_sicher": False,
            "schwelle_v": self._threshold,
            "aussentemperatur_entity": self._outdoor_entity,
            "annahme_zelltemperatur": f"Aussentemperatur + {CELL_OVER_AMBIENT:.0f} K",
        }
