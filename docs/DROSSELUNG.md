# Umbau `sensor.pv_drosselung_leistung` — Entwurf

Stand: 2026-08-11, 17:45 Uhr. Reiner Entwurf. An der laufenden Instanz wurde
nichts geändert; alle Angaben stammen aus lesenden Abfragen.

---

## 0. Sperrvermerk: der Umbau ist heute nicht ausführbar

**Die neuen Entities existieren nicht.** Alle neun in der Aufgabe genannten
Strang-Entities wurden abgefragt und liefern `ENTITY_NOT_FOUND`:

```
sensor.pv_modul_1_spannung   sensor.pv_modul_1_strom   sensor.pv_modul_1_leistung
sensor.pv_modul_2_spannung   sensor.pv_modul_2_strom   sensor.pv_modul_2_leistung
sensor.pv_modul_3_spannung   sensor.pv_modul_3_strom   sensor.pv_modul_3_leistung
```

`ha_search` nach „pv modul" liefert null Treffer in der Entity-Registry.
`ha_get_integration` kennt genau zwei geladene Solarbank-Einträge —
`anker_solix_official` (`01KZGFJ0FEJC7B6RSJBKBMDCC5`) und den Riemann-Integrator
`Solarbank Hausabgabe`. Ein Config-Entry der Domain `solarbank_pv` existiert
nicht.

Der Grund liegt im Repository: `custom_components/solarbank_pv/` enthält
`__init__.py`, `const.py`, `coordinator.py`, `modbus_reader.py` und
`manifest.json` — aber **weder `sensor.py` noch `binary_sensor.py` noch
`config_flow.py`**. `__init__.py` deklariert in Zeile 34
`PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR]`, `manifest.json` setzt
`"config_flow": true`. Beides zeigt auf Dateien, die es nicht gibt. Die
Integration lässt sich in diesem Zustand nicht einrichten.

Nur `sensor.aussentemperatur` ist vorhanden (22,9 °C) — allerdings nicht aus
dieser Integration, sondern als eigener UI-Template-Helper
`01KW2P6HTWQAAFS823D1XKAXAH`, der `state_attr('weather.ahlen', 'temperature')`
spiegelt.

### Zweiter Befund: die Entity-IDs werden anders heißen

Selbst nach Fertigstellung entstehen die IDs aus der Aufgabenstellung nicht von
selbst. `__init__.py` Zeile 63–69 setzt den Gerätenamen auf
`Solarbank DC-Straenge (441)`, `const.py` Zeile 185–190 die Entity-Namen auf
`Modul 1 Spannung` usw. Mit `has_entity_name` — dem Normalfall — erzeugt Home
Assistant daraus:

```
sensor.solarbank_dc_straenge_441_modul_1_spannung
```

nicht `sensor.pv_modul_1_spannung`. Vor dem Umbau ist deshalb genau eine
Entscheidung zu treffen: entweder die Entity-IDs nach der Ersteinrichtung in der
Registry auf `sensor.pv_modul_N_spannung` umsetzen, oder in allen Templates
dieses Dokuments die IDs ersetzen. Die Templates unten verwenden durchgehend die
in der Aufgabe genannten Kurzformen; ein reiner Namenstausch ist die einzige
nötige Anpassung.

Ebenso offen: `pvN_leistung` ist **kein Register**. `const.py` Zeile 294–298
führt `STRINGS` als „Abgeleitete Groessen je Strang", aber die ableitende
`sensor.py` fehlt. Leistung = Spannung × Strom muss erst noch implementiert
werden. Für die Logik unten ist das folgenlos — sie braucht nur Spannungen.

---

## 1. Befund zur Entity-Identität

Bestätigt: `sensor.pv_drosselung_leistung` ist ein Config-Entry der Domain
`template`.

| Feld | Wert |
|---|---|
| `entry_id` | `01KZNWBWJ8FDWZGR4RYHN24Q9W` |
| Domain | `template` |
| Titel | PV Drosselung Leistung |
| Zustand | `loaded`, `supports_options: true` |
| angelegt | 1786367046 (2026-08-10) |
| zuletzt geändert | 1786446130 (2026-08-11, 13:22 Uhr) |

Die Schlussfolgerung der Aufgabenstellung ist richtig und wird hier nur bestätigt:
Ein Nachbau in `templates.yaml` erzeugt eine **zweite** Entity. Home Assistant
hängt bei ID-Kollision `_2` an. Der Riemann-Integrator, das Utility Meter, die
Automation und beide Dashboards zeigten danach auf einen Sensor, den niemand mehr
speist. Der Umbau muss über den Options-Flow dieses Entries laufen.

### Der Options-Flow kann weniger, als man denkt

Abgefragt mit `include_schema=true`. Der Flow hat einen einzigen Schritt
(`step_id: "sensor"`) und akzeptiert **ausschließlich** diese Felder:

| Feld | Pflicht | Selector |
|---|---|---|
| `state` | ja | template |
| `unit_of_measurement` | nein | select, `custom_value: true` |
| `device_class` | nein | select |
| `state_class` | nein | select |
| `device_id` | nein | device |
| `additional_options.availability` | nein | template (expandable) |

Nicht vorhanden: `trigger`, `action`, `attributes`, `variables`, `icon`, `name`.

Das hat eine harte Konsequenz für Abschnitt 4: **ein triggerbasiertes Template
ist in diesem Helper nicht möglich.** Jede Lösung, die sich einen Wert merken
muss, braucht eine zusätzliche Entity außerhalb dieses Config-Entries.

