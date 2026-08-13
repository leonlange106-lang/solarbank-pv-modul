# Gesundheitsueberwachung der Modbus-Integration

Stand 13.08.2026.

## Warum es das gibt

Am 13.08.2026 wurden an einem Tag drei Fehler gefunden, die alle seit Tagen
liefen und im Dashboard unauffaellig aussahen:

| Befund | Ursache | Wie es aussah |
|---|---|---|
| Nennkapazitaet dauerhaft `0,0` kWh | Register 10250 als u16 statt u32 gelesen; der Wert steckt im Lowword 10251 | eine plausible Null |
| PV-Leistung Fremdanlage dauerhaft `unknown` | 10004 lag ausserhalb des Leseblocks | eine leere Kachel |
| Strang 4 fehlte vollstaendig | kein eigenes Register, kein Differenzsensor | 25 % der Anlage unsichtbar |

Der gemeinsame Nenner: **die Integration liefert bei Stoerungen still falsche
Werte statt Fehler.** Ein eingefrorener plausibler Wert ist gefaehrlicher als
ein sichtbarer Ausfall, weil er geglaubt wird. Genau darauf zielt diese
Ueberwachung.

## Aufbau

Die Ueberwachung liegt bewusst auf zwei Ebenen:

```
custom_components/solarbank_pv/diagnose.py   meldet FAKTEN je Registergruppe
        |                                    (verworfene Bloecke, fehlende
        |                                     Register, letzte Abfrage)
        v
packages/solarbank_diagnose.yaml             BEWERTET sie
        |                                    (Schwellen, Warnung/Stoerung)
        v
sensor.solarbank_diagnose_gesamtzustand      ok | warnung | stoerung
```

Der Schnitt liegt dort, weil eine Schwelle in der YAML-Ebene ohne Neustart
aenderbar ist, ein Wert in der Integration nicht. Die Integration bewertet
deshalb nichts, sie berichtet nur.

### Warum ein Teil in der Integration stecken muss

Der gefaehrlichste Ausfall dieser Integration ist der **stille Blockausfall**.
Ein Leseblock, den das Geraet dreimal mit Ausnahme 2 ablehnt, wird nach
`MAX_BLOCK_FAILURES = 3` aus der Abfrage genommen (`coordinator.py`). Die
Gruppe liest danach weiter, nur ohne die Register dieses Blocks:

- kein Coordinator meldet einen Fehler
- keine Entity wird `unavailable`
- die betroffenen Werte gehen lautlos auf `unknown`

Von Home Assistant aus ist dieser Zustand **nicht erkennbar** — `dropped_blocks`
lebt in einem Python-Objekt, an das kein Template herankommt. Deshalb gibt es
je Gruppe einen `sensor.solarbank_diagnose_gruppe_<schluessel>` mit dem Zustand
`ok` / `teilausfall` / `ausfall` und dem Attribut `register_fehlend`, das die
**Adresse** nennt, nicht bloss die Tatsache.

Der Gesundheitssensor ueberschreibt `available` auf konstant `True`. Ohne das
wuerde ausgerechnet der Sensor, der den Ausfall melden soll, bei einem Ausfall
selbst `unavailable` — das Dashboard zeigte eine Luecke statt eines Alarms.

## Die Pruefungen

Schwelle, Begruendung, Bedeutung, Massnahme. Wer hier eine Zahl aendert,
aendert sie in `packages/solarbank_diagnose.yaml` mit.

### 1 Integration ausgefallen — Stoerung

`binary_sensor.solarbank_diagnose_integration_ausgefallen`

**Schwelle:** eine Gruppe im Zustand `ausfall`, oder ein Gesundheitssensor
fehlt ganz.

**Warum so:** Faengt drei Faelle in einem — Integration gar nicht geladen,
Integration geladen aber eine Gruppe liest nicht, Config-Entry defekt. Der
Zustand `ausfall` entspricht `coordinator.last_update_success is False`, also
einem Transportfehler auf TCP-Ebene.

**Bedeutung:** Die Modbus-Verbindung zu 192.168.178.86:502 steht nicht, oder
die Integration ist nicht hochgekommen.

**Massnahme:** Erreichbarkeit des Geraets pruefen. Attribut
`betroffene_gruppen` sagt, ob es alle Gruppen trifft (Netz/Geraet) oder nur
eine (dann eher ein Blockproblem).

### 2 Leseblock verworfen — Stoerung

