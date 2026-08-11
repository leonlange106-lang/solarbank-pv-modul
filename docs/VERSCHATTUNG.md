# Messkampagne Verschattung — Entwurf

Stand: 11.08.2026 · Entscheidungstermin: Mitte September 2026 · **Nur Entwurf, nichts umgesetzt**

Ziel laut Auftrag: *„Verschattungsereignisse zusammen mit `sun.sun` (Azimut, Elevation)
aufzeichnen. Nach vier Wochen eine Aussage, bei welchem Sonnenstand welches Modul wie
stark einbricht."* Das Ergebnis geht in die Entscheidung „mehr Module oder mehr Speicher"
ein.

Dieses Dokument ist ein Bauplan, kein Protokoll. An der laufenden Instanz wurde nichts
geändert; das Modbus-Gerät unter 192.168.178.86 wurde nicht angefasst. Alle Aussagen über
den Bestand stammen aus lesenden Abfragen, jede ist unten mit ihrem Beleg versehen.

---

## 0. Zwei Befunde vorweg, die den Entwurf bestimmen

### 0.1 Sperrend: die Datenquelle existiert auf der Instanz noch nicht

| Prüfung | Ergebnis |
|---|---|
| `ha_search("pv_modul")` | 0 Entities |
| `ha_get_state` auf `sensor.pv_modul_1_leistung` u. a. | 7 × `ENTITY_NOT_FOUND` |
| `ls /config/custom_components/` | kein `solarbank_pv` |
| Repository `custom_components/solarbank_pv/` | `const.py`, `coordinator.py`, `modbus_reader.py`, `__init__.py`, `manifest.json` — **keine `sensor.py`, keine `binary_sensor.py`** |

`__init__.py` Zeile 34 lädt `PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR]`. Beide
Plattformmodule fehlen. Die Integration ist damit nicht lauffähig, und die im Auftrag
genannten Entities `sensor.pv_modul_n_*` / `binary_sensor.pv_modul_n_verschattet` sind
Entwurfsnamen, keine existierenden Objekte.

**Konsequenz für den Zeitplan.** Die Kampagne kann erst starten, wenn `sensor.py` und
`binary_sensor.py` geschrieben, die Integration installiert und ein Konfigurationseintrag
angelegt ist. Bis zum 15.09. sind es 35 Tage. Jeder Tag Verzug ist ein Tag weniger
Messung, und die Kampagne verliert überproportional: die letzten Tage vor der Entscheidung
liefern die niedrigsten Sonnenstände und damit die für den Horizont interessantesten
Punkte.

### 0.2 Sperrend für die Auswertung: `sun.sun` zeichnet Azimut und Elevation nicht auf

Der Auftrag lautet, die Ereignisse „zusammen mit `sun.sun` (Azimut, Elevation)"
aufzuzeichnen. Der naheliegende Weg — `sun.sun` mitschreiben und die Attribute später aus
der Historie lesen — **funktioniert nicht**. Beleg, zwei Abfragen im selben Zeitfenster:

```
ha_get_history("sun.sun", 15:00–15:30, minimal_response=false)
  → 8 Zeilen, attributes: {"friendly_name": "Sun"}          ← nur das

ha_get_history("sensor.anker_..._solarstrom", 15:00–15:03, minimal_response=false)
  → 26 Zeilen, attributes: {state_class, modbus_address, data_type,
     register_count, primary_value, unit_of_measurement, ...}   ← vollständig
```

Die Live-Abfrage von `sun.sun` liefert `elevation: 29.66`, `azimuth: 256.3` und acht
weitere Attribute. In der Historie ist davon nichts übrig. Die `sun`-Integration meldet
ihre Positionsattribute dem Recorder ausdrücklich als nicht aufzuzeichnen ab — sonst
schriebe sie rund um die Uhr Zeilen. Das ist sinnvoll, aber es heißt: **Azimut und
Elevation sind aus der Vergangenheit grundsätzlich nicht rekonstruierbar, nicht einmal
innerhalb der zehn Recorder-Tage.**

Zwei Auswege, beide werden im Entwurf genutzt:

1. **Kopieren.** Die Attribute in Template-Sensoren mit `state_class` spiegeln. Für die
   Elevation existiert das bereits: `sensor.sonne_elevation` in `templates.yaml`
   (`unique_id: sonne_elevation_grad`, `state_class: measurement`), aktuell `29.66`. Für
   den Azimut fehlt das Gegenstück — es wird unten angelegt.
2. **Nachrechnen.** Der Sonnenstand ist eine deterministische Funktion von Zeit und Ort.
   Aus dem Zeitstempel allein ist er exakt rekonstruierbar. Gegenprobe mit dem
   NOAA-Algorithmus für 51,7619 °N / 7,8766 °O (aus `zone.home`) gegen die Live-Ablesung:

   | Zeitpunkt | berechnet | `sun.sun` meldete | Abweichung |
   |---|---|---|---|
   | 11.08.2026 17:37:47 MESZ | Az 256,30° / El 29,63° | Az 256,30° / El 29,66° | **0,00° / 0,03°** |

   Damit gilt: **der Zeitstempel ist die eigentlich tragende Größe.** Azimut und Elevation
   werden trotzdem mitgeschrieben — als Selbstkontrolle und um die Auswertung von
   Zeitzonen- und Sommerzeitfehlern unabhängig zu machen —, aber sie sind redundant. Ein
   Datensatz ohne Sonnenstand wäre reparabel; ein Datensatz ohne verlässlichen Zeitstempel
   wäre wertlos.

### 0.3 Nebenbefund zur Arbeitshypothese

Die Arbeitshypothese lautet, eine Schattenkante wandere nachmittags von West/Südwest über
die Reihe, der Verursacher stehe **westlich**. Für den dokumentierten Messpunkt
(REGISTER.md §8, 11.08.2026 14:40, Modul 3 auf 65 %) ergibt die Rückrechnung:

```
11.08.2026 14:40 MESZ  →  Azimut 206,0°   Elevation 51,1°
```

Azimut 206° ist Südsüdwest, nicht West. Entscheidender ist die Elevation: Damit ein
Hindernis die Sonne bei **51,1°** verdeckt, muss seine Oberkante vom verschatteten Punkt
aus unter mehr als 51° erscheinen, also

```
Höhe über Modulebene / horizontaler Abstand  >  tan(51,1°) = 1,24
```

Ein Baum oder ein Nachbardach in 10 m Entfernung müsste dafür über 12 m über die
Modulebene ragen. Ein Schornstein in 3 m Entfernung braucht 3,7 m. **Der Verursacher ist
also mit hoher Wahrscheinlichkeit nah und hoch — ein Aufbau auf derselben Dachfläche —,
nicht ein entfernter Horizont im Westen.** Das ist ein Zwischenergebnis aus einem einzigen
Messpunkt, ausdrücklich nicht belegt; die Kampagne prüft es. Es ändert nichts am Entwurf,
aber es verschiebt die Erwartung, und es zeigt, dass die Kampagne die Hypothese tatsächlich
widerlegen kann.

---

## 1. Entwurfsentscheidung samt Begründung

### 1.1 Die Wahl: periodische Abtastung als Rückgrat, Flankenereignisse als Ergänzung

Gefordert war eine begründete Entscheidung zwischen einer Automation, die **bei jedem
Verschattungswechsel** einen Datensatz schreibt, und einer **periodischen Abtastung**.

**Die Entscheidung fällt auf periodische Abtastung alle zwei Minuten.** Die
ereignisgesteuerte Aufzeichnung wird zusätzlich betrieben, aber sie ist nicht tragend.

### 1.2 Warum die reine Ereignisaufzeichnung das Ziel verfehlt

Vier Einwände, in absteigender Schwere:

**(a) Sie liefert Kanten, aber keine Tiefe.** Gefragt ist „welches Modul *wie stark*
einbricht". Ein Flankenereignis sagt „Schwelle unterschritten", nicht „auf 65 %". Zwischen
zwei Flanken — das sind an einem klaren Tag womöglich vier Stunden — steht kein einziger
Wert. Die Amplitude, die eigentliche Zielgröße, wird nicht erfasst.

**(b) Das Totband verschluckt genau den interessanten Fall.** `const.py` Zeile 57 f. setzt
`SHADE_ON = 0.60`, `SHADE_OFF = 0.70`. Eine weiche Schattenkante — Halbschatten eines
Baums, Kante eines entfernten Dachs — kann eine halbe Stunde bei 62 bis 68 % verharren und
löst **nie** aus. Ein Modul, das jeden Nachmittag zuverlässig auf 65 % fällt, erzeugt in
der Ereignisaufzeichnung null Datensätze und wäre unsichtbar. Für eine Ausbauentscheidung
ist ein dauerhafter 35-%-Verlust hochrelevant.

