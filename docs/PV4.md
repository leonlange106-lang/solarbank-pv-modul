# PV4 — Was der vierte Strang der Solarbank 4 E5000 Pro über Modbus ist

Stand: 11.08.2026, Abendmessung. Gerät AE103, SN …441, Firmware 1.0.2.30.
Alle Zahlen sind nachgerechnet, nicht geschätzt. Das Modbus-Gerät wurde für
diese Auswertung **nicht** angefasst — es wurden ausschließlich die vom Sampler
geschriebenen Dateien und die Home-Assistant-Historie (lesend) ausgewertet.

Datengrundlage:

| Quelle | Umfang | Rolle |
|---|---|---|
| `pv4_evening.jsonl` | 30-s-Takt ab 17:28:26 Ortszeit, 150 Register je Punkt | Hauptdatensatz |
| `longrun_teil1.jsonl` | 109 Punkte 14:03–15:52, 60-s-Takt | zweites, unabhängiges Fenster |
| HA-Recorder `…_441_solarstrom` | 5-s-Takt, ganztägig | unabhängige Gesamtleistung für den 14:40-Punkt |
| `scan_log.jsonl` | 5069 Anfragen | Einzelwerte der nicht mitgeloggten Register |
| Anker-App | vier Ablesungen (14:40, 17:20, 17:40, 18:00) | Wahrheit für PV4 |

---

## 1. Kurzantwort in drei Sätzen

**Strang 4 hat kein eigenes Modbus-Register** — kein einziges der 150 mitgeloggten
Register bewegt sich mit dem Restwert, und die Negativkontrolle bestätigt, dass
das Auswertefenster dafür taugt. **Der Restwert `PV4 = 10002 − (U₁I₁+U₂I₂+U₃I₃)`
ist unverzerrt**: am Kalibrierpunkt 14:40 Uhr trifft er die App-Ablesung von
60 W auf 1–2 W genau, und er reproduziert auch den Gegenlauf, dass PV4 von 60 auf
130 W steigt, während die Gesamtleistung von 1160 auf 550 W fällt. **Belastbar
ist aber erst das 10-Minuten-Mittel** — der Einzelwert streut mit ±41 W um einen
Messwert von 60–180 W und ist damit unbrauchbar, das 10-min-Mittel liegt bei
±17 W Reproduzierbarkeit und ±23 W mittlerem Fehler gegen die App, zusammen
**±25 W**.

---

## 2. Gültigkeit der Restwertmethode

### 2.1 Der stärkste Beleg ist nicht der Sonnenuntergang, sondern der 14:40-Punkt

Der 14:40-Punkt ist die einzige Ablesung, für die die App **alle vier** Stränge
genannt hat (418 / 413 / 273 / 60 W, gesamt 1160 W). Er ist deshalb der einzige
echte Kalibrierpunkt. Er ließ sich rekonstruieren, obwohl der damalige Langlauf
Register 10002 gar nicht mitgelesen hat: die Strangregister stammen aus
`longrun_teil1.jsonl`, die Gesamtleistung aus dem HA-Recorder. **Zwei völlig
getrennte Erfassungswege** — das schließt einen gemeinsamen Rechenfehler aus.

| Ortszeit | pv_total (HA) | U₁I₁+U₂I₂+U₃I₃ (Modbus) | Restwert |
|---|---|---|---|
| 14:35:23 | 1140 | 1101,0 | 39,0 |
| 14:36:24 | 1140 | 1090,3 | 49,7 |
| 14:37:25 | 1160 | 1088,5 | 71,5 |
| 14:38:25 | 1170 | 1104,3 | 65,7 |
| 14:39:26 | 1100 | 1026,2 | 73,8 |
| **14:40:27** | **1130** | **1072,2** | **57,8** |
| 14:41:28 | 1160 | 1108,2 | 51,8 |
| 14:42:28 | 1170 | 1117,8 | 52,2 |
| 14:43:29 | 1160 | 1088,1 | 71,9 |
| 14:44:30 | 1160 | 1077,9 | 82,1 |

Mittelwert 61,6 W, Standardabweichung 13,0 W (21 %).
**App-Ablesung: 60 W. Abweichung des Einzelwerts −2 W, des 5-min-Mittels ±0 W.**

Ein systematischer Sockel existiert an diesem Punkt also **nicht**: Wäre der
Restwert um einen konstanten Betrag verschoben, müsste er bei einer wahren
Leistung von 60 W danebenliegen. Er tut es nicht. Der Restwert ist bei 1160 W
Gesamtleistung genauso unverzerrt wie bei 550 W.

### 2.2 Der Gegenlauf — Dynamikprüfung

Die App liefert PV4 = 60 → 120 → 80 → 130 W, während die Gesamtleistung von
1160 auf rund 550 W fällt. Strang 4 steigt also **gegen** den Trend. Der
Restwert muss das reproduzieren, sonst ist er ein Artefakt der Gesamtleistung.

| Ortszeit | Gesamt | Σ Strang 1–3 | Restwert (5-min-Mittel) | Anteil | App PV4 | App-Anteil |
|---|---|---|---|---|---|---|
| 14:40 | 1146 | 1085 | **61** | 5,4 % | 60 W | 5,2 % |
| 17:20 | (680, App) | — | — | — | 120 W | 17,6 % |
| 17:30 | 680 | 503 | **177** | 26,0 % | — | — |
| 17:40 | 664 | 530 | **134** | 20,2 % | 80 W | ~12 % |
| 17:50 | 563 | 448 | **115** | 20,4 % | — | — |
| 18:00 | 540 | 444 | **96** | 17,8 % | 130 W | 23,6 % |

Der Restwert steigt absolut von 61 W auf 96–177 W, während die Gesamtleistung
sich halbiert. Sein Anteil an der Gesamtleistung steigt von 5,4 % auf 18–26 %.
Die App nennt für dieselbe Spanne 5,2 % → 23,6 %. **Der Gegenlauf ist in Betrag
und Anteil reproduziert.** Das ist der stärkste Einzelbeleg dieser Arbeit: eine
Größe, die bloß ein Rechenrest der Gesamtleistung wäre, könnte gegen die
Gesamtleistung nicht steigen.

