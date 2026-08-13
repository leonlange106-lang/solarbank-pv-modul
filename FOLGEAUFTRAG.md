# Folgeauftrag: PV-Strangüberwachung und Prognose

### Anker SOLIX Solarbank 4 E5000 Pro an Home Assistant
### Stand nach der Sitzung vom 13.08.2026

Dieser Auftrag ist self-contained. Er setzt keinen Vorwissenskontext voraus.
Er löst den Masterauftrag vom 13.08. ab.

---

## TEIL 0 — Vorbedingung: Werkzeuge prüfen

**Erster Schritt, vor jeder Analyse und vor jeder Zeile Code.**

Prüfe, welche Plugins, MCP-Server, Skills und Zugänge verfügbar sind. Fehlt
etwas: konkret melden und warten. Nicht mit halber Ausstattung anfangen.

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
Betreiber technisch versiert, Sprache **Deutsch**, Antworten knapp und
strukturiert.

**Speicher:** Anker SOLIX Solarbank 4 E5000 Pro, Modell AE103, SN
AK7DN7M0G21100441, Firmware 1.0.2.30, unter **192.168.178.86:502**.
Offizielle HACS-Integration `anker_solix_official` 1.4.1, Polling 5 s.
Kapazität 5,1 kWh.

**PV:** vier Module à 500 Wp, koplanar auf einer Dachfläche, Azimut 188°,
Neigung 20°, je eigener MPP-Tracker. Module **Sakete SKT500M12-108D4**,
N-Typ Doppelglas **bifazial**. Vmp 33,18 V, Voc 39,90 V, Imp 15,07 A,
Temperaturkoeffizient Voc/Vmp −0,250 %/°C.

**AC-Ausgang auf 800 W begrenzt.** Nach Einbau einer Wieland-Dose sind
2500 W geplant, Umstellung in der Anker-App.

**Nulleinspeisung:** HA-seitige Regelung existiert als Rückfallebene, ist
aktuell **aus**. Normalbetrieb ist Ankers `self_consumption`. Von diesem
Auftrag nicht betroffen, darf unter keinen Umständen gestört werden.

