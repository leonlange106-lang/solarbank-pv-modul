# Folgeauftrag: PV-Strangüberwachung und Prognose

### Anker SOLIX Solarbank 4 E5000 Pro an Home Assistant
### Stand: 13.08.2026, 14:30 Uhr — Revision 2

Dieser Auftrag ist self-contained. Er setzt keinen Vorwissenskontext voraus.
Er löst den Masterauftrag und die erste Fassung des Folgeauftrags vom 13.08. ab.

---

## INITIALPROMPT — hiermit anfangen

Du übernimmst ein laufendes Projekt. Drei Dinge vorweg, in dieser Reihenfolge:

**Erstens: Lies diese Datei vollständig, bevor du irgendetwas tust.** Sie
beschreibt eine produktive Anlage, die ins Hausnetz einspeist. TEIL 2 sagt dir,
was bereits steht und nicht neu gebaut werden darf. TEIL 4 enthält
Rahmenbedingungen, deren Missachtung teuer wird — mindestens in Zeit, im
schlimmsten Fall in Sicherheit.

**Zweitens: Prüfe deine Werkzeuge (TEIL 0), melde das Ergebnis, und warte auf
Rückmeldung.** Nicht mit halber Ausstattung anfangen. Ein großer Teil der Arbeit
ist Verifikation gegen ein laufendes System; ohne die entsprechenden Zugriffe
entstehen plausibel aussehende Vermutungen statt belegter Aussagen.

**Drittens: Arbeite die Reihenfolge aus TEIL 5 ab**, nicht die Nummerierung aus
TEIL 3. Die Abschnittsnummern sind historisch gewachsen und sagen nichts über
Priorität.

### Haltung

Der Betreiber ist technisch versiert. Sprache **Deutsch**, Antworten knapp und
strukturiert, keine Einleitungsfloskeln.

Wenn etwas nicht eindeutig zu deuten ist: **hinschreiben statt raten.** Ein
Register, das nicht antwortet, ist ein Ergebnis. Eine Schwelle, die geschätzt
und nicht hergeleitet ist, gehört als solche markiert. Dieses Projekt hat
mehrfach davon profitiert, dass Fehlannahmen benannt statt geglättet wurden —
und mehrfach Zeit verloren, wo das nicht geschah.

Widersprüche zwischen Datenquellen sind ein Befund. Wenn Doku und Code
auseinanderlaufen, ist nicht automatisch eines von beiden richtig (siehe 3.5:
am 13.08. lag die Wahrheit einmal in der Doku und einmal im Code).

**Nichts ungefragt ausrollen, was den Regelbetrieb berührt.** Vorlegen.

---

## TEIL 0 — Vorbedingung: Werkzeuge prüfen

**Erster Schritt, vor jeder Analyse und vor jeder Zeile Code.**

Prüfe, welche Plugins, MCP-Server, Skills und Zugänge verfügbar sind. Fehlt
etwas: konkret melden — welches Plugin, welcher Zugang — und warten.

| Zweck | Benötigt |
|---|---|
| Entities, Automationen, Helper lesen und schreiben | Home-Assistant-Zugriff (MCP) |
| `configuration.yaml`, `custom_components/` | Dateizugriff auf `/config` |
| Modbus-Register lesen | Netzwerkzugriff auf 192.168.178.86:502 |
| Backtest gegen Historie | Recorder oder History-API |
| Versionierung | Git und GitHub |
| Neustart auslösen und prüfen | Supervisor- oder HA-Zugriff |

**Hinweis aus der Vorsitzung:** `pymodbus` wird lokal **nicht** gebraucht.
`tools/modbus_ro.py` ist ein eigener Client auf `socket`/`struct` mit harter
Sperre auf FC 1–4 im Code.

---

## TEIL 1 — Anlage und Umgebung

Home Assistant OS 18.2 / Core 2026.8.1 in einer Proxmox-VM auf einem BananaPi.

**Speicher:** Anker SOLIX Solarbank 4 E5000 Pro, Modell AE103, SN
AK7DN7M0G21100441, Firmware 1.0.2.30, unter **192.168.178.86:502**.
Offizielle HACS-Integration `anker_solix_official` 1.4.1, Polling 5 s.
Kapazität 5,1 kWh.

**PV:** vier Module à 500 Wp, koplanar auf einer Dachfläche, Azimut 188°,
Neigung 20°, je eigener MPP-Tracker. Module **Sakete SKT500M12-108D4**,
N-Typ Doppelglas **bifazial**. Vmp 33,18 V, Voc 39,90 V, Imp 15,07 A,
Temperaturkoeffizient Voc/Vmp −0,250 %/°C.

**Physische Reihenfolge auf dem Dach — belegt, nicht mehr offen:**
**PV1 ganz westlich, dann PV2, PV3, PV4 ganz östlich.** Der Schatten wandert
PV1 → PV4, also von West nach Ost.

> **Nie „rechts" oder „links" schreiben.** Die frühere Fassung sagte „PV1 ganz
> rechts, PV4 ganz links" nach einem Betreiberfoto, dessen Blickrichtung nicht
> festgehalten wurde — und ein Foto südwärts ausgerichteter Module entsteht
> normalerweise mit Blick nach Norden, dann liegt West links. Rechts/links ist
> ohne Standpunkt nie eindeutig, die Himmelsrichtung dagegen schon: Ein
> Hindernis südlich der Reihe wirft morgens nach Westen und nachmittags nach
> Osten, der Schatten wandert also über den Tag von West nach Ost. Weil PV1
> zuerst einbricht (11:20) und PV4 zuletzt (14:24–15:36), **ist PV1 zwingend
> das westlichste Modul.** Das ist gemessen, nicht berichtet.

**AC-Ausgang auf 800 W begrenzt.** Nach Einbau einer Wieland-Dose sind
2500 W geplant, Umstellung in der Anker-App.

**Nulleinspeisung:** HA-seitige Regelung existiert als Rückfallebene, ist
aktuell **aus**. Normalbetrieb ist Ankers `self_consumption`. Von diesem
Auftrag nicht betroffen, darf unter keinen Umständen gestört werden.

