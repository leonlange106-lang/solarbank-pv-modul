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

from . import SolarbankData
from .const import (
    CELL_OVER_AMBIENT,
    CONF_OUTDOOR_TEMP,
    CURTAIL_VOC_FRACTION,
    DEFAULT_OUTDOOR_TEMP,
    DOMAIN,
    MIN_CURRENT_FOR_TEMP,
    MODULE_TEMP_COEFF,
    MODULE_VOC_STC,
    REGISTERS_BY_KEY,
    SHADE_OFF,
    SHADE_ON,
    STRINGS,
)
from .coordinator import SolarbankGroupCoordinator
from .sensor import display_name, read_value

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

        if own is None or reference is None or reference < MIN_CURRENT_FOR_TEMP:
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

        if ambient is None or any(v is None for v in voltages) or any(c is None for c in currents):
            self._threshold = None
            self._state = None
            super()._handle_coordinator_update()
            return

        cell = ambient + CELL_OVER_AMBIENT
        voc = MODULE_VOC_STC * (1.0 - MODULE_TEMP_COEFF * (cell - 25.0))
        threshold = CURTAIL_VOC_FRACTION * voc
        self._threshold = round(threshold, 1)

        # Nachts steht die Spannung ohne Last ebenfalls hoch. Ohne einen
        # Mindeststrom auf mindestens einem Strang waere jede Nacht eine
        # gemeldete Abregelung.
        producing = any(c >= MIN_CURRENT_FOR_TEMP for c in currents if c is not None)
        self._state = producing and all(v >= threshold for v in voltages if v is not None)

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