`binary_sensor.solarbank_diagnose_leseblock_verworfen`

**Schwelle:** eine Gruppe im Zustand `teilausfall`, also mindestens ein
verworfener Block **oder** ein gefordertes Register fehlt im letzten Abbild.

**Warum so:** Kein Toleranzband moeglich und keines noetig — ein gefordertes
Register ist da oder nicht. Genau dieser Test haette den Fremdanlagen-Befund
(10004 ausserhalb des Blocks) am ersten Tag gemeldet.

**Bedeutung:** Das Geraet lehnt eine Start/Count-Kombination ab, oder ein
Register wurde in `const.py` eingetragen, ohne dass ein Block es abdeckt.

**Massnahme:** Attribut `fehlende_register` nennt Gruppe und Adresse. Danach
in `const.py` pruefen, ob ein `Block` die Adresse ueberhaupt abdeckt.
`verworfene_bloecke` nennt die konkrete `Start:Count`-Kombination.

### 3 Daten eingefroren — Stoerung

`binary_sensor.solarbank_diagnose_daten_eingefroren`

**Schwelle:** `last_reported` eines Gruppensensors aelter als
`2 x Gruppenintervall + 60 s`.

**Warum genau diese Groesse — und warum `last_reported`, nicht `last_updated`:**

Das ist der wichtigste Test, weil er die Fehlerklasse vom 13.08. direkt trifft.
Er haengt aber an der richtigen Zeitmarke. `last_updated` springt **nur bei
einer Wertaenderung**. Gemessen am 13.08. um 11:37:

```
sensor...pv_nennkapazitaet_modbus = 5,1   last_updated 1678 s   last_reported 9 s
```

Der Wert ist voellig korrekt und die Abfrage laeuft im 30-s-Takt — ueber
`last_updated` waere dieser Sensor trotzdem "seit 28 Minuten eingefroren". Der
Alarm waere binnen eines Tages verrauscht und damit wertlos. `last_reported`
wandert dagegen bei jedem Schreibvorgang mit, auch wenn der Wert gleich bleibt,
und steht genau dann still, wenn der Coordinator wirklich stehenbleibt.

Der Faktor 2 stammt daher, dass ein einzelner verpasster Poll normal ist, zwei
hintereinander nicht. Die 60 s decken den Minutentakt, in dem Home Assistant
Templates mit `now()` neu rechnet, plus Jitter. Je Gruppe ergibt das:

| Gruppe | Intervall | Schwelle |
|---|---|---|
| `strings` | 30 s | 120 s |
| `mirror` | 30 s | 120 s |
| `grid` | 60 s | 180 s |
| `limits` | 300 s | 660 s |
| `unknown` | 300 s | 660 s |
| `clock` | 3600 s | 7260 s |

**Bedeutung:** Der Coordinator plant nicht mehr. Die Entities halten ihre
letzten Werte und sehen weiterhin plausibel aus — der gefaehrlichste Zustand
ueberhaupt.

**Massnahme:** Attribut `eingefrorene_gruppen` nennt Gruppe und Alter.
Integration neu laden; wenn das hilft, ins Log sehen, warum sie stehenblieb.

### 4 Entities unavailable — Stoerung

`binary_sensor.solarbank_diagnose_entities_unavailable`

**Schwelle:** mindestens eine Entity des Geraets im Zustand `unavailable`.

**Warum nur `unavailable` und ausdruecklich nicht `unknown`:** Mehrere
abgeleitete Groessen liefern **planmaessig** `unknown`, wenn ihre Voraussetzung
fehlt — die Zelltemperatur unterhalb von 5 A, der Stromanteil nachts. Am
13.08. um 11:37 stand `sensor.pv_modul_1_zelltemperatur` bei voller Sonne auf
`unknown`, weil Modul 1 verschattet war und unter 5 A lag. Ein Test auf
`unknown` wuerde jede Nacht und bei jeder Verschattung ausloesen und waere nach
zwei Wochen unsichtbar. Fehlende **Rohregister** faengt Pruefung 2 praeziser
ab, weil sie die Adresse nennt.

### 5 Energiebilanz — Stoerung

`binary_sensor.solarbank_diagnose_bilanzabweichung_momentan`
→ `sensor.solarbank_diagnose_bilanzabweichung_anteil_1h`
→ `binary_sensor.solarbank_diagnose_bilanzabweichung_dauerhaft`

