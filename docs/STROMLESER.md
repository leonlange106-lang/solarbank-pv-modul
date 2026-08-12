# Stromleser: Ausfall am 12.08.2026 und die Konsequenzen

Betrifft nicht die Solarbank, sondern den IR-Lesekopf am Stromzähler — er liefert
den Reglereingang der Nulleinspeisung. Ohne ihn steht die Regelung.

Stand: 12.08.2026. Gerät: Tasmota `stromleser` auf ESP32-C3, 192.168.178.37,
Firmware 15.0.1.5 (stromleser.com-Build), MQTT-Client `DVES_B642B8`.

---

## 1. Was passiert ist

Um 12:17 Uhr wurde die HAOS-VM neu gestartet. Danach fehlten
`sensor.stromleser_emh_power` und `sensor.stromleser_emh_e_in` **vollständig** —
nicht `unavailable`, sondern gar nicht mehr in der Registry. Die neun
Diagnose-Entitäten des Geräts (SSID, Reconnects, Restart Reason) kamen dagegen
zurück.

Der Lesekopf selbst war die ganze Zeit in Ordnung. Seine Weboberfläche zeigte
durchgehend `EMH Verbrauch 24846,796 kWh` und `EMH akt. Leistung −2 W`,
Betriebszeit 1 Tag 18 Stunden, kein Neustart.

## 2. Die Ursache

Das Skript auf dem Lesekopf (`script.txt`, Tasmota-Scripting) liest den Zähler
über den SML-Treiber und veröffentlicht die Werte mit einem **manuellen
`publish`**:

```
>M 1
+1,3,s,16,9600,EMH,1
1,77070100010800ff@1000,Verbrauch,kWh,E_in,3
1,77070100020800ff@1000,Einspeisung,kWh,E_out,3
1,77070100100700ff@1,akt. Leistung,W,Power,0
>S
=>publish tele/tasmota_B642B8/SENSOR {"EMH":{"E_in":...,"E_out":...,"Power":...}}
```

Damit umgeht es Tasmotas eigene Sensor-Pipeline. Die Folge ist entscheidend:
**`Status 10` liefert ein leeres `StatusSNS`** — Tasmota kennt die Werte nicht,
es leitet sie nur durch.

Die HA-Entitäten stammten von Tasmotas Discovery-Topic
`tasmota/discovery/<mac>/sensors`. Das lag **retained** auf dem Broker. Als der
Mosquitto-Container um 12:16:58 frisch startete, waren alle retained Nachrichten
weg. Tasmota schrieb das Discovery-Topic beim nächsten Connect neu — **aber es
erzeugt es aus `StatusSNS`, und das ist leer**.

Deshalb kamen die Diagnose-Entitäten zurück (sie stehen im `config`-Topic, das
Tasmota bei jedem MQTT-Connect neu setzt) und die drei EMH-Sensoren nicht. Ein
Geräteneustart hilft nicht; er wurde am 12.08. um 12:46 ausgeführt und änderte
nichts.

Nebenbei aus dem Broker-Protokoll: Das Gerät verbindet sich **vor** Home
Assistant (12:17:33 gegen 12:17:52). Für retained Discovery wäre das
gleichgültig — nur gab es die eben nicht mehr.

## 3. Die Reparatur

Die drei Sensoren sind jetzt **fest in `/config/mqtt.yaml` definiert**, gebunden
an `mqtt: !include mqtt.yaml` in `configuration.yaml`. Sie hängen damit nicht
mehr an der Discovery und überstehen jeden künftigen Broker-Neustart.

Nutzlast des Topics `tele/tasmota_B642B8/SENSOR`:

```jsonc
{"EMH":{"E_in":24846.796,"E_out":0.000,"Power":-2}}
```

Die Namen sind so gewählt, dass **exakt die alten entity_ids** entstehen
(`sensor.stromleser_emh_power`, `sensor.stromleser_emh_e_in`). Das ist der Grund,
warum die Historie erhalten blieb: Der Recorder verknüpft über die `entity_id`,
nicht über die `unique_id`.

## 4. Der Statistikschaden — 541,189 kWh Phantomverbrauch

Der Ausfall hat über eine zweite Ecke Schaden angerichtet. Der Template-Sensor
`Strom Bezug Dashboard` in `templates.yaml` hatte eine Fallback-Kette mit einem
**hartkodierten Endwert**:

```jinja
{% else %}
  24305.61
{% endif %}
```

Während der Sensor fehlte, fiel der Wert auf 24 305,61 und sprang danach zurück
auf 24 846,797. Bei einem `total_increasing`-Energiesensor liest Home Assistant
den Absturz als Zählerwechsel und den Wiederanstieg als echten Verbrauch:
**+541,189 kWh** in einer einzigen Stunde, sichtbar in Netzbezug Tag, Monat und
Jahr, und weitergereicht an Hausverbrauch und Autarkiegrad.

Repariert in zwei Schritten — beide waren nötig:

| Schritt | Werkzeug | Wirkung |
|---|---|---|
| Zählerstände | `utility_meter.calibrate` | korrigiert den Live-Wert |
| aufgezeichnete Historie | `recorder/adjust_sum_statistics` | korrigiert den Rückblick |

Ohne den zweiten Schritt bleibt der Sprung in allen Auswertungen stehen, auch
wenn die Anzeige stimmt.

