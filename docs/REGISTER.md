# Modbus-Registerkarte — Anker SOLIX Solarbank 4 E5000 Pro

Gerät: AE103, SN AK7DN7M0G21100441, Firmware 1.0.2.30
Adresse: 192.168.178.86:502, Unit-ID 1
Erhoben: 11.08.2026, ausschließlich lesend (Function Code 3 und 4)

Diese Tabelle existiert in keiner Herstellerdokumentation. Sie wurde durch einen
vollständigen Adressraumscan und durch Zeitreihenvergleich gegen die Anker-App
und gegen Home-Assistant-Historie erarbeitet. Der Code, der sie erzeugt hat, ist
reproduzierbar — die Tabelle selbst ist es nicht.

---

## 1. Protokolleigenschaften

| Eigenschaft | Befund | Beleg |
|---|---|---|
| Function Codes | FC03 und FC04 über den **gesamten** Adressraum aliasiert, identische Antworten | 4490 Blockanfragen, beide FC an jeder Startadresse |
| FC01 / FC02 | **Nicht unterstützt.** Exception 1 (Illegal Function), also funktionsweit, nicht adressweise | je 1 Anfrage, beide Exception 1 |
| Wortreihenfolge | Big-Endian, `registers[0]` = High-Word | `modbus_client.py` Zeile 294 der Herstellerintegration |
| Strings | High-Byte zuerst, nullterminiert | „AE103" aus 32768–32770, „1.0.2.30" aus 10112–10115 |
| Adressierung | Roh, **kein** 30001-Offset | Registerwerte decken sich mit den YAML-Definitionen des Herstellers |
| Unit-IDs | 0 und 1 antworten, identisch | siehe Einschränkung unten |
| Maximale Blockgröße | 32 Register pro Anfrage nachweislich in Ordnung; größer nicht getestet | Scan arbeitete durchgängig mit count=32 |

### Kritische Protokolleigenheit: Start-/Count-Validierung

Das Gerät validiert die **Kombination aus Startadresse und Count**, nicht jede
Adresse einzeln. Ein Einzelread auf 10039 wirft Exception 2, während
`10038 count=2` gültig ist.

Das Muster ist an den 575 Einzelreads eindeutig ablesbar. Erfolgreich mit
`count=1` waren:

```
10018, 10022, 10026, 10030, 10034, 10036, 10038, 10040-10047
```

Das sind exakt die **Startadressen der 32-Bit-Objekte** (10018
`pv_total_generation`, 10036 `max_charge_power`, 10038 `max_discharge_power`)
sowie der zusammenhängende 16-Bit-Bereich 10040–10047. Die jeweils folgende
Adresse — 10019, 10037, 10039 — wirft Exception 2.

**Konsequenz für die Implementierung:** Leseblöcke müssen auf gültigen
Startadressen aufsetzen und dürfen kein 32-Bit-Objekt zerschneiden. Die Lücken
sind real und bestimmen die Blockgrenzen.

### Einschränkung zur Unit-ID

Der Scan hat **13 Unit-IDs** geprüft: 0, 1, 2, 3, 4, 5, 6, 10, 16, 32, 100,
200, 246, 247. Davon antworteten 0 und 1; die übrigen liefen in Timeout.
Die Aussage „2–247 antworten nicht" ist damit **nicht belegt** — belegt ist,
dass eine Stichprobe von zwölf weiteren Unit-IDs nicht antwortete.
Unit 0 wurde nur **ein einziges Mal** abgefragt; „Unit 0 und 1 sind derselbe
Server" beruht auf dieser einen Stichprobe.

---

## 2. Nachweislich lesbare Adressen

Abgeleitet aus allen erfolgreichen Antworten, 248 Register insgesamt:

```
10000            10002-10003      10008-10009      10014
10018            10022            10026            10030
10034            10036-10079      10090-10175      10183
10187            10199            10202            10205
10208-10239      10250            10252            10254
10256            10262            10264            32768-32799
60000-60031
```

Nichts unterhalb 10000, nichts oberhalb 60031.

**Wichtig:** Der Bereich 10000–10035 ist **nicht** als Block lesbar. Ein
`count=32`-Read ab 10000 schlägt fehl. Die dort liegenden Größen wurden
einzeln beziehungsweise als 32-Bit-Paar gelesen.

### Belegte Blockstartadressen mit count=32