`name` darf beim Update nicht mitgeschickt werden — Options-Flows weisen den
Schlüssel zurück. Umbenennen geht nur über Löschen und Neuanlegen, und genau das
soll hier vermieden werden.

### Konsumenten — vollständige Liste

Die vier aus der Aufgabe sind bestätigt. **Ein fünfter kam hinzu**, der in der
Aufgabenstellung fehlt:

| Konsument | Art | Details |
|---|---|---|
| `automation.pv_ueberschuss_nutzen` | Automation `1786389447751` | Trigger `numeric_state above: 300, for: 10 min`; Bedingung `time 08:00–18:00`; Aktion `notify.send_message` mit Template über `pv_drosselung_leistung` und `pv_drosselung_tag`; danach `delay 2 h`; `mode: single`, `max_exceeded: silent` |
| `sensor.pv_drosselung_energie` | Riemann `01KZNWC5CAQHWMWFDVKDS0AD88` | `method: left`, `max_sub_interval: 5 min`, `round: 3`, `unit_prefix: k`, `unit_time: h` |
| `sensor.pv_drosselung_tag` | Utility Meter, daily | Stand 0,199 kWh; `last_valid_state` 0,498; `last_reset` 2026-08-10T22:00Z; `next_reset` 2026-08-12T00:00+02:00 |
| Dashboard `nulleinspeisung-control` | Lovelace | — |
| Dashboard `nulleinspeisung-preview` | Lovelace | — |
| **`sensor.pv_nutzungsgrad_heute`** | **Template-Helper `01KZPGDRYKR648GFGMXJ3EK192`** | **hängt über `pv_drosselung_tag` an dieser Kette — in `availability` und in `state`: `ist / (ist + weg) * 100`** |

`sensor.pv_nutzungsgrad_heute` ist der empfindlichste Konsument der ganzen Kette.
Er teilt durch `PV-Ertrag + Drosselung`. Jede systematische Verzerrung der
Watt-Zahl schlägt dort als Prozentzahl durch, die aussieht, als wäre sie
gemessen.

---

## 2. Neues state-Template

### Die Physik, auf eine Zeile eingedampft

Mit `T_zelle = T_außen + 25` wird `(T_zelle − 25)` zu `T_außen`. Die
Schwellenformel kürzt sich damit auf:

```
Schwelle = 0.92 * 39.90 * (1 - 0.0025 * T_außen)
```

Kein Zwischenschritt über die Zelltemperatur nötig.

**Schwellenwerte über den Temperaturbereich** (gerechnet, nicht geschätzt):

| T_außen | 0 °C | 5 °C | 10 °C | 15 °C | 20 °C | 25 °C | 30 °C | 35 °C |
|---|---|---|---|---|---|---|---|---|
| Schwelle | 36,71 V | 36,25 V | 35,79 V | 35,33 V | 34,87 V | **34,41 V** | 33,95 V | 33,50 V |

**Abweichung zu den Vorgabewerten:** Der 5-°C-Wert des Auftraggebers (36,3 V)
trifft die Formel exakt (36,25 V). Der 25-°C-Wert (34,0 V) trifft sie **nicht** —
die Formel liefert 34,41 V. 34,0 V entsteht erst bei etwa 30 °C Außentemperatur
(33,95 V) oder bei einer Zelltemperaturannahme von +30 K statt +25 K. Die
Differenz von 0,41 V ist nicht folgenlos: sie entspricht rund 4 K Zelltemperatur
und liegt in derselben Größenordnung wie der Sicherheitsabstand, den die Schwelle
zum Arbeitspunkt hat. **Welcher der beiden Werte gilt, muss der Auftraggeber
entscheiden.** Die Templates unten rechnen mit +25 K, also der schriftlich
festgelegten Formel.

Bei heutigen 22,9 °C: `Voc(T) = 37,62 V`, `Vmp(T) = 31,28 V`, Schwelle
**34,61 V** — also 3,33 V oder 10,6 % Abstand über dem Arbeitspunkt. Das ist ein
brauchbares, aber kein großzügiges Fenster.

### Die Gate-Logik

Drei Zusatzbedingungen über die Unterscheidungstabelle hinaus, jede mit Grund:

1. **Ein Strang zählt erst ab 16 V als aktiv.** `const.py` Zeile 340 nennt das
   MPP-Fenster der Tracker mit 16–50 V. Unter 16 V arbeitet der Tracker gar
   nicht — der Wert ist kein Arbeitspunkt, sondern Dunkelheit. Ohne diese Regel
   zieht ein nachts auf 0 V liegender Strang die Auswertung ins Leere.
2. **Mindestens zwei aktive Stränge.** Ein einzelner Strang kann nicht zwischen
   „alle" und „einer" unterscheiden — genau die Zweitprüfung aus der Aufgabe. Ein
   ausgefallener Modbus-Block darf die Entscheidung nicht allein tragen.
3. **PV-Gesamtleistung ≥ 100 W.** Der einzige verbleibende Fehlalarm-Pfad ist
   die Morgen- und Abenddämmerung: steht der Wechselrichter im Leerlauf, liegen
   alle Stränge bei Voc, also weit über der Schwelle, bei Strom nahe null. Das
   sieht formal identisch zu harter Abregelung aus. Die 100-W-Schranke schließt
   diesen Fall, weil bei echter Abregelung mit vollem Speicher die Hauslast
   weiter aus PV bedient wird und die Gesamtleistung nie auf null fällt.