Physikalisch passt es zur Verschattungshypothese: eine Schattenkante wandert am
späten Nachmittag über die Modulreihe hinaus, Modul 4 kommt frei, während die
Einstrahlung insgesamt sinkt.

### 2.3 Sonnenuntergangstest

Sonnenuntergang laut `sun.sun`: **20:59:20 Ortszeit**, bürgerliche Dämmerung
endet 21:38. Der Sampler läuft bis 23:59.

> **STATUS: Messung läuft.** Dieser Abschnitt wird nachgetragen, sobald die
> Datei den Sonnenuntergang enthält. Die Entscheidungsregel steht vorher fest:
>
> - `pv_total → 0` **und** `resid → 0` (|resid| < 10 W über die letzten
>   10 Messpunkte) → kein Sockel, `PV4 = resid` gilt unverändert.
> - `pv_total → 0`, aber `resid` bleibt auf einem Wert *S* stehen → systematischer
>   Versatz, `PV4 = resid − S`. Ursache dann zu benennen.
> - `resid` wird beim Herunterfahren **negativ** und bleibt es → die
>   Strangregister werden nach dem Abschalten eingefroren, während 10002 schon
>   null meldet. Das wäre kein Sockel, sondern ein Abschaltartefakt, und
>   erzwingt die Verfügbarkeitsbedingung `pv_total > 15 W` im Template-Sensor.
>
> Bereits jetzt belegt: der Restwert wird **auch tagsüber** gelegentlich negativ
> (2 von 59 Punkten im Abschnitt vor 17:57, Minimum −65 W). Da eine negative
> Modulleistung physikalisch unmöglich ist, ist das reines Messrauschen — und es
> beziffert die Rauschamplitude von unten: mindestens ±65 W im Einzelwert.

### 2.4 Woher das Rauschen kommt — zwei Anteile, beide beziffert

`REGISTER.md` führt das Rauschen des Restwerts auf den zeitlichen Versatz
zwischen dem Lesen von 10002 und dem Lesen der Strangregister zurück. Der
Sampler-Neustart um 17:57:51 hat diesen Versatz von 1,2 s auf ~0,2 s verkürzt
und erlaubt damit den direkten Test:

| Abschnitt | n | Leseversatz | mean(resid) | sd(resid) | sd nach Abzug des pv_total-Trends | Median \|Δpv_total\| |
|---|---|---|---|---|---|---|
| bis 17:57:26 | 59 | 1,2 s | 114,6 W | 59,9 W | **42,8 W** | 10 W |
| ab 17:57:51 | 41 | 0,2 s | 115,6 W | 43,1 W | **33,1 W** | 20 W |

**Der Leseversatz erklärt einen Teil des Rauschens, aber nicht alles.** Die
trendbereinigte Streuung sinkt von 42,8 auf 33,1 W, also um 23 % — und das,
obwohl die Einstrahlung im neuen Abschnitt **unruhiger** war (Median
`|Δpv_total|` 20 statt 10 W), was für sich genommen mehr Rauschen erzeugt hätte.
Der Vorteil ist also eher noch unterschätzt.

Zerlegt man quadratisch, entfallen auf den Leseversatz
√(42,8² − 33,1²) ≈ **27 W** und auf alles Übrige ≈ **33 W**. Ebenfalls
bezeichnend: im alten Abschnitt waren 2 von 59 Restwerten physikalisch
unmöglich negativ (Minimum −65 W), im neuen **0 von 41** (Minimum +20 W).

*Diese Auswertung war nach den ersten 18 Punkten des neuen Abschnitts noch
ergebnislos (sd 59,5 gegen 59,9 W) und hat erst mit n = 41 gekippt. Sie ist
damit ein Beispiel dafür, wie schnell man sich bei diesem Rauschniveau
verrechnet — und ein Grund, die Zahlen mit dem vollen Nachtdatensatz noch einmal
nachzurechnen.*

Der verbleibende Anteil von ~33 W hängt an der **Wetterdynamik**:

| Änderung der Gesamtleistung zwischen zwei Punkten | n | Median \|Δresid\| |
|---|---|---|
| ruhig, ≤ 10 W | 53 | 25,1 W |
| mittel, 10–40 W | 31 | 38,1 W |
| böig, > 40 W | 16 | 52,6 W |

r(|Δresid|, |Δpv_total|) = **+0,445**. Der Fenstervergleich zeigt dasselbe: im
ruhigen Fenster 14:35–14:45 streut der Restwert mit 13,0 W (21 % des Mittels),
im unruhigen Abendfenster mit 53,4 W (46 %) — obwohl das Abendfenster mit 30 s
**dichter** getaktet ist als das Mittagsfenster mit 60 s.

**Deutung:** Das Gerät aktualisiert 10002 und die Strangregister intern zu
verschiedenen Zeitpunkten und vermutlich mit verschiedenen Glättungszeiten.
Solange die Einstrahlung konstant ist, fällt das nicht auf. Sobald sie sich
ändert, vergleicht man eine frische Gesamtleistung mit einer alten Strangsumme.
Ein engerer Lesetakt hilft — er beseitigt den Anteil, der im *Client* entsteht.
Den Anteil, der im *Gerät* entsteht, beseitigt er nicht.

Ein Test dieser Deutung stützt sie: verschiebt man die Strangsumme künstlich
gegen die Gesamtleistung, wird die Streuung in **beide** Richtungen schlechter
(Lag ±30 s → sd 72,9 / 69,9 W gegen 53,4 W bei Lag 0). Der Restversatz ist also
kein fester Zeitversatz, den man herausrechnen könnte, sondern ein variabler
Glättungsunterschied.

**Praktische Folgerung für die Integration:** 10002 und den Block 10144:32
immer unmittelbar hintereinander lesen, ohne andere Blöcke dazwischen. Das ist
der einzige Hebel, den ein Client überhaupt hat, und er ist 27 W wert.

---

## 3. Belastbarkeit und nötiges Mittelungsfenster

### 3.1 Die vier Kalibrierpunkte