**Schwelle:** momentan `|Summe(Modul 1..4) − Gesamtleistung| > max(25 W, 3 %)`,
Befund erst wenn dieser Zustand ueber 60 % der letzten Stunde anhaelt.

**Warum ueberhaupt eine Toleranz, wo die Rechnung doch exakt ist:** Modul 4 ist
als Differenz definiert, die Summe **muss** aufgehen — aber nur innerhalb
desselben Abfragezyklus. Die vier Modulleistungen kommen aus dem
`strings`-Coordinator, die verglichene Gesamtleistung
(`sensor.solarbank_dc_straenge_441_pv_leistung_gesamt_modbus`) aus dem
`mirror`-Coordinator. Beide laufen mit 30 s, aber **versetzt**. Bei ziehenden
Wolken entstehen daraus echte Differenzen von mehreren hundert Watt aus reinem
Zeitversatz. Dazu kommt, dass Register 10002/10003 die Gesamtleistung nur in
**10-W-Stufen** liefert (gemessen ueber 1461 Messpunkte des 12.08.).

Ein exakter Vergleich waere nur gegen die Gesamtleistung **aus dem
strings-Zyklus** moeglich, und die ist nicht als Entity ausgewiesen. Deshalb:
grosszuegige Momentantoleranz plus Dauerhaftigkeitspruefung. Ein Zeitversatz
erzeugt kurze Spitzen, ein Deutungsfehler einen Dauerzustand.

**Bedeutung:** Eine Deutung stimmt nicht — entweder die Gesamtleistung oder
einer der drei gemessenen Straenge.

**Massnahme:** `abweichung_w` im Attribut. Vorzeichen beachten: positive
Abweichung heisst, die Module summieren sich zu mehr als das Ganze, also ist
Modul 4 auf null geklemmt (siehe Pruefung 8).

### 6 Querpruefung gegen die offizielle Integration — Warnung

`binary_sensor.solarbank_diagnose_querabweichung_momentan`
→ `sensor.solarbank_diagnose_querabweichung_anteil_1h`
→ `binary_sensor.solarbank_diagnose_querabweichung_dauerhaft`

**Schwelle:** momentan `|Modbus − offiziell| > max(60 W, 8 %)`, Befund erst bei
ueber 60 % Anteil in der letzten Stunde.

**Warum die Trennung ausdruecklich noetig ist:** Beide lesen dasselbe Geraet,
aber die offizielle Integration pollt im Sekundenbereich und die Modbus-Seite
alle 30 s. An einer Wolkenkante liegen dazwischen leicht mehrere hundert Watt,
**ohne dass irgendetwas kaputt waere**. Wuerde der Momentanwert alarmieren,
klingelte das Handy an jedem bewoelkten Tag — und ein Alarmkanal, der zu oft
klingelt, wird ignoriert. Deshalb wird nicht der Momentanwert bewertet, sondern
sein **Zeitanteil**: ein Zeitversatz erzeugt kurze Spitzen (kleiner Anteil), ein
Lesefehler einen Dauerzustand (Anteil gegen 100 %).

Zur Kalibrierung: am 13.08. um 11:37 standen beide Seiten exakt auf 1330 W,
um 11:52 exakt auf 1190 W. Die Uebereinstimmung im Normalbetrieb ist also sehr
gut, 8 % sind reichlich Luft.

**Warum nur Warnung:** Eine Abweichung sagt, dass **eine** Seite falsch liest,
aber nicht welche. Das ist ein Prueffall, kein Ausfall.

### 7 Plausibilitaetsgrenzen — Stoerung

`binary_sensor.solarbank_diagnose_messwert_unplausibel`

**Schwellen:**

| Groesse | Band | Begruendung |
|---|---|---|
| Strangspannung | 16–50 V, **nur bei Strom > 1 A** | MPP-Fenster laut Geraetespezifikation |
| Strangstrom | Betrag ≤ 36 A | Geraetegrenze; Imp des Moduls ist 15,07 A |
| Zelltemperatur | −20 bis +95 °C | physikalisch sinnvolles Band fuer ein Modul |
| AC-Ausgangsstrom | Betrag ≤ 36 A | wie Strangstrom |

**Warum die Spannung nur unter Last:** Ohne Strom faehrt der Strang Richtung
Leerlauf und verlaesst das MPP-Fenster voellig regulaer; nachts steht er nahe
null. Ohne diese Bedingung waere der Test jede Nacht rot.

