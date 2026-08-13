# Solarbank-App — Plan

Eine eigene Oberfläche in Home Assistant, nicht auf Lovelace-Karten beschränkt.
UI/UX nach **Google Material Design 3**. Stand 13.08.2026.

---

## 1. Architekturentscheidung

Vier Wege standen zur Wahl. Gewählt ist **C**.

| Weg | Bewertung |
|---|---|
| A — Custom Lovelace Card | Bleibt im Kartenraster gefangen. Genau die Einschränkung, die weg soll. |
| B — Add-on mit Ingress | Eigener Container, eigener Build, eigene Auth-Kette. Schweres Geschütz für eine Oberfläche. |
| **C — `panel_custom` aus eigener Integration** | **Gewählt.** Volle Kontrolle über DOM und CSS, läuft **innerhalb** der angemeldeten HA-Oberfläche, bekommt das `hass`-Objekt gestellt. Kein Login, kein Token, kein CORS. Versioniert im Repo wie der übrige Code. |
| D — externe Seite | Bräuchte Token, CORS und eine zweite Anmeldung. Gewinnt nichts. |

**Kein Build-Schritt, keine npm-Abhängigkeit.** ES-Module als Web Components.
Grund: Jede Toolchain ist etwas, das in zwei Jahren nicht mehr baut. Das Repo
bleibt ohne Node reproduzierbar.

### Datenzugriff

| Zweck | Weg |
|---|---|
| Live-Werte | `hass.states` — von HA gepusht, kein Polling |
| Historie beim Aufklappen | `history/history_during_period` über WebSocket, on demand |
| Langzeitverlauf | `recorder/statistics_during_period` |
| Steuerung | `hass.callService(...)` |

### Datenquelle: bestehende Integrationen, keine zweite Implementierung

Die App bekommt **keinen** eigenen Modbus-Client. Sie liest, was `solarbank_pv`,
`pv_lernprognose` und `anker_solix_official` bereits als Entities bereitstellen.
Ein zweiter Leser am Gerät wäre eine weitere TCP-Sitzung auf einem Gerät, dessen
Verbindungsverhalten in `REGISTER.md` §10 als empfindlich dokumentiert ist — und
die Register sind ohnehin schon gelesen.

---

## 2. Die Sicherheitsregel, fest verdrahtet

> **Schreiben ausschließlich über `anker_solix_official` und HA-Helfer.
> Niemals über `solarbank_pv`.**

`solarbank_pv` hat keinen Schreibpfad und bekommt keinen. Die App ruft für jede
Änderung einen HA-Service auf; welcher Registerzugriff daraus wird, entscheidet
allein die offizielle Integration.

- Jedes Bedienelement trägt sichtbar die Quelle, über die es schreibt.
- Alles aus `solarbank_pv` ist in der App **schreibgeschützt** und als „nur
  lesend" markiert.
- Eingriffe in die Nulleinspeisung brauchen eine bewusste Bestätigung.

---

## 3. Material Design 3

| Aspekt | Umsetzung |
|---|---|
| Farbsystem | M3 Tonal Palette, Quellfarbe **Solar-Amber** `#F5A623`, Sekundär Blau-Grau. Light und Dark aus denselben Tokens. |
| Rollen | `surface`, `surface-container-*`, `primary`, `on-primary`, `outline-variant` als CSS Custom Properties |
| Typografie | M3-Skala: `display`, `headline`, `title`, `body`, `label` — Roboto/System-Stack |
| Form | M3 Corner Tokens: `xs 4` · `s 8` · `m 12` · `l 16` · `xl 28` |
| Elevation | Level 0–5 als Schattentokens, Container statt Schlagschatten wo möglich |
| Navigation | **Navigation Bar** unten (Mobil, ≤ 600 px) · **Navigation Rail** links (Tablet) · **Navigation Drawer** (Desktop ≥ 1240 px) |
| Komponenten | Card (filled/elevated), List, Switch, Slider, Segmented Button, FAB, Snackbar, Dialog, Chip |
| Motion | M3 Easing `emphasized` für Aufklappen, `standard` für Zustandswechsel; Dauern 200/300/500 ms |
| Zustände | State Layer 8 % hover / 12 % pressed, Ripple auf allen Tap-Zielen |
| Barrierefreiheit | Tap-Ziele ≥ 48 dp, Kontrast ≥ 4,5:1, `prefers-reduced-motion` respektiert |