| App-Zeit | PV4 (App) | Einzelwert | 1-min-Mittel | 3-min-Mittel | 5-min-Mittel | 10-min-Mittel |
|---|---|---|---|---|---|---|
| 14:40 | 60 W | 58 | — | 61 | 60 | 62 |
| 17:20 | 120 W | (112)¹ | — | — | — | — |
| 17:40 | 80 W | 194 | 184 | 150 | 134 | 123 |
| 18:00 | 130 W | 152 | 159 | 118 | 96 | 106 |

¹ **Kein gültiger Vergleich.** Zum Zeitpunkt 17:20 existiert keine
Registermessung; der Sampler startete erst 17:28:26. Die 112 W stammen vom
8 Minuten späteren Punkt und stehen hier nur zur Einordnung. Der Wert geht in
keine Fehlerrechnung ein.

Fehler gegen die App:

| App-Zeit | Einzelwert | 1 min | 3 min | 5 min | 10 min |
|---|---|---|---|---|---|
| 14:40 | −2 W | — | +1 W | ±0 W | +2 W |
| 17:40 | +114 W | +104 W | +70 W | +54 W | +43 W |
| 18:00 | +22 W | +29 W | −12 W | −34 W | −24 W |
| **MAE** | **46 W** | **67 W** | **28 W** | **29 W** | **23 W** |
| **Bias** | +45 W | +67 W | +20 W | +7 W | +7 W |

(Die MAE-Zeile umfasst die drei gültigen Punkte. Die 1-min-Spalte hat nur zwei
Punkte und ist deshalb nicht aussagekräftig — sie enthält ausgerechnet die
beiden schlechten und keinen der guten.)

### 3.2 Reproduzierbarkeit — wie stark glättet Mittelung überhaupt?

Streuung des gleitenden Mittels des um den pv_total-Trend bereinigten Restwerts:

| Fenster | Punkte | Streuung | Erwartung bei rein zufälligem Rauschen (÷√k) |
|---|---|---|---|
| Einzelwert | 1 | 40,9 W | 40,9 W |
| 1 min | 2 | 34,5 W | 28,9 W |
| 3 min | 6 | 26,1 W | 16,7 W |
| 5 min | 10 | 21,8 W | 12,9 W |
| **10 min** | **20** | **17,0 W** | 9,1 W |
| 15 min | 30 | 15,1 W | 7,5 W |

(n = 100 Messpunkte, 17:28–18:18.)

Die Mittelung wirkt, aber **schwächer als ÷√k** — das Rauschen ist teilweise
zeitlich korreliert. Ab 10 Minuten läuft der Gewinn aus: von 10 auf 15 Minuten
sinkt die Streuung nur noch von 17,0 auf 15,1 W, während die Zeitauflösung um
die Hälfte schlechter wird. 15 Minuten wären vertretbar, 30 wären Verschwendung.

### 3.3 Die praktisch wichtigste Zahl

> **Über 10 Minuten mitteln. Nicht kürzer.**
>
> Dann gilt: **PV4 = Restwert, belastbar auf ±25 W (1 σ)** — zusammengesetzt aus
> 17 W Reproduzierbarkeit und 23 W mittlerem Fehler gegen die App, wovon ein
> Teil der App selbst anzulasten ist (10-W-Quantisierung, Cloud-Latenz, und ihre
> eigenen Einzelwerte summieren sich um 50 W nicht auf ihre eigene Gesamtangabe).
>
> Bei einem typischen PV4 von 60–130 W sind ±25 W **20–40 % relativer Fehler**.
> Das reicht für Verschattungsanalyse und Tagesbilanz. Es reicht **nicht**, um
> zu behaupten, Modul 4 liefere gerade 112 statt 130 W.

Kürzere Fenster ausdrücklich:

- **Einzelwert (30 s): unbrauchbar.** ±41 W Streuung, MAE 46 W, im alten
  Leseschema in 3 % der Fälle physikalisch unmöglich negativ. Bei einem Signal
  von 100 W ist das Rauschen so groß wie das Signal.
- **3 und 5 Minuten: grenzwertig.** MAE bereits bei 28/29 W, aber Streuung noch
  22–26 W. Wer die zeitliche Auflösung wirklich braucht, kann 5 Minuten nehmen
  und muss ±35 W hinschreiben.
- **10 Minuten: die Empfehlung.**

### 3.4 Zur 17:20-Ablesung und ihrer Summe

Die App nennt 220 + 90 + 200 + 120 = 630 W bei angegebenen 680 W gesamt, also
50 W Fehlbetrag — 7,4 %. Gleichzeitig meldete das Gerät um 17:28 eine
Gesamtleistung von 670 W. Die App rundet ihre Einzelwerte offensichtlich auf
10 W und aktualisiert die Kacheln nicht gleichzeitig.

**Konsequenz für die Fehlerrechnung:** Die App ist selbst keine exakte Referenz.
Ihre Einzelwerte haben eine Unsicherheit in der Größenordnung von ±25 W — genau
der Betrag, den auch das 10-min-Mittel des Restwerts erreicht. **Damit ist die
untere Grenze des nachweisbaren Fehlers erreicht:** Mit dieser Referenz lässt
sich nicht zeigen, dass der Restwert besser als ±25 W ist, aber auch nicht,
dass er schlechter ist. Für eine schärfere Aussage bräuchte es eine bessere
Wahrheit als die App (Abschnitt 7).

Ein zweiter Punkt, der zur 17:40-Ablesung gehört: Um 17:39:26–17:40:26 sprang
die Gesamtleistung von 690 auf 800 W — eine Aufhellung. Genau in dieser Sekunde
ist der Restwert am unzuverlässigsten (Abschnitt 2.4), und genau hier liegt der
größte Fehler der ganzen Tabelle (+114 W). Das ist kein Zufall, sondern die
Bestätigung des Rauschmodells: **die schlechten Punkte liegen dort, wo das
Modell sie vorhersagt.**

---

## 4. Registersuche: Gibt es doch ein Register für Strang 4?

### 4.1 Negativkontrolle — taugt das Fenster?

Das Abendfenster 17:28–18:21 (n = 106) ist mit einer Spanne der Gesamtleistung
von 320–810 W (83 % des Mittels) und mehrfachem Richtungswechsel **nicht
monoton**.

