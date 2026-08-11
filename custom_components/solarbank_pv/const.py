"""Konstanten und Registertabelle fuer die Solarbank-DC-Auslesung.

Die Registertabelle ist das eigentliche Ergebnis der Vorarbeit. Sie existiert in
keiner Herstellerdokumentation. Belege und Sicherheitsbewertung stehen in
docs/REGISTER.md; hier steht nur, was der Code braucht.

Trennung von Identitaet und Bezeichnung: die unique_id leitet sich aus Adresse
und Seriennummernkuerzel ab und wird nie geaendert. Der Anzeigename ist frei und
darf spaeter verbessert werden, ohne dass Automationen, Dashboards oder
Verlaufsdaten brechen.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Final

DOMAIN: Final = "solarbank_pv"

CONF_SERIAL_SUFFIX: Final = "serial_suffix"
CONF_OUTDOOR_TEMP: Final = "outdoor_temp_entity"

DEFAULT_HOST: Final = "192.168.178.86"
DEFAULT_PORT: Final = 502
DEFAULT_UNIT: Final = 1
DEFAULT_SERIAL_SUFFIX: Final = "441"
DEFAULT_OUTDOOR_TEMP: Final = "sensor.aussentemperatur"

# Kuerzer als die 10 s der offiziellen Integration, damit wir bei einer
# Kollision schnell zuruecktreten statt sie auszubremsen.
SOCKET_TIMEOUT: Final = 4.0

# Bewusst nicht 5 s wie die offizielle Integration - sonst liegen beide
# dauerhaft im selben Takt.
FALLBACK_INTERVAL: Final = 30

# Ein Block, der wiederholt Ausnahme 2 liefert, wird aus der Abfrage genommen.
# Das Geraet validiert Start/Count-Kombinationen; ein dauerhaft ungueltiger
# Block soll es nicht bei jedem Zyklus erneut belasten.
MAX_BLOCK_FAILURES: Final = 3


# ---------------------------------------------------------------------------
# Moduldaten Sakete SKT500M12-108D4, fuer die abgeleiteten Groessen
# ---------------------------------------------------------------------------

MODULE_VMP_STC: Final = 33.18       # V bei 25 Grad C
MODULE_VOC_STC: Final = 39.90       # V bei 25 Grad C
MODULE_TEMP_COEFF: Final = 0.0025   # 1/K, gilt fuer Voc wie Vmp
CELL_OVER_AMBIENT: Final = 25.0     # K, aus NMOT abgeleitet

# Untergrenzen fuer abgeleitete Groessen.
#
# MIN_CURRENT_FOR_TEMP: Die Rueckrechnung der Zelltemperatur ueber Vmp(T)
# unterstellt einen Arbeitspunkt nahe Nennbedingungen. Bei schwacher Einstrahlung
# wandert der MPP relativ zu Vmp, und die Formel liefert Unsinn - gemessen am
# 11.08.2026 um 17:52: 35,3 V bei 3,44 A ergaben rechnerisch minus 0,6 Grad C.
# Ein Drittel des Nennstroms (Imp = 15,07 A) ist die Grenze, ab der die
# Rueckrechnung belastbar ist. Darunter liefert der Sensor None statt einer
# erfundenen Temperatur.
MIN_CURRENT_FOR_TEMP: Final = 5.0   # A

# Fuer das Stromverhaeltnis genuegt eine viel niedrigere Schranke: dort geht es
# nur darum, eine Division durch nahezu null zu vermeiden, nicht um die
# Gueltigkeit eines physikalischen Modells.
MIN_CURRENT_FOR_RATIO: Final = 0.5  # A

# Verschattungsschwellen mit Hysterese, bezogen auf den Median der uebrigen
# Straenge. Unter 0.60 gilt als verschattet, erst ueber 0.70 wieder als frei.
SHADE_ON: Final = 0.60
SHADE_OFF: Final = 0.70

# Abregelung: ein MPP-Tracker faehrt normal bei 0.832 * Voc. Verschiebt sich der
# Arbeitspunkt ueber diesen Anteil Richtung Leerlauf, regelt der Wechselrichter ab.
CURTAIL_VOC_FRACTION: Final = 0.92


# ---------------------------------------------------------------------------
# Gruppen: Anzeigename, Abfrageintervall, standardmaessig aktiv
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Group:
    key: str
    name: str
    interval: int
    enabled: bool


GROUPS: Final[dict[str, Group]] = {
    g.key: g
    for g in (
        Group("strings", "Strangdaten", 30, True),
        Group("limits", "Leistungsgrenzen", 300, True),
        Group("grid", "Netzqualitaet", 60, False),
        Group("clock", "Geraetezeit", 3600, False),
        Group("mirror", "Redundanz zur offiziellen Integration", 30, False),
        Group("unknown", "Unbestimmt", 300, False),
    )
}


# ---------------------------------------------------------------------------
# Lesebloecke je Gruppe.
#
# proven=True heisst: diese Start/Count-Kombination ist im Adressraumscan als
# erfolgreich protokolliert. proven=False heisst ungeprueft, nicht widerlegt -
# solche Bloecke duerfen fehlschlagen, ohne die Gruppe mitzureissen.
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Block:
    address: int
    count: int
    proven: bool = True


BLOCKS: Final[dict[str, tuple[Block, ...]]] = {
    # 10144:32 deckt 10156 und 10167-10175 in EINER Anfrage ab.
    "strings": (Block(10144, 32), Block(10205, 1)),
    "limits": (Block(10036, 2), Block(10038, 2)),
    "grid": (Block(10199, 1), Block(10202, 1), Block(10208, 32)),
    "clock": (Block(10060, 2, proven=False),),
    "mirror": (
        Block(10002, 2),
        Block(10008, 2),
        Block(10010, 2),
        Block(10012, 2),
        Block(10014, 1),
        Block(10018, 2, proven=False),
        Block(10040, 32),
        Block(10208, 32),
        Block(10250, 1),
        Block(10262, 2, proven=False),
        Block(10264, 2, proven=False),
        Block(32768, 32),
        Block(60000, 32),
    ),
    "unknown": (
        Block(10040, 32),
        Block(10048, 32),
        Block(10112, 32),
        Block(10144, 32),
        Block(10183, 1),
        Block(10187, 1),
        Block(10208, 32),
        Block(10252, 1),
        Block(10256, 1),
        Block(32768, 32),
        Block(60000, 32),
    ),
}


# ---------------------------------------------------------------------------
# Registerdefinitionen
#
# kind: u16 | i32 | u32 | u16_hi (Highbyte eines bytegepackten Registers)
# scale: Rohwert wird damit multipliziert
# certain: Deutung gegen App, HA-Historie oder Herstellerdefinition verifiziert
# ---------------------------------------------------------------------------

# kind "i16": vorzeichenbehaftetes 16-Bit-Register. Die Strangstroeme brauchen
# das - siehe modbus_reader.decode(). Ohne Vorzeichen wird aus -0,08 A ein Wert
# von 655,28 A, und die abgeleitete Leistung springt auf ueber 20 kW.
@dataclass(frozen=True)
class Reg:
    key: str
    address: int
    kind: str
    scale: float
    name: str
    group: str
    certain: bool
    unit: str | None = None
    device_class: str | None = None
    state_class: str | None = "measurement"
    icon: str | None = None
    enabled: bool | None = None      # None = Gruppenvorgabe
    words: int = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "words", 2 if self.kind in ("i32", "u32") else 1)

    @property
    def default_enabled(self) -> bool:
        if self.enabled is not None:
            return self.enabled
        return GROUPS[self.group].enabled


_V = dict(unit="V", device_class="voltage", icon="mdi:solar-panel")
_A = dict(unit="A", device_class="current", icon="mdi:solar-panel")
_W = dict(unit="W", device_class="power")
_KWH = dict(unit="kWh", device_class="energy", state_class="total_increasing")
_PCT = dict(unit="%", device_class="battery")
_UNKNOWN = dict(state_class=None, icon="mdi:help-circle-outline")

REGISTERS: Final[tuple[Reg, ...]] = (
    # --- Strangdaten, aktiv --------------------------------------------------
    Reg("pv1_voltage", 10167, "u16", 0.1, "Modul 1 Spannung", "strings", True, **_V),
    Reg("pv1_current", 10168, "i16", 0.01, "Modul 1 Strom", "strings", True, **_A),
    Reg("pv2_voltage", 10169, "u16", 0.1, "Modul 2 Spannung", "strings", True, **_V),
    Reg("pv2_current", 10170, "i16", 0.01, "Modul 2 Strom", "strings", True, **_A),
    Reg("pv3_voltage", 10171, "u16", 0.1, "Modul 3 Spannung", "strings", True, **_V),
    Reg("pv3_current", 10172, "i16", 0.01, "Modul 3 Strom", "strings", True, **_A),
    # 10205 war der letzte Kandidat fuer Strang 4 und ist es nicht: ueber 29
    # Messpunkte deckt es sich mit AC-Leistung / Netzspannung auf 0,025 A genau
    # (r = +0,996), waehrend die Korrelation zum PV4-Restwert bei +0,30 liegt.
    Reg("ac_output_current", 10205, "i16", 0.01, "AC-Ausgangsstrom",
        "strings", True, enabled=True, unit="A", device_class="current",
        icon="mdi:transmission-tower-export"),
    # Stufenwert in 1,0-V-Schritten, faellt ueber den Tag mit der Einstrahlung.
    # Deutung weiterhin offen, deshalb ohne Einheit und ohne device_class.
    Reg("r10156", 10156, "u16", 1.0, "Unbekannt Stufenwert 1",
        "strings", False, enabled=True, **_UNKNOWN),

    # --- Leistungsgrenzen, aktiv --------------------------------------------
    Reg("max_charge_power", 10036, "i32", 1.0, "Maximale Ladeleistung",
        "limits", True, icon="mdi:battery-charging-high", **_W),
    Reg("ac_output_limit", 10038, "i32", 1.0, "AC-Ausgangslimit",
        "limits", True, icon="mdi:transmission-tower", **_W),

    # --- Netzqualitaet, deaktiviert -----------------------------------------
    Reg("grid_voltage_a", 10199, "u16", 0.1, "Netzspannung Messpunkt A",
        "grid", False, unit="V", device_class="voltage", icon="mdi:flash-triangle"),
    Reg("grid_voltage_b", 10202, "u16", 0.1, "Netzspannung Messpunkt B",
        "grid", False, unit="V", device_class="voltage", icon="mdi:flash-triangle"),
    Reg("grid_voltage_c", 10224, "u16", 0.1, "Netzspannung Messpunkt C",
        "grid", False, unit="V", device_class="voltage", icon="mdi:flash-triangle"),
    Reg("grid_voltage_d", 10227, "u16", 0.1, "Netzspannung Messpunkt D",
        "grid", False, unit="V", device_class="voltage", icon="mdi:flash-triangle"),
    Reg("grid_frequency", 10213, "u16", 0.01, "Netzfrequenz",
        "grid", True, unit="Hz", device_class="frequency", icon="mdi:sine-wave"),
    Reg("grid_frequency_2", 10238, "u16", 0.01, "Netzfrequenz Zweitmessung",
        "grid", True, unit="Hz", device_class="frequency", icon="mdi:sine-wave"),

    # --- Geraetezeit, deaktiviert -------------------------------------------
    Reg("device_time", 10060, "u32", 1.0, "Geraetezeit", "clock", True,
        device_class="timestamp", state_class=None, icon="mdi:clock-outline"),

    # --- Redundanz zur offiziellen Integration, deaktiviert ------------------
    Reg("pv_power_mb", 10002, "i32", 1.0, "PV-Leistung gesamt (Modbus)",
        "mirror", True, icon="mdi:solar-power", **_W),
    Reg("third_party_pv_mb", 10004, "i32", 1.0, "PV-Leistung Fremdanlage (Modbus)",
        "mirror", True, icon="mdi:solar-power-variant", **_W),
    Reg("battery_power_mb", 10008, "i32", 1.0, "Batterieleistung (Modbus)",
        "mirror", True, icon="mdi:battery-charging", **_W),
    Reg("load_power_mb", 10010, "i32", 1.0, "Hauslast (Modbus)",
        "mirror", True, icon="mdi:home-lightning-bolt", **_W),
    Reg("grid_power_mb", 10012, "i32", 1.0, "Netzleistung (Modbus)",
        "mirror", True, icon="mdi:transmission-tower", **_W),
    Reg("battery_soc_mb", 10014, "u16", 1.0, "Ladezustand (Modbus)",
        "mirror", True, **_PCT),
    # Highbyte von 10041, gegen die HA-Historie auf 11 von 11 Stichproben belegt.
    Reg("battery_soc_bytefield", 10041, "u16_hi", 1.0,
        "Ladezustand Bytefeld (Modbus)", "mirror", True, **_PCT),
    Reg("pv_total_generation_mb", 10018, "u32", 0.1, "PV-Gesamtertrag (Modbus)",
        "mirror", True, icon="mdi:counter", **_KWH),
    Reg("ac_output_power_mb", 10208, "i32", 1.0, "AC-Ausgangsleistung (Modbus)",
        "mirror", True, icon="mdi:transmission-tower-export", **_W),
    Reg("rated_energy_mb", 10250, "u16", 0.1, "Nennkapazitaet (Modbus)",
        "mirror", True, unit="kWh", device_class="energy_storage",
        state_class=None, icon="mdi:battery"),
    Reg("cumulative_charge_mb", 10262, "u32", 0.1, "Ladeenergie kumuliert (Modbus)",
        "mirror", True, icon="mdi:battery-plus", **_KWH),
    Reg("cumulative_discharge_mb", 10264, "u32", 0.1,
        "Entladeenergie kumuliert (Modbus)", "mirror", True,
        icon="mdi:battery-minus", **_KWH),
    Reg("ems_mode_mask", 32774, "u16", 1.0, "EMS-Modusmaske (Modbus)",
        "mirror", True, state_class=None, icon="mdi:format-list-checks"),
    Reg("charging_limit_soc_mb", 60000, "u16", 1.0, "Ladeobergrenze (Modbus)",
        "mirror", True, unit="%", state_class=None, icon="mdi:battery-arrow-up"),
    Reg("discharge_limit_soc_mb", 60001, "u16", 1.0, "Entladegrenze (Modbus)",
        "mirror", True, unit="%", state_class=None, icon="mdi:battery-arrow-down"),
    Reg("backup_reserve_soc_mb", 60002, "u16", 1.0, "Notstromreserve (Modbus)",
        "mirror", True, unit="%", state_class=None, icon="mdi:battery-lock"),
    Reg("backup_soc_enable_mb", 60003, "u16", 1.0, "Notstromreserve aktiv (Modbus)",
        "mirror", True, state_class=None, icon="mdi:battery-lock"),

    # --- Unbestimmt, deaktiviert --------------------------------------------
    # Ohne Einheit, ohne device_class, ohne state_class: eine falsche Einheit
    # wuerde eine Deutung suggerieren, die nicht belegt ist.
    Reg("r10040", 10040, "u16", 1.0, "Unbekannt Batterieblock 1", "unknown", False, **_UNKNOWN),
    Reg("r10042", 10042, "u16", 1.0, "Unbekannt Batterieblock 2", "unknown", False, **_UNKNOWN),
    Reg("r10044", 10044, "u16", 1.0, "Unbekannt Batterieblock 3", "unknown", False, **_UNKNOWN),
    Reg("r10046", 10046, "u16", 1.0, "Unbekannt Batterieblock 4", "unknown", False, **_UNKNOWN),
    Reg("r10074", 10074, "u16", 1.0, "Unbekannt Konfigblock 2", "unknown", False, **_UNKNOWN),
    Reg("r10075", 10075, "u16", 1.0, "Unbekannt Konfigblock 3", "unknown", False, **_UNKNOWN),
    Reg("r10076", 10076, "u16", 1.0, "Unbekannt Konfigblock 4", "unknown", False, **_UNKNOWN),
    Reg("r10079", 10079, "u16", 1.0, "Unbekannter Grenzwert 1", "unknown", False, **_UNKNOWN),
    Reg("r10118", 10118, "u16", 1.0, "Unbekannt Geraeteinfo 1", "unknown", False, **_UNKNOWN),
    Reg("r10124", 10124, "u16", 1.0, "Unbekannt Geraeteinfo 2", "unknown", False, **_UNKNOWN),
    Reg("r10125", 10125, "u16", 1.0, "Unbekannt Geraeteinfo 3", "unknown", False, **_UNKNOWN),
    Reg("r10130", 10130, "u16", 1.0, "Unbekannt Geraeteinfo 4", "unknown", False, **_UNKNOWN),
    Reg("r10133", 10133, "u16", 1.0, "Unbekannt Geraeteinfo 5", "unknown", False, **_UNKNOWN),
    Reg("r10183", 10183, "u16", 1.0, "Unbekannt Einzelregister 1", "unknown", False, **_UNKNOWN),
    Reg("r10187", 10187, "u16", 1.0, "Unbekannt Einzelregister 2", "unknown", False, **_UNKNOWN),
    Reg("r10230", 10230, "u16", 1.0, "Unbekannt AC-Block 1", "unknown", False, **_UNKNOWN),
    Reg("r10234", 10234, "u16", 1.0, "Unbekannt AC-Block 2", "unknown", False, **_UNKNOWN),
    Reg("r10236", 10236, "u16", 1.0, "Unbekannt AC-Block 3", "unknown", False, **_UNKNOWN),
    Reg("r10252", 10252, "u16", 1.0, "Unbekannt Energieblock 1", "unknown", False, **_UNKNOWN),
    Reg("r10256", 10256, "u16", 1.0, "Unbekannt Energieblock 2", "unknown", False, **_UNKNOWN),
)

REGISTERS_BY_KEY: Final[dict[str, Reg]] = {r.key: r for r in REGISTERS}


# ---------------------------------------------------------------------------
# Abgeleitete Groessen je Strang
# ---------------------------------------------------------------------------

# (Schluesselpraefix, Anzeigepraefix, Spannungsregister, Stromregister)
STRINGS: Final[tuple[tuple[str, str, str, str], ...]] = (
    ("pv1", "Modul 1", "pv1_voltage", "pv1_current"),
    ("pv2", "Modul 2", "pv2_voltage", "pv2_current"),
    ("pv3", "Modul 3", "pv3_voltage", "pv3_current"),
)
