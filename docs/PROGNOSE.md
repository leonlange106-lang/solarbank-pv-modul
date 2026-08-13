# Kalibrierung von `sensor.nulleinspeisung_speicher_prognose`

Stand: 13.08.2026. Anlage: Anker SOLIX Solarbank 4 E5000 Pro, 5,1 kWh nutzbar,
4 × 500 Wp, Azimut 188°, Neigung 20°, AC-Ausgang auf 800 W begrenzt.
Standort Hamm/NRW (51,674° N, 7,815° O), Zeitzone Europe/Berlin.

**Nichts ausgerollt.** Es wurde keine Entity, kein Helper, keine Automation und
kein YAML geändert. Reine Auswertung der HA-Historie.

Reproduzierbar über `tools/backtest_prognose.py` mit den Datei-Caches
`tools/prognose_daten.json` und `tools/prognose_daten_5min.json`.

---

## 0. Kurzfassung

Die drei Parameter, nach denen gefragt war, sind **nicht** die Ursache des
Prognosefehlers. Das Modell liegt auf allen auswertbaren Tagen um
**−22 bis −29 Prozentpunkte zu niedrig**, und zwar bei *jeder* Kombination aus
`EXPONENT`, Klammer und Mittelungsfenster. Der Fehler steckt im **Pegel**, nicht
in der Kurvenform:

1. **Forecast.Solar unterschätzt diese Anlage um rund 30 %.** Für die
   Vormittags-Startzeitpunkte (geringste Zensur durch Abregelung) liegt der
   Median von `ist_rest / rohrest` bei **1,42**.
2. **Das vorbelegte Hauslastprofil ist zu hoch**, vor allem um 14 und 15 Uhr,
   wo die Reglertests stecken.
3. **Die `k`-Korrektur verschlimmert es**, weil sie die Nachmittagsverschattung
   als „bewölkt" liest und diese Fehlmessung auf den ganzen Resttag hochrechnet.

Die Verschattung ist bestätigt und quantifiziert (Abschnitt 4) — sie ist eine
**Delle zwischen 12:30 und 15:30 mit Erholung ab 16 Uhr**, kein gleichmäßiger
Nachmittagsabfall. Eine symmetrische `cos^n`-Kurve kann das grundsätzlich nicht
abbilden.

**Empfehlung** (Fehlermaße in Abschnitt 7):

| Parameter | alt | neu | Begründung |
|---|---|---|---|
| Hauslastprofil | Mittel 11./12.08. | Juli-Median, Abschnitt 3 | 19 saubere Tage statt 2 verseuchte |
| Pegelkorrektur auf `rohrest` | *fehlt* | **1,30** | Abschnitt 2, wichtigste Einzeländerung |
| `EXPONENT` | 2 | **2,5** | Abschnitt 5, Kompromiss; 2,0–3,0 gleichwertig |
| `KMIN` / `KMAX` | 0,6 / 1,6 | **0,85 / 1,15** | Abschnitt 6, weite Klammer schadet nachweislich |
| Mittelungsfenster | 20 min | **15 min** | Abschnitt 6, Effekt klein |
| Vormittags-Halbbreite | `sunset − peak` | **`peak − sunrise`** | Abschnitt 6, Strukturfehler |

Damit sinkt der mittlere absolute Fehler des Maximal-SOC von **28,6 auf 7,7
Prozentpunkte**, der Zeitfehler von **95 auf 43 Minuten**.

**Wie belastbar ist das?** Der Pegel (Punkt 1–2) ist gut belegt: vier
unabhängige Tage zeigen dieselbe Richtung, und eine unabhängige physikalische
Rechnung bestätigt sie. Der `EXPONENT` ist **nicht bestimmbar** — siehe
Abschnitt 5. Dafür reichen vier Tage nicht, und ich erfinde keinen Wert.

---

## 1. Datenlage

Der Recorder reicht **nicht** bis zum 08.08. zurück, wie angenommen, sondern nur
bis **08.08. 12:00**. Damit sind auswertbar:

| Tag | Status |
|---|---|
| 08.08. | ab 12:00, PV konstant 798 W über sechs Stunden → Drosselungstest, **unbrauchbar** |
| 09.–12.08. | vollständig, **4 verwertbare Tage** |
| 13.08. | laufend, Ausgang unbekannt → nur Live-Prognose, kein Backtest |

```
Tag         Sonne        astr. Mittag   PV gemessen*   Forecast.Solar
2026-08-09  06:03-21:05  13:34           9,02 kWh       6,28 kWh
2026-08-10  06:05-21:03  13:34           9,12 kWh       7,71 kWh
2026-08-11  06:06-21:01  13:34          10,37 kWh       9,14 kWh
2026-08-12  06:08-20:59  13:34          10,79 kWh       8,15 kWh
```
\* Sonnenauf-/-untergang astronomisch gerechnet (NOAA), nicht aus der Historie.
Der gemessene Ertrag ist eine **Untergrenze**: sobald der Speicher voll ist,
regelt die Nulleinspeisung die PV auf die Hauslast herunter (auf allen vier
Tagen sichtbar als Plateau bei ~798 W).

**Zwei Einschränkungen, die den Backtest begrenzen:**

- Auf **allen vier Tagen** erreichte der Speicher 100 %. Der Vergleich
  „prognostizierter gegen tatsächlicher Maximal-SOC" ist damit **zensiert** —
  ein Modell, das zu hoch schätzt, wird nicht bestraft. Als Hauptmaß dient
  deshalb der **RMSE der SOC-Bahn** bis zum ersten Erreichen von 100 %; das sind
  je Lauf 20–40 Vergleichspunkte statt einem.
- Es ist **kein durchgehend bedeckter Tag** dabei. Was `k` leisten *soll*, lässt
  sich an diesen Daten nicht messen — nur, was es hier anrichtet.

---

## 2. Der eigentliche Fehler: der Pegel

`rohrest` gegen die tatsächlich noch erzeugte Energie ab dem Startzeitpunkt:

```
Tag        | 08:00 09:00 10:00 11:00 12:00 13:00 14:00 15:00 16:00 | Median
2026-08-09 |  1,40  1,49  1,48  1,48  1,39  1,36  1,18             |  1,40
2026-08-10 |  1,44  1,44  1,39  1,31  1,19  0,88  0,80             |  1,31
2026-08-11 |  1,26  1,25  1,20  1,14  0,98  0,95  0,94  0,93       |  1,06
2026-08-12 |  1,55  1,48  1,44  1,51  1,49  1,48  1,42  1,36  1,10 |  1,48

alle 31 Startzeitpunkte:   Median 1,36   Mittel 1,28
nur Start <= 12:00:        Median 1,42   Mittel 1,36
```

Die Werte unter 1,0 am späten Nachmittag sind **kein Gegenbeleg** — dort ist die
Messung bereits abgeregelt und damit künstlich klein. Die Vormittagswerte sind
die ehrlichen.

**Unabhängige Gegenprobe.** Aus Sonnenstand, Modulazimut 188°, Neigung 20° und
einem Klarhimmelmodell lässt sich die Einstrahlung auf die Modulebene rechnen.
Eicht man den Systemwirkungsgrad am nachweislich klaren, unverschatteten
Vormittag (09:00–11:30) der beiden klaren Tage, ergibt sich für einen klaren Tag
**mit** der gemessenen Verschattung ein Ertrag von **12,0 kWh**. Forecast.Solar
sagte für dieselben Tage 8,2 bzw. 9,1 kWh. Das ist derselbe Faktor von rund 1,3.

Ob die Ursache eine zu niedrig eingetragene kWp-Zahl, die DC/AC-Definition oder
ein zu pessimistischer Verlustansatz ist, lässt sich aus der Historie nicht
entscheiden — für das Modell ist nur der Faktor relevant.

> **Vorbehalt zur Multiplikation.** Der Faktor ist an Prognosen von 6–9 kWh
> geeicht. Für den 13.08. sagt Forecast.Solar 9,67 kWh; die physikalische
> Erwartung liegt bei 11,94 kWh, also Faktor 1,23. Ein fester Faktor von 1,30
> würde hier leicht überschießen. Mit vier Tagen ist nicht zu entscheiden, ob
> der Bias rein multiplikativ ist. Sinnvoll wäre eine Deckelung auf einen
> physikalisch plausiblen Tageswert (~12 kWh für diese 2 kWp).

---

## 3. Hauslastprofil

Das vorbelegte Profil ist der **Mittelwert aus genau zwei Tagen** (11. und
12.08.) von `sensor.anker_solix_solarbank_4_e5000_pro_441_startseite_last`. Das
lässt sich nachrechnen: 14 Uhr = Mittel aus 1472 W (11.08.) und 543 W (12.08.)
= **1008 W**, 15 Uhr = Mittel aus 842 W und 1281 W = **1062 W**. Genau die
beiden Werte aus der Aufgabenstellung. Die Reglertests stecken also unmittelbar
drin.

Diese Entity taugt auch nicht als Basis: sie liefert **erst ab 10.08. 18:00**
Werte, davor steht das Register konstant auf 0. Es gibt also nur 2,7 Tage — und
das sind genau die verseuchten.

