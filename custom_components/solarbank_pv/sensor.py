"""Sensoren: Rohregister und abgeleitete Groessen.

Bei vier identischen, koplanaren, gleich ausgerichteten Modulen ist jedes Modul
die Kontrollgruppe fuer die anderen. Deshalb ist das Stromverhaeltnis zum Median
der uebrigen Straenge die Kernkennzahl - es braucht weder Sonnenstandsmodell
noch Wetterprognose, weil sich alle Module dieselbe Wolke teilen.

Zur Benennung: has_entity_name ist bewusst False. Mit True wuerde Home Assistant
den Geraetenamen voranstellen und Entity-IDs der Form
sensor.solarbank_dc_straenge_441_modul_1_leistung erzeugen. Die Anlage fuehrt
aber die Konvention sensor.pv_*, und die hat Vorrang. Der Anzeigename traegt
deshalb selbst das Praefix "PV".
"""
from __future__ import annotations

import statistics
from datetime import datetime, timezone

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from . import SolarbankData
from .const import (
    DOMAIN,
    MIN_CURRENT_FOR_RATIO,
    MIN_CURRENT_FOR_TEMP,
    MIN_POWER_FOR_RATIO,
    MIN_VOLTAGE_FOR_ESTIMATE,
    MODULE_TEMP_COEFF,
    MODULE_VMP_STC,
    PV4_ERROR_CLEAR,
    PV4_ERROR_SHADED,
    REGISTERS,
    REGISTERS_BY_KEY,
    SHADE_ON,
    STRINGS,
    Reg,
)
from .coordinator import SolarbankGroupCoordinator
from .diagnose import build_health_sensors
from .modbus_reader import decode


def display_name(name: str) -> str:
    """Stellt das Anlagenpraefix voran, ohne es zu verdoppeln."""
    return name if name.startswith("PV") else f"PV {name}"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    data: SolarbankData = hass.data[DOMAIN][entry.entry_id]
    entities: list[SensorEntity] = []

    for reg in REGISTERS:
        coordinator = data.coordinators[reg.group]
        cls = DeviceTimeSensor if reg.key == "device_time" else RegisterSensor
        entities.append(cls(coordinator, data, reg))

    strings = data.coordinators["strings"]
    for index, (prefix, label, v_key, i_key) in enumerate(STRINGS):
        entities.append(StringPowerSensor(strings, data, prefix, label, v_key, i_key))
        entities.append(CellTemperatureSensor(strings, data, prefix, label, v_key, i_key))
        entities.append(CurrentRatioSensor(strings, data, prefix, label, i_key))
        # Zusaetzlich zum bestehenden Stromanteil, nicht an dessen Stelle. Der
        # Leistungsanteil ist die einzige Kennzahl, die auch fuer Strang 4
        # exakt ist - erst damit sind alle vier Module vergleichbar.
        entities.append(PowerRatioSensor(strings, data, prefix, label, index))

    entities.append(String4PowerSensor(strings, data))
    entities.append(String4VoltageSensor(strings, data))
    entities.append(String4CurrentSensor(strings, data))
    entities.append(PowerRatioSensor(strings, data, "pv4", "Modul 4", 3))

    entities.extend(build_health_sensors(data))

    async_add_entities(entities)


def string_powers(registers: dict[int, int]) -> tuple[list[float | None], bool]:
    """Leistung aller vier Straenge aus EINEM Registerabbild.

    Index 0..2 sind gemessen (U mal I), Index 3 ist die Differenz zur
    Gesamtleistung. Dass alles aus demselben Abbild kommt, ist die
    Voraussetzung der Rechnung - siehe den Kommentar an BLOCKS["strings"].

    Zweiter Rueckgabewert: ob die Differenz negativ war und auf null geklemmt
    wurde. Eine dauerhaft negative Differenz waere ein Deutungsfehler und darf
    nicht stillschweigend verschwinden.
    """
    gemessen: list[float | None] = []
    for _prefix, _label, v_key, i_key in STRINGS:
        volt = read_value(registers, REGISTERS_BY_KEY[v_key])
        amp = read_value(registers, REGISTERS_BY_KEY[i_key])
        gemessen.append(None if volt is None or amp is None else volt * amp)

    total = read_value(registers, REGISTERS_BY_KEY["pv_power_mb"])
    if total is None or any(p is None for p in gemessen):
        return [*gemessen, None], False

    rest = total - sum(p for p in gemessen if p is not None)
    return [*gemessen, max(rest, 0.0)], rest < 0


