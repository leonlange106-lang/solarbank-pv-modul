# Verschattungsprofil je Strang nach Sonnenazimut

Grundlage der Tagesansicht im Dashboard `pv-module`, View **Verschattung**.

**Stand 13.08.2026. Das Profil ist vorlaeufig.** Es ruht auf einem
vollstaendigen Messtag und einem halben. Es ist ein Anfang, keine gesicherte
Aussage — und im Dashboard ist es als solches gekennzeichnet.

## Warum nach Azimut und nicht nach Uhrzeit

Ein Schattenwerfer steht fest im Raum. Ueber den **Sonnenazimut** bleibt das
Profil deshalb gueltig, waehrend sich die zugehoerigen Uhrzeiten ueber die
Wochen verschieben. Dieselben Fenster liegen am 13.08. und am 15.09. rund eine
halbe Stunde auseinander:

| Strang | Fenster (Azimut) | am 13.08. | am 15.09. |
|---|---|---|---|
| PV1 | 135–155 Grad | 11:31–12:29 | 10:57–12:07 |
| PV2 | 150–175 Grad | 12:16–13:21 | 11:50–13:08 |
| PV3 | 170–205 Grad | 13:08–14:37 | 12:53–14:40 |
| PV4 | 200–225 Grad | 14:24–15:36 | 14:24–15:49 |

**Gespeichert werden deshalb Azimutgrenzen, keine Uhrzeiten.** Die Uhrzeiten
rechnet die Dashboard-Karte fuer den jeweils laufenden Tag aus — mit derselben
NOAA-Formel, die auch `custom_components/pv_lernprognose/sonne.py` benutzt.

## Die Geometrie, vom Betreiber am 13.08. erklaert

Der Schattenwerfer ist der Giebel des gegenueberliegenden Hauses. Er wirft einen
**A-foermigen Schatten**: die Spitze reicht am weitesten, die Dachschraegen
laufen nach aussen ab.

Zwei Angaben des Betreibers erklaeren das gemessene Muster vollstaendig:

1. **Die Mitte der Modulreihe — zwischen PV2 und PV3 — liegt genau auf der Mitte
   des Nachbarhauses.** Die Giebelspitze projiziert also auf die Reihenmitte.
2. **Alle vier Module liegen nebeneinander in EINER Reihe, nicht uebereinander.**
   Der Schattenrand kreuzt die Reihe damit an einem Punkt. Bei zwei
   uebereinanderliegenden Reihen wuerde die Spitze Modulpaare erfassen; hier
   wandert sie als schmaler Streifen ueber die Reihe.

**Warum der Schatten im Sommer schmal ist:** Die Sonne steht hoch, der Schatten
ist kurz, die Giebelspitze **streift** die Reihe nur. Verschattet wird ein
schmaler Bereich um die Spitze, kein breiter Keil. Deshalb kann ein Modul
einbrechen, waehrend der direkte Nachbar volle Leistung liefert.

### Am Tagesverlauf des 13.08. validiert

Der Verlauf aus der Dashboard-View *Verlaeufe* zeigt die Staffelung lueckenlos.
Bis etwa 11:15 laufen alle vier Kurven deckungsgleich, dann wandert der Streifen
von West nach Ost durch die Reihe:

| Strang | Einbruch gemessen | Tiefpunkt | Fenster laut Profil |
|---|---|---|---|
| PV1 (ganz westlich) | 11:20–12:10 | rund 30 W | 11:31–12:29 |
| PV2 | 12:05–13:20 | rund 55 W | 12:16–13:21 |
| PV3 | ab 13:00 | 45 W | 13:08–14:37 |
| PV4 (ganz oestlich) | noch offen | — | 14:24–15:36 |

Die vorhergesagten Fenster decken sich mit den gemessenen Einbruechen auf wenige
Minuten. **Die Wanderrichtung ist PV1 nach PV4, also von West nach Ost** — und
genau diese Reihenfolge belegt umgekehrt die Lage der Module: ein Hindernis
suedlich der Reihe wirft morgens nach Westen, nachmittags nach Osten.

Entscheidend ist die **Ueberlappung**: PV1 klettert ab 12:10 zurueck, waehrend
PV2 bereits abgestuerzt ist. Genau das erwartet man von einem schmalen
wandernden Streifen — und genau das schliesst einen breiten Keil aus, der
mehrere Module gleichzeitig deckeln wuerde.

