"""Solarbank DC-Strangdaten.

Zweite, ausschliesslich lesende Integration neben anker_solix_official. Sie
liest die vier MPP-Tracker-Register, die die offizielle Integration nicht kennt.

Konfliktfreiheit ist an drei Stellen abgesichert:
  - eigene Domain und eigenes Geraet in der Registry, kein connections-Set
  - die Zielregister 10167-10172 liegen in der Luecke zwischen 10156 und 10208,
    die die offizielle Integration nicht abfragt
  - nur Function Code 4; ein Schreibzugriff ist konstruktiv unmoeglich
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo

from .const import (
    CONF_SERIAL_SUFFIX,
    DEFAULT_SERIAL_SUFFIX,
    DOMAIN,
    GROUPS,
    SOCKET_TIMEOUT,
)
from .coordinator import SolarbankGroupCoordinator
from .modbus_reader import SolarbankReader

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR]

CONF_UNIT = "unit"


@dataclass
class SolarbankData:
    """Laufzeitcontainer, unter hass.data abgelegt."""

    reader: SolarbankReader
    device_info: DeviceInfo
    serial_suffix: str
    coordinators: dict[str, SolarbankGroupCoordinator] = field(default_factory=dict)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Verbindung aufbauen und je Registergruppe einen Coordinator anlegen."""
    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]
    unit = entry.data[CONF_UNIT]
    suffix = entry.data.get(CONF_SERIAL_SUFFIX, DEFAULT_SERIAL_SUFFIX)

    reader = SolarbankReader(host, port, unit, SOCKET_TIMEOUT)

    # Bewusst eigenstaendiges Geraet. Der Identifier traegt die eigene Domain,
    # der Name wiederholt NICHT den der offiziellen Integration - sonst haengt
    # Home Assistant an den generierten Entity-IDs stumm "_2" an. Kein
    # connections-Set: das ist der einzige integrationsuebergreifende
    # Verschmelzungsvektor, und die offizielle Integration setzt ebenfalls keines.
    device_info = DeviceInfo(
        identifiers={(DOMAIN, f"{host}:{port}")},
        name=f"Solarbank DC-Straenge ({suffix})",
        manufacturer="Anker",
        model="Solarbank 4 E5000 Pro (DC-Auslesung)",
        configuration_url=f"http://{host}",
    )

    data = SolarbankData(reader=reader, device_info=device_info, serial_suffix=suffix)

    for key, group in GROUPS.items():
        data.coordinators[key] = SolarbankGroupCoordinator(hass, reader, group)

    # Nur die standardmaessig aktiven Gruppen einmal vorab laden. Die uebrigen
    # holen sich ihre Daten selbst, sobald jemand eine ihrer Entities aktiviert.
    for key, group in GROUPS.items():
        if group.enabled:
            await data.coordinators[key].async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = data
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Plattformen entladen und die TCP-Sitzung sauber schliessen."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        data: SolarbankData = hass.data[DOMAIN].pop(entry.entry_id)
        await data.reader.close()
    return unloaded


async def _async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