**Repo:** `C:\Users\User\solarbank-pv-modul`, Remote
`github.com/leonlange106-lang/solarbank-pv-modul` (privat), Branch `main`.
Deployment nach `\\192.168.178.43\config\`.
Diese Datei liegt ebenfalls im Repo — **von dort lesen, nicht aus einer
hochgeladenen Kopie**, sonst driften Übergabe und Wahrheit auseinander.

---

## TEIL 2 — Was steht (nicht neu bauen)

### Vier Bausteine laufen

**`solarbank_pv`** — eigene lesende Modbus-Integration, rund 80 Entities.
Registerkarte in `docs/REGISTER.md`, Deutungssicherheit in
`docs/UNBESTAETIGT.md`. Alle Registergruppen aktiv, damit unbestimmte
Register im Recorder mitlaufen.

**`pv_lernprognose`** — selbstlernende Prognose, elf Entities, rein lesend.
Modell: `P(t) = Systemgain · POA_klar(t) · Tagesform(Azimut) · Trübung(t)`.
Die Tagesform ist nach **Sonnenazimut** indiziert, nicht nach Uhrzeit —
dadurch wandert die Verschattungskurve von selbst mit dem Sonnenlauf durch
die Jahreszeiten. Anlagenkennwerte (Kapazität, AC-Grenze Reg. 10038,
Ladeleistung Reg. 10036, Ladeobergrenze) kommen aus dem Gerät, mit
Plausibilitätsprüfung und Halten des letzten guten Werts.

**Diagnoseschicht** — `custom_components/solarbank_pv/diagnose.py` meldet
Fakten, `packages/solarbank_diagnose.yaml` bewertet sie. Zehn Prüfungen,
Gesamtzustand in `sensor.solarbank_diagnose_gesamtzustand`, Alarmierung mit
Zustandstrigger **plus** 5-Minuten-Zeitmuster. Details in `docs/DIAGNOSE.md`.

**Verschattungskosten** — vier Sensoren, seit 13.08. gegen 14:00:

| Entity | Bedeutung |
|---|---|
| `sensor.pv_theoretische_leistung` | was die Anlage ohne Verschattung lieferte |
| `sensor.pv_verschattungsverlust` | momentaner Verlust in W |
| `sensor.pv_theoretische_energie_tag` | kWh, die möglich gewesen wären |
| `sensor.pv_verschattungsverlust_tag` | **kWh, die der Giebel heute gekostet hat** |

Reine Messung, kein Modell — kein Forecast, keine gelernte Tagesform, kein
Systemgain. Referenz ist das **Mittel aller Stränge innerhalb 10 % des
besten**, nicht das Maximum: Letzteres überschätzt das wahre Mittel um 2,57 %
im Median (gemessen an 355 Punkten des 12.08.). Der zweithöchste Wert wäre
glatter, wurde aber verworfen — deckt der Schatten drei Stränge, wäre er
selbst verschattet und die Referenz bräche zusammen, mit Fehlerrichtung
„kein Problem".

Klarhimmelbezug über `poa_w_m2` (reine Geometrie) mal Datenblattleistung,
nicht über die gelernten Größen — die sind bei ungelerntem Stand Platzhalter.

> **Achtung bei der ersten Auswertung:** Die beiden Tagessensoren wurden am
> 13.08. gegen 14:00 angelegt und integrieren erst ab da. Um 14:28 standen sie
> auf 0,284 kWh Verlust bei 0,776 kWh theoretisch — das ist die halbe Stunde
> seit Anlage, **nicht der Tag**. Der erste vollständige Messtag ist der
> **14.08.**

**Dashboard** — `pv-module`, fünf Views: Übersicht, Module, Verschattung,
Verläufe, Diagnose. `solarbank-diagnose` ist inhaltlich verwaist, aus der
Seitenleiste genommen, aber nicht gelöscht. **Visuell nie geprüft** — Aufbau
und Datenfluss sind verifiziert, das Aussehen nicht. Größtes Risiko sind die
vier `data_generator`-Blöcke der Apexcharts-Karte in „Verschattung": in Node
mit identischem Code getestet, aber ob Apexcharts das so rendert, ist offen.
Bleibt die Karte leer, dort zuerst schauen.

### Gesicherte Befunde

- **PV4 hat kein eigenes Register.** Adressraum vollständig geprüft. Der
  letzte Kandidat 10205 ist AC-Ausgangsstrom (r = +0,996 gegen
  AC-Leistung/Netzspannung). Strang 4 wird als Differenz aus Register 10002
  minus den drei gemessenen Strängen gebildet — exakt, verifiziert auf
  0,05 W gegen 1461 aufgezeichnete Messpunkte.
- **10156 ist die Gerätetemperatur** (/10 °C, sehr wahrscheinlich). Es ist
  das Highbyte von 10252 mal 10, belegt an 311 von 312 Messpunkten. Daraus
  folgt die 1-°C-Stufung.
- **10250 ist UINT32** über 10250/10251, /10 kWh. Als u16 gelesen liefert es
  konstant 0 — dieser Fehler lief tagelang unbemerkt.
- **Verschattungsursache: der Giebel des gegenüberliegenden Hauses.** Die
  Mitte der Modulreihe (zwischen PV2 und PV3) liegt auf der Mitte des
  Nachbarhauses. Bei hoher Sommersonne ist der Schatten kurz, die Giebelspitze
  streift die Reihe nur — daher ein schmaler wandernder Streifen statt eines
  breiten Keils. Dass ein Modul einbricht, während der direkte Nachbar voll
  liefert, ist die Folge davon, keine Anomalie.
- **Verschattungsfahrplan, out-of-sample validiert.** Profil aus dem 12.08.
  gerechnet, am 13.08. auf wenige Minuten getroffen:

  | Strang | gemessener Einbruch 13.08. | Profil sagt |
  |---|---|---|
  | PV1 (westlich) | 11:20–12:10 | 11:31–12:29 |
  | PV2 | 12:05–13:20 | 12:16–13:21 |
  | PV3 | ab 13:00 | 13:08–14:37 |
  | PV4 (östlich) | offen | 14:24–15:36 |

  Gesamtdelle 12:30–15:30, Minimum 0,60 gegen geometrische
  Klarhimmelerwartung, volle Erholung ab 16 Uhr. Deshalb liegt die Tagesspitze
  bei 11:25 statt am astronomischen Mittag 13:34.
- **PV4-Schätzfehler beziffert:** Spannung und Strom von Strang 4 sind
  geschätzt (`V4 ≈ Median(V1..V3)`). Unverschattet 0,48 % Fehler,
  bei Eigenverschattung **9,56 %, gerichtet** — der Strom wird um +10,54 %
  überschätzt. Durch keinen Median heilbar. Deshalb gibt es für PV4 **keinen
  Stromanteil**, sondern den Leistungsanteil (exakt).
- **Register 10002 liefert nur 10-W-Stufen.** PV4 erbt das als Differenz.
  Mit Zwei-Punkt-Bestätigung abgefangen.
- **Forecast.Solar unterschätzt um rund 30 %.** Anlagenleistung ist mit
  2000 W korrekt eingetragen; Neigung/Azimut stehen auf 25°/180° statt real
  20°/188°. Der Rest ist plausibel bifazialer Rückseitenertrag.

### Offener Vorbehalt zum Verschattungsprofil

**Der Azimutbezug fängt die Uhrzeitverschiebung auf, nicht die Schattenlänge.**
Im Winter legt sich der Λ mit den Schenkeln über die ganze Reihe, statt sie mit
der Spitze zu streifen — dann brechen Module *gleichzeitig* ein statt
nacheinander. Ein Augustprofil ist auf September fortschreibbar, auf Dezember
nicht. **Die Sommermessung unterschätzt den Winterverlust strukturell.** Für
die Ausbauentscheidung ist das der kritische Punkt.

Zusätzlich: PV3 und PV4 ruhen bisher auf einem einzigen Messtag.

### Rohdaten

`tools/rohdaten/` — 5,94 MB Messreihen, darunter `pv4_tag.jsonl` (Tageslauf
12.08., voller Registersatz je Messpunkt mit vorberechnetem `resid`) und
`fullsweep_progress.jsonl` (Adressraumscan). Format in
`tools/rohdaten/README.md`. **Diese Daten sind nicht reproduzierbar.**

---

## TEIL 3 — Was offen ist

> Die Nummerierung ist historisch. Für die Bearbeitungsreihenfolge gilt TEIL 5.

### 3.1 Umstellung der beiden Prognosesensoren — wartet auf Lernstand

`sensor.nulleinspeisung_speicher_prognose` und
`sensor.prioritaetsladung_ziel_erreicht_um` laufen **unverändert** mit der
alten Logik. Beide sind Template-Helfer in `.storage`.

Der Umbau ist je eine Zeile: die Berechnung durch
`{{ states('sensor.pv_lernen_...') }}` ersetzen. **Entity-IDs beibehalten**,
bei `prioritaetsladung_ziel_erreicht_um` zusätzlich `device_class: timestamp`.

**Vorbedingung:** `sensor.pv_lernen_lernstand` steht auf „4 von 4
eingeschwungen". Am 13.08. 14:28 stand er auf **0 von 4**. Vorher nicht
umstellen — die Schätzer brauchen mehrere Tage. Bis dahin laufen alt und neu
sichtbar nebeneinander; das ist gewollt und der beste verfügbare Vergleich.

Zusätzlich braucht es die **Freigabe des Betreibers** (TEIL 6).

### 3.1b Den Fehler der ungelernten Tagesform beziffern

Am 13.08. wurde dieser Fehler erstmals sauber isoliert, weil die
Trübungssperre (Abschnitt 20 in `docs/PROGNOSE.md`) die zweite Fehlerquelle
beseitigt hat. Vorher enthielt die Trübung die Verschattung fälschlich und
schob nach hinten; jetzt ist die Trübung sauber, aber die Verschattung fehlt
komplett, weil die Tagesform bei 1,0 steht — das zieht nach vorn.

**Aufgenommene Messreihe vom 13.08.:**

| Uhrzeit | SOC | Ladeleistung | neue Prognose | vorhergesagte Restzeit |
|---|---|---|---|---|
| 13:26 | 63 % | 580 W | voll um 16:40 | 3:14 h |
| 13:47 | 66 % | 460 W | voll um 15:28 | 1:41 h |
| 14:26 | 71 % | 340 W | voll um 16:10 | 1:44 h |
| 14:28 | 71 % | 420 W | voll um 16:13 | 1:45 h |

(Der Sprung zwischen 13:26 und 13:47 ist die Trübungssperre, nicht Drift.)

**Der entscheidende Befund: die Prognose konvergiert nicht, sie wandert mit.**
Zwischen 13:47 und 14:26 vergingen 39 reale Minuten, das Ziel rückte um 42
Minuten nach hinten. Die vorhergesagte Restzeit bleibt konstant bei ~1:45 h.
Das ist die Signatur eines Modells, das die Laderate systematisch überschätzt
und dem Ziel deshalb nie näher kommt.

Rechnerische Gegenprobe um 14:28: 29 fehlende SOC-Punkte in 1:45 h sind
1,48 kWh, also **846 W** mittlere Ladeleistung — gemessen wurden 420 W.

**Vergleichsbasis, korrekt gebildet (gleiche Uhrzeit, nicht gleicher SOC):**

| Uhrzeit | 12.08. | 13.08. |
|---|---|---|
| 12:46 | 57 % | 58 % |
| 13:26 | 67 % | 63 % |
| 13:47 | 69 % | 66 % |

Der 13.08. liegt drei bis vier Punkte **hinter** dem 12.08. Am 12.08. fiel die
100 % gegen **16:45**. Erwartet wurde für den 13.08. daher 17:00 oder später.

> **Aufgabe:** Aus der Historie ablesen, wann die 100 % am 13.08. tatsächlich
> gefallen sind. Die Differenz zur damaligen Prognose (15:28 bzw. 16:13) ist
> der Fehlerbetrag der ungelernten Tagesform — die einzige Größe, die den
> Nutzen des Lernens quantifiziert, vor und nach dem Einschwingen vergleichbar.

**Wichtig für die Einordnung:** Der Fehler ist nach oben beschränkt. Weil sich
die Tagesform aus der Tagessumme herauskürzt (Beweis in Abschnitt 20), kann
das Modell Energie nicht erfinden, sondern nur zeitlich falsch verteilen. Der
Fehler schrumpft deshalb im Lauf des Nachmittags von selbst.

### 3.2 Tagesertrag je Modul — bewusst zurückgestellt

Riemann-Integral plus Utility Meter je Strang, vier Einzelerträge.

**Nicht bauen, bevor 3.4 entschieden ist.** Die ursprüngliche Begründung war,
den Verschattungsverlust beziffern zu können — das leistet seit dem 13.08.
bereits `sensor.pv_verschattungsverlust_tag` direkt in kWh pro Tag. Vier
zusätzliche Einzelerträge bedeuten acht weitere Helfer und zusätzliche
Recorder-Last, ausgerechnet vor dem noch offenen Punkt 3.4.

Sie beantworten eine andere Frage als der Gesamtverlust — nämlich welcher
Strang über den Monat am meisten verliert. Für die Ausbauentscheidung reicht
voraussichtlich der Gesamtverlust.

### 3.2b Blindfleck-Pfad — und ein konkreter Verdacht

`sensor.pv_theoretische_leistung` und `sensor.pv_verschattungsverlust` haben
eine Absicherung gegen den Fall, dass **alle vier Stränge gleichzeitig im
Schatten liegen** — dann gibt es keine unverschattete Referenz mehr, und ein
naives Verfahren meldete Verlust null, obwohl der Verlust maximal ist.

Erkennung über zwei Attribute: `traeger_straenge` (wie viele Stränge liegen
innerhalb 10 % des besten) und `anteil_klarhimmel`. Bei vier trägen Strängen
und einem Klarhimmelanteil unter 0,50 liefern beide Sensoren `unknown` mit
`grund = "Bewoelkung oder Totalverschattung, nicht unterscheidbar"`.

> **Verdacht, am 13.08. um 14:28 beobachtet und noch nicht geklärt:**
> `traeger_straenge` steht sauber auf 2, aber **`anteil_klarhimmel` liefert
> `None`.** Das Attribut existiert im Attributsatz, hat aber keinen Wert.
> Wenn die Bedingung „`traeger_straenge` = 4 **und** `anteil_klarhimmel` <
> 0,50" ein `None` auswerten muss, greift die Absicherung am bedeckten Tag
> möglicherweise gar nicht — oder wirft einen Fehler.
> **Das gehört geprüft, bevor der erste trübe Tag kommt.** Klären, ob `None`
> nur bei aktuell unkritischer Lage auftritt oder generell.

**Der Pfad ist nie live eingetreten** — bei klarem Himmel steht
`traeger_straenge` auf 1 bis 2. Belegt ist er nur durch 20 Unit-Tests
(`tools/test_referenzlogik.py`) und die Rechnung.

Weiter zu prüfen am ersten bedeckten Tag:

- Greift die Erkennung wie gedacht?
- **Die Schwelle 0,50 ist gesetzt, nicht hergeleitet.** Ein klarer Tag liegt
  bei 0,9. Wo ein trüber Tag tatsächlich landet, ist ungemessen.
- Stundenlanges `unknown` ist bei Bewölkung *korrekt*, sieht aber nach Ausfall
  aus. Prüfen, ob das im Dashboard verständlich dargestellt ist.

Der Fall ist im Winter der Regelfall, nicht die Ausnahme. Die Fehlerrichtung
ohne Absicherung wäre die denkbar schlechteste — „kein Problem", obwohl der
Verlust am größten ist.

### 3.3 `sensor.pv_drosselung_leistung` — Bestandsschutz-Umbau offen

Der Sensor rechnet noch Forecast-minus-Ist und ist über
`sensor.saunaraum_..._pv_signal_streuung_5min` gegated. Er wird konsumiert
von `sensor.pv_drosselung_energie` und `automation.pv_ueberschuss_nutzen`.

`binary_sensor.pv_abregelung_erkannt` existiert bereits und arbeitet über die
Spannungsschwelle 0,92 × Voc(T). **Entity-ID `sensor.pv_drosselung_leistung`
beibehalten, nur die Logik ersetzen.**

### 3.4 Recorder- und Rechenlast — nie gemessen

Rund 80 Entities aus `solarbank_pv`, elf aus `pv_lernprognose`, vier aus der
Verschattungskostenrechnung, dazu `sensor.saunaraum_..._pv_mittel_20min`
(statistics, taktet mit 5,4 s, grob 16.000 Recorder-Einträge/Tag). Messen, ob
die CPU des BananaPi das trägt. Falls nötig: Drosselungsvorschlag, ohne die
Reaktion auf Wetteränderungen zu verlieren. Die `exclude`-Liste in
`configuration.yaml` **nur ergänzen**.

### 3.5 `REGISTER.md` gegen `const.py` abgleichen

Die beiden liefen am 13.08. an zwei Stellen auseinander — **in beide
Richtungen**: Bei 10250 stand die richtige u32-Deutung längst in der Doku,
während der Code u16 las. Bei 10156 war es umgekehrt. Ein vollständiger
Abgleich beider Richtungen steht aus.

Das ist die eigentliche Lieferung des Projekts: Der Code ist reproduzierbar,
die Registertabelle nicht.

### 3.6 Trübungs-Halbwertszeit — Sweep wiederholen

Meta-Parameter `TAU_TRUEBUNG = 120 min` in
`custom_components/pv_lernprognose/const.py`. Der Sweep ist auf den
vorhandenen Daten **monoton** — länger ist immer besser, bis hin zu „nur
Live-Messung". Grund: In der Stichprobe ist kein bedeckter Tag, der Schaden
eines großen τ kann dort nicht sichtbar werden.

**Sobald ein bedeckter Tag in der Historie liegt: Sweep wiederholen.**

### 3.7 Verschattungsprofil — läuft, Auswertung ab Mitte September

Die Verschattungsereignisse werden mit `sun.sun` aufgezeichnet. Nach vier
Wochen sollte eine Aussage möglich sein, bei welchem Sonnenstand welches
Modul wie stark einbricht.

Ein Teil davon lässt sich **schon jetzt** aus `tools/rohdaten/pv4_tag.jsonl`
rekonstruieren, statt vier Wochen zu warten.

**Belegter Bias, seit 13.08. nicht mehr nur Beobachtung: das Profil sagt
durchweg ZU WENIG Verschattung voraus.** Vier unabhängige Vergleichspunkte,
alle in dieselbe Richtung:

| # | Zeitpunkt | Profil sagt | gemessen |
|---|---|---|---|
| 1 | Azimut 165,4° | PV2 17 % | 9 % |
| 2 | Azimut 165,4° | PV3 66 % | rund 60 % |
| 3 | 13.08., kurz vor 15:00 | PV3 frei ab 14:37 | **64 %**, Doppelsignatur Verschattung |
| 4 | 13.08., 15:50 | PV4 frei ab 15:36 | **65 %** (PV1 355 W, PV2 366 W, PV3 372 W, **PV4 237 W**) |

**Punkt 4 ist beziffert, nicht nur beobachtet.** PV4 kam noch in derselben
Sitzung frei; der Verlauf von `sensor.pv_modul_4_leistungsanteil` gibt die
Verspätung auf die Minute:

| Kriterium | Zeitpunkt | Verspätung gegen 15:36 |
|---|---|---|
| 15:40–15:49 | 57–72 %, unter der Hysteresegrenze | — |
| erstes Überschreiten von `SHADE_OFF` = 0,70 | 15:49:36 | **+13,6 min** |
| dauerhaft darüber | 15:51:06 | **+15 min** |
| voll frei (> 90 %) | 15:54:55 | **+19 min** |

Das Profil endet also rund **eine Viertelstunde zu früh**. Die Ablesung des
Betreibers um 15:50 (65 %) deckt sich mit dem aufgezeichneten Wert 64,7 % um
15:50:36 — die Reihe ist konsistent.

Die ersten beiden unterschätzen die **Tiefe**, die letzten beiden das **Ende**
des Schattens. Vier konsistente Punkte an zwei verschiedenen Tagen und an drei
verschiedenen Strängen sind kein Zufall mehr.

**Konsequenz für die Ausbauentscheidung:** Das Profil unterschätzt den Verlust.
Jede Wirtschaftlichkeitsrechnung, die auf ihm aufsetzt, rechnet den Schaden der
Verschattung zu klein — und damit den Nutzen einer Gegenmaßnahme ebenfalls.
Bis der Bias beziffert ist, gilt das Profil als **untere Schranke**, nicht als
Erwartungswert.

**Was zur Bezifferung fehlt:** Die vier Punkte belegen die Richtung, nicht die
Größe. Dafür braucht es die systematische Auswertung über mehrere Tage — die
läuft ohnehin. Ab dem 14.08. liefert `sensor.pv_verschattungsverlust_tag`
erstmals einen vollständigen Tag; das ist die Zahl für die Entscheidung, und
sie ist ab dann täglich da.

### 3.8 Zwei Hauslast-Lernsysteme laufen parallel — aufräumen

Redundanz, die beim Bau der Lernprognose entstanden ist und die niemand
entschieden hat:

- **alt:** `input_text.hauslastprofil_werktag` / `_wochenende`, gefüttert von
  `automation.hauslastprofil_stundenwert_lernen` per EWMA. Wird von der alten
  Prognose gelesen.
- **neu:** `pv_lernprognose` liest `..._startseite_last` direkt und lernt ein
  **eigenes** Stundenprofil, getrennt Werktag/Wochenende, mit Bootstrap aus
  der Langzeitstatistik. Es nutzt die `input_text` **nicht**.

Beide lernen dasselbe aus derselben Quelle. Nach der Umstellung (3.1) wird
das alte System arbeitslos. Entscheiden, ob die Automation und die beiden
`input_text` dann entfallen — dabei prüfen, wer sie sonst noch liest.

**Am 13.08. behoben:** `input_text.hauslastprofil_wochenende` stand auf
`unknown` statt auf 24 Werten. Am Samstag wäre die Lernautomation beim
Zerlegen gescheitert. Belegt mit dem Werktagsprofil, aber mit den
Juli-Medianen an den durch Reglertests verfälschten Stunden (14 Uhr
1008 → 501, 15 Uhr 1062 → 584).

Die übrigen Nachmittagswerte des Werktagsprofils stammen weiterhin aus
Reglertests vom 11./12.08. Das EWMA arbeitet sichtbar (9–11 Uhr sind von
460/468/462 auf 461/443/440 gewandert), braucht für die Nachmittagsstunden
aber noch ein bis zwei Wochen.

### 3.9 Zwei Sensoren werden zu Waisen

Nach 3.1 und 3.3 hängt an keinem Konsumenten mehr:

- `sensor.saunaraum_..._pv_mittel_20min` — nur an der alten Prognose
- `sensor.saunaraum_..._pv_signal_streuung_5min` — nur am alten
  Drosselungssensor

Beide sind Statistics-Helfer, die mit dem Anker-Poll takten (5,4 s) und
zusammen grob 32.000 Recorder-Einträge pro Tag erzeugen. Ihre Entfernung
erledigt ein gutes Stück von 3.4 gleich mit. **Vor dem Entfernen prüfen, ob
sie sonst noch jemand liest.**

### 3.10 Kleinere Punkte

- **Forecast.Solar korrigieren:** Neigung 25° → 20°, Azimut 180° → 188°.
  Erklärt ein bis zwei Prozent. **Erst nach 3.1**, denn der Pegelschätzer hat
  sich auf die falschen Werte eingestellt (Pegel steht bei 1,42) und müsste
  sonst mitten im Einschwingen neu justieren.
- **Anzeigenamen** tragen das Geräte-Präfix („Solarbank DC-Straenge (441) PV
  Modul 4 …"). Bestandsverhalten, ändern hieße umbenennen.
- **Erste Minute nach Neustart:** Die Prognose meldet kurz „Prognose nicht
  moeglich", weil ihr Coordinator vor `anker_solix_official` startet. Ehrlich,
  aber unschön.
- **Koexistenzprüfung ungetestet:** Ob Prüfung 10 bei einem längeren Ausfall
  von `anker_solix_official` wirklich anschlägt, ist nicht belegt. Ein
  20-Sekunden-Ausfall am 13.08. blieb unter der Schwelle.

---

## TEIL 4 — Rahmenbedingungen

### Sicherheit

- **Modbus ausschließlich lesend.** Niemals FC05, 06, 15, 16. Gilt auch für
  60000–60031 — die offizielle Integration bedient diese Register bereits
  schreibend.
- **Register 10071 nicht anfassen.** Sollwert der Nulleinspeisungsregelung.
- **Nulleinspeisung nicht anfassen:** Automationen mit Präfix
  `nulleinspeisung_*`, `betriebsart_*`, `pv_*`; Dashboards
  `nulleinspeisung-control` und `nulleinspeisung-preview`. Neues bekommt
  eigene Präfixe.
- Vor Arbeiten am Gerät bestätigen, dass `input_boolean.nulleinspeisung_aktiv`
  **aus** ist und das Gerät in `self_consumption` läuft.
- **Nach jeder Änderung prüfen**, ob `anker_solix_official` weiterhin frische
  Werte liefert. Bricht sie weg: sofort trennen und melden.

### Fallen, die schon zugeschnappt sind

- **Das Repo ist NICHT das Deployment.** Home Assistant liest ausschließlich
  aus `\\192.168.178.43\config\`; `C:\Users\User\solarbank-pv-modul` ist eine
  Arbeitskopie. Wer nur ins Repo schreibt und neu startet, wartet fünf Minuten
  auf nichts — **es gibt keine Fehlermeldung**, die Entities fehlen einfach.
  Das ist am 13.08. einem Agenten passiert. Nach jedem Kopieren per SHA256
  gegenprüfen, dass Repo und Deployment übereinstimmen.
- **Das Dashboard kann sich zwischendurch ändern.** Der Betreiber bearbeitet
  es im Browser. Am 13.08. hatte er `PV gesamt (Modbus)` als fünfte Kurve
  ergänzt; der `config_hash`-Konflikt hat es aufgedeckt, die Änderung wurde
  übernommen statt überschrieben. **Bei einem 409-Konflikt niemals `force`** —
  neu lesen, eigene Änderung daraufsetzen, erneut schreiben.
- **Änderungen an `custom_components/` brauchen einen HA-Neustart** — sonst
  importiert HA die geänderten Module nicht. Ein Neustart dauert gemessen
  rund 5 Minuten.
- **Registerschlüssel in `const.py` nie umbenennen** — sie bilden die
  `unique_id`. Eine Umbenennung erzeugt eine neue Entity und schneidet den
  Verlauf ab. Der Anzeigename ist frei.
- **Zustandstrigger ohne Zustandswechsel feuern nie.** Am 13.08. hätte die
  Störungsmeldung ausgerechnet dann geschwiegen, wenn HA bereits gestört
  hochkommt. Deshalb tragen die Diagnose-Alarme zusätzlich ein
  5-Minuten-Zeitmuster. Dasselbe Muster gilt für `for:`-Bedingungen auf
  flatternden Sensoren — ein Zustand, der nie 5 Minuten stabil bleibt,
  erfüllt `for: 5 min` nie.
- **Push-Zustellung kann fehlschlagen und Automationen abbrechen.** Am 12.08.
  hat ein abgelaufener iOS-Token eine komplette Automation gerissen. Jeder
  `notify`-Schritt braucht `continue_on_error: true`, besonders wenn danach
  noch Zustandsänderungen folgen.

### Sonstiges

- Recorder-`exclude` nur ergänzen, nie überschreiben.
- Entity-IDs nicht ändern.
- Nichts ungefragt ausrollen, was den Regelbetrieb berührt.
- Wenn etwas nicht eindeutig zu deuten ist: hinschreiben statt raten.

### Arbeitsweise

Unabhängige Stränge parallelisieren (Dateianalyse, Backtests, Dokumentation).
**Nicht parallel:** gleichzeitiger Modbus-Zugriff, gleichzeitiges Schreiben
auf dieselbe Datei, und **gleichzeitige HA-Neustarts** — zwei Agenten, die
sich gegenseitig neu starten, jagen Phantomfehler. Ein Agent hält den
Gerätezugriff, alle anderen bekommen dessen Ergebnisse.

Widersprüche zwischen Strängen sind ein Befund und gehören benannt, nicht
geglättet.

**Vergleiche immer bei gleicher Uhrzeit, nicht bei gleichem Zustand.** Am
13.08. führte ein Vergleich „heute 13:20 → 62 %, gestern 12:46 → 57 %" zu dem
falschen Schluss, der Tag laufe besser. Bei gleicher Uhrzeit lag er drei bis
vier Punkte zurück.

---

## TEIL 5 — Reihenfolge

Diese Reihenfolge gilt, nicht die Nummerierung aus TEIL 3.

**Sofort möglich, kein Gerät, kein Neustart, keine Wartezeit:**

1. **Werkzeugprüfung** (TEIL 0), Ergebnis melden, auf Rückmeldung warten
2. **`REGISTER.md` gegen `const.py` abgleichen** (3.5) — reine Dateianalyse
3. **Messpunkt 3.1b nachtragen** — aus der Historie ablesen, wann die 100 %
   am 13.08. gefallen sind, und den Fehlerbetrag festhalten
4. **Recorder- und Rechenlast messen** (3.4) — **bevor** weitere Entities
   dazukommen
5. **Waisen-Sensoren prüfen** (3.9) — erst entfernen, wenn 3.1 und 3.3 durch
   sind, aber Konsumenten schon jetzt feststellen

**Danach, mit Gerät und Neustarts:**

6. **`anteil_klarhimmel = None` klären** (3.2b) — die Blindfleck-Absicherung
   hängt daran, und sie ist nie live geprüft worden
7. **`pv_drosselung_leistung` umbauen** (3.3)

**Wartet auf externe Bedingungen — nicht vorziehen:**

8. **Prognosesensoren umstellen** (3.1) — erst bei Lernstand 4 von 4 **und**
   Freigabe des Betreibers
9. **Forecast.Solar-Geometrie korrigieren** (3.10) — erst nach 8
10. **Hauslast-Lernsysteme zusammenführen** (3.8) — erst nach 8
11. **Trübungs-Sweep wiederholen** (3.6) — sobald ein bedeckter Tag vorliegt
12. **Tagesertrag je Modul** (3.2) — nur falls 3.4 zeigt, dass Luft ist
13. **Verschattungsprofil auswerten** (3.7) — ab Mitte September

---

## TEIL 6 — Was der Betreiber entscheiden muss

Diese Punkte kann kein Agent klären:

- **`solarbank-diagnose` löschen?** Nach der Dashboard-Konsolidierung ist es
  nur noch aus der Sidebar genommen, nicht entfernt. Löschen ist irreversibel.
- **Freigabe für die Prognoseumstellung** (3.1), sobald der Lernstand auf
  4 von 4 steht.
- **Wieland-Dose und 2500 W** — Hardware plus Umstellung in der Anker-App.
  Die Prognose zieht danach automatisch nach, weil sie Register 10038 liest
  statt einer festen Zahl.
- **Ausbauentscheidung Mitte September** — dafür liefern das
  Verschattungsprofil (3.7) und `sensor.pv_verschattungsverlust_tag` die
  Grundlage. **Achtung:** Beide unterschätzen den Winterverlust strukturell,
  siehe Vorbehalt in TEIL 2.

> Die physische Modulzuordnung ist **erledigt** — PV1 ganz westlich bis PV4
> ganz östlich, aus dem Verschattungsfahrplan hergeleitet (siehe TEIL 1). Nicht
> erneut erfragen und kein Abdeck-Experiment vorschlagen.

---

## TEIL 7 — Nachtrag der Sitzung vom 13.08., 15:10

Alles hier ist neu gegenüber Revision 2 und im Repo belegt.

### 7.1 Register 10254: Identitätshypothese widerlegt

Der alte Kommentar in `const.py` behauptete, 10254/10255 sei **dieselbe Größe**
wie 10008/10009 mit umgekehrtem Vorzeichen. Das ist falsch.

`tools/korrelation_10254.py` (neu) rechnet beide Registerpaare gegeneinander.
Sie stehen in `tools/rohdaten/pv4_tag.jsonl` je Messpunkt im **selben
Abfragezyklus** — Nichtgleichzeitigkeit scheidet als Erklärung also aus.
1461 Messpunkte des 12.08.:

| Regime | n | r | Steigung | Achsenabschnitt |
|---|---|---|---|---|
| Laden | 882 | **−0,982** | **−0,9572** | **−54,3 W** |
| Entladen | 364 | −0,148 | −2,3849 | +694,5 W |

Verhältnis `10254 / |10008|` beim Laden: Median 0,884, p10 0,796, p90 0,921.
Exakt deckungsgleich: **1 von 882**.

**Der Achsenabschnitt ist der eigentliche Befund, nicht der Median.** Die
Regression beschreibt einen **festen Sockel von 54 W plus 4,3 % proportionalen
Verlust** — die Signatur eines Wandlungspfads mit Eigenverbrauch:

| 10008 | 10254 | Verhältnis |
|---|---|---|
| 200 W | 137 W | 0,69 |
| 380 W | 309 W | 0,81 |
| 1000 W | 903 W | 0,90 |
| 2000 W | 1860 W | 0,93 |

Die Spannweite p10–p90 ist damit keine Streuung, sondern die Lastabhängigkeit
selbst. Richtung plausibel: **10008 misst vor, 10254 nach dem Verlust** — welche
Seite genau, bleibt offen. Im Entladeregime bricht der Zusammenhang zusammen.

`const.py` steht deshalb jetzt auf `certain=False`. Nur das Feld `certain`
geändert, `unique_id` unberührt, kein Verlaufsbruch. **Noch nicht deployt.**

### 7.2 Neuer offener Punkt: Wirkungsgrad lastabhängig statt konstant

Beide Prognosen rechnen mit **0,95 konstant** —
`input_number.nulleinspeisung_speicher_wirkungsgrad` und
`sensor.pv_lernen_speicherwirkungsgrad` stehen beide auf 0,95.

Die Messung sagt: bei 380 W sind es **0,81**, bei 200 W nur **0,69**.

Unabhängige Gegenprobe vom 13.08.: SOC 63 % (13:26) auf 74 % (14:58), also
11 Punkte = 0,561 kWh in 92 Minuten = **366 W in die Zellen**, bei rund 450 W
gemeldeter Ladeleistung. Verhältnis **0,81** — genau der Regressionswert.

Ein Modell mit 0,95 füllt den Speicher rechnerisch rund 17 % zu schnell; bei
26 fehlenden SOC-Punkten sind das etwa **20 Minuten**. Nicht die ganze Stunde
Abweichung, aber ein messbarer Anteil — und **unabhängig von der ungelernten
Tagesform**. Die Regressionskoeffizienten aus 7.1 sind der Startwert.

Betrifft `pv_lernprognose` **und** den alten Sensor.

### 7.3 Neuer offener Punkt: ±65-kW-Ausschlag am Nulldurchgang

An **8 von 1461 Punkten** passen High- und Lowword von 10254/10255 nicht
zusammen (roh `0/65526` bzw. `65535/0`), jeweils am Nulldurchgang. Als INT32
ergibt das Ausschläge von **±65 kW**, die ungefiltert im Recorder landen.
Ursache ist ein nicht-atomares Update beider Wörter — bekanntes Modbus-Verhalten.

0,5 % klingt harmlos, ist es nicht: ein einzelner 65-kW-Wert dominiert jedes
`average_linear`-Fenster und jedes Riemann-Integral, in das er fällt.

**Noch nicht gebaut**, weil es ein Eingriff in den Lesepfad ist. Vorgabe, wenn
gebaut wird: Werte außerhalb von ±`max_charge_power` (3000 W, Register 10036)
verwerfen, letzten guten Wert halten, und **die Zahl der Verwürfe als Attribut
mitführen** — ein still filternder Filter versteckt irgendwann einen echten
Defekt.

### 7.4 Messreihe 3.1b, fortgeschrieben

| Uhrzeit | SOC | Laden | Prognose 100 % | Restzeit | nötig | Faktor |
|---|---|---|---|---|---|---|
| 13:26 | 63 % | 580 W | 16:40 | 3:14 h | — | — |
| 13:47 | 66 % | 460 W | 15:28 | 1:41 h | 991 W | 2,2 |
| 14:28 | 71 % | 420 W | 16:13 | 1:45 h | 846 W | 2,0 |
| 14:38 | 72 % | 670 W | 16:07 | 1:30 h | 952 W | 1,4 |
| 14:49 | 74 % | 380 W | 16:04 | 1:15 h | 1062 W | 2,8 |
| 14:52 | 74 % | 290 W | 16:06 | 1:15 h | 1061 W | 3,7 |
| **15:07** | **75 %** | **410 W** | **18:07** | **3:00 h** | **425 W** | **1,0** |

| 15:11 | 76 % | — | 17:41 | — | — | — |

Der Faktor ist reines Spiegelbild der Momentanladeleistung, kein Konvergenzmaß.

> **Korrektur:** Der Sprung von 16:06 auf 18:07 zwischen 14:52 und 15:07 sah
> nach Instabilität des Modells aus. **Er ist es nicht.** Um 15:06 hat
> `energy_production_today_remaining` seinen stündlichen Wert von Forecast.Solar
> bekommen, `energy_production_today` sprang mit (9,619 → 9,55 kWh). Die
> Prognose gibt eine Sprungfunktion sauber weiter, statt selbst zu springen.
> Um 15:11 stand sie bei 17:41, also wieder auf dem erwarteten Fenster
> 17:00–17:15 zu. **Prüfbar:** die Sprünge müssen immer kurz nach :05 liegen.
> Ursache im Modell siehe 7.9.

Die alte Prognose sagte um 15:07 „heute nur ca. 79 %, Höchststand gegen 16:52",
sieht die 100 % also weiterhin gar nicht.

**Der Messpunkt fehlt weiter:** wann die 100 % tatsächlich gefallen sind.
`sensor.pv_lernen_speicher_prognose` steht im Recorder-`exclude`
(`configuration.yaml` Zeile 63), die Prognosebahn ist also **nicht**
rekonstruierbar — der SOC-Verlauf dagegen schon. Wer die Sitzung fortsetzt:
den tatsächlichen 100-%-Zeitpunkt aus der SOC-Historie nachtragen.

### 7.5 Was das 85-%-Ziel nicht leistet

`sensor.prioritaetsladung_ziel_erreicht_um` (alt) und
`sensor.pv_lernen_ziel_erreicht_um` (neu) zielen beide auf 85 %
(`input_number.nulleinspeisung_prioritaetsladung_max_soc` = 85, der neue Sensor
führt `ziel_soc: 85` als Attribut) und liegen **beide im Recorder** — 1748 bzw.
171 Einträge in drei Stunden.

Das verführt dazu, 3.1b darüber auszuwerten. **Das trägt nicht.** Auf einem
Horizont von 90 Minuten bei stabiler Ladeleistung ist die lineare Extrapolation
der alten Prognose ein gutes Verfahren — ihr Konstruktionsfehler wird dort gar
nicht sichtbar. Das 85-%-Ziel prüft also nicht nur einen anderen Tagesabschnitt
(mitten in der Verschattungsdelle statt nach der Erholung), sondern einen
Horizont, auf dem sich beide Verfahren systematisch angleichen.

### 7.6 Ergebnis von 3.5 — Abgleich `REGISTER.md` gegen `const.py`

Vollständig durchgeführt, beide Richtungen, alle 40 Register und 25 Leseblöcke.
`certain`-Flag und Sicherheitsspalte sind **ausnahmslos konsistent**, alle
Skalierungen stimmen überein, 10250 als u32 ÷10 ist durch (live 5,1 kWh).

**Doku hinter Code, noch nicht eingearbeitet:**

1. **10156** — §3.7 führt es als „unbestimmt, nur zwei Zustände 370/380". Es ist
   die Gerätetemperatur. Live geprüft: 10156 = 360, Highbyte(10252) = 0x24 = 36,
   ×10 = 360. Und 360 ist ein **dritter** Wert — die „zwei Zustände" waren ein
   110-Minuten-Fenster.
2. **§4 „Nicht vorhanden"** listet Gerätetemperaturen als nicht verfügbar —
   durch 1 widerlegt.
3. **10254/10255 fehlt in der Registertabelle komplett.** Einzutragen als
   **plausibel**, nicht sicher, mit den Zahlen aus 7.1.
4. **10252** — Highbyte-Zusammenhang zu 10156 fehlt.
5. **10168 / 10170 / 10172 / 10205** stehen als UINT16 in der Doku, der Code
   liest **i16**. Der Code hat recht: ohne Vorzeichen wird −0,08 A zu 655,28 A.
6. **§2 „Nachweislich lesbare Adressen"** listet 10001, 10004 und 10005 nicht,
   obwohl §3.1 sie führt. Live: `10000+6 = [0, 1, 0, 1100, 0, 0]`, alle sechs
   antworten.
7. **§5** enthält noch „Offen bleibt: 10205 …" direkt über „Erledigt: auch
   10205 ist ausgeschlossen".

**Code hinter Doku, vom Betreiber freigegeben, einzubauen nach 3.4:**

8. **10001 `battery_status`** — in der Doku sicher, im Code kein `Reg`. Live = 1
   (Laden). Liegt im ohnehin gültigen Block 10000:6.
9. **10064 `operating_mode`** — in der Doku sicher, im Code kein `Reg`. TEIL 4
   verlangt vor Gerätearbeiten die Bestätigung von `self_consumption`; die hängt
   derzeit allein an der offiziellen Integration. Ein unabhängiger Lesepfad
   macht genau die Sicherheitsprüfung robust, die im Zweifel greifen soll.

Beide kosten keine zusätzliche Modbus-Anfrage.

**§7 der `REGISTER.md`** braucht denselben rechts/links-Durchgang wie TEIL 1,
und der Abschnitt „Folge für die Verschattungshypothese" ist überholt: er
verortet ein Hindernis „südsüdwestlich des Ostendes", während der Giebel des
gegenüberliegenden Hauses mittig zwischen PV2 und PV3 steht. Die Messdaten des
Abschnitts bleiben gültig, die Erklärung darüber nicht.

### 7.7 Nebenbefund zum Verschattungsprofil

Kurz vor 15:00 gemessen: PV1 28,8 V × 13,76 A = 396 W, PV2 28,9 V × 13,97 A =
404 W, **PV3 31,5 V × 8,21 A = 259 W** — also 64 % mit der Doppelsignatur
Verschattung. Der Fahrplan lässt PV3 um **14:37** frei werden. Das ist ein
dritter Punkt in dieselbe Richtung wie die beiden in 3.7 vermerkten: **das
Profil sagt zu wenig Verschattung voraus.** 10173–10175 weiterhin konstant null.

### 7.8 Reihenfolge ab hier

1. ~~`REGISTER.md` Punkte 1–7 aus 7.6 einarbeiten, 10254 als **plausibel**~~
   **erledigt 13.08. 15:30**, siehe 7.10
2. ~~rechts/links-Durchgang über `REGISTER.md` §7 und das Dashboard~~
   **erledigt 13.08. 15:30**, siehe 7.10 — Dashboard nur im Repo, **nicht deployt**
3. ~~**3.4** Recorder- und Rechenlast messen — vor allen weiteren Entities~~
   **erledigt 13.08. 15:30**, siehe 7.11 — Ergebnis: CPU unkritisch, Freigabe
   für Schritt 4 aus Lastsicht erteilt
4. dann 8 + 9 aus 7.6 einbauen, deployen, **ein** Neustart, SHA256-Gegenprüfung
5. 7.3 (Plausibilitätsklammer) und 7.2 (lastabhängiger Wirkungsgrad) vorlegen

Der Neustart für `const.py` aus 7.1 ist noch offen und wird mit Schritt 4
gebündelt — nicht einzeln auslösen.

### 7.9 Neuer offener Punkt: Forecast.Solar schlägt als Stufe durch

`E_FS` geht als **Momentanmultiplikator** in die Trübung ein:

```
Trübung = Pegel · E_FS / Σ(gain · POA · Form)
```

Forecast.Solar aktualisiert in der kostenlosen Stufe **stündlich**. Jede
Aktualisierung erzeugt damit einen Stufensprung in der Prognose, dazwischen
driftet das Modell. Das ist die Ursache des in 7.4 korrigierten Sprungs.

**Vorschlag:** `E_FS` nur langsam in den **Pegel** einrechnen und die
Restenergie aus dem eigenen POA-Integral ziehen. Dann verschwinden die Stufen,
ohne dass die Reaktion auf Wetteränderungen verloren geht.

Nicht in dieser Runde. Berührt den Rechenweg beider Prognosen.

### 7.10 Erledigt am 13.08. — Doku-Durchgang, nichts deployt

**Schritt 1 aus 7.8, `docs/REGISTER.md`.** Alle sieben Punkte aus 7.6
eingearbeitet:

| Punkt | Was jetzt dort steht |
|---|---|
| 1 | 10156 aus §3.7 entfernt, in §3.4 als **Gerätetemperatur, plausibel** geführt, mit dem Live-Wert 360 und der Byte-Herleitung der 1-Grad-Stufung |
| 2 | §4 „Nicht vorhanden": Gerätetemperatur gestrichen und begründet; **Batterie**temperatur bleibt als nicht auffindbar stehen |
| 3 | 10254 neu in §3.1 als **plausibel**, mit Regressionstabelle, Verhältnistabelle und dem ±65-kW-Defekt |
| 4 | 10252 in §3.4: Highbyte = Temperatur, Lowbyte weiter offen; §3.7 führt nur noch das Lowbyte |
| 5 | 10168 / 10170 / 10172 / 10205 auf **INT16** korrigiert, mit dem Grund (−0,08 A würde sonst 655,28 A) |
| 6 | §2 auf `10000-10005` erweitert, Live-Beleg `[0, 1, 0, 1100, 0, 0]` notiert |
| 7 | „Offen bleibt: 10205 …" entfernt; der Absatz erzählt die Auflösung jetzt in einem Zug |

**Schritt 2, rechts/links.** `REGISTER.md` §7 stützte sich noch auf das Foto und
die angenommene Blickrichtung — ersetzt durch die Herleitung aus dem
Verschattungsfahrplan. Der Abschnitt „Folge für die Verschattungshypothese"
behält seine Messdaten, bekommt aber das Giebelmodell als Erklärung und den
Nebenbefund aus 7.7 als offenen Punkt.

Betroffen waren mehr Dateien als die beiden genannten:

| Datei | Änderung |
|---|---|
| `docs/REGISTER.md` | §7 neu begründet, Warnhinweis ergänzt |
| `docs/DIAGNOSE.md` | Zuordnungstabelle und beide Messtabellen auf West/Ost |
| `docs/VERSCHATTUNG-PROFIL.md` | Fahrplantabelle und Azimutleiste |
| `docs/PROGNOSE.md` | Beobachtungsprotokoll zur Schattenform |
| `tools/verschattungsprofil.js` | Beschriftungs-Array der Konsolenausgabe |
| `docs/dashboard-pv-module.json` | alle `name`-Felder, zwei Erläuterungstexte, ein Jinja-Array |
| `FOLGEAUFTRAG.md` | „(rechts)" / „(links)" in der Fahrplantabelle in TEIL 1 |

**Stehen geblieben, absichtlich:** die Warnhinweise „Nie rechts oder links
schreiben" in `REGISTER.md` und `DIAGNOSE.md`; `DROSSELUNG.md` („rechts vom
MPP", Kennlinienrichtung); `VERSCHATTUNG.md` Zeile 790 (Leserichtung einer
Heatmap-Grafik); die Variablennamen `links` / `rechts` in `modell.py`,
`schaetzer.py` und `pruefe_lernprognose.py` — dort sind es die
Interpolationsnachbarn im Array, kein Ortsbezug.

**Nicht deployt.** Das Dashboard ist nur im Repo geändert. Die laufende
Lovelace-Ansicht zeigt weiter „ganz rechts" / „ganz links", bis das Deployment
freigegeben ist. `docs/dashboard-pv-module.json` parst nach der Änderung
fehlerfrei (`json.load`).

### 7.11 Ergebnis von 3.4 — Recorder- und Rechenlast, gemessen 13.08. 15:30

Ohne eine einzige neue Entity gemessen: CPU liefert die Proxmox-Integration,
die Datenbankgröße `sensor.diagnose_recorder_datenbankgroesse`, die Zeilenzahlen
die Recorder-Historie selbst.

**CPU: unkritisch, aber die Reihe hat einen Bruch.**

| Tag | Tagesmittel |
|---|---|
| 28.07.–09.08. | rund 31 % |
| 10.08. | 25,5 % |
| 11.08. | 8,8 % |
| 12.08. | 9,3 % |
| 13.08. | 9,6 % |

Der Abfall um 22 Punkte fällt mit der Inbetriebnahme von `solarbank_pv`
zusammen — falsche Richtung, also kein Kausalzusammenhang. **Zwei Lesarten,
beide dokumentiert:** entweder wurde am 10.08. etwas entfernt, das dauerhaft
Last zog, oder die Bezugsgröße hat sich geändert — `sensor.haos_18_1_maximale_cpu_leistung`
(4 Kerne) hat **selbst erst ab 10.08.** Statistik, die Sensorfamilie wurde an
dem Tag neu angelegt. Ging die VM dabei von 1 auf 4 Kerne, erklärt 31 / 4 ≈ 7,8
den Sprung fast vollständig.

Vergleichbar ist deshalb nur das Fenster ab 11.08. — und das ist genau das
Fenster, in dem die rund 95 Entities dazukamen: **8,8 → 9,6 %**, also **unter
einem Prozentpunkt auf vier Kernen.** Die CPU trägt das mühelos.

**Recorder: das ist die eigentliche Kostenstelle.** Datenbank 1128 MiB, und sie
wächst weiter — stündlich gemessen, nicht geschätzt:

| Zeitraum | Zuwachs |
|---|---|
| Tagsüber | 8–14 MiB/h |
| Nachts | 8–9 MiB/h |
| 24 h (12.08. 11:00 → 13.08. 11:00) | **+174 MiB** |

> Der Helfer `sensor.diagnose_recorder_wachstum` meldet **76 MB/d** und liegt
> damit um mehr als den Faktor zwei zu niedrig. Seine Glättung frisst den
> Trend. Wer die Zahl zur Entscheidung heranzieht, entscheidet auf falscher
> Grundlage — der stündliche Verlauf der Größe selbst ist belastbar.

**Der Purge läuft.** Zwischen 05:00 und 10:00 stand die Größe exakt still, davor
und danach wuchs sie mit 8 MiB/h. Das ist die Signatur des nächtlichen Purge um
04:12: freigegebene Seiten werden fünf Stunden lang wiederbefüllt, bevor die
Datei erneut wächst. Gegen die Alternativlesart „Sensor hing" spricht, dass er
um 10:00 **nicht** nachgesprungen ist. `purge_keep_days` ist nicht gesetzt,
also 10 Tage. Das Plateau stellt sich ein, sobald das 10-Tage-Fenster
vollständig aus Tagen mit der neuen Schreibrate besteht — grob ab dem 21.08.,
bei rund 1,7 GB. Platte: 63,3 GB gesamt, 25,9 GB belegt. Kein Engpass.

**Zeilen je Stunde, mittags gemessen** (`significant_changes_only=False`):

| Gruppe | Entities | Zeilen/h |
|---|---|---|
| PV-Stapel (`solarbank_pv`, `pv_lernprognose`, Verschattung) | 54 | **3742** |
| offizielle Integration + Stromleser-Dashboard | 10 | **3217** |

Die drei größten Einzelverursacher sind **keine** Register:

| Entity | Zeilen/h | /Tag |
|---|---|---|
| `sensor.saunaraum_…_pv_signal_streuung_5min` | 702 | 16 848 |
| `sensor.…_441_startseite_last` | 617 | 14 808 |
| `sensor.…_441_batterieladeleistung` | 513 | 12 312 |
| `sensor.saunaraum_…_pv_mittel_20min` | 269 | 6 456 |

Die Modbus-Register liegen bei **120 Zeilen/h** — exakt der 30-s-Takt, jede
Abfrage ein neuer Wert. Sie sind einzeln billig; teuer sind die
Statistik-Helfer, die auf dem 5-s-Polling der offiziellen Integration sitzen.

**Was die Messung nicht belegt:** die Umrechnung von Zeilen in Bytes. 6959
gemessene Zeilen/h stehen 14 MiB/h Wachstum gegenüber — das wären 2 KiB je
Zeile, unplausibel viel für eine `states`-Zeile. Es schreiben also noch weitere
Entities kräftig mit, oder einzelne führen große Attribute. **Der Byteanteil des
PV-Stapels ist damit offen; die Zeilenzahlen sind es nicht.**

**Nicht gemacht, weil `exclude` den Regelbetrieb berührt:** Der naheliegende
Hebel wäre `sensor.saunaraum_…_pv_signal_streuung_5min` — 16 848 Zeilen/Tag für
eine 5-Minuten-Streuung. Ob der Verlauf gebraucht wird, entscheidet der
Betreiber. Ergänzung der `exclude`-Liste wäre die Umsetzung, **nie**
Überschreiben.

**Freigabe für Schritt 4 aus 7.8:** Aus Sicht der Last spricht nichts gegen die
beiden neuen Entities (10001 `battery_status`, 10064 `operating_mode`). Sie
kosten keine zusätzliche Modbus-Anfrage und ändern sich selten — `battery_status`
kennt vier Zustände, `operating_mode` steht seit Tagen auf 0. Erwartete
Zusatzlast: unter 50 Zeilen/Tag.

### 7.12 Neuer Befund: Langzeitstatistik von 10156 steht seit 08:55 still

Aktiver Reparaturhinweis in HA, entstanden **13.08. 08:55**:
`units_changed_sensor.pv_unbekannt_stufenwert_1`. Der Zustand trägt jetzt `°C`,
die Statistik-Metadaten stehen weiter auf `unitless`.

| | |
|---|---|
| Zustand jetzt | 36,0 °C, zuletzt 15:28 — der Sensor selbst läuft normal |
| Statistikzeilen in 48 h | **eine einzige** |
| deren Werte | Mittel 319,8, Min 310, Max 320 — **Rohwerte**, aus der Zeit vor der ÷10-Skalierung |
| `is_fixable` | false — kein Ein-Klick-Fix in Reparaturen |

Ursache ist die Umdeutung des Registers selbst: aus einem einheitenlosen
Stufenwert wurde eine Temperatur mit Einheit und `device_class`. Der
Kurzzeitverlauf ist unberührt, die **Langzeitstatistik** nimmt seit 08:55 nichts
mehr an.

**Nicht angefasst.** Die Bereinigung löscht oder überschreibt aufgezeichnete
Statistik, und die Entity trägt den Präfix `pv_`. Zwei Wege, beide für die
Vorlage:

1. **Statistik-Metadaten löschen** (Entwicklerwerkzeuge → Statistiken). Die
   alten Rohwert-Zeilen verschwinden, die Aufzeichnung startet in °C neu. Die
   verlorenen Daten sind ohnehin unbrauchbar — 320 statt 32 °C.
2. **Einheit entfernen** und die Temperatur einheitenlos führen. Erhält die
   alte Reihe, macht den Verlauf aber unlesbar. Widerspricht der Begründung in
   `const.py`.

Empfehlung: Weg 1. Die zu erhaltende Reihe besteht aus falsch skalierten
Werten eines damals falsch gedeuteten Registers.

### 7.13 Der CPU-Bruch ist echt — die Bezugsgrößen-Lesart ist widerlegt

Entscheidungstest: `sensor.proxmox_cpu_auslastung` misst den **Host** von außen
und hat durchgehende Statistik seit dem 28.07., also von **vor** dem Bruch.
Eine geänderte Kernzahl der HAOS-VM kann die Prozentzahl des Hosts nicht
verschieben. Zeigt er denselben Sprung, war es ein echter Effekt.

| Tag | Host (Proxmox) | HAOS-VM |
|---|---|---|
| 28.07.–09.08. | rund 34 % | rund 31 % |
| 10.08. | 27,5 % | 25,5 % |
| 11.08. | **5,2 %** | **8,8 %** |
| 12.08. | 10,3 % | 9,3 % |
| 13.08. | 15,0 % | 9,6 % |

**Beide Reihen brechen gleichzeitig und gleich stark.** Damit ist die zweite
Lesart aus 7.11 widerlegt: es ist kein Bezugsgrößenwechsel, sondern eine echte
Entlastung am 10./11.08. Was dort entfernt oder repariert wurde, ist unbekannt
und liegt außerhalb dieses Projekts.

**Was daraus für die Zukunft folgt:** Der Host steigt seit dem Tiefpunkt
deutlich schneller wieder an als die VM — 5,2 → 15,0 gegen 8,8 → 9,6. Die
Rückkehr der Last kommt also überwiegend **nicht** aus Home Assistant. Wer die
VM-Reihe als Maß für die Kosten dieses Projekts liest, liest richtig; wer die
Host-Reihe dafür hält, schreibt uns fremde Last zu.

### 7.14 Attributtest: die Deduplizierung hält — der Verdacht bestätigt sich nicht

Geprüft an `sensor.pv_theoretische_leistung`, dem Sensor mit den meisten
Attributen: 60 aufeinanderfolgende Zustände über 20 Minuten im 30-s-Takt.

| | |
|---|---|
| Zustandszeilen | 60 |
| **verschiedene Attributsätze** | **3** |
| Wechsel 1 | `referenzstrang` „Modul 1" → „Modul 2" um 13:58:42 |
| Wechsel 2 | Neustart 14:06 — neues Attributschema mit `traeger_straenge`, `anteil_klarhimmel`, `blindfleck` |

Ein Verhältnis von 20:1 statt 1:1. Home Assistant schreibt den Attributsatz
also **nicht** je Zyklus neu — die Hash-Deduplizierung greift. Die
2-KiB-Lücke aus 7.11 erklärt sich damit **nicht** über breitere Zeilen.

**Einschränkung, die dazugehört:** Das Messfenster hatte stabile Verschattung,
`traeger_straenge` stand konstant auf 2. Bei Verschattungsübergängen ändert
sich der Wert, und dann wird der ganze Satz neu geschrieben — inklusive der
langen `blindfleck`-Zeichenkette. Die Churn-Rate ist also lastabhängig und an
einem wechselhaften Tag höher als hier gemessen. Der Rat, veränderliche
Diagnoseattribute aus hochtaktenden Sensoren herauszuziehen, bleibt richtig;
er ist nur nicht die Erklärung der Lücke.

**Die verbleibende Erklärung ist die einfachste:** Gemessen wurden 64 Entities.
Die Anlage hat sehr viel mehr. 14 MiB/h sind Systemwachstum, 6959 Zeilen/h sind
ein Ausschnitt daraus. Wer die Lücke schließen will, braucht die Gesamtzahl der
Zeilen, nicht die Breite einer einzelnen.

### 7.15 Vorlage: Wachstumssensor ersetzen statt reparieren

`sensor.diagnose_recorder_wachstum` (Derivative) meldet 76 MB/d gegen gemessene
174 MiB/24 h. Vorschlag des Betreibers, noch **nicht gebaut**: Differenz über
24 Stunden statt Ableitung mit Glättung — robust, kein Glättungsparameter, und
bei einer Größe, die sich täglich um Prozent ändert, völlig ausreichend.

Neuer Sensor mit Präfix `diagnose_`, also vorlegen und warten.

### 7.16 Ausgeführt am 13.08., 15:40–15:50 — ein Neustart, vier Freigaben

| Freigabe | Umsetzung |
|---|---|
| Schritt 4 | 10001 `battery_status` und 10064 `operating_mode` in `const.py`; Blöcke erweitert statt Anfragen ergänzt |
| 7.12 | `recorder/clear_statistics` auf `sensor.pv_unbekannt_stufenwert_1` |
| Recorder | zwei Statistik-Helfer in `exclude` ergänzt, nichts überschrieben |
| Dashboard | West/Ost-Beschriftung ins Deployment |

**Blockerweiterungen statt zusätzlicher Anfragen — live geprüft vor dem Einbau:**

| Gruppe | vorher | nachher | Probe (13.08., FC) |
|---|---|---|---|
| `mirror` | `Block(10002, 4)` | `Block(10000, 6)` | FC04 → `[0, 1, 0, 1320, 0, 0]` |
| `clock` | `Block(10060, 2)` | `Block(10060, 5)` | FC03 → `[27261, 51544, 0, 0, 0]` |

Beide Kombinationen antworten fehlerfrei; zusätzlich einzeln geprüft: FC04
`10001:1` → `[1]`, FC03 `10064:1` → `[0]`. Damit ist **`operating_mode` = 0 =
`self_consumption` unabhängig von der offiziellen Integration bestätigt** —
genau die Sicherheitsprüfung, die TEIL 4 verlangt und die bisher an einer
einzigen Quelle hing. Die sechs Sondenzeilen stehen in `tools/scan_log.jsonl`.

**Zwei bewusste Einschränkungen:**

1. `operating_mode` liegt in der Gruppe `clock` mit **Stundentakt**. Der Wert
   kann bis zu 60 Minuten alt sein. Für einen Modus, der sich nur durch
   Bedienung ändert, reicht das. Wer ihn frischer braucht: nach `limits`
   (300 s) verschieben und dort `Block(10064, 1)` ergänzen — ebenfalls geprüft,
   kostet dann eine zusätzliche Anfrage.
2. `battery_status` erscheint als **nackte Zahl 0–3**. Eine Enum-Übersetzung
   wäre eine Änderung am Lesepfad und ist nicht Teil dieser Freigabe. Die
   Bedeutung steht in `docs/REGISTER.md` 3.1.

**Verifikation nach dem Neustart, alles um 15:45–15:48 geprüft:**

| Prüfung | Ergebnis |
|---|---|
| `sensor.pv_batteriestatus` | 1,0 = Laden, deckt sich mit dem Vorzeichen von 10008 |
| `sensor.pv_betriebsmodus` | 0,0 = `self_consumption` |
| `anker_solix_official` | liefert frisch — `solarstrom` 1320 W um 15:45:16 |
| `input_boolean.nulleinspeisung_aktiv` | aus, vor und nach dem Eingriff |
| SHA256 `const.py` Repo ↔ Deployment | identisch (`FD25A142…44F5`) |
| Recorder-`exclude` | greift: beide Sensoren schreiben ab dem Neustart **nichts** mehr (letzte Zeilen 15:43:59 und 15:43:54) |
| Dashboard `pv-module` | 0 Treffer für „ganz rechts", 15 für „ganz westlich", 10 für „ganz östlich" |
| Repo-Kopie ↔ Live-Dashboard | als JSON deckungsgleich; die Browser-Fassung wurde **nicht** überschrieben, sondern per `config_hash` fortgeschrieben |

**Noch nicht prüfbar:** ob die Langzeitstatistik von 10156 in °C neu anläuft.
Statistiken werden zur vollen Stunde gerechnet, die erste Zeile kann also erst
ab 16:00 entstehen. Erwartet werden Werte um 36, nicht um 360.

### 7.17 Der CPU-Bruch ist aufgeklärt — nicht mehr untersuchen

Die Ursache ist benannt und liegt außerhalb dieses Projekts: Am **10.08.2026**
lief ein vollständiges HA-System-Audit. Darunter **fünf deinstallierte
Add-ons**, sechs gelöschte veraltete Automationen, eine reparierte kaputte
Template-Sensor-Kette und ein Neustart des ESPHome-Add-ons.

Fünf Add-ons erklären einen Host-CPU-Abfall von 34 auf 5 % in der richtigen
Größenordnung und zum richtigen Zeitpunkt. **Der Bruch ist damit erklärt; wer
ihn in der Reihe wiederfindet, muss ihn nicht erneut untersuchen.**

Der Nebenbefund aus 7.13 bleibt der wichtigere und ist davon unberührt:
Host 5,2 → 15,0 gegen VM 8,8 → 9,6. Die zurückkehrende Last kommt fast
vollständig **nicht** aus Home Assistant. Für die Kosten dieses Projekts ist
die VM-Reihe das Maß, nicht die Host-Reihe.

### 7.18 Nachgeschärft am 13.08., 16:00 — zweiter Neustart

Zwei Entscheidungen des Betreibers, beide umgesetzt:

**1. `operating_mode` von `clock` nach `limits`.** Begründung wörtlich: „Eine
Sicherheitsprüfung, die bis zu 60 Minuten alt sein darf, ist keine." Der
Stundentakt ist damit weg, der Wert ist höchstens 300 s alt. Preis ist eine
zusätzliche Modbus-Anfrage je 300 s — `Block(10064, 1)`, als Einzelread live
geprüft. Die Gruppe `clock` steht wieder auf `Block(10060, 2)`.

**2. `battery_status` bleibt eine Zahl, bekommt aber ein statisches Attribut.**
Neues Feld `bedeutung` im `Reg`-Dataclass, ausgegeben in
`sensor.py:extra_state_attributes`, aber nur wenn gesetzt:

| Entity | `bedeutung` |
|---|---|
| `sensor.pv_batteriestatus` | `0=standby, 1=laden, 2=entladen, 3=sleep` |
| `sensor.pv_betriebsmodus` | `0=self_consumption; andere Werte siehe Hersteller-YAML` |

**Warum statisch der Punkt ist:** Der Attributsatz bleibt über die Laufzeit
konstant und wird von Home Assistant per Hash dedupliziert — er kostet keine
zusätzliche Recorder-Zeile. Eine Übersetzung des Zustands selbst wäre eine
Änderung am Lesepfad gewesen und ist bewusst unterblieben.

**Geprüft, weil der Betreiber danach gefragt hat:** Beide Entities tragen
**kein** `state_class`. Es werden also keine Mittelwerte über Zustandscodes
gerechnet — ein Mittel von 1,4 zwischen „Laden" und „Entladen" kann gar nicht
erst entstehen. `state_class=None` stand von Anfang an im `Reg`, die Sorge war
gegenstandslos.

---

### 7.19 Sitzung vom „14.08." fand am 13.08. statt — drei Punkte nicht ausführbar

Der Sitzungsauftrag ist auf den **14.08.2026** datiert und nennt drei
zeitkritische Punkte. Uhr und Repo sagen etwas anderes:

| Beleg | Wert |
|---|---|
| Systemzeit bei Sitzungsbeginn | **13.08.2026, 16:06** |
| `git pull` | „Already up to date", HEAD unverändert `dd254ed` |
| Letzte Aktion der Vorsitzung | 13.08., 15:55 |

Zwischen beiden Sitzungen liegen **elf Minuten**, kein Tag. Damit sind alle
drei zeitkritischen Punkte nicht ausführbar — sie sind nicht verfallen,
sondern **noch nicht fällig**:

| Punkt | Warum nicht ausführbar |
|---|---|
| **A** 100-%-Zeitpunkt aus dem Recorder | Die 100 % sind noch nicht gefallen. SOC 85 % um 16:06, Prognose 17:05. Es gibt nichts zu holen. |
| **B** Bias diskriminieren (saisonal vs. Offset) | Der Test verlangt **denselben** Messwert an einem **anderen** Tag. Heute ist der Tag, dessen Wert bereits in 3.7 steht (+13,6 / +15 / +19 min). Eine Wiederholung am selben Tag misst nichts Neues. |
| **C** Erster vollständiger Verschattungstag | Der 14.08. hat nicht begonnen. `pv_verschattungsverlust_tag` steht weiter auf 0,772 kWh, `pv_theoretische_energie_tag` auf 3,248 kWh — beides Teiltag seit 14:00 des 13.08. |

**Für die nächste Sitzung gilt unverändert:** A aus dem SOC-Verlauf holen, B als
zweite Messung der PV4-Verspätung, C morgens ablesen. Die Vorgaben sind
richtig, sie brauchen nur den Tageswechsel.

**Erledigt gemeldet werden kann dagegen:** die Statistik von 10156 ist nach der
Bereinigung sauber neu angelaufen — Stundenzeile 15:00 mit Mittel/Min/Max je
**36**, nicht 360. Der Punkt aus 7.12 ist damit geschlossen.

### 7.20 Die 85-%-Prognose konvergiert nicht — sie meldet „jetzt + Konstante"

Gefragt war, ob die Prognose bei jedem stündlichen Forecast.Solar-Update
springt. Die Antwort ist ja, aber der Verlauf von
`sensor.pv_lernen_ziel_erreicht_um` zeigt daneben etwas Größeres.

| Ortszeit | Prognose | **Restzeit** |
|---|---|---|
| 14:30:00 | 15:14:17 | 0:44:17 |
| 14:47:17 | 15:32:17 | **0:45:00** |
| 14:48:17 | 15:18:17 | **0:30:00** |
| 15:00:17 | 15:30:17 | **0:30:00** |
| 15:06:17 | 15:36:17 | **0:30:00** |
| 15:07:17 | 15:52:17 | **0:45:00** |
| 15:13:17 | 15:58:17 | **0:45:00** |

**Die Restzeit ist auf die Sekunde konstant**, über 18 Minuten am Stück, und
springt nur in Stufen zwischen 30:00 und 45:00. Die vorhergesagte Uhrzeit
wandert also **exakt eine Minute pro Minute mit der Uhr mit**. Zwischen zwei
Neuberechnungen nähert sich die Prognose dem Ziel nicht an.

**Zwei Lesarten, beide dokumentiert:**

1. **Quantisierte Restzeit.** Der Sensor rechnet `jetzt + Restzeit`, und die
   Restzeit ist grob gerastert (30 / 45 min). Dafür spricht die Exaktheit:
   physikalische Modelle liefern verrauschte Differenzen, keine Sekunde-genauen
   Konstanten über 18 Messpunkte.
2. **Echt konstante Restzeit.** Ladeleistung und SOC-Zuwachs entwickeln sich
   gerade so, dass die Restzeit stehen bleibt. Möglich, erklärt aber die
   Sekunde-genaue Gleichheit nicht.

Lesart 1 ist die deutlich wahrscheinlichere. **Konsequenz:** Eine beobachtete
„Konvergenz" der Prognose ist kein Qualitätsmerkmal, solange sie nur zwischen
zwei Neuberechnungen gemessen wird. Das trifft die Bewertung in 7.5.

**Die Prüfbedingung aus 7.4 ist nur zur Hälfte bestätigt.** Dort stand: „die
Sprünge müssen immer kurz nach :05 liegen".

- Der Sprung um **15:07:17** (+16 min) liegt kurz nach :05 — Forecast.Solar
  aktualisiert um 15:06. **Bestätigt.**
- Der Sprung um **14:48:17** (−14 min) liegt **nicht** dort. Er hat eine
  andere Ursache.

**Es gibt also eine zweite Sprungquelle**, und sie ist unidentifiziert. Damit
greift der Vorschlag aus 7.9 (`E_FS` langsam in den Pegel statt als
Momentanmultiplikator) nur den einen Sprung ab — der zweite bliebe. Das gehört
in die Bewertung, bevor 7.9 gebaut wird.

**Gegenprobe am Ergebnis:** Die 85 % sind um **16:06** gefallen. Die letzte
aufgezeichnete Prognose davor sagte 15:58 — **8 Minuten zu früh**. Als
Fehlerbetrag der ungelernten Tagesform auf dem 85-%-Horizont brauchbar, aber
nicht als Ersatz für den 100-%-Test aus 7.5.

---

## TEIL 8 — Arbeitsregeln für die Sitzung

Vom Betreiber am 13.08. gesetzt. Faustregel dahinter: **Was reversibel und
nicht im Regelbetrieb ist, wird gemacht und berichtet — nicht gefragt.**

**Selbstständig entscheiden und nur berichten:**

- Doku-Korrekturen jeder Art (`REGISTER.md`, `FOLGEAUFTRAG.md`, Kommentare)
- `certain`-Flags, Anzeigenamen, Attribute
- rein lesende Analyseskripte in `tools/`
- Messreihen aufnehmen und auswerten

**Vorlegen und warten:**

- alles, was den Lesepfad verändert (Decoder, Filter, Klammern)
- neue Entities
- Deployment und Neustart
- alles mit Präfix `nulleinspeisung_` / `betriebsart_` / `pv_`

**Bei Unsicherheit über die Deutung einer Messung:** nicht fragen, sondern
**beide Lesarten dokumentieren und weiterarbeiten.**