**Bedeutung:** Skalierungs- oder Vorzeichenfehler. Genau so faellt der
INT16-Fehler auf: als vorzeichenlos gelesen wurden aus −0,08 A ganze 655,28 A.

**Massnahme:** Attribut `befunde` nennt Modul, Groesse und Wert. Dann `kind`
und `scale` des betroffenen Registers in `const.py` pruefen.

### 8 Modul 4 dauerhaft auf null geklemmt — Warnung

`binary_sensor.solarbank_diagnose_modul_4_geklemmt_momentan`
→ `sensor.solarbank_diagnose_modul_4_geklemmt_anteil_6h`
→ `binary_sensor.solarbank_diagnose_modul_4_dauerhaft_geklemmt`

**Schwelle:** Attribut `auf_null_geklemmt` gesetzt **und** Gesamtleistung
> 100 W; Befund bei ueber 25 % Anteil in 6 Stunden.

**Warum die Produktionsbedingung:** Nachts sind alle Summanden null und die
Differenz besteht nur aus Rundungsrauschen — ein kleiner negativer Rest ist
dann normal. Ueber den Tagesverlauf des 12.08. gemessen: 199 von 1461
Messpunkten geklemmt, ganz ueberwiegend bei schwachem Licht.

**Bedeutung:** Die Differenz wird unter Last dauerhaft negativ, die drei
gemessenen Straenge liefern also mehr als die gemeldete Gesamtleistung. Dann
stimmt eine Deutung nicht.

### 9 Werte stehen still trotz Produktion — Stoerung

`binary_sensor.solarbank_diagnose_werte_unveraendert`

**Schwelle:** `sensor.pv_modul_2_strom` **und** `sensor.pv_modul_3_strom` seit
ueber 60 Minuten unveraendert (`last_changed`), waehrend
`sensor.anker_solix_..._solarstrom` ueber 150 W meldet.

**Warum ein unabhaengiger Gegenzeuge:** Der Kern des Tests ist, dass eine
**andere** Quelle belegt, dass sich etwas bewegen muesste. Ohne ihn waere der
Test zirkulaer — stuende die Modbus-Seite still, saehe auch ihre eigene
Leistung konstant aus und der Test bliebe stumm.

**Warum hier `last_changed` und nicht `last_reported`:** Gefragt ist, ob sich
der **Wert** bewegt, nicht ob geschrieben wurde. Das ist die Gegenprobe zu
Pruefung 3, die genau umgekehrt fragt.

**Warum zwei Straenge:** Ein einzelner Strang kann bei gleichmaessiger
Einstrahlung durchaus lange auf demselben Digit stehen. Zwei gleichzeitig ueber
eine Stunde nicht.

### 10 Offizielle Integration stumm — Warnung

`binary_sensor.solarbank_diagnose_offizielle_integration_stumm`

**Schwelle:** kein Wert, oder `last_reported` aelter als 10 Minuten.

**Warum es das gibt:** `solarbank_pv` oeffnet eine zweite TCP-Verbindung zum
selben Geraet. `anker_solix_official` darf dadurch nicht wegbrechen.

**Warum nur Warnung und mit 10 Minuten so grosszuegig:** Diese Integration
haengt an der Anker-Cloud. Kurze Aussetzer kommen dort vor und haben mit
unserer Verbindung nichts zu tun. Ein anhaltendes Verstummen dagegen ist genau
der Zustand, der nicht eintreten darf.

## Gesamtzustand und Alarmierung

`sensor.solarbank_diagnose_gesamtzustand` kennt drei Werte:

- **`stoerung`** — mindestens ein Befund aus 1, 2, 3, 4, 5, 7, 9
- **`warnung`** — mindestens ein Befund aus 6, 8, 10
- **`ok`** — kein Befund

Das Attribut `befunde` traegt die Klartextliste. Die Benachrichtigung liest sie
von dort und wiederholt die Logik nicht.

| Automation | Zustand | Entprellung | Kanal |
|---|---|---|---|
| `solarbank_diagnose_alarm_bei_stoerung` | `stoerung` | 5 min | Push **und** persistente Meldung |
| `solarbank_diagnose_hinweis_bei_warnung` | `warnung` | 15 min | nur persistente Meldung |
| `solarbank_diagnose_entwarnung` | `ok` | 10 min | raeumt beide Meldungen ab |

