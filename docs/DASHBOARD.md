# Dashboard — PV-Module

Entwurf. Nichts davon ist ausgerollt. Die YAML unten ist zum Einfügen in den
Rohkonfigurations-Editor eines Dashboards gedacht; die Entscheidung, ob das ein
neues Dashboard oder eine weitere Ansicht in `nulleinspeisung-control` wird,
steht noch aus (siehe Offene Punkte).

**Nichts wird final ohne Abnahme durch den Auftraggeber.** Echte Screenshots
sind derzeit nicht möglich — die dafür nötige Rendering-Engine ist nicht
installiert. Was fehlt und was stattdessen zur Beurteilung vorliegt, steht in
Abschnitt 5; die Nachbildung des Layouts liegt als
`docs/dashboard-mockup.html` daneben.

Geprüft wurde am 11.08.2026 ausschließlich lesend: die registrierten
Lovelace-Ressourcen, der HACS-Bestand der Kategorie `lovelace`, die Existenz der
verwendeten Entitäten und die vorhandenen Dashboards. Am Gerät 192.168.178.86
wurde nichts angefasst.

---

## 1. Aufteilung und warum sie so ist

**Eine Ansicht, fünf Abschnitte, in genau der Reihenfolge der Vorgabe:**
Modulreihe, darunter Ströme, darunter Zelltemperaturen, darunter
Verschattungsstatus, darunter der Anlagenkontext.

Der Ansichtstyp ist `sections` mit `max_columns: 2`. Auf dem Handy fällt das auf
eine Spalte zusammen, damit steht die Reihenfolge oben nach unten exakt so wie
gefordert. Der Abschnitt mit der Modulreihe bekommt `column_span: 2` und bleibt
dadurch auch auf dem Schreibtisch oben und über die volle Breite — das „darunter"
der Vorgabe bleibt also in beiden Layouts wahr.

**2D, weil vier koplanare Module eine Fläche sind.** Die Modulreihe ist ein
`grid` mit `columns: 4` und `square: false`. Eine verschachtelte Grid-Karte
behält ihre Spaltenzahl bei *jeder* Breite bei — anders als die Abschnittsspalten
der Ansicht, die auf Handybreite umbrechen würden. Vier Kacheln bleiben also vier
Kacheln in einer Reihe, auf dem Handy wie auf dem Bildschirm. Keine Karte hat
eine feste Pixelbreite; die einzigen festen Maße sind die Schriftgrößen und eine
Mindesthöhe von 118 px je Kachel. Damit gibt es keine horizontale Scrollleiste.

Die Mindesthöhe steht dort, wo zuerst `aspect_ratio: "3/4"` stand — Hochformat
wie die Module selbst. Beim Bau der Nachbildung (Abschnitt 5) fiel auf, dass ein
festes Seitenverhältnis auf dem Schreibtisch entgleist: bei 1024 px
Inhaltsbreite wäre eine Kachel 246 px breit und damit 328 px hoch. Vier davon
füllen den halben Bildschirm mit Farbe und drei Zahlen. Eine feste Mindesthöhe
ergibt auf dem Handy dieselbe Hochformat-Kachel (88 × 118 px) und auf dem
Schreibtisch ein ruhiges Querformat. Genau dafür ist die Nachbildung da.

**Die vierte Kachel ist da, grau, gestrichelt umrandet und beschriftet.**
Weglassen wäre die Lüge, die der Auftrag ausdrücklich ausschließt. Zusätzlich —
und deutlich als Rechnung, nicht als Messung, gekennzeichnet — steht unter der
Reihe die Differenz aus der Gesamtleistung und den drei gemessenen Strängen. Das
ist der einzige verfügbare Hinweis auf Modul 4, und er ist schwächer als eine
Messung: er mischt zwei Abtastraten (offizielle Integration 5 s, `solarbank_pv`
30 s) und trägt die Fehler aller drei gemessenen Stränge mit.

**Ein einziger Zusatz gegenüber den Bordmitteln.** Nur die Modulreihe braucht
`button-card` (installiert), weil keine eingebaute Karte eine Hintergrundfarbe
aus einem Zahlenwert ableiten kann. Alles darunter — Verläufe, Temperaturen,
Verschattung, Kontext — ist `history-graph`, `tile`, `heading`, `grid` und
`markdown`. `card-mod` wird nicht gebraucht und deshalb auch nicht verwendet:
es greift über Shadow-DOM-Selektoren in Frontend-Interna und ist damit die
Komponente, die HA-Updates am ehesten zerlegt.

**Die Reihenfolge der Kacheln ist die Registerreihenfolge, nicht die
Dachreihenfolge.** Welches Register zu welchem Modul in der Reihe gehört, ist
ungeklärt (REGISTER.md, Abschnitt 7). Das steht als Unterzeile über der Reihe,
nicht nur in diesem Dokument — sonst liest jemand die Kachelreihe als Geometrie,
die sie nicht ist.

---

## 2. Farbskala und Begründung der Schwellen

Eingefärbt wird nach `sensor.pv_modul_n_stromanteil`, also nach dem Strom im
Verhältnis zum Median der übrigen Stränge.

| Anteil | Farbe | Hex | Bedeutung |
|---|---|---|---|
| ≥ 95 % | grün | `#2e7d32` | normal |
| 85 – < 95 % | gold | `#8d6e00` | auffällig |
| 70 – < 85 % | orange | `#b35300` | deutlich reduziert, Verschattungssensor sicher aus |
| 60 – < 70 % | rot | `#c62828` | Hysteresefenster, Sensor kann in beiden Zuständen stehen |
| < 60 % | dunkelrot | `#7f0000` | Verschattungssensor schaltet sicher ein |
| kein Wert oder < 0,5 A | grau | `#5c5c5c` | nicht aussagekräftig |

**Warum 95 % oben.** Die Module sind koplanar, gleicher Typ, gleicher Azimut,
gleiche Neigung. Unverschattet unterscheiden sie sich nur durch
Fertigungstoleranz (positive Binnung, 0 bis +5 Wp, also bis ~1 % Pmax),
Verschmutzung und kleine Temperaturunterschiede. Die Messung vom 11.08. zeigt
für zwei freie Stränge 100 % und 99 %. Die Stromauflösung des Registers beträgt
0,01 A, bei 14 A also 0,07 % — Quantisierung spielt keine Rolle. Ein Band von
5 % ist damit großzügig bemessen; alles darüber soll den Blick gar nicht erst
auf sich ziehen.

