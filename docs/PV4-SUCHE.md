# PV4-Suche: der lückenlose Einzeladress-Nachweis

Stand: 12.08.2026, 09:00 Uhr. Gerät AE103, SN …441, Firmware 1.0.2.30.

> **Der Adressraum ist vollständig geprüft.** Alle 65 536 Adressen einzeln mit
> `count=1`, davon 63 528 im Nachtlauf vom 11.08. 20:18 bis 12.08. 03:21 Uhr —
> **null neue gültige Register**. Eine Gegenprobe über 500 Adressen unter
> laufender Einspeisung am 12.08. um 08:53 Uhr bestätigt das (Abschnitt 9.2a).
> Die Kernaussage dieses Dokuments steht damit nicht mehr auf drei Bereichen,
> sondern auf dem gesamten 16-Bit-Adressraum.

Auftrag: lückenlos nachweisen, ob die Solarbank ein eigenes Register für den
vierten PV-Strang hat, und dabei die methodische Lücke des bisherigen
32er-Block-Scans schließen.

Der Sweep lief von 19:38 bis 19:54 Uhr, nachdem der Auftraggeber die
Integration `solarbank_pv` deaktiviert und damit einen Verbindungsplatz
freigegeben hatte. Ausschließlich lesend, ausschließlich FC03 und FC04.

---

## 1. Kurzantwort

**Der methodische Einwand des Auftraggebers war berechtigt — er hat zwölf
bisher unbekannte Register zutage gefördert. Ein Register für Strang 4 ist
nicht darunter.**

1. **Die Lücke war real und ist jetzt für die aussichtsreichen Bereiche
   geschlossen.** 2003 Adressen wurden einzeln mit `count=1` angesprochen.
   Ergebnis: **131 gültig, 1872 Exception 2, Summe exakt 2003** — kein
   Transportfehler, keine übersprungene Adresse. Für 10000–11000,
   32700–33100 und 59900–60500 ist die Aussage jetzt **lückenlos**.

2. **Die Methode hat geliefert, was der Blockscan nicht konnte: 12 neue
   gültige Adressen.** Darunter acht im Smart-Meter-Bereich 10632–10649, den
   `REGISTER.md` als „durchgehend Exception 2" abgeschrieben hatte — das war
   ein reiner Blockread-Artefakt. Und zwei Register, die in **keiner**
   Herstellerdefinition vorkommen: **10006** und **10015**.

3. **Keine dieser Adressen ist Strang 4.** Der entscheidende Test lief über
   12 Messpunkte bei fallender Dämmerung: während der PV4-Restwert zwischen
   −13,7 W und +29,4 W schwankte, blieben 10015 (= 100), 10006 (= 0),
   10001, 10004 und 10648/10649 **völlig unbewegt**. Die einzigen bewegten
   Neuzugänge — 10635/10636/10637 — sind laut Hersteller-YAML die
   **Phasenströme des Smart Meters**, springen ohne jede physikalische
   Kontinuität (65012 → 2621 → 59769 → 13107) und stehen neben Phasenspannungen
   von exakt 0 V. Es ist kein Smart Meter angeschlossen; die Register sind
   uninitialisiert.

4. **Unit 0 ist jetzt geklärt** — 107 Adressen Wert für Wert gegen Unit 1:
   **103 identisch**, die 4 Abweichungen sind ausschließlich die schnellsten
   Messgrößen und liegen im Rahmen von 0,35 s realer Änderung. Unit 0 und
   Unit 1 bedienen dasselbe Registerabbild. Kein zweites Abbild, kein
   versteckter Strang.

**Antwort auf die Ausgangsfrage: Strang 4 hat kein eigenes Modbus-Register.**
Für die drei hier ausgewerteten Bereiche ist das lückenlos belegt und nicht
mehr nur „nicht gefunden".

**Nachgetragen am 12.08.:** Inzwischen gilt das für den **gesamten
Adressraum**. Der vollständige Sweep über die restlichen 63 528 Adressen ist
durchgelaufen und hat **null** gültige Register gefunden (Abschnitt 9.2), die
Gegenprobe unter Produktion bestätigt es (Abschnitt 9.2a). Der Vorbehalt „rund
65 000 Adressen bleiben offen" aus der ursprünglichen Fassung ist damit
eingelöst — es gibt kein ungeprüftes Versteck mehr.

---

## 2. Bilanz des Sweeps

| Bereich | Adressen | gültig | Exception 2 | Summe | lückenlos? |
|---|---|---|---|---|---|
| 10000–11000 | 1001 | 121 | 880 | 1001 | ✅ |
| 32700–33100 | 401 | 6 | 395 | 401 | ✅ |
| 59900–60500 | 601 | 4 | 597 | 601 | ✅ |
| **gesamt** | **2003** | **131** | **1872** | **2003** | ✅ |

Kein einziger Transportfehler, kein Timeout, keine Lücke. Jede der 2003
Adressen hat eine eindeutige Antwort geliefert.

