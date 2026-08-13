"""Konstanten der Solarbank-App.

Diese Integration liefert AUSSCHLIESSLICH eine Oberflaeche. Sie hat keinen
Modbus-Client, keine Entities und keinen Schreibpfad zum Geraet. Alles, was die
App anzeigt, kommt aus bereits vorhandenen Integrationen; alles, was sie
aendert, laeuft ueber HA-Services der offiziellen Anker-Integration oder ueber
HA-Helfer.
"""
from typing import Final

DOMAIN: Final = "solarbank_app"

# URL, unter der die Oberflaeche in der Seitenleiste erscheint.
PANEL_URL: Final = "solarbank"
PANEL_TITLE: Final = "Solarbank"
PANEL_ICON: Final = "mdi:solar-power-variant"

# Basis, unter der die statischen Dateien ausgeliefert werden. Der Modulpfad
# bekommt in __init__.py einen Versionsanhang, damit ein Browser nach einem
# Update nicht die alte Datei aus dem Cache nimmt - der haeufigste Grund fuer
# "die Aenderung kommt nicht an" bei Custom Panels.
STATIC_URL: Final = "/solarbank_app_static"
STATIC_DIR: Final = "www"

# Einstiegsmodul und Name des Custom Elements. Beides muss zusammenpassen:
# HA laedt das Modul und instanziiert dann genau dieses Element.
PANEL_MODULE: Final = "app.js"
PANEL_ELEMENT: Final = "solarbank-app"