**(c) Wolke und Bauwerk lösen identisch aus.** Ein Flankenereignis trägt keine Information
darüber, was die Ursache war. Um Wolke von Geometrie zu trennen, braucht man **Stichproben
desselben Sonnenstands an verschiedenen Tagen**. Genau die liefert nur ein regelmäßiges
Raster: dieselbe Zelle (Azimut × Elevation) wird über die Kampagne an vielen Tagen erneut
besucht, und über diese Wiederholungen bildet man einen Median. Eine Wolke ist an
verschiedenen Tagen an verschiedenen Stellen; ein Schornstein ist immer an derselben.
Ereignisdaten sind an den Zeitpunkten aufgehängt, an denen etwas passierte — sie sind
nach Konstruktion unbalanciert und lassen sich nicht zu einem Feld verrechnen.

**(d) Es fehlt die Referenz des unverschatteten Zustands.** Ohne Messpunkte aus derselben
Zelle im freien Zustand gibt es keinen Nenner für die Aussage „bricht um N Prozent ein".

### 1.3 Warum die Ereignisaufzeichnung trotzdem mitläuft

Sie kostet fast nichts (siehe §6) und liefert eine Größe, die das 2-Minuten-Raster nur
gröber auflöst: den **exakten Zeitpunkt des Kantendurchgangs**. Die Kante ist die schärfste
geometrische Information der ganzen Kampagne — der Punkt, an dem die Sonne hinter der
Oberkante des Hindernisses verschwindet. Ein Flankendatensatz lokalisiert ihn auf die
Sekunde, das 2-Minuten-Raster nur auf ±0,5° Azimut. Beide zusammen kosten weniger als eine
Variante allein an Denkarbeit, weil sie in dieselbe Datei im selben Format schreiben und
sich nur in der Spalte `quelle` unterscheiden.

### 1.4 Warum zwei Minuten

| Kriterium | Rechnung | Ergebnis |
|---|---|---|
| Datenquelle | `solarbank_pv` aktualisiert alle 30 s (`const.py:34`, `GROUPS["strings"].interval = 30`) | schneller als 30 s ist sinnlos |
| Winkelauflösung | Sonne wandert ~15°/h in Azimut → 0,5° je 2 min | feiner als die 5°-Zelle |
| Rasterbelegung | 26 317 Sonnenminuten (El > 5°) über 35 Tage | 13 158 Datensätze |
| Punkte je Zelle | 162 belegte 5°×5°-Zellen | **81 Punkte/Zelle im Mittel** |
| Unabhängige Tage je Zelle | entscheidend für Wolkenrobustheit | **Median 13 Tage/Zelle** |

13 unabhängige Tage je Zelle sind genug für einen belastbaren Median und dafür, dass eine
einzelne verregnete Woche das Ergebnis nicht kippt. Ein 1-Minuten-Raster verdoppelt das
Datenvolumen und gewinnt keine unabhängigen Tage hinzu — die zusätzliche Auflösung ist
innerhalb desselben Tages korreliert und trägt statistisch fast nichts bei. Ein
5-Minuten-Raster fiele auf 32 Punkte/Zelle; das wäre noch tragbar, würde aber die
Kantenlokalisierung auf ±1,25° Azimut verschlechtern.

**Getroffene Wahl: 2 Minuten.** Bei Bedarf über `input_number` nachjustierbar, ohne die
Automation anzufassen.

### 1.5 Was aufgezeichnet wird: Primitive, keine Ableitungen

Grundregel: **abgeleitete Größen sind später rekonstruierbar, gemessene nicht.** Deshalb
wandern in die Datei die Rohgrößen — Strom und Spannung je Strang —, und die
Prozentanteile, Leistungen und Zelltemperaturen werden in der Auswertung neu berechnet.

Das ist nicht Sparsamkeit, sondern Notwendigkeit. Der Anteilssensor der Integration ist als
„Strom im Verhältnis zum **Median der übrigen** Stränge" definiert. Mit nur drei messbaren
Strängen ist der „Median der übrigen" der Median aus zwei Werten, also deren Mittel — und
dieser Bezug ist verzerrt: Fällt Strang 3 aus, sinkt sein Anteil korrekt, **aber die
Anteile von Strang 1 und 2 steigen zugleich über 100 %**, weil ihr Nenner mitgefallen ist.
Die drei Anteile sind also nicht unabhängig, und eine Heatmap direkt aus ihnen wäre
irreführend. Aus den Rohströmen lässt sich in der Auswertung eine robustere Normierung
bilden (§4.2). Aus den Anteilen zurück auf die Ströme kommt man nicht.

Ebenso werden Zustände **wörtlich** protokolliert: `unknown` und `unavailable` gehen als
Zeichenkette in die Datei, nicht als 0. Eine Messlücke muss von einem gemessenen Nullwert
unterscheidbar bleiben — bei Nacht, bei Modbus-Timeout und bei der Zelltemperatur unter
0,5 A ist das der Unterschied zwischen „kein Wert" und „kein Strom".

### 1.6 Warum die Aufzeichnung nicht in die Datenbank geht

Vorweggenommen aus §2: Das Rückgrat der Kampagne ist eine **CSV-Datei**, nicht der
Recorder. Der Recorder läuft mit, aber nur als Netz mit grobem Maschenwerk.

---

## 2. Aufbewahrungsproblem und Lösung

### 2.1 Das Problem, belegt

| Größe | Wert | Beleg |
|---|---|---|
| Vorhaltezeit Recorder | **10 Tage** | `/config/gui_recorder.yaml`: `purge_keep_days: 10` |
| `recorder:`-Block in `configuration.yaml` | ohne `purge_keep_days` | Zeilen 27–33; HA-Standard wäre ebenfalls 10 |
| Datenbankgröße | **768,6 MiB** (805 953 536 B) | `ls -la /config/home-assistant_v2.db` |
| Kampagnendauer | 28–35 Tage | Auftrag |

Die Kampagne ist drei- bis dreieinhalbmal so lang wie das Gedächtnis der Datenbank. Am
Entscheidungstag wären die ersten drei bis vier Wochen gelöscht — also genau der Teil mit
den hohen Sonnenständen. Eine Aufzeichnung, die das nicht löst, ist wertlos.

### 2.2 Warum Long-Term Statistics allein nicht reichen

LTS halten dauerhaft, aber sie haben zwei Eigenschaften, die hier beide beißen:

**(a) Sie setzen `state_class` voraus.** Erfüllt: `const.py:161` setzt
`state_class: str | None = "measurement"` als Vorgabe, Strom und Spannung erben sie
(`_V`, `_A` in Zeile 176 f. überschreiben sie nicht). Für `binary_sensor` gibt es
grundsätzlich keine LTS.

**(b) Sie sind nach zehn Tagen stündlich.** Das ist der tödliche Punkt. HA hält
5-Minuten-Statistiken nur `purge_keep_days` lang; dauerhaft überlebt ausschließlich die
**Stundentabelle** mit min/mean/max. Die Sonne wandert in einer Stunde **15° in Azimut** —
über eine ganze 5°-Zelle hinweg und weiter. Ein Schattendurchgang, der zehn Minuten dauert,
verschwindet im Stundenmittel fast vollständig; ein Stundenminimum sagt „irgendwann in
dieser Stunde war ein Modul bei 60 %", aber nicht bei welchem Sonnenstand. **Genau die
Frage der Kampagne wird von LTS strukturell nicht beantwortet.**

LTS sind also keine Lösung, sondern bestenfalls eine Rückfallebene.

### 2.3 Die Lösung: dreischichtig

| Schicht | Medium | Auflösung | Haltbarkeit | Rolle |
|---|---|---|---|---|
| **1** | CSV-Datei auf Platte | 2 min, vollständig | **unbegrenzt** | **tragend** |
| 2 | Recorder (`states`) | 30 s | 10 Tage | Fehlersuche im laufenden Betrieb |
| 3 | LTS (`statistics`) | 1 h min/mean/max | unbegrenzt | Rückfallebene, Jahresbilanz |

**Schicht 1 löst das Problem vollständig.** Eine Datei unterliegt keiner Purge, wächst
nicht in die Datenbank hinein (§6: ~1,3 MiB gesamt), behält die volle Auflösung und ist
mit jedem Werkzeug auswertbar. Sie ist außerdem das einzige Medium, das die
Sonnenstandsspalten überhaupt tragen kann — siehe §0.2.

**Schicht 3 ist die Versicherung.** Bricht die Dateiaufzeichnung unbemerkt ab — Platte
voll, Pfad nicht mehr freigegeben, Integration entladen —, bleiben die stündlichen
Minima der Anteilssensoren erhalten. Daraus lässt sich die Kampagne nicht rekonstruieren,
aber man sieht *dass* und *ungefähr wann* etwas war, und man kann eine verkürzte Kampagne
nachziehen. Sie kostet ~8 MiB/Jahr (§6) und ist damit praktisch gratis. Der Watchdog in
§3.5 soll verhindern, dass es je darauf ankommt.