def other_median(werte: list[float | None], index: int) -> float | None:
    """Median der uebrigen Straenge. None, sobald einer davon fehlt.

    Bewusst streng: ein Median ueber zwei statt drei Nachbarn waere eine andere
    Kennzahl und wuerde im Verlauf unbemerkt neben der bisherigen stehen.
    """
    andere = [w for i, w in enumerate(werte) if i != index]
    if any(w is None for w in andere):
        return None
    return statistics.median([w for w in andere if w is not None])


def read_value(registers: dict[int, int], reg: Reg) -> float | None:
    """Dekodiert ein Register aus dem Rohwoerter-Abbild der Gruppe."""
    words: list[int] = []
    for offset in range(reg.words):
        word = registers.get(reg.address + offset)
        if word is None:
            return None
        words.append(word)
    return decode(reg.kind, words) * reg.scale


class SolarbankEntity(CoordinatorEntity[SolarbankGroupCoordinator]):
    """Gemeinsame Basis: Geraetezuordnung und stabile Identitaet."""

    _attr_has_entity_name = False

    def __init__(
        self,
        coordinator: SolarbankGroupCoordinator,
        data: SolarbankData,
        unique_suffix: str,
        name: str,
    ) -> None:
        super().__init__(coordinator)
        self._attr_device_info = data.device_info
        # Bewusst aus Adresse beziehungsweise Schluessel und Seriennummernkuerzel
        # gebildet, nicht aus der entry_id: so ueberleben Verlaufsdaten auch ein
        # Entfernen und Neuanlegen des Config-Entries. Diese Kennung wird nie
        # geaendert, der Anzeigename darf jederzeit verbessert werden.
        self._attr_unique_id = f"solarbank_{data.serial_suffix}_{unique_suffix}"
        self._attr_name = name
        # Muss ausdruecklich gesetzt werden. Home Assistant stellt bei der
        # ID-Bildung sonst den Geraetenamen voran und erzeugt
        # sensor.solarbank_dc_straenge_441_pv_modul_1_leistung - auch bei
        # has_entity_name = False. Die Anlage fuehrt aber sensor.pv_*.
        self.entity_id = f"sensor.{slugify(name)}"


class RegisterSensor(SolarbankEntity, SensorEntity):
    """Ein Rohregister, unveraendert bis auf die Skalierung."""

    def __init__(
        self,
        coordinator: SolarbankGroupCoordinator,
        data: SolarbankData,
        reg: Reg,
    ) -> None:
        super().__init__(coordinator, data, f"r{reg.address}", display_name(reg.name))
        self._reg = reg
        self._attr_native_unit_of_measurement = reg.unit
        self._attr_device_class = reg.device_class
        self._attr_state_class = reg.state_class
        self._attr_icon = reg.icon
        self._attr_entity_registry_enabled_default = reg.default_enabled

    @property
    def native_value(self) -> float | None:
        if not self.coordinator.data:
            return None
        value = read_value(self.coordinator.data, self._reg)
        return None if value is None else round(value, 3)

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        return {
            "modbus_address": self._reg.address,
            "modbus_function": 4,
            "modbus_datatype": self._reg.kind,
            "modbus_scale": self._reg.scale,
            "deutung_sicher": self._reg.certain,
        }


class DeviceTimeSensor(RegisterSensor):
    """Geraetezeit als Zeitstempel statt als Sekundenzahl."""

    @property
    def native_value(self) -> datetime | None:  # type: ignore[override]
        if not self.coordinator.data:
            return None
        raw = read_value(self.coordinator.data, self._reg)
        if raw is None or raw <= 0:
            return None
        return datetime.fromtimestamp(int(raw), tz=timezone.utc)


