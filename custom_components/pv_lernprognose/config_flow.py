"""Konfiguration.

Abgefragt wird nur, was sich nicht messen laesst: Neigung und Azimut der
Modulebene. Alles andere kommt aus dem Geraet (kennwerte.py) oder wird
gelernt (schaetzer.py). Standort und Zeitzone stammen aus der
Home-Assistant-Grundeinstellung.

Ein Fehler in Neigung und Azimut ist unkritisch: die gelernte Tagesform
ist das Verhaeltnis von Messung zu Geometrie und schluckt jede
systematische Schieflage mit. Die beiden Werte bestimmen nur, wieviel
Arbeit die Form leisten muss.
"""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import CONF_AZIMUT, CONF_NEIGUNG, DEFAULT_AZIMUT, DEFAULT_NEIGUNG, DOMAIN


def _schema(vorgabe_neigung: float, vorgabe_azimut: float) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_NEIGUNG, default=vorgabe_neigung): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0, max=90, step=0.5, unit_of_measurement="Grad",
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
            vol.Required(CONF_AZIMUT, default=vorgabe_azimut): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0, max=360, step=1, unit_of_measurement="Grad",
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
        }
    )


class LernprognoseConfigFlow(ConfigFlow, domain=DOMAIN):
    """Einmalige Einrichtung."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        if user_input is not None:
            return self.async_create_entry(title="PV Lernprognose", data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=_schema(DEFAULT_NEIGUNG, DEFAULT_AZIMUT),
        )

    @staticmethod
    @callback
    def async_get_options_flow(entry: ConfigEntry) -> OptionsFlow:
        return LernprognoseOptionsFlow()


class LernprognoseOptionsFlow(OptionsFlow):
    """Neigung und Azimut nachtraeglich aendern."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        aktuell_neigung = self.config_entry.options.get(
            CONF_NEIGUNG, self.config_entry.data.get(CONF_NEIGUNG, DEFAULT_NEIGUNG)
        )
        aktuell_azimut = self.config_entry.options.get(
            CONF_AZIMUT, self.config_entry.data.get(CONF_AZIMUT, DEFAULT_AZIMUT)
        )
        return self.async_show_form(
            step_id="init",
            data_schema=_schema(aktuell_neigung, aktuell_azimut),
        )