Die Entprellung laeuft ueber das **native `for:`**, nicht ueber eine
Zeitrechnung im Template. Fuenf Minuten sind mehr als das Doppelte des
laengsten schnellen Intervalls und ueberstehen damit einige verpasste Polls.

### Warum jede Automation zwei Ausloeser hat

Das ist keine Redundanz aus Vorsicht, sondern die Reparatur eines **im Test
gefundenen Fehlers**.

Die erste Fassung hatte nur einen Zustandstrigger
(`to: stoerung`, `for: 00:05:00`). Beim Provozieren am 13.08. stand der
Gesamtzustand auf `stoerung`, die Befundliste war korrekt gefuellt — und die
Automation loeste **auch nach sechs Minuten nicht aus**, `last_triggered` blieb
`null`.

Grund: Ein Zustandstrigger braucht ein **Aenderungsereignis**. Steht die
Entity beim Laden der Automation bereits im Zielzustand, gibt es keinen
Uebergang und damit nie eine Ausloesung. Im Betrieb heisst das: kommt Home
Assistant hoch, waehrend die Integration nicht laedt oder das Geraet nicht
erreichbar ist, rendert der Gesamtzustand sofort `stoerung` — ohne Uebergang.
**Der Alarm haette in genau dem Fall geschwiegen, fuer den er gebaut ist.**

Deshalb jetzt je Automation:

1. der Zustandstrigger mit `for:` als schneller Weg
2. ein `time_pattern` alle fuenf Minuten als Netz darunter

Die eigentliche Pruefung liegt in der **Bedingung**, deren eigenes `for:`
dieselbe Entprellung leistet — unabhaengig davon, ob je ein Uebergang
stattfand. Ein `input_boolean`-Latch je Kanal macht das idempotent; ohne ihn
meldete das Zeitmuster alle fuenf Minuten erneut.

Nach dem Umbau feuerte der Alarm bei erneutem Test **exakt fuenf Minuten** nach
dem Zustandswechsel (12:10:47 -> 12:15:47).

Warnungen gehen bewusst **nicht** aufs Handy. Ein Alarmkanal, der zu oft
klingelt, wird ignoriert — dann ist auch die echte Stoerung verloren.

Der Push laeuft ueber `notify.send_message` an `notify.iphone_von_schleon`, den
Kanal, den die Anlage bereits fuer sicherheitsrelevante Meldungen nutzt. Er
traegt `continue_on_error: true` und steht **vor** der persistenten Meldung: am
12.08. ist ein Push an einem Token-Problem gescheitert. Ein fehlgeschlagener
Push darf die Meldung nicht verschlucken.

`input_boolean.solarbank_diagnose_alarm_aktiv` und
`input_boolean.solarbank_diagnose_hinweis_aktiv` sind die Latches. Ohne sie
wuerde die Entwarnung auch dann feuern, wenn nie ein Alarm ausging — etwa nach
einem Neustart, der kurz durch `stoerung` laeuft. Die Entwarnung prueft den
Alarm-Latch **vor** dem Zuruecksetzen und schickt einen Push nur dann, wenn
zuvor auch einer rausging.

## Wie das geprueft wurde

Ein Alarm, der nie ausgeloest hat, ist unbewiesen. Der Ablauf am 13.08.:

1. Schwelle von Pruefung 3 in der **ausgerollten** Datei von `2 * iv + 60` auf
   `-1` gesetzt, sodass sie immer zutrifft. `homeassistant.reload_all`.
2. `binary_sensor.solarbank_diagnose_daten_eingefroren` ging auf `on`,
   `sensor.solarbank_diagnose_gesamtzustand` auf `stoerung` mit dem Befund
   „Daten eingefroren, Gruppe aktualisiert nicht mehr".
3. Erster Durchgang: **kein Alarm** nach sechs Minuten — der oben beschriebene
   Trigger-Fehler. Automationen umgebaut.
4. Zweiter Durchgang: Zustandswechsel 12:10:47, Ausloesung 12:15:47, Latch auf
   `on`, persistente Meldung mit korrektem Klartext vorhanden.
5. Schwelle aus dem Repo zurueckgespielt, `reload_all`, Gesamtzustand wieder
   `ok`, Entwarnung raeumt Latch und Meldungen ab.

Beim Provozieren fiel nebenbei auf, dass in Schritt 2 das Attribut
`eingefrorene_gruppen` leer blieb: die Testaenderung traf nur die Formel im
State, nicht die im Attribut. Im ausgelieferten Stand rechnen beide dieselbe
Formel — der Unterschied war ein Artefakt des chirurgischen Testeingriffs.