SOC ≥ 98 % und Entladeleistung < 20 W bleiben unverändert.

### Template

```jinja
{% set soc = states('sensor.anker_solix_solarbank_4_e5000_pro_441_soc') | float(0) %}
{% set entl = states('sensor.anker_solix_solarbank_4_e5000_pro_441_batterieentladeleistung') | float(0) %}
{% set ist = states('sensor.anker_solix_solarbank_4_e5000_pro_441_solarstrom') | float(0) %}
{% set prog = states('sensor.power_production_now') | float(0) %}
{% set tamb = states('sensor.aussentemperatur') | float(15) %}
{% set schwelle = 0.92 * 39.90 * (1 - 0.0025 * tamb) %}
{% set u = [ states('sensor.pv_modul_1_spannung') | float(0),
             states('sensor.pv_modul_2_spannung') | float(0),
             states('sensor.pv_modul_3_spannung') | float(0) ] %}
{% set aktiv = u | select('>=', 16) | list %}
{% set hoch = aktiv | select('>=', schwelle) | list %}
{% set ab = (aktiv | count) >= 2 and (hoch | count) == (aktiv | count) and ist >= 100 %}
{{ ([prog - ist, 0] | max) | round(0) if (ab and soc >= 98 and entl < 20) else 0 }}
```

Einheit `W`, `device_class: power`, `state_class: measurement` — unverändert.

`float(15)` als Rückfallwert für die Außentemperatur ist bewusst gewählt: 15 °C
liegt in der Mitte des Jahresbandes, der Schwellenfehler bleibt damit auch bei
Ausfall des Wetterdienstes unter ±0,7 V. Ein `float(0)` würde die Schwelle auf
36,71 V heben und im Sommer jede Abregelung verschlucken.

### Gegen die Unterscheidungstabelle geprüft

Alle Fälle im HA-Template-Renderer durchgerechnet, Schwelle 34,61 V bei 22,9 °C:

| Fall | Spannungen | Ergebnis | erwartet |
|---|---|---|---|
| Abregelung | 36,8 / 36,5 / 37,1 V | `True` | ✓ |
| **Verschattung, echte Messung 11.08. 14:40** | **29,9 / 29,9 / 32,4 V** | **`False`** | **✓** |
| Nacht | 0 / 0 / 0 V | `False` | ✓ |
| Ein Strang ausgefallen, zwei abgeregelt | 36,9 / 0 / 37,0 V | `True` | ✓ |
| Ist-Zustand jetzt (Entities fehlen) | unknown | `False`, Sensor 0 W | ✓ |

Der zweite Fall ist der wertvollste Beleg: Es ist das reale Verschattungsereignis
aus `docs/REGISTER.md` Abschnitt 8. Strang 3 lag mit 32,4 V um 2,5 V über den
anderen beiden — deutlich sichtbar, aber **2,2 V unter der Schwelle**. Die
Verschattungssignatur löst das Gate nicht aus. Der Wolkenfall braucht keinen
eigenen Test: fallen alle Ströme gleichzeitig, bleiben die Spannungen im
MPP-Band, also unter 34,61 V.

Der Abstand ist allerdings knapp. 2,2 V bei einer Schwelle, deren Lage von einer
ungemessenen Zelltemperaturannahme abhängt — siehe Abschnitt 8.

---

## 3. Neue availability

```jinja
{{ has_value('sensor.anker_solix_solarbank_4_e5000_pro_441_soc')
   and has_value('sensor.anker_solix_solarbank_4_e5000_pro_441_batterieentladeleistung')
   and has_value('sensor.anker_solix_solarbank_4_e5000_pro_441_solarstrom')
   and has_value('sensor.power_production_now')
   and has_value('sensor.aussentemperatur')
   and ([ 'sensor.pv_modul_1_spannung',
          'sensor.pv_modul_2_spannung',
          'sensor.pv_modul_3_spannung' ] | select('has_value') | list | count) >= 2 }}
```

Zwei Punkte zur gestellten Anforderung:

**Nachts null ist kein Problem.** `has_value()` prüft auf `unknown` und
`unavailable`, nicht auf null. Ein Strang, der nachts 0 V meldet, *hat* einen
Wert. Die Sorge trifft die Konstruktion nicht — richtig ist sie trotzdem, denn
sie schließt den anderen Fall aus: Würde man statt `has_value` auf `> 0` prüfen,
wäre der Sensor jede Nacht unavailable und der Riemann-Integrator verlöre
täglich seinen Anschluss.

**2 von 3 statt 3 von 3.** Fällt ein einzelner Modbus-Block dauerhaft aus —
`coordinator.py` Zeile 71–80 nimmt Blöcke nach drei Ablehnungen aus der
Abfrage —, bleibt der Sensor arbeitsfähig. Das ist konsistent mit der
Gate-Logik, die ebenfalls mit zwei Strängen entscheidet. Fallen alle drei aus,
wird der Sensor unavailable, und das ist richtig: dann ist die Aussage nicht
mehr belegt.

`sensor.saunaraum_..._pv_signal_streuung_5min` entfällt aus der availability, da
das Glattheitsgate entfällt. Der Sensor selbst bleibt bestehen und wird nur nicht
mehr von hier referenziert.

**Warnung:** Mit den heutigen Gegebenheiten liefert diese availability `false` —
geprüft. Der Sensor ginge sofort nach dem Umbau dauerhaft auf `unavailable`, weil
keine einzige Strangspannung existiert. Siehe Abschnitt 0.

