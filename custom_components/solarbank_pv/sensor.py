"""Sensoren: Rohregister und abgeleitete Groessen.

Bei vier identischen, koplanaren, gleich ausgerichteten Modulen ist jedes Modul
die Kontrollgruppe fuer die anderen. Deshalb ist das Stromverhaeltnis zum Median
der uebrigen Straenge die Kernkennzahl - es braucht weder Sonnenstandsmodell
noch Wetterprognose, weil sich alle Module dieselbe Wolke teilen.

Zur Benennung: has_entity_name ist bewusst False. Mit True wuerde Home Assistant
den Geraetenamen voranstellen und Entity-IDs der Form
sensor.solarbank_dc_straenge_441_modul_1_leistung erzeugen. Die Anlage fuehrt
aber die Konvention sensor.pv_*, und die hat Vorrang. Der Anzeigename traegt
deshalb selbst das Praefix "PV".
"""
from __future__ import annotations

import statistics
from datetime import datetime, timezone

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from . import SolarbankData
from .const import (
    DOMAIN,
    MIN_CURRENT_FOR_RATIO,
    MIN_CURRENT_FOR_TEMP,
    MODULE_TEMP_COEFF,
    MODULE_VMP_STC,
    REGISTERS,
    REGISTERS_BY_KEY,
    STRINGS,
    Reg,
)
from .coordinator import SolarbankGroupCoordinator
from .modbus_reader import decode


def display_name(name: str) -> str:
    """Stellt das Anlagenpraefix voran, ohne es zu verdoppeln."""
    return name if name.startswith("PV") else f"PV {name}"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    data: SolarbankData = hass.data[DOMAIN][entry.entry_id]
    entities: list[SensorEntity] = []

    for reg in REGISTERS:
        coordinator = data.coordinators[reg.group]
        cls = DeviceTimeSensor if reg.key == "device_time" else RegisterSensor
        entities.append(cls(coordinator, data, reg))

    strings = data.coordinators["strings"]
    for prefix, label, v_key, i_key in STRINGS:
        entities.append(StringPowerSensor(strings, data, prefix, label, v_key, i_key))
        entities.append(CellTemperatureSensor(strings, data, prefix, label, v_key, i_key))
        entities.append(CurrentRatioSensor(strings, data, prefix, label, i_key))

    async_add_entities(entities)


def read_value(registers: dict[int, int], reg: Reg) -> float | None:
    """Dekodiert ein Register aus dem Rohwoerter-Abbild der Gruppe."""
    words: list[int] = []
    for offset in range(reg.words):
        word = registers.get(reg.address + offset)
        if word is None:
            return None
        words.append(word)
    return decode(reg.kind, words) * reg.scale


class SolarbankEntity(CoordinatorEntity[SolarbankGroupCoordinator]):
    """Gemeinsame Basis: Geraetezuordnung und stabile Identitaet."""

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
        # Bewusst aus Adresse beziehungsweise Schluessel und Seriennummernkuerzel
        # gebildet, nicht aus der entry_id: so ueberleben Verlaufsdaten auch ein
        # Entfernen und Neuanlegen des Config-Entries. Diese Kennung wird nie
        # geaendert, der Anzeigename darf jederzeit verbessert werden.
        self._attr_unique_id = f"solarbank_{data.serial_suffix}_{unique_suffix}"
        self._attr_name = name
        # Muss ausdruecklich gesetzt werden. Home Assistant stellt bei der
        # ID-Bildung sonst den Geraetenamen voran und erzeugt
        # sensor.solarbank_dc_straenge_441_pv_modul_1_leistung - auch bei
        # has_entity_name = False. Die Anlage fuehrt aber sensor.pv_*.
        self.entity_id = f"sensor.{slugify(name)}"


class RegisterSensor(SolarbankEntity, SensorEntity):
    """Ein Rohregister, unveraendert bis auf die Skalierung."""

    def __init__(
        self,
        coordinator: SolarbankGroupCoordinator,
        data: SolarbankData,
        reg: Reg,
    ) -> None:
        super().__init__(coordinator, data, f"r{reg.address}", display_name(reg.name))
        self._reg = reg
        self._attr_native_unit_of_measurement = reg.unit
        self._attr_device_class = reg.device_class
        self._attr_state_class = reg.state_class
        self._attr_icon = reg.icon
        self._attr_entity_registry_enabled_default = reg.default_enabled

    @property
    def native_value(self) -> float | None:
        if not self.coordinator.data:
            return None
        value = read_value(self.coordinator.data, self._reg)
        return None if value is None else round(value, 3)

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        return {
            "modbus_address": self._reg.address,
            "modbus_function": 4,
            "modbus_datatype": self._reg.kind,
            "modbus_scale": self._reg.scale,
            "deutung_sicher": self._reg.certain,
        }


class DeviceTimeSensor(RegisterSensor):
    """Geraetezeit als Zeitstempel statt als Sekundenzahl."""

    @property
    def native_value(self) -> datetime | None:  # type: ignore[override]
        if not self.coordinator.data:
            return None
        raw = read_value(self.coordinator.data, self._reg)
        if raw is None or raw <= 0:
            return None
        return datetime.fromtimestamp(int(raw), tz=timezone.utc)


