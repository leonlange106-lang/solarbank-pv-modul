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
from datetime import datetime, timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import BLOCKS, DOMAIN, MAX_BLOCK_FAILURES, Group, required_addresses
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
        # Letzter Fehlertext, damit die Diagnose nicht nur "kaputt" meldet,
        # sondern den Grund. Ein Zaehler ohne Grund ist keine Diagnose.
        self.last_error: str | None = None
        # Selbst mitgefuehrt statt aus dem Coordinator gelesen: ein Attribut
        # wie last_update_success_time gibt es in dieser Kernversion nicht,
        # und ein getattr-Zugriff darauf liefert stumm None - genau die Sorte
        # stiller Leerwert, gegen die diese Datei gebaut wird.
        self.last_success_time: datetime | None = None

    # -- Fakten fuer die Gesundheitsanzeige ---------------------------------
    #
    # Bewusst nur Fakten, keine Bewertung. Ob ein verworfener Block eine
    # Warnung oder eine Stoerung ist, entscheidet die Diagnoseschicht in Home
    # Assistant - dort laesst sich die Schwelle ohne Neustart aendern.

    @property
    def block_count(self) -> int:
        return len(self._blocks)

    @property
    def dropped_labels(self) -> list[str]:
        return sorted(f"{addr}:{count}" for addr, count in self.dropped_blocks)

    @property
    def missing_addresses(self) -> list[int]:
        """Geforderte Register, die im letzten Abbild fehlen.

        Das ist der Kern der ganzen Uebung. Faellt ein Leseblock nach
        MAX_BLOCK_FAILURES aus der Abfrage, liefert die Gruppe weiterhin
        Daten - nur eben ohne die Register dieses Blocks. Die betroffenen
        Entities gehen auf unknown, ohne dass irgendetwas unavailable wird.
        Genau so blieb 10004/10005 tagelang unbemerkt.
        """
        vorhanden = self.data or {}
        return sorted(a for a in required_addresses(self.group.key) if a not in vorhanden)

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
                self.last_error = str(exc)
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

        self.last_error = None
        self.last_success_time = dt_util.utcnow()
        return registers