```
10040   10048   10112   10144   10208   32768   60000
```

Nur diese sieben sind als 32er-Block bestätigt. Andere Startadressen sind
ungetestet, nicht widerlegt.

---

## 3. Registertabelle

Spalte „Sicherheit":
**sicher** = gegen App, HA-Historie oder Herstellerdefinition verifiziert ·
**plausibel** = konsistente Deutung, nicht unabhängig bestätigt ·
**unbestimmt** = Wert bekannt, Bedeutung offen

### 3.1 Leistung und Energie

| Adresse | FC | Typ | Skalierung | Deutung | Sicherheit | Beleg |
|---|---|---|---|---|---|---|
| 10001 | 04 | UINT16 | 1 | `battery_status`: 0 Standby, 1 Laden, 2 Entladen, 3 Sleep | sicher | Hersteller-YAML |
| 10002 | 04 | INT32 | 1 W | `pv_power`, Summe aller Stränge | sicher | Hersteller-YAML, HA-Entity |
| 10004 | 04 | INT32 | 1 W | `third_party_pv_power` | sicher | Hersteller-YAML (`internal: true`) |
| 10008 | 04 | INT32 | 1 W | Batterieleistung. **Negativ = Laden.** Ein Register, in HA per `power_split_mode` auf zwei Entities aufgeteilt | sicher | Hersteller-YAML |
| 10010 | 04 | INT32 | 1 W | `load_power` | sicher | Hersteller-YAML |
| 10012 | 04 | INT32 | 1 W | Netzleistung. **Negativ = Einspeisung.** Ebenfalls ein Register, zwei Entities | sicher | Hersteller-YAML |
| 10014 | 04 | UINT16 | 1 % | `battery_soc` | sicher | Hersteller-YAML, HA-Entity |
| 10018 | 04 | UINT32 | ÷10 kWh | `pv_total_generation` | sicher | Hersteller-YAML |
| 10036 | 04 | INT32 | 1 W | `max_charge_power`, gelesen: 3000 | sicher | Hersteller-YAML, Messwert |
| 10038 | 04 | INT32 | 1 W | `max_discharge_power` = **AC-Ausgangslimit**, gelesen: 800 | sicher | Hersteller-YAML, deckt sich mit App-Limit |
| 10208 | 04 | INT32 | 1 W | `ac_grid_output_power` | sicher | Hersteller-YAML |
| 10250 | 04 | UINT32 | ÷10 kWh | `rated_energy` | sicher | Hersteller-YAML |
| 10262 | 04 | UINT32 | ÷10 kWh | kumulierte Ladeenergie | sicher | Hersteller-YAML |
| 10264 | 04 | UINT32 | ÷10 kWh | kumulierte Entladeenergie | sicher | Hersteller-YAML |

### 3.2 DC-Strangdaten — der Kernbefund

| Adresse | FC | Typ | Skalierung | Deutung | Sicherheit | Beleg |
|---|---|---|---|---|---|---|
| 10167 | 04 | UINT16 | ÷10 V | Strang 1 Spannung | sicher | App-Vergleich |
| 10168 | 04 | UINT16 | ÷100 A | Strang 1 Strom | sicher | App-Vergleich |
| 10169 | 04 | UINT16 | ÷10 V | Strang 2 Spannung | sicher | App-Vergleich |
| 10170 | 04 | UINT16 | ÷100 A | Strang 2 Strom | sicher | App-Vergleich |
| 10171 | 04 | UINT16 | ÷10 V | Strang 3 Spannung | sicher | App-Vergleich |
| 10172 | 04 | UINT16 | ÷100 A | Strang 3 Strom | sicher | App-Vergleich |
| 10173–10175 | 04 | UINT16 | — | **Konstant null** über 109 Messpunkte, während Strang 4 produzierte | sicher (als Nullbefund) | Langlauf 14:03–15:52 |

**Verifikation gegen die Anker-App, 11.08.2026 14:40 Uhr:**

| Strang | Register | gemessen | App | Abweichung |
|---|---|---|---|---|
| 1 | 10167 × 10168 | 29,9 V × 14,0 A = 419 W | 418 W | 0,2 % |
| 2 | 10169 × 10170 | 29,9 V × 14,1 A = 422 W | 413 W | 2,2 % |
| 3 | 10171 × 10172 | 32,4 V × 8,3 A = 268 W | 273 W | 1,8 % |
| 4 | — | nicht gefunden | 60 W | — |