class StringDerivedEntity(SolarbankEntity, SensorEntity):
    """Basis fuer die aus Spannung und Strom berechneten Groessen."""

    def __init__(
        self,
        coordinator: SolarbankGroupCoordinator,
        data: SolarbankData,
        unique_suffix: str,
        name: str,
    ) -> None:
        super().__init__(coordinator, data, unique_suffix, name)
        self._attr_entity_registry_enabled_default = True

    def _reg_value(self, key: str) -> float | None:
        if not self.coordinator.data:
            return None
        return read_value(self.coordinator.data, REGISTERS_BY_KEY[key])


class StringPowerSensor(StringDerivedEntity):
    """Leistung eines Strangs, Spannung mal Strom."""

    _attr_native_unit_of_measurement = "W"
    _attr_device_class = "power"
    _attr_state_class = "measurement"
    _attr_icon = "mdi:solar-panel"

    def __init__(self, coordinator, data, prefix, label, v_key, i_key) -> None:
        super().__init__(
            coordinator, data, f"{prefix}_power", display_name(f"{label} Leistung")
        )
        self._v_key = v_key
        self._i_key = i_key

    @property
    def native_value(self) -> float | None:
        volt = self._reg_value(self._v_key)
        amp = self._reg_value(self._i_key)
        if volt is None or amp is None:
            return None
        return round(volt * amp, 1)


class CellTemperatureSensor(StringDerivedEntity):
    """Zelltemperatur, aus der Spannung ueber Vmp(T) zurueckgerechnet.

    Zweiter, physikalisch unabhaengiger Verschattungsnachweis - ein verschattetes
    Modul heizt sich nicht auf - und nebenbei eine Ueberhitzungsueberwachung ohne
    einen einzigen Fuehler.

    Gueltig nur unter Last: ohne nennenswerten Strom liegt der Arbeitspunkt
    Richtung Leerlauf, und eine Rueckrechnung ueber Vmp waere sinnlos. Dann wird
    None geliefert statt einer erfundenen Zahl.
    """

    _attr_native_unit_of_measurement = "°C"
    _attr_device_class = "temperature"
    _attr_state_class = "measurement"
    _attr_icon = "mdi:thermometer"

    def __init__(self, coordinator, data, prefix, label, v_key, i_key) -> None:
        super().__init__(
            coordinator, data, f"{prefix}_cell_temp", display_name(f"{label} Zelltemperatur")
        )
        self._v_key = v_key
        self._i_key = i_key

    @property
    def native_value(self) -> float | None:
        volt = self._reg_value(self._v_key)
        amp = self._reg_value(self._i_key)
        if volt is None or amp is None or amp < MIN_CURRENT_FOR_TEMP:
            return None
        return round(25.0 + (1.0 - volt / MODULE_VMP_STC) / MODULE_TEMP_COEFF, 1)

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        return {
            "modbus_address": REGISTERS_BY_KEY[self._v_key].address,
            "modbus_function": 4,
            "modbus_datatype": "berechnet",
            "modbus_scale": 1,
            "deutung_sicher": False,
            "formel": "25 + (1 - U / 33.18) / 0.0025",
            "gueltig_ab_strom": MIN_CURRENT_FOR_TEMP,
        }


class CurrentRatioSensor(StringDerivedEntity):
    """Strom dieses Strangs im Verhaeltnis zum Median der uebrigen.

    Die Kernkennzahl. Unabhaengig von Tageszeit, Wetter und Jahreszeit, weil
    sich alle Module dieselbe Einstrahlung teilen. Jede Abweichung ist
    Verschattung, Verschmutzung oder Defekt.
    """

    _attr_native_unit_of_measurement = "%"
    _attr_state_class = "measurement"
    _attr_icon = "mdi:scale-balance"

    def __init__(self, coordinator, data, prefix, label, i_key) -> None:
        super().__init__(
            coordinator, data, f"{prefix}_current_ratio", display_name(f"{label} Stromanteil")
        )
        self._i_key = i_key
        self._other_keys = [k for _, _, _, k in STRINGS if k != i_key]

    @property
    def native_value(self) -> float | None:
        own = self._reg_value(self._i_key)
        if own is None:
            return None
        others = [v for v in (self._reg_value(k) for k in self._other_keys) if v is not None]
        if not others:
            return None
        reference = statistics.median(others)
        # Nachts liefern alle Straenge null. Ein Verhaeltnis waere dann entweder
        # eine Division durch null oder eine Scheinaussage.
        if reference < MIN_CURRENT_FOR_RATIO:
            return None
        return round(own / reference * 100.0, 1)

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        return {
            "modbus_address": REGISTERS_BY_KEY[self._i_key].address,
            "modbus_function": 4,
            "modbus_datatype": "berechnet",
            "modbus_scale": 1,
            "deutung_sicher": True,
            "referenz": "Median der uebrigen Straenge",
        }