**Wichtig und leicht zu übersehen:** Schicht 3 hängt an Schicht 2. Wird eine Entity über
`recorder: exclude` ausgeschlossen, entstehen für sie **auch keine Statistiken**. Der
Ausschluss ist kein Filter auf die `states`-Tabelle, sondern auf den Recorder insgesamt.
Deshalb darf in §5 nur ausgeschlossen werden, was auch in LTS entbehrlich ist.

### 2.4 Wohin die Datei geschrieben wird

Die `file`-Integration schreibt nur in Verzeichnisse, die in `allowlist_external_dirs`
stehen. Vorgeschlagen: `/config/verschattung/verschattung.csv`.

Alternative, ohne neue Integration: Auf der Instanz ist **pyscript** installiert und mit
`allow_all_imports: true`, `hass_is_global: true` konfiguriert (`configuration.yaml`
Zeilen 63–65). Ein pyscript-Service kann die Datei ohne Allowlist anlegen, den Kopf
selbständig schreiben und atomar anhängen. Der Entwurf gibt in §3.6 beide Varianten; die
YAML-Variante ist die vorgeschlagene, weil sie ohne Python auskommt und der Auftrag
vollständige YAML verlangt.

---

## 3. Vollständige YAML für Helfer und Automationen

Alle Blöcke sind **additiv**. Bestehende Schlüssel werden ergänzt, nicht ersetzt.

> **Anmerkung zur Methodik.** Der Home-Assistant-Styleguide bevorzugt Helfer über die
> Oberfläche gegenüber YAML-Template-Sensoren. Der Auftrag verlangt ausdrücklich
> vollständige YAML, deshalb steht sie hier. Wo ein eingebauter Helfer den
> Template-Sensor schlägt, ist das vermerkt und der Helfer wird verwendet
> (`min_max` statt Template-Aggregation, `threshold` statt Template-Schwelle,
> `counter` statt `input_number`-Zählerei).

### 3.1 Neue Template-Sensoren — Anhang an `templates.yaml`

Die Datei besteht bereits aus einer Liste von `- sensor:`-Blöcken (drei Stück, zuletzt
`Sonne Elevation` und ein `- switch:`). Der folgende Block wird **angehängt**.

```yaml
- sensor:
    # Gegenstueck zum bestehenden sensor.sonne_elevation. Ohne diesen Sensor ist der
    # Azimut nachtraeglich nicht verfuegbar - sun.sun meldet seine Positionsattribute
    # dem Recorder als nicht aufzuzeichnen ab.
    - name: "Sonne Azimut"
      unique_id: sonne_azimut_grad
      unit_of_measurement: "°"
      state_class: measurement
      icon: "mdi:compass-outline"
      availability: "{{ state_attr('sun.sun', 'azimuth') is not none }}"
      state: "{{ state_attr('sun.sun', 'azimuth') | float(0) | round(2) }}"

    # Strang 4 ist auf Modbus nicht auffindbar (REGISTER.md Abschnitt 5). Seine Leistung
    # ist aber als Differenz zugaenglich: Register 10002 fuehrt die Summe ueber alle
    # Straenge. Verifikation an der Messung vom 11.08.2026 14:40 steht in Abschnitt 7.
    # Bewusst NICHT auf 0 begrenzt: ein dauerhaft negativer Wert ist das Warnsignal
    # dafuer, dass die beiden Quellen zeitlich auseinanderlaufen.
    - name: "PV Modul 4 Leistung"
      unique_id: pv_modul_4_leistung
      unit_of_measurement: "W"
      device_class: power
      state_class: measurement
      icon: "mdi:solar-panel"
      availability: >
        {{ has_value('sensor.anker_solix_solarbank_4_e5000_pro_441_solarstrom')
           and has_value('sensor.pv_modul_1_leistung')
           and has_value('sensor.pv_modul_2_leistung')
           and has_value('sensor.pv_modul_3_leistung') }}
      state: >
        {{ ((states('sensor.anker_solix_solarbank_4_e5000_pro_441_solarstrom') | float(0))
            - (states('sensor.pv_modul_1_leistung') | float(0))
            - (states('sensor.pv_modul_2_leistung') | float(0))
            - (states('sensor.pv_modul_3_leistung') | float(0))) | round(0) }}

    # Anteil von Modul 4 am besten der drei messbaren Module. Bezug ist bewusst das
    # Maximum und nicht der Median: bei nur drei Referenzstraengen verschiebt ein
    # verschattetes Modul den Median, das Maximum bleibt beim unverschatteten Modul.
    - name: "PV Modul 4 Anteil"
      unique_id: pv_modul_4_anteil
      unit_of_measurement: "%"
      state_class: measurement
      icon: "mdi:percent-outline"
      availability: >
        {{ has_value('sensor.pv_modul_4_leistung')
           and has_value('sensor.pv_modul_1_leistung')
           and has_value('sensor.pv_modul_2_leistung')
           and has_value('sensor.pv_modul_3_leistung') }}
      state: >
        {% set ref = [states('sensor.pv_modul_1_leistung') | float(0),
                      states('sensor.pv_modul_2_leistung') | float(0),
                      states('sensor.pv_modul_3_leistung') | float(0)] | max %}
        {{ 0 if ref < 50 else
           ((states('sensor.pv_modul_4_leistung') | float(0)) / ref * 100) | round(1) }}
```

### 3.2 Eingebaute Helfer — Anhang an `configuration.yaml`

`min_max` und `threshold` sind eingebaute Integrationen und dem Template-Sensor
vorzuziehen: sie behandeln `unavailable` deklarativ und bringen im Fall von `threshold`
eine Hysterese mit.

```yaml
# Schwaechstes der vier Module in einer Zahl. Traegt state_class und damit LTS - das
# ist die Rueckfallebene aus Abschnitt 2.3.
sensor:
  - platform: min_max
    name: "PV Verschattung schwaechster Anteil"
    unique_id: pv_verschattung_schwaechster_anteil
    type: min
    round_digits: 1
    entity_ids:
      - sensor.pv_modul_1_stromanteil
      - sensor.pv_modul_2_stromanteil
      - sensor.pv_modul_3_stromanteil
      - sensor.pv_modul_4_anteil

# Stabiler Himmel. Nutzt den bereits vorhandenen Streuungssensor der Anlage
# (Helfer "PV Signal Streuung 5min", 5-Minuten-Standardabweichung der PV-Summe).
# Die Schwelle 50 W ist aus dem bestehenden Template "PV Drosselung Leistung"
# uebernommen, das dieselbe Groesse mit streu < 50 auswertet.
binary_sensor:
  - platform: threshold
    name: "PV Himmel stabil"
    unique_id: pv_himmel_stabil
    entity_id: sensor.saunaraum_anker_solix_solarbank_4_e5000_pro_441_pv_signal_streuung_5min
    lower: 50
    hysteresis: 10
```

### 3.3 Steuerhelfer — Anhang an `configuration.yaml`

Die bestehenden `input_*`-Helfer der Anlage liegen in `.storage` (über die Oberfläche
angelegt). YAML-definierte Helfer koexistieren damit problemlos, solange die IDs neu sind
— `pv_verschattung_*` ist frei.

```yaml
input_boolean:
  pv_verschattung_kampagne:
    name: "PV Verschattung Kampagne laeuft"
    icon: "mdi:record-rec"

input_number:
  pv_verschattung_min_elevation:
    name: "PV Verschattung minimale Elevation"
    min: 0
    max: 30
    step: 0.5
    initial: 5
    mode: box
    unit_of_measurement: "°"
    icon: "mdi:angle-acute"

input_datetime:
  pv_verschattung_start:
    name: "PV Verschattung Kampagnenstart"
    has_date: true
    has_time: true
    icon: "mdi:calendar-start"

counter:
  pv_verschattung_datensaetze:
    name: "PV Verschattung Datensaetze heute"
    icon: "mdi:counter"
    step: 1
```

### 3.4 Die Aufzeichnungsautomationen — Anhang an `automations.yaml`

Spaltenschema, identisch für beide Automationen:

```
ts;az;el;i1;i2;i3;u1;u2;u3;p_ges;p_3rd;streu5;prog;ac;soc;status;v1;v2;v3;quelle
```