**Bessere Quelle:** `sensor.stromleser_emh_power`, der IR-Lesekopf am Zähler.
Er reicht bis zum 20.07. zurück. Entscheidend: **vor dem 08.08. 12:00 gab es
keine PV**, also ist die Netzleistung dort identisch mit der Hauslast. Das
ergibt **17–18 saubere Tage je Stunde**, ohne Solarbank, ohne Reglertests.

| h | Juli-Median | Juli-Mittel | vorbelegt | Differenz | h | Juli-Median | Juli-Mittel | vorbelegt | Differenz |
|---|---|---|---|---|---|---|---|---|---|
| 00 | 355 | 373 | 370 | +15 | 12 | 485 | 509 | 385 | −100 |
| 01 | 324 | 327 | 294 | −31 | 13 | 657 | 698 | 695 | +38 |
| 02 | 318 | 329 | 262 | −55 | **14** | **501** | 598 | **1008** | **+506** |
| 03 | 267 | 289 | 255 | −12 | **15** | **584** | 604 | **1062** | **+478** |
| 04 | 292 | 293 | 290 | −2 | 16 | 579 | 629 | 666 | +87 |
| 05 | 351 | 338 | 326 | −25 | 17 | 568 | 602 | 700 | +131 |
| 06 | 541 | 515 | 598 | +57 | 18 | 682 | 772 | 595 | −87 |
| 07 | 480 | 481 | 528 | +48 | 19 | 629 | 737 | 973 | +344 |
| 08 | 400 | 435 | 397 | −3 | 20 | 550 | 695 | 657 | +107 |
| 09 | 497 | 499 | 460 | −37 | 21 | 587 | 631 | 434 | −154 |
| 10 | 385 | 445 | 468 | +83 | 22 | 510 | 584 | 539 | +29 |
| 11 | 394 | 476 | 462 | +68 | 23 | 392 | 452 | 445 | +53 |

**Tagessumme: Median 11,33 kWh, Mittel 12,31 kWh, vorbelegt 12,87 kWh.**

Der Befund bestätigt den Verdacht exakt: **14 Uhr ist um 506 W, 15 Uhr um 478 W
überhöht** — jeweils rund das Doppelte des Medians. Das sind die 1,4-kW-Tests.
Zusätzlich fällt 19 Uhr mit +344 W auf; auch das ist ein Zwei-Tage-Artefakt
(12.08. um 19 Uhr: 1404 W).

Der **Median** schlägt das Mittel im Backtest deutlich (RMSE-Bahn 12,4 gegen
13,8 pp), weil er einzelne Großverbraucher-Stunden nicht in den ganzen Tag
schmiert. Empfohlene Werte als Liste (Index 0 = 00 Uhr):

```
355, 324, 318, 267, 292, 351, 541, 480, 400, 497, 385, 394,
485, 657, 501, 584, 579, 568, 682, 629, 550, 587, 510, 392
```

> Vorbehalt: Das Profil stammt aus dem Juli. Änderte sich der Haushalt seither
> systematisch, trägt es das nicht nach. Es ist der Zwei-Tage-Basis aber in
> jeder Hinsicht überlegen.

---

## 4. Die Nachmittagsverschattung — bestätigt

Drei unabhängige Zugänge, gleiches Ergebnis.

**a) Zeitpunkt der Tagesspitze.** Eine Südanlage (188°) hat ihre Spitze am
astronomischen Mittag. Gemessen:

```
2026-08-09  Spitze 11:30   Mittag 13:34   Versatz −124 min
2026-08-10  Spitze 11:25   Mittag 13:34   Versatz −129 min
2026-08-11  Spitze 11:25   Mittag 13:34   Versatz −129 min
2026-08-12  Spitze 11:25   Mittag 13:34   Versatz −129 min
```

Über zwei Stunden zu früh, auf allen vier Tagen auf fünf Minuten reproduzierbar.

**b) Messung gegen geometrische Klarhimmelerwartung.** Systemwirkungsgrad geeicht
auf 09:00–11:30 (klarer, unverschatteter Vormittag) = 1,00. `zens` = Speicher
voll, PV abgeregelt, Messung nicht aussagekräftig.

```
Zeit   11:00 11:30 12:00 12:30 13:00 13:30 14:00 14:30 15:00 15:30 16:00 16:30
08-09   0,97  1,11  0,98  0,85  0,74  0,72  0,74  zens  zens  zens  zens  zens
08-10   0,99  0,91  0,86  0,73  0,65  0,69  0,62  zens  zens  zens  zens  zens
08-11   0,98  0,90  0,82  0,68  0,62  0,61  0,62  0,61  0,64  zens  zens  zens
08-12   0,94  0,89  0,73  0,66  0,63  0,56  0,57  0,60  0,59  0,77  0,87  0,93
Median  0,97  0,90  0,84  0,71  0,64  0,65  0,62  0,60  0,62  0,77  0,87  0,93
```

Das ist die Verschattung, sauber quantifiziert: ab **12:00 setzt der Abfall
ein**, zwischen **13:00 und 15:00 fehlen 35–40 %**, ab **15:30 erholt es sich
wieder**, um 16:30 sind 93 % erreicht. Vier Tage, gleiche Kurve.

**c) Modulebene.** Die Beobachtung vom 11.08. um 14:40 (418/413/273/60 W) fügt
sich ein: Gesamtleistung 1164 W, gemessen 1156 W — der Schatten steht zu diesem
Zeitpunkt auf Modul 3 und 4.

### Was das für das Modell heißt

Die Delle liegt **genau in dem Fenster, in dem das Modell sein Maximum
verortet**. Zwei Folgen:

1. **`cos^n` kann das strukturell nicht.** Die reale Kurve ist ein Plateau mit
   einer Kerbe, kein Glockenberg. Deshalb ziehen die beiden natürlichen
   Gütekriterien in verschiedene Richtungen (Abschnitt 5).
2. **`k` liest die Delle als Bewölkung.** `gemessen` wird zwischen 12 und 16 Uhr
   um 35–40 % gedrückt, `k` schließt auf einen schlechten Tag und rechnet das
   auf den **ganzen Resttag** hoch — auch auf 16–20 Uhr, wo der Schatten längst
   weg ist. Das mittlere `k` nach Startstunde zeigt es:

```
Start  08:00 09:00 10:00 11:00 12:00 13:00 14:00 15:00 16:00
k       0,36  0,66  0,81  1,04  0,92  0,85  0,84  0,76  0,90
```

Ein systematisch zu kleines `k` in genau den Stunden, in denen der Sensor
üblicherweise abgefragt wird.

### Ein zusätzlicher Strukturfehler

Der Einbruch auf **`k` = 0,36 um 08:00** hat eine andere Ursache. Das Modell
verwendet `width = (sunset − peak)` für **beide** Seiten der Kurve. Weil
Forecast.Solar den Spitzenzeitpunkt auf 11:00–13:00 legt und die Sonne erst um
21:00 untergeht, wird `width` ≈ 9,5 h — die Kurve reicht damit bis etwa
**02:00 Uhr** zurück. Um 08:00 steht das Modell also schon fast auf halber Höhe,
während real gerade der steile Morgenanstieg beginnt. `modelljetzt` ist viel zu
hoch, `k` bricht ein.

Abhilfe: Vormittagsseite auf `peak − sunrise` stauchen. Das hebt `k` um 09:00
von 0,66 auf 0,87 und um 10:00 von 0,81 auf 0,91.

---

## 5. `EXPONENT` — nicht bestimmbar

`EXPONENT` und Pegel sind **austauschbar**: eine schmalere Kurve schiebt mehr
Energie in die nächsten Stunden, ein höherer Pegel auch. Rechnet man je
`EXPONENT` den jeweils besten Pegel aus (profilierte Güte, `k` abgeschaltet),
bleibt für die Bahn-Güte ein flaches Tal:

```
EXP  | bestes gain | RMSE-Bahn | MAE Zeit | Modellspitze | real
1,00 |        1,55 |      5,58 |    66 min|     1,25 kW  | 1,48 kW
1,25 |        1,45 |      5,66 |    67 min|     1,24 kW  |
1,50 |        1,40 |      5,84 |    61 min|     1,26 kW  |
1,75 |        1,40 |      6,06 |    49 min|     1,32 kW  |
2,00 |        1,35 |      6,27 |    48 min|     1,33 kW  |
2,25 |        1,30 |      6,50 |    45 min|     1,33 kW  |
2,50 |        1,30 |      6,76 |    43 min|     1,38 kW  |
2,75 |        1,25 |      6,95 |    43 min|     1,37 kW  |
3,00 |        1,25 |      7,18 |    45 min|     1,41 kW  |
3,50 |        1,20 |      7,58 |    44 min|     1,44 kW  |
4,00 |        1,15 |      7,97 |    45 min|     1,45 kW  |
```

**Die Kriterien widersprechen sich:**

- Die **Bahn-Güte** zieht zu kleinen Exponenten (Minimum bei 1,0; innerhalb
  +0,5 pp liegt der ganze Bereich **1,00–1,75**).
- Die **Spitzenleistung** zieht zu großen. Real werden im Mittel **1,48 kW**
  erreicht; `EXPONENT` = 2 liefert 1,33 kW (−10 %), erst ab 3,0 wird es
  getroffen. Das ist genau das Kriterium, mit dem `EXPONENT` = 1 schon verworfen
  wurde — zu Recht: 1,25 kW gegen 1,48 kW real.