**Zweiter, unabhängiger Beleg (Physik):** Über 110 Minuten fielen die Ströme,
während die Spannungen stiegen. Das ist die Kennlinie einer Solarzelle —
sinkende Einstrahlung senkt den Strom nahezu proportional, die begleitende
Abkühlung hebt die Spannung. Eine Batterie oder ein Zwischenkreis verhält sich
gegenläufig.

**Strang 4 ist auf Modbus nicht auffindbar.** Siehe Abschnitt 5.

### 3.3 Netzqualität

| Adresse | FC | Typ | Skalierung | Deutung | Sicherheit | Beleg |
|---|---|---|---|---|---|---|
| 10199 | 04 | UINT16 | ÷10 V | Netzspannung, Messpunkt A | plausibel | Wertebereich 240,6–243,8 V |
| 10202 | 04 | UINT16 | ÷10 V | Netzspannung, Messpunkt B | plausibel | wie oben |
| 10224 | 04 | UINT16 | ÷10 V | Netzspannung, Messpunkt C | plausibel | wie oben |
| 10227 | 04 | UINT16 | ÷10 V | Netzspannung, Messpunkt D | plausibel | wie oben |
| 10213 | 04 | UINT16 | ÷100 Hz | Netzfrequenz | sicher | 49,94–50,05 Hz, physikalisch eindeutig |
| 10238 | 04 | UINT16 | ÷100 Hz | Netzfrequenz, Zweitmessung | sicher | identischer Verlauf zu 10213 |
| 10205 | 04 | UINT16 | ÷100 A | **AC-Ausgangsstrom** | **sicher** | siehe unten |

**Verifikation von 10205.** Über 29 Messpunkte am Abend des 11.08.2026 wurde
`AC-Leistung (10208) ÷ Netzspannung (10224) × 100` gegen den Rohwert von 10205
gerechnet:

| Zeit | AC-Leistung | Netzspannung | berechnet ×100 | 10205 | Differenz |
|---|---|---|---|---|---|
| 17:28:26 | 680 W | 240,2 V | 283 | 282 | +1 |
| 17:31:26 | 730 W | 240,1 V | 304 | 300 | +4 |
| 17:34:26 | 710 W | 240,9 V | 295 | 293 | +2 |
| 17:40:26 | 800 W | 240,7 V | 332 | 332 | 0 |
| 17:41:56 | 520 W | 240,4 V | 216 | 219 | −3 |

Mittlere Abweichung 2,5 Rohwerte, also **0,025 A**; maximal 0,05 A.
Korrelation mit der AC-Leistung **r = +0,996**.

Zur Abgrenzung: die Korrelation desselben Registers mit dem Restwert, der
Strang 4 entspricht, beträgt **r = +0,297**. 10205 ist damit als
Strang-4-Kandidat **ausgeschlossen**.

Ob die vier Spannungsmesspunkte Phasen sind, ist **ungeklärt**. Deshalb neutrale
Bezeichner A–D statt L1–L3. Ein falsches Label wäre schlimmer als ein
nichtssagendes, weil es eine Deutung suggeriert, die nicht belegt ist.

### 3.4 Gerät und Zustand

| Adresse | FC | Typ | Skalierung | Deutung | Sicherheit | Beleg |
|---|---|---|---|---|---|---|
| 10060 / 10061 | 03 | UINT32 | Unix-Sekunden UTC | **Gerätezeit, live mitlaufend** | sicher | auf ±2 s gegen Wanduhr geprüft; Highword 27259 konstant, Lowword zählt |
| 10064 | 03 | UINT16 | 1 | `operating_mode`, gelesen: 0 = `self_consumption` | sicher | Hersteller-YAML, deckt sich mit HA-Select |
| 10071 / 10072 | 03 | INT32 | 1 W | `battery_power_setpoint` / Richtung, High- und Lowword. **Nicht anfassen** — Sollwert der Nulleinspeisungsregelung, wird von der offiziellen Integration per FC16 beschrieben | sicher | Hersteller-YAML, `select.py:429` |
| 10090–10092 | 04 | STRING | — | Modellkennung „AE103" | sicher | ASCII-Dekodierung |
| 10100–10111 | 04 | STRING ×12 | — | Seriennummer AK7DN7M0G21100441 | sicher | Hersteller-YAML, ASCII |
| 10112–10115 | 04 | STRING ×6 | — | Firmware „1.0.2.30" | sicher | ASCII: 0x312E 0x302E 0x322E 0x3330 |
| 32768–32772 | 03 | STRING ×5 | — | Modell „AE103" | sicher | ASCII: 0x4145 0x3130 0x3300 |
| 32774 | 03 | UINT16 | Bitmaske | `ems_mode_mask`, gelesen: 111 = 0x6F | sicher | Bits 0,1,2,3,5,6 gesetzt, Bit 4 frei → alle Modi außer „Socket Overlay" |