> **Zur Schreibweise der Zeile.** Die gesamte CSV-Zeile steht in **einem einzigen**
> Jinja-Ausdruck, der die Felder mit `~` verkettet. Grund: Ein gefalteter YAML-Block
> (`>-`) ersetzt Zeilenumbrüche durch Leerzeichen — und stärker eingerückte
> Folgezeilen, wie sie hier stehen, behält er sogar als echte Zeilenumbrüche bei.
> Stünden mehrere `{{ }}`-Blöcke nebeneinander, geriete damit an jeder Umbruchstelle
> ein Leerzeichen oder ein Zeilenumbruch mitten in die CSV-Datei. Innerhalb *eines*
> Jinja-Ausdrucks ist Leerraum dagegen bedeutungslos: Jinja wertet ihn aus und gibt
> genau eine Zeile aus. Diese Form ist deshalb gegen beide Faltungsvarianten immun —
> auch dann noch, wenn jemand später die Einrückung ändert.

> **Zur Nichtbehandlung von Fehlwerten.** Es wird durchgängig `states(...)` ohne
> `| float()` geschrieben. Damit landet bei einem Modbus-Timeout wörtlich `unavailable`
> in der Datei statt einer erfundenen 0 (§1.5).

```yaml
- id: "pv_verschattung_abtastung"
  alias: "PV Verschattung: Abtastung"
  description: >-
    Schreibt alle zwei Minuten einen Datensatz nach
    /config/verschattung/verschattung.csv, solange die Kampagne laeuft und die Sonne
    ueber der eingestellten Mindestelevation steht. Rueckgrat der Kampagne. Der
    Zeitstempel ist die tragende Groesse - Azimut und Elevation sind daraus exakt
    rekonstruierbar und werden nur als Selbstkontrolle mitgefuehrt.
  triggers:
    - trigger: time_pattern
      minutes: "/2"
  conditions:
    - condition: state
      entity_id: input_boolean.pv_verschattung_kampagne
      state: "on"
    - condition: numeric_state
      entity_id: sensor.sonne_elevation
      above: input_number.pv_verschattung_min_elevation
  actions:
    - action: notify.send_message
      target:
        entity_id: notify.pv_verschattung_log
      data:
        message: >-
          {{ now().isoformat(timespec="seconds")
             ~ ";" ~ (state_attr('sun.sun', 'azimuth') | float(0) | round(3))
             ~ ";" ~ (state_attr('sun.sun', 'elevation') | float(0) | round(3))
             ~ ";" ~ states('sensor.pv_modul_1_strom')
             ~ ";" ~ states('sensor.pv_modul_2_strom')
             ~ ";" ~ states('sensor.pv_modul_3_strom')
             ~ ";" ~ states('sensor.pv_modul_1_spannung')
             ~ ";" ~ states('sensor.pv_modul_2_spannung')
             ~ ";" ~ states('sensor.pv_modul_3_spannung')
             ~ ";" ~ states('sensor.anker_solix_solarbank_4_e5000_pro_441_solarstrom')
             ~ ";" ~ states('sensor.pv_leistung_fremdanlage_modbus')
             ~ ";" ~ states('sensor.saunaraum_anker_solix_solarbank_4_e5000_pro_441_pv_signal_streuung_5min')
             ~ ";" ~ states('sensor.power_production_now')
             ~ ";" ~ states('sensor.anker_solix_solarbank_4_e5000_pro_441_ac_ausgang')
             ~ ";" ~ states('sensor.anker_solix_solarbank_4_e5000_pro_441_soc')
             ~ ";" ~ states('sensor.anker_solix_solarbank_4_e5000_pro_441_geratestatus')
             ~ ";" ~ states('binary_sensor.pv_modul_1_verschattet')
             ~ ";" ~ states('binary_sensor.pv_modul_2_verschattet')
             ~ ";" ~ states('binary_sensor.pv_modul_3_verschattet')
             ~ ";p" }}
    - action: counter.increment
      target:
        entity_id: counter.pv_verschattung_datensaetze
  mode: single
  max_exceeded: silent

- id: "pv_verschattung_flanke"
  alias: "PV Verschattung: Flanke"
  description: >-
    Schreibt zusaetzlich bei jedem Wechsel eines Verschattungsmelders. Liefert den
    Kantendurchgang auf die Sekunde genau, waehrend das 2-Minuten-Raster ihn nur auf
    etwa 0,5 Grad Azimut eingrenzt. Nicht tragend - die Hysterese 60/70 Prozent laesst
    weiche Kanten durchrutschen, deshalb ist die periodische Abtastung das Rueckgrat.
    mode queued, damit gleichzeitige Flanken mehrerer Module nicht verlorengehen.
  triggers:
    - trigger: state
      entity_id:
        - binary_sensor.pv_modul_1_verschattet
        - binary_sensor.pv_modul_2_verschattet
        - binary_sensor.pv_modul_3_verschattet
      to:
        - "on"
        - "off"
  conditions:
    - condition: state
      entity_id: input_boolean.pv_verschattung_kampagne
      state: "on"
  actions:
    - action: notify.send_message
      target:
        entity_id: notify.pv_verschattung_log
      data:
        message: >-
          {{ now().isoformat(timespec="seconds")
             ~ ";" ~ (state_attr('sun.sun', 'azimuth') | float(0) | round(3))
             ~ ";" ~ (state_attr('sun.sun', 'elevation') | float(0) | round(3))
             ~ ";" ~ states('sensor.pv_modul_1_strom')
             ~ ";" ~ states('sensor.pv_modul_2_strom')
             ~ ";" ~ states('sensor.pv_modul_3_strom')
             ~ ";" ~ states('sensor.pv_modul_1_spannung')
             ~ ";" ~ states('sensor.pv_modul_2_spannung')
             ~ ";" ~ states('sensor.pv_modul_3_spannung')
             ~ ";" ~ states('sensor.anker_solix_solarbank_4_e5000_pro_441_solarstrom')
             ~ ";" ~ states('sensor.pv_leistung_fremdanlage_modbus')
             ~ ";" ~ states('sensor.saunaraum_anker_solix_solarbank_4_e5000_pro_441_pv_signal_streuung_5min')
             ~ ";" ~ states('sensor.power_production_now')
             ~ ";" ~ states('sensor.anker_solix_solarbank_4_e5000_pro_441_ac_ausgang')
             ~ ";" ~ states('sensor.anker_solix_solarbank_4_e5000_pro_441_soc')
             ~ ";" ~ states('sensor.anker_solix_solarbank_4_e5000_pro_441_geratestatus')
             ~ ";" ~ states('binary_sensor.pv_modul_1_verschattet')
             ~ ";" ~ states('binary_sensor.pv_modul_2_verschattet')
             ~ ";" ~ states('binary_sensor.pv_modul_3_verschattet')
             ~ ";e:" ~ trigger.entity_id ~ ":" ~ trigger.to_state.state }}
  mode: queued
  max: 10
```

### 3.5 Überwachung und Tagesbericht

Eine vierwöchige unbeaufsichtigte Kampagne, die still ausfällt, ist der wahrscheinlichste
Weg, die Entscheidung zu verpassen. Zwei kleine Automationen dagegen.

Der Watchdog nutzt einen nativen Zustandstrigger mit `for:`. Da der Zähler alle zwei
Minuten hochzählt, bedeutet „Zustand hält zehn Minuten" exakt „seit zehn Minuten kein
Datensatz". Dafür ist kein Template nötig.

```yaml
- id: "pv_verschattung_watchdog"
  alias: "PV Verschattung: Watchdog"
  description: >-
    Meldet, wenn der Datensatzzaehler zehn Minuten stillsteht, obwohl die Sonne hoch
    genug steht und die Kampagne laeuft. Faengt volle Platte, entzogene
    Verzeichnisfreigabe und entladene Integration ab.
  triggers:
    - trigger: state
      entity_id: counter.pv_verschattung_datensaetze
      for:
        minutes: 10
  conditions:
    - condition: state
      entity_id: input_boolean.pv_verschattung_kampagne
      state: "on"
    - condition: numeric_state
      entity_id: sensor.sonne_elevation
      above: 10
  actions:
    - action: notify.send_message
      target:
        entity_id: notify.alle_mobilgeraete
      data:
        title: "Verschattungskampagne steht"
        message: >-
          Seit zehn Minuten kein Datensatz, obwohl die Sonne bei
          {{ states('sensor.sonne_elevation') }} Grad steht. Bitte
          /config/verschattung/verschattung.csv und das Protokoll pruefen.
    - action: persistent_notification.create
      data:
        title: "Verschattungskampagne steht"
        message: >-
          Aufzeichnung unterbrochen seit
          {{ states.counter.pv_verschattung_datensaetze.last_changed
             .astimezone(now().tzinfo).strftime('%d.%m. %H:%M') }} Uhr.
        notification_id: pv_verschattung_watchdog
  mode: single

- id: "pv_verschattung_tagesbericht"
  alias: "PV Verschattung: Tagesbericht"
  description: >-
    Meldet abends die Zahl der Datensaetze des Tages und setzt den Zaehler zurueck.
    Erwartungswert Mitte August rund 375, Mitte September rund 340. Deutlich weniger
    heisst, dass tagsueber Luecken entstanden sind.
  triggers:
    - trigger: time
      at: "22:00:00"
  conditions:
    - condition: state
      entity_id: input_boolean.pv_verschattung_kampagne
      state: "on"
  actions:
    - action: notify.send_message
      target:
        entity_id: notify.alle_mobilgeraete
      data:
        title: "Verschattungskampagne Tagesbericht"
        message: >-
          {{ states('counter.pv_verschattung_datensaetze') }} Datensaetze heute,
          schwaechstes Modul im Tagesminimum
          {{ states('sensor.pv_verschattung_schwaechster_anteil') }} Prozent.
          Tag {{ (now().date()
                  - (states('input_datetime.pv_verschattung_start') | as_datetime
                     | as_local).date()).days }} der Kampagne.
    - action: counter.reset
      target:
        entity_id: counter.pv_verschattung_datensaetze
  mode: single
```