- Der **Zeitpunkt** des Maximums ist am besten bei 2,25–2,75 (43–45 min).

Beides zugleich ist mit einer symmetrischen Glocke nicht zu haben — weil die
reale Kurve ein Plateau mit Kerbe ist (Abschnitt 4). Eine Glocke, die die Spitze
trifft, ist zu schmal für die Energie; eine, die die Energie trifft, ist zu flach
für die Spitze.

**Empfehlung: `EXPONENT` = 2,5.** Das ist der Kompromiss: Spitze 1,38 kW
(−7 % statt −10 %), bester Zeitpunktfehler, Bahn-RMSE 1,2 pp über dem flachen
Optimum. **Der Unterschied zu 2,0 ist zweitrangig** — wer nichts ändern will,
verliert wenig. Was aus diesen Daten *nicht* geht, ist die Behauptung, ein Wert
sei signifikant besser als sein Nachbar.

---

## 6. Klammer und Mittelungsfenster

Klammer, bei `EXPONENT` = 2,5, gain 1,30, Profil Juli-Median, Fenster 15 min:

```
KMIN  KMAX | Bias SOC | MAE SOC | MAE Zeit | RMSE Bahn | k-Mittel | am Anschlag
1,00  1,00 |     −3,2 |    3,18 |   43 min |      6,8  |    1,00  |    (aus)
0,90  1,10 |     −5,9 |    5,86 |   44 min |      6,8  |    0,95  |     74 %
0,85  1,15 |     −7,7 |    7,72 |   43 min |      7,3  |    0,93  |     68 %
0,80  1,25 |     −9,3 |    9,30 |   45 min |      7,9  |    0,91  |     52 %
0,70  1,40 |    −12,2 |   12,22 |   44 min |      9,3  |    0,87  |     35 %
0,60  1,60 |    −14,4 |   14,37 |   47 min |     10,5  |    0,84  |     16 %
0,40  2,00 |    −16,4 |   16,38 |   63 min |     11,8  |    0,82  |      6 %
```