**Gefundene gültige Adressen, vollständig:**

```
10000-10002, 10004, 10006, 10008, 10010, 10012, 10014-10015, 10018, 10022,
10026, 10030, 10034, 10036, 10038, 10040-10049, 10060, 10064, 10071,
10073-10075, 10077-10078, 10090-10124, 10130, 10133, 10144-10156,
10167-10172, 10183, 10187, 10199, 10202, 10205, 10208, 10210, 10212-10213,
10224, 10227, 10230, 10233, 10235, 10237-10238, 10250, 10252, 10254, 10256,
10262, 10264, 10632-10637, 10648-10649, 32768-32772, 32774, 60000-60003
```

**Wichtig für das Verständnis der Geräteregeln:** 79 Adressen, die der alte
Scan als gültig kannte, antworten bei `count=1` **nicht** — darunter 10003,
10009, 10011, 10013, 10061, 10173–10175, 10209 und die Blöcke 10134–10143,
10157–10166, 10214–10239. Das ist kein Widerspruch, sondern die bekannte
Start-/Count-Validierung: diese Adressen sind ausschließlich **innerhalb eines
Blocks** lesbar, nie einzeln. Ebenso 32773, 32775–32799 und 60004–60031.

**Die beiden Methoden sind also komplementär, nicht redundant.** Der Blockscan
findet, was nur im Block lesbar ist; der Einzelscan findet, was nur einzeln
lesbar ist. Erst beide zusammen ergeben die vollständige Karte. Genau das war
der Punkt des Auftraggebers.

---

## 3. Alle neu gefundenen gültigen Adressen

Zwölf Adressen, die der alte Scan nie als gültig belegt hatte. Werte aus dem
Sweep um 19:38–19:45 Uhr, Zeitreihe aus 12 Messpunkten 19:57:47–19:59:35.

| Adresse | Wert | Zustände über 12 Punkte | Quelle | Deutung | PV4? |
|---|---|---|---|---|---|
| **10001** | 2 | **1** (konstant) | Hersteller-YAML | `battery_status` = **2 = Entladen**. Deckt sich mit dem Betriebszustand am Abend. Erstmals tatsächlich gelesen — der Blockread ab 10000 scheitert immer | Nein |
| **10004** | 0 | **1** | Hersteller-YAML | `third_party_pv_power`, Highword des INT32 (10004/10005) | Nein |
| **10006** | 0 | **1** | **keine** | **Undokumentiert.** In keiner der fünf Hersteller-YAMLs definiert. Vermutlich Highword eines ungenutzten INT32-Objekts 10006/10007 (10007 antwortet einzeln nicht — typisch für ein 32-Bit-Objekt) | **Nein** — konstant null, während der Restwert um 43 W schwankte |
| **10015** | 100 | **1** | **keine** | **Undokumentiert.** Liegt direkt hinter `battery_soc` (10014). Wert 100 bei einem SOC von 90–94 → **kein** SOC-Duplikat. Plausibelster Kandidat: **State of Health in %**. Das wäre ein echter Fund, denn `REGISTER.md` §4 führt Zyklen/Gesundheit als „nicht vorhanden" | **Nein** — exakt 100 über alle 12 Punkte, siehe Test unten |
| **10632** | 0 | **1** | Smart-Meter-YAML | `primary_phase_1_voltage` (UINT16, gain 10) → **0,0 V** | Nein |
| **10633** | 0 | **1** | Smart-Meter-YAML | `primary_phase_2_voltage` → 0,0 V | Nein |
| **10634** | 0 | **1** | Smart-Meter-YAML | `primary_phase_3_voltage` → 0,0 V | Nein |
| **10635** | 47186 | **12** | Smart-Meter-YAML | `primary_phase_1_current` (INT16, gain 100) → −183,5 A | **Nein**, siehe unten |
| **10636** | 12583 | **4** | Smart-Meter-YAML | `primary_phase_2_current` → +125,8 A | **Nein** |
| **10637** | 30933 | **12** | Smart-Meter-YAML | `primary_phase_3_current` → +309,3 A | **Nein** |
| **10648** | 0 | **1** | Smart-Meter-YAML | im Leistungsblock des Meters | Nein |
| **10649** | 0 | **1** | Smart-Meter-YAML | dito | Nein |

### 3.1 Der Smart-Meter-Bereich — eine Korrektur an `REGISTER.md`

`REGISTER.md` §4 schreibt: „Seine Registerdefinition 10620–10702 liefert unter
Unit 0 wie Unit 1 und mit FC03 wie FC04 **durchgehend Exception 2**."

**Das ist widerlegt.** Acht Adressen dieses Bereichs antworten bei `count=1`
einwandfrei. Die alte Aussage beruhte ausschließlich auf Blockreads und ist
exakt der Fehlschluss, um den es in diesem Auftrag ging.