**Warum 70 % und 60 % nicht frei gewählt sind.** Das sind `SHADE_OFF` und
`SHADE_ON` aus `const.py`. Die Farbe muss zum Verschattungssensor passen, sonst
widersprechen sich zwei Anzeigen auf demselben Bildschirm. Unter 60 % schaltet
der Sensor sicher ein — dunkelrot. Über 70 % ist er sicher aus — orange oder
besser. Dazwischen liegt das Hysteresefenster, in dem der Sensorzustand von der
Vorgeschichte abhängt und nicht vom aktuellen Wert ablesbar ist; diese
Mehrdeutigkeit bekommt eine eigene Farbe, statt sie einer der beiden Seiten
zuzuschlagen.

**Warum 85 % dazwischen.** Zwischen „innerhalb der Toleranz" und „so weit
unten, dass die Verschattungslogik in Reichweite kommt" liegt ein Bereich, der
zu Verschmutzung, Randabschattung oder einem beginnenden Modulproblem passt und
eine Beobachtung wert ist, aber keinen Alarm. Diese Schwelle ist gesetzt, nicht
hergeleitet — sie ist der Kandidat, den man nach ein paar Wochen Verlauf
korrigiert.

**Warum grau unter 0,5 A.** Ein Verhältnis zweier kleiner Zahlen ist Rauschen.
0,5 A ist dieselbe Schwelle, mit der die Integration die Zelltemperatur
unterdrückt (`MIN_CURRENT_FOR_TEMP`) — eine zweite, abweichende Schwelle für
dieselbe Frage wäre eine unnötige Erklärungspflicht.

**Farbe ist nie der einzige Träger.** Auf jeder Kachel steht die Prozentzahl.
Die Skala ist außerdem monoton in der Helligkeit (grün → gold → orange → rot →
dunkelrot), damit die Reihenfolge auch bei Farbsehschwäche erhalten bleibt, und
die Kachel für Modul 4 ist zusätzlich gestrichelt umrandet. Die Hex-Werte sind
bewusst fest und keine Theme-Variablen: die Bedeutung einer Farbe darf sich
nicht mit dem Theme verschieben. Der Preis steht in den Offenen Punkten.

---

## 3. Dashboard-YAML