| Negativkontrolle | r(resid) | r(pv_total) |
|---|---|---|
| 10213 Netzfrequenz | **+0,001** | +0,085 |
| 10238 Netzfrequenz (Zweitmessung) | **+0,001** | +0,085 |

Zum Vergleich: im verworfenen Mittagsfenster lieferte dieselbe Netzfrequenz
r = −0,83. Hier ist sie **null**. Das Fenster ist damit nicht bloß tauglich,
sondern sauber: es gibt keinen gemeinsamen Trend, an dem sich beliebige Größen
scheinbar korrelieren könnten. Jeder r-Wert unterhalb von etwa 0,2 ist
Rauschen; erst darüber ist überhaupt etwas zu deuten.

### 4.2 Korrelationstabelle, sortiert nach Stärke

Alle 150 mitgeloggten Register, davon 27 variabel. `Bereich` prüft, ob der
Wertebereich zu einem Strangstrom (0–1600 Rohwert = 0–16 A) oder einer
Strangspannung (160–500 = 16–50 V) passen könnte.

| Adresse | r(resid) | r(pv_total) | Wertebereich | Zustände | Bereich passt? | Urteil |
|---|---|---|---|---|---|---|
| 10003 | +0,624 | +1,000 | 320–810 | 29 | (Strom) | **Zirkulär** — Lowword von 10002, aus dem der Restwert gebildet wird |
| 10205 | +0,504 | +0,936 | 192–337 | 59 | (Strom) | AC-Ausgangsstrom, r(AC-Leistung) = **+0,996**. Bereits ausgeschlossen |
| 10209 | +0,497 | +0,928 | 460–810 | 25 | (Strom) | Lowword der AC-Ausgangsleistung |
| 10011 | +0,407 | +0,748 | 440–2180 | 30 | nein | Hauslast, Lowword |
| 10230 | −0,364 | −0,378 | 17–36 | 13 | nein | siehe Abschnitt 5 |
| 10169 | −0,360 | −0,283 | 288–370 | 46 | (Spannung) | Spannung Strang 2 — bekannt |
| 10236 | −0,342 | −0,338 | 42–82 | 23 | nein | siehe Abschnitt 5 |
| 10170 | +0,326 | +0,657 | 77–705 | 80 | (Strom) | Strom Strang 2 — bekannt |
| 10252 | +0,301 | +0,236 | 8960–9216 | 3 | nein | siehe Abschnitt 5 |
| 10156 | +0,300 | +0,234 | 350–360 | **2** | nein | zwei Zustände — als Messgröße ausgeschlossen |
| 10009 | −0,285 | −0,225 | 0–260 | 7 | (Strom) | Batterieleistung, Lowword |
| 10254 | +0,260 | +0,146 | 0/65535 | 2 | nein | siehe Abschnitt 5 |
| 10167 | −0,175 | −0,273 | 273–366 | 45 | (Spannung) | Spannung Strang 1 — bekannt |
| 10224 / 10227 | −0,173 | −0,234 | 2377–2410 | 21 | nein | Netzspannung |
| 10202 / 10199 | −0,17 | −0,22 | 2377–2410 | 21 | nein | Netzspannung |
| 10234 | −0,152 | −0,278 | 1–3 | 3 | nein | siehe Abschnitt 5 |
| 10071 | +0,148 | +0,167 | 0/65535 | 2 | nein | Batterie-Sollwert (wird vom Hersteller beschrieben) |
| 10061 | −0,147 | −0,485 | 16281–19427 | 106 | nein | Gerätezeit (Unix-Lowword), zählt monoton |
| 10171 | −0,139 | −0,300 | 294–374 | 51 | (Spannung) | Spannung Strang 3 — bekannt |
| 10172 | −0,072 | +0,428 | 4–740 | 87 | (Strom) | Strom Strang 3 — bekannt |
| 10168 | +0,063 | +0,505 | 169–695 | 92 | (Strom) | Strom Strang 1 — bekannt |
| 10013 | +0,017 | −0,056 | 0–65526 | 16 | nein | Netzleistung, Lowword |
| 10012 | +0,015 | −0,060 | 0/65535 | 2 | nein | Netzleistung, Highword (Vorzeichen) |
| **10213** | **+0,001** | +0,085 | 4991–5009 | 19 | nein | **Negativkontrolle** |
| **10238** | **+0,001** | +0,085 | 4991–5009 | 19 | nein | **Negativkontrolle** |

123 der 150 Register sind über das gesamte Fenster **konstant**, darunter
10173–10175 (die Plätze eines vierten Strangpaares), 10183, 10187 und die
Bereiche 10042–10059, 10062–10070, 10134–10155, 10157–10166.

**Die Anzahl verschiedener Zustände ist das schärfere Ausschlusskriterium als
die Korrelation.** Die vier bestätigten Strangregister nehmen im selben Fenster
80, 87, 92 und 45–51 verschiedene Werte an. Ein Register mit 2, 3 oder 13
Zuständen kann keine Modulmessgröße sein, unabhängig von seinem r-Wert. Damit
scheiden 10156 (2), 10252 (3), 10234 (3), 10254 (2), 10230 (13) und 10236 (23)
allein aus der Auflösung heraus aus.

### 4.3 Ergebnis der Suche

**Kein Kandidat übersteht die Prüfung.**

- Das höchste r stammt von 10003, dem Lowword der Gesamtleistung. Es ist
  **zirkulär** — der Restwert wird daraus gebildet. Es zeigt nur, dass PV4 mit
  der Gesamtleistung mitläuft, was es tut.
- Der zweitstärkste Kandidat 10205 ist der AC-Ausgangsstrom mit r = +0,996 gegen
  die AC-Leistung. Er war der letzte offene Kandidat und ist erledigt.
- Alle übrigen r > 0,3 gehören zu bereits identifizierten Größen oder scheitern
  an der Auflösung: 10230 (17–36, 13 Zustände), 10234 (1–3) und 10236 (42–82)
  können weder 0–16 A (Rohwert 0–1600) noch 16–50 V (Rohwert 160–500)
  darstellen, egal wie sie skaliert werden — sie haben schlicht zu wenige
  Stufen. Die Strangströme hatten im selben Fenster 80, 87 und 92 verschiedene
  Zustände, 10230 hat dreizehn.