---

## 4. Herleitung der Watt-Zahl samt Unsicherheit

### Die kurze Antwort

**Die Spannungsmessung kann die Watt-Zahl nicht liefern. Der Forecast ist als
Mengengerüst nicht vollständig ersetzbar.** Empfohlen wird die Hybridlösung, die
die Aufgabenstellung selbst als Möglichkeit nennt: Spannung als Auslöser,
Forecast als Betrag. Genau das tut das Template in Abschnitt 2.

### Warum die Spannung den Betrag nicht hergibt

Der Arbeitspunkt eines Strangs ist ein Punkt auf der I-U-Kennlinie. Bei
Abregelung wandert er von `(Vmp, Imp)` nach `(V', I')` mit `V' > Vmp` und
`I' < Imp`. Gemessen wird `P' = V' × I'` — die *abgegebene* Leistung. Verworfen
wird `P_mpp − P'`, und `P_mpp` steht auf der Kennlinie, die man nicht befährt.

Formal ließe sich `P_mpp` über das Eindiodenmodell rekonstruieren: aus einem
bekannten Punkt `(V', I')` bei bekannter Temperatur den Photostrom `Iph`
zurückrechnen, daraus das MPP. Praktisch scheitert das an zwei Stellen:

1. **Rechts vom MPP ist die Kennlinie steil.** `dI/dV` ist dort groß, das heißt
   umgekehrt: ein kleiner Spannungsfehler erzeugt einen großen Stromfehler in der
   Rückrechnung. Die Modbus-Auflösung beträgt 0,1 V (`const.py` Zeile 185,
   `scale 0.1`) — das ist auf dem steilen Ast keine gute Stützstelle.
2. **Bei harter Abregelung wird die Gleichung entartet.** Geht `V' → Voc`, geht
   `I' → 0`. Alle Einstrahlungswerte bilden dann fast auf denselben Punkt ab. Die
   einzige verbleibende Information steckt im logarithmischen Anteil von Voc.

Diesen letzten Pfad kann man beziffern, und das Ergebnis ist eindeutig negativ:

```
Voc(G) = Voc(T) + Ns · n·kT/q · ln(G / G_ref)
```

Bei 54 Serienzellen (39,90 V ÷ 54 ≈ 0,74 V pro Zelle — plausibel für N-Typ; die
108 Halbzellen liegen als 2 × 54 vor), `n ≈ 1,1` und `T_zelle = 50 °C`
(`kT/q = 27,85 mV`) ergibt sich **1,65 V pro e-Faches Einstrahlung**. Eine
Halbierung der Einstrahlung senkt Voc also um `1,65 · ln 2 = 1,15 V`.

Dem steht der Temperaturgang gegenüber: `dVoc/dT = −0,0025 · 39,90 =
−0,0998 V/K`. Die 1,15 V sind damit **äquivalent zu 11,5 K Zelltemperatur**.

Und die Zelltemperatur wird nicht gemessen, sondern als `Außentemperatur + 25 K`
angenommen. `docs/REGISTER.md` Abschnitt 8 widerlegt diese Annahme mit eigenen
Zahlen: Am 11.08. um 14:40 rechnete das Dokument aus den gemessenen 29,9 V eine
Zelltemperatur von ~57 °C zurück — bei einer Außentemperatur im Bereich 22–25 °C
also `+32` bis `+35 K`, nicht `+25 K`. Im selben Moment lag der verschattete
Strang 3 bei ~34 °C. **23 K Spreizung zwischen Modulen auf derselben Dachfläche
zur selben Sekunde.**

Eine Zelltemperaturunsicherheit von ±10 K entspricht ±1 V auf Voc, und das
entspricht einem Einstrahlungsfaktor von `e^(1/1,65) ≈ 1,8`. **Eine
Leistungsschätzung, die um den Faktor 1,8 danebenliegen kann, ist kein
Energiezähler.** Damit ist der Pfad geschlossen.

Nebenbei: Die Zahlen `Ns = 54` und `n = 1,1` sind meine Ableitung aus der
Zellspannung, nicht dem Datenblatt entnommen. Sie ändern die Größenordnung nicht,
sind aber nicht belegt.

### Warum der Forecast als Betrag trotzdem schlecht ist — mit Messung

Der Forecast liefert das Mengengerüst, aber schlecht. Belegt an den heutigen
Daten, 11.08.2026:

| Uhrzeit | `power_production_now` | tatsächlicher `solarstrom` |
|---|---|---|
| 17:35 | 494 W | 690–810 W |

**Der Forecast lag zu diesem Zeitpunkt 30–40 % zu niedrig.** Konsequenz für
`max(prog − ist, 0)`: Hätte in diesem Moment eine echte Abregelung stattgefunden,
hätte der Sensor **0 W verworfene Leistung** gemeldet, weil die Differenz negativ
ist und weggeklemmt wird. Unterschätzung ist der dominante Fehlermodus, und die
Klemme auf 0 macht ihn unsichtbar.

Der umgekehrte Fall ist heute ebenso sichtbar. Der Sensor pendelt derzeit im
Sekundentakt zwischen 0 und 7…117 W — 459 Zustandswechsel im abgefragten
10-Stunden-Fenster, Tageswert 0,195 kWh, gestern 0,292 kWh. SOC steht auf 100 %,
die Entladeleistung auf 0 W, die Streuung auf 24 W: **das Gate ist offen**, und
was der Sensor integriert, ist reines Forecast-Rauschen. Die 0,195 kWh von heute
sind mit hoher Wahrscheinlichkeit keine verworfene Energie, sondern der
Prognosefehler der Forecast.Solar-Kurve.