```yaml
button_card_templates:
  pv_modul:
    show_icon: false
    show_name: true
    show_state: true
    show_label: true
    layout: "vertical"
    tap_action:
      action: "more-info"
    label: >-
      [[[
        var a = states[variables.anteil];
        var i = states[variables.strom];
        if (!a || !i) return "—";
        if (isNaN(Number(a.state)) || isNaN(Number(i.state))) return "—";
        if (Number(i.state) < 0.5) return "< 0,5 A";
        return Math.round(Number(a.state)) + " %";
      ]]]
    styles:
      card:
        - padding: "6px 2px"
        - border-radius: "12px"
        - min-height: "118px"
        - color: "white"
        - background-color: >-
            [[[
              var a = states[variables.anteil];
              var i = states[variables.strom];
              if (!a || !i) return "#5c5c5c";
              if (isNaN(Number(a.state)) || isNaN(Number(i.state))) return "#5c5c5c";
              if (Number(i.state) < 0.5) return "#5c5c5c";
              var p = Number(a.state);
              if (p >= 95) return "#2e7d32";
              if (p >= 85) return "#8d6e00";
              if (p >= 70) return "#b35300";
              if (p >= 60) return "#c62828";
              return "#7f0000";
            ]]]
      name:
        - font-size: "0.72rem"
        - opacity: "0.9"
      state:
        - font-size: "1.05rem"
        - font-weight: "600"
      label:
        - font-size: "0.68rem"
        - opacity: "0.95"

views:
  - title: "PV-Module"
    path: "pv-module"
    icon: "mdi:solar-panel"
    type: "sections"
    max_columns: 2
    badges:
      - type: "entity"
        entity: sensor.anker_solix_solarbank_4_e5000_pro_441_solarstrom
        name: "PV gesamt"
      - type: "entity"
        entity: sensor.anker_solix_solarbank_4_e5000_pro_441_soc
        name: "Speicher"
      - type: "entity"
        entity: sensor.pv_ac_ausgangslimit
        name: "AC-Limit"
      - type: "entity"
        entity: sun.sun
        name: "Sonne"
      - type: "entity"
        entity: binary_sensor.pv_abregelung_erkannt
        name: "Abregelung"
        color: "red"
        visibility:
          - condition: "state"
            entity: binary_sensor.pv_abregelung_erkannt
            state: "on"
    sections:
      - type: "grid"
        column_span: 2
        cards:
          - type: "heading"
            heading: "Modulreihe"
            heading_style: "title"
            icon: "mdi:solar-panel"
          - type: "heading"
            heading: "Reihenfolge 1–4 ist die Registerreihenfolge, nicht die nachgewiesene Reihenfolge auf dem Dach"
            heading_style: "subtitle"
          - type: "grid"
            columns: 4
            square: false
            grid_options:
              columns: "full"
            cards:
              - type: "custom:button-card"
                template: "pv_modul"
                entity: sensor.pv_modul_1_leistung
                name: "Modul 1"
                variables:
                  anteil: sensor.pv_modul_1_stromanteil
                  strom: sensor.pv_modul_1_strom
                hold_action:
                  action: "more-info"
                  entity: sensor.pv_modul_1_stromanteil
              - type: "custom:button-card"
                template: "pv_modul"
                entity: sensor.pv_modul_2_leistung
                name: "Modul 2"
                variables:
                  anteil: sensor.pv_modul_2_stromanteil
                  strom: sensor.pv_modul_2_strom
                hold_action:
                  action: "more-info"
                  entity: sensor.pv_modul_2_stromanteil
              - type: "custom:button-card"
                template: "pv_modul"
                entity: sensor.pv_modul_3_leistung
                name: "Modul 3"
                variables:
                  anteil: sensor.pv_modul_3_stromanteil
                  strom: sensor.pv_modul_3_strom
                hold_action:
                  action: "more-info"
                  entity: sensor.pv_modul_3_stromanteil
              - type: "custom:button-card"
                name: "Modul 4"
                icon: "mdi:eye-off-outline"
                show_icon: true
                show_name: true
                show_state: false
                show_label: true
                label: "nicht messbar"
                layout: "vertical"
                size: "20px"
                tap_action:
                  action: "none"
                styles:
                  card:
                    - padding: "6px 2px"
                    - border-radius: "12px"
                    - min-height: "118px"
                    - background-color: "#5c5c5c"
                    - color: "white"
                    - border: "2px dashed rgba(255, 255, 255, 0.55)"
                  name:
                    - font-size: "0.72rem"
                    - opacity: "0.9"
                  label:
                    - font-size: "0.68rem"
                    - opacity: "0.95"
          - type: "markdown"
            entity_id:
              - sensor.anker_solix_solarbank_4_e5000_pro_441_solarstrom
              - sensor.pv_modul_1_leistung
              - sensor.pv_modul_2_leistung
              - sensor.pv_modul_3_leistung
            content: |-
              **Farbe = Strom im Verhältnis zum Median der übrigen Stränge.**
              ≥ 95 % grün · 85–95 % gold · 70–85 % orange · 60–70 % rot ·
              < 60 % dunkelrot · grau = kein belastbarer Wert (< 0,5 A).
              Die Prozentzahl steht auf jeder Kachel — die Farbe ist nie der
              einzige Träger der Aussage.

              **Modul 4 hat keine Modbus-Register** (REGISTER.md, Abschnitt 5).
              Es gibt dafür keinen Messwert und keinen Verschattungsstatus.
              Ersatzweise die Differenz zur Gesamtleistung, eine Rechnung und
              keine Messung:
              {% if has_value('sensor.anker_solix_solarbank_4_e5000_pro_441_solarstrom')
                and has_value('sensor.pv_modul_1_leistung')
                and has_value('sensor.pv_modul_2_leistung')
                and has_value('sensor.pv_modul_3_leistung') %}
              **{{ (states('sensor.anker_solix_solarbank_4_e5000_pro_441_solarstrom') | float
                - states('sensor.pv_modul_1_leistung') | float
                - states('sensor.pv_modul_2_leistung') | float
                - states('sensor.pv_modul_3_leistung') | float) | round(0) }} W**
              {% else %}
              **nicht berechenbar**, mindestens ein Eingangswert fehlt.
              {% endif %}
              Kleine negative Werte sind Rundung und unterschiedliche
              Abtastzeitpunkte (offizielle Integration 5 s, solarbank_pv 30 s),
              keine negative Erzeugung.

      - type: "grid"
        cards:
          - type: "heading"
            heading: "Ströme"
            heading_style: "title"
            icon: "mdi:current-dc"
          - type: "heading"
            heading: "Drei von vier Strängen. Modul 4 fehlt, weil es dafür keine Messung gibt."
            heading_style: "subtitle"
          - type: "history-graph"
            hours_to_show: 12
            grid_options:
              columns: "full"
              rows: 5
            entities:
              - entity: sensor.pv_modul_1_strom
                name: "Modul 1"
                color: "#1f77b4"
              - entity: sensor.pv_modul_2_strom
                name: "Modul 2"
                color: "#9467bd"
              - entity: sensor.pv_modul_3_strom
                name: "Modul 3"
                color: "#17a2a8"
          - type: "heading"
            heading: "Stromanteil, Bezug ist der Median der übrigen Stränge"
            heading_style: "subtitle"
          - type: "history-graph"
            hours_to_show: 12
            min_y_axis: 0
            max_y_axis: 110
            fit_y_data: false
            grid_options:
              columns: "full"
              rows: 5
            entities:
              - entity: sensor.pv_modul_1_stromanteil
                name: "Modul 1"
                color: "#1f77b4"
              - entity: sensor.pv_modul_2_stromanteil
                name: "Modul 2"
                color: "#9467bd"
              - entity: sensor.pv_modul_3_stromanteil
                name: "Modul 3"
                color: "#17a2a8"

      - type: "grid"
        cards:
          - type: "heading"
            heading: "Zelltemperatur"
            heading_style: "title"
            icon: "mdi:thermometer"
          - type: "heading"
            heading: "Aus der Spannung zurückgerechnet, gültig erst ab 0,5 A. Lücken im Verlauf sind der Normalfall, kein Ausfall."
            heading_style: "subtitle"
          - type: "tile"
            entity: sensor.pv_modul_1_zelltemperatur
            name: "Modul 1"
            grid_options:
              columns: 4
          - type: "tile"
            entity: sensor.pv_modul_2_zelltemperatur
            name: "Modul 2"
            grid_options:
              columns: 4
          - type: "tile"
            entity: sensor.pv_modul_3_zelltemperatur
            name: "Modul 3"
            grid_options:
              columns: 4
          - type: "history-graph"
            hours_to_show: 12
            grid_options:
              columns: "full"
              rows: 5
            entities:
              - entity: sensor.pv_modul_1_zelltemperatur
                name: "Modul 1"
                color: "#1f77b4"
              - entity: sensor.pv_modul_2_zelltemperatur
                name: "Modul 2"
                color: "#9467bd"
              - entity: sensor.pv_modul_3_zelltemperatur
                name: "Modul 3"
                color: "#17a2a8"

      - type: "grid"
        cards:
          - type: "heading"
            heading: "Verschattung"
            heading_style: "title"
            icon: "mdi:weather-cloudy"
          - type: "heading"
            heading: "Schaltet unter 60 % Stromanteil ein, erst über 70 % wieder aus"
            heading_style: "subtitle"
          - type: "tile"
            entity: binary_sensor.pv_modul_1_verschattet
            name: "Modul 1"
            grid_options:
              columns: 4
          - type: "tile"
            entity: binary_sensor.pv_modul_2_verschattet
            name: "Modul 2"
            grid_options:
              columns: 4
          - type: "tile"
            entity: binary_sensor.pv_modul_3_verschattet
            name: "Modul 3"
            grid_options:
              columns: 4
          - type: "markdown"
            content: |-
              Das Maß ist relativ. Bei drei messbaren Strängen ist der „Median
              der übrigen" der Mittelwert der beiden anderen — ein Schatten, der
              zwei Stränge gleichzeitig trifft, verschiebt also den Bezug und
              lässt den dritten zu gut aussehen. Ein Schatten über alle Stränge
              gleichzeitig wird prinzipiell nicht erkannt. Für Modul 4 gibt es
              keinen Verschattungsstatus.

      - type: "grid"
        cards:
          - type: "heading"
            heading: "Anlage"
            heading_style: "title"
            icon: "mdi:home-lightning-bolt"
          - type: "tile"
            entity: sensor.anker_solix_solarbank_4_e5000_pro_441_solarstrom
            name: "PV gesamt"
            grid_options:
              columns: 6
          - type: "tile"
            entity: sensor.anker_solix_solarbank_4_e5000_pro_441_soc
            name: "Speicher"
            grid_options:
              columns: 6
          - type: "tile"
            entity: sensor.pv_ac_ausgangslimit
            name: "AC-Ausgangslimit"
            grid_options:
              columns: 6
          - type: "tile"
            entity: sensor.pv_maximale_ladeleistung
            name: "Max. Ladeleistung"
            grid_options:
              columns: 6
          - type: "tile"
            entity: binary_sensor.pv_abregelung_erkannt
            name: "Abregelung erkannt"
            grid_options:
              columns: 6
          - type: "tile"
            entity: sensor.pv_drosselung_leistung
            name: "Drosselung jetzt"
            grid_options:
              columns: 6
          - type: "tile"
            entity: sensor.pv_drosselung_tag
            name: "Drosselung heute"
            grid_options:
              columns: 12
          - type: "markdown"
            content: |-
              „Abregelung erkannt" kommt aus dem Arbeitspunkt der MPP-Tracker
              (über 0,92 × Voc Richtung Leerlauf), „PV Drosselung" aus dem
              bestehenden Template-Helfer. Zwei unabhängige Wege zur selben
              Frage. Widersprechen sie sich, ist das ein Befund und kein
              Anzeigefehler.

              Das AC-Limit steht derzeit auf 800 W. Nach der Umstellung auf
              2500 W verschiebt sich die Schwelle, ab der Abregelung überhaupt
              auftreten kann — die Verläufe davor und danach sind nicht
              unmittelbar vergleichbar.
```