**Die Ursache ist beseitigt:** Der Fallback ist raus. Der Sensor wird jetzt
`unavailable`, wenn die Quelle fehlt — dann pausieren die Utility-Meter und
laufen danach ohne Phantomsprung weiter, genau so wie vorgesehen.

**Merksatz:** Ein `total_increasing`-Sensor darf bei Ausfall der Quelle niemals
auf einen niedrigeren Festwert zurückfallen. `unavailable` ist immer richtig,
Raten ist immer falsch.

## 5. Einheitenfehler in der Langzeitstatistik

`recorder/validate_statistics` meldete nach dem Umbau für `emh_e_in` und
`emh_e_out` den Typ `units_changed`: gespeicherte Metadaten `unit = null`, neuer
Zustand `kWh`. Der alte, von Tasmota erzeugte Sensor hatte nie eine Einheit
gesetzt, die Statistik lag also als „unitless" vor.

Behoben über `recorder/update_statistics_metadata` — die Metadaten wurden auf
`kWh` gehoben, statt den Sensor auf die falsche Altlast herunterzuziehen. Die
Zahlen waren immer Kilowattstunden. Kein Datenpunkt ging verloren.

## 6. Der geglättete Dashboard-Sensor

Der Lesekopf sendet mit **1 Hz**. Für die Nulleinspeisungsregelung ist das genau
richtig, für eine Anzeige unbrauchbar unruhig — und im Recorder wären es 86 400
Zeilen pro Tag.

`sensor.stromleser_emh_power` bleibt deshalb im Recorder-Ausschluss. Daneben
steht in `/config/sensors.yaml` neu:

```yaml
- platform: filter
  name: "Stromleser EMH Power Dashboard"
  entity_id: sensor.stromleser_emh_power
  filters:
    - filter: time_simple_moving_average
      window_size: "00:00:30"
    - filter: time_throttle
      window_size: "00:00:30"
```

Zwei Filter hintereinander: Das gleitende 30-Sekunden-Mittel glättet, der
`time_throttle` begrenzt die Aktualisierung auf alle 30 Sekunden und hält damit
die Datenbank klein. Eine Filterkette geht nur in YAML — der
UI-Konfigurationsfluss erzeugt genau einen Filter je Eintrag.

## 7. Dashboards umgestellt

Alle Karten, die auf dem Rohsensor lagen, wurden auf den Dashboard-Sensor
umgezogen — **33 Fundstellen in vier Dashboards**:

| Dashboard | Fundstellen |
|---|---|
| `dashboard-stromleser` | 7 |
| `nulleinspeisung-control` | 10 |
| `nulleinspeisung-preview` | 12 |
| `echo-show-5-dashboard` | 1 |

Zwei Gründe: Verlaufs- und Statistikkarten zeigten auf dem Rohsensor
**strukturell nichts**, weil er vom Recorder ausgeschlossen ist. Und bei
Live-Anzeigen stört ein im Sekundentakt springender Wert nur.

**Zwei Karten behalten bewusst den Rohsensor**, beide in `dashboard-neuer`
(„HA-Überwachung"):

- der Frischewächter, der `now() - last_reported` misst und ab 15 s Alarm
  schlägt — mit einem 30-s-Sensor wäre er blind
- die Störungsanleitung, die den Rohsensor namentlich zum Prüfen nennt

## 8. Aufräumarbeiten am selben Tag

| Punkt | Vorher | Nachher |
|---|---|---|
| `pyscript` | geladen mit `allow_all_imports: true`, Verzeichnis leer, keine Aufrufe | YAML-Block entfernt **und** Config-Eintrag gelöscht |
| Cloudflare-Statuscheck | `curl http://192.168.178.43:2000/ready` | `http://396f0234-cloudflared.local.hass.io:36500/ready` |
| Recorder-Ausschluss | unkommentiert | Begründung im Code |

Zum Cloudflare-Punkt zwei Fallstricke, die leicht zu übersehen sind:
`command_line` läuft **im HA-Core-Container**, dort ist `localhost` Home
Assistant selbst und nicht der Host. Und Port 2000 existiert nur als
Host-Mapping; intern hört das Add-on auf **36500**. Die Supervisor-DNS
`<slug>.local.hass.io` ist der richtige Weg und überlebt sowohl einen
IP-Wechsel als auch eine Änderung des Port-Mappings.

Zum pyscript-Punkt: Bei Config-Einträgen mit `source: import` genügt das
Entfernen der YAML **nicht** — der Eintrag bleibt bestehen und die Integration
lädt weiter. Er muss zusätzlich gelöscht werden.

## 9. Prüfliste bei erneutem Ausfall

1. **Liefert das Gerät?** `http://192.168.178.37/?m=1` zeigt die Rohwerte der
   Weboberfläche. `Status 10` ist bei diesem Skript **immer leer** und taugt
   nicht als Test — das war beim ersten Durchgang die falsche Fährte.
2. **Existieren die Entitäten?** Fehlen sie ganz, ist `mqtt.yaml` nicht geladen
   (`homeassistant.check_config`, dann `mqtt.reload`).
3. **Kommen Werte an?** In der Tasmota-Konsole muss im Sekundentakt
   `MQT: tele/tasmota_B642B8/SENSOR` erscheinen.
4. **Nach jedem Ausfall:** `recorder/validate_statistics` aufrufen und die
   Utility-Meter auf Phantomsprünge prüfen.