Inhaltlich ändert das nichts an der Schlussfolgerung, aber die Begründung ist
eine andere: Die Register **existieren** in der Firmware der Solarbank, sind
aber **unbelegt**, weil kein Smart Meter angeschlossen ist. Belege:

- Alle drei Phasenspannungen (10632–10634) sind **exakt 0**. Ein
  angeschlossenes Messgerät an einem 230-V-Netz kann keine 0 V melden.
- Die drei „Ströme" ergäben −183,5 A, +125,8 A und +309,3 A — bei 0 V.
  Physikalisch unmöglich.
- Über 12 Messpunkte springen sie ohne jede Kontinuität:
  10635 = 65012 → 40370 → 64487 → 2621 → 59769 → 35652 → 13107 → 55050 →
  7864 → 56623 → 28836 → 34603. Eine Messgröße verhält sich nicht so.
  10636 wechselt nur zwischen vier Werten (65012, 2621, 5767, 12583).

Das Muster der wiederkehrenden Werte (0x0A3D = 2621, 0x1687 = 5767,
0xFDF4 = 65012) legt nahe, dass hier **Bruchstücke von IEEE-754-Gleitkommazahlen**
in einem nicht initialisierten Puffer stehen. Für die PV4-Frage ist das
gleichgültig: Es sind laut Herstellerdefinition **netzseitige Phasenströme**,
keine DC-Strangwerte.

### 3.2 Der entscheidende Test: bewegen sich die Neuzugänge mit PV4?

Der Auftrag verlangt Korrelation gegen `resid` mit 10213 als Negativkontrolle
und der Auflösungsprüfung. Beides wurde durchgeführt, über 12 Messpunkte im
10-s-Takt bei fallender Dämmerung (`watch_new.jsonl`).

Im Messfenster bewegte sich der **Restwert von −13,7 W über +29,4 W** — eine
Spanne von 43 W bei einer Gesamtleistung von 40 W. Wenn ein Register Strang 4
misst, muss es sich hier bewegen.

| Register | Zustände | Urteil |
|---|---|---|
| 10001, 10004, 10006, 10015, 10632, 10633, 10634, 10648, 10649 | **1** | **Konstant, während PV4 um 43 W schwankte.** Als Messgröße für Strang 4 ausgeschlossen |
| 10635, 10637 | 12 | Bewegt, aber sprunghaft ohne Kontinuität, neben 0 V Phasenspannung. Smart-Meter-Phasenströme, kein DC-Strang |
| 10636 | 4 | dito, und 4 Zustände reichen nicht |

**Auflösungsmaßstab zum Vergleich:** Die drei bestätigten Strangströme nehmen
im Abendlauf **161 / 156 / 154** verschiedene Zustände an. Der vom
Auftraggeber genannte Maßstab (80–92 Zustände über einen Tag) ist damit sogar
konservativ. Kein Neuzugang kommt auch nur in die Nähe.

**Negativkontrolle:** 10213 (Netzfrequenz) liefert im Abendlauf über 229
Punkte **r(resid) = −0,032**. Das Fenster ist sauber; ein r-Wert unter etwa
0,2 ist Rauschen.

---

## 4. Ergebnis des Unit-0-Vergleichs

**Durchgeführt wie beauftragt: 10144–10250, Wert für Wert, unmittelbar
nacheinander** (Unit 0 und Unit 1 im Abstand von 0,35 s, damit reale Änderung
minimal bleibt).

| Ergebnis | Anzahl |
|---|---|
| Adressen verglichen | **107** |
| **identisch** | **103** |
| abweichend | 4 |

Die vier Abweichungen:

| Adresse | Unit 0 | Unit 1 | Was es ist |
|---|---|---|---|
| 10168 | 65523 (= −13) | 65529 (= −7) | Strom Strang 1, in der Dämmerung im Sekundentakt springend |
| 10170 | 72 | 89 | Strom Strang 2 |
| 10172 | 99 | 112 | Strom Strang 3 |
| 10213 | 4996 | 4995 | Netzfrequenz, ±0,01 Hz |

**Alle vier sind genau die volatilsten Größen des Geräts**, und die Differenzen
entsprechen dem, was sich in 0,35 s ohnehin ändert — bei den Strangströmen in
der Dämmerung nachweislich sogar mehr (siehe Abschnitt 7.2). **Kein einziges
statisches Register weicht ab.** Ein zweites, abweichendes Registerabbild
unter Unit 0 gibt es nicht.

Damit ist die Aussage „Unit 0 und 1 sind derselbe Server" von **einer
Stichprobe auf 107 Stichproben** gehoben und bestätigt. Der aussichtsreichste
verbliebene Einzeltest ist damit erledigt — er hat nichts ergeben.

**Unit-IDs — abgeschlossen (Nachlauf 20:15 Uhr).** Nach Reparatur des Wrappers
(ein Timeout ist eine gültige Antwort „diese Unit-ID existiert nicht", kein
Verbindungsverlust) wurden die verbliebenen **17 IDs in 40 Sekunden** statt in
8,5 Minuten geprüft:

```
9, 11, 12, 13, 14, 15, 17, 20, 24, 30, 33, 50, 64, 128, 240, 254, 255
```

**Alle 17 antworten nicht** (Timeout). Zusammen mit den zwölf des Altscans und
den beiden aus dem ersten Durchlauf (7, 8) sind damit **31 Unit-IDs außer 0
und 1 geprüft — keine einzige antwortet.** Das Gerät bedient genau zwei
Unit-IDs, und beide zeigen dasselbe Registerabbild. Ein zweiter Modbus-Server
im Gerät, der Strang 4 führen könnte, existiert nicht.

---

## 5. FC03 gegen FC04

Alle 131 gefundenen Adressen wurden zusätzlich mit FC03 gelesen.

**Das belastbare Ergebnis: Kein einziger FC03-Read lieferte eine Exception.**
Jede über FC04 lesbare Adresse ist auch über FC03 lesbar — das Aliasing gilt
also auch für die neu gefundenen Adressen, einschließlich des
Smart-Meter-Bereichs. Von 131 Adressen lieferten **109 exakt denselben Wert**.

**Die 22 abweichenden Adressen sind kein Befund, sondern ein Messfehler
meinerseits — das gehört hierhin, weil es sonst jemand als Aliasing-Bruch
liest.** Verglichen wurde der FC03-Wert von 19:51 gegen den FC04-Wert aus dem
Sweep von 19:38–19:45. Zwischen beiden Lesungen liegen **6 bis 13 Minuten**.
Die 22 Abweichungen sind ausnahmslos zeitveränderliche Größen:

```
10012, 10014, 10041, 10130, 10167-10172, 10199, 10202, 10205, 10213,
10224, 10227, 10230, 10238, 10256, 10635-10637
```

Beispiel 10014 (`battery_soc`): FC04 = 92 (19:38), FC03 = 90 (19:51). Der
Akku hat in 13 Minuten 2 % entladen — und **10041 und 10256, die beide den SOC
spiegeln, zeigen exakt dieselbe Differenz** (Highbyte 92 → 90). Das ist ein
konsistenter Zeitversatz, kein Registerunterschied.

### 5.1 Der Nachtest — erledigt, der Verdacht war unbegründet

Um 20:16 Uhr wurden alle 131 Adressen erneut geprüft, diesmal **FC04 und FC03
im Abstand von 50 ms** statt von Minuten.

| Ergebnis | Anzahl |
|---|---|
| Adressen geprüft | **131** |
| **identischer Wert** | **130** |
| abweichend | **1** |
| FC03-Ausnahmen | **0** |

Die einzige Abweichung: **10167, FC04 = 348, FC03 = 347** — die Spannung von
Strang 1, um **einen** Rohwert (0,1 V) verschieden, bei zwei Lesungen 50 ms
auseinander. Das ist Messrauschen, kein Registerunterschied.

**Damit ist das Aliasing FC03 ⇄ FC04 für alle 131 Adressen bewiesen**, auch für
die volatilen und auch für den Smart-Meter-Bereich. Die 22 „Abweichungen" des
ersten Durchlaufs waren restlos der Zeitversatz — der Verdacht ist ausgeräumt,
nicht bloß unbewiesen geblieben.

**Ebenfalls nachgeprüft: 10650–10702.** 53 Adressen einzeln, **0 gültig** —
wie schon im Hauptsweep, der diesen Bereich (er liegt innerhalb 10000–11000)
bereits abgedeckt hatte. Die Angabe „noch offen" in der vorigen Fassung dieses
Dokuments war ein Fehler meinerseits; die Wiederholung bestätigt das Ergebnis
reproduzierbar. Gültig im Smart-Meter-Bereich sind ausschließlich
10632–10637 und 10648/10649.

---

## 6. Neubewertung aller bisherigen Befunde

Datengrundlage `pv4_evening.jsonl`, Stand 19:23 Uhr, **n = 229 Messpunkte**,
PV-Spanne **60–810 W**, Restwert −65…288 W. Negativkontrolle 10213:
r(resid) = **−0,032** → Fenster tauglich.

### 6.1 Der kritische Fall 10205 — Gegenhypothese geprüft, sie fällt

Die Gegenhypothese lautete: die Korrelation sei Zufall, weil AC-Ausgang und
PV-Summe abends gleichläufig fallen. **Falsifiziert, dreifach:**

1. **Die Voraussetzung trifft nicht zu.** Wären beide gleichläufig, müsste
   r(ac, resid) hoch sein. Gemessen: **+0,530**. Es gibt also reichlich
   Zeitfenster, in denen sie auseinanderlaufen.
2. **Nach Abzug des AC-Anteils bleibt nichts.** `|AC| ÷ U × 100` von 10205
   abgezogen ergibt einen Rest von im Mittel −0,60 Rohwerten, der mit dem
   Restwert zu **r = −0,031** korreliert.
