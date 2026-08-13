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
