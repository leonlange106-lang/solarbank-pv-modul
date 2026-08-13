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

# Dasselbe fuer das Leistungsverhaeltnis. 15 W entsprechen bei rund 30 V
# Strangspannung genau den 0,5 A von MIN_CURRENT_FOR_RATIO - die beiden
# Schranken schneiden denselben Betriebsbereich ab, damit Strom- und
# Leistungsanteil dieselben Messpunkte bewerten.
MIN_POWER_FOR_RATIO: Final = 15.0  # W

# Untergrenze fuer die geschaetzte Spannung von Strang 4. Darunter waere die
# Division P4/V4 numerisch wertlos.
MIN_VOLTAGE_FOR_ESTIMATE: Final = 5.0  # V

# --- Unverschattete Referenz (theoretische Leistung) ----------------------
# Als Referenz gilt das MITTEL aller Straenge, die nah am besten liegen, nicht
# der beste allein. Grund: das Maximum von vier verrauschten Werten liegt
# systematisch darueber. Am Tageslauf des 12.08. an den Punkten, wo alle vier
# eng beieinander liegen, ueberschaetzt das schlichte Maximum das Mittel im
# Median um 2,57 % (p90 5,16 %) - mal vier ist das der Fehler in W.
#
# Liegt nur ein Strang nah am besten, faellt das Mittel auf genau diesen einen
# zurueck. Das ist der wichtige Fall: wenn der Schatten drei Straenge deckt,
# darf die Referenz nicht auf einen verschatteten Nachbarn heruntergezogen
# werden. Deshalb NICHT der zweithoechste - der unterschaetzt genau dann, und
# damit in Richtung "kein Problem".
REFERENZ_NAHE_ANTEIL: Final = 0.90

# Nennleistung eines Moduls bei STC, aus dem Datenblatt: 33,18 V x 15,07 A.
# Keine gelernte Groesse.
MODULE_IMP_STC: Final = 15.07       # A bei 25 Grad C
MODULE_WP: Final = MODULE_VMP_STC * MODULE_IMP_STC   # rund 500 W

# --- Blindfleck: alle vier gleichzeitig verschattet ------------------------
# Liegen alle vier Straenge eng beieinander, ist entweder NICHTS verschattet
# oder ALLES. Das Verfahren misst nur Unterschiede zwischen den Straengen und
# kann die beiden Faelle aus sich heraus nicht trennen. Getrennt wird ueber die
# absolute Hoehe gegen die geometrische Klarhimmelerwartung.
#
# Bezug ist das Attribut `poa_w_m2` von sensor.pv_lernen_klarhimmelleistung -
# reine Geometrie ohne gelernte Groesse. Der Zustand des Sensors selbst waere
# unbrauchbar, er enthaelt den gelernten Systemgain.
KLARHIMMEL_ENTITY: Final = "sensor.pv_lernen_klarhimmelleistung"
KLARHIMMEL_ATTRIBUT: Final = "poa_w_m2"

