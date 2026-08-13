"""PV Lernprognose - selbstlernende Speicherprognose.

Ersetzt die festen Groessen der bisherigen Jinja-Prognose durch
mitlaufende Schaetzer. Was gelernt wird, steht in schaetzer.py; was aus
dem Geraet gelesen wird, in kennwerte.py; was reine Physik bleibt, in
sonne.py und im Abschnitt B von const.py.

Warum eine eigene Integration und nicht pyscript (beides waere moeglich,
pyscript ist installiert):

  - Der Lernstand muss Neustarts ueberleben. `helpers.storage.Store` gibt
    versionierte, atomar geschriebene Persistenz, die Home Assistant beim
    Herunterfahren selbst noch leert. In pyscript muesste man Dateien von
    Hand schreiben, ohne Atomizitaetsgarantie - und ein halb geschriebener
    Lernstand ist schlimmer als keiner.
  - Der Kaltstart liest die Langzeitstatistik. Das braucht den
    Recorder-Executor (`get_instance(hass).async_add_executor_job`);
    aus pyscript heraus ist das umstaendlich und blockiert leicht den
    Event-Loop.
  - Die gelernten Groessen sollen als Entities mit stabiler `unique_id`
    sichtbar sein, damit man ihnen beim Lernen zusehen kann und die
    Langzeitstatistik sie behaelt. pyscript-Entities haben keine
    unique_id und tauchen nicht in der Entity-Registry auf.
  - Das Repo fuehrt mit solarbank_pv bereits genau dieses Muster.

Diese Integration schreibt nichts. Kein Modbus, kein Service-Call, keine
Zustandsaenderung an fremden Entities. Sie liest, lernt und stellt eigene
Sensoren bereit.
"""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import Event, HomeAssistant

from .const import DOMAIN
from .coordinator import LernprognoseCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    coordinator = LernprognoseCoordinator(hass, entry)
    await coordinator.async_laden()
    await coordinator.async_config_entry_first_refresh()

    async def _beim_beenden(_: Event) -> None:
        # Den laufenden Tag verdichten, damit er nicht verloren geht.
        coordinator.lernstand.hauslast.tag_abschliessen()
        coordinator.lernstand.form.tag_abschliessen()
        await coordinator.async_speichern()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _beim_beenden)
    )

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    entladen = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if entladen:
        coordinator: LernprognoseCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.async_speichern()
    return entladen


async def _async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