### 3.6 Das Ziel der Schreibvorgänge

**Variante A — `file`-Integration (vorgeschlagen).**

Zuerst das Verzeichnis freigeben. `configuration.yaml` hat bisher keinen
`homeassistant:`-Block; dieser wird neu angelegt:

```yaml
homeassistant:
  allowlist_external_dirs:
    - "/config/verschattung"
```

Dann das Verzeichnis anlegen und die Integration hinzufügen — Einstellungen → Geräte &
Dienste → Integration hinzufügen → **File** → *Notify*:

| Feld | Wert |
|---|---|
| Dateipfad | `/config/verschattung/verschattung.csv` |
| Zeitstempel voranstellen | **aus** — der Zeitstempel steht bereits als erste Spalte |

Die entstehende Entity anschließend auf `notify.pv_verschattung_log` umbenennen, damit sie
zu den Automationen oben passt.

Die Kopfzeile schreibt die `file`-Integration nicht. Sie ist einmalig anzulegen:

```
ts;az;el;i1;i2;i3;u1;u2;u3;p_ges;p_3rd;streu5;prog;ac;soc;status;v1;v2;v3;quelle
```

**Variante B — pyscript (bereits installiert, `allow_all_imports: true`).**

Braucht keine Allowlist, legt die Kopfzeile selbst an und schreibt atomar. Als
`/config/pyscript/verschattung.py`; die Automationen rufen dann statt
`notify.send_message` den Dienst `pyscript.verschattung_log` mit `zeile: "..."` auf.

```python
import os

PFAD = "/config/verschattung/verschattung.csv"
KOPF = ("ts;az;el;i1;i2;i3;u1;u2;u3;p_ges;p_3rd;streu5;prog;ac;soc;"
        "status;v1;v2;v3;quelle")


@service
def verschattung_log(zeile=None):
    """yaml: Haengt eine CSV-Zeile an die Verschattungsaufzeichnung an."""
    if not zeile:
        return
    os.makedirs(os.path.dirname(PFAD), exist_ok=True)
    neu = not os.path.exists(PFAD)
    with open(PFAD, "a", encoding="utf-8") as fh:
        if neu:
            fh.write(KOPF + "\n")
        fh.write(zeile + "\n")
        fh.flush()
        os.fsync(fh.fileno())
```

### 3.7 Eine Voraussetzung in der Integration

Die Spalte `p_3rd` bezieht sich auf `sensor.pv_leistung_fremdanlage_modbus`
(`const.py`, `Reg("third_party_pv_mb", 10004, ...)`). Diese Entity gehört zur Gruppe
`mirror`, die in `const.py:84` mit `enabled=False` voreingestellt ist. Sie muss **vor
Kampagnenstart in der Entity-Registry aktiviert** werden. Warum das nicht optional ist,
steht in §7.2.

---

## 4. Auswertungsverfahren

Vom Rohdatensatz zur Aussage „bei Azimut X und Elevation Y bricht Modul Z um N Prozent
ein", in sechs Schritten.

### 4.1 Einlesen und Sonnenstand prüfen

CSV einlesen, `ts` als zeitzonenbehaftete Zeit parsen. Aus `ts` den Sonnenstand
**neu berechnen** und gegen die Spalten `az`/`el` halten. Weichen sie um mehr als 0,1° ab,
liegt ein Zeitproblem vor (Sommerzeitwechsel am 25.10. — nach dem Entscheidungstermin,
aber die Prüfung kostet nichts). Bei Übereinstimmung ist der Datensatz in sich konsistent
und die berechneten Werte werden weiterverwendet, weil sie auch für die Flankenzeilen
zwischen den Rasterpunkten gelten.

### 4.2 Normieren — der entscheidende Schritt

Die Rohleistung je Strang: `P_n = U_n · I_n` für n = 1..3, und
`P_4 = p_ges − p_3rd − (P_1 + P_2 + P_3)`.

Dann die **relative Ausbeute** gegen das jeweils beste Modul:

```
f_n = P_n / max(P_1, P_2, P_3, P_4)        n = 1..4
```

Warum das Maximum und nicht der Median der übrigen: Bei vier koplanaren Modulen mit
identischer Ausrichtung ist das momentan hellste Modul die beste verfügbare Schätzung für
die unverschattete Einstrahlung. Der Median verschiebt sich, sobald zwei Module gleichzeitig
verschattet sind — und genau das ist bei einer über die Reihe wandernden Kante der
Normalfall. Das Maximum bleibt so lange belastbar, wie mindestens ein Modul frei ist.

**Hier liegt die Wolkenimmunität der ganzen Kampagne.** Die vier Module sind koplanar,
Azimut 188°, Neigung 20° (REGISTER.md §6). Eine Wolke verdunkelt alle vier gleichzeitig und
im selben Verhältnis — Zähler und Nenner fallen zusammen, `f_n` bleibt unverändert. Ein
Schornstein verdunkelt eines. **`f_n` misst Ungleichheit, und Ungleichheit zwischen
koplanaren Modulen kann nicht vom Wetter kommen.** Deshalb ist ein Klarhimmelfilter für die
Kernaussage gar nicht nötig; `streu5` und `prog` werden erst in §4.6 gebraucht.

Zwei Einschränkungen, die dazugehören:

- **Der Randfall „alle vier verschattet"** ist mit dieser Normierung nicht auflösbar; alle
  `f_n` gehen gegen 1. Er ist erkennbar daran, dass `max(P)` weit unter `prog`
  (Klarhimmelprognose) liegt, und wird verworfen.
- **Zeitversatz.** `p_ges` kommt von der offiziellen Integration (5-s-Takt), die
  Strangdaten von `solarbank_pv` (30-s-Takt). Nur `P_4` ist davon betroffen, weil nur dort
  subtrahiert wird. Bei ziehenden Wolken entstehen Artefakte. Deshalb wird `f_4` nur
  ausgewertet, wenn `streu5 < 50` — die Bedingung, die die Anlage im Template
  „PV Drosselung Leistung" bereits benutzt.

### 4.3 Rastern

Zellen zu 5° Azimut × 5° Elevation. Belegung über die Kampagne, gerechnet für
51,7619 °N / 7,8766 °O, 11.08.–15.09.2026:

| Größe | Wert |
|---|---|
| belegte Zellen (El > 5°) | 162 |
| davon Azimut ≥ 180° | 81 |
| Azimutbereich | 70° … 290° |
| Elevationsbereich | 5° … 55° |
| Messpunkte je Zelle (2-min-Raster) | Median 81 |
| **unabhängige Tage je Zelle** | **Median 13** |

Für die Kantenregion, sobald sie aus dem groben Raster bekannt ist, lohnt eine
Nachverdichtung auf 5° × 2°: 346 Zellen, Median 8 unabhängige Tage — immer noch genug für
einen Median, aber mit 2,5-fach feinerer Auflösung in der Elevation.

### 4.4 Verdichten

Je Zelle und Modul der **Median** aller `f_n` in der Zelle. Der Median, nicht das Mittel:
Ein einzelner Wolkenschatten, der eine Zelle an einem Tag streift, wird von zwölf anderen
Tagen überstimmt.

```
Defizit  D_n(az, el) = (1 − median f_n) · 100 %
```

Dazu je Zelle mitführen: Anzahl Messpunkte, Anzahl unabhängiger Tage, Interquartilsabstand
von `f_n`. Der Interquartilsabstand ist das Vertrauensmaß. **Eine feste Verschattung
erzeugt einen kleinen Interquartilsabstand** — der Schatten fällt jeden Tag gleich. **Ein
großer Interquartilsabstand bei mittlerem Defizit heißt Wetter, nicht Geometrie.**

### 4.5 Darstellung

**Vorschlag: vier Heatmaps, eine je Modul, plus eine Tabelle.**