## Was bewusst nicht geprueft wird

- **Register-Rohwerte der Gruppe `unknown` auf Plausibilitaet.** Ihre Deutung
  ist offen; eine Grenze waere geraten. Sie werden ueber Pruefung 2 und 3 auf
  Vorhandensein und Aktualitaet ueberwacht, mehr laesst sich redlich nicht
  sagen.
- **Absolute Ertragsplausibilitaet** (etwa "mittags muessten es X kW sein").
  Das braucht ein Einstrahlungsmodell und wuerde bei jeder Wolke falsch
  ausloesen. Die Querpruefung gegen die offizielle Integration leistet dasselbe
  ohne Modell.
- **Der Recorder wurde nicht angefasst.** Die `exclude`-Liste in
  `configuration.yaml` bleibt unveraendert — die drei `history_stats`-Sensoren
  **brauchen** ihre Quell-Binaersensoren in der Historie, ein Ausschluss wuerde
  sie stillegen.

---

# Zuordnung der Straenge zur Dachflaeche

**Vom Betreiber am 13.08.2026 per Foto belegt.** Bis dahin war die Zuordnung
offen und in `input_select.pv_modul_N_dachposition` als `unbestaetigt: ...`
gefuehrt.

Blick auf die Dachflaeche, **von rechts nach links**:

| Strang | Position in der Reihe |
|---|---|
| PV1 | ganz rechts |
| PV2 | daneben |
| PV3 | daneben |
| PV4 | ganz links |

Damit ist die **raeumliche Reihenfolge** gesichert. Eine Himmelsrichtung ist
damit **nicht** belegt: `rechts` und `links` beziehen sich auf die
Blickrichtung des Fotos, die nicht dokumentiert ist. Die frueher im Dashboard
gefuehrte Beschriftung "PV1 West / PV4 Ost" stammte aus dem Registervergleich
und war nie bestaetigt — sie ist deshalb entfernt worden. Das Dashboard stellt
die Module jetzt in der Reihenfolge der Dachflaeche dar (links im Bild = PV4).

## Der Schattenwerfer ist der Giebel des gegenueberliegenden Hauses

**Am 13.08.2026 vom Betreiber per Foto belegt.** Das gegenueberliegende Haus
hat ein Satteldach mit Spitze, keine gerade horizontale Kante.

Ein Giebel wirft einen **Lambda-foermigen Schatten**: die Spitze reicht am
weitesten, die beiden Schenkel laufen schraeg nach aussen. Wandert dieser
Schatten ueber die Modulreihe, trifft er sie nicht gleichmaessig von einer
Seite. Ein Randmodul kann voll in der Sonne stehen, waehrend der direkte
Nachbar tief im Schatten liegt.

Zwei Messungen, die das belegen:

**13.08., Sonnenazimut 165,4 Grad, Elevation 52,1 Grad** — die Spitze steht
ueber PV2, beide Randmodule liegen ausserhalb der Schenkel:

| Strang | Position | Leistung | Spannung |
|---|---|---|---|
| PV1 | ganz rechts | 403 W | 29,1 V |
| PV2 | daneben | **35,5 W** | **33,5 V** |
| PV3 | daneben | 260 W | 31,6 V |
| PV4 | ganz links | 441 W | — |

**11.08. um 14:40** — der Schatten ist weitergewandert und breiter geworden,
ein Schenkel erfasst die linke Seite: PV1 100 %, PV2 99 %, PV3 65 %, PV4 14 %.

**Eine einzige Geometrie erklaert beide Bilder.** Eine frueher notierte
Vermutung, es muesse mehrere unabhaengige Schattenwerfer geben, ist damit
gegenstandslos.

PV2 zeigt dabei die Doppelsignatur eines verschatteten Strangs lehrbuchmaessig:
**hoechste Spannung bei niedrigstem Strom**. Die Zelltemperatur von PV2 steht
folgerichtig auf `unknown` statt auf einer erfundenen Zahl, weil bei 1,06 A die
Untergrenze von 5 A greift.

### Warum das fuer die Ausbauentscheidung zaehlt