**Eine frueher notierte These ist damit widerlegt:** Es sind nicht zwei
unabhaengige Schattenwerfer. Eine einzige Giebelgeometrie erklaert sowohl die
Staffelung heute als auch den monotonen Abfall vom 11.08. um 14:40
(PV1 100 %, PV2 99 %, PV3 65 %, PV4 14 %) — da stand die Spitze bereits ueber PV4.

### Was das Azimutprofil NICHT leistet

Der Azimutbezug faengt die **Uhrzeitverschiebung** ueber die Jahreszeiten auf,
nicht die **Schattenlaenge**. Im Winter steht die Sonne tiefer, der Schatten wird
laenger, und der A-Schatten streift die Reihe nicht mehr nur mit der Spitze,
sondern legt sich mit den Schenkeln darueber. Dann sind mehrere Module
**gleichzeitig** betroffen statt nacheinander — eine andere Verlustcharakteristik
als die heute gemessene.

Fuer die Ausbauentscheidung heisst das: Die Sommermessung unterschaetzt den
Winterverlust strukturell. Ein Profil aus Augustdaten laesst sich ueber den
Azimut auf September fortschreiben, aber **nicht** auf Dezember.

## Datengrundlage

| Quelle | Zeitraum | brauchbare Punkte |
|---|---|---|
| `tools/rohdaten/pv4_tag.jsonl` | 12.08., 09:02–19:09 | 1208 |
| Recorder-5-Minuten-Statistik | 12.08. abends bis 13.08. 12:50 | 137 |

Zusammen **1345 Punkte an zwei Kalendertagen**. Der 08.08. ist wegen des
Drosselungstests (PV sechs Stunden konstant 798 W) ausgeschlossen; er faellt
ohnehin aus der 5-Minuten-Retention des Recorders.

**Die Abdeckung ist ungleich verteilt** — das ist der wichtigste Vorbehalt:

- Azimut **95–160 Grad**: 14 Faecher, **zwei Tage**. Die Fenster von PV1 und
  PV2 sind damit an zwei unabhaengigen Tagen reproduziert.
- Azimut **165–280 Grad**: 23 Faecher, **nur der 12.08.** Die Fenster von PV3
  und PV4 ruhen auf einem einzigen Tag.

## Verfahren

1. Je Messpunkt Sonnenhoehe und -azimut aus Zeit und Standort (51,7619 N /
   7,8766 O) nach NOAA rechnen. Der Port ist gegen `sun.sun` geprueft und
   weicht um 0,3 Grad Azimut ab.
2. Punkte verwerfen mit Gesamtleistung unter 50 W oder Sonnenhoehe unter
   10 Grad. Bei flacher Sonne dominieren Horizont und Einfallswinkel, das
   Verhaeltnis wird Rauschen.
3. Je Strang den **Leistungsanteil** bilden: `P_i / Median(die uebrigen drei)`.
4. Faecher von 5 Grad Breite, je Fach und Strang der **Median**.
5. Faecher mit weniger als 5 Punkten werden nicht veroeffentlicht.

### Der Bezug bricht zusammen, wenn zwei Straenge zugleich tief liegen

Der Leistungsanteil ist ein **relatives** Mass. Liegen zwei Straenge
gleichzeitig im Schatten, verschiebt sich der Median der Vergleichsgruppe und
die Zahlen werden unbrauchbar — im Fach 245–250 Grad bis zu einem negativen
Anteil fuer PV4 und 4,5 fuer PV2.

Solche Punkte werden erkannt (zweitkleinster Strang unter 25 % des groessten)
und verworfen; ein Fach, in dem mehr als die Haelfte der Punkte so ausfaellt,
wird ganz verworfen. **Das Fach 245–250 Grad ist auf diesem Weg entfallen** und
erscheint im Dashboard als Luecke, nicht als Verschattung.

Werte **ueber 100 %** bedeuten nur, dass die *Nachbarn* verschattet sind. Fuer
die Darstellung sind sie auf 100 % gedeckelt.

## Ergebnis

Anteil je Fach, gedeckelt auf 100 %. `--` heisst verworfen.

