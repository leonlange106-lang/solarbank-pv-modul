"""Ein Gesundheitssensor je Registergruppe.

Warum das in der Integration steckt und nicht in einem Template:

Der gefaehrlichste Ausfall dieser Integration ist der stille Blockausfall. Ein
Leseblock, den das Geraet dreimal mit Ausnahme 2 ablehnt, wird nach
MAX_BLOCK_FAILURES aus der Abfrage genommen (siehe coordinator.py). Die Gruppe
liefert danach weiterhin Daten - nur ohne die Register dieses Blocks. Kein
Coordinator meldet einen Fehler, keine Entity wird unavailable, die betroffenen
Werte gehen lautlos auf unknown oder bleiben bei einem alten Wert stehen.

Von Home Assistant aus ist dieser Zustand nicht erkennbar: dropped_blocks lebt
in einem Python-Objekt, das kein Template erreicht. Deshalb wird er hier nach
aussen gereicht.

Arbeitsteilung: Diese Sensoren melden ausschliesslich FAKTEN - wie viele Bloecke
verworfen sind, welche Register fehlen, wann zuletzt erfolgreich gelesen wurde.
Die BEWERTUNG dieser Fakten (ab wann Warnung, ab wann Stoerung) liegt in
packages/solarbank_diagnose.yaml auf der Home-Assistant-Seite. Dort laesst sich
eine Schwelle ohne Neustart aendern; hier nicht.
"""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
# EntityCategory kommt aus homeassistant.const, nicht aus helpers.entity. Der
# Reexport dort ist seit Jahren veraltet und in neueren Kernen entfernt.
from homeassistant.const import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from .const import DOMAIN, required_addresses
from .coordinator import SolarbankGroupCoordinator

ZUSTAND_OK = "ok"
ZUSTAND_TEIL = "teilausfall"
ZUSTAND_AUSFALL = "ausfall"


class GroupHealthSensor(CoordinatorEntity[SolarbankGroupCoordinator], SensorEntity):
    """Zustand einer Registergruppe: ok, teilausfall oder ausfall."""

    _attr_has_entity_name = False
    _attr_icon = "mdi:heart-pulse"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    # Ein Zustandswort, keine Messreihe. Eine state_class waere hier falsch.
    _attr_state_class = None
    _attr_device_class = None

    def __init__(self, coordinator: SolarbankGroupCoordinator, data) -> None:
        super().__init__(coordinator)
        gruppe = coordinator.group
        self._attr_device_info = data.device_info
        self._attr_unique_id = f"solarbank_{data.serial_suffix}_health_{gruppe.key}"
        self._attr_name = f"Solarbank Diagnose Gruppe {gruppe.name}"
        # Die Entity-ID traegt bewusst den GRUPPENSCHLUESSEL, nicht den
        # Anzeigenamen: "mirror" bleibt kurz und stabil, waehrend aus
        # "Redundanz zur offiziellen Integration" eine unbrauchbar lange ID
        # wuerde, die sich zudem mit jeder Umbenennung aendern koennte.
        # Identitaet und Bezeichnung sind getrennt - wie ueberall hier.
        self.entity_id = f"sensor.solarbank_diagnose_gruppe_{slugify(gruppe.key)}"
        self._erwartet = len(required_addresses(gruppe.key))

    @property
    def available(self) -> bool:
        """Immer verfuegbar, auch wenn die Gruppe nicht liest.

        CoordinatorEntity setzt available normalerweise auf
        coordinator.last_update_success. Genau das waere hier fatal: bei einem
        Totalausfall wuerde ausgerechnet der Sensor unavailable, der den
        Ausfall melden soll, und das Dashboard zeigte eine Luecke statt eines
        Alarms.
        """
        return True

    @property
    def native_value(self) -> str:
        if not self.coordinator.last_update_success:
            return ZUSTAND_AUSFALL
        if self.coordinator.dropped_blocks or self.coordinator.missing_addresses:
            return ZUSTAND_TEIL
        return ZUSTAND_OK

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        koord = self.coordinator
        gelesen = len(koord.data or {})
        fehlend = koord.missing_addresses
        zeit = koord.last_success_time
        return {
            "gruppe": koord.group.key,
            "intervall_s": koord.group.interval,
            "bloecke_gesamt": koord.block_count,
            "bloecke_verworfen": koord.dropped_labels,
            "anzahl_verworfen": len(koord.dropped_blocks),
            # Die eigentliche Diagnose: welches Register fehlt, nicht nur dass
            # eines fehlt. 10004 statt "irgendwas in der mirror-Gruppe".
            "register_gefordert": self._erwartet,
            "register_fehlend": fehlend,
            "anzahl_fehlend": len(fehlend),
            "woerter_gelesen": gelesen,
            "letzte_aktualisierung": zeit.isoformat() if zeit else None,
            "letzter_fehler": koord.last_error,
            "deutung_sicher": True,
        }


def build_health_sensors(data) -> list[GroupHealthSensor]:
    """Je Gruppe ein Sensor.

    Nebenwirkung, die bewusst in Kauf genommen wird: Ein Gesundheitssensor ist
    ein Zuhoerer seines Coordinators und haelt dessen Abfrage damit am Leben,
    auch wenn der Betreiber alle uebrigen Entities der Gruppe deaktiviert. Das
    ist der Preis dafuer, dass eine Gruppe nicht unbemerkt verstummen kann.
    Bei den heutigen Intervallen (langsamste Gruppe 3600 s) ist die zusaetzliche
    Last vernachlaessigbar.
    """
    return [GroupHealthSensor(koord, data) for koord in data.coordinators.values()]