class StringDerivedEntity(SolarbankEntity, SensorEntity):
    """Basis fuer die aus Spannung und Strom berechneten Groessen."""

    def __init__(
        self,
        coordinator: SolarbankGroupCoordinator,
        data: SolarbankData,
        unique_suffix: str,
        name: str,
    ) -> None:
        super().__init__(coordinator, data, unique_suffix, name)
        self._attr_entity_registry_enabled_default = True

    def _reg_value(self, key: str) -> float | None:
        if not self.coordinator.data:
            return None
        return read_value(self.coordinator.data, REGISTERS_BY_KEY[key])


class StringPowerSensor(StringDerivedEntity):
    """Leistung eines Strangs, Spannung mal Strom."""

    _attr_native_unit_of_measurement = "W"
    _attr_device_class = "power"
    _attr_state_class = "measurement"
    _attr_icon = "mdi:solar-panel"

    def __init__(self, coordinator, data, prefix, label, v_key, i_key) -> None:
        super().__init__(
            coordinator, data, f"{prefix}_power", display_name(f"{label} Leistung")
        )
        self._v_key = v_key
        self._i_key = i_key

    @property
    def native_value(self) -> float | None:
        volt = self._reg_value(self._v_key)
        amp = self._reg_value(self._i_key)
        if volt is None or amp is None:
            return None
        return round(volt * amp, 1)


class CellTemperatureSensor(StringDerivedEntity):
    """Zelltemperatur, aus der Spannung ueber Vmp(T) zurueckgerechnet.

    Zweiter, physikalisch unabhaengiger Verschattungsnachweis - ein verschattetes
    Modul heizt sich nicht auf - und nebenbei eine Ueberhitzungsueberwachung ohne
    einen einzigen Fuehler.

    Gueltig nur unter Last: ohne nennenswerten Strom liegt der Arbeitspunkt
    Richtung Leerlauf, und eine Rueckrechnung ueber Vmp waere sinnlos. Dann wird
    None geliefert statt einer erfundenen Zahl.
    """

    _attr_native_unit_of_measurement = "°C"
    _attr_device_class = "temperature"
    _attr_state_class = "measurement"
    _attr_icon = "mdi:thermometer"

    def __init__(self, coordinator, data, prefix, label, v_key, i_key) -> None:
        super().__init__(
            coordinator, data, f"{prefix}_cell_temp", display_name(f"{label} Zelltemperatur")
        )
        self._v_key = v_key
        self._i_key = i_key

    @property
    def native_value(self) -> float | None:
        volt = self._reg_value(self._v_key)
        amp = self._reg_value(self._i_key)
        if volt is None or amp is None or amp < MIN_CURRENT_FOR_TEMP:
            return None
        return round(25.0 + (1.0 - volt / MODULE_VMP_STC) / MODULE_TEMP_COEFF, 1)

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        return {
            "modbus_address": REGISTERS_BY_KEY[self._v_key].address,
            "modbus_function": 4,
            "modbus_datatype": "berechnet",
            "modbus_scale": 1,
            "deutung_sicher": False,
            "formel": "25 + (1 - U / 33.18) / 0.0025",
            "gueltig_ab_strom": MIN_CURRENT_FOR_TEMP,
        }