Eine feste Giebelgeometrie ist ueber den **Sonnenazimut** sauber beschreibbar
und damit ueber die Jahreszeiten extrapolierbar: das Hindernis steht fest im
Raum, nur der Sonnenstand wandert. Im Winter steht die Sonne tiefer, der
Schatten reicht weiter. Genau dafuer ist die Azimut-Indizierung des Profils in
[`VERSCHATTUNG-PROFIL.md`](VERSCHATTUNG-PROFIL.md) die richtige Wahl — und
genau deshalb ist ein Profil **je Modul** noetig: die Gesamtkurve der Anlage
verdeckt, dass zu jedem Zeitpunkt ein anderes Modul betroffen ist.

---

# Strang 4: was gemessen ist und was geschaetzt

Getrennter Abschnitt, weil hier zum ersten Mal Entities entstehen, die **keine
Messung** sind.

## Die Lage

| Groesse | Status | Warum |
|---|---|---|
| **Leistung** `sensor.pv_modul_4_leistung` | **exakt** | Differenz zweier Messgroessen: Gesamtleistung minus die drei gemessenen Straenge |
| **Leistungsanteil** `sensor.pv_modul_4_leistungsanteil` | **exakt** | Verhaeltnis exakter Groessen |
| **Verschattet** `binary_sensor.pv_modul_4_verschattet` | **exakt** | ueber den Leistungsanteil |
| Spannung `sensor.pv_modul_4_spannung_geschaetzt` | **geschaetzt** | aus einem Produkt lassen sich zwei Faktoren nicht zurueckgewinnen |
| Strom `sensor.pv_modul_4_strom_geschaetzt` | **geschaetzt** | folgt aus der geschaetzten Spannung |

Die Annahme fuer Spannung und Strom: vier identische, koplanare Module mit je
eigenem MPP-Tracker fuehren dieselbe MPP-Spannung. Also `V4 = Median(V1..V3)`
und `I4 = P4 / V4`.

## Die Annahme ist beziffert, nicht behauptet

`tools/kreuzvalidierung_pv4.py` schaetzt fuer jeden der **drei bekannten**
Straenge die Spannung aus den beiden uebrigen und haelt sie gegen die Messung.
Grundlage sind die 1025 Messpunkte unter Last des Tageslaufs vom 12.08.
(`tools/rohdaten/pv4_tag.jsonl`, 1461 Messpunkte gesamt, 09:02–19:09 Ortszeit).

Relativer Fehler der geschaetzten **Spannung**:

| Lage | n | Median | p90 | p95 | max | Bias |
|---|---|---|---|---|---|---|
| ohne Verschattung | 2325 | 0,48 % | 3,87 % | 5,54 % | 18,75 % | +0,04 % |
| **Zielstrang selbst verschattet** | 250 | **9,56 %** | 12,35 % | 12,89 % | 16,71 % | **−9,47 %** |
| nur Nachbar verschattet | 500 | 5,90 % | 11,45 % | 12,12 % | 15,15 % | +5,39 % |
| Fenster 12:30–15:30 | 783 | 5,80 % | 11,62 % | 12,21 % | 15,15 % | +0,34 % |

Daraus folgender Fehler des geschaetzten **Stroms** (`I = P / V`, P exakt):

| Lage | Median | p95 | Bias |
|---|---|---|---|
| ohne Verschattung | 0,48 % | 5,65 % | +0,02 % |
| **Zielstrang selbst verschattet** | **10,57 %** | 14,80 % | **+10,54 %** |

### Wie das zu lesen ist

Die Zeile **„Zielstrang selbst verschattet"** ist die entscheidende und trifft
PV4 genau dann, wenn PV4 im Schatten steht: die Spannung wird systematisch um
rund **9,5 % zu niedrig** und der daraus gerechnete Strom um rund **10,5 % zu
hoch** geschaetzt. Der Fehler ist **gerichtet**, nicht zufaellig — ein
verschattetes Modul faehrt hoehere Spannung, weil es kuehler ist.

Ein Median ueber drei Nachbarn hilft dagegen **nicht**. Er verwirft einen
verschatteten Nachbarn (Zeile „nur Nachbar verschattet", deren +5,39 % ein
Artefakt der Validierung sind — sie bildet den Median aus nur zwei Werten,
der Schaetzer im Feld aus drei). Die Verschattung des Zielstrangs selbst bleibt
ihm unsichtbar.

### Warum die Werte trotzdem geliefert werden und nicht `unknown`