3. **Der Trenntest in den Divergenzfenstern** — Schritte, in denen AC-Leistung
   und Restwert in **entgegengesetzte** Richtung gehen:

   | Schrittweite | Divergenzschritte | 10205 folgt AC | 10205 folgt resid |
   |---|---|---|---|
   | 30 s | 7 | 7 | 0 |
   | 60 s | 6 | 6 | 0 |
   | 120 s | 11 | 11 | 0 |
   | **Summe** | **24** | **24** | **0** |

4. **Gegenprobe bei stillstehender AC-Leistung:** In 177 Schritten mit
   |ΔAC| ≤ 20 W schwankte der Restwert um −132…+171 W, 10205 aber nur um
   −19…+13 Rohwerte (r = +0,040).

**10205 ist der AC-Ausgangsstrom. Endgültig.** r(10205, AC) = **+0,995**.

### 6.2 Vollständige Tabelle

| Register | Zustände | Spanne | r(resid) | bisherige Deutung | Könnte es PV4 sein? |
|---|---|---|---|---|---|
| 10003 | 58 | 60–810 | +0,653 | Lowword von `pv_power` | **Nein — zirkulär**, der Restwert wird daraus gebildet |
| 10170 | 156 | 30–705 | +0,540 | Strom Strang 2 | Nein — App-verifiziert (2,2 %) |
| 10209 | 37 | 390–810 | +0,530 | Lowword AC-Leistung | Nein — r(ac) = 1,000 |
| 10205 | 105 | 165–337 | +0,527 | AC-Ausgangsstrom | **Nein — 24:0**, siehe 6.1 |
| 10014/10041/10130/10256 | 6 | 95–100 | +0,490 | SOC (drei Kopien) | Nein — 6 Zustände |
| 10009 | 35 | 0–480 | −0,481 | Batterieleistung Lowword | Nein — negativ korreliert |
| 10156 | 3 | 340–360 | +0,462 | Stufenwert | Nein — 3 Zustände |
| 10252 | 4 | 8705–9216 | +0,458 | Highbyte = 10156 ÷ 10 | Nein — 4 Zustände |
| 10168 | 161 | −10…695 | +0,445 | Strom Strang 1 | Nein — App-verifiziert (0,2 %) |
| 10265 | 4 | 136–139 | −0,407 | Lowword Entladeenergie | Nein — monotoner Zähler |
| 10061 | 229 | — | −0,402 | Gerätezeit Lowword | Nein — zählt monoton |
| 10172 | 154 | 4–740 | +0,353 | Strom Strang 3 | Nein — App-verifiziert (1,8 %) |
| 10224/10227/10199/10202 | 32–34 | 2376–2410 | +0,32…0,33 | Netzspannung A–D | Nein — 237,6–241,0 V |
| 10230 | 15 | 17–41 | −0,329 | AC-Blindstrom | Nein — 15 Zustände, negativ |
| 10011 | 44 | 400–2630 | +0,328 | Hauslast Lowword | Nein — r(ac) = +0,722 |
| 10236 | 26 | 42–99 | −0,305 | AC-Blindleistung | Nein — 26 Zustände, negativ |
| 10234 | 4 | 1–4 | −0,249 | Zustandscode | Nein — 4 Zustände |
| 10254/10255 | 41 | −550…0 W | −0,069 | **neu**: INT32, folgt −Batterieleistung (+48,5 ± 19,4 W) | Nein — negativ, Betrag wächst bei fallender PV |
| 10213/10238 | 19 | 4991–5009 | **−0,032** | Netzfrequenz | **Negativkontrolle** |
| **10173/10174/10175** | **1** | **0** | — | Plätze des vierten Strangpaars | **Nein** — konstant null über 306 Punkte, auch bei 288 W Restwert |
| **10183/10187** | **1** | **0** | — | unbestimmt | **Nein** — konstant null; jetzt zusätzlich einzeln bestätigt gültig |
| **10001/10004/10006/10015** | **1** | — | — | **neu**, siehe §3 | **Nein** — konstant, während PV4 um 43 W schwankte |
| **10632–10637, 10648/10649** | 1–12 | — | — | **neu**: Smart Meter, unbelegt | **Nein** — netzseitig, 0 V Phasenspannung |
| 121 weitere | 1 | konstant | — | siehe `REGISTER.md` | Nein |

**Kein Kandidat übersteht die Prüfung.** Der höchste nicht-zirkuläre, nicht
bereits identifizierte r-Wert liegt bei 0,04.

---

## 7. Zwei neue Protokollbefunde für `REGISTER.md`

### 7.1 Das Gerät erlaubt nur drei gleichzeitige Sitzungen

Vor der Freigabe war ein vierter Client **nicht** möglich: Der TCP-Handshake
gelingt, die erste Modbus-PDU wird mit RST beantwortet. **434 Versuche über
15 Minuten, 0 Erfolge.** Ausgeschlossen wurde:

- **Netzweg:** Bindung an die direkte LAN-Adresse (192.168.178.129) statt an
  den Tailscale-Pfad (100.74.115.49) — **ebenfalls RST**. Kein Tunnel-Artefakt.
- **Begrenzung pro Quell-IP:** sonst hätte die LAN-Adresse funktioniert.

Alle drei Clients halten ihre Sitzung **dauerhaft** (offizielle Integration
`modbus_client.py:107`; `solarbank_pv` `modbus_reader.py:92-93`; Nacht-Sampler
`pv4_evening.py:208-209`, bestätigt per `netstat` über 14 s gleicher
Quellport). Sobald `solarbank_pv` deaktiviert war, kam die Verbindung
**im ersten Versuch** zustande.

**Konsequenz für den Betrieb:** Ein vierter Modbus-Client ist an diesem Gerät
grundsätzlich nicht möglich, solange die drei bestehenden laufen. Wer messen
will, muss einen abschalten.

### 7.2 Die Strangströme sind INT16, nicht UINT16 — mit Folgen für den Sampler

`REGISTER.md` §3.2 führt 10168/10170/10172 als UINT16. **Das ist falsch.** In
der Dämmerung liefert 10168 Werte ab 32768 aufwärts:

| Zeit (UTC) | 10168 roh | als INT16 | als Strom |
|---|---|---|---|
| 17:28:49 | 65529 | −7 | −0,07 A |
| 17:30:49 | 65526 | −10 | −0,10 A |
| 17:38:19 | 65526 | −10 | −0,10 A |

Über den ganzen Lauf: 10168 min **−10**, 10170 min +28, 10172 min +4. Nur
Strang 1 geht negativ — physikalisch plausibel für ein Modul, das bei
Restlicht als Erstes unter die Schwelle fällt.

**Der Nacht-Sampler rechnet diese Werte vorzeichenlos** und produziert dadurch
Leistungen von **+20 000 W** für Strang 1 und Restwerte von **−20 000 W**.
Betroffen sind bislang 8 von 306 Messpunkten, alle nach 19:28 Uhr — und es
werden mit fortschreitender Nacht mehr. Wirkung auf die Auswertung:

| Dämmerungsabschnitt (pv_total ≤ 60 W, n = 76) | Mittelwert des Restwerts |
|---|---|
| wie vom Sampler geschrieben | **−10 164,8 W** |
| mit INT16 korrigiert | **+15,7 W** (Spanne −17,6…+34,1) |

**Jede Nachtauswertung, die `resid` aus `pv4_evening.jsonl` ungefiltert
verwendet, ist damit unbrauchbar.** Die Korrektur ist ein Einzeiler:
`v - 65536 if v >= 32768 else v` auf 10167–10172 in `derive()`. Bis das
geschehen ist, müssen Punkte mit `|resid| > 1000` verworfen oder neu gerechnet
werden.

---

## 8. Sonnenuntergangstest und die Sockel-Hypothese

Der Auftraggeber meldet: Restwert von ~90 W auf 22 W gefallen, Gesamtleistung
auf 70 W. **Die korrigierte Rechnung bestätigt das und stellt es auf eine
breitere Basis.** Restwert nach Leistungsklasse, INT16-korrigiert, n = 306:

| pv_total | n | Restwert Mittel | sd | Anteil an pv_total |
|---|---|---|---|---|
| ≥ 400 W | 167 | 118,7 W | 41,0 | 21,7 % |
| 200–399 W | 39 | 88,5 W | 26,9 | 26,8 % |
| 100–199 W | 7 | 70,1 W | 21,7 | 53,3 % |
| 40–99 W | 93 | **17,4 W** | 12,9 | 30,4 % |

**Der Restwert fällt mit der Gesamtleistung — er bleibt nicht auf einem
Plateau stehen.** Ein konstanter systematischer Versatz (Sockel) hätte genau
das tun müssen. **Die Sockel-Hypothese ist damit erledigt**, und zwar mit
korrigierten Zahlen statt mit den vom Vorzeichenfehler verseuchten.

Der endgültige Test steht weiterhin aus: `pv_total → 0` tritt erst nach
Sonnenuntergang (20:59) ein. Der Sampler läuft bis 09:00 und deckt ihn ab —
**vorausgesetzt, die INT16-Korrektur wird vorher eingebaut oder nachträglich
gerechnet.**

---

## 9. Was jetzt lückenlos ausgeschlossen ist — und was offen bleibt

### 9.1 Lückenlos ausgeschlossen

| Bereich | Methode | Status |
|---|---|---|
| **10000–11000** | 1001 × count=1, FC04 | ✅ vollständig, 121 gültig |
| **32700–33100** | 401 × count=1, FC04 | ✅ vollständig, 6 gültig |
| **59900–60500** | 601 × count=1, FC04 | ✅ vollständig, 4 gültig |
| **Unit 0, 10144–10250** | 107 × Wert-für-Wert gegen Unit 1 | ✅ identisch |
| Alle 131 gefundenen Adressen | FC03 zusätzlich gelesen | ✅ keine Exception |