Damit ist der eigentliche Gewinn des Umbaus benannt: **Nicht die genauere
Watt-Zahl, sondern das Abschalten des Rauschens.** Das Spannungs-Gate ist die
überwiegende Zeit geschlossen und lässt den Forecast-Fehler gar nicht erst in die
Integration. Der Betrag wird nicht besser — er wird nur noch dann gebildet, wenn
er überhaupt eine Bedeutung hat.

### Unsicherheit, ehrlich beziffert

| Größe | Unsicherheit | Art |
|---|---|---|
| Auslösung (ob abgeregelt) | gut, solange Zelltemperaturannahme ±10 K hält | systematisch, siehe Abschnitt 8 |
| Betrag (wie viel verworfen) | **±30…40 % des Momentanwerts** | systematisch, Vorzeichen tagesabhängig |
| Betrag bei negativer Differenz | Ausgabe 0 W statt des wahren Werts | einseitiger Abschneidefehler |
| Erfassungsbereich | **nur 3 von 4 Strängen messbar** | Strang 4 ≈ 60 W von 1160 W ≈ 5 %, siehe REGISTER.md Abschnitt 5 |
| Tagesenergie `pv_drosselung_tag` | dieselbe relative Unsicherheit, über den Tag teilweise ausgleichend | — |

Der Sensor ist damit ein **Indikator mit Größenordnung**, kein Messgerät. Für
seinen Zweck — „jetzt lohnt sich die Waschmaschine" — reicht das. Für die
Prozentzahl in `sensor.pv_nutzungsgrad_heute` reicht es nicht; die Zahl sollte
dort als Schätzung gekennzeichnet werden.

### Die bessere Betragsquelle — Version 2

Wenn der Betrag später besser werden soll, ist der belegbare Weg die
**Referenzhaltung mit Forecast-Formkorrektur**:

```
P_verfügbar ≈ P_ref · (prog_jetzt / prog_ref)
verworfen  = max(P_verfügbar − ist, 0)
```

`P_ref` ist die gemessene PV-Leistung unmittelbar **bevor** das Gate zuschlug,
`prog_ref` der Forecast zum selben Zeitpunkt. Der Trick: Im Verhältnis
`prog_jetzt / prog_ref` **kürzt sich der systematische Niveaufehler des
Forecasts heraus.** Verwendet wird nur noch seine Tagesform — die Kosinuskurve
des Sonnenstands —, und die ist ungleich zuverlässiger als sein Absolutniveau.
Der Anker ist eine echte Messung, kein Modell.

Restunsicherheit: Zieht während des Abregelfensters eine Wolkenfront auf, bricht
die Formannahme. Unter klarem Himmel liegt der Fehler bei ±10–15 % über eine
halbe Stunde; über zwei Stunden gebrochener Bewölkung ist er unbegrenzt.

**Das geht in diesem Helper nicht.** Der Options-Flow kennt kein `trigger` — der
Helper kann sich nichts merken. Version 2 braucht zusätzlich entweder ein
triggerbasiertes Template-Sensor in YAML (eine *neue* Entity, damit unkritisch)
oder ein `input_number` plus schreibende Automation. Beides ist ein eigener
Vorgang und ausdrücklich nicht Teil dieses Entwurfs.

---

## 5. Nebenwirkungen und bester Umbauzeitpunkt

### Was beim Speichern passiert

`ha_config_set_helper` schreibt die Options und löst einen Reload des
Config-Entries aus. Die Entity wird abgemeldet und neu aufgebaut. In diesem
Fenster ist sie `unavailable`, unmittelbar danach für einen Renderzyklus
`unknown`. Die Dauer liegt typischerweise deutlich unter einer Sekunde, ist aber
nicht garantiert — bei belastetem System kann sie länger sein.

### Riemann-Integrator `sensor.pv_drosselung_energie`

`method: left` bedeutet: über ein Intervall wird der Wert am **Anfang** des
Intervalls verwendet. Nicht-numerische Zustände sind für den Integrator keine
Stützstellen. Der Ablauf ist damit:

1. Quelle wird `unavailable` → Integration hält an, der akkumulierte Zählerstand
   bleibt erhalten. **Kein Reset auf null.** Der Wert 0,498 kWh übersteht den
   Umbau.
2. Die Lücke wird nicht nachintegriert. Verlorene Energie = letzter Wert ×
   Lückendauer.
3. Quelle kommt zurück → neue Stützstelle, `max_sub_interval` von 5 min startet
   neu.

Rechnung: Bei 400 W und 2 s Lücke gehen `400 W · 2 s = 0,22 Wh` verloren. Der
Integrator rundet auf `round: 3` in kWh, also auf 1 Wh. Der Verlust bleibt schon
im ungünstigen Fall unter der Anzeigeauflösung. **Beim Umbau zu einem Zeitpunkt
mit 0 W ist er exakt null.**

### Utility Meter `sensor.pv_drosselung_tag`