- **10173, 10174, 10175** — die Plätze, an denen ein viertes Paar nach dem
  Schema 10167/68, 10169/70, 10171/72 stehen müsste — sind über alle 106
  Abendmesspunkte **konstant null**, während der Restwert 96–177 W anzeigte.

**Damit ist die Frage beantwortet: Strang 4 hat kein Modbus-Register.** Das
Gerät misst ihn (die Gesamtleistung enthält ihn), aber es veröffentlicht ihn
nicht. Vier MPP-Tracker, drei Registerpaare.

*Einschränkung, die dazugehört:* Geprüft ist der Adressraum, den der Sampler
liest — 10002–10014, 10040–10071, 10112–10143, 10144–10175, 10183, 10187,
10199–10205, 10208–10239, 10250–10265. Nicht in einer Zeitreihe erfasst und
damit formal nicht widerlegt sind 10018/10022/10026/10030/10034/10036/10038
(im Scan konstant und als 32-Bit-Energiezähler bzw. Grenzwerte identifiziert),
10074–10081 (FC03, im Scan konstant) und 32768–32799 / 60000–60031 (im Scan
konstant bzw. Konfiguration). Alle diese waren im Scan über Stunden unverändert
und scheiden damit als Messgröße aus.

---

## 5. Thesen zu den unbestimmten Registern

Vorweg zwei **neue, harte Strukturbefunde**, die mehrere Register auf einen
Schlag erklären:

**(A) Es gibt ein bytegepacktes Statusfeld, das mehrfach im Adressraum liegt.**
Das Muster ist `(Wert << 8) | Flag`. Belegt:

| Adresse | Highbyte | Beleg |
|---|---|---|
| 10041 | Batterie-SOC in % | 11/11 gegen HA-Historie (bekannt) |
| **10130** | **Batterie-SOC in %** | **neu**: Scan 13:37 → 79 bei SOC 79 · 13:46 → 81 · 15:00 → 93 · 17:24 → 100 bei SOC 100. Im gesamten Abendlauf gilt 10130 == 10041 == 0x6401 |
| **10252** | **10156 ÷ 10** | **neu**: `Highbyte(10252) × 10 == 10156` in **104 von 104** Abendmesspunkten und in allen drei Scanlesungen (13:44 → 37 bei 10156 = 370; 13:53 → 38 bei 380; 15:00 → 37 bei 370) |

Das Lowbyte ist bei 10041/10130 konstant 1, bei 10252 wechselt es zwischen 0, 1
und (am Mittag) 2.

**(B) 10230 und 10236 sind ein Strom-/Leistungspaar an der Netzspannung.**

Die Beziehung `10236 = 10230 × 10224 / 1000` — also *Leistung = Strom × Spannung*
mit 10230 in 0,01 A und 10236 in 1 W bzw. var — gilt über alle 104 Messpunkte mit
einer mittleren Abweichung von **+0,44** und einer Streuung von **1,92** bei
Werten um 73, also **2,6 %**. Der Bestfit-Faktor ist 2,4173, die gemessene
Netzspannung ÷ 100 ist 2,4026 ± 0,0055.

Rechnet man 10230 als Blindstrom, ergibt sich ein Leistungsfaktor von 0,98–1,01
bei einer Wirkleistung von 650–800 W — physikalisch genau das, was der
Ausgangsfilter eines 800-W-Wechselrichters erzeugt. Dass beide Größen **fallen**,
wenn die Wirkleistung steigt, passt dazu: der kapazitive Blindstrom des Filters
ist annähernd konstant und wird bei steigendem Wirkstrom teilweise kompensiert.

*Ehrliche Einschränkung:* Der Faktor 2,4173 liegt auch 0,003 neben 1+√2. Das ist
Zahlenmystik, aber es zeigt, dass die Übereinstimmung mit der Netzspannung nicht
beweisend ist — die Netzspannung schwankte im Fenster nur um 1,4 %, das
Quantisierungsrauschen beträgt 2,6 %. **Die Proportionalität ist bewiesen, die
Identifikation des Proportionalitätsfaktors mit der Netzspannung nicht.**

### 5.1 Thesentabelle