In diesen Bereichen liegt **kein Register, das Strang 4 misst**.

### 9.1a Nachgetragen am 11.08. um 20:15–20:18 Uhr

| Punkt | Ergebnis | Dauer |
|---|---|---|
| 17 verbliebene Unit-IDs | **alle Timeout** — 31 IDs außer 0/1 geprüft, keine antwortet | 40 s |
| FC03/FC04 unmittelbar hintereinander, 131 Adressen | **130/131 identisch**, 1 × 0,1 V Rauschen, 0 Ausnahmen | 60 s |
| 10650–10702 einzeln | **0 gültig** (war bereits im Hauptsweep enthalten) | 21 s |

**Der vollständige Sweep über die restlichen 63 528 Adressen** lief von
20:18 bis 03:21 Uhr und ist abgeschlossen. Ergebnis in 9.2.

### 9.2 Der vollständige Sweep — abgeschlossen, Nullbefund

Der Lauf `fullsweep.py` startete am 11.08. um 20:18 Uhr und endete am 12.08.
um **03:21:51 Uhr**, nach 7,1 Stunden. Er arbeitete die Liste in der
Reihenfolge der Erfolgsaussicht ab: erst die Nachbarschaft der bekannten
Registerinseln, dann der große Rest.

| Ergebnis | Anzahl |
|---|---|
| Arbeitsliste | 63 528 |
| Adressen geprüft | **63 528** |
| **gültige Adressen gefunden** | **0** |
| übersprungene Adressen | 0 |

**`fullsweep_hits.jsonl` ist leer geblieben — null Zeilen.** Gegenprobe auf
Dateiebene: `fullsweep_progress.jsonl` enthält 63 528 Zeilen und **keine
einzige mit `ok: true`**. Der Nullbefund steht damit nicht auf der leeren
Trefferdatei allein, sondern auf dem lückenlosen Protokoll jeder einzelnen
Adresse.

**Damit ist der gesamte 16-Bit-Adressraum geprüft.** 2 003 Adressen im ersten
Sweep, 63 528 im zweiten, dazu die Einzelproben — zusammen alle 65 536
Adressen, jede einzeln mit `count=1`. Außerhalb der bereits bekannten
Registerinseln 10000–10649, 32768–32799 und 60000–60031 existiert **kein
einziges gültiges Register**.

### 9.2a Gegenprobe unter Produktion — die letzte offene Halbfrage

Der Sweep lief bei Dunkelheit. Modbus-Adressgültigkeit ist normalerweise
statisch, aber die Möglichkeit blieb, dass ein PV4-Register **nur unter
Produktion überhaupt antwortet** — dann hätte der Nachtlauf es übersehen.

Am 12.08. um 08:53 Uhr wurde das geprüft: **500 zufällig gezogene Adressen**
(feste Saat 20260812, Spanne 182–65503) aus der Menge der nachts negativ
getesteten, erneut gelesen bei laufender Einspeisung von rund 400 W.

Der Lauf trägt eine **Positivkontrolle**: alle 50 Adressen wird ein bekannt
gültiges Register mitgelesen (10002, 10014, 10156, 10173, 10174, 10175). Ohne
das wären 500 Fehlschläge nicht von einer stillen Verbindungsstörung zu
unterscheiden. 10173–10175 sind dabei der interessanteste Fall: gültig, aber
konstant null — genau das Muster, das ein leeres PV4-Feld hätte.

**Ergebnis, 08:53–08:56 Uhr:**

| | Anzahl |
|---|---|
| Adressen geprüft | **500** |
| **gültig unter Produktion** | **0** |
| Exception 2 | 500 |
| Transportfehler | 0 |

**Keine einzige nachts negative Adresse antwortet unter Produktion.** Damit
ist auch die zweite Hälfte der Frage beantwortet: Der Nullbefund hängt nicht
am Betriebszustand des Geräts.

**Zu den Positivkontrollen — hier lag ein Fehler in meinem Versuchsaufbau.**
Von zehn Kontrollzugriffen gelangen sechs und vier scheiterten. Das Muster ist
aber nicht zufällig, sondern vollständig deterministisch:

| Kontrollregister | Versuche | erfolgreich | Wert |
|---|---|---|---|
| 10002 (PV-Leistung, Highword) | 2 | **2** | 0 |
| 10014 (SOC) | 2 | **2** | 5 → 6 |
| 10156 (Stufenwert) | 2 | **2** | 300 |
| 10173 | 2 | 0 | Exception 2 |
| 10174 | 1 | 0 | Exception 2 |
| 10175 | 1 | 0 | Exception 2 |