| Azimut | PV1 | PV2 | PV3 | PV4 |
|---|---|---|---|---|
| 130 | 96 | 99 | 100 | 100 |
| 135 | **57** | 99 | 100 | 100 |
| 140 | **18** | 98 | 100 | 100 |
| 145 | **58** | 62 | 100 | 100 |
| 150 | **59** | **35** | 100 | 100 |
| 155 | 91 | **12** | 100 | 100 |
| 160 | 100 | **13** | 85 | 100 |
| 165 | 100 | **17** | 66 | 100 |
| 170 | 100 | **49** | **52** | 100 |
| 175 | 100 | 66 | **24** | 100 |
| 180 | 100 | 67 | **23** | 100 |
| 185 | 100 | 82 | **24** | 100 |
| 190 | 100 | 100 | **38** | 76 |
| 195 | 100 | 100 | **34** | 69 |
| 200 | 100 | 100 | **57** | **29** |
| 205 | 100 | 100 | 67 | **21** |
| 210 | 100 | 100 | 81 | **22** |
| 215 | 99 | 100 | 100 | **25** |
| 220 | 99 | 100 | 100 | **46** |
| 225 | 98 | 100 | 100 | 70 |
| 245 | -- | -- | -- | -- |
| 250 | 100 | 95 | 100 | **51** |
| 255 | 100 | 97 | 100 | 65 |
| 275 | **36** | 69 | 100 | 100 |

Schwellen wie bei den Verschattungssensoren: **unter 60 % verschattet, erst
ueber 70 % wieder frei.**

### Fenster je Strang

| Strang | Fenster | tiefster Wert | Tage |
|---|---|---|---|
| PV1 | 135–155 Grad | 18 % | **2** |
| PV1 | 275–280 Grad | 36 % | 1, flache Sonne — unsicher |
| PV2 | 150–175 Grad | 12 % | **2** (bis 160 Grad) |
| PV3 | 170–205 Grad | 23 % | 1 |
| PV4 | 200–225 Grad | 21 % | 1 |
| PV4 | 250–255 Grad | 51 % | 1, nahe der verworfenen Zone — unsicher |

## Die Ursache ist bekannt: der Giebel gegenueber

Per Foto belegt, siehe [`DIAGNOSE.md`](DIAGNOSE.md): das gegenueberliegende
Haus hat ein **Satteldach mit Spitze**. Der Lambda-foermige Schatten wandert
ueber die Reihe, und weil seine Kanten schraeg stehen, trifft er die vier
Straenge **nacheinander** statt gleichzeitig.

Genau das zeigt die Tabelle: ein zusammenhaengender Einbruch je Strang, aber
in modulabhaengig verschobenen Azimutbereichen —

```
PV1  135-155        (westlich, zuerst)
PV2       150-175
PV3            170-205
PV4                 200-225   (oestlich, zuletzt)
```

Die Live-Messung des Betreibers bei Azimut 165,4 Grad (PV2 9 %, PV3 rund 60 %,
PV1 und PV4 voll) trifft das Fach 165 Grad dieser Tabelle (PV2 17 %, PV3 66 %,
PV1 und PV4 100 %) — **unabhaengige Bestaetigung an einem anderen Tag.** Dass
dabei die Mitte im Schatten liegt und beide Raender frei sind, ist kein
Widerspruch zum Wandern, sondern eine Momentaufnahme davon.

### Zu den zwei Nebenfenstern

Das Verfahren kann mehrere getrennte Fenster je Strang abbilden, und es meldet
zwei: PV1 bei 275–280 Grad und PV4 bei 250–255 Grad. **Beide sind vermutlich
Artefakte, keine zweite Schattenquelle.**

- PV1 bei 275–280 Grad liegt kurz vor Sonnenuntergang bei rund 8 Grad
  Sonnenhoehe. Dort dominieren Horizont und Einfallswinkel.
- PV4 bei 250–255 Grad grenzt unmittelbar an das Fach 245 Grad, das wegen
  zusammengebrochenen Bezugs ganz verworfen wurde.

Mit der bekannten Giebelgeometrie ist **ein** zusammenhaengendes Fenster je
Strang die Erwartung. Die Faehigkeit, mehrere abzubilden, bleibt im Verfahren —
ausschliessen laesst sich ein weiteres Hindernis nicht, es ist nur nicht mehr
noetig, um die Messungen zu erklaeren.