| Register | Beobachtung im Abendlauf | These | Widerlegt, wenn |
|---|---|---|---|
| **10040** | konstant 0x0101 über 104 Punkte und 109 Langlaufpunkte | Kopfsatz des Akku-Datensatzfelds: „ein Akkupack vorhanden, Typ 1". Zusammen mit 10041 ein Paar je Einheit | Ein Erweiterungsakku wird angebaut und 10040 bleibt 0x0101, während 10042 ff. weiter null sind |
| **10041** | 0x6401, Highbyte = SOC | **bekannt/sicher**: Highbyte = SOC %, Lowbyte = Vorhandenseitsflag | — |
| **10042–10047** | konstant 0 über 213 Punkte | Plätze für Erweiterungsakkus 2 und 3, nach dem Schema 10040/10041 | Anbau eines Erweiterungsakkus, ohne dass 10042/10043 belegt werden |
| **10074** | 1 (FC03, Holding) | Boolesche Konfigurationsgröße im Holding-Block 10074–10081, den die Herstellerintegration liest, aber keiner Entity zuordnet | Wert nimmt jemals einen Wert > 1 an |
| **10075 / 10076** | je 0xFFFF (FC03) | „nicht gesetzt"-Sentinel für zwei optionale Konfigurationswerte (als INT16 = −1) | Wert wird nach Änderung einer App-Einstellung zu etwas anderem als 0xFFFF oder 0 |
| **10079** | konstant 10000 (FC03) | Grenzwert mit Skalierung ÷100, also 100,00 % — vermutlich eine Leistungsbegrenzung in Prozent | Wert ändert sich, wenn die AC-Ausgangsbegrenzung in der App von 800 W auf einen anderen Wert gesetzt wird, ohne dass 10038 sich ändert. Ändert sich stattdessen 10038 allein, ist 10079 keine Leistungsbegrenzung |
| **10118–10121** | konstant, ASCII `.1.0.203` bzw. `.1.0` + `0` + `3` | Zweite Versionszeichenkette (BMS- oder Funkmodul-Firmware), direkt hinter der Hauptfirmware in 10112–10115 | Ein Firmware-Update ändert 10112–10115, lässt 10118–10121 aber unverändert (dann ist es keine mitgeführte Version, sondern eine feste Kennung) |
| **10124** | 18772 = 0x4954 = ASCII „IT" | Ländercode / Netzregelwerk-Kennung. „IT" wäre Italien — für ein Gerät in Deutschland falsch, daher eher **kein** ASCII, sondern eine binäre Kennung, die zufällig als „IT" lesbar ist | Der Netzcode wird in der App auf ein anderes Land gestellt und 10124 ändert sich nicht (→ keine Ländercodierung). Ändert er sich, ist die These bestätigt |
| **10125** | 57356 = 0xE00C | Binäre Kennung, kein ASCII (0xE0 ist kein druckbares Zeichen). Vermutlich Hardware-Revision oder Merkmalsmaske; Lowbyte 12 könnte eine Variantennummer sein | Wert ändert sich zur Laufzeit — dann ist es keine Kennung, sondern ein Zustand |
| **10130** | 0x6401 = 0x64 << 8 \| 1 | **NEU, hoch belegt**: Duplikat von 10041, Highbyte = Batterie-SOC in %. Vier unabhängige Scanlesungen bei SOC 79 / 81 / 93 / 100 stimmen | Bei einem SOC ungleich dem von 10041 weichen die Highbytes voneinander ab |
| **10133** | 9480 = 0x2508 | Binäre Kennung im Geräteinfoblock. Highbyte 37 fällt auf, weil auch 10252 ein Highbyte von 35–38 hat — ein Zusammenhang ist aber **nicht** belegt, 10133 war über alle 104 Punkte konstant | 10133 bewegt sich jemals — dann ist es eine Messgröße und die Kennungsthese fällt |
| **10156** | 2 Zustände (350, 360) am Abend, über den Tag 380 → 370 → 380 → 370 → 360 → 350, Quantisierung exakt 1,0 | **These A: Batterie-Packspannung in 0,1 V, mit 1-V-Auflösung berichtet.** 35,0–38,0 V passen zu einem 11S-LFP-Pack. **These B: Innen- oder Akkutemperatur in 0,1 °C mit 1-°C-Auflösung.** Beide erklären den Tagesverlauf; siehe Zwischenbefund unten | **Die Nacht entscheidet.** Der Akku entlädt von 100 % auf die Entladegrenze 5 %. Fällt 10156 dabei stetig und eng an den SOC gekoppelt um mehrere Einheiten (350 → ~320), ist es die Spannung. Fällt es nur um 2–3 Einheiten und ohne SOC-Kopplung, ist es die Temperatur. **Springt es in dem Moment, in dem die Entladung einsetzt** (IR-Sprung), ist es zwingend die Spannung — eine Temperatur kann nicht springen |
| **10183 / 10187** | konstant 0 in 104 Punkten und im Scan | Reservierte Einzelregister ohne Funktion in dieser Firmware. Sie sind lesbar, weil das Gerät Start/Count-Kombinationen und nicht Einzeladressen validiert | Ein Wert ungleich null tritt auf |
| **10230** | 17–34, 11 Zustände, r(pv_total) = −0,433, ändert sich in 65 % der Takte | **AC-Blindstrom in 0,01 A** (0,17–0,34 A). Gemeinsam mit 10236 durch `10236 = 10230 × U/1000` verbunden | 10236 löst sich jemals von dieser Beziehung um mehr als 10 %; oder der Wert überschreitet den plausiblen Blindstrombereich eines 800-W-Geräts (> 1 A) |
| **10234** | 1–3 (im Langlauf 0–4), keine Kopplung an 10230/10236 (r = +0,25 / +0,18) | Zählwert oder Zustandscode, **kein** Teil des Blindleistungspaars. Kandidaten: Anzahl aktiver Regelkreise, Netzqualitätsklasse, oder ein Zähler mit kleinem Wertevorrat | Wert nimmt jemals einen Wert > 4 an, oder er zeigt eine feste Zuordnung zu einem bekannten Betriebszustand (dann ist es ein Zustandscode und die Zählerthese fällt) |
| **10236** | 42–82, 21 Zustände, r(10230) = **+0,960** | **AC-Blindleistung in var**, = 10230 × Netzspannung. Abweichung von dieser Formel: +0,44 ± 1,92 über 104 Punkte | Siehe 10230. Zusätzlich: geht 10236 nach Sonnenuntergang auf null, obwohl das Gerät am Netz bleibt, spricht das gegen einen Filterblindstrom und für eine wirkleistungsabhängige Größe |
| **10250 / 10252 / 10254 / 10256** | 10250 = 0 · 10252 = 0x2300/0x2301/0x2400 · 10254 wechselt 0 ↔ 65535 · 10256 = 100 (im Scan 15:00: 93) | **Der Sampler hat hier nur die Highwords gelesen.** 10250 ist per Herstellerdefinition das Highword von `rated_energy` (INT32) — der eigentliche Wert 51 (= 5,1 kWh) steht in 10251, das nie gelesen wurde. Ebenso fehlen 10253, 10255, 10257. **10254 = 0xFFFF ist das Highword einer negativen INT32-Größe** — sie wechselt das Vorzeichen im Takt mit dem Lowbyte von 10252. **10256 = 93 bei SOC 93 und 100 bei SOC 100: dritte Kopie des SOC** | 10256 weicht bei einem SOC ungleich 100 von 10014 ab. Für 10252/10254: ein Lauf, der 10250–10257 als Block liest, entscheidet in einer einzigen Messung, ob es 32-Bit-Objekte oder 16-Bit-Register sind |
| **32775–32799** | konstant 0, im Scan wie im Betrieb | Auffüllung des 32er-Blocks hinter der Modellzeichenkette (32768–32770 „AE103") und der Modusmaske 32774. Kein Inhalt in dieser Firmware | Ein Wert ungleich null tritt auf |
| **60004–60031** | konstant 0 (FC03, Holding) | Auffüllung des Konfigurationsblocks hinter den vier belegten Sollwerten 60000–60003. Reserviert für künftige Einstellungen | Eine bislang unbenutzte App-Einstellung wird gesetzt und ein Register in 60004+ ändert sich |

### 5.1a Zwischenbefund zu 10156: der Ladestromtest

Wäre 10156 die Packspannung, müsste sie dem Ladestrom folgen — der Spannungsabfall
am Innenwiderstand ist die einzige schnelle Einflussgröße einer LFP-Zelle, deren
Ladekurve sonst flach ist. Gegen die HA-Statistik der Batterieladeleistung
(5-min-Mittel) über das Ladefenster 14:00–15:50:

| Ortszeit | 10156 | Ladeleistung |
|---|---|---|
| 14:00 | 380 | 469 W |
| 14:10 | 370 | 412 W |
| 14:30 | 370 | **714 W** |
| 15:00 | 370 | 586 W |
| 15:25 | 370 | **790 W** |
| 15:30 | **380** | 544 W (Ladeende, SOC erreicht 100) |
| 15:40 | 374 | 0 W |
| 15:45 | 370 | 0 W |

r(10156, Ladeleistung) = **−0,312** · r(10156, SOC) = **+0,132**

**10156 bleibt 90 Minuten lang exakt auf 370 stehen, während die Ladeleistung
zwischen 390 und 790 W schwankt.** Bei 36 V entspricht das einer Stromspanne von
rund 11 A; selbst ein sehr kleiner Innenwiderstand von 20 mΩ ergäbe 0,22 V —
das liegt unter der 1,0-Quantisierung und ist damit **nicht ausschließend**, aber
es liefert auch keinerlei Stütze für die Spannungsthese.

Was dagegen für die Spannung spricht: der Ausschlag auf 380 fällt exakt auf
15:30, den Moment des Ladeendes (Ladeschlussspannung), und geht binnen zehn
Minuten wieder zurück (Relaxation). Was dagegen für die Temperatur spricht: der
Abfall 360 → 350 am Abend geschieht innerhalb von vier Minuten bei einem völlig
unbelasteten Akku bei SOC 100 — eine Ruhespannung fällt zwei Stunden nach
Ladeende nicht mehr um ein ganzes Volt.

**Beide Thesen haben Gegenargumente. Der Nachtverlauf entscheidet, nicht die
Plausibilität.**

### 5.2 Was diese Thesen zusammen bedeuten

Drei bisher unbestimmte Register sind damit **aufgeklärt** (10130, 10252 als
Kopie von 10156, 10256), zwei sind auf eine **prüfbare Formel** reduziert
(10230/10236), und für 10156 steht ein Experiment bereit, das in derselben
Nacht entscheidet, ohne dass jemand etwas anfassen müsste.

Die Register, die übrig bleiben — 10124, 10125, 10133, 10074–10079 — sind
allesamt **konstant**. Konstante Register lassen sich nicht durch Beobachtung
deuten, nur durch Verändern des Zustands, den sie beschreiben. Für sie ist
Beobachtung die falsche Methode; sie brauchen ein Experiment in der App.

---

## 6. Entwurf des PV4-Template-Sensors

**Nicht angelegt — nur Entwurf.** Zwei Sensoren: ein roher Restwert und ein
geglätteter. Die Trennung ist wichtig, weil die Glättung nur dann unverzerrt
ist, wenn der Rohwert **nicht** bei null abgeschnitten wird. Schneidet man vor
der Mittelung ab, verschwinden die negativen Rauschausschläge, die positiven
bleiben, und der Mittelwert wird systematisch zu groß — bei niedriger Leistung
um bis zu 20 W.

```yaml
# configuration.yaml — Rohwert, ungeglättet, NICHT bei null abgeschnitten
template:
  - sensor:
      - name: "PV Modul 4 Restwert roh"
        unique_id: pv_modul_4_restwert_roh
        unit_of_measurement: "W"
        device_class: power
        state_class: measurement
        icon: mdi:solar-panel
        availability: >-
          {{ states('sensor.anker_solix_solarbank_4_e5000_pro_441_solarstrom') | is_number
             and states('sensor.pv_modul_1_leistung') | is_number
             and states('sensor.pv_modul_2_leistung') | is_number
             and states('sensor.pv_modul_3_leistung') | is_number }}
        state: >-
          {% set tot = states('sensor.anker_solix_solarbank_4_e5000_pro_441_solarstrom') | float %}
          {% set s123 = states('sensor.pv_modul_1_leistung') | float
                      + states('sensor.pv_modul_2_leistung') | float
                      + states('sensor.pv_modul_3_leistung') | float %}
          {# Unterhalb von 15 W Gesamtleistung ist die Differenz reines Rauschen
             zweier fast gleicher Zahlen. Dann hart auf 0 setzen, nicht rechnen. #}
          {% if tot < 15 %}
            0
          {% else %}
            {{ (tot - s123) | round(1) }}
          {% endif %}
        attributes:
          gesamtleistung: >-
            {{ states('sensor.anker_solix_solarbank_4_e5000_pro_441_solarstrom') | float(0) }}
          summe_1_bis_3: >-
            {{ (states('sensor.pv_modul_1_leistung') | float(0)
              + states('sensor.pv_modul_2_leistung') | float(0)
              + states('sensor.pv_modul_3_leistung') | float(0)) | round(1) }}
          methode: "Restwert 10002 minus Summe der Straenge 1-3. Einzelwert unbrauchbar, nur als Quelle fuer die 10-min-Mittelung."

# Der eigentliche Nutzsensor: 10-Minuten-Mittel des Rohwerts.
sensor:
  - platform: statistics
    name: "PV Modul 4 Leistung"
    unique_id: pv_modul_4_leistung
    entity_id: sensor.pv_modul_4_restwert_roh
    state_characteristic: mean
    max_age:
      minutes: 10
    sampling_size: 120
    precision: 0
```

Wer den negativen Rauschanteil im Ergebnis nicht sehen will, klemmt ihn
**nach** der Mittelung ab — als dritter, reiner Anzeigesensor:

```yaml
template:
  - sensor:
      - name: "PV Modul 4 Leistung (Anzeige)"
        unique_id: pv_modul_4_leistung_anzeige
        unit_of_measurement: "W"
        device_class: power
        state_class: measurement
        availability: "{{ states('sensor.pv_modul_4_leistung') | is_number }}"
        state: "{{ [ states('sensor.pv_modul_4_leistung') | float, 0 ] | max | round(0) }}"
```

**Wenn nur ein einziger Sensor ohne die `statistics`-Plattform in Frage kommt**
(die ist YAML-only und nicht über die Oberfläche anlegbar), ist die
`filter`-Plattform mit gleitendem Mittel die Alternative:

```yaml
sensor:
  - platform: filter
    name: "PV Modul 4 Leistung"
    entity_id: sensor.pv_modul_4_restwert_roh
    filters:
      - filter: time_simple_moving_average
        window_size: "00:10:00"
        precision: 0
```

**Was in der Dokumentation des Sensors stehen muss**, damit ihn später niemand
falsch liest:

> Dieser Wert ist **kein Messwert**, sondern eine Differenz. Er ist auf ±25 W
> genau, solange über 10 Minuten gemittelt wird. Der Rohwert schwankt um ±41 W
> und wird bei wechselnder Bewölkung auch negativ. Für Momentanwerte ist er
> ungeeignet, für Verschattungsanalyse und Tagesbilanz geeignet. Spannung und
> Strom von Strang 4 sind über Modbus **nicht** verfügbar — der Arbeitspunkt des
> vierten Moduls bleibt unbekannt.

Für die Energiebilanz (`sensor` → `Riemann sum integral`) ist der geglättete
Sensor zu verwenden, nicht der rohe: über einen Tag mitteln sich die
Rauschausschläge zwar heraus, aber nur, wenn nicht bei null abgeschnitten wurde.

---

## 7. Was noch fehlt und welche Messung es klären würde

| Offene Frage | Warum sie offen ist | Die Messung, die sie beantwortet |
|---|---|---|
| **Spannung und Strom von Strang 4** | Es existiert kein Register. Der Restwert liefert nur das Produkt | Keine über Modbus. Nur ein DC-Zangenamperemeter am vierten Strangkabel, oder das Auslesen der Anker-Cloud-API, die der App die Einzelwerte liefert |
| **Ist der Restwert besser als ±25 W?** | Die App als Referenz hat selbst ±25 W Unsicherheit (10-W-Rundung, ihre Einzelwerte summieren sich um 7,4 % nicht auf ihre eigene Gesamtangabe) | Zehn App-Ablesungen innerhalb einer Stunde bei ruhigem Himmel, jeweils auf die Sekunde notiert. Mit n = 10 statt n = 3 sinkt der Standardfehler des Vergleichs auf ein Drittel und trennt App-Rauschen von Restwertrauschen |
| **Welches Dachmodul ist Strang 4?** | Aus den Daten nicht ableitbar | Ein Modul 60 Sekunden abdecken und beobachten, welcher der drei Ströme einbricht. Bricht keiner ein und steigt stattdessen der Restwert nicht mehr, ist das abgedeckte Modul Strang 4. Drei Handgriffe, klärt gleichzeitig die Zuordnung aller vier |
| **Ist 10156 Spannung oder Temperatur?** | Beide Deutungen passen zum bisherigen Tagesverlauf | Läuft heute Nacht automatisch mit: der Akku entlädt von 100 % auf 5 %. Entscheidungsregel in Abschnitt 5.1 |
| **Was steht in 10251, 10253, 10255, 10257?** | Der Sampler liest 10250/10252/10254/10256 einzeln mit `count=1` und erwischt bei 32-Bit-Objekten nur das Highword | Ein einziger Lesezyklus mit `(10250, 8)`. Der Scan belegt, dass der Block 10250–10265 lesbar ist. Das klärt in einer Messung, ob 10252 und 10254 16- oder 32-Bit-Objekte sind |
| **Bestätigt sich 10230/10236 als Blindstrom/Blindleistung?** | Die Proportionalität ist bewiesen, der Faktor nicht eindeutig der Netzspannung zuzuordnen (Netzspannung schwankte nur 1,4 %, Quantisierungsrauschen 2,6 %) | Eine Messung über einen Tag mit größerer Netzspannungsschwankung, oder — besser — eine Messung, in der die AC-Ausgangsleistung auf null geht, während das Gerät am Netz bleibt. Bleibt 10236 dann stehen, ist es der Filterblindstrom; geht es auf null, ist es wirkleistungsabhängig |
| **Verhalten der Register bei Erweiterungsakku** | 10042–10047 sind konstant null, weil vermutlich keiner verbaut ist | Anbau eines Erweiterungsakkus. Bis dahin nicht klärbar |
| **Sonnenuntergangstest** | Läuft zur Abfassung dieses Dokuments noch | Siehe Abschnitt 2.3 — wird nachgetragen |

### Was diese Arbeit *nicht* zeigt

- Sie zeigt nicht, dass 10002 exakt die Summe der vier DC-Stränge ist. Sie zeigt,
  dass 10002 sekundengenau mit der HA-Entity `…_441_solarstrom` übereinstimmt und
  dass die Differenz zu den drei bekannten Strängen die App-Angabe für Strang 4
  trifft. Ob 10002 vor oder hinter den MPPT-Wandlern gemessen wird, ist unbekannt.
  Sollte es dahinter sein, enthielte der Restwert zusätzlich die Wandlerverluste
  der Stränge 1–3 — bei 97 % Wirkungsgrad wären das rund 15 W bei 500 W
  Strangleistung. Das liegt **innerhalb** der ±25 W und ist mit dieser Datenlage
  nicht abtrennbar. Der 14:40-Punkt (Abweichung 1–2 W bei 1160 W Gesamtleistung)
  spricht allerdings deutlich dagegen: bei dreifacher Leistung müsste ein
  Verlustanteil dreifach sichtbar sein, und er ist es nicht.
- Sie zeigt nicht, dass in keinem Register des Geräts ein PV4-Wert steht. Sie
  zeigt, dass in keinem der 150 über 104 Messpunkte beobachteten Register einer
  steht, und dass die restlichen lesbaren Adressen über Stunden konstant waren.