Heatmap, ein Feld je Modul:

- x-Achse Azimut 70°…290°, y-Achse Elevation 0°…55°
- Farbe = `D_n` in Prozent, divergierende Skala mit Nullpunkt bei 0 %
- Zellen mit weniger als 5 unabhängigen Tagen ausgegraut, nicht eingefärbt
- eingezeichnet: die Sonnenbahnen vom 11.08., 28.08. und 15.09. als Linien, dazu die
  Bahnen vom 21.10. und 21.12. gestrichelt — letztere zeigen sofort, was die Kampagne
  **nicht** gemessen hat (§7.4)
- als senkrechte Linie: Azimut 188°, die Anlagenausrichtung

Vier Felder nebeneinander machen die Kernfrage auf einen Blick lesbar: Wandert eine
zusammenhängende dunkle Region von Feld zu Feld nach rechts, ist es eine über die Reihe
wandernde Kante. Sitzt sie in nur einem Feld fest, ist es ein lokales Problem an einem
Modul.

Die Heatmap ist zum Ansehen; die Zahl für die Entscheidung liefert die **Horizonttabelle**.
Sie ist das eigentliche Produkt der Kampagne:

| Azimut | Modul 1 | Modul 2 | Modul 3 | Modul 4 | Tage | Deutung |
|---|---|---|---|---|---|---|
| 200–205° | — | — | 48° | 52° | 14 | Kante über 3 und 4 |
| 205–210° | — | 41° | 46° | 50° | 13 | … |

Eintrag = kritische Elevation, unterhalb derer `D_n > 20 %`. „—" heißt: im gemessenen
Bereich kein Einbruch. Diese Tabelle ist die Vermessung des realen Horizonts. Sie ist
jahreszeitunabhängig, weil ein Schornstein sich nicht bewegt — und deshalb auf jeden
beliebigen Tag des Jahres anwendbar, **soweit die Kampagne den betreffenden Azimut
überhaupt in ausreichender Tiefe abgetastet hat** (§7.4).

### 4.6 Von Prozenten zu Kilowattstunden

Erst hier wird der Klarhimmelbezug gebraucht, denn die Entscheidung hängt an Energie, nicht
an Prozenten.

Je Zelle: mittlere Verlustleistung `ΔP = D_n · max(P)`, gewichtet mit der jährlichen
Verweildauer der Sonne in dieser Zelle (aus der Ephemeride berechenbar, keine Messung
nötig). Summiert über alle Zellen und alle Module ergibt das den **Jahresverlust in kWh**.

Erst diese Zahl beantwortet die Frage. Sie ist gegen den Ertrag eines zusätzlichen Moduls
zu halten:

- Verliert die Anlage jährlich mehr als etwa ein halbes Modul an Verschattung, sind
  **mehr Module** die schlechtere Investition — man vervielfacht ein Problem, statt es zu
  lösen, es sei denn, die neuen Module stehen außerhalb des vermessenen Schattenbereichs.
- Fällt der Verlust überwiegend nachmittags an, während der Speicher ohnehin voll ist,
  ist er wirtschaftlich fast bedeutungslos — dann sagt die Kampagne „**mehr Speicher**".
  Diese Prüfung geht direkt: Spalten `soc` und `status` stehen im Datensatz. War der SOC
  während der Verschattungsfenster überwiegend bei 100 und der Status `standby`, wurde die
  fehlende Energie ohnehin nicht gebraucht.

**Diese letzte Auswertung ist der eigentliche Zweck der Spalten `soc` und `status`.** Ohne
sie beantwortet die Kampagne die physikalische Frage, aber nicht die wirtschaftliche.

### 4.7 Alternative Erklärungen, die die Kampagne unterscheiden kann

Die Kampagne ist nur dann eine Messung, wenn sie auch etwas anderes als Verschattung
finden kann. Sie kann:

| Befundmuster | Deutung |
|---|---|
| Defizit auf zusammenhängende (az, el)-Region beschränkt, an allen Tagen reproduzierbar, kleiner Interquartilsabstand | **feste Verschattung** — Hypothese bestätigt |
| Defizit über **alle** Zellen gleich groß, unabhängig vom Sonnenstand | **Verschmutzung, Defekt, schwächeres Modul** — keine Verschattung |
| Defizit nur bei hoher Gesamtleistung, verschwindet bei niedriger | **Abregelung / MPP-Problem**, nicht Verschattung (`CURTAIL_VOC_FRACTION`, `const.py:62`) |
| Defizit korreliert mit `streu5`, nicht mit (az, el) | **Wetter** |
| Defizit springt zwischen Modulen ohne geometrische Ordnung | **Messfehler oder Registerverwechslung** |

Die schärfste Einzelunterscheidung ist bereits in den Rohdaten enthalten und kostet keine
Statistik: **Verschattung senkt den Strom und hebt gleichzeitig die Spannung.** Eine Wolke
senkt beides. Genau diese Doppelsignatur wurde am 11.08. beobachtet (Modul 3: Strom
8,28 A statt 14 A, aber Spannung 32,4 V statt 29,9 V, zurückgerechnete Zelltemperatur 23 °C
niedriger). Weil `i_n` und `u_n` beide je Datensatz protokolliert werden, lässt sich diese
Prüfung für jeden einzelnen Messpunkt durchführen — nicht nur im Nachhinein für den einen
dokumentierten Fall.

---

## 5. Recorder-Ergänzung

### 5.1 Bestand

`configuration.yaml` Zeilen 27–33, unverändert wiedergegeben:

```yaml
recorder:
  exclude:
    entities:
      - automation.nulleinspeisung_watchdog
      - sensor.nulleinspeisung_speicher_prognose
      - sensor.stromleser_emh_power
      - sensor.nulleinspeisung_regelfehler
```

Vier Einträge, kein `purge_keep_days` (Vorhaltezeit kommt aus `gui_recorder.yaml`: 10 Tage),
keine `entity_globs`, kein `include`. **Diese Liste wird ausschließlich ergänzt.** Der
bestehende `logbook:`-Block (Zeilen 34–43) bleibt ebenfalls unberührt.

### 5.2 Was neu in den Recorder gehört

Diese Entities **dürfen nicht ausgeschlossen werden** — sie tragen `state_class` und liefern
damit die dauerhafte Rückfallebene aus §2.3:

| Entity | Warum |
|---|---|
| `sensor.sonne_azimut` | ohne sie ist der Azimut historisch nicht existent (§0.2) |
| `sensor.sonne_elevation` | vorhanden, bereits aufgezeichnet |
| `sensor.pv_modul_1_stromanteil` … `_3_stromanteil` | Kerngröße, stündliches Minimum ist die Rückfallebene |
| `sensor.pv_modul_4_anteil` | dito für den nicht messbaren Strang |
| `sensor.pv_modul_1_leistung` … `_3_leistung` | LTS liefert dauerhaft die Energie je Modul |
| `sensor.pv_modul_4_leistung` | dito |
| `sensor.pv_verschattung_schwaechster_anteil` | eine Zahl für den Gesamtzustand |
| `binary_sensor.pv_modul_1_verschattet` … `_3_verschattet` | keine LTS, aber geringes Volumen und im 10-Tage-Fenster wertvoll |

### 5.3 Was neu ausgeschlossen werden sollte

Alle drei Gruppen stehen vollständig in der CSV-Datei und sind dort dauerhaft und feiner
verfügbar. Im Recorder erzeugen sie nur Volumen.

```yaml
recorder:
  exclude:
    entities:
      # --- Bestand, unveraendert ---
      - automation.nulleinspeisung_watchdog
      - sensor.nulleinspeisung_speicher_prognose
      - sensor.stromleser_emh_power
      - sensor.nulleinspeisung_regelfehler
      # --- neu: Verschattungskampagne ---
      # Rohgroessen. Stehen im 2-Minuten-Raster dauerhaft in der CSV-Datei; im
      # Recorder erzeugen sie 9000 Zeilen am Tag ohne Zusatznutzen. LTS sind fuer
      # sie entbehrlich - die physikalisch interessante Groesse ist die Leistung,
      # und die bleibt aufgezeichnet.
      - sensor.pv_modul_1_strom
      - sensor.pv_modul_2_strom
      - sensor.pv_modul_3_strom
      - sensor.pv_modul_1_spannung
      - sensor.pv_modul_2_spannung
      - sensor.pv_modul_3_spannung
      # Zelltemperatur wechselt unterhalb 0,5 A staendig nach unknown und zurueck
      # (const.py MIN_CURRENT_FOR_TEMP) - viele Zeilen, wenig Inhalt. Exakt aus der
      # Spannung rueckrechenbar (REGISTER.md Abschnitt 6).
      - sensor.pv_modul_1_zelltemperatur
      - sensor.pv_modul_2_zelltemperatur
      - sensor.pv_modul_3_zelltemperatur
      # Die Automationen selbst: jeder Lauf schreibt last_triggered, das sind 375
      # Zeilen am Tag je Automation. Gleiche Begruendung wie beim bereits
      # ausgeschlossenen automation.nulleinspeisung_watchdog.
      - automation.pv_verschattung_abtastung
      - automation.pv_verschattung_flanke
      # Zaehlt alle zwei Minuten hoch. Der Watchdog-Trigger arbeitet auf der
      # Zustandsmaschine, nicht auf dem Recorder - der Ausschluss stoert ihn nicht.
      - counter.pv_verschattung_datensaetze
```