### 3.5 Konfiguration (Holding, vom Hersteller beschrieben)

| Adresse | FC | Typ | Deutung | gelesen | Sicherheit |
|---|---|---|---|---|---|
| 60000 | 03 | UINT16 | Ladeobergrenze SOC % | 100 | sicher |
| 60001 | 03 | UINT16 | Entladegrenze SOC % | 5 | sicher |
| 60002 | 03 | UINT16 | Notstromreserve SOC % | 5 | sicher |
| 60003 | 03 | UINT16 | `backup_soc_enable` | 0 = aus | sicher |
| 60004–60031 | 03 | UINT16 | konstant null | 0 | unbestimmt |

**Diese Register bedient die offizielle Integration bereits schreibend als
`number`-Entities. Niemals selbst beschreiben.**

### 3.6 Neu identifiziert: 10040 / 10041

| Adresse | FC | Typ | Deutung | Sicherheit | Beleg |
|---|---|---|---|---|---|
| 10041 | 04 | UINT16, bytegepackt | **Highbyte = Batterie-SOC in Prozent.** Lowbyte konstant 1 | **sicher** | siehe unten |
| 10040 | 04 | UINT16, bytegepackt | konstant 0x0101 | unbestimmt | 109 Messpunkte |
| 10042–10047 | 04 | UINT16 | konstant null | unbestimmt | 109 Messpunkte |

**Verifikation.** Das Highbyte von 10041 stieg im Langlauf monoton von 85 auf
100 und blieb dort stehen. Gegenprobe gegen die Recorder-Historie von
`sensor.anker_solix_solarbank_4_e5000_pro_441_soc`:

| Zeit (lokal) | 10041 Highbyte | HA-SOC |
|---|---|---|
| 14:03 | 85 | 85 |
| 14:12 | 86 | 86 |
| 14:21 | 87 | 87 |
| 14:30 | 88 | 88 |
| 14:39 | 90 | 90 |
| 14:48 | 91 | 91 |
| 14:57 | 93 | 93 |
| 15:06 | 94 | 94 |
| 15:15 | 96 | 96 |
| 15:24 | 97 | 97 |
| 15:34 | 100 | 100 |

Elf von elf Stichproben deckungsgleich.

**Hypothese zu den Nachbarregistern, ausdrücklich unbewiesen:** 10040/10041
könnten ein bytegepacktes Datensatzpaar je Akkueinheit sein (0x0101 =
Einheit vorhanden, dann SOC + Status). Dann wären 10042–10047 die Plätze für
**Erweiterungsakkus** — derzeit null, weil keine verbaut sind. Testbar nur
durch Anbau eines Erweiterungsakkus. Bis dahin: unbestimmt.

### 3.7 Unbestimmte Register

Alle folgenden sind lesbar, ihre Bedeutung ist offen. Der **Blockkontext** ist
die eigentliche Information: Wer ein Register im AC-Block über Wochen
beobachtet, sucht nach etwas Netzbezogenem, nicht nach einer Batteriegröße.