**Repo:** `C:\Users\User\solarbank-pv-modul`, Remote
`github.com/leonlange106-lang/solarbank-pv-modul` (privat), Branch `main`.
Deployment nach `\\192.168.178.43\config\`.

---

## TEIL 2 — Was steht (nicht neu bauen)

### Drei Bausteine laufen

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
- **Verschattung quantifiziert:** scharfe Delle 12:30–15:30, Minimum 0,60
  gegen geometrische Klarhimmelerwartung, volle Erholung ab 16 Uhr. Deshalb
  liegt die Tagesspitze bei 11:25 statt am astronomischen Mittag 13:34.
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

### Rohdaten

`tools/rohdaten/` — 5,94 MB Messreihen, darunter `pv4_tag.jsonl` (Tageslauf
12.08., voller Registersatz je Messpunkt mit vorberechnetem `resid`) und
`fullsweep_progress.jsonl` (Adressraumscan). Format in
`tools/rohdaten/README.md`. Diese Daten sind nicht reproduzierbar.

---

## TEIL 3 — Was offen ist

### 3.1 Umstellung der beiden Prognosesensoren — wartet auf Lernstand

`sensor.nulleinspeisung_speicher_prognose` und
`sensor.prioritaetsladung_ziel_erreicht_um` laufen **unverändert** mit der
alten Logik. Beide sind Template-Helfer in `.storage`.

Der Umbau ist je eine Zeile: die Berechnung durch
`{{ states('sensor.pv_lernen_...') }}` ersetzen. **Entity-IDs beibehalten**,
bei `prioritaetsladung_ziel_erreicht_um` zusätzlich `device_class: timestamp`.

**Vorbedingung:** `sensor.pv_lernen_lernstand` steht auf „4 von 4
eingeschwungen". Vorher nicht umstellen — die Schätzer brauchen mehrere Tage.
Bis dahin laufen alt und neu sichtbar nebeneinander; das ist gewollt und der
beste verfügbare Vergleich.

### 3.2 Tagesertrag je Modul — nie gebaut

Riemann-Integral plus Utility Meter je Strang. Für Strang 4 auf der
Differenzleistung, die exakt ist. Damit ließe sich erstmals sagen, wie viel
Ertrag die Verschattung über einen Monat tatsächlich kostet — die Zahl, die
in die Ausbauentscheidung gehört.

### 3.3 `sensor.pv_drosselung_leistung` — Bestandsschutz-Umbau offen

Der Sensor rechnet noch Forecast-minus-Ist und ist über
`sensor.saunaraum_..._pv_signal_streuung_5min` gegated. Er wird konsumiert
von `sensor.pv_drosselung_energie` und `automation.pv_ueberschuss_nutzen`.

`binary_sensor.pv_abregelung_erkannt` existiert bereits und arbeitet über die
Spannungsschwelle 0,92 × Voc(T). **Entity-ID `sensor.pv_drosselung_leistung`
beibehalten, nur die Logik ersetzen.**

### 3.4 Recorder- und Rechenlast — nie gemessen

Rund 80 Entities aus `solarbank_pv`, elf aus `pv_lernprognose`, dazu
`sensor.saunaraum_..._pv_mittel_20min` (statistics, taktet mit 5,4 s, grob
16.000 Recorder-Einträge/Tag). Messen, ob die CPU des BananaPi das trägt.
Falls nötig: Drosselungsvorschlag, ohne die Reaktion auf Wetteränderungen zu
verlieren. Die `exclude`-Liste in `configuration.yaml` **nur ergänzen**.

### 3.5 `REGISTER.md` gegen `const.py` abgleichen

Die beiden liefen am 13.08. an zwei Stellen auseinander — **in beide
Richtungen**: Bei 10250 stand die richtige u32-Deutung längst in der Doku,
während der Code u16 las. Bei 10156 war es umgekehrt. Ein vollständiger
Abgleich beider Richtungen steht aus. Das ist die eigentliche Lieferung des
Projekts: Der Code ist reproduzierbar, die Registertabelle nicht.

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
Modul wie stark einbricht. Das ist eine Vermessung des realen Horizonts, die
kein Simulationswerkzeug liefert, und geht in die Ausbauentscheidung ein.

Ein Teil davon lässt sich **schon jetzt** aus `tools/rohdaten/pv4_tag.jsonl`
rekonstruieren, statt vier Wochen zu warten.

### 3.8 Zwei Hauslast-Lernsysteme laufen parallel — aufräumen

Das ist Redundanz, die beim Bau der Lernprognose entstanden ist und die
niemand entschieden hat:

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

Die übrigen Nachmittagswerte des Werktagsprofils stammen weiterhin aus den
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
  Erklärt ein bis zwei Prozent. Ob das die gelernten Größen stört, vorher
  prüfen — der Pegelschätzer hat sich auf die falschen Werte eingestellt.
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
- **Änderungen an `custom_components/` brauchen einen HA-Neustart** — sonst
  importiert HA die geänderten Module nicht. Ein Neustart dauert gemessen
  rund 5 Minuten.
- **Registerschlüssel in `const.py` nie umbenennen** — sie bilden die
  `unique_id`. Eine Umbenennung erzeugt eine neue Entity und schneidet den
  Verlauf ab. Der Anzeigename ist frei.
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

---

## TEIL 5 — Vorschlag zur Reihenfolge

1. Werkzeugprüfung, Ergebnis melden, auf Rückmeldung warten
2. `REGISTER.md` gegen `const.py` abgleichen (3.5) — billig, kein Gerät nötig
3. Tagesertrag je Modul (3.2) — schließt die letzte Lücke der Strangdaten
4. Recorder- und Rechenlast messen (3.4) — bevor weitere Entities dazukommen
5. `pv_drosselung_leistung` umbauen (3.3)
6. Prognosesensoren umstellen (3.1) — **erst wenn Lernstand 4 von 4**
7. Forecast.Solar-Geometrie korrigieren (3.8) — nach 6, damit der
   Pegelschätzer sich nicht mitten im Einschwingen neu justieren muss
8. Trübungs-Sweep wiederholen (3.6) — sobald ein bedeckter Tag vorliegt
9. Verschattungsprofil auswerten (3.7) — ab Mitte September

---

## TEIL 6 — Was der Betreiber entscheiden muss

Diese Punkte kann kein Agent klären:

- **`solarbank-diagnose` löschen?** Nach der Dashboard-Konsolidierung ist es
  nur noch aus der Sidebar genommen, nicht entfernt.
- **Prognose umstellen, wenn der Lernstand steht** — Freigabe für 3.1.
- **Wieland-Dose und 2500 W** — Hardware plus Umstellung in der Anker-App.
  Die Prognose zieht danach automatisch nach, weil sie Register 10038 liest.
- **Physische Modulzuordnung** — welches Register zu welchem Modul in der
  Reihe gehört, lässt sich nur experimentell klären: ein Modul kurz abdecken
  und beobachten, welcher Strom einbricht. Fünf Minuten.
- **Ausbauentscheidung Mitte September** — dafür liefert das
  Verschattungsprofil die Grundlage.
