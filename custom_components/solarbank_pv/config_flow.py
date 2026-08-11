"""Minimaler Einrichtungsdialog.

Ein Wizard ist laut Auftrag nicht noetig, aber ein Config-Entry schon: nur damit
bekommt die Integration ein eigenes Geraet in der Registry, eine saubere
Entladelogik und die Moeglichkeit, Host oder Aussentemperatur-Entity zu aendern,
ohne eine Datei anzufassen. Alle Felder sind vorbelegt - im Normalfall genuegt
ein Klick auf Absenden.
"""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.helpers import selector

from .const import (
    CONF_OUTDOOR_TEMP,
    CONF_SERIAL_SUFFIX,
    DEFAULT_HOST,
    DEFAULT_OUTDOOR_TEMP,
    DEFAULT_PORT,
    DEFAULT_SERIAL_SUFFIX,
    DEFAULT_UNIT,
    DOMAIN,
    SOCKET_TIMEOUT,
)
from .modbus_reader import ModbusError, SolarbankReader

CONF_UNIT = "unit"

# Belegter Block: deckt 10156 und die Straenge 10167-10175 in einer Anfrage ab.
PROBE_ADDRESS = 10144
PROBE_COUNT = 32


class SolarbankPvConfigFlow(ConfigFlow, domain=DOMAIN):
    """Einstufiger Dialog mit Verbindungstest."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            port = user_input[CONF_PORT]
            unit = user_input[CONF_UNIT]

            await self.async_set_unique_id(f"{host}:{port}")
            self._abort_if_unique_id_configured()

            reader = SolarbankReader(host, port, unit, SOCKET_TIMEOUT)
            try:
                # Nur lesen. Schlaegt das fehl, stimmt etwas an Adresse, Port
                # oder Unit-ID nicht - dann gar nicht erst einrichten.
                await reader.read_block(PROBE_ADDRESS, PROBE_COUNT)
            except ModbusError:
                errors["base"] = "cannot_connect"
            finally:
                await reader.close()

            if not errors:
                return self.async_create_entry(
                    title=f"Solarbank DC-Straenge ({user_input[CONF_SERIAL_SUFFIX]})",
                    data=user_input,
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_HOST, default=DEFAULT_HOST): str,
                vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
                vol.Required(CONF_UNIT, default=DEFAULT_UNIT): int,
                vol.Required(
                    CONF_SERIAL_SUFFIX, default=DEFAULT_SERIAL_SUFFIX
                ): str,
                vol.Required(
                    CONF_OUTDOOR_TEMP, default=DEFAULT_OUTDOOR_TEMP
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor", device_class="temperature")
                ),
            }
        )
        return self.async_show_form(
            step_id="user", data_schema=schema, errors=errors
        )