---

## 4. Vorausgesetzte benutzerdefinierte Karten

Der Entwurf verlangt **keine Karte, die nicht installiert ist.**

| Karte | Status im Bestand | Im Entwurf verwendet |
|---|---|---|
| `button-card` (custom-cards/button-card) | installiert, v7.0.1, Ressource `/hacsfiles/button-card/button-card.js` | **ja**, ausschließlich für die vier Kacheln der Modulreihe |
| `card-mod` (thomasloven/lovelace-card-mod) | installiert, v4.2.1 | nein, bewusst nicht |
| `bubble-card` (Clooos/Bubble-Card) | installiert, v3.2.5 | nein |
| `apexcharts-card` | installiert, v2.2.3 | nein, `history-graph` reicht und ist leichter |
| `mini-graph-card` | installiert, v0.13.0 | nein |
| `mushroom` | installiert, v5.2.2 | nein |
| `layout-card` | installiert, v2.4.7 | nein, durch `sections` überholt |
| `plotly-graph-card`, `power-flow-card-plus`, `auto-entities`, `flex-table-card`, `statistics-graph-chart-card`, `statistics-table-card`, `navbar-card`, `kiosk-mode`, `material-you-utilities`, `lovelace-material-components`, `card-mod-studio`, Strategien (`bonbon`, `mushroom`) | installiert | nein |

Erhoben über `ha_config_list_dashboard_resources` (26 Ressourcen) und
`ha_get_hacs_info(category="lovelace", installed_only=true)` (20 Repositories),
beides lesend.

Warum nicht `card-mod`, obwohl es da ist: es färbt zwar Karten ein, aber die
Farbe müsste aus einem Zahlenwert kommen, und dafür bräuchte es Jinja in einem
`card_mod:`-Block auf jeder einzelnen Kachel. `button-card` kann dieselbe Logik
in **einem** Template, das alle vier Kacheln teilen. Weniger Wiederholung, und
kein Eingriff ins Shadow DOM, der nach dem nächsten HA-Update nachgezogen werden
muss.

### Variante ohne jede benutzerdefinierte Karte

Falls `button-card` nicht laufen soll: Nur der erste Abschnitt wird ersetzt, die
Abschnitte „Ströme", „Zelltemperatur", „Verschattung" und „Anlage" oben sind
bereits reine Bordmittel und bleiben unverändert. Der Root-Schlüssel
`button_card_templates` entfällt dann ebenfalls.

```yaml
      - type: "grid"
        column_span: 2
        cards:
          - type: "heading"
            heading: "Modulreihe"
            heading_style: "title"
            icon: "mdi:solar-panel"
          - type: "heading"
            heading: "Reihenfolge 1–4 ist die Registerreihenfolge, nicht die nachgewiesene Reihenfolge auf dem Dach"
            heading_style: "subtitle"
          - type: "grid"
            columns: 4
            square: false
            grid_options:
              columns: "full"
            cards:
              - type: "vertical-stack"
                cards:
                  - type: "gauge"
                    entity: sensor.pv_modul_1_stromanteil
                    name: "Modul 1"
                    min: 0
                    max: 110
                    needle: false
                    severity:
                      green: 95
                      yellow: 70
                      red: 0
                  - type: "tile"
                    entity: sensor.pv_modul_1_leistung
                    name: "Modul 1"
                    vertical: true
              - type: "vertical-stack"
                cards:
                  - type: "gauge"
                    entity: sensor.pv_modul_2_stromanteil
                    name: "Modul 2"
                    min: 0
                    max: 110
                    needle: false
                    severity:
                      green: 95
                      yellow: 70
                      red: 0
                  - type: "tile"
                    entity: sensor.pv_modul_2_leistung
                    name: "Modul 2"
                    vertical: true
              - type: "vertical-stack"
                cards:
                  - type: "gauge"
                    entity: sensor.pv_modul_3_stromanteil
                    name: "Modul 3"
                    min: 0
                    max: 110
                    needle: false
                    severity:
                      green: 95
                      yellow: 70
                      red: 0
                  - type: "tile"
                    entity: sensor.pv_modul_3_leistung
                    name: "Modul 3"
                    vertical: true
              - type: "vertical-stack"
                cards:
                  - type: "button"
                    name: "Modul 4"
                    icon: "mdi:eye-off-outline"
                    show_state: false
                    tap_action:
                      action: "none"
                  - type: "markdown"
                    content: |-
                      **nicht messbar**
```