### 5.4 Zwei Fallstricke

**Kein `entity_globs` auf `sensor.pv_modul_*`.** Ein Glob wäre kürzer, würde aber die
Anteils- und Leistungssensoren mitnehmen und damit die Rückfallebene aus §5.2 zerstören —
still, ohne Fehlermeldung. Die ausgeschriebene Liste ist hier die richtige Wahl.

**Ausschluss beendet auch die Statistik.** Für jede oben ausgeschlossene Entity entstehen
keine LTS. Das ist beabsichtigt und für Strom, Spannung und Zelltemperatur unschädlich —
aber es ist der Grund, warum die Liste so vorsichtig zusammengestellt ist.

### 5.5 Nach der Änderung

`recorder` lässt sich nicht einzeln neu laden; die Änderung wird erst mit einem Neustart
von Home Assistant wirksam. Vorher `check_config` laufen lassen. Der Zeitpunkt ist relevant:
Ein Neustart **nach** Kampagnenstart erzeugt eine Lücke von ein bis zwei Datensätzen —
tolerabel. Sauberer ist, Recorder-Änderung und Kampagnenstart in einen Neustart zu legen.

---

## 6. Mengenabschätzung

### 6.1 Grundlage

Sonnenminuten mit Elevation > 5°, gerechnet für 51,7619 °N / 7,8766 °O:
**26 317 Minuten in 35 Tagen** = 752 min/Tag = 12,53 h/Tag.

Eine CSV-Datenzeile im obigen Schema misst **107 Byte** einschließlich Zeilenumbruch
(gemessen an einer realistischen Beispielzeile mit den Werten vom 11.08. 14:40).

### 6.2 Die Datei

| Abtastung | 4 Wochen (28 Tage) | bis 15.09. (35 Tage) |
|---|---|---|
| alle 1 min | 21 054 Sätze · 2,15 MiB | 26 317 Sätze · 2,69 MiB |
| **alle 2 min (gewählt)** | **10 527 Sätze · 1,07 MiB** | **13 158 Sätze · 1,34 MiB** |
| alle 5 min | 4 211 Sätze · 0,43 MiB | 5 263 Sätze · 0,54 MiB |

Dazu die Flankenzeilen. Bei geschätzt vier bis zwölf Flanken pro Tag (drei Module, Ein- und
Ausschaltflanke, plus Wolkenflattern) sind das über 35 Tage 150 bis 400 Zeilen, also
**unter 45 KiB**. Vernachlässigbar.

**Ergebnis: rund 10 500 Datensätze und gut 1 MiB in vier Wochen; 13 200 Datensätze und
1,4 MiB bis zum Entscheidungstermin.** Die Datei passt in jede Tabellenkalkulation und in
jedes Backup.

### 6.3 Die Datenbank

Annahme: rund 300 Byte je Zeile in `states` einschließlich `states_meta` und Indizes. Die
Entities aktualisieren im 30-s-Takt, also bis zu 2 Zeilen/min je Entity, und zwar nur
tagsüber — nachts sind die Werte konstant und erzeugen keine Zeilen.

| Fall | Zeilen/Tag | pro Tag | im 10-Tage-Fenster |
|---|---|---|---|
| **ohne Ausschluss** (15 Entities) | 22 557 | 6,5 MiB | **65 MiB** |
| **mit Ausschluss nach §5.3** (~10 Entities) | ~15 000 | ~4,3 MiB | **~43 MiB** |
| Ersparnis | | | **~22 MiB** |

Gemessen an 768,6 MiB heutiger Datenbankgröße: ohne Ausschluss **+8,5 %**, mit Ausschluss
**+5,6 %**. Beides ist ein stationärer Aufschlag, kein Wachstum — nach zehn Tagen läuft die
Purge und der Bestand pendelt sich ein.

Zur Einordnung, wie viel Luft da ist: `sensor.anker_..._solarstrom` allein schrieb im
gemessenen Fenster **26 Zeilen in 3 Minuten** (≈ 8,7/min, 5-s-Polling der offiziellen
Integration). Das ist mehr als die vier hier neu aufgezeichneten Anteilssensoren zusammen.
Die Kampagne ist nicht der Grund, falls die Datenbank weiter wächst.

### 6.4 Long-Term Statistics

Rund 8 Entities mit `state_class` × 24 Stundenzeilen/Tag × ~120 Byte =
**22,5 KiB/Tag = 8,0 MiB/Jahr**, dauerhaft. Das ist der Preis der Rückfallebene aus §2.3
und im Verhältnis zu ihrem Wert vernachlässigbar.

### 6.5 Last auf dem Modbus-Gerät

**Keine zusätzliche.** Die Kampagne liest ausschließlich Entity-Zustände aus der
Zustandsmaschine von Home Assistant. Sie erzeugt keine einzige Modbus-Anfrage über das
hinaus, was `solarbank_pv` ohnehin im 30-s-Takt tut. Das Gerät unter 192.168.178.86 merkt
von der Kampagne nichts.

---

## 7. Der vierte Strang

### 7.1 Was fehlt

Strang 4 ist auf Modbus nicht auffindbar (REGISTER.md §5: 10173–10175 konstant null über
109 Messpunkte, während Strang 4 produzierte; 10156 als Kandidat widerlegt). Damit fehlen
für Modul 4 **Strom, Spannung, Zelltemperatur und Verschattungsmelder** — ein Viertel der
Anlage, und ausgerechnet dasjenige, das am 11.08. um 14:40 mit 60 W von möglichen ~415 W
den mit Abstand schwersten Einbruch zeigte (86 % Defizit).

### 7.2 Was sich trotzdem erschließen lässt: die Leistung, durch Subtraktion

Register 10002 (`pv_power`) führt die **Summe über alle Stränge** und ist sicher belegt.
Also:

```
P_4 = p_ges − p_3rd − (U_1·I_1 + U_2·I_2 + U_3·I_3)
```

Gegenprobe an der Messung vom 11.08.2026 14:40 (REGISTER.md §3.2 und §8):

| Größe | Wert |
|---|---|
| Summe Modbus (10002) | 1164 W |
| Strang 1 + 2 + 3 gemessen | 419 + 422 + 268 = 1109 W |
| **Differenz** | **55 W** |
| **Strang 4 laut Anker-App** | **60 W** |

Abweichung 5 W bei einem App-Wert von 60 W. **Das Verfahren funktioniert.** Es ist als
`sensor.pv_modul_4_leistung` in §3.1 umgesetzt.

Damit ist die Kampagne für Modul 4 **nicht blind, sondern unschärfer**. Vier
Einschränkungen, ehrlich benannt:

1. **Fehlerfortpflanzung.** Die absoluten Fehler aller vier Terme addieren sich. Bei ~2 %
   Unsicherheit je Strang (aus dem App-Vergleich in REGISTER.md §3.2) sind das rund
   ±22 W auf 1109 W. Gegen `P_4 = 55 W` ist das ein relativer Fehler von **±40 %**. `P_4`
   taugt zur Aussage „Modul 4 ist eingebrochen", nicht zu „Modul 4 liefert 63 statt 68 %".
   Je kleiner `P_4`, desto schlechter das Verhältnis — ausgerechnet im interessanten Fall.
   Über 13 unabhängige Tage je Zelle mittelt sich das allerdings weitgehend heraus: der
   Fehler ist zufällig, nicht systematisch.
2. **Zeitversatz.** Zwei Integrationen mit 5-s- und 30-s-Takt. Bei ziehenden Wolken werden
   nicht gleichzeitige Messungen subtrahiert. Deshalb der Filter `streu5 < 50` in §4.2.
3. **Fremdanlage.** Die Entity `solarstrom` führt `additional_sources:
   ["third_party_pv_power"]`, aktuell `source_third_party_pv_power: 0`. Solange das null
   bleibt, ist die Rechnung sauber. Wird jemals eine Fremdanlage angeschlossen, ist `P_4`
   still falsch. **Deshalb wird `p_3rd` als eigene Spalte mitgeschrieben und in der Formel
   abgezogen** — die Kampagne bleibt dann gültig, statt unbemerkt zu kippen. Das ist der
   Grund für die Aktivierungsanforderung in §3.7.
