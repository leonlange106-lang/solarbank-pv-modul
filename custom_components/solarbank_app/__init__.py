"""Solarbank-App: eigene Oberflaeche als Custom Panel in Home Assistant.

WAS DIESE INTEGRATION IST
-------------------------
Ein Auslieferer fuer statische Dateien plus eine Panel-Registrierung. Mehr
nicht. Sie legt keine Entities an, haelt keinen Zustand und spricht kein
Modbus.

WAS SIE BEWUSST NICHT IST
-------------------------
Sie ist KEIN zweiter Leser am Geraet. Die Oberflaeche liest ausschliesslich
Entities, die `solarbank_pv`, `pv_lernprognose` und `anker_solix_official`
ohnehin bereitstellen. Ein weiterer Modbus-Client waere eine zusaetzliche
TCP-Sitzung auf einem Geraet, dessen Verbindungsverhalten in
docs/REGISTER.md Abschnitt 10 als empfindlich dokumentiert ist.

SCHREIBEN
---------
Die Oberflaeche schreibt nur ueber HA-Services - `select.select_option`,
`number.set_value`, `input_boolean.turn_on/off`, `input_number.set_value`.
Welcher Registerzugriff daraus wird, entscheidet allein die offizielle
Integration. `solarbank_pv` hat keinen Schreibpfad und bekommt keinen.

EINRICHTUNG
-----------
Eine Zeile in configuration.yaml:

    solarbank_app:
"""
from __future__ import annotations

import logging
from pathlib import Path

import voluptuous as vol

from homeassistant.components import frontend
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import async_get_integration

from .const import (
    DOMAIN,
    PANEL_ELEMENT,
    PANEL_ICON,
    PANEL_MODULE,
    PANEL_TITLE,
    PANEL_URL,
    STATIC_DIR,
    STATIC_URL,
)

_LOGGER = logging.getLogger(__name__)

# Die Integration nimmt keine Optionen entgegen. Das leere Schema sagt HA
# ausdruecklich, dass "solarbank_app:" ohne Unterschluessel gueltig ist -
# ohne das wirft die Konfigurationspruefung eine Warnung.
CONFIG_SCHEMA = vol.Schema({DOMAIN: vol.Schema({})}, extra=vol.ALLOW_EXTRA)


async def _version(hass: HomeAssistant) -> str:
    """Version aus dem Manifest, als Cache-Buster fuer die Modul-URL.

    Ohne Anhang liefert der Browser nach einem Update die alte Datei aus dem
    Cache aus. Das ist bei Custom Panels der mit Abstand haeufigste Grund
    dafuer, dass eine Aenderung scheinbar nicht ankommt.

    Gelesen wird ueber den Integrations-Loader, NICHT ueber einen eigenen
    Dateizugriff. Die erste Fassung tat Letzteres und HA hat es zu Recht
    gemeldet: "Detected blocking call to open ... inside the event loop".
    Ein synchroner Dateizugriff im Event-Loop blockiert alles andere, was HA
    in diesem Moment tut. Der Loader haelt das Manifest ohnehin im Cache.
    """
    try:
        integration = await async_get_integration(hass, DOMAIN)
        return str(integration.version or "0")
    except Exception:  # noqa: BLE001 - darf das Setup nie kippen
        return "0"


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Statische Dateien ausliefern und das Panel in die Seitenleiste haengen."""
    quelle = Path(__file__).parent / STATIC_DIR
    if not quelle.is_dir():
        _LOGGER.error(
            "Verzeichnis %s fehlt - die Oberflaeche kann nicht ausgeliefert werden",
            quelle,
        )
        return False

    # cache_headers=False: waehrend der Entwicklung soll der Browser nicht
    # aggressiv cachen. Der Versionsanhang unten deckt den Produktivfall ab.
    await hass.http.async_register_static_paths(
        [StaticPathConfig(STATIC_URL, str(quelle), False)]
    )

    modul_url = f"{STATIC_URL}/{PANEL_MODULE}?v={await _version(hass)}"

    # require_admin=False: die Ansichten sind Anzeige und Bedienung fuer den
    # Betreiber. Die Steuerelemente rufen HA-Services auf, deren
    # Berechtigungspruefung ohnehin serverseitig greift.
    frontend.async_register_built_in_panel(
        hass,
        component_name="custom",
        sidebar_title=PANEL_TITLE,
        sidebar_icon=PANEL_ICON,
        frontend_url_path=PANEL_URL,
        require_admin=False,
        config={
            "_panel_custom": {
                "name": PANEL_ELEMENT,
                "module_url": modul_url,
                # Kein iframe: das Panel soll das hass-Objekt direkt
                # bekommen. Mit iframe gaebe es keinen Zugriff darauf.
                "embed_iframe": False,
                "trust_external": False,
            }
        },
    )

    _LOGGER.info("Solarbank-App bereit: /%s, Modul %s", PANEL_URL, modul_url)
    return True