class CurrentRatioSensor(StringDerivedEntity):
    """Strom dieses Strangs im Verhaeltnis zum Median der uebrigen.

    Die Kernkennzahl. Unabhaengig von Tageszeit, Wetter und Jahreszeit, weil
    sich alle Module dieselbe Einstrahlung teilen. Jede Abweichung ist
    Verschattung, Verschmutzung oder Defekt.
    """

    _attr_native_unit_of_measurement = "%"
    _attr_state_class = "measurement"
    _attr_icon = "mdi:scale-balance"

    def __init__(self, coordinator, data, prefix, label, i_key) -> None:
        super().__init__(
            coordinator, data, f"{prefix}_current_ratio", display_name(f"{label} Stromanteil")
        )
        self._i_key = i_key
        self._other_keys = [k for _, _, _, k in STRINGS if k != i_key]

    @property
    def native_value(self) -> float | None:
        own = self._reg_value(self._i_key)
        if own is None:
            return None
        others = [v for v in (self._reg_value(k) for k in self._other_keys) if v is not None]
        if not others:
            return None
        reference = statistics.median(others)
        # Nachts liefern alle Straenge null. Ein Verhaeltnis waere dann entweder
        # eine Division durch null oder eine Scheinaussage.
        if reference < MIN_CURRENT_FOR_RATIO:
            return None
        return round(own / reference * 100.0, 1)

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        return {
            "modbus_address": REGISTERS_BY_KEY[self._i_key].address,
            "modbus_function": 4,
            "modbus_datatype": "berechnet",
            "modbus_scale": 1,
            "deutung_sicher": True,
            "referenz": "Median der uebrigen Straenge",
        }


class String4PowerSensor(StringDerivedEntity):
    """Leistung von Strang 4 als Differenz zur Gesamtleistung.

    Strang 4 hat kein eigenes Register. Der Adressraum wurde vollstaendig
    geprueft (Scan 0-65535, FC01-FC04); der letzte Kandidat 10205 erwies sich
    als AC-Ausgangsstrom. Damit bleibt nur die Differenz.

    Das ist keine Notloesung, sondern eine exakte Rechnung: 10002 ist die
    Summe ueber alle vier Tracker, die drei uebrigen sind einzeln gemessen.
    Der Fehler ist die Summe der Rundungsfehler der drei Einzelstraenge,
    nicht ein Modellfehler. Ohne diesen Sensor blieben rund 25 Prozent der
    Anlage unsichtbar - gemessen am 13.08.: 1270 W gesamt gegen 925 W aus
    den drei bekannten Straengen.

    Voraussetzung ist, dass 10002 in derselben Abfrage gelesen wird wie die
    Strangregister; siehe den Kommentar an BLOCKS["strings"] in const.py.
    """

    _attr_native_unit_of_measurement = "W"
    _attr_device_class = "power"
    _attr_state_class = "measurement"
    _attr_icon = "mdi:solar-panel"

    def __init__(self, coordinator, data) -> None:
        super().__init__(
            coordinator, data, "pv4_power", display_name("Modul 4 Leistung")
        )
        self._clamped = False

    @property
    def native_value(self) -> float | None:
        if not self.coordinator.data:
            return None
        # Nachts sind alle Summanden null und die Differenz besteht nur aus
        # Rundungsrauschen. Ein kleiner negativer Wert ist dann kein Defekt.
        # Er wird auf null geklemmt, aber im Attribut kenntlich gemacht, damit
        # eine dauerhaft negative Differenz als Hinweis auf einen Deutungs-
        # fehler sichtbar bleibt statt stillschweigend verschwiegen zu werden.
        werte, geklemmt = string_powers(self.coordinator.data)
        self._clamped = geklemmt
        return None if werte[3] is None else round(werte[3], 1)

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        return {
            "modbus_address": "10002 minus 10167..10172",
            "modbus_function": 4,
            "modbus_datatype": "berechnet",
            "modbus_scale": 1,
            # Die Rechnung ist sicher, die Zuordnung zu einem physischen Modul
            # nicht: welches der vier Module Strang 4 ist, steht nicht fest.
            "deutung_sicher": False,
            "methode": "Gesamtleistung minus Summe der drei gemessenen Straenge",
            "auf_null_geklemmt": self._clamped,
        }