| Adresse | Beobachtung | Vorgeschlagener Name |
|---|---|---|
| 10074 | 1 | Unbekannt Konfigblock 2 |
| 10075 / 10076 | je 65535 (= −1 als INT16, oder „nicht gesetzt") | Unbekannt Konfigblock 3 / 4 |
| 10079 | konstant 10000 | Unbekannter Grenzwert 1 |
| 10118–10121 | ASCII „.1.0.203", vermutlich zweite Versionszeichenkette | Unbekannt Geräteinfo 1 |
| 10124 | 18772 = 0x4954 = ASCII „IT" | Unbekannt Geräteinfo 2 |
| 10125 | 57356 = 0xE00C | Unbekannt Geräteinfo 3 |
| 10130 | 23809 = 0x5D01 | Unbekannt Geräteinfo 4 |
| 10133 | 9480 = 0x2508 | Unbekannt Geräteinfo 5 |
| 10156 | **Nur zwei Zustände: 370 und 380.** Siehe Abschnitt 5 | Unbekannt Stufenwert 1 |
| 10183 | isolierte gültige Adresse | Unbekannt Einzelregister 1 |
| 10187 | isolierte gültige Adresse | Unbekannt Einzelregister 2 |
| 10230 | variabel 25–36 | Unbekannt AC-Block 1 |
| 10234 | variabel 0–4 | Unbekannt AC-Block 2 |
| 10236 | variabel 59–90 | Unbekannt AC-Block 3 |
| 10252 / 10256 | im Energieblock | Unbekannt Energieblock 1 / 2 |
| 32775–32799 | konstant null | Unbekannt Modellblock 1 ff. |

**Zu 10230 und 10236 ausdrücklich:** Beide korrelieren mit dem SOC-Verlauf
(r ≈ −0,72 beziehungsweise −0,70). Das ist **kein Befund**. Der SOC stieg im
Messfenster monoton, deshalb korreliert jede fallende Größe mit ihm. Ohne ein
Messfenster mit nicht-monotonem SOC ist daraus nichts abzuleiten.

---

## 4. Nicht vorhanden

Trotz vollständigem Adressraumscan **nicht** auf Modbus verfügbar:

- Zellspannungen
- Zyklenzahl
- Fehler- oder Statuscodes
- Batterie- oder Gerätetemperaturen
- Wirkungsgrade
- Erweiterungsakku-Slots (siehe aber die Hypothese in 3.6)

Der **Anker Smart Meter Gen 2** antwortet nicht unter eigener Unit-ID. Seine
Registerdefinition 10620–10702 liefert unter Unit 0 wie Unit 1 und mit FC03 wie
FC04 durchgehend Exception 2. Er ist ein eigenständiges Modbus-Gerät mit eigener
IP-Adresse.

---

## 5. Strang 4: Stand der Beweisführung

**Widerlegt: 10156 ist nicht die Spannung von Strang 4.**

Über 109 Messpunkte in 110 Minuten nimmt 10156 **exakt zwei Werte** an, 370 und
380, und springt zwischen ihnen hin und her, statt der Tageszeit zu folgen. Zum
Vergleich, im selben Fenster:

| Register | Spannweite | verschiedene Werte |
|---|---|---|
| 10156 | 370–380 | **2** |
| 10167 Strang 1 | 295–374 | 25 |
| 10169 Strang 2 | 294–369 | 27 |
| 10171 Strang 3 | 258–349 | 43 |

Eine gemessene Modulspannung hat im selben Zeitraum 25 bis 43 Abstufungen.
Zwei Zustände in 1,0-V-Quantisierung sind ein Stufen- oder Nennwert, keine
Messgröße. Hinzu kommt: 37,0–38,0 V liegen **über jedem plausiblen Vmp** dieses
Moduls — selbst bei 0 °C wären es nur 35,3 V. Das entspricht etwa 0,94 × Voc,
also nahe Leerlauf; ein Modul nahe Leerlauf liefert aber keine 3,3 A.

**Weiteres Ausschlussargument:** 10173, 10174 und 10175 — also genau die Plätze,
an denen ein viertes Paar nach dem Schema 10167/68, 10169/70, 10171/72 stehen
müsste — sind über den gesamten Langlauf **konstant null**, obwohl Strang 4 in
diesem Fenster produzierte.

**Vollständigkeitsprüfung:** In den beprobten Blöcken 10040–10071, 10144–10175
und 10208–10239 variiert **kein** Register mit Strangsignatur. Bewegt haben sich
nur die drei bestätigten Stränge, die Gerätezeit, der SOC, der AC-Ausgang,
zweimal Netzfrequenz, zweimal Netzspannung und die drei AC-Block-Unbekannten,
deren Wertebereiche (25–36, 0–4, 59–90) nicht zu 0–16 A passen.

**Offen bleibt:** 10205 war in **keiner** Zeitreihe enthalten — der Langlauf las
die Blöcke 10144:32, 10208:32 und 10040:32, und 10205 liegt in keinem davon.
Für den endgültigen Ausschluss fehlt eine Messung über den Sonnenuntergang, die
10205 einschließt. Entscheidungsregel: Fallen 10168, 10170 und 10172 nach
Sonnenuntergang auf null und 10205 ebenfalls, ist 10205 der vierte Strang.
Bleibt 10205 bei etwa 330 stehen, sind drei von vier Strängen über Modbus
lesbar und der vierte nicht.

**Erledigt: auch 10205 ist ausgeschlossen.** Es war der letzte Kandidat und hat
sich am Abend des 11.08.2026 als AC-Ausgangsstrom erwiesen, siehe Abschnitt 3.3.

### Die Restwertmethode: Strang 4 messen, ohne ihn zu finden

Das Gerät liefert seine eigene Gegenprobe. Register 10002 ist die
**Gesamt-PV-Leistung** über alle vier Stränge. Damit gilt:

```
PV4 = pv_total(10002) - (U1*I1 + U2*I2 + U3*I3)
```

Die Methode ist gegen Home Assistant kalibriert: Um 17:25:49 Ortszeit lieferte
Register 10002 den Wert 690 W, und `sensor.…_441_solarstrom` stand in derselben
Sekunde ebenfalls auf 690 W. Die drei bestätigten Stränge ergaben zusammen
544 W, der Restwert also **146 W** — plausibel gegen die App-Ablesung von 120 W
fünf Minuten zuvor.

Damit ist Strang 4 **beobachtbar, ohne dass sein Register existiert**. Für
Verschattungsanalyse und Ertragsbilanz reicht das; was fehlt, sind Spannung und
Strom getrennt, also der Arbeitspunkt.

**Einschränkung, die dazugehört:** Der Restwert ist eine Differenz großer
Zahlen. Er schwankt im 30-Sekunden-Takt zwischen 78 und 210 W, während die
Gesamtleistung glatt von 690 auf 520 W fällt. Ursache ist die
Nichtgleichzeitigkeit: 10002 und die Strangregister werden vom Gerät nicht im
selben Moment aktualisiert. Der **Mittelwert** über mehrere Minuten ist
belastbar, der Einzelwert nicht.

**Stand der Beweislast:** Strang 4 hat kein eigenes Registerpaar. Geprüft und
ausgeschlossen sind 10173–10175 (konstant null bei Produktion), 10156
(Stufenwert in 1,0-V-Schritten), 10205 (AC-Ausgangsstrom) sowie sämtliche
variablen Register der Blöcke 10040–10071, 10144–10175 und 10208–10239.

---

## 6. Moduldaten

**Sakete SKT500M12-108D4**, N-Typ Doppelglas bifazial, 108 Halbzellen,
1961 × 1134 × 30 mm, 23,5 kg. Vier Stück à 500 Wp, koplanar auf einer
Dachfläche, Azimut 188°, Neigung 20°, je ein eigener MPP-Tracker.

| | STC | NMOT |
|---|---|---|
| Pmax | 500 W | 377,5 W |
| Voc | 39,90 V | 37,84 V |
| Vmp | 33,18 V | 31,02 V |
| Imp | 15,07 A | 12,17 A |
| Isc | 15,93 A | 12,89 A |

Temperaturkoeffizienten: Voc −0,250 %/°C · Pmax −0,290 %/°C · Isc +0,045 %/°C
NMOT-Zelltemperatur 45 ± 2 °C bei 800 W/m² und 20 °C Umgebung
Vmp/Voc bei STC: **0,832**

```
Voc(T) = 39.90 * (1 - 0.0025 * (T_zelle - 25))
Vmp(T) = 33.18 * (1 - 0.0025 * (T_zelle - 25))
T_zelle_rueckgerechnet = 25 + (1 - V_gemessen / 33.18) / 0.0025
```

Solarbank-Tracker: vier Stück à 1250 W, MPP-Fenster 16–50 V, maximal 36 A.

---

## 7. Physische Modulzuordnung

**Geklärt am 11.08.2026, 18:30.** Grundlage sind zwei unabhängige Angaben:

1. Die Registerzuordnung zu den App-Kanälen PV1–PV3 ist am 14:40-Wertevergleich
   belegt (Abweichung 0,2 / 2,2 / 1,8 %), PV4 ergibt sich als Restwert.
2. Der Betreiber hat die Reihenfolge auf dem Dach angegeben und ein Foto
   geliefert: „ganz nahe PV4, ganz weit weg PV1", Blickrichtung der Aufnahme
   **nach Westen**. Nahes liegt damit östlich von Fernem.

| Register | App-Kanal | Lage in der Reihe |
|---|---|---|
| 10167 / 10168 | PV1 | westlichstes Modul |
| 10169 / 10170 | PV2 | |
| 10171 / 10172 | PV3 | |
| Restwert | PV4 | östlichstes Modul |

**Sicherheit:** Die Registerzuordnung ist gemessen. Die Zuordnung der App-Kanäle
zu den Dachpositionen ist eine **Angabe des Betreibers aus der Installation**,
keine Messung. Die unabhängige Gegenprobe wäre weiterhin, ein Modul kurz
abzudecken und zu beobachten, welcher Strom einbricht.

### Folge für die Verschattungshypothese

Die ursprüngliche Annahme — eine Schattenkante wandert nachmittags von
West/Südwest über die Reihe, der Verursacher steht westlich — ist mit dieser
Zuordnung **nicht haltbar**. Die Messdaten zeigen das Gegenteil:

- **14:40**, Sonne bei Azimut 206°, Elevation 51,1°: Das **Ostende** ist
  verschattet. PV3 auf 65 %, PV4 auf 14 %; PV1 und PV2 laufen voll. Ein Schatten
  bei diesem Sonnenstand zeigt nach Nordnordost — das Hindernis steht also
  **südsüdwestlich des Ostendes** und nah, denn es trifft nur zwei von vier
  Modulen.
- **14:40 bis 18:00**: PV4 steigt von 60 auf 130 W, während die Gesamtleistung
  von 1160 auf 550 W fällt. Wandert die Sonne nach Westen, dreht der Schatten
  desselben Hindernisses nach Osten und läuft über die Dachkante hinaus. Das
  östlichste Modul kommt frei — gegen den Trend der Anlage.

**Prüfbare Vorhersage:** Morgens muss es umgekehrt sein. Sonne im Osten, Schatten
nach Westen — PV1 und PV2 starten schwach, PV3 und PV4 stark. Trifft das nicht
zu, ist die Deutung falsch.

---

## 8. Messung vom 11.08.2026, 14:40 Uhr

| Modul | Spannung | Strom | Leistung | Anteil | zurückgerechnete Zelltemperatur |
|---|---|---|---|---|---|
| Strang 1 | 29,9 V | 13,97 A | 418 W | 100 % | ~57 °C |
| Strang 2 | 29,9 V | 14,12 A | 413 W | 99 % | ~57 °C |
| Strang 3 | 32,4 V | 8,28 A | 273 W | 65 % | **~34 °C** |
| Strang 4 | — | — | 60 W (App) | 14 % | — |

Monotoner Abfall entlang der Reihe. Strang 3 war rund 23 °C kühler — ein
verschattetes Modul heizt sich nicht auf. Höhere Spannung bei niedrigerem Strom
ist die Doppelsignatur von Verschattung.

**Nebenbefund, geklärt:** Die gemessenen ~30 V sind **kein** falscher
Arbeitspunkt. Vmp beträgt 33,18 V, temperaturkorrigiert auf 57 °C sind das
30,7 V. Die Module liefen im Optimum.

---

## 9. Methodik und Belegquellen

| Quelle | Umfang |
|---|---|
| `scan_log.jsonl` | 5069 Anfragen, Adressraum 0–65535, FC01–FC04, 13 Unit-IDs |
| `longrun_teil1.jsonl` | 109 Messpunkte im 60-s-Takt, 12:03–13:52 UTC, 96 Register |
| `timeseries.jsonl` | 29 Messpunkte im 10-s-Takt |
| Hersteller-YAML | `custom_components/anker_solix_official/config/58f0132b…yaml` |
| Anker-App | Einzelablesung 11.08.2026 14:40 |
| HA-Recorder | `sensor.…_441_soc`, 14:03–15:53 |

**Verworfene Auswertung:** Eine frühere Korrelationsanalyse über ein Fenster mit
nur 5 % Variation der PV-Leistung ergab für die Netzfrequenz (Register 10213,
mit Sicherheit nicht PV-getrieben) einen Koeffizienten von r = −0,83. Dieses
Register diente danach als Negativkontrolle; alle r-Werte aus jenem Datensatz
sind ungültig. Die Strangzuordnung stützt sich deshalb auf direkten
Absolutwertvergleich mit der App, nicht auf Korrelation.

**Die Herstellerdefinitionen für Solarbank Max, Max AC und E5000 Pro 4 sind
byte-identisch.** Die DC-Register fehlen in der offiziellen Integration also
nicht aus Rücksicht auf das Max-AC-Modell — die Integration kennt für **kein**
Modell welche.

---

## 10. Koexistenz mit `anker_solix_official` 1.4.1

Quellcodeanalyse der installierten Integration, Belege als Datei:Zeile.

### Was sie liest, alle 5 Sekunden, sieben Anfragen

| Function Code | Bereiche |
|---|---|
| FC04 (input) | 10000–10050 · 10090–10156 · 10208–10265 · 32768–32774 |
| FC03 (holding) | 10060–10072 · 10074–10081 · 60000–60003 |

Dazu bei jedem Verbindungsaufbau ein FC04-Read auf 32768, count 5
(`modbus_client.py:441`).

**Der entscheidende Punkt: 10167–10172 liegen in der Lücke zwischen 10156 und
10208.** Die offizielle Integration fasst die Strangregister nicht an — weder
lesend noch schreibend. Ein zweiter Leser dort erzeugt keine Überschneidung.

### Was sie schreibt

| Adresse | FC | Auslöser |
|---|---|---|
| 10064 | 06 | `operating_mode`-Select **und** einmalig Wert 3 beim allerersten Connect (`auto_mode_on_connect: 3`, Hersteller-YAML Zeile 14) |
| 10071 + 10072 | 16 | `battery_power_setpoint` und Richtungswechsel |
| 60000 | 06 | Ladeobergrenze SOC |
| 60001 | 06 | Entladegrenze SOC |
| 60002 | 06 | Notstromreserve SOC |

### Verbindungsverhalten, relevant für einen zweiten Client

- **Dauerhafte TCP-Sitzung**, Socket-Timeout 10 s, `retries=0`
  (`modbus_client.py:107`). Idle-Cleanup nach 300 s greift bei 5-s-Polling nie.
- **Vor jedem Schreibvorgang wird die Verbindung abgerissen und neu aufgebaut**
  (`modbus_manager.py:262-277`). In diesem Moment entsteht kurzzeitig ein
  zusätzlicher Verbindungsaufbau. Ein zweiter Client muss vereinzelte Timeouts
  tolerieren, statt das Gerät sofort als offline zu melden.
- Locks sind reine `asyncio`-Locks **innerhalb** der HA-Eventloop
  (`coordinator.py:78`, `modbus_manager.py:43-46`). Sie serialisieren nur die
  eigene Instanz und schützen einen zweiten Client **nicht**.
- Backoff bei Ausfall: ≤3 Fehler → 10 s, ≤10 → 30 s, ≤30 → 60 s, danach 300 s
  (`coordinator.py:640-648`).
- Es wird **keine** Unit-/Slave-ID an pymodbus übergeben (verifiziert per Grep
  über das gesamte Paket); es gilt der pymodbus-Default. Ein eigener Client
  sollte Unit 1 **explizit** setzen.

### Identität, die ein zweites Gerät meiden muss

- Domain `anker_solix_official` (`const.py:3`, `manifest.json:2`)
- Device-Identifier `(DOMAIN, entry_id)` (`coordinator.py:119-124`)
- `connections` wird **nirgends** gesetzt — es gibt also keinen
  MAC-Verschmelzungsvektor, solange ein zweites Gerät ebenfalls keinen setzt.
- Gerätename nach dem ersten Poll: `"<Produktname> (<letzte 3 Zeichen der SN>)"`
  (`coordinator.py:320-336`). Ein zweites Gerät darf diesen Namen nicht
  wiederholen, sonst hängt HA an den generierten Entity-IDs stumm `_2` an.

### Übernehmenswerte Muster

Bei Verbindungsverlust setzt die Integration `_latest_data = {}` und pusht
sofort `async_set_updated_data({})` (`coordinator.py:615-619`). Entities werden
dadurch unmittelbar `unavailable`, statt alte Werte einzufrieren. Ergänzend
existiert ein Per-Register-Verfügbarkeitsset (`coordinator.py:475-515`), sodass
ein einzelnes defektes Register nicht das ganze Gerät abschaltet.