### Warum das fuer die Ausbauentscheidung zaehlt

Eine feste Giebelgeometrie ist ueber den Azimut **extrapolierbar**. Im Winter
steht die Sonne tiefer, der Schatten reicht weiter — das Profil sagt vorher,
welche Module wann betroffen sind, ohne dass ein ganzes Jahr gemessen werden
muss. Das ist der eigentliche Wert der Azimut-Indizierung.

Der Vorbehalt bleibt: die *Uhrzeit*-Verschiebung faengt der Azimutbezug
vollstaendig auf, die groessere **Schattenlaenge** bei tieferer Sonne nicht.
Dafuer braeuchte es die Giebelhoehe und den Abstand, beides ist nicht gemessen.

## Theoretische Leistung ohne Verschattung

Das Profil sagt, *wann* verschattet wird. Zwei Sensoren sagen, *was es kostet* —
und zwar ohne Modell, ohne Prognose und ohne Einschwingen:

| Entity | Bedeutung |
|---|---|
| `sensor.pv_theoretische_leistung` | `4 x max(P1..P4)` in W |
| `sensor.pv_verschattungsverlust` | `P_theoretisch - P_ist` in W, auf 0 geklemmt |

### Die Referenz ist nicht das Maximum, sondern das Mittel der Besten

Vier baugleiche, koplanare Module mit je eigenem MPP-Tracker. Der Schatten ist
ein schmaler wandernder Streifen — zu jedem Zeitpunkt liefert **mindestens
einer unverschattet**.

Das schlichte Maximum waere dafuer der naheliegende Schaetzer, ist aber
**systematisch zu hoch**: das Maximum von vier verrauschten Werten liegt ueber
dem wahren Mittel. An den 355 Messpunkten des 12.08., an denen alle vier eng
beieinander liegen, ueberschaetzt es um **2,57 % im Median** (p90 5,16 %) — mal
vier ist das der Fehler in W, und er geht voll in den ausgewiesenen Verlust ein.
Die Momentaufnahme PV1 402 W bei 28,5 V gegen PV4 387 W bei 31,2 V zeigt, dass
das nicht nur Rauschen ist: die kaeltere Spannung von PV4 verraet die kuerzere
Besonnungsgeschichte.

Verglichen wurden vier Varianten am vollen Tageslauf (1275 Punkte):

| Variante | Median-Sprung zum Vorwert | Tagesverlust |
|---|---|---|
| `max` | 30,0 W | 2,23 kWh (18,1 %) |
| zweithoechster | 18,4 W | 1,67 kWh (14,1 %) |
| Median der Straenge ≥ 90 % vom Besten | 20,8 W | 2,00 kWh (16,5 %) |
| **Mittel der Straenge ≥ 90 % vom Besten** | **20,0 W** | **1,99 kWh (16,4 %)** |

Gewaehlt ist das **Mittel aller Straenge innerhalb von 10 % des besten**:

- Liegen mehrere unverschattet, mittelt es deren Rauschen weg — ein Drittel
  ruhiger als das Maximum.
- Liegt **nur einer** unverschattet, faellt es auf genau diesen einen zurueck
  und ist dann mit dem Maximum identisch.

Der **zweithoechste** ist ausdruecklich verworfen. Deckt der Schatten drei
Straenge — genau der Fall, um den es geht —, ist der zweithoechste selbst
verschattet, die Referenz bricht zusammen und der Verlust wird massiv
unterschaetzt. Sein scheinbar bester Glattheitswert erkauft sich das mit einem
Fehler in Richtung „kein Problem".

Gegenprobe am Tageslauf des 12.08.: **12,14 kWh theoretisch gegen 10,15 kWh
real, also 1,99 kWh oder 16,4 % Verschattungsverlust an einem klaren Tag.**

Der Vorteil gegenueber `pv_lernprognose`: das funktioniert ab der ersten
Sekunde. Kein Forecast.Solar, keine gelernte Tagesform, kein Systemgain, kein
`0 von 4 eingeschwungen`.

### Wann die Sensoren bewusst nichts liefern