class PowerRatioSensor(StringDerivedEntity):
    """Leistung dieses Strangs im Verhaeltnis zum Median der uebrigen drei.

    Die eine Kennzahl, die fuer ALLE VIER Straenge gilt. Der bestehende
    Stromanteil gibt es nur fuer die drei gemessenen Straenge, weil Strang 4
    keinen gemessenen Strom hat - und ein aus der Schaetzspannung gerechneter
    Stromanteil waere ausgerechnet bei Verschattung um rund 10 % zu hoch
    (siehe PV4_ERROR_SHADED in const.py). Die Leistung dagegen ist fuer alle
    vier exakt, also ist es auch dieses Verhaeltnis.

    Dass der Leistungsanteil den Stromanteil als Verschattungsmass ersetzen
    kann, ist an den drei gemessenen Straengen geprueft: ueber 3075 Messpunkte
    des 12.08. faellen beide Masse in 99,22 % der Faelle dasselbe Urteil
    (tools/kreuzvalidierung_pv4.py).
    """

    _attr_native_unit_of_measurement = "%"
    _attr_state_class = "measurement"
    _attr_icon = "mdi:scale-balance"

    def __init__(self, coordinator, data, prefix, label, index: int) -> None:
        super().__init__(
            coordinator, data, f"{prefix}_power_ratio",
            display_name(f"{label} Leistungsanteil"),
        )
        self._index = index

    def _ratio(self) -> float | None:
        if not self.coordinator.data:
            return None
        werte, _ = string_powers(self.coordinator.data)
        eigen = werte[self._index]
        referenz = other_median(werte, self._index)
        if eigen is None or referenz is None:
            return None
        # Nachts liefern alle Straenge null. Ein Verhaeltnis waere dann
        # entweder eine Division durch null oder eine Scheinaussage.
        if referenz < MIN_POWER_FOR_RATIO:
            return None
        return eigen / referenz

    @property
    def native_value(self) -> float | None:
        ratio = self._ratio()
        return None if ratio is None else round(ratio * 100.0, 1)

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        exakt = self._index < 3
        return {
            "modbus_datatype": "berechnet",
            "modbus_function": 4,
            "modbus_scale": 1,
            # Fuer alle vier Straenge exakt: die Leistung von Strang 4 ist eine
            # Differenz zweier Messgroessen, keine Schaetzung.
            "deutung_sicher": True,
            "referenz": "Median der uebrigen drei Straenge",
            "mindestleistung_referenz_w": MIN_POWER_FOR_RATIO,
            "leistung_gemessen": exakt,
        }


class String4EstimateEntity(StringDerivedEntity):
    """Basis der beiden geschaetzten Groessen von Strang 4.

    Beide teilen dieselbe Annahme und muessen sie deshalb identisch
    ausweisen. Die Guete haengt davon ab, ob Strang 4 gerade verschattet ist;
    der Fehler ist dann nicht zufaellig, sondern gerichtet.
    """

    def _powers(self) -> tuple[list[float | None], float | None]:
        """Alle vier Leistungen und die geschaetzte Spannung von Strang 4."""
        if not self.coordinator.data:
            return [None] * 4, None
        werte, _ = string_powers(self.coordinator.data)
        spannungen = [self._reg_value(v_key) for _, _, v_key, _ in STRINGS]
        if any(v is None for v in spannungen):
            return werte, None
        return werte, statistics.median([v for v in spannungen if v is not None])

    def _shaded(self) -> bool | None:
        """Steht Strang 4 im Schatten? Ueber den Leistungsanteil, nicht den Strom."""
        if not self.coordinator.data:
            return None
        werte, _ = string_powers(self.coordinator.data)
        eigen = werte[3]
        referenz = other_median(werte, 3)
        if eigen is None or referenz is None or referenz < MIN_POWER_FOR_RATIO:
            return None
        return eigen / referenz < SHADE_ON

    def _estimate_attributes(self) -> dict[str, object]:
        schatten = self._shaded()
        return {
            "modbus_address": "geschaetzt aus 10167, 10169, 10171",
            "modbus_function": 4,
            "modbus_datatype": "geschaetzt",
            "modbus_scale": 1,
            # Der wichtigste Eintrag: dieser Wert ist NICHT gemessen.
            "deutung_sicher": False,
            "gemessen": False,
            "methode": "geschaetzt, V4 = Median(V1..V3), I4 = P4 / V4",
            "annahme": (
                "vier identische koplanare Module mit je eigenem MPP-Tracker "
                "fuehren dieselbe MPP-Spannung"
            ),
            "verschattung_beeintraechtigt": schatten,
            # Beziffert, nicht behauptet: Kreuzvalidierung ueber 1025
            # Messpunkte unter Last, tools/kreuzvalidierung_pv4.py.
            "schaetzfehler_prozent": (
                PV4_ERROR_SHADED if schatten else PV4_ERROR_CLEAR
            ),
            "belegstelle": "tools/kreuzvalidierung_pv4.py, docs/DIAGNOSE.md",
        }