Was diese Variante nicht kann, und das ist kein Detail:

- Die eingebaute `gauge`-Karte kennt genau **drei** Stufen (`green`, `yellow`,
  `red`). Die fünfstufige Skala aus Abschnitt 2 fällt auf rot < 70 %,
  gelb 70–95 %, grün ≥ 95 % zusammen. Das Hysteresefenster 60–70 % ist damit
  nicht mehr sichtbar.
- Es gibt keinen grauen Zustand für „zu wenig Strom". Nachts steht die Anzeige
  auf 0 % oder auf „nicht verfügbar" und sieht aus wie ein Defekt.
- Vier Rundinstrumente nebeneinander sind auf einem schmalen Handy grenzwertig
  lesbar (etwa 85 px je Instrument). Wer das nicht will, setzt `columns: 2` und
  bekommt zwei Reihen zu zwei — was der Vorgabe „vier Rechtecke in einer Reihe"
  widerspricht. Das ist eine Entscheidung, keine Empfehlung.

---

## 5. Abnahme über gerenderte Screenshots

Auftrag: nichts wird final, bevor gerenderte Screenshots vorliegen und abgenommen
sind. Das ist der Stand dazu.

### 5.1 Befund: die Rendering-Engine fehlt

Das Werkzeug `ha_get_dashboard_screenshot` ist vorhanden, rendert aber nicht
selbst — es spricht ein Add-on namens **Puppet** an. Lesend geprüft am
11.08.2026:

| Prüfung | Ergebnis |
|---|---|
| Installierte Add-ons (9 Stück) | Cloudflared, Mosquitto, OpenCCU, ha_mcp, Terminal & SSH, ESPHome, Spotify Connect, Zählwerk App Space, Samba — **kein Puppet** |
| Verfügbar im Store | `0f1cc410_puppet` · „Puppet — Turn dashboards into nice pictures" · Repository *Balloob's experimental playground* |
| Ebenfalls im Store | `81f33d0f_puppet` aus dem ha-mcp-Repository |

**Echte Screenshots sind derzeit nicht möglich.** Was fehlt, ist genau eine
Sache: das Add-on **Puppet** (`0f1cc410_puppet`) aus dem Repository
`https://github.com/balloob/home-assistant-addons`. Das Repository ist in dieser
Installation bereits als Add-on-Quelle eingetragen, das Add-on selbst ist nur
nicht installiert. Nach der Installation muss es gestartet sein; die Engine hält
für die Aufnahmen einen Chromium-Prozess vor
(Option `keep_browser_open`, verwaltbar über `ha_manage_addon`).

**Warnung zum zweiten Treffer:** `81f33d0f_puppet` sieht nach demselben Add-on
aus, ist es aber nicht. Die eigene Beschreibung sagt: „Test-only mock … returns a
synthetic PNG instead of launching Chromium … Never shipped to users." Das Ding
liefert ein Platzhalterbild statt einer Aufnahme. Für eine Abnahme ist es
schlimmer als nichts, weil das Ergebnis wie ein Screenshot aussieht und keiner
ist. Wenn installiert wird, dann `0f1cc410_puppet`.

### 5.2 Was stattdessen vorliegt

`docs/dashboard-mockup.html` — eine statische Nachbildung des Layouts in HTML,
Handybreite 390 px und Schreibtischbreite 1024 px nebeneinander, im Browser zu
öffnen. Maße, Kachelgrößen, Farbschwellen, Umbrüche und Reihenfolge sind
maßstäblich nachgebaut.

Das ist **kein Screenshot und nicht der Home-Assistant-Renderer.** Schriftbild,
Kartenschatten, Icons und vor allem die Diagrammachsen weichen ab; die
Verlaufskurven sind von Hand gezeichnete Beispiele, keine echten Daten. Was sich
daran belastbar beurteilen lässt: Aufteilung, ob vier Kacheln auf 390 px
nebeneinander lesbar bleiben, ob die Farbskala wirkt, ob etwas horizontal
überläuft. Was sich daran *nicht* beurteilen lässt: wie HA die
`history-graph`-Karten tatsächlich zeichnet.

Ein Fehler ist dabei schon aufgefallen und in Abschnitt 1 und in der YAML
korrigiert worden: das ursprüngliche feste Seitenverhältnis der Modulkacheln
hätte auf dem Schreibtisch 328 px hohe Kacheln ergeben.

### 5.3 In Home Assistant wurde nichts angelegt

Kein Vorschau-Dashboard, keine Ressource, kein Add-on, keine Entität. Alle
Aufrufe an Home Assistant in diesem Auftrag waren lesend:
`ha_config_list_dashboard_resources`, `ha_get_hacs_info`, `ha_get_addon`,
`ha_get_state`, `ha_search`, `ha_get_overview`, `ha_get_skill_guide`.
`nulleinspeisung-control` und `nulleinspeisung-preview` wurden nicht geöffnet und
nicht verändert. Auf 192.168.178.86 wurde nicht zugegriffen.

Der Vorschlag, ein Vorschau-Dashboard `pv-module-preview` anzulegen und zu
rendern, ist **nicht ausgeführt** — aus zwei unabhängigen Gründen:

1. Ohne Puppet gäbe es davon ohnehin keinen Screenshot. Es bliebe ein
   angelegtes Dashboard ohne den Nutzen, für den es angelegt wurde.
2. Die Anweisung, in dieser Instanz nichts anzulegen und `ha_config_set_dashboard`
   nicht aufzurufen, steht unwidersprochen im ursprünglichen Auftrag. Ein
   Zwischenschritt, der genau das täte, braucht ein ausdrückliches Ja des
   Auftraggebers — nicht meine Auslegung.

### 5.4 Reihenfolge für die Abnahme

1. Nachbildung `docs/dashboard-mockup.html` ansehen. Reicht das zur Abnahme des
   Layouts, ist Schritt 2 und 3 überflüssig.
2. Sollen es echte Screenshots sein: Add-on `0f1cc410_puppet` installieren und
   starten. Das ist eine Installation in der laufenden Instanz und braucht eine
   Freigabe.
3. Vorschau-Dashboard mit `url_path: "pv-module-preview"` aus der
   Platzhalter-Variante in 6.5 anlegen, mit `viewport_presets: mobile, desktop`
   rendern, Bilder vorlegen. Ebenfalls freigabepflichtig.