Ein gerichteter Fehler bekannter Groesse ist auswertbar; eine Luecke im Graphen
ausgerechnet zur Verschattungszeit ist es nicht. Die Kurve behaelt Form und
Groessenordnung. Entscheidend ist, dass die Beeintraechtigung **maschinenlesbar
ausgewiesen** wird — beide Sensoren tragen:

```
gemessen:                     false
deutung_sicher:               false
methode:                      geschaetzt, V4 = Median(V1..V3), I4 = P4 / V4
verschattung_beeintraechtigt: true | false | null
schaetzfehler_prozent:        1.0 oder 10.0
```

`schaetzfehler_prozent` schaltet automatisch auf 10, sobald der Leistungsanteil
Verschattung anzeigt. Das Dashboard zeigt diesen Wert an.

## Verschattung von Strang 4 laeuft ueber den Leistungsanteil

Der naheliegende Weg — Strom aus der Schaetzspannung zurueckrechnen und wie bei
PV1–3 den Stromanteil bilden — ist ausgerechnet hier der falsche: der Strom
wird bei Verschattung um 10,5 % **zu hoch** geschaetzt, der Stromanteil fiele
also zu guenstig aus und die Verschattung wuerde zu spaet erkannt. Blinder
Fleck genau dort, wo der Sensor gebraucht wird.

Der **Leistungsanteil** `P4 / Median(P1..P3)` braucht keine Spannungsannahme.
Ueber den Tageslauf: Median 101,0 % — Strang 4 verhaelt sich wie die anderen.

**Deshalb gibt es fuer Strang 4 bewusst keinen Stromanteil.**

### Gleichwertigkeit der beiden Masse

Geprueft an den drei gemessenen Straengen, wo beide Masse verfuegbar sind:
ueber **3075 Messpunkte faellen Stromanteil und Leistungsanteil in 99,22 % der
Faelle dasselbe Verschattungsurteil** (24 Abweichungen). Median der Differenz
0,75 Prozentpunkte.

Damit ist belegt, dass Strang 4 nach demselben Massstab bewertet wird wie
PV1–3, obwohl er eine andere Kennzahl benutzt. Fuer die Vergleichbarkeit im
Dashboard tragen **alle vier** Module zusaetzlich einen Leistungsanteil; der
bestehende Stromanteil von PV1–3 bleibt unangetastet.

### Warum PV4 zwei Messpunkte Bestaetigung braucht

Register 10002/10003 liefert die Gesamtleistung nur in **10-W-Stufen**. P4 ist
eine Differenz gegen diesen groben Wert und erbt dessen Quantisierungsrauschen,
waehrend P1–P3 aus feinem `U x I` entstehen. Bei einer Referenz um 100 W ist
eine 10-W-Stufe ein Sprung von 10 Prozentpunkten im Verhaeltnis — genug, um das
Hysteresefenster 0,60/0,70 wiederholt zu durchschlagen, ohne dass sich am
Schatten etwas aendert.

Am Tageslauf des 12.08. gemessen:

| Bestaetigung | Flanken | verschattete Zeit |
|---|---|---|
| ohne (1 Messpunkt) | 42 | 24,1 % |
| **2 Messpunkte** | **20** | **24,0 %** |
| 3 Messpunkte | 12 | 25,9 % |

Zum Vergleich mit derselben Methode: PV1 20 Flanken, PV2 22, PV3 11.

Zwei Messpunkte bringen PV4 also **genau auf das Niveau der anderen drei**, und
die verschattete Zeit aendert sich dabei von 24,1 % auf 24,0 % — es verschwindet
Rauschen, keine Substanz. Die Schwellen `SHADE_ON = 0,60` und `SHADE_OFF = 0,70`
bleiben identisch zu PV1–3. Die Bestaetigung **stellt die Vergleichbarkeit her,
statt sie aufzuheben**.

## Was fuer Strang 4 bewusst fehlt

- **Zelltemperatur.** Sie wuerde aus der geschaetzten Spannung gerechnet, also
  Schaetzung auf Schaetzung. Der Spannungsfehler von 9,5 % bei Verschattung
  schluege ueber `25 + (1 − U/33,18)/0,0025` mit rund 38 K durch — das waere
  keine Temperatur mehr, sondern eine Zahl.
- **Stromanteil.** Begruendung oben.

## Reproduktion

```
python tools/kreuzvalidierung_pv4.py
```

Ohne Argument nimmt das Skript `tools/rohdaten/pv4_tag.jsonl`.