Quelle ist der Energiezähler, nicht der Leistungssensor. Der Leistungssensor wird
also nur mittelbar berührt. Das Utility Meter führt `last_valid_state` (aktuell
0,498) und übersteht eine kurze Nichtverfügbarkeit der Quelle ohne
Tageswertverlust. `next_reset` steht auf 2026-08-12T00:00+02:00 — der Umbau darf
diesen Moment nicht treffen, sonst überlagern sich Reload und
Perioden-Rollover.

### numeric_state-Trigger mit `for: 10 min`

Das ist der einzige Konsument mit echtem Zustandsverlust. Der Trigger feuert,
wenn `pv_drosselung_leistung` **durchgehend** 10 Minuten über 300 liegt. Geht die
Entity zwischendurch auf `unknown` oder `unavailable`, wird die Bedingung falsch
und **die laufende 10-Minuten-Uhr verworfen**. Ein erneutes Auslösen verlangt
eine frische Überschreitung von unten.

Kosten im schlimmsten Fall: eine um bis zu 10 Minuten verspätete Meldung. Kein
Datenverlust, keine Fehlmeldung. Doppelmeldungen sind ebenfalls ausgeschlossen —
`mode: single` mit `max_exceeded: silent` und der 2-Stunden-Sperrfrist am Ende
der Aktionsliste.

Zusatzbefund: Wie in Abschnitt 4 gezeigt, springt der Sensor derzeit im
Sekundentakt auf 0 zurück. Der Trigger kann in der Praxis **gar nicht feuern** —
10 Minuten ununterbrochen über 300 W kommen bei diesem Zappeln nie zustande. Der
Umbau repariert das nebenbei: Das Spannungs-Gate ist eine träge Größe, und
solange es offen ist, bleibt auch der Wert stehen.

### Bester Zeitpunkt

Zwei Kriterien, die gegeneinander laufen:

**Schadensfrei:** nachts, zwischen Sonnenuntergang und Sonnenaufgang. Der Sensor
steht bei 0 W, der Integrator verliert exakt nichts, die Automation ist ohnehin
durch ihre Zeitbedingung `08:00–18:00` blockiert, und niemand wartet auf eine
Meldung. **Nicht** um Mitternacht — `next_reset` des Utility Meters.
**Empfehlung: 22:00–23:30 Uhr oder 00:30–05:00 Uhr.**

**Prüfbar:** ein klarer Tag um die Mittagszeit bei vollem Speicher. Nur dann
lässt sich sehen, ob das Gate greift.

Das ist kein Widerspruch, sondern eine Reihenfolge: **nachts umbauen, am
Folgetag prüfen.** Der Umbau ist reversibel — der alte `state`-String steht
vollständig in Abschnitt 1 dieses Dokuments und lässt sich mit demselben
Werkzeugaufruf zurückschreiben.

Bis Abschnitt 0 erledigt ist, ist der günstigste Zeitpunkt allerdings: **keiner.**

---

## 6. Fertiger Werkzeugaufruf

Ausführen erst, wenn Abschnitt 0 erledigt ist und die Strang-Entities unter den
hier verwendeten IDs existieren.

**Werkzeug:** `mcp__claude_ai_homeassistant__ha_config_set_helper`

**Parameter:**

```json
{
  "helper_type": "template",
  "action": "update",
  "helper_id": "01KZNWBWJ8FDWZGR4RYHN24Q9W",
  "config": {
    "template_type": "sensor",
    "state": "{% set soc = states('sensor.anker_solix_solarbank_4_e5000_pro_441_soc') | float(0) %}{% set entl = states('sensor.anker_solix_solarbank_4_e5000_pro_441_batterieentladeleistung') | float(0) %}{% set ist = states('sensor.anker_solix_solarbank_4_e5000_pro_441_solarstrom') | float(0) %}{% set prog = states('sensor.power_production_now') | float(0) %}{% set tamb = states('sensor.aussentemperatur') | float(15) %}{% set schwelle = 0.92 * 39.90 * (1 - 0.0025 * tamb) %}{% set u = [ states('sensor.pv_modul_1_spannung') | float(0), states('sensor.pv_modul_2_spannung') | float(0), states('sensor.pv_modul_3_spannung') | float(0) ] %}{% set aktiv = u | select('>=', 16) | list %}{% set hoch = aktiv | select('>=', schwelle) | list %}{% set ab = (aktiv | count) >= 2 and (hoch | count) == (aktiv | count) and ist >= 100 %}{{ ([prog - ist, 0] | max) | round(0) if (ab and soc >= 98 and entl < 20) else 0 }}",
    "unit_of_measurement": "W",
    "device_class": "power",
    "state_class": "measurement",
    "additional_options": {
      "availability": "{{ has_value('sensor.anker_solix_solarbank_4_e5000_pro_441_soc') and has_value('sensor.anker_solix_solarbank_4_e5000_pro_441_batterieentladeleistung') and has_value('sensor.anker_solix_solarbank_4_e5000_pro_441_solarstrom') and has_value('sensor.power_production_now') and has_value('sensor.aussentemperatur') and ([ 'sensor.pv_modul_1_spannung', 'sensor.pv_modul_2_spannung', 'sensor.pv_modul_3_spannung' ] | select('has_value') | list | count) >= 2 }}"
    }
  }
}
```

Anmerkungen zum Aufruf:

- **`name` fehlt bewusst.** Options-Flows weisen den Schlüssel beim Update
  zurück. Der Anzeigename „PV Drosselung Leistung" bleibt unverändert erhalten.
- **`helper_id` ist die Entry-ID, nicht die Entity-ID.** Für Flow-Helper ist das
  die dokumentierte Form. Damit bleibt `sensor.pv_drosselung_leistung` als
  Entity-ID bestehen — der ganze Zweck der Übung.