# Unterhalb dieses Anteils der Klarhimmelerwartung gilt die Anlage als "tief".
# 0.50 ist bewusst grosszuegig: Temperaturverluste, Einfallswinkel und
# Verschmutzung druecken den realen Ertrag auch bei klarem Himmel deutlich
# unter die STC-Erwartung. Erst darunter ist Bewoelkung oder Totalverschattung
# die plausiblere Erklaerung.
KLARHIMMEL_BLIND_ANTEIL: Final = 0.50

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
        # Ab 12.08.2026 alle Gruppen aktiv: die unbestimmten Register sollen im
        # Recorder mitlaufen, damit sich ihre Funktion aus dem Langzeitverlauf
        # erschliessen laesst. Genau so wurde 10254/10255 identifiziert - erst
        # der Vergleich von Lade- und Entladeregime hat es entschieden.
        # Die Deutungssicherheit steckt weiterhin im certain-Flag je Reg, nicht
        # in der Sichtbarkeit.
        Group("grid", "Netzqualitaet", 60, True),
        Group("clock", "Geraetezeit", 3600, True),
        Group("mirror", "Redundanz zur offiziellen Integration", 30, True),
        Group("unknown", "Unbestimmt", 300, True),
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
    #
    # 10002 wird hier ein zweites Mal gelesen, obwohl es auch in "mirror" steht.
    # Grund: Strang 4 hat kein eigenes Register und wird als Differenz aus der
    # Gesamtleistung und den drei gemessenen Straengen gebildet. Kaeme die
    # Gesamtleistung aus der mirror-Gruppe, laegen beide Seiten der Subtraktion
    # in verschiedenen Abfragezyklen - bei ziehenden Wolken entstuenden daraus
    # Differenzen von mehreren hundert Watt aus reinem Zeitversatz. Eine
    # zusaetzliche Anfrage je 30 s ist der Preis fuer Zeitgleichheit.
    "strings": (Block(10144, 32), Block(10205, 1), Block(10002, 4)),
    "limits": (Block(10036, 2), Block(10038, 2)),
    "grid": (Block(10199, 1), Block(10202, 1), Block(10208, 32)),
    "clock": (Block(10060, 2, proven=False),),
    "mirror": (
        # count=4 statt 2: 10004/10005 (Fremdanlage) liegt im selben Block und
        # blieb sonst ungelesen, wodurch die Entity dauerhaft unknown zeigte.
        # 10002..10005 ist als gueltige Start/Count-Kombination geprueft.
        Block(10002, 4),
        Block(10008, 2),
        Block(10010, 2),
        Block(10012, 2),
        Block(10014, 1),
        Block(10018, 2, proven=False),
        Block(10040, 32),
        Block(10208, 32),
        # 10250:8 deckt 10250-10257 ab und liefert damit auch das INT32-Paar
        # 10254/10255 in derselben Anfrage. Belegt durch 729 fehlerfreie
        # Messpunkte der Laeufe vom 11. und 12.08. (tools/pv4_evening.py:57).
        Block(10250, 8),
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
    # Geraetetemperatur. Ueber zwei Tage geprueft und als sehr wahrscheinlich
    # eingestuft; die fruehere Spannungsthese ist widerlegt (16 Prozentpunkte
    # SOC-Abfall ohne jede Regung des Registers).
    #
    # Das Register ist das Highbyte von 10252 mal 10 - belegt an 311 von 312
    # Messpunkten. Daraus folgt zwingend die Stufung: als Highbyte kann es nur
    # in Zehnerschritten springen, was bei /10 genau 1-Grad-Schritte ergibt.
    # Die vermeintlich stoerende Grobstufigkeit ist also kein Argument gegen
    # die Temperaturdeutung, sondern ihre Bestaetigung.
    #
    # certain bleibt False: "sehr wahrscheinlich" ist nicht "gegen App oder
    # Physik verifiziert". Einheit und device_class sind dennoch gesetzt, weil
    # eine Temperatur ohne Einheit im Verlauf nicht lesbar ist - die Unsicher-
    # heit steht im Attribut deutung_sicher, wo sie hingehoert.
    # Der Schluessel bleibt r10156: er bildet die unique_id. Ihn auf einen
    # sprechenden Namen zu heben wuerde eine neue Entity erzeugen und den
    # bisherigen Verlauf abschneiden. Identitaet und Bezeichnung sind getrennt,
    # genau dafuer.
    Reg("r10156", 10156, "u16", 0.1, "Geraetetemperatur",
        "strings", False, enabled=True, unit="°C",
        device_class="temperature", icon="mdi:thermometer"),

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
    # u32 ueber 10250/10251, nicht u16: das Highword 10250 steht konstant auf 0,
    # der Wert steckt im Lowword. Als u16 gelesen lieferte der Sensor deshalb
    # dauerhaft 0,0 kWh. Rohblock vom 13.08.: [0, 51, ...] -> 51 * 0,1 = 5,1 kWh.
    Reg("rated_energy_mb", 10250, "u32", 0.1, "Nennkapazitaet (Modbus)",
        "mirror", True, unit="kWh", device_class="energy_storage",
        state_class=None, icon="mdi:battery"),
    # 10254/10255 ist die Batterieleistung mit umgekehrtem Vorzeichen zu
    # 10008/10009: positiv = laden. Belegt ueber beide Betriebsregime -
    # 11.08. abends beim Entladen -550..0 W, 12.08. morgens beim Laden
    # +200..+1120 W gegen eine Batterieleistung von -1170..-270 W.
    # 10254 ist das Highword und steht bei positiven Werten konstant auf 0,
    # bei negativen auf 0xFFFF; der fruehere Befund "springt zwischen 0 und
    # 65535" war genau dieser Vorzeichenwechsel.
    Reg("battery_charge_power_mb", 10254, "i32", 1.0,
        "Batterieladeleistung (Modbus)",
        "mirror", True, icon="mdi:battery-sync", **_W),
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


# ---------------------------------------------------------------------------
# Guete der Schaetzung fuer Strang 4
#
# Strang 4 hat kein eigenes Registerpaar. Seine LEISTUNG ist exakt - sie ist die
# Differenz aus der Gesamtleistung und den drei gemessenen Straengen. Spannung
# und Strom einzeln sind es nicht: aus einem Produkt lassen sich zwei Faktoren
# nicht eindeutig zurueckgewinnen. Es braucht die Annahme, dass alle vier
# koplanaren Module dieselbe MPP-Spannung fuehren, also V4 = Median(V1..V3).
#
# Diese Annahme ist beziffert, nicht behauptet. tools/kreuzvalidierung_pv4.py
# schaetzt fuer jeden der drei bekannten Straenge die Spannung aus den beiden
# uebrigen und haelt sie gegen die Messung. Grundlage sind die 1025 Messpunkte
# unter Last des Tageslaufs vom 12.08. (tools/rohdaten/pv4_tag.jsonl):
#
#   unverschattet                  Median 0,48 %   p95  5,54 %   Bias +0,04 %
#   Zielstrang selbst verschattet  Median 9,56 %   p95 12,89 %   Bias -9,47 %
#
# Der zweite Fall ist der gefaehrliche und trifft PV4 genau dann, wenn PV4
# selbst im Schatten steht: die Spannung wird systematisch zu NIEDRIG und der
# daraus gerechnete Strom um denselben Faktor zu HOCH geschaetzt. Ein Median
# ueber drei Nachbarn hilft dagegen nicht - er verwirft einen verschatteten
# Nachbarn, aber die Verschattung des Zielstrangs bleibt unsichtbar.
#
# Konsequenz im Code: Die Verschattungserkennung von Strang 4 laeuft ueber den
# LEISTUNGSANTEIL, der ohne Spannungsannahme auskommt und damit exakt ist.
# Dass beide Masse gleichwertig sind, ist an PV1-3 geprueft: in 99,22 % von
# 3075 Messpunkten faellen Strom- und Leistungsanteil dasselbe Urteil.
PV4_ERROR_CLEAR: Final = 1.0     # %, unverschattet
PV4_ERROR_SHADED: Final = 10.0   # %, waehrend Strang 4 verschattet ist

# Wie viele aufeinanderfolgende Messpunkte die Verschattung von Strang 4
# bestaetigen muessen, bevor der Binaersensor umschaltet.
#
# Warum nur Strang 4 das braucht: Die Gesamtleistung aus 10002/10003 kommt in
# 10-W-Stufen. P4 ist eine Differenz gegen diesen groben Wert und erbt dessen
# Quantisierungsrauschen, waehrend P1..P3 aus feinem U mal I entstehen. Bei
# einer Referenz um 100 W ist eine 10-W-Stufe ein Sprung von 10 Prozentpunkten
# im Verhaeltnis - genug, um das Hysteresefenster 0,60/0,70 wiederholt zu
# durchschlagen, ohne dass sich am Schatten etwas aendert.
#
# Die Schwellen bleiben identisch zu PV1-3, nur die Bestaetigung kommt hinzu.
# Am Tageslauf des 12.08. gemessen (tools/kreuzvalidierung_pv4.py-Datensatz):
# ohne Bestaetigung 42 Flanken, mit zwei Messpunkten 20 - das ist genau das
# Niveau von PV1 (20), PV2 (22) und PV3 (11). Die verschattete Zeit aendert
# sich dabei von 24,1 % auf 24,0 %, es verschwindet also Rauschen und keine
# Substanz. Ohne diese Regel waere Strang 4 NICHT mit den uebrigen
# vergleichbar - die Bestaetigung stellt die Vergleichbarkeit her, statt sie
# aufzuheben.
PV4_SHADE_CONFIRM: Final = 2


# ---------------------------------------------------------------------------
# Register, die eine Gruppe ueber ihre eigenen Entities hinaus braucht.
#
# Ohne diese Liste wuerde die Gesundheitspruefung einen Blockausfall uebersehen,
# der keine eigene Entity betrifft, aber eine abgeleitete Groesse still auf
# unknown setzt - genau die Fehlerklasse, um die es geht.
# ---------------------------------------------------------------------------

EXTRA_REQUIRED: Final[dict[str, tuple[int, ...]]] = {
    # Strang 4 ist die Differenz zur Gesamtleistung. 10002/10003 muss im selben
    # Zyklus wie die Strangregister vorliegen, sonst faellt sensor.pv_modul_4_*
    # aus, ohne dass eine einzige Entity der Gruppe unavailable wuerde.
    "strings": (10002, 10003),
}


def required_addresses(group_key: str) -> frozenset[int]:
    """Registeradressen, ohne die die Gruppe unvollstaendig ist.

    Bewusst nicht alle Adressen der Lesebloecke: ein Block deckt bis zu 32
    Register ab, von denen die meisten nie gedeutet wurden. Gefordert ist nur,
    was tatsaechlich in einen Wert eingeht.
    """
    adressen: set[int] = set(EXTRA_REQUIRED.get(group_key, ()))
    for reg in REGISTERS:
        if reg.group != group_key:
            continue
        adressen.update(range(reg.address, reg.address + reg.words))
    return frozenset(adressen)