`unknown` statt einer falschen Zahl, mit Begruendung im Attribut `grund`:

| `grund` | Warum |
|---|---|
| `Abregelung aktiv, Referenz waere gedrueckt` | bei vollem Speicher drosselt der Wechselrichter **alle vier** Tracker gleichzeitig; dann ist auch das Maximum gedrueckt und der Verlust erschiene faelschlich klein |
| `Abregelung nicht entscheidbar` | Aussentemperatur oder ein Strangregister fehlt — `None` ist hier nicht `nein` |
| `Einstrahlung zu schwach` | bester Strang unter `MIN_POWER_FOR_RATIO` (15 W); nachts ist die Aussage sinnlos |
| `Strangleistung unvollstaendig` | ein Register fehlt im Abbild |
| `alle vier eng und tief gegen Klarhimmel` | der Blindfleck, siehe unten |
| `alle vier eng, Klarhimmelbezug fehlt` | Blindfleck nicht pruefbar, weil `pv_lernprognose` keinen POA-Wert liefert |

Die Abregelungssperre benutzt dieselbe Entscheidung wie
`binary_sensor.pv_abregelung_erkannt`. Beide rufen `is_curtailed()` in
`physik.py` auf — vorher stand die Schwelle nur im Binaersensor, zwei Kopien
waeren ein Fehler, der erst auffiele, wenn jemand nur eine davon aendert.

Das Tagesintegral bleibt in diesen Zeiten **stehen** statt zu raten: die
Riemann-Integration akkumuliert nicht ueber `unknown`.

### Der Winter-Blindfleck

**Liegen alle vier Module gleichzeitig im Schatten, gibt es keine unverschattete
Referenz mehr.** Ohne Absicherung meldete das Verfahren dann `P_verlust = 0` —
obwohl der Verlust maximal ist.

Das ist kein Randfall. Im Sommer streift der Giebelschatten die Reihe nur mit
der Spitze; im Winter steht die Sonne tiefer, der Schatten wird laenger, und die
Schenkel legen sich ueber die ganze Reihe. **Ein total verschatteter Wintertag
saehe aus wie ein perfekter Tag** — und die Fehlerrichtung ist die denkbar
schlechteste, weil die Zahl in eine Ausbauentscheidung eingeht und in Richtung
„kein Problem" irrt.

Abgesichert ueber zwei Groessen, beide als Attribut sichtbar:

- **`traeger_straenge`** — wieviele Straenge innerhalb von 10 % des besten
  liegen und die Referenz tragen. Bei **4** liegen alle eng beieinander: dann
  ist entweder *nichts* verschattet oder *alles*.
- **`anteil_klarhimmel`** — die theoretische Leistung geteilt durch die
  geometrische Klarhimmelerwartung (`4 × 500 Wp × POA / 1000`).

Die Entscheidung:

| `traeger_straenge` | `anteil_klarhimmel` | Deutung |
|---|---|---|
| < 4 | egal | ein Strang sticht heraus, es gibt eine unverschattete Referenz — **gueltig** |
| 4 | ≥ 0,50 | alle hoch: nichts verschattet, Verlust wirklich null — **gueltig** |
| 4 | < 0,50 | alle tief: Bewoelkung **oder** Totalverschattung — **`unknown`** |

Als POA dient das Attribut **`poa_w_m2`** von
`sensor.pv_lernen_klarhimmelleistung` — reine Geometrie, nur gelesen. Der
*Zustand* dieses Sensors waere unbrauchbar: er enthaelt laut eigenem Hinweis
„Systemgain mal geometrische POA mal gelernte Tagesform", und beide gelernten
Groessen stehen bei `0 von 4 eingeschwungen` auf Platzhaltern.

Die Schwelle 0,50 ist grosszuegig gewaehlt. Am klaren Mittag des 13.08. lag der
Anteil bei **0,908** (POA 908 W/m², theoretisch rund 1650 W) — der Abstand zur
Schwelle ist also gross, und schwache Morgensonne loest nichts aus, weil die POA
dann ebenfalls klein ist.

**Bewoelkung und Totalverschattung sind mit vier koplanaren Modulen nicht
trennbar.** Beide sehen identisch aus: alle vier fallen gleichmaessig. Deshalb
nennt der Zustand beide Moeglichkeiten und entscheidet nicht. Wer die Trennung
braucht, braucht einen Sensor ausserhalb der Modulebene.

