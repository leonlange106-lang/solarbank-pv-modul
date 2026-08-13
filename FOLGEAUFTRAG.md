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
PV1 ganz rechts, dann PV2, PV3, PV4 ganz links. Vom Betreiber per Foto
bestätigt. Der Schatten wandert PV1 → PV4, also von rechts nach links.

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
  | PV1 (rechts) | 11:20–12:10 | 11:31–12:29 |
  | PV2 | 12:05–13:20 | 12:16–13:21 |
  | PV3 | ab 13:00 | 13:08–14:37 |
  | PV4 (links) | offen | 14:24–15:36 |

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

**Bisher unbestätigte Beobachtung:** Beide bisherigen Out-of-Sample-Vergleiche
zeigten *zu wenig* Verschattung — das Profil sagte 17/66/100/100 voraus,
gemessen wurden 9/60/voll/voll. Zwei Punkte sind kein Befund, aber die
Richtung ist konsistent. Bei nun vier gestaffelten Einbrüchen pro Tag ließe
sich das systematisch prüfen.

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

> Die physische Modulzuordnung ist **erledigt** — vom Betreiber per Foto
> belegt, PV1 ganz rechts bis PV4 ganz links. Nicht erneut erfragen und kein
> Abdeck-Experiment vorschlagen.