- **`action: "update"` ist gesetzt**, damit ein Tippfehler in `helper_id` als
  „helper not found" auffällt statt still einen zweiten Helper anzulegen.
- **`template_type`** steht nicht in der `data_schema` des Options-Schritts und
  wird von HA ignoriert. Er ist mitgeführt, weil er in den gespeicherten Options
  steht; er schadet nicht.
- **`BestPracticeKey`** ist hier nicht ausgefüllt. Ist der Strict-Modus aktiv,
  muss der Ausführende zuvor die `home-assistant-best-practices`-Skill lesen und
  die dort veröffentlichte Attestierungsphrase wörtlich mitgeben. Ein geratener
  Wert wäre schlicht falsch.
- Beide Templates sind einzeilig — genau so, wie sie oben im
  HA-Template-Renderer geprüft wurden.

### Rückbau

Identischer Aufruf, `state` und `availability` durch die Originalwerte aus
Abschnitt 1 ersetzt.

---

## 7. Abregelungs-Binärsensor

`binary_sensor.pv_abregelung_erkannt` — reiner Zustandsindikator, ohne Betrag.
Er trägt die Aussage, die physikalisch belegt ist, und **nur** die.

Getrennt zu halten ist er aus einem inhaltlichen Grund: Der Leistungssensor
mischt eine gemessene Aussage („abgeregelt") mit einer geschätzten („so viel").
Der Binärsensor enthält ausschließlich die gemessene. Er ist damit der
belastbarere der beiden und die richtige Grundlage für Schaltentscheidungen —
Dashboards, spätere Automationen, Fehlersuche. Wo eine Wahrheitsaussage genügt,
sollte niemand die Schätzung anfassen müssen.

**Template (`state`):**

```jinja
{% set soc = states('sensor.anker_solix_solarbank_4_e5000_pro_441_soc') | float(0) %}
{% set entl = states('sensor.anker_solix_solarbank_4_e5000_pro_441_batterieentladeleistung') | float(0) %}
{% set ist = states('sensor.anker_solix_solarbank_4_e5000_pro_441_solarstrom') | float(0) %}
{% set tamb = states('sensor.aussentemperatur') | float(15) %}
{% set schwelle = 0.92 * 39.90 * (1 - 0.0025 * tamb) %}
{% set u = [ states('sensor.pv_modul_1_spannung') | float(0),
             states('sensor.pv_modul_2_spannung') | float(0),
             states('sensor.pv_modul_3_spannung') | float(0) ] %}
{% set aktiv = u | select('>=', 16) | list %}
{% set hoch = aktiv | select('>=', schwelle) | list %}
{{ (aktiv | count) >= 2 and (hoch | count) == (aktiv | count) and ist >= 100 and soc >= 98 and entl < 20 }}
```

Identisch zum Gate in Abschnitt 2, nur ohne den Forecast-Term. Im
HA-Template-Renderer geprüft, liefert derzeit `false`.

Keine `device_class`: `problem` wäre falsch — Abregelung bei vollem Speicher ist
der Normalbetrieb, keine Störung. `power` wäre irreführend. Ein Icon lässt sich
nachträglich in der UI setzen (`mdi:solar-power-variant-outline`).

**Werkzeugaufruf zum Anlegen** (neue Entity, daher unkritisch — es gibt nichts zu
erhalten):

```json
{
  "helper_type": "template",
  "action": "create",
  "name": "PV Abregelung erkannt",
  "config": {
    "template_type": "binary_sensor",
    "name": "PV Abregelung erkannt",
    "state": "{% set soc = states('sensor.anker_solix_solarbank_4_e5000_pro_441_soc') | float(0) %}{% set entl = states('sensor.anker_solix_solarbank_4_e5000_pro_441_batterieentladeleistung') | float(0) %}{% set ist = states('sensor.anker_solix_solarbank_4_e5000_pro_441_solarstrom') | float(0) %}{% set tamb = states('sensor.aussentemperatur') | float(15) %}{% set schwelle = 0.92 * 39.90 * (1 - 0.0025 * tamb) %}{% set u = [ states('sensor.pv_modul_1_spannung') | float(0), states('sensor.pv_modul_2_spannung') | float(0), states('sensor.pv_modul_3_spannung') | float(0) ] %}{% set aktiv = u | select('>=', 16) | list %}{% set hoch = aktiv | select('>=', schwelle) | list %}{{ (aktiv | count) >= 2 and (hoch | count) == (aktiv | count) and ist >= 100 and soc >= 98 and entl < 20 }}",
    "additional_options": {
      "availability": "{{ has_value('sensor.anker_solix_solarbank_4_e5000_pro_441_soc') and has_value('sensor.anker_solix_solarbank_4_e5000_pro_441_batterieentladeleistung') and has_value('sensor.anker_solix_solarbank_4_e5000_pro_441_solarstrom') and has_value('sensor.aussentemperatur') and ([ 'sensor.pv_modul_1_spannung', 'sensor.pv_modul_2_spannung', 'sensor.pv_modul_3_spannung' ] | select('has_value') | list | count) >= 2 }}"
    }
  }
}
```

`power_production_now` fehlt in dieser availability bewusst: Der Binärsensor
braucht den Forecast nicht und soll nicht ausfallen, wenn der Wetterdienst
ausfällt. Aus dem Namen „PV Abregelung erkannt" erzeugt HA die Entity-ID
`binary_sensor.pv_abregelung_erkannt`.