4. Erst nach Abnahme und nach dem Ausrollen von `solarbank_pv` das echte
   Dashboard aus Abschnitt 3 anlegen und die Entity-IDs gegen die dann
   tatsächlich vorhandenen prüfen.

### 5.5 Platzhalter-Variante für den Vorschau-Rendergang

Dieselbe Struktur, gefüllt mit Entitäten, die **heute schon existieren**. Damit
zeigt ein Rendergang etwas, statt „Entität nicht verfügbar" in jeder Kachel.
Ersetzt werden nur die `entity`- und `variables`-Zeilen; Aufbau, Farben,
Schwellen und Texte bleiben wie in Abschnitt 3.

**Jede dieser Zuordnungen ist fachlich falsch und nur zum Ansehen da.** Werte vom
11.08.2026, sie wandern:

| Rolle im Entwurf | Platzhalter-Entität | Wert | ergibt |
|---|---|---|---|
| Modul 1 Leistung | `sensor.anker_solix_solarbank_4_e5000_pro_441_solarstrom` | 700 W | Kachelwert |
| Modul 1 Anteil | `sensor.anker_solix_solarbank_4_e5000_pro_441_soc` | 100 % | **grün** |
| Modul 1 Strom | `sensor.netzbezug_leistung` | 11,0 | ≥ 0,5 → nicht grau |
| Modul 2 Leistung | `sensor.power_production_now` | 494 W | Kachelwert |
| Modul 2 Anteil | `sensor.leons_zimmer_steckdose_schreibtisch_leistung` | 83,7 | **orange** |
| Modul 2 Strom | `sensor.haos_18_1_cpu_auslastung` | 9,8 | ≥ 0,5 → nicht grau |
| Modul 3 Leistung | `sensor.anker_solix_solarbank_4_e5000_pro_441_netzbezugsleistung` | 0 W | Kachelwert |
| Modul 3 Anteil | `sensor.fritz_box_7490_ui_cpu_temperatur` | 64 | **rot**, Hysteresefenster |
| Modul 3 Strom | `sensor.proxmox_cpu_auslastung` | 5,5 | ≥ 0,5 → nicht grau |
| Modul 4 | keine | — | grau, unverändert |
| Zelltemperatur 1–3 | `sensor.outdoor_meter_01/02/03_temperatur` | 25,2 / 25,4 / 27,8 °C | echte °C-Sensoren |
| Verschattung 1–3 | `binary_sensor.hmip_smi_000918a9952d5a_bewegung`, `binary_sensor.hmip_smo_00095be99a86fc_bewegung`, `binary_sensor.adguard_status` | aus / aus / an | zeigt beide Zustände |
| AC-Ausgangslimit | `sensor.anker_solix_solarbank_4_e5000_pro_441_netzeinspeiseleistung` | 0 W | |
| Max. Ladeleistung | `sensor.anker_solix_solarbank_4_e5000_pro_441_batterieladeleistung` | 0 W | |
| Abregelung erkannt | `binary_sensor.adguard_status` | an | zeigt den Alarmzustand |

Die drei Anteil-Platzhalter sind bewusst so gewählt, dass drei verschiedene
Stufen der Skala gleichzeitig zu sehen sind — grün, orange und das rote
Hysteresefenster. Vier Kacheln in vier Farben zu prüfen ist der Sinn des
Rendergangs.

Nur der erste Abschnitt und die Entity-Zeilen ändern sich:

```yaml
button_card_templates:
  pv_modul:
    show_icon: false
    show_name: true
    show_state: true
    show_label: true
    layout: "vertical"
    tap_action:
      action: "more-info"
    label: >-
      [[[
        var a = states[variables.anteil];
        var i = states[variables.strom];
        if (!a || !i) return "—";
        if (isNaN(Number(a.state)) || isNaN(Number(i.state))) return "—";
        if (Number(i.state) < 0.5) return "< 0,5 A";
        return Math.round(Number(a.state)) + " %";
      ]]]
    styles:
      card:
        - padding: "6px 2px"
        - border-radius: "12px"
        - min-height: "118px"
        - color: "white"
        - background-color: >-
            [[[
              var a = states[variables.anteil];
              var i = states[variables.strom];
              if (!a || !i) return "#5c5c5c";
              if (isNaN(Number(a.state)) || isNaN(Number(i.state))) return "#5c5c5c";
              if (Number(i.state) < 0.5) return "#5c5c5c";
              var p = Number(a.state);
              if (p >= 95) return "#2e7d32";
              if (p >= 85) return "#8d6e00";
              if (p >= 70) return "#b35300";
              if (p >= 60) return "#c62828";
              return "#7f0000";
            ]]]
      name:
        - font-size: "0.72rem"
        - opacity: "0.9"
      state:
        - font-size: "1.05rem"
        - font-weight: "600"
      label:
        - font-size: "0.68rem"
        - opacity: "0.95"

views:
  - title: "PV-Module (Vorschau, Platzhalterwerte)"
    path: "pv-module"
    icon: "mdi:solar-panel"
    type: "sections"
    max_columns: 2
    badges:
      - type: "entity"
        entity: sensor.anker_solix_solarbank_4_e5000_pro_441_solarstrom
        name: "PV gesamt"
      - type: "entity"
        entity: sensor.anker_solix_solarbank_4_e5000_pro_441_soc
        name: "Speicher"
      - type: "entity"
        entity: sun.sun
        name: "Sonne"
    sections:
      - type: "grid"
        column_span: 2
        cards:
          - type: "heading"
            heading: "Modulreihe"
            heading_style: "title"
            icon: "mdi:solar-panel"
          - type: "heading"
            heading: "VORSCHAU — alle Zahlen sind Platzhalter aus fremden Entitäten, nur das Layout gilt"
            heading_style: "subtitle"
          - type: "grid"
            columns: 4
            square: false
            grid_options:
              columns: "full"
            cards:
              - type: "custom:button-card"
                template: "pv_modul"
                entity: sensor.anker_solix_solarbank_4_e5000_pro_441_solarstrom
                name: "Modul 1"
                variables:
                  anteil: sensor.anker_solix_solarbank_4_e5000_pro_441_soc
                  strom: sensor.netzbezug_leistung
              - type: "custom:button-card"
                template: "pv_modul"
                entity: sensor.power_production_now
                name: "Modul 2"
                variables:
                  anteil: sensor.leons_zimmer_steckdose_schreibtisch_leistung
                  strom: sensor.haos_18_1_cpu_auslastung
              - type: "custom:button-card"
                template: "pv_modul"
                entity: sensor.anker_solix_solarbank_4_e5000_pro_441_netzbezugsleistung
                name: "Modul 3"
                variables:
                  anteil: sensor.fritz_box_7490_ui_cpu_temperatur
                  strom: sensor.proxmox_cpu_auslastung
              - type: "custom:button-card"
                name: "Modul 4"
                icon: "mdi:eye-off-outline"
                show_icon: true
                show_name: true
                show_state: false
                show_label: true
                label: "nicht messbar"
                layout: "vertical"
                size: "20px"
                tap_action:
                  action: "none"
                styles:
                  card:
                    - padding: "6px 2px"
                    - border-radius: "12px"
                    - min-height: "118px"
                    - background-color: "#5c5c5c"
                    - color: "white"
                    - border: "2px dashed rgba(255, 255, 255, 0.55)"
                  name:
                    - font-size: "0.72rem"
                    - opacity: "0.9"
                  label:
                    - font-size: "0.68rem"
                    - opacity: "0.95"

      - type: "grid"
        cards:
          - type: "heading"
            heading: "Ströme"
            heading_style: "title"
            icon: "mdi:current-dc"
          - type: "history-graph"
            hours_to_show: 12
            grid_options:
              columns: "full"
              rows: 5
            entities:
              - entity: sensor.anker_solix_solarbank_4_e5000_pro_441_solarstrom
                name: "Modul 1"
                color: "#1f77b4"
              - entity: sensor.power_production_now
                name: "Modul 2"
                color: "#9467bd"
              - entity: sensor.netzbezug_leistung
                name: "Modul 3"
                color: "#17a2a8"
          - type: "heading"
            heading: "Stromanteil"
            heading_style: "subtitle"
          - type: "history-graph"
            hours_to_show: 12
            min_y_axis: 0
            max_y_axis: 110
            fit_y_data: false
            grid_options:
              columns: "full"
              rows: 5
            entities:
              - entity: sensor.anker_solix_solarbank_4_e5000_pro_441_soc
                name: "Modul 1"
                color: "#1f77b4"
              - entity: sensor.pv_nutzungsgrad_heute
                name: "Modul 2"
                color: "#9467bd"
              - entity: sensor.haos_18_1_cpu_auslastung
                name: "Modul 3"
                color: "#17a2a8"

      - type: "grid"
        cards:
          - type: "heading"
            heading: "Zelltemperatur"
            heading_style: "title"
            icon: "mdi:thermometer"
          - type: "tile"
            entity: sensor.outdoor_meter_01_temperatur
            name: "Modul 1"
            grid_options:
              columns: 4
          - type: "tile"
            entity: sensor.outdoor_meter_02_temperatur
            name: "Modul 2"
            grid_options:
              columns: 4
          - type: "tile"
            entity: sensor.outdoor_meter_03_temperatur
            name: "Modul 3"
            grid_options:
              columns: 4
          - type: "history-graph"
            hours_to_show: 12
            grid_options:
              columns: "full"
              rows: 5
            entities:
              - entity: sensor.outdoor_meter_01_temperatur
                name: "Modul 1"
                color: "#1f77b4"
              - entity: sensor.outdoor_meter_02_temperatur
                name: "Modul 2"
                color: "#9467bd"
              - entity: sensor.outdoor_meter_03_temperatur
                name: "Modul 3"
                color: "#17a2a8"

      - type: "grid"
        cards:
          - type: "heading"
            heading: "Verschattung"
            heading_style: "title"
            icon: "mdi:weather-cloudy"
          - type: "tile"
            entity: binary_sensor.hmip_smi_000918a9952d5a_bewegung
            name: "Modul 1"
            grid_options:
              columns: 4
          - type: "tile"
            entity: binary_sensor.hmip_smo_00095be99a86fc_bewegung
            name: "Modul 2"
            grid_options:
              columns: 4
          - type: "tile"
            entity: binary_sensor.adguard_status
            name: "Modul 3"
            grid_options:
              columns: 4

      - type: "grid"
        cards:
          - type: "heading"
            heading: "Anlage"
            heading_style: "title"
            icon: "mdi:home-lightning-bolt"
          - type: "tile"
            entity: sensor.anker_solix_solarbank_4_e5000_pro_441_solarstrom
            name: "PV gesamt"
            grid_options:
              columns: 6
          - type: "tile"
            entity: sensor.anker_solix_solarbank_4_e5000_pro_441_soc
            name: "Speicher"
            grid_options:
              columns: 6
          - type: "tile"
            entity: sensor.anker_solix_solarbank_4_e5000_pro_441_netzeinspeiseleistung
            name: "AC-Ausgangslimit"
            grid_options:
              columns: 6
          - type: "tile"
            entity: sensor.anker_solix_solarbank_4_e5000_pro_441_batterieladeleistung
            name: "Max. Ladeleistung"
            grid_options:
              columns: 6
          - type: "tile"
            entity: binary_sensor.adguard_status
            name: "Abregelung erkannt"
            grid_options:
              columns: 6
          - type: "tile"
            entity: sensor.pv_drosselung_leistung
            name: "Drosselung jetzt"
            grid_options:
              columns: 6
          - type: "tile"
            entity: sensor.pv_drosselung_tag
            name: "Drosselung heute"
            grid_options:
              columns: 12
```

---

## 6. Offene Punkte

1. **Keine der `solarbank_pv`-Entitäten existiert bisher.** Am 11.08.2026 lesend
   geprüft: `sensor.pv_ac_ausgangslimit`, `sensor.pv_maximale_ladeleistung` und
   `binary_sensor.pv_abregelung_erkannt` liefern `ENTITY_NOT_FOUND`, eine Suche
   nach `pv_modul` findet null Entitäten. Die IDs in dieser YAML stammen
   ausschließlich aus der Aufgabenstellung und sind gegen die laufende Instanz
   **nicht** verifiziert. Bestätigt sind nur die fünf bestehenden Entitäten
   (`…_solarstrom` 700 W, `…_soc` 100 %, `pv_drosselung_leistung` 0 W,
   `pv_drosselung_tag` 0,199 kWh, `sun.sun`).