---

## 4. Ansichten

### 4.1 Start — Hausansicht mit Stromfluss

Vorbild ist die Anker-App, Anspruch höher: **unser** Haus, Blick aus
**Südwest** (vom Garten auf Carport und Haus), und der Schatten **live**.

| Element | Quelle |
|---|---|
| PV → Speicher → Haus → Netz, animierte Flüsse | `..._solarstrom`, `..._batterieladeleistung`/`_batterieentladeleistung`, `..._startseite_last`, `..._netzbezugsleistung`/`_netzeinspeiseleistung` |
| Schattenwurf über die Modulreihe | `sun.sun` Azimut/Elevation + Azimutprofil aus `VERSCHATTUNG-PROFIL.md` |
| Je Modul eingefärbt | `sensor.pv_modul_N_leistungsanteil` |

**Bis Fotos und Maße vorliegen: Platzhalter.** Schematisches Haus mit Carport
und vier Modulen, Blickrichtung Südwest angedeutet, deutlich als Platzhalter
gekennzeichnet. Flussanimation und Schattenlogik laufen darauf **bereits echt** —
getauscht wird später nur Hintergrund und Modulgeometrie.

**Benötigt:** Fotos aus Südwest (Garten → Carport/Haus), bei hoher **und** tiefer
Sonne · Grundriss oder Maße von Haus und Carport · Lage und Firsthöhe des
gegenüberliegenden Hauses · Foto der Modulreihe von vorn.

### 4.2 Gesamtsystem
Erzeugung, Speicher, Hauslast, Netz — plus Tageswerte. Jede Kachel aufklappbar.

### 4.3 PV
Vier Stränge einzeln: Spannung, Strom, Leistung, Anteil. Dazu theoretische
Leistung und Verschattungsverlust. Sichtbar markiert, was **gemessen** und was
**geschätzt** ist — PV4 hat kein eigenes Registerpaar.

### 4.4 Akku
SOC, Lade-/Entladeleistung, Batteriestatus, kumulierte Energien, Wirkungsgrad,
Prognose „voll um" / „Ziel um" — mit dem Hinweis auf die 15-Minuten-Auflösung.

### 4.5 Prognose
Lernstand der vier Schätzer, Pegel, Tagesform, Trübung, Systemgain. Der
Lernstand ist die wichtigste Zahl: solange er nicht „4 von 4" sagt, sind alle
Prognosen Startwerte.

### 4.6 Verschattung
Fahrplan gegen Messung je Strang. Der belegte Bias gehört sichtbar dazu — das
Profil sagt zu wenig Verschattung voraus.

### 4.7 Steuerung
Nur Bedienelemente, die über die **offizielle** Integration schreiben:

| Element | Entity |
|---|---|
| Betriebsmodus | `select.anker_solix_..._betriebsmodus_gerat_lauft_im_drittanbieter_steuermodus` |
| Ladeobergrenze | `number.anker_solix_..._ladeobergrenze` |
| Entladegrenze | `number.anker_solix_..._entladegrenze` |
| Notstromreserve | `number.anker_solix_..._notstromreserve` |

Abgesetzt und mit Bestätigung: **Nulleinspeisung als Rückfallebene**
(`input_boolean.nulleinspeisung_aktiv`, `..._pv_prioritaetsladung`) samt
Parametern (`input_number.nulleinspeisung_*`).