class String4VoltageSensor(String4EstimateEntity):
    """Geschaetzte Spannung von Strang 4 als Median der drei gemessenen.

    Unverschattet traegt die Annahme gut: der Median der uebrigen weicht im
    Median um 0,48 % von der Messung ab (p95 5,54 %). Steht der Strang selbst
    im Schatten, wird seine Spannung systematisch um rund 9,5 % zu NIEDRIG
    geschaetzt - ein verschattetes Modul faehrt hoeher, weil es kuehler ist.

    Der Wert wird trotzdem geliefert und nicht auf unknown gesetzt: ein
    gerichteter Fehler bekannter Groesse ist auswertbar, eine Luecke im Graphen
    ausgerechnet zur Verschattungszeit nicht. Die Beeintraechtigung steht im
    Attribut verschattung_beeintraechtigt und wird im Dashboard angezeigt.
    """

    _attr_native_unit_of_measurement = "V"
    _attr_device_class = "voltage"
    _attr_state_class = "measurement"
    # Bewusst ein anderes Icon als die gemessenen Straenge (mdi:solar-panel):
    # die Schaetzung soll sich schon in der Liste unterscheiden.
    _attr_icon = "mdi:calculator-variant-outline"

    def __init__(self, coordinator, data) -> None:
        super().__init__(
            coordinator, data, "pv4_voltage_est",
            display_name("Modul 4 Spannung (geschaetzt)"),
        )

    @property
    def native_value(self) -> float | None:
        _werte, spannung = self._powers()
        return None if spannung is None else round(spannung, 1)

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        return self._estimate_attributes()


class String4CurrentSensor(String4EstimateEntity):
    """Geschaetzter Strom von Strang 4 aus der exakten Leistung.

    I4 = P4 / V4. Der Zaehler ist exakt, der Nenner geschaetzt - der relative
    Fehler des Stroms ist deshalb der Kehrwert des Spannungsfehlers und zeigt
    in die entgegengesetzte Richtung: bei Verschattung rund 10,5 % zu HOCH.

    Genau deshalb gibt es fuer Strang 4 bewusst KEINEN Stromanteil. Er wuerde
    die Verschattung um denselben Faktor beschoenigen und sie damit zu spaet
    melden - blinder Fleck genau dort, wo die Kennzahl gebraucht wird. Die
    Verschattung von Strang 4 laeuft ueber den Leistungsanteil.
    """

    _attr_native_unit_of_measurement = "A"
    _attr_device_class = "current"
    _attr_state_class = "measurement"
    _attr_icon = "mdi:calculator-variant-outline"

    def __init__(self, coordinator, data) -> None:
        super().__init__(
            coordinator, data, "pv4_current_est",
            display_name("Modul 4 Strom (geschaetzt)"),
        )

    @property
    def native_value(self) -> float | None:
        werte, spannung = self._powers()
        leistung = werte[3]
        if leistung is None or spannung is None:
            return None
        if spannung < MIN_VOLTAGE_FOR_ESTIMATE:
            # Unter dieser Spannung ist die Division numerisch wertlos.
            return None
        return round(leistung / spannung, 2)

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        attrs = self._estimate_attributes()
        attrs["kein_stromanteil_weil"] = (
            "Schaetzfehler zeigt bei Verschattung nach oben und wuerde die "
            "Verschattung verdecken; stattdessen Leistungsanteil verwenden"
        )
        return attrs