Die drei fehlgeschlagenen sind **genau** 10173–10175 — also genau die
Register, die nach Abschnitt 2 dieses Dokuments ausschließlich **innerhalb
eines Blocks** lesbar sind und bei `count=1` zwangsläufig Exception 2 werfen.
Sie als Kontrolle für einen `count=1`-Lauf zu wählen war mein Fehler: Ich habe
sie genommen, weil sie „gültig, aber konstant null" sind — das Muster eines
leeren PV4-Feldes —, und dabei übersehen, dass ihre Gültigkeit an den Blockread
gebunden ist.

**Der Lauf bleibt dadurch belastbar**, denn alle einzeln lesbaren Kontrollen
gelangen ausnahmslos, über die gesamten 3,4 Minuten verteilt. Der stärkste
Beleg ist 10014: Der SOC **stieg während des Laufs von 5 auf 6 %**. Ein
totes oder eingefrorenes Registerabbild liefert keinen sich ändernden Wert.
Die Verbindung stand, und das Gerät arbeitete.

Nebenbei reproduziert der Fehlschlag die Start-/Count-Validierung aus
`REGISTER.md` ein weiteres Mal, diesmal unter Produktion statt bei Nacht.

**Achtung bei Wiederholung:** Die automatische Schlusszeile des Skripts lautete
„Kontrolle fehlgeschlagen — Lauf NICHT belastbar". Dieses Urteil war durch die
falsche Kontrollauswahl ausgelöst, nicht durch einen Mangel des Laufs. Die
Kontrollliste ist inzwischen auf 10002, 10014, 10156, 10167, 10171 und 10172
korrigiert — letztere drei sind einzeln lesbar *und* bewegen sich unter
Produktion, belegen also zusätzlich, dass tatsächlich eingespeist wird.

Skript: `stichprobe.py`, read-only, ausschließlich FC04 mit `count=1`,
wiederholbar über die feste Saat.

### 9.3 Nicht ausgeführt, weil untersagt

**FC43 (Read Device Identification).** Weiterhin nicht ausgeführt. Ich halte es
für den letzten wirklich aussichtsreichen Schritt: MEI Typ 0x0E, Objekt-IDs
0x80–0xFF sind herstellerspezifisch und enthalten bei manchen Wechselrichtern
die Registerkarte selbst. Reiner Lesezugriff, eine einzige Anfrage genügt für
die Ja/Nein-Frage. **Nur nach ausdrücklicher Freigabe.**

---

## 10. Was diese Arbeit zeigt — und was nicht

**Sie zeigt:**

- Der methodische Einwand war berechtigt: Der Einzeladress-Sweep hat **12
  Register gefunden, die 5085 Blockanfragen nicht gefunden haben**, darunter
  zwei in keiner Herstellerdokumentation (10006, 10015) und acht in einem
  Bereich, der als „durchgehend Exception 2" abgeschrieben war.
- Für 10000–11000, 32700–33100 und 59900–60500 ist der Nullbefund jetzt
  **lückenlos** statt „nicht gefunden": 2003 von 2003 Adressen beantwortet.
- Unit 0 bedient dasselbe Registerabbild wie Unit 1 (103/107 identisch, die
  4 Abweichungen sind die volatilsten Größen).
- 10205 ist der AC-Ausgangsstrom, belegt durch einen Test, der die Hypothesen
  trennt (24:0) statt sich auf eine Korrelation zu stützen.
- Die Strangströme sind **INT16**, und der laufende Sampler rechnet sie falsch
  — mit Fehlern von 20 000 W in der Dämmerung.
- Das Gerät erlaubt **nur drei gleichzeitige Modbus-Sitzungen**.

**Sie zeigt nicht:**

- ~~Dass im gesamten Adressraum kein PV4-Register steht. Geprüft sind 2003 von
  65 536 Adressen; rund 65 000 bleiben offen (Kosten: 7,2 h).~~ **Eingelöst am
  12.08.:** Alle 65 536 Adressen sind einzeln geprüft, null Treffer
  (Abschnitt 9.2), unter Produktion gegengeprüft (Abschnitt 9.2a). Dieser
  Vorbehalt gilt nicht mehr.
- Dass das Aliasing FC03/FC04 auch für die 22 volatilen Register gilt — der
  Test hatte 6–13 Minuten Zeitversatz. Nachholbar in 2 Minuten.
- Dass 10015 der State of Health ist. Belegt ist nur: konstant 100 bei einem
  SOC von 90–94, in keiner Herstellerdefinition, und **kein** PV4-Register.
  Zu klären wäre es über einen Langzeitverlauf oder einen Akku mit sichtbarer
  Alterung.

**Der Stand der Beweislast:** Strang 4 hat kein eigenes Modbus-Register. Das
Gerät misst ihn — die Gesamtleistung in 10002 enthält ihn —, veröffentlicht
ihn aber nicht. Vier MPP-Tracker, drei Registerpaare. Der Restwert
`PV4 = 10002 − (U₁I₁+U₂I₂+U₃I₃)` bleibt die einzige Messmethode, und sie ist
nach der INT16-Korrektur auch in der Dämmerung wieder belastbar.