**Vorschlag zur Reihenfolge:** Diesen Binärsensor **zuerst** anlegen und einige
sonnige Tage beobachten, ohne den Leistungssensor anzufassen. Er ist reine
Beobachtung — kein Konsument hängt an ihm, keine Historie steht auf dem Spiel.
Erst wenn belegt ist, dass er bei echter Abregelung anschlägt und bei Verschattung
und Wolken schweigt, lohnt der Eingriff in Abschnitt 6. Das kostet ein paar Tage
und ersetzt eine Annahme durch eine Messung.

---

## 8. Offene Punkte

1. **Die Integration existiert nicht.** `sensor.py`, `binary_sensor.py` und
   `config_flow.py` fehlen. Ohne sie ist keiner der Aufrufe in Abschnitt 6 und 7
   ausführbar. Das ist die einzige echte Vorbedingung.

2. **Die Entity-IDs stehen nicht fest.** `const.py` und `__init__.py` erzeugen
   `sensor.solarbank_dc_straenge_441_modul_1_spannung`, nicht
   `sensor.pv_modul_1_spannung`. Entscheidung nötig: Registry umsetzen oder
   Templates anpassen.

3. **Die beiden Vorgabewerte widersprechen sich.** 36,3 V bei 5 °C trifft die
   Formel, 34,0 V bei 25 °C nicht (Formel: 34,41 V). 34,0 V passt zu einer
   Zelltemperaturannahme von +30 K. Welche gilt?

4. **Die Zelltemperaturannahme +25 K ist durch die eigenen Daten in Frage
   gestellt.** REGISTER.md Abschnitt 8 rechnet +32 bis +35 K zurück, und
   zwischen zwei Modulen derselben Fläche lagen zeitgleich 23 K. Die Schwelle
   verschiebt sich um 0,1 V je Kelvin — bei +35 K statt +25 K sinkt sie um 1,0 V
   und rückt der Verschattungssignatur von 32,4 V auf 1,2 V nahe. **Das ist der
   größte Einzelrisikoposten des ganzen Entwurfs.** Ein gemessener Modulwert
   wäre die saubere Lösung; ersatzweise ließe sich die Zelltemperatur je Strang
   aus `Vmp` zurückrechnen (`const.py` Zeile 337 hat die Formel bereits), was
   allerdings nur solange gilt, wie der Strang tatsächlich im MPP fährt — also
   genau dann nicht mehr, wenn man sie braucht.

5. **Teilabregelung wird nicht erkannt.** Die Schwelle 0,92 × Voc liegt weit
   rechts. Drosselt der Wechselrichter nur um 20–30 %, steigt die Spannung
   messbar, aber nicht über die Schwelle. Der Sensor meldet dann 0 W, obwohl
   Energie verfällt. Wie viel dabei durchrutscht, lässt sich ohne Messreihe nicht
   sagen. Eine niedrigere Schwelle würde mehr erfassen und gleichzeitig die
   Verschattung einfangen — die 2,2 V Abstand aus Abschnitt 2 sind das Budget.

6. **Der wahrscheinlich bessere Weg liegt ungenutzt herum.** `const.py` liest in
   der Gruppe `limits` alle 300 s die Register 10036 (`max_charge_power`) und
   10038 (`ac_output_limit`) — standardmäßig aktiv. Sinkt das AC-Ausgangslimit,
   ist das kein *abgeleiteter* Hinweis auf Abregelung, sondern die **vom Gerät
   selbst deklarierte Grenze**. Das wäre die direktere Evidenz als der Umweg über
   die Modulspannung, und es könnte den Betrag mitliefern. Ungeprüft, weil die
   Register noch nie ausgelesen wurden. **Vor dem Umbau einen Tag mitschreiben
   lassen** — das könnte den ganzen Entwurf überflüssig machen.

7. **Nur 3 von 4 Strängen sind messbar.** Strang 4 ist laut REGISTER.md
   Abschnitt 5 mit hoher Wahrscheinlichkeit nicht über Modbus verfügbar. Für das
   Gate ist das folgenlos — Abregelung trifft alle Tracker. Für jede spätere
   Betragsrechnung aus Strangdaten fehlen ~5 %.

8. **`sensor.pv_nutzungsgrad_heute` war nicht in der Konsumentenliste.** Er hängt
   über `pv_drosselung_tag` mit an der Kette und rechnet die Drosselung in eine
   Prozentzahl um. Er bricht durch den Umbau nicht, aber seine Zahl ändert
   Bedeutung und Größenordnung — vermutlich deutlich nach unten, sobald das
   Forecast-Rauschen wegfällt. Der Sprung im Verlauf ist zu erwarten und kein
   Fehler.

9. **Die Verlaufsdaten bleiben, ihre Bedeutung ändert sich.** Vor dem Umbau
   misst der Sensor überwiegend Prognosefehler, danach gegatete Abregelung. Die
   Zeitreihe ist über den Umbauzeitpunkt hinweg nicht vergleichbar. Ein Marker im
   Dashboard wäre ehrlicher als eine durchgehende Kurve.

10. **Die physische Modulzuordnung ist ungeklärt** (REGISTER.md Abschnitt 7).
    Für dieses Gate irrelevant — es fragt nur, ob *alle* Stränge hoch sind, nicht
    welcher. Für die Verschattungsdiagnose bleibt sie offen.