Monoton: **je enger, desto besser.** Die heutige Klammer 0,6/1,6 ist zu weit —
sie lässt `k` genau die Fehlmessung durchreichen, gegen die sie schützen soll.
Der Extremfall („`k` ganz aus") ist auf diesen Daten der beste.

**Ich empfehle trotzdem nicht, `k` abzuschalten**, sondern 0,85/1,15. Grund: In
der Stichprobe ist **kein bedeckter Tag**. Was `k` leisten soll — einen Tag
retten, der deutlich schlechter kommt als prognostiziert — kann hier nicht
gemessen werden. Eine enge Klammer behält die Anpassungsfähigkeit und deckelt
den nachgewiesenen Schaden. Wer rein auf die vorliegende Evidenz optimiert,
setzt `KMIN` = `KMAX` = 1 und gewinnt weitere 4,5 pp.

Mittelungsfenster, bei `EXPONENT` = 2,5, gain 1,30, Klammer 0,85/1,15:

```
Fenster |  5     10    15    20    30    45    60    90 min
MAE SOC | 7,20  7,15  7,72  8,02  9,04 10,37 10,74 10,98 pp
MAE Zeit| 46    45    43    42    42    43    41    39   min
RMSE    | 7,4   7,2   7,3   7,2   7,3   8,0   8,1   8,2  pp
```

Kurz ist besser für den SOC, lang minimal besser für den Zeitpunkt. Zwischen
5 und 30 Minuten ist der RMSE praktisch konstant (7,2–7,4 pp) — das Fenster ist
der unwichtigste der drei Parameter. **10 bis 20 min sind gleichwertig**;
15 min ist ein vernünftiger Mittelweg, das heutige 20 min ebenso vertretbar.
Ab 45 min wird es messbar schlechter. Ist `k` abgeschaltet, ist das Fenster
bedeutungslos.

---

## 7. Fehlermaße

31 Läufe (4 Tage × stündliche Startzeitpunkte 08:00–16:00, soweit sinnvoll).
`Bias`/`MAE` in Prozentpunkten des Maximal-SOC, `Zeit` in Minuten,
`RMSE` = Wurzel des mittleren quadratischen Fehlers der SOC-Bahn.

| Konfiguration | Bias | MAE | Zeit | RMSE |
|---|---|---|---|---|
| **alt** EXP 2,0 · 0,6/1,6 · 20 min · Profil vorbelegt | −28,6 | 28,64 | 95 | 17,2 |
| nur Profil neu (Juli-Median), sonst alles alt | −22,3 | 22,30 | 51 | 13,7 |
| EXP 2,0 · 0,85/1,15 · 15 min · Pegel 1,30 · asym. · Juli | −10,7 | 10,69 | 40 | 7,8 |
| **empfohlen** EXP 2,5 · 0,85/1,15 · 15 min · 1,30 · asym. · Juli | **−7,7** | **7,72** | **43** | **7,3** |
| dieselbe, aber `k` aus | −3,2 | 3,18 | 43 | 6,8 |

Der Restbias von −7,7 pp ist nicht wegzukalibrieren: er entsteht überwiegend
daraus, dass `k` an verschatteten Vormittagen unter 1 bleibt.

### Validierungspunkt 12.08.

Die geforderte Trajektorie wird von den Daten exakt bestätigt:

```
gemessen   10:05 → 15 %   12:00 → 45 %   14:00 → 72 %   16:00 → 91 %
           100 % erstmals um 16:40
```

Modelllauf ab 10:05 (SOC 12 %, `rohrest` 5,571 kWh, `peak` 11:00):

| Konfiguration | Prognose |
|---|---|
| alt | 51,4 % um 14:05 (`k` = 1,12) |
| empfohlen | 61,8 % um 15:20 (`k` = 0,85) |
| empfohlen, `k` aus | 78,5 % um 15:50 (`k` = 1,00) |

**Kein Parametersatz trifft diesen Punkt.** Der Grund steht in Abschnitt 2:
Forecast.Solar sagte am 12.08. um 10:11 noch 5,571 kWh Rest vorher, tatsächlich
kamen mindestens 8,9 kWh. Selbst mit Faktor 1,30 fehlt dem Modell rund 1,3 kWh.
Der 12.08. war mit einem impliziten Faktor von etwa **1,5** der am stärksten
unterschätzte Tag der Stichprobe.

Das ist die ehrliche Grenze: Die Streuung des Forecast.Solar-Bias von 1,19 bis
1,55 lässt sich mit einem festen Faktor nicht auffangen. Die Richtung stimmt
(51 % → 78 %), das Ziel wird nicht erreicht.

### Heute, 13.08., Stand 10:45 (SOC 25 %, `rohrest` 8,216 kWh, `peak` 13:00)

| Konfiguration | Prognose |
|---|---|
| alt | 96,9 % um 17:15 |
| empfohlen | 100 % um 14:30 |
| empfohlen, `k` aus | 100 % um 14:00 |

Der Verdacht aus der Aufgabenstellung, der Endwert sei zu niedrig, bestätigt
sich. Die neue Prognose ist aber am oberen Rand: Faktor 1,30 auf die heute
ohnehin hohe Prognose von 9,67 kWh ergibt 12,6 kWh, während die physikalische
Klarhimmelerwartung bei 11,94 kWh liegt. Realistisch ist **100 % zwischen 14:30
und 16:00**.

---

## 8. Was nicht geht und wie es weitergeht

**Nicht belastbar aus vier Tagen:**

- `EXPONENT` auf 0,25 genau. Der Bereich 2,0–3,0 ist gleichwertig; die Wahl
  innerhalb dieses Bereichs ist Geschmackssache, solange der Pegel stimmt.
- Der Nutzen von `k`. Ohne bedeckten Tag lässt sich nur der Schaden messen.
- Ob der Forecast.Solar-Bias multiplikativ oder teils additiv ist.

**Der eigentliche Hebel liegt woanders.** Solange die Kurvenform symmetrisch
bleibt, bleibt die Verschattungsdelle unmodelliert. Wirksamer als jedes
Feilen an `EXPONENT` wäre, das Gewicht `w[i]` mit dem gemessenen
Verschattungsprofil aus Abschnitt 4b zu multiplizieren — eine Tabelle mit zwölf
Halbstundenwerten. Damit würde auch `k` wieder das messen, wofür es gedacht ist:
Bewölkung statt Schatten. Das ist ein Modelleingriff, kein Parameter, und
gehörte separat entschieden.

### Backtest in zwei Wochen wiederholen

Die Recorder-Retention von ~10 Tagen ist der Engpass. Damit in zwei Wochen mehr
als vier Tage zur Verfügung stehen:

1. **Jetzt** ein `recorder`-Exclude prüfen bzw. die Retention für die fünf
   relevanten Entities verlängern — oder besser: einen `statistics`-Helper
   anlegen, denn **Langzeitstatistiken bleiben dauerhaft erhalten**. Für
   `..._soc` und `..._solarstrom` reicht `state_class: measurement`, das ist
   bereits gesetzt; die Stundenstatistik bleibt also ohnehin. Nur die
   5-Minuten-Auflösung fällt nach 10 Tagen weg. Für den Backtest genügt die
   Stundenauflösung bei allem außer der Zeitpunktbestimmung.
2. **`rohrest` und `peak` sichern.** Beide haben keine `state_class` und sind
   deshalb nach 10 Tagen unwiederbringlich weg. Das ist die eigentliche Lücke.
   Ein kleiner Template-Sensor mit `state_class: measurement` auf
   `energy_production_today_remaining` würde sie dauerhaft konservieren — das
   ist die einzige Vorbereitung, die wirklich nötig ist.
3. **Lauf wiederholen** mit `python tools/backtest_prognose.py`. Die
   Datei-Caches neu ziehen (die Abschnittsstruktur des Skripts gibt vor, welche
   Entities in welcher Auflösung gebraucht werden), dann läuft die Auswertung
   unverändert durch.
4. **Worauf zu achten ist:** mindestens ein bedeckter Tag und mindestens ein Tag,
   an dem der Speicher **nicht** voll wird. Ohne den zweiten bleibt die
   Endwert-Metrik zensiert; ohne den ersten bleibt `k` unbewertbar.

---

## 9. Dateien

| Datei | Inhalt |
|---|---|
| `tools/backtest_prognose.py` | Modellnachbau, Backtest, alle Parametersweeps, Verschattungsanalyse |
| `tools/prognose_daten.json` | Stundenwerte: Netzleistung (20.07.–11.08.), Hauslast, PV |
| `tools/prognose_daten_5min.json` | 5-Minuten-Werte SOC und PV (09.–12.08.), Forecast.Solar-Rohhistorie |

Aufruf: `python tools/backtest_prognose.py` (vollständig) oder `--kurz`.

---

# Teil II: Die lernende Architektur

Stand: 13.08.2026. Teil I oben ist die Fehleranalyse des alten Modells und
bleibt unverändert stehen — er ist die Begründung für alles, was hier folgt.

Die Vorgabe des Betreibers lautet:

> „Bitte so bauen dass es sich immer dynamisch auf neue Lastmuster und
> Sonnenmuster/Wettermuster anpassen kann. Niemals irgendwas fix festlegen."

und ergänzend:

> „die physikalischen kennwerte sollten aber immer auch auf messwerte
> referenzieren. 5,1kwh bspw. auf die kapazität welche per tcp ausgelesen wird
> […] damit sofern aufgestockt wird dies sich dynamisch erweitert."

Umgesetzt in der Integration `custom_components/pv_lernprognose`.

## 10. Warum eine eigene Integration und nicht pyscript

Beides wäre gegangen, pyscript ist installiert. Ausschlaggebend waren vier
Punkte:

- **Persistenz.** Der Lernstand muss Neustarts überleben.
  `homeassistant.helpers.storage.Store` schreibt versioniert und atomar und
  wird beim Herunterfahren von Home Assistant selbst noch geleert. In pyscript
  müsste man Dateien von Hand schreiben — ein halb geschriebener Lernstand ist
  schlimmer als keiner.
- **Kaltstart aus der Langzeitstatistik.** Das braucht den Recorder-Executor
  (`get_instance(hass).async_add_executor_job`). Aus pyscript heraus blockiert
  man damit leicht den Event-Loop.
- **Sichtbarkeit.** Die gelernten Größen sollen Entities mit stabiler
  `unique_id` sein, damit die Langzeitstatistik sie behält und man ihnen über
  Monate beim Lernen zusehen kann. pyscript-Entities haben keine `unique_id`
  und stehen nicht in der Entity-Registry.
- **Muster im Haus.** `custom_components/solarbank_pv` führt bereits
  Coordinator, Entity-Beschreibungen und Attributkonventionen vor.

Die Integration ist **rein lesend**. Kein Modbus-Schreibzugriff, kein
Service-Call, keine Zustandsänderung an fremden Entities.

## 11. Das neue Modell in einer Zeile

Statt `cos^EXPONENT` um einen Spitzenzeitpunkt:

```
P(t) = Systemgain · POA_klar(t) · Tagesform(Azimut(t)) · Trübung(t)
```

| Faktor | Herkunft | Was er einfängt |
|---|---|---|
| `POA_klar(t)` | reine Geometrie, keine freien Parameter | Sonnenstand, Jahreszeit, Modulebene |
| `Systemgain` | **gelernt** | Modulfläche, Systemwirkungsgrad, bifazialer Mehrertrag |
| `Tagesform` | **gelernt je Sonnenazimut** | die Verschattung aus Abschnitt 4 |
| `Trübung` | tagesaktuell aus Messung und Forecast.Solar | Bewölkung |

Der entscheidende Unterschied zum alten Modell: **die Verschattung steckt jetzt
in der Tagesform, nicht in der Trübung.** Damit misst die Trübung endlich das,
wofür `k` gedacht war. Abschnitt 4 hatte gezeigt, dass `k` die
Nachmittagsdelle als Bewölkung las und auf den ganzen Resttag hochrechnete —
dieser Fehler ist konstruktiv ausgeschlossen.

Tag und Nacht sind kein getrennter Zweig mehr, sondern ein durchgehender Lauf
über 24 Stunden. Nachts ist `POA_klar` null, damit ist die Erzeugung null, und
die Bilanz entlädt von selbst.

## 12. Die gelernten Größen

Alle vier folgen demselben Muster: **zweistufiger Median** (erst je Tag
verdichten, dann über die Tage), **MAD-Ausreißerfilter** vor der zweiten Stufe,
**Rezenzgewichtung** mit 14 Tagen Halbwertszeit.

Zwei Stufen, weil beide Fehlerarten vorkommen: einzelne verrückte Messpunkte
innerhalb eines Tages (der Reglertest um 14 Uhr) und ganze verrückte Tage (der
Drosselungstest am 08.08.). Ein einstufiger Median über alle Punkte würde einen
langen schlechten Tag durchlassen, weil er viele Punkte beisteuert.

| Größe | Fenster | Index | Robustheit | Startwert | eingeschwungen ab |
|---|---|---|---|---|---|
| **Hauslastprofil** | 28 Tage | Stunde × (Werktag/Wochenende) | Median je Stunde und Tag, dann gewichteter Median über Tage — **ohne** MAD-Filter, Begründung in Abschnitt 19 | Startprofil aus der Zählerhistorie, 43 Tage (Abschnitt 19) | 7 Tage je Stunde und Tagestyp |
| **Pegel vs. Forecast.Solar** | 21 Tage | — | ein Wert je Tag, dann gewichteter Median nach MAD-Filter | 1,42 (Abschnitt 13) | 5 Tage |
| **Tagesform** | 45 Tage | Sonnenazimut in 5°-Fächern | Median je Fach und Tag, dann gewichteter Median über Tage | 1,0 („keine Verschattung bekannt") | 4 Tage **und** 8 Proben je Fach |
| **Systemgain** | 45 Tage | — | 0,90-Quantil über die belegten Azimutfächer | 2,06 W/(W/m²) | 8 belegte Fächer |
| **Speicherwirkungsgrad** | 21 Tage | — | ein Wert je Tag, dann gewichteter Median nach MAD-Filter | 0,95 | 5 Tage |

Jede Größe hat eine eigene Entity und meldet in ihren Attributen `gelernt`
(true/false) und `stichprobe`. Solange `gelernt: false` steht, liefert sie den
Startwert und sagt genau das.

### Warum die Tagesform nach Azimut indiziert ist, nicht nach Uhrzeit

Ein Baum oder Dachvorsprung steht fest im Raum. Er verschattet immer dann, wenn
die Sonne in seiner Richtung steht — unabhängig vom Datum. Über Uhrzeit
indiziert müsste die Kurve jeden Monat neu gelernt werden; über Azimut
indiziert wandert sie von selbst mit dem Sonnenlauf durch die Jahreszeiten mit.
Genau das war gefordert.

Die verbleibende Abhängigkeit ist die **Sonnenhöhe**: dasselbe Hindernis
verschattet bei flacher Wintersonne stärker als bei hoher Sommersonne. Das
fängt die Rezenzgewichtung ab — der Schätzer folgt der Jahreszeit mit etwa zwei
bis drei Wochen Nachlauf. Eine zweite Indexachse über die Höhe wäre
physikalisch sauberer, würde die Stichprobe je Fach aber so ausdünnen, dass
nichts mehr einschwingt. **Das ist eine bewusste Abwägung, keine Auslassung.**

### Wie Ausreißer aussortiert werden, ohne dass jemand sie benennt

Der 08.08. (PV sechs Stunden konstant 798 W wegen Drosselungstest) fällt durch
drei unabhängige Siebe:

1. **SOC am oberen Anschlag** (`smax − 1 pp`). Dann drosselt die
   Nulleinspeisung die PV auf die Hauslast, und die Messung zeigt nicht mehr
   das Dargebot.
2. **Leistung steht still, während die Geometrie sich bewegt.** Über 30 Minuten
   entrendete Reststreuung unter 1 % bei gleichzeitig über 10 % Änderung der
   Klarhimmelerwartung. Kein Naturvorgang sieht so aus. Das ist genau das
   Muster des 08.08. — erkannt am Muster, nicht am Datum.
3. **MAD-Filter über die Tage.** Ein Tag, der um mehr als 3,5 modifizierte
   z-Werte abweicht, fällt aus der zweiten Medianstufe heraus.

Für die Tagesform kommt ein viertes Sieb hinzu: **Klarheit.** Ein Messpunkt
geht nur ein, wenn die Abweichung der PV-Leistung von ihrer eigenen
Ausgleichsgeraden über 15 Minuten unter 5 % liegt. Eine ungestörte
Klarhimmelkurve ist über eine Viertelstunde nahezu linear; Wolken erzeugen
sofort mehrere Prozent Reststreuung. Die Schwelle ist an der gemessenen
Streuung geeicht: `sensor.*_pv_signal_streuung_5min` lag bei klarer Sicht bei
20–35 W auf 1300–1400 W Signal, also 1,5–2,7 %.

### Wie das Zensurproblem beim Pegel gelöst ist

Auf allen vier Backtest-Tagen wurde der Speicher voll, und danach ist der
gemessene Ertrag nur noch eine Untergrenze. Ein Verhältnis aus Tagesenergien
wäre dadurch systematisch zu klein.

Der Schätzer vergleicht deshalb zwei **Trübungsindizes** desselben Tages, wobei
beide Klarhimmelgrößen in rein geometrischen Einheiten geführt werden (POA mal
Tagesform, ohne Systemgain — so kürzt sich der Gain exakt heraus):

```
Pegel = E_gemessen · G_gesamt / (G_offen · E_prognose)
```

`G_offen` ist die geometrische Erwartung nur über die **unzensierten**
Abschnitte, `G_gesamt` über den ganzen Tag. Ein Tag, von dem weniger als 35 %
unzensiert beobachtet wurde, fällt ganz heraus — sonst misst man den Vormittag,
der bei dieser Anlage systematisch besser läuft als der verschattete
Nachmittag.

### Speicherwirkungsgrad

Über einen Tag gilt mit den kumulierten Zählern des Geräts

```
ΔSOC/100 · Kapazität = η · E_laden − E_entladen / η
```

nach η aufgelöst: `η = (d + √(d² + 4ab)) / (2a)`. Tage mit unter 1 kWh
Ladeumsatz zählen nicht, weil dann die SOC-Auflösung (1 pp = 51 Wh) dominiert.

Bemerkenswert: das Ergebnis hängt an der **gelesenen** Kapazität. Wird der
Speicher aufgerüstet, wächst die Kapazität mit, und der Wirkungsgrad bleibt
richtig. Wäre die Kapazität fest, würde ein Umbau sich als scheinbare
Wirkungsgradänderung tarnen.

## 13. Anlagenkennwerte kommen aus dem Gerät

| Größe | Quelle | Rückfall | Erwartungsbereich |
|---|---|---|---|
| Speicherkapazität | `sensor.anker_solix_..._akkukapazitat` | `sensor.solarbank_dc_straenge_441_pv_nennkapazitaet_modbus` (Reg. 10250) | 1–100 kWh |
| AC-Ausgangsgrenze | `sensor.pv_ac_ausgangslimit` (Reg. 10038) | — | 100–20000 W |
| max. Ladeleistung | `sensor.pv_maximale_ladeleistung` (Reg. 10036) | — | 200–20000 W |
| Ladeobergrenze | `number.anker_solix_..._ladeobergrenze` (Reg. 60000) | `..._pv_ladeobergrenze_modbus` | 50–100 % |
| SOC-Untergrenze | `input_number.nulleinspeisung_soc_untergrenze` | — | 0–60 % |

Die SOC-Untergrenze ist eine **Betreibereinstellung, kein Messwert** — sie darf
gesetzt bleiben.

Drei Sicherungen dagegen, dass ein Ausfall der Quelle die Prognose kippt:

1. **Quellenkette.** Fällt die offizielle Integration aus, greift der eigene
   Modbus-Sensor.
2. **Plausibilitätsbereich.** Ein Wert außerhalb gilt als ungelesen. Das fängt
   den Fall ab, der bis zum 13.08.2026 real bestand: Register 10250 wurde als
   u16 statt u32 dekodiert und lieferte dauerhaft 0,0 (behoben in Commit
   0c8ddfa). **Ältere Historie dieses Sensors ist wertlos.**
3. **Letzter guter Wert.** Ist gerade nichts lesbar, wird der zuletzt plausible
   Wert gehalten — und das im Attribut ausgewiesen (`zustand: gelesen |
   gehalten | ersatzwert`).

Der wichtigste Fall ist die **AC-Ausgangsgrenze**. Nach Einbau der
Wieland-Dose sind 2500 W statt 800 W geplant, umgestellt wird in der Anker-App.
Ohne diese Anbindung würde die Prognose danach mit einer Grenze rechnen, die es
nicht mehr gibt — und niemand würde es merken, weil die Zahl plausibel
aussieht. Die Vorwärtssimulation modelliert die Grenze korrekt: das System
liefert höchstens `AC-Grenze` ins Haus, der Rest kommt aus dem Netz, und was
die PV darüber hinaus erzeugt, lädt den Speicher.

**Physikalisch fest bleiben nur noch die Modul-Datenblattwerte** (Vmp 33,18 V,
Voc 39,90 V, Temperaturkoeffizient 0,0025 1/K). Sie stehen auf keinem Register
und ändern sich nur beim Modultausch. Dazu kommen die Naturkonstanten des
Klarhimmelmodells (Solarkonstante, Albedo) — deren Absolutwert ist unkritisch,
weil der gelernte Systemgain sie wegnormiert.

Neigung und Azimut der Modulebene (20°/188°) sind Konfigurationswerte im
Config-Flow. Ein Fehler darin ist unkritisch: die gelernte Tagesform ist das
Verhältnis von Messung zu Geometrie und schluckt jede systematische Schieflage
mit.

## 14. Die Meta-Parameter, die ich setzen musste

Das sind Parameter des **Lernverfahrens**, nicht der Anlage. Ohne sie gibt es
kein Verfahren. Sie stehen gesammelt und einzeln begründet in Abschnitt A von
`custom_components/pv_lernprognose/const.py`.

| Parameter | Wert | Begründung |
|---|---|---|
| Abtastung | 60 s | schnellster Quellsensor liefert alle 30 s; schneller bringt keine neue Information |
| Fenster Hauslast | 28 Tage | vier volle Wochen, jeder Wochentag gleich oft |
| Fenster Pegel | 21 Tage | kurz genug für die saisonale Drift, lang genug für einen Median |
| Fenster Tagesform | 45 Tage | ein Azimutfach wird pro Tag nur wenige Minuten befüllt und nur bei klarer Sicht |
| Fenster Wirkungsgrad | 21 Tage | je Tag genau ein Wert |
| Rezenzhalbwertszeit | 14 Tage | lässt die Schätzer der Jahreszeit folgen, statt über das Fenster zu mitteln |
| MAD-Schwelle | 3,5 | Standardwert nach Iglewicz/Hoaglin; verwirft rund 0,05 % gutartiger Werte |
| Klarheitsschwelle | 5 % | an der gemessenen Streuung geeicht (1,5–2,7 % bei klarer Sicht) |
| Azimut-Fachbreite | 5° | ≈ 20 min Sonnenlauf — fein genug für die gemessene Schattenkante, grob genug für die Stichprobe |
| Gain-Quantil | 0,90 | markiert das unverschattete Plateau; nicht 1,00, damit ein Ausreißerfach die Normierung nicht verschiebt |
| Zensur: Stillstandsfenster | 30 min / 1 % / 10 % | Mustererkennung des Drosselungstests |
| **Trübungs-Halbwertszeit** | **120 min** | **schwächst belegt, siehe unten** |

### Die Trübungs-Halbwertszeit ist der schwache Punkt

Sie steuert, wie schnell die Live-Messung zugunsten der Wetterprognose an
Gewicht verliert. Der Sweep über die vier Tage vom 09.–12.08. ist **monoton und
flach**:

```
τ [min]     15    30    45    60    90   120   180   240   360   ∞
RMSE Bahn  7,48  7,20  7,01  6,87  6,69  6,59  6,48  6,43  6,37  6,29
MAE  SOC   1,91  1,84  1,77  1,69  1,58  1,55  1,52  1,49  1,49  1,72
```

Länger ist auf **diesen** Daten immer besser. Trotzdem steht dort 120 und nicht
∞: in der Stichprobe ist **kein einziger bedeckter Tag**. Was ein großes τ
anrichtet — vormittags klar messen und daraus einen klaren Nachmittag
hochrechnen, während eine Front hereinzieht — kann an diesen Daten gar nicht
sichtbar werden. 120 Minuten liegt 0,3 pp über dem Sweep-Optimum und lässt die
Wetterprognose ab etwa drei Stunden Vorlauf übernehmen. **Sobald ein bedeckter
Tag in der Historie liegt, gehört der Sweep wiederholt.**

Das ist dieselbe Einschränkung, die Abschnitt 6 für `KMIN`/`KMAX` festgehalten
hat, und sie ist nicht kleiner geworden.

## 15. Was der Prüfstand zeigt

`python tools/pruefe_lernprognose.py` fährt die reinen Rechenmodule der
Integration gegen dieselben Daten wie Teil I. Home Assistant muss dafür nicht
installiert sein.

**Geometrie.** Sonnenauf- und -untergang sowie der astronomische Mittag stimmen
auf 1,6 Minuten mit den Werten aus Abschnitt 1 überein.

**Tagesform.** Der Schätzer findet die Verschattung wieder, ohne dass ihm
jemand sagt, wo sie liegt:

```
Zeit    Azimut  gelernt  Abschnitt 4b  Diff
11:00    125,3   0,99     0,97          +0,02
11:30    134,1   0,94     0,90          +0,04
12:00    143,8   0,79     0,84          -0,05
12:30    154,5   0,70     0,71          -0,01
13:00    166,1   0,63     0,64          -0,01
13:30    178,2   0,61     0,65          -0,04
14:00    190,4   0,63     0,62          +0,01
14:30    202,2   0,60     0,60           0,00
15:00    213,2   0,63     0,62          +0,01
15:30    223,2   0,77     0,77           0,00
16:00    232,3   0,87     0,87           0,00
16:30    240,5   0,78     0,93          -0,15
```

Mittlere absolute Abweichung **0,029**. Der letzte Wert (16:30) ist das
äußerste belegte Fach mit der dünnsten Stichprobe.

**Unabhängige Gegenprobe.** Mit dem gelernten Systemgain von 2,065 W/(W/m²)
sagt das Klarhimmelmodell einschließlich der gelernten Verschattung für einen
klaren Augusttag **11,96 kWh** vorher. Abschnitt 2 hatte auf völlig anderem Weg
— Eichung des Systemwirkungsgrads am unverschatteten Vormittag — **12,0 kWh**
gerechnet. Die beiden Rechnungen wissen nichts voneinander.

**Prognosefehler**, 31 Läufe (4 Tage × stündliche Startzeitpunkte):

| Konfiguration | Bias | MAE | Zeit | RMSE |
|---|---|---|---|---|
| alt: EXP 2,0 · 0,6/1,6 · 20 min · Profil vorbelegt | −28,6 | 28,64 | 95 | 17,2 |
| empfohlen aus Abschnitt 7 | −7,7 | 7,72 | 43 | 7,3 |
| **Lernprognose** | **−4,4** | **4,41** | **47** | **6,6** |

Zwei Vorbehalte, die diese Zahl kleiner machen als sie aussieht:

- **In-sample.** Tagesform und Pegel wurden aus denselben vier Tagen gelernt,
  gegen die hier geprüft wird. Das ist unvermeidlich, solange der Recorder
  nicht weiter zurückreicht, aber es ist kein unabhängiger Test.
- **Zensiert.** Der Maximal-SOC ist auf allen vier Tagen zensiert — der
  Speicher wurde jedes Mal voll. Aussagekräftig ist der RMSE der SOC-Bahn, und
  dort ist der Vorsprung mit 6,6 gegen 7,3 pp bescheiden.

Ehrlich ist: **der große Gewinn liegt nicht in diesen 0,7 Prozentpunkten,
sondern darin, dass keiner der Werte mehr von Hand gesetzt ist.** Das alte
Modell erreichte seine 7,3 pp mit vier auf genau diese vier Tage getunten
Parametern. Das neue erreicht 6,6 pp ohne einen einzigen davon — und passt
sich an, wenn sich die Anlage, der Haushalt oder die Jahreszeit ändert.

Der Restfehler steckt weiterhin dort, wo ihn Abschnitt 7 verortet hat: die
Streuung des Forecast.Solar-Bias von 1,26 bis 1,66 lässt sich mit einem
einzigen Faktor nicht auffangen. Der Unterschied ist, dass der Faktor jetzt
mitläuft statt festzustehen.

## 16. Was ausgerollt ist und was vorliegt

**Ausgerollt und laufend** (rein additiv, keine bestehende Entity berührt):

| Entity | Inhalt |
|---|---|
| `sensor.pv_lernen_hauslast` | gelernte Hauslast der laufenden Stunde, Profil in den Attributen |
| `sensor.pv_lernen_pegelfaktor` | Pegel gegen Forecast.Solar |
| `sensor.pv_lernen_tagesform` | gelernte Tagesform am aktuellen Sonnenazimut, Kurve in den Attributen |
| `sensor.pv_lernen_speicherwirkungsgrad` | η aus der Tagesenergiebilanz |
| `sensor.pv_lernen_systemgain` | wirksame Anlagenleistung je Einstrahlung |
| `sensor.pv_lernen_truebung` | Bewölkungsindex — der ehemalige Faktor `k`, ohne Schattenfehler |
| `sensor.pv_lernen_klarhimmelleistung` | Erwartung bei klarem Himmel, mit Verschattung |
| `sensor.pv_lernen_lernstand` | Sammelanzeige „n von 4 eingeschwungen" |
| `sensor.pv_lernen_anlagenkennwerte` | was aus dem Gerät gelesen, was gehalten, was Ersatzwert ist |
| `sensor.pv_lernen_speicher_prognose` | die neue Prognose, gleicher Wortlaut wie die alte |
| `sensor.pv_lernen_ziel_erreicht_um` | Zielzeitpunkt aus voller Simulation statt linearer Hochrechnung |

**Vorgelegt, nicht scharf geschaltet.** Die beiden bestehenden Sensoren

- `sensor.nulleinspeisung_speicher_prognose`
- `sensor.prioritaetsladung_ziel_erreicht_um`

sind **unverändert**. Beide sind Template-Helfer im UI-Speicher
(`.storage`, Entry-IDs `01KZM75V9053HEE4E2S46HMEB7` und
`01KZNPG0FCEH3YQE1B3Z2AH2XT`). Der Umbau bestünde darin, ihre `state`-Vorlage
durch je eine Zeile zu ersetzen:

```jinja
{{ states('sensor.pv_lernen_speicher_prognose') }}
```

```jinja
{{ states('sensor.pv_lernen_ziel_erreicht_um') }}
```

Entity-IDs, `device_class: timestamp` und alle Dashboardbindungen blieben
dabei erhalten. **Empfehlung: erst umstellen, wenn
`sensor.pv_lernen_lernstand` auf „4 von 4 eingeschwungen" steht** — das dauert
je nach Wetter zwischen fünf Tagen (Pegel, Wirkungsgrad) und vier Wochen
(Hauslastprofil je Stunde und Tagestyp). Bis dahin laufen beide Prognosen
nebeneinander und lassen sich vergleichen. Genau dafür sind die neuen Sensoren
additiv angelegt.

**Recorder.** Die `exclude`-Liste in `configuration.yaml` wurde **ergänzt**, nie
überschrieben: `sensor.pv_lernen_lernstand`, `..._anlagenkennwerte` und
`..._speicher_prognose` führen große Attribute im Minutentakt. Die numerischen
Lernsensoren bleiben bewusst drin — ihr Verlauf über Wochen ist der eigentliche
Nutzen.

**Nicht angefasst.** Nulleinspeisung (`nulleinspeisung_*`, `betriebsart_*`,
`pv_*`-Automationen, beide Dashboards, `input_boolean.nulleinspeisung_aktiv`),
kein Modbus-Schreibzugriff, Register 10071 unberührt.

## 17. Was das Verfahren nicht kann

- **Kein Temperaturmodell.** Die Modultemperatur (gemessen bis 68 °C) senkt den
  Wirkungsgrad um rund 0,35 %/K. Der Effekt ist weitgehend kollinear zur
  Einstrahlung und landet damit in der Tagesform — was systematisch richtig
  ist, aber an einem ungewöhnlich kühlen klaren Tag zu einer Unterschätzung
  führt.
- **Keine zweite Indexachse über die Sonnenhöhe.** Siehe Abschnitt 12. Die
  Jahreszeitendrift der Verschattung wird über die Rezenzgewichtung
  nachgeführt, mit zwei bis drei Wochen Nachlauf.
- **Kein bedeckter Tag in der Eichstichprobe.** Trübungs-Halbwertszeit und
  Klarheitsschwelle sind an klarem bis wechselhaftem Wetter geeicht.
- **Kaltstart der Tagesform.** Die Hauslast bekommt beim ersten Start ein
  vollwertiges Profil aus 43 Tagen Zählerhistorie (Abschnitt 19). Für
  Tagesform, Pegel und Wirkungsgrad gibt es keinen Bootstrap: sie brauchen
  Auflösung unterhalb der Stunde, die der Recorder nach zehn Tagen nicht mehr
  hat. Sie starten mit den Startwerten aus Teil I und weisen das aus.
- **Standort.** Die Integration nimmt Breite und Länge aus der
  Home-Assistant-Grundeinstellung (51,762° N, 7,877° O). Teil I rechnete mit
  51,674° N, 7,815° O. Die Differenz von rund 10 km verschiebt den
  Sonnenstand um deutlich unter einer Minute und ist für das Verfahren ohne
  Belang — die gelernte Tagesform nimmt sie ohnehin mit auf.

## 18. Dateien (Teil II)

| Datei | Inhalt |
|---|---|
| `custom_components/pv_lernprognose/const.py` | Meta-Parameter (A), Physik (B), Quellen (C) — dreigeteilt und einzeln begründet |
| `custom_components/pv_lernprognose/sonne.py` | Sonnenstand und Klarhimmel-POA, ohne jede empirische Größe |
| `custom_components/pv_lernprognose/robust.py` | Median, MAD, gewichteter Median, entrendete Streuung |
| `custom_components/pv_lernprognose/schaetzer.py` | die vier Schätzer plus Systemgain |
| `custom_components/pv_lernprognose/kennwerte.py` | Anlagenkennwerte aus dem Gerät, mit Plausibilität und Halteverhalten |
| `custom_components/pv_lernprognose/modell.py` | Vorwärtssimulation über 24 h |
| `custom_components/pv_lernprognose/coordinator.py` | Abtastung, Klarheits- und Zensurerkennung, Persistenz |
| `custom_components/pv_lernprognose/sensor.py` | die elf Entities |
| `tools/pruefe_lernprognose.py` | Prüfstand gegen die Daten aus Teil I |

## 19. Das Startprofil der Hauslast aus dem Zähler

Nachtrag vom 13.08.2026, nach einem Hinweis des Betreibers: der IR-Lesekopf am
Zähler misst die Netzleistung direkt, und **vor der PV-Inbetriebnahme ist der
Netzbezug identisch mit der Hauslast** — kein Umweg über die Solarbank, keine
Regelung dazwischen. Der Hinweis war richtig und liefert eine deutlich bessere
Basis als das, worauf der Bootstrap zuerst aufsetzte.

### Was vorher schieflief

Der erste Bootstrap zog aus
`sensor.anker_solix_solarbank_4_e5000_pro_441_startseite_last`. Diese Entity
existiert erst **seit** der PV-Installation und lieferte genau vier Tage —
darunter der 11. und 12.08. mit den Reglertests, die Abschnitt 3 als Ursache des
alten Fehlers nachgewiesen hat. Der Schätzer startete also ausgerechnet auf den
verseuchten Tagen.

### Quelle und Zeitraum

| | |
|---|---|
| Quelle | `sensor.stromleser_emh_power` (IR-Lesekopf am Zähler) |
| Statistik | Stundenmittel und Stundenminimum aus der Langzeitstatistik |
| Verfügbar | 23.06.2026 20:00 bis 11.08.2026 10:00, 1126 Stundenwerte |
| Verwendet | 24.06. bis 07.08.2026 |
| Tage | **43** mit mindestens 20 Stundenwerten — davon **31 Werktage, 12 Wochenendtage** |

Der 23.06. fällt heraus, weil davon nur vier Stunden vorliegen.

### Wie der Umschlagpunkt bestimmt wird

**Nicht über ein Datum.** Ein einkompiliertes Datum würde beim nächsten
Anlagenumbau stillschweigend falsch werden. Stattdessen über das **Vorzeichen**:
die erste Stunde, in der das Minimum unter −5 W fällt, beweist Rückspeisung ins
Netz und damit eine laufende Erzeugungsanlage. Ab dort schneidet der Bootstrap
hart ab.

```
2026-08-05   Mittel 555 W   min +171 W   max 4986 W   kein Rücklauf
2026-08-06   Mittel 514 W   min +171 W   max 3380 W   kein Rücklauf
2026-08-07   Mittel 509 W   min +146 W   max 2977 W   kein Rücklauf
2026-08-08   Mittel 217 W   min −587 W   max 4053 W   RÜCKLAUF
```

Erste Stunde mit Rücklauf: **08.08.2026 11:00, Minimum −423 W.**
In den 1043 Stunden davor ist **kein einziger** negativer Wert; das kleinste
Minimum liegt bei +141 W.

Das ist einen Tag früher als beim ersten Überschlag über die Tagesmittel
vermutet, und es passt exakt zu Abschnitt 1: dort ist der 08.08. ab 12:00 als
Tag des Drosselungstests dokumentiert. Die Anlage ging an diesem Vormittag in
Betrieb.

Die Schwelle steht auf −5 W statt auf 0 W, damit Messrauschen und Nulldurchgänge
des Lesekopfs nicht als Einspeisung gelesen werden. Der Abstand zum ersten
echten Wert (−423 W) ist groß genug, dass die Wahl unkritisch ist.

### Warum das Startprofil kein Pseudo-Tag im Fenster ist

Der erste Entwurf schob die Bootstrap-Tage als normale Tage in das gleitende
Fenster. Für Juni/Juli-Daten funktioniert das **nicht**: das Fenster reicht 28
Tage zurück und hätte sie schlicht weggeworfen, und die Rezenzgewichtung
(Halbwertszeit 14 Tage) hätte den Rest auf rund ein Zehntel gedrückt. Der
Bootstrap hätte damit gar keine Wirkung gehabt.

Deshalb ist das Startprofil eine **eigenständige Größe** neben dem gleitenden
Fenster, ohne Verfall und ohne Rezenzgewichtung. Die Regel ist scharf getrennt:

- Stunde hat **weniger** als 7 eigene beobachtete Tage → es gilt das Startprofil.
- Stunde hat **mindestens** 7 eigene Tage → es gilt der eigene gewichtete Median.

Eigene und fremde Daten werden also nie vermischt. Das Attribut
`startwert_herkunft` sagt, welcher Fall gerade zutrifft.

### Der MAD-Filter greift hier nicht

Der Auftrag verlangte ausdrücklich zu prüfen, ob der Ausreißerfilter reale
Lastspitzen wegwirft. Gemessen an den 31 Werktagen:

```
verworfene Stundenwerte   22 von 744  (3,0 %)
Wirkung auf die Tagessumme  −0,123 kWh  (−1,13 %)
schlimmste Stunde           20 Uhr: 7 von 31 verworfen, −29 W (−5,6 %)
```

Jede einzelne Abweichung ist **negativ** — der Filter hebt nie einen Wert. Das
ist der erwartete Effekt bei einer rechtsschiefen Verteilung: Trimmen der oberen
Flanke verschiebt den Median systematisch nach unten. Die Tagesmaxima bis 6910 W
sind reale Lastspitzen, und im Stundenmittel sind sie ohnehin geglättet.

**Konsequenz: für das Hauslastprofil entfällt der MAD-Vorfilter.** Der Median
allein hat 50 % Bruchpunkt — bei mindestens sieben Tagen können zwei verseuchte
Tage ihn nicht bewegen. Genau daran war das alte Profil gescheitert, und zwar
nicht weil es ein Median ohne Filter war, sondern weil es ein **Mittel aus zwei
Tagen** war.

Für die Tagesschätzer (Pegel, Wirkungsgrad) bleibt der MAD-Filter, denn dort ist
ein abweichender Tag ein Gerätefehler und kein Verbrauchsmuster.

### Das Profil vorher und nachher

`alt` ist der Juli-Median aus Abschnitt 3 (19 Tage, ohne Trennung nach
Tagestyp), `verseucht` das ursprünglich im Sensor hinterlegte Zwei-Tage-Mittel.

| h | Werktag neu | Wochenende neu | alt (Abschn. 3) | verseucht | h | Werktag neu | Wochenende neu | alt | verseucht |
|---|---|---|---|---|---|---|---|---|---|
| 00 | 324 | 450 | 355 | 370 | 12 | 433 | 617 | 485 | 385 |
| 01 | 310 | 359 | 324 | 294 | 13 | 677 | 583 | 657 | 695 |
| 02 | 287 | 320 | 318 | 262 | **14** | **532** | 563 | 501 | **1008** |
| 03 | 276 | 277 | 267 | 255 | **15** | **534** | 507 | 584 | **1062** |
| 04 | 294 | 285 | 292 | 290 | 16 | 667 | 494 | 579 | 666 |
| 05 | 327 | 338 | 351 | 326 | 17 | 557 | 579 | 568 | 700 |
| 06 | 543 | 353 | 541 | 598 | 18 | 522 | 590 | 682 | 595 |
| 07 | 529 | 326 | 480 | 528 | 19 | 595 | 689 | 629 | 973 |
| 08 | 372 | 469 | 400 | 397 | 20 | 517 | 581 | 550 | 657 |
| 09 | 387 | 551 | 497 | 460 | 21 | 560 | 549 | 587 | 434 |
| 10 | 354 | 426 | 385 | 468 | 22 | 509 | 581 | 510 | 539 |
| 11 | 386 | 444 | 394 | 462 | 23 | 371 | 500 | 392 | 445 |

**Tagessumme: Werktag 10,86 kWh, Wochenende 11,43 kWh, alt 11,33 kWh,
verseucht 12,87 kWh.**

Die beiden Stunden, um die es ging:

```
14 Uhr:  532 W   statt 1008 W   (−476 W, minus 47 %)
15 Uhr:  534 W   statt 1062 W   (−528 W, minus 50 %)
```

Beide liegen jetzt bei ziemlich genau der Hälfte des verseuchten Werts — also
dort, wo Abschnitt 3 sie aus 19 Tagen vermutet hatte, nur auf 43 Tagen und mit
Wochenendtrennung.

### Das Wochenende hatte vorher gar keine Basis

Das ist der zweite Gewinn. Der alte Startwert war ein einziges Profil für alle
Tage; das Wochenendprofil des Schätzers hatte keinerlei Datengrundlage. Die
Unterschiede sind erheblich und plausibel:

```
06 Uhr   Werktag 543 W   Wochenende 353 W    (kein Aufstehen zur Arbeit)
07 Uhr   Werktag 529 W   Wochenende 326 W
09 Uhr   Werktag 387 W   Wochenende 551 W    (spätes Frühstück)
12 Uhr   Werktag 433 W   Wochenende 617 W    (Mittagessen zu Hause)
16 Uhr   Werktag 667 W   Wochenende 494 W
19 Uhr   Werktag 595 W   Wochenende 689 W
```

### Wirkung auf den Backtest

Dieselben 31 Läufe wie in Abschnitt 15, nur mit dem neuen Startprofil statt dem
Juli-Median:

| Konfiguration | Bias | MAE | Zeit | RMSE |
|---|---|---|---|---|
| alt: EXP 2,0 · 0,6/1,6 · 20 min · Profil vorbelegt | −28,6 | 28,64 | 95 | 17,2 |
| empfohlen aus Abschnitt 7 | −7,7 | 7,72 | 43 | 7,3 |
| Lernprognose mit Juli-Median | −4,4 | 4,41 | 47 | 6,6 |
| **Lernprognose mit Zähler-Startprofil** | **−4,0** | **3,99** | **45** | **5,8** |

Der RMSE der SOC-Bahn fällt von 6,6 auf **5,8 Prozentpunkte**. Das ist eine
unabhängige Bestätigung: der Backtest kennt das Startprofil nicht, er sieht nur,
dass die Prognose besser trifft.

### Warum der Zähler keine laufende Quelle ist

Ab dem 08.08. 11:00 misst derselbe Sensor den Netzbezug **nach** PV und
Speicher. Die Tagesmittel fallen von 509 W auf 147–228 W — das ist nicht der
Verbrauch, das ist der Rest, den die Anlage nicht deckt.

`sensor.stromleser_emh_power` steht deshalb bewusst **nicht** in
`QUELLE_HAUSLAST_W`, sondern in einer eigenen Konstanten
`QUELLE_HAUSLAST_BOOTSTRAP`, und die Vorzeichenprüfung sitzt im Code, nicht in
dieser Dokumentation. Als laufende Quelle bleibt es bei
`startseite_last` beziehungsweise dem Modbus-Hauslastregister — die messen die
Hauslast auch mit laufender Anlage.

Der Bootstrap läuft genau einmal: er wird übersprungen, sobald ein Startprofil
im Lernstand steht. Eine bestehende Installation zieht ihn beim nächsten Start
nach, ohne dass jemand den Lernstand löschen muss.

### Live bestätigt

Nach dem Neustart am 13.08.2026 hat die Integration den Bootstrap selbst
ausgeführt und exakt das reproduziert, was oben von Hand gerechnet wurde:

```
quelle       sensor.stromleser_emh_power
von          2026-06-24        bis   2026-08-07
grenze       2026-08-08T11:00+02:00
n_werktag    31                n_wochenende   12
```

Die vier vorbelegten Tage aus `startseite_last` wurden beim Laden verworfen; im
gleitenden Fenster steht nur noch der laufende eigene Tag.

## 20. Die Trübung war blind, solange die Tagesform es war

Nachtrag vom 13.08.2026, im Live-Betrieb gefunden. Der Befund ist ein
Konstruktionsfehler, kein Messfehler.

### Der Befund

Klarer Himmel, Sonnenazimut rund 176°:

```
sensor.pv_lernen_truebung
  live            = 0,608
  aus_prognose    = 0,907        (Forecast.Solar mal Pegel)
  moment_klar     = true
  moment_zensiert = false

sensor.pv_lernen_tagesform = 1,0   (gelernt: false)
```

Die 0,608 sind **keine Bewölkung**, sondern der Giebelschatten — Modul 3 lag bei
52 W gegen 409 und 429 W der unverschatteten Nachbarn.

Abschnitt 11 behauptet: *„Weil die Verschattung jetzt in der Tagesform steckt,
misst die Trübung endlich das, wofür `k` gedacht war."* Dieser Schutz greift
aber **erst, wenn die Tagesform gelernt ist**. Steht sie auf 1,0, enthält die
Klarhimmelerwartung keine Verschattung — und der Schatten läuft wieder als
Bewölkung ein. Es ist derselbe Konstruktionsfehler wie beim alten `k`, nur eine
Ebene tiefer, und die Blend-Halbwertszeit trägt ihn über den ganzen Resttag fort
— auch über 15:30 hinaus, wo der Schatten laut Profil endet.

### Die Sperre

Die Live-Messung der Trübung ist gesperrt, solange die Tagesform für das
**aktuelle Azimutfach** nicht als gelernt gilt. Dann fällt die Trübung auf
`aus_prognose` zurück, die mit 0,907 deutlich näher an der Wahrheit lag.

Die Entscheidung fällt **je Azimutfach**, nicht für den Tag: sobald ein Fach
seine vier Tage und acht Proben hat, wird dort wieder live gemessen, während
benachbarte Fächer noch gesperrt bleiben. Sonst bliebe die Trübung unnötig lange
blind.

Sichtbar im Attribut:

```
quelle        = "Prognose, gesperrt: Tagesform fuer dieses Azimutfach ungelernt"
live          = null
live_zustand  = "gesperrt: Tagesform fuer dieses Azimutfach ungelernt"
aus_prognose  = 0,956
tagesform_fach_gelernt = false
```

Damit gibt es jetzt drei Sperren für die Live-Trübung, jede gegen eine andere
Fehlmessung: Abregelung (Speicher voll), ungelernte Tagesform (Schatten), und
zu kleine Erwartung (Rauschen).

### Rückwärtsschaden: keiner, und zwar aus zwei Gründen

Die Frage war, ob verschattete Messpunkte bereits als zu niedriger Pegel gelernt
wurden und die Verschattung damit **doppelt** gezählt würde, sobald die Tagesform
greift.

**Erstens: strukturell ausgeschlossen.** Die Vorhersage für den Resttag ist

```
Energie = Σ (gain · POA · Form) · Trübung
        = Σ (gain · POA · Form) · Pegel · E_FS / Σ (gain · POA · Form)
        = Pegel · E_FS
```

Die Tagesform **kürzt sich vollständig heraus**. Sie verteilt Energie innerhalb
des Tages um, aber die Tagessumme hängt allein am Pegel und an der
Forecast.Solar-Prognose. Eine Doppelzählung ist damit unmöglich, ganz gleich in
welchem Lernzustand die Form beim Messen des Pegels war.

Dasselbe gilt für den Pegel selbst:

```
Pegel = E_gemessen · G_gesamt / (G_offen · E_prognose)
```

Beide geometrischen Größen tragen die Form. Verteilt sich die Verschattung
ähnlich über das unzensierte Fenster wie über den ganzen Tag, kürzt sie sich
auch hier.

**Zweitens: nachgemessen.** An den vier Backtest-Tagen, einmal mit gelernter
Form und einmal mit Form = 1,0:

```
Tag          Form gelernt   Form = 1,0    Diff
2026-08-09       1,662         1,614      −0,048
2026-08-10       1,487         1,466      −0,020
2026-08-11       1,275         1,234      −0,041
2026-08-12       1,373         1,353      −0,020
Median           1,430         1,410      −0,020   (−1,4 %)
```

Der Restfehler von **1,4 %** ist genau der oben genannte Zweiter-Ordnung-Term.
Zum Vergleich: die Streuung des Pegels von Tag zu Tag beträgt 1,26 bis 1,66,
also rund **±14 %**. Der Effekt der ungelernten Form ist damit eine Größenordnung
kleiner als die Unsicherheit, die der Pegel ohnehin trägt.

**Drittens: im persistierten Lernstand liegt gar nichts.** Zum Zeitpunkt des
Befunds:

```
pegel.tage = {}      eta.tage = {}
```

Die Integration lief erst seit dem Mittag desselben Tages; kein einziger
Tageswert war abgeschlossen. Es gab also nichts zu bereinigen.

**Konsequenz:** keine Bereinigung, keine Sonderbehandlung, kein zusätzlicher
Mechanismus. Eine Maschinerie gegen einen 1,4-Prozent-Effekt zu bauen, während
die Größe selbst ±14 % streut, würde Genauigkeit vortäuschen, die es nicht gibt.
Der Wert des laufenden Tages wird normal abgeschlossen.

### Der Formschätzer bleibt unangetastet

Dort ist das Lernen aus verschatteten Punkten der Zweck der Übung — genau daraus
entsteht die Tagesform. Er wurde nicht geändert.

### Was die Live-Beobachtung über die Schattenform sagt

Zwei Korrekturen aus dem Betrieb, die die Annahmen von Abschnitt 12 stützen:

- Der Schatten ist ein **schmaler wandernder Streifen**, keine breite Keilspitze.
  Innerhalb von 20 Minuten wanderte der Tiefpunkt von PV2 auf PV3, während PV4
  direkt daneben bei voller Leistung blieb. Ursache ist weiterhin das
  gegenüberliegende Haus, aber eher eine schräge Traufkante als der First.
- Modulzuordnung: PV1 ganz westlich, PV2, PV3, PV4 ganz östlich. Der Streifen
  wandert über den Tag von West nach Ost. Die Richtung ist nicht angenommen,
  sondern aus der Reihenfolge der Einbrüche hergeleitet — PV1 zuerst (11:20),
  PV4 zuletzt (14:24–15:36).

Für die Indizierung nach Sonnenazimut ist das eine **gute** Nachricht: ein
schmaler Streifen ist eine scharfe Funktion des Azimuts und genau das, was
5-Grad-Fächer auflösen können. Eine breite, langsam veränderliche Keilspitze wäre
schwerer zu treffen gewesen. Es unterstreicht aber auch, warum die Fächer fein
bleiben müssen — bei 10 Grad würde der Streifen über zwei Fächer verschmiert.