Warum `unknown` und nicht `0`: eine ausgewiesene Null liefe in das
Tagesintegral ein und behauptete „heute kein Verlust". `unknown` laesst das
Integral stehen, und der Grund steht im Attribut. Auf einem bedeckten Tag ist
der wahre Verschattungsverlust tatsaechlich nahe null — aber das *wissen* wir
nicht, und der Sensor darf es nicht behaupten.

### Drei Grenzen des Verfahrens

**Bewoelkung ist kein Verschattungsverlust.** Zieht eine Wolke ueber die ganze
Anlage, fallen alle vier gleichmaessig — das Maximum sinkt mit, der Verlust
geht korrekt gegen null. Das ist gewollt und **kein Fehler**.

**Gleichmaessige Verschmutzung oder ein Defekt an allen vier Modulen wird nicht
erfasst.** Das Verfahren misst ausschliesslich Unterschiede *zwischen* den
Straengen. Dafuer ist das Prognosemodell zustaendig, das gegen eine
Klarhimmelerwartung rechnet.

**PV4 als Referenz ist etwas gröber.** Strang 4 ist eine Differenz gegen die
in 10-W-Stufen gelieferte Gesamtleistung. Er ist an **40,9 %** der Messpunkte
des 12.08. der beste Strang, laesst sich also nicht ausschliessen. Der
Aufschlag ist aber klein — gemessen am Sprung zum jeweiligen Vorwert:

| bester Strang | Median | p90 |
|---|---|---|
| PV1–PV3 | 24,4 W | 86,0 W |
| PV4 | 32,0 W | 83,2 W |

Der Median steigt um rund 8 W, das p90 liegt sogar leicht darunter. Die
Streuung wird also von der natuerlichen Einstrahlungsschwankung dominiert,
nicht von der Quantisierung. **Spuerbar verrauscht ist die Groesse dadurch
nicht.** Das Attribut `referenz_ist_differenzwert` weist jeden solchen
Messpunkt trotzdem aus.

### Tagesenergie

Riemann-Integral (`integration`, Methode `left`, da beide Groessen sprungweise
aus dem Pollintervall kommen) plus `utility_meter` mit Tageszyklus:

| Entity | Bedeutung |
|---|---|
| `sensor.pv_theoretische_energie_tag` | was ohne Verschattung moeglich gewesen waere, kWh |
| `sensor.pv_verschattungsverlust_tag` | was die Verschattung gekostet hat, kWh |

Das ist die Zahl fuer die Ausbauentscheidung: nicht „18 % irgendwann", sondern
kWh pro Tag, aufsummiert ueber die Wochen bis Mitte September.

## Was fehlt

- **Jahresgang.** Zwei Tage im August. Wie sich die Fenster im Oktober
  verschieben, wenn die Sonne flacher steht und dieselben Objekte laenger
  werfende Schatten haben, ist damit nicht bestimmt. Der Azimutbezug faengt die
  *Uhrzeit*-Verschiebung auf, nicht die Aenderung der Schattenlaenge.
- **Bedeckte Tage.** Beide Messtage waren ueberwiegend klar. Bei diffusem Licht
  verschwindet der gerichtete Schatten und das Profil ueberschaetzt.
- **Der Lernstand steht auf `0 von 4 eingeschwungen`.** Dieses Profil kommt aus
  der Historie, nicht aus dem eingeschwungenen Schaetzer der Lernprognose.
  `sensor.pv_lernen_tagesform` steht auf 1,0 und ist bis auf Weiteres ohne
  Aussage; ausserdem ist sie eine Form fuer die **Gesamtanlage** und kann
  grundsaetzlich nicht sagen, welches Modul betroffen ist.

## Reproduktion

Die Auswertung ist ein eigenstaendiges Skript ohne Abhaengigkeiten:

```
node tools/verschattungsprofil.js
```

Es liest `tools/rohdaten/pv4_tag.jsonl` und schreibt die Tabelle nach stdout.
Die Recorder-Haelfte laesst sich nicht reproduzieren — die 5-Minuten-Statistik
verfaellt nach rund zehn Tagen.