### 4.8 Admin — Parameter und Historie
Alle Stellgrößen und Meta-Parameter an einer Stelle: Verschattungsschwellen,
Schwachlichtsperre, Plausibilitätsklammer, Wirkungsgradkurve,
Trübungs-Halbwertszeit, `E_FS`-Dämpfung. Je Eintrag Wert, Herkunft, Belegstelle —
und **aufklappbar die Historie**.

### 4.9 Diagnose
Die zehn Prüfungen, Registergesundheit, Verwurfszähler beider Klammern,
Recorder-Wachstum.

---

## 5. Aufklappbare Werte

Jede Kachel mit nicht-statischem Wert ist antippbar und zeigt darunter:

- Verlauf der letzten 24 h als Sparkline, nachgeladen beim Aufklappen
- Min, Max, Mittel im Fenster
- Zeitpunkt der letzten Änderung
- Herkunft: Entity-ID, Registeradresse, gemessen oder gerechnet

Umschaltbar auf 7 Tage über die Langzeitstatistik.

---

## 6. Dateien

```
custom_components/solarbank_app/
  __init__.py     Integration, Panel-Registrierung, statischer Pfad
  manifest.json
  const.py
  www/
    app.js        Panel-Element, Router, Shell
    m3.js         M3-Tokens, Basiskomponenten, Icons
    data.js       hass-Brücke, Historie, Formatierung, Service-Aufrufe
    tile.js       Kachel mit Aufklapp-Historie und Sparkline
    views.js      die neun Ansichten
    haus.js       Hausansicht: Flusslogik und Schattenprojektion
```

---

## 7. Umsetzungsstand

> **Korrektur.** Die erste Fassung dieser Tabelle führte alle Zeilen als
> „gebaut", während die Dateien noch gar nicht existierten — ich hatte den
> Zielzustand als Iststand geschrieben. Aufgefallen ist es beim Bau des
> Datenlayers. Die Tabelle führt ab jetzt nur, was tatsächlich im Repo liegt.

Stand 13.08.2026, 22:00 — alle sechs Module gebaut, Importgraph geprüft
(12 von 12 Importen aufgelöst), per SHA256 deployt, ein Neustart.

| Schritt | Stand | Beleg |
|---|---|---|
| Integration, Panel-Registrierung, statischer Pfad | **gebaut** | `__init__.py`, 9 Dateien SHA256-identisch deployt |
| M3-Designsystem (Tokens, Typo, Form, Elevation, Motion, Komponenten) | **gebaut** | `m3.js`, `M3_CSS` |
| Shell, Hash-Router, Navigation, Statuspunkt, Datenschnitt-Banner | **gebaut** | `app.js`, Element `solarbank-app` |
| Datenlayer, Historie, Statistik, 60-s-Cache | **gebaut** | `data.js`, Klasse `Data` |
| Kachel mit Aufklapp-Historie und Sparkline | **gebaut** | `tile.js`, `<sb-tile>` |
| Die neun Ansichten | **gebaut** | `views.js`, `VIEWS` |
| Hausansicht als Platzhalter, Fluss und Schatten echt | **gebaut** | `haus.js`, `buildHaus` |
| Echtes Haus, echte Schattengeometrie | **offen** | wartet auf Fotos und Maße |

**Noch nicht am echten Gerät erprobt:** Die Module sind statisch geprüft —
Syntax, Exporte, Importgraph, Entity-IDs gegen die Live-Anlage. Wie sich die
Oberfläche im Browser verhält, zeigt erst der erste Aufruf von `/solarbank`.

**Werte sind erst ab dem 14.08. verwertbar** (`FOLGEAUFTRAG.md` 7.23) — die App
blendet bis dahin ein Banner ein, das danach von selbst verschwindet.

### Fundstelle für die nächste Sitzung

Beim Bau kam eine Namenslücke heraus: `tile.js` liest
`--md-sys-shape-corner-large`, die Spezifikation nennt `-l`. Gelöst durch
Aliase in `M3_CSS`, sodass beide Schreibweisen auf denselben Wert zeigen. Wer
neue Komponenten baut, kann beide verwenden.