4. **Keine Doppelsignatur.** Ohne `U_4` entfällt für Modul 4 der schärfste
   Einzeldiskriminator: „Strom fällt, Spannung steigt" (§4.7). Auch die
   Zelltemperatur-Rückrechnung, die am 11.08. mit 23 K Unterschied so eindeutig war, ist
   für Modul 4 nicht verfügbar. Modul 4 muss sich allein auf den Vergleich mit den anderen
   drei stützen.

### 7.3 Was das für die Aussagekraft bedeutet

**Für die Ausbauentscheidung: fast nichts.** Die Entscheidung braucht Energie, und Energie
liefert `P_4` mit ausreichender Genauigkeit, sobald über viele Zellenbesuche gemittelt
wird. Die Frage „fällt ein Viertel der Anlage jeden Nachmittag aus" ist mit `P_4`
beantwortbar — und war es, mit einem einzigen Messpunkt, im Ansatz schon.

**Für die physikalische Diagnose: spürbar.** Ob Modul 4 hart verschattet oder nur
teilverschattet ist, ob eine Bypassdiode arbeitet, ob der MPP-Tracker in einem
Nebenmaximum hängt — das steht in der Spannung, und die fehlt. Fällt die Kampagne für
Modul 4 auffällig aus, ist die Klärung nicht aus den Daten, sondern nur am Dach möglich.

**Ein Randnutzen, der leicht übersehen wird:** Weil `P_4` mitläuft, ordnet die Kampagne
alle vier Module in eine Reihenfolge. Wandert eine Schattenkante über die Reihe, liefert
die Reihenfolge, in der die vier Module einbrechen, **die Laufrichtung der Kante** — und
damit die Himmelsrichtung des Verursachers. Das ist genau die Frage der Arbeitshypothese,
und sie ist auch ohne `U_4` beantwortbar.

### 7.4 Was die Kampagne grundsätzlich nicht messen kann

Unabhängig von Modul 4: Die Kampagne tastet einen **Streifen** des Himmels ab, nicht die
ganze Halbkugel. Der Vergleich der abgedeckten Elevationen mit späteren Sonnenbahnen:

| Azimut | Kampagne 11.08.–15.09. | Sonne 21.10. | Sonne 21.12. |
|---|---|---|---|
| 130–140° | 30,8° … 47,6° | 19,3° | 5,3° |
| 170–180° | 41,1° … 53,4° | 27,4° | 14,8° |
| 200–210° | 37,9° … 51,9° | 25,4° | 12,5° |
| 240–250° | 19,3° … 39,4° | 8,6° | — |
| 270–280° | 3,0° … 19,2° | — | — |

Im gesamten Südsektor liegen die Herbst- und Winterbahnen **vollständig unterhalb** des
gemessenen Bereichs. Am 21.12. steht die Sonne hier höchstens 14,8° hoch; die Kampagne
sieht bei Azimut 180° nie etwas unter 41°.

Daraus folgt eine asymmetrische Aussagekraft, die bei der Auswertung ausdrücklich zu
beachten ist:

- **Findet** die Kampagne bei einem Azimut eine Schattenkante, ist der Horizont dort
  **gemessen**. Weil ein Bauwerk sich nicht bewegt, gilt dieser Wert für jede Jahreszeit,
  und die Winterverschattung ist daraus vorhersagbar.
- **Findet** sie bei einem Azimut **keine** Verschattung, ist damit nur belegt, dass der
  Horizont dort **unter** der niedrigsten gemessenen Elevation liegt — bei Azimut 180° also
  unter 41°. Ob unter 40° oder unter 5°, bleibt offen. **Über die Winterverschattung im
  Südsektor sagt die Kampagne dann nichts.**

Für die anstehende Entscheidung ist das vertretbar: Der Ertrag einer Anlage in Ahlen fällt
weit überwiegend zwischen April und September an, und genau dort misst die Kampagne. Es
wäre aber falsch, aus einem sauberen Kampagnenergebnis auf ein verschattungsfreies
Winterhalbjahr zu schließen. Wer diese Aussage braucht, misst im Februar nach — oder
bestimmt den Horizont einmalig geometrisch (§8, erster Punkt).

---

## 8. Offene Punkte

1. **Welches Modul ist Strang 3?** REGISTER.md §7 hält fest, dass die Zuordnung von
   Register zu physischer Position in der Dachreihe **ungeklärt** ist. Die Kampagne
   liefert Aussagen über *Stränge*. Ohne die Zuordnung weiß man am Ende, dass Strang 3
   bei Azimut 205° einbricht — aber nicht, welches Modul man auf dem Dach anschauen muss
   und wo ein zusätzliches Modul verschattungsfrei stünde. **Das entwertet das Ergebnis für
   die Ausbauentscheidung erheblich.** Die dort vorgeschlagene Klärung — ein Modul kurz
   abdecken und beobachten, welcher Strom einbricht — dauert Minuten und sollte **vor
   Kampagnenstart** erfolgen, damit sie mitprotokolliert ist. Ein Foto der Dachfläche mit
   Kompassrichtung erledigt zugleich den Horizont im Südsektor aus §7.4.
2. **Die Integration ist nicht lauffähig** (§0.1). `sensor.py` und `binary_sensor.py`
   fehlen. Kritischer Pfad. Bis dahin läuft die Uhr gegen die Kampagne.
3. **`sensor.pv_leistung_fremdanlage_modbus` muss aktiviert werden** (§3.7), sonst schreibt
   die Automation `unknown` in die Spalte `p_3rd` und die Absicherung aus §7.2 Punkt 3
   greift nicht.
4. **Entity-IDs sind Entwurfsnamen.** Die tatsächlichen IDs entstehen erst beim ersten
   Start aus dem Gerätenamen `Solarbank DC-Straenge (441)` (`__init__.py:66`) und den
   Anzeigenamen in `const.py`. Erwartbar ist eher
   `sensor.solarbank_dc_straenge_441_modul_1_strom` als `sensor.pv_modul_1_strom`. **Vor
   Kampagnenstart sind alle IDs in den YAML-Blöcken gegen die Registry abzugleichen** — oder
   die Entities werden einmalig auf das `pv_modul_n_*`-Schema umbenannt, was der
   Namenskonvention der Anlage (`sensor.pv_*`, `sensor.nulleinspeisung_*`) entspricht und
   die Automationen lesbar hält. Umbenennen vor dem ersten Aufzeichnungstag, nie danach.
5. **`sensor.sonne_azimut` springt bei 360°/0°.** Für den hier abgetasteten Bereich
   (70°…290°) ist das ohne Belang, aber eine Mittelung über den Nordpunkt wäre falsch. In
   der Auswertung nicht über Azimut mitteln, nur binnen.
6. **Der Watchdog meldet einmal beim Start**, weil der Zähler vor dem ersten Datensatz
   zehn Minuten unverändert steht. Einmalige Fehlmeldung, bewusst in Kauf genommen; die
   Alternative wäre eine Zusatzbedingung, die den Watchdog schwächt.
7. **Register 10205 ist weiter offen.** REGISTER.md §5 nennt die Entscheidungsregel: Fallen
   10168/10170/10172 nach Sonnenuntergang auf null und 10205 ebenfalls, ist 10205 der
   vierte Strang. Bleibt es bei ~330, ist es das nicht. `const.py` zeichnet 10205 bereits
   auf (`enabled=True`), und die Kampagne läuft über 35 Sonnenuntergänge. **Diese Frage
   klärt sich als Nebenprodukt in der ersten Nacht** — vorausgesetzt, jemand schaut hin.
   Wird 10205 als Strang 4 bestätigt, entfällt die gesamte Unschärfe aus §7.2.
8. **Verschmutzung ist die unangenehmste Alternativhypothese.** Sie erzeugt ein
   sonnenstandsunabhängiges Defizit (§4.7) und ist damit unterscheidbar — aber nur, wenn
   sie sich während der Kampagne nicht ändert. Ein Regenguss in Woche zwei, der ein Modul
   reinigt, sieht in der Auswertung wie eine Änderung der Geometrie aus. Empfehlung:
   Datum stärkerer Niederschläge notieren und die Auswertung einmal getrennt für beide
   Hälften rechnen. Ergeben beide Hälften dieselbe Horizonttabelle, ist das ein starkes
   Argument für Geometrie.
9. **Nicht geprüft, weil schreibend:** ob `notify.send_message` auf einer
   `file`-Notify-Entity tatsächlich genau eine Zeile ohne eigenen Zeitstempel anhängt.
   Das ist vor Kampagnenstart mit einem einzelnen Testaufruf zu verifizieren — und die
   ersten zehn Zeilen der Datei sind von Hand anzusehen, bevor man vier Wochen darauf
   vertraut.

