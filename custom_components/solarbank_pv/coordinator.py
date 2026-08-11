"""Ein Coordinator je Registergruppe.

Warum je Gruppe und nicht einer fuer alles: Die Gruppen haben sehr
unterschiedliche Aktualisierungsintervalle - Strangdaten alle 30 s, das
AC-Ausgangslimit alle 5 Minuten, die Geraetezeit stuendlich. Ein gemeinsamer
Coordinator muesste sich am schnellsten Intervall orientieren und wuerde das
Geraet ohne Nutzen belasten.

Nebeneffekt, der hier ausdruecklich erwuenscht ist: Ein DataUpdateCoordinator
plant seine Aktualisierung erst, wenn sich der erste Zuhoerer anmeldet, und
stellt sie ein, wenn der letzte geht. Deaktivierte Entities melden sich nie an.
Eine Gruppe, deren Entities alle deaktiviert sind, erzeugt daher gar keinen
Netzverkehr - die Voreinstellung "alles ausser Strangdaten und Grenzen ist aus"
kostet nichts.
"""
from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import BLOCKS, DOMAIN, MAX_BLOCK_FAILURES, Group
from .modbus_reader import ModbusError, ModbusExceptionResponse, SolarbankReader

_LOGGER = logging.getLogger(__name__)


class SolarbankGroupCoordinator(DataUpdateCoordinator[dict[int, int]]):
    """Liest die Bloecke einer Gruppe und stellt Rohwoerter je Adresse bereit."""

    def __init__(
        self,
        hass: HomeAssistant,
        reader: SolarbankReader,
        group: Group,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} {group.key}",
            update_interval=timedelta(seconds=group.interval),
        )
        self.group = group
        self._reader = reader
        self._blocks = list(BLOCKS[group.key])
        # Bloecke, die das Geraet dauerhaft ablehnt. Werden aus der Abfrage
        # genommen, damit wir es nicht bei jedem Zyklus erneut belasten.
        self.dropped_blocks: set[tuple[int, int]] = set()
        self._failures: dict[tuple[int, int], int] = {}
        self._offline_logged = False

    async def _async_update_data(self) -> dict[int, int]:
        registers: dict[int, int] = {}

        for block in self._blocks:
            ident = (block.address, block.count)
            if ident in self.dropped_blocks:
                continue

            try:
                words = await self._reader.read_block(block.address, block.count)

            except ModbusExceptionResponse as exc:
                # Das Geraet antwortet, lehnt aber diese Start/Count-Kombination
                # ab. Das ist ein Konfigurationsproblem, kein Verbindungsproblem
                # - die uebrigen Bloecke der Gruppe bleiben gueltig.
                count = self._failures.get(ident, 0) + 1
                self._failures[ident] = count
                if count >= MAX_BLOCK_FAILURES:
                    self.dropped_blocks.add(ident)
                    _LOGGER.warning(
                        "Block %s:%s wird nicht mehr abgefragt, das Geraet lehnt "
                        "ihn dauerhaft ab (%s). Dieser Block war %s.",
                        block.address,
                        block.count,
                        exc,
                        "als belegt eingetragen" if block.proven else "ungeprueft",
                    )
                continue

            except ModbusError as exc:
                # Transportfehler. Die ganze Gruppe gilt als nicht gelesen,
                # damit Entities unavailable werden statt alte Werte zu halten.
                if not self._offline_logged:
                    _LOGGER.warning("Gruppe %s nicht lesbar: %s", self.group.key, exc)
                    self._offline_logged = True
                raise UpdateFailed(str(exc)) from exc

            self._failures.pop(ident, None)
            for offset, word in enumerate(words):
                registers[block.address + offset] = word

        if not registers:
            raise UpdateFailed(
                f"Gruppe {self.group.key} lieferte kein einziges Register"
            )

        if self._offline_logged:
            _LOGGER.info("Gruppe %s wieder lesbar", self.group.key)
            self._offline_logged = False

        return registers