2. **Die IDs hängen davon ab, wie die Integration den Gerätenamen setzt.** HA
   bildet die Entity-ID aus Gerätename plus Entitätsname. Steht bei
   `has_entity_name` ein Gerätename wie „Solarbank PV" davor, entsteht
   `sensor.solarbank_pv_modul_1_spannung` statt `sensor.pv_modul_1_spannung`.
   Vor dem Ausrollen einmal prüfen; danach ist es ein Suchen-und-Ersetzen.
3. **Die physische Zuordnung Modul ↔ Register ist ungeklärt** (REGISTER.md,
   Abschnitt 7). Bis das Abdeck-Experiment gemacht ist, zeigt die Reihe vier
   Kacheln in Registerreihenfolge und nicht die Dachreihe. Entweder das
   Experiment durchführen und die Kacheln umbenennen, oder die Unterzeile
   dauerhaft stehen lassen.
4. **Der Differenzwert für Modul 4 ist nicht abgesichert.** Er unterstellt, dass
   `…_solarstrom` alle vier Stränge enthält und dieselbe Größe misst wie die drei
   Strangleistungen. Die Einzelablesung vom 11.08. stützt das
   (418 + 413 + 273 + 60 ≈ 1160 W), ein einzelner Vergleichspunkt ist aber kein
   Beleg. Ungeklärt bleibt auch, ob der Gesamtwert DC- oder wandlerseitig ist.
5. **Wo gehört der 0,5-A-Riegel hin?** `const.py` definiert
   `MIN_CURRENT_FOR_TEMP` nur für die Zelltemperatur. Ob `stromanteil` bei
   kleinen Strömen `unknown` liefert oder eine verrauschte Zahl, steht nicht
   fest. Die Kachel prüft es zusätzlich selbst — doppelt gemoppelt, falls die
   Integration es ohnehin tut, aber nicht falsch. Sauberer wäre eine
   Entscheidung an einer Stelle.
6. **Der Bezug „Median der übrigen Stränge" ist bei drei Strängen schwach.** Der
   Median von zwei Werten ist deren Mittelwert; ein Schatten auf zwei Strängen
   verschiebt den Bezug. Ein absoluter Bezug (Einstrahlung, Sonnenstand,
   erwartete Leistung aus Temperatur und Uhrzeit) wäre robuster, existiert aber
   nicht. Die Grenze gehört der Kennzahl, nicht dem Dashboard.
7. **Feste Hex-Farben statt Theme-Variablen.** Absicht, damit die Bedeutung einer
   Farbe stabil bleibt. Der Preis: unter einem Nutzertheme, besonders unter dem
   installierten Material You Utilities, wirkt die Modulreihe wie ein Fremdkörper.
   Wenn das stört, ist der Kontrast der hellen Stufen gegen Weiß neu zu prüfen —
   nicht einfach die Farben tauschen.
8. **`hours_to_show: 12` ist gesetzt, nicht hergeleitet.** Für Tagesvergleiche
   bräuchte es `statistics-graph` auf Langzeitstatistiken. Ob die abgeleiteten
   Sensoren überhaupt `state_class: measurement` bekommen und damit in die
   Statistik einlaufen, ist nicht geprüft.
9. **Verhältnis „Drosselung" zu „Abregelung erkannt" undefiniert.** Ersteres ist
   eine bestehende Kette aus Template-Helfer, Integrations-Helfer und
   Utility-Meter, letzteres kommt aus dem MPP-Arbeitspunkt. Beide stehen
   nebeneinander auf dem Dashboard, ohne dass geklärt wäre, ob sie dasselbe
   messen. Ein Abgleich über einen Tag mit Abregelung würde es zeigen.
10. **Zielort noch offen.** Vorhanden sind `nulleinspeisung-control`,
    `nulleinspeisung-preview` und `dashboard-stromleser`. Der `url_path`
    `pv-module` ist frei und enthält den geforderten Bindestrich. Wird die
    Ansicht stattdessen in ein bestehendes Dashboard eingehängt, muss
    `button_card_templates` auf dessen **Wurzelebene** stehen, nicht innerhalb
    von `views`.
11. **Außentemperatur nicht eingebunden.** `const.py` kennt
    `DEFAULT_OUTDOOR_TEMP = sensor.aussentemperatur`; ob diese Entität existiert,
    wurde nicht geprüft. Im Zelltemperatur-Verlauf wäre sie die natürliche
    Bezugslinie — 23 °C Unterschied wie am 11.08. sagen erst mit Bezug etwas.
12. **Nicht vom echten Renderer gerendert.** Es gibt eine maßstäbliche
    Nachbildung (`docs/dashboard-mockup.html`), aber keinen Screenshot aus Home
    Assistant, weil das Puppet-Add-on fehlt. Offen bleibt damit, wie HA die
    `history-graph`-Karten tatsächlich zeichnet, ob `min_y_axis`/`max_y_axis`
    dort in 2026.8.1 unverändert greifen und ob die Kachelbeschriftung auf
    Geräten unter 360 px Breite umbricht. Die Nachbildung legt nahe, dass es
    passt — sie beweist es nicht.
13. **Freigabe für die Add-on-Installation steht aus.** Für echte Screenshots
    muss `0f1cc410_puppet` installiert und gestartet werden. Das ist ein
    Eingriff in die laufende Instanz und in diesem Auftrag ausdrücklich
    ausgeschlossen. Ohne dieses Ja bleibt es bei der Nachbildung.
14. **Freigabe für das Vorschau-Dashboard steht aus.** Die Platzhalter-Variante
    in Abschnitt 5.5 ist fertig, aber nicht angelegt. Sie würde einen neuen
    `url_path` `pv-module-preview` belegen. Auch das ändert die laufende
    Instanz.
15. **Die Platzhalterwerte wandern.** Die Tabelle in Abschnitt 5.5 wurde so
    gewählt, dass am 11.08.2026 drei verschiedene Farbstufen gleichzeitig zu
    sehen sind. CPU-Auslastung und Steckdosenleistung ändern sich; ein
    Rendergang an einem anderen Tag kann vier gleichfarbige Kacheln zeigen und
    damit weniger über die Skala aussagen. Vor dem Rendern kurz die aktuellen
    Werte prüfen und gegebenenfalls andere Platzhalter wählen.
```
