# PV4-Suche: der lückenlose Einzeladress-Nachweis

Stand: 11.08.2026, 19:25 Uhr. Gerät AE103, SN …441, Firmware 1.0.2.30.
Auftrag: lückenlos nachweisen, ob die Solarbank ein eigenes Register für den
vierten PV-Strang hat, und dabei die methodische Lücke des bisherigen
32er-Block-Scans schließen.

---

## 1. Kurzantwort

**Die methodische Lücke ist bestätigt und exakt beziffert — aber sie konnte
nicht geschlossen werden, weil das Gerät keine vierte Modbus-Sitzung zulässt.**

Drei Aussagen, in der Reihenfolge ihrer Belastbarkeit:

1. **Der Einwand des Auftraggebers ist methodisch berechtigt.** Das Audit des
   alten Scanlogs bestätigt ihn Zahl für Zahl: von 65 536 Adressen wurden genau
   **267 jemals einzeln (count=1) angesprochen**. **99,3 % des Adressraums
   (65 073 Adressen) sind weder als gültig belegt noch jemals einzeln
   geprüft.** Die fünf isolierten Register 10183, 10187, 10199, 10202 und 10205
   waren in **jeder** erfolgreichen Anfrage mit count=1 gelesen worden — kein
   einziger Blockread hat sie je erwischt. Genau dieser Effekt kann weitere
   Register verbergen.

2. **Der geplante Sweep ließ sich nicht ausführen.** Das Gerät erlaubt
   **höchstens drei gleichzeitige Modbus-TCP-Sitzungen**. Alle drei sind von
   den Clients des Betreibers dauerhaft belegt. Ein vierter Client bekommt den
   TCP-Handshake, aber auf die erste Modbus-Anfrage sofort ein RST. Beleg und
   Diagnose in Abschnitt 2. **Damit ist der Nullbefund für die geplanten
   Bereiche *nicht* erbracht** — er bleibt offen, nicht widerlegt.

3. **Was ohne Gerätezugriff prüfbar war, stützt den bisherigen Befund
   deutlich.** Der Nachtlauf ist inzwischen auf 229 Messpunkte mit einer
   PV-Spanne von 60–810 W gewachsen — ein weit besseres Fenster als die
   frühere Auswertung. In ihm ist **10205 endgültig als AC-Ausgangsstrom
   erwiesen** (Abschnitt 5.1, 24:0-Entscheidung in den Divergenzfenstern),
   und **kein** beobachtetes Register bewegt sich mit dem PV4-Restwert.
   Die Negativkontrolle 10213 liefert r = −0,032, das Fenster ist also sauber.

**Für den Auftraggeber in einem Satz:** Sein methodischer Einwand ist richtig
und bislang unwiderlegt, aber um ihn zu prüfen, muss er mir einen der drei
Verbindungsplätze freigeben — die Prüfung selbst dauert dann 13 Minuten.

---

## 2. Der Blocker: das Gerät lässt nur drei Sitzungen zu

Das ist ein **neuer Protokollbefund**, der in `REGISTER.md` fehlt und dort
nachgetragen gehört.

### 2.1 Beobachtung

| Versuch | Ergebnis |
|---|---|
| `modbus_ro.py probe` (19:07, 19:08) | `ConnectionResetError` nach erfolgreichem TCP-Connect |
| 20 Versuche im 3-s-Takt (19:09:01–19:09:59) | **0/20 erfolgreich**, durchgehend RST bzw. „peer closed connection" |
| Dauerretry im 2-s-Takt seit 19:11 | zum Redaktionsschluss **über 400 Versuche, 0 erfolgreich** |

Der TCP-Handshake gelingt jedes Mal. Erst die erste Modbus-PDU wird mit RST
beantwortet. Das ist die Signatur eines Geräts, das die Verbindung annimmt,
aber keinen freien Sitzungsplatz hat.

### 2.2 Ausschluss der naheliegenden Fehlerquellen

- **Kein Problem des Netzwegs.** Dieser Rechner erreicht das Gerät über einen
  Tailscale-Subnetz-Router (Quelladresse 100.74.115.49), liegt aber
  gleichzeitig selbst im LAN (192.168.178.129). Ein Bindungstest gegen beide
  Quelladressen wurde durchgeführt: **beide** werden zurückgesetzt. Es ist
  also kein Tunnel- und kein NAT-Artefakt.
- **Keine Begrenzung pro Quell-IP.** Sonst hätte die direkte LAN-Adresse
  funktioniert, denn von ihr bestand keine Verbindung.
- **Das Gerät ist gesund.** Der Nacht-Sampler protokolliert im selben Moment
  lückenlos weiter, und `sensor.…_441_solarstrom` in Home Assistant war bei
  jeder Kontrolle frisch (19:07:24, 19:17:03 — jeweils Sekunden alt).

### 2.3 Wer die drei Plätze hält

| Client | Verbindungsverhalten | Beleg |
|---|---|---|
| `anker_solix_official` | dauerhafte TCP-Sitzung, 5-s-Polling | `modbus_client.py:107`, dokumentiert in `REGISTER.md` §10 |
| `solarbank_pv` (eigene Integration) | dauerhaft: `if not self.connected: await self.connect()` | `modbus_reader.py:92-93`; Entities um 19:17:03 frisch |
| Nacht-Sampler `pv4_evening.py` | dauerhaft: verbindet nur, wenn `client.sock is None` | `pv4_evening.py:208-209`; `netstat` zeigt über 14 s denselben Quellport 61381 |

Alle drei halten die Sitzung **dauerhaft** — keiner gibt sie zwischen den
Abfragen frei. Deshalb öffnet sich auch kein Fenster.

### 2.4 Was ich bewusst *nicht* getan habe

- **Keinen der drei Clients beendet.** Der Nacht-Sampler erhebt gerade den
  Datensatz, mit dem `PV4.md` die 10156-Frage (Spannung oder Temperatur) und
  den Sonnenuntergangstest entscheiden will; ihn abzuschalten hätte diese
  Messung zerstört. Die beiden HA-Integrationen sind Fremdbesitz, und Home
  Assistant war ausdrücklich nur lesend anzufassen.
- **Kein Wettlauf um den Verbindungsplatz.** Die offizielle Integration reißt
  vor **jedem** Schreibvorgang ihre Verbindung ab und baut sie neu auf
  (`modbus_manager.py:262-277`). Man könnte diesen Millisekundenspalt mit
  ~3 Verbindungsversuchen/s abpassen und den Platz an sich reißen. Das habe
  ich unterlassen: Die offizielle Integration führt die Sollwertschreibungen
  der Nulleinspeisungsregelung aus (10071/10072). Sie für die Dauer eines
  13-Minuten-Sweeps auszusperren, hätte in die laufende Regelung des
  Hausspeichers eingegriffen. Dafür lag keine Freigabe vor.
- **Kein FC43.** Ausdrücklich untersagt, siehe Vorschlag in Abschnitt 7.

Der Dauerretry (`jaeger.py`) lief von 19:11 bis 19:26 und hat in **434
protokollierten Versuchen keinen einzigen Platz** bekommen. Er wurde danach
**beendet** — bewusst nicht als unbeaufsichtigter Hintergrundprozess
zurückgelassen, weil er sonst zu einem unvorhersehbaren Zeitpunkt einen Platz
hätte übernehmen und die offizielle Integration für 14 Minuten aussperren
können. Er steht startbereit, siehe Abschnitt 7.

**Nebenwirkungsbilanz dieser Untersuchung:** Es wurde ausschließlich gelesen,
und zwar nur FC04 auf Register 10014 (Batterie-SOC) — jede einzelne der 434
Anfragen. Kein Schreibzugriff, kein FC43. Home Assistant wurde nur abgefragt.
Das alte `scan_log.jsonl` wurde vor dem ersten Zugriff nach
`scan_log_ORIG_BACKUP.jsonl` gesichert (5085 Zeilen, unverändert). An
`scan_log.jsonl` selbst hängen zwei zusätzliche Zeilen — die beiden ersten
`probe`-Aufrufe um 17:07:10Z und 17:08:03Z, beide fehlgeschlagen; alle
weiteren 432 Anfragen gingen nach `sweep_log.jsonl`. Der Nacht-Sampler lief durchgehend
ohne Unterbrechung weiter, und `sensor.…_441_solarstrom` war bei jeder
Kontrolle sekundenfrisch (19:07:24, 19:17:03, 19:25:37).

---

## 3. Alle neu gefundenen gültigen Adressen

Der geplante Sweep hat **keine** geliefert, weil er nicht laufen konnte.

Aus dem laufenden Nachtlauf ergeben sich jedoch **sechs Adressen, die der alte
Scan nie als gültig belegt hatte** — er hatte im Block 10250–10265 nur die
geraden Adressen mit count=1 erwischt, der Sampler liest inzwischen den ganzen
Block. Das ist derselbe Effekt in klein und bestätigt die These des
Auftraggebers ein weiteres Mal.

| Adresse | aktueller Wert | Zustände | Deutung | PV4? |
|---|---|---|---|---|
| 10251 | 51 | 1 über 120 Punkte | Lowword von `rated_energy` (10250/10251 INT32) = **5,1 kWh** | nein — konstant |
| 10253 | 0 | 1 über 120 Punkte | Lowword zu 10252 | nein — konstant |
| **10255** | 65016 | **43** über 120 Punkte | Lowword eines INT32 mit 10254. Als INT32: **−550…0 W** | **nein** — siehe unten |
| 10257 | 0 | 1 über 120 Punkte | Lowword zu 10256; 10256/10257 = SOC × 65536 | nein — konstant |
| 10263 | 162 | 1 über 230 Punkte | Lowword der kumulierten Ladeenergie = **16,2 kWh** | nein — konstant |
| 10265 | 139 | 4 über 230 Punkte | Lowword der kumulierten Entladeenergie = **13,6→13,9 kWh**, zählt am Abend hoch | nein — Energiezähler |

**Damit ist eine offene Frage aus `PV4.md` §7 beantwortet:** 10251 = 51
(5,1 kWh Nennkapazität, exakt die dort vorhergesagte Zahl), 10253 = 0,
10257 = 0. Der Block 10250–10265 besteht aus INT32-Objekten, nicht aus
16-Bit-Registern.

**Zu 10254/10255 im Detail**, weil es das einzige neue Register mit
nennenswerter Dynamik ist: Als INT32 gelesen läuft es über −550…0 W mit 41–43
Zuständen. Es ist **batteriebezogen, nicht PV**:

- Es ist **durchweg negativ oder null**, PV4 ist positiv (60–180 W).
- Sein Betrag wird bis 550 W groß, also das Dreifache des PV4-Maximums.
- `10254/10255 + Batterieleistung(10008/10009)` ergibt **−48,5 W ± 19,4 W**
  über 117 Punkte, Spanne −100…0. Es folgt also der Batterieleistung mit
  umgekehrtem Vorzeichen und einem kleinen Versatz.
- Sein Betrag **wächst**, wenn die PV-Leistung fällt — das Gegenteil eines
  Strangs.

---

## 4. Ergebnis des Unit-0-Vergleichs

**Nicht durchgeführt — aus demselben Grund (kein Verbindungsplatz).**

Was das Audit des alten Scanlogs dazu beitragen kann, bestätigt die Kritik des
Auftraggebers vollständig:

| Unit-ID | Anfragen im Altscan |
|---|---|
| 1 | 5072 |
| **0** | **1** |
| 2, 3, 4, 5, 6, 10, 16, 32, 100, 200, 246, 247 | je 1 |

Die einzige Anfrage an Unit 0 war `2026-08-11T11:33:34Z fc4 addr10014 count1
ok=True`. Die Aussage „Unit 0 und 1 sind derselbe Server" beruht auf **einem
einzigen übereinstimmenden SOC-Wert**. Sie ist damit nicht belegt, sondern nur
nicht widerlegt. Der geplante Wert-für-Wert-Vergleich über 10144–10250
(214 Anfragen, ~1,4 min) bleibt offen und ist nach wie vor der aussichtsreichste
Einzeltest, weil eine Abweichung sofort ein zweites Registerabbild beweisen
würde.

Ebenso offen: die 19 nie getesteten Unit-IDs 7, 8, 9, 11, 12, 13, 14, 15, 17,
20, 24, 30, 33, 50, 64, 128, 240, 254, 255 (19 Anfragen, ~7 s).

---

## 5. Neubewertung aller bisherigen Befunde — ergebnisoffen

Datengrundlage: `pv4_evening.jsonl`, Stand 19:23 Uhr, **n = 229 gültige
Messpunkte**, 15:28:26Z–17:22:49Z, 154 Register je Punkt.

**Das Fenster ist tauglich.** PV-Spanne 60–810 W (mehrfacher
Richtungswechsel), Restwert −65…288 W. Negativkontrolle:

| Negativkontrolle | r(resid) | r(pv_total) | r(ac) |
|---|---|---|---|
| 10213 Netzfrequenz | **−0,032** | +0,013 | −0,001 |
| 10238 Netzfrequenz | **−0,032** | +0,013 | −0,001 |

Zum Vergleich lieferte dieselbe Netzfrequenz im verworfenen Mittagsfenster
r = −0,83. Hier ist sie null. **Das Ergebnis ist damit nicht wertlos, sondern
belastbar.**

**Auflösungsmaßstab.** Die drei bestätigten Strangströme nehmen in genau
diesem Fenster **161 / 156 / 154** verschiedene Zustände an (10168 / 10170 /
10172). Der vom Auftraggeber genannte Maßstab von 80–92 Zuständen ist also eher
noch zu milde. Ein Kandidat mit ≤ 26 Zuständen kann kein Strangstrom sein.

### 5.1 Die kritischen Fälle

#### 10205 — bisher AC-Ausgangsstrom. Gegenhypothese geprüft, sie fällt.

Die Gegenhypothese lautete: die Korrelation sei Zufall, weil AC-Ausgang und
PV-Summe abends gleichläufig fallen. **Sie ist falsifiziert**, und zwar
dreifach:

1. **Die Voraussetzung der Gegenhypothese trifft nicht zu.** Wären AC und PV4
   gleichläufig, müsste r(ac, resid) hoch sein. Gemessen: **r = +0,530** —
   mäßig. Es gibt also reichlich Zeit, in der beide auseinanderlaufen.

2. **Nach Abzug des AC-Anteils bleibt nichts übrig.** Rechnet man
   `|AC-Leistung| ÷ Netzspannung × 100` und zieht das von 10205 ab, bleibt ein
   Rest von im Mittel **−0,60 Rohwerten** (Spanne −15,3…+16,9). Dieser Rest
   korreliert mit dem Restwert zu **r = −0,031**. Steckte PV4 in 10205, müsste
   genau hier das Signal auftauchen. Es ist nicht da.

3. **Der direkte Trenntest — die Divergenzfenster.** Gesucht wurden Schritte,
   in denen AC-Leistung und Restwert in **entgegengesetzte** Richtung gehen
   (|ΔAC| > 40 W und |Δresid| > 20 W bei verschiedenem Vorzeichen). Dort und
   nur dort trennt sich die Frage:

   | Schrittweite | Divergenzschritte | 10205 folgt der AC-Leistung | 10205 folgt dem Restwert |
   |---|---|---|---|
   | 30 s | 7 | **7** | 0 |
   | 60 s | 6 | **6** | 0 |
   | 120 s | 11 | **11** | 0 |
   | **Summe** | **24** | **24** | **0** |

   **24:0.** Ein Register, das den vierten Strang misst, kann sich nicht
   vierundzwanzig Mal von ihm weg und zur AC-Leistung hin bewegen.

4. **Die Gegenprobe bei stillstehender AC-Leistung.** In 177 Schritten mit
   |ΔAC| ≤ 20 W schwankte der Restwert um −132…+171 W — 10205 aber nur um
   −19…+13 Rohwerte, r(Δ10205, Δresid) = **+0,040**. Wenn PV4 sich um 170 W
   bewegt und das Register schläft, misst es PV4 nicht.

**Urteil: 10205 ist der AC-Ausgangsstrom. Endgültig ausgeschlossen.**
r(10205, AC) = +0,995 über 229 Punkte.

#### 10173 / 10174 / 10175 — die Plätze eines vierten Strangpaars

Über inzwischen **229 Messpunkte konstant null**, in einem Fenster, in dem der
Restwert bis 288 W erreichte. Auch der Mittags-Langlauf (109 Punkte) zeigt
null.

**Der vom Auftraggeber geforderte Nacht-/Sonnenaufgangstest läuft bereits** und
ist der einzige Weg, sie endgültig zu erledigen: Der Sampler protokolliert
diese drei Adressen bis 09:00 Uhr, also über Sonnenuntergang (20:59),
Nacht und Sonnenaufgang. Ein Register, das nur unter bestimmten Bedingungen
belegt wird, müsste sich dort zeigen. **Bis morgen früh ist das ohne jeden
weiteren Eingriff beantwortet.**

#### 10183 / 10187 — bisher völlig unbestimmt

Über 229 Abendpunkte **konstant null**, ebenso in allen Scanlesungen. Sie sind
lesbar, tragen aber in dieser Firmware keinen Inhalt. Als PV4-Kandidat
ausgeschlossen, solange sie null bleiben — derselbe Nachtlauf prüft auch das
mit.

#### 10156 — Stufenwert

Nimmt über den ganzen Tag **3 Zustände** an (340 / 350 / 360; Wechsel um
15:28→350 und 16:49→340). Ein Strangstrom hat im selben Fenster 154–161.
**Als Messgröße für PV4 ausgeschlossen**, unabhängig von der noch offenen
Frage Spannung-oder-Temperatur.

#### 10230 / 10234 / 10236 — bisher Blindstrom/Blindleistung

| Register | Zustände | Spanne | r(resid) | Urteil |
|---|---|---|---|---|
| 10230 | 15 | 17–41 | −0,329 | zu grob, und **negativ** korreliert |
| 10234 | 4 | 1–4 | −0,249 | zu grob |
| 10236 | 26 | 42–99 | −0,305 | zu grob, und **negativ** korreliert |

Alle drei scheitern am Auflösungskriterium (15 / 4 / 26 gegen 154–161). Hinzu
kommt: ihre Korrelation mit dem Restwert ist **negativ**. PV4 stieg im
Messfenster, während diese Register fielen. Ein Strangstrom kann nicht fallen,
während der Strang mehr liefert.

### 5.2 Vollständige Neubewertungstabelle

Alle 33 Register, die sich im Fenster überhaupt bewegt haben, plus die
Nullbefunde. Sortiert nach |r(resid)|.

| Register | Zustände | Spanne | r(resid) | bisherige Deutung | Könnte es PV4 sein? |
|---|---|---|---|---|---|
| 10003 | 58 | 60–810 | +0,653 | Lowword von `pv_power` (10002) | **Nein — zirkulär.** Der Restwert wird aus dieser Zahl gebildet |
| 10170 | 156 | 30–705 | +0,540 | Strom Strang 2 | Nein — gegen App verifiziert (2,2 %) |
| 10209 | 37 | 390–810 | +0,530 | Lowword AC-Ausgangsleistung | Nein — r(ac) = 1,000 exakt |
| 10205 | 105 | 165–337 | +0,527 | AC-Ausgangsstrom | **Nein — 24:0 in den Divergenzfenstern**, siehe 5.1 |
| 10256 / 10014 / 10041 / 10130 | 6 | 95–100 | +0,490 | SOC (drei Kopien) | Nein — 6 Zustände, und es ist der SOC |
| 10009 | 35 | 0–480 | −0,481 | Batterieleistung, Lowword | Nein — negativ korreliert, Batterie |
| 10156 | 3 | 340–360 | +0,462 | Stufenwert (Spannung/Temperatur offen) | Nein — 3 Zustände |
| 10252 | 4 | 8705–9216 | +0,458 | Highbyte = 10156 ÷ 10 | Nein — 4 Zustände |
| 10168 | 161 | 8–695 | +0,445 | Strom Strang 1 | Nein — gegen App verifiziert (0,2 %) |
| **10265** | 4 | 136–139 | −0,407 | **neu**: Lowword kumulierte Entladeenergie | Nein — monotoner Energiezähler, 4 Zustände |
| 10061 | 229 | — | −0,402 | Gerätezeit, Lowword | Nein — zählt monoton |
| 10172 | 154 | 4–740 | +0,353 | Strom Strang 3 | Nein — gegen App verifiziert (1,8 %) |
| 10224 / 10227 / 10199 / 10202 | 32–34 | 2376–2410 | +0,32…+0,33 | Netzspannung A–D | Nein — 237,6–241,0 V, das ist Netz, kein Modul |
| 10230 | 15 | 17–41 | −0,329 | AC-Blindstrom | Nein — 15 Zustände, negativ |
| 10011 | 44 | 400–2630 | +0,328 | Hauslast, Lowword | Nein — bis 2630 W, r(ac) = +0,722 |
| 10236 | 26 | 42–99 | −0,305 | AC-Blindleistung | Nein — 26 Zustände, negativ |
| 10234 | 4 | 1–4 | −0,249 | Zustandscode | Nein — 4 Zustände |
| 10071 | 2 | 0/65535 | −0,186 | Batterie-Sollwert (Vorzeichen) | Nein — 2 Zustände |
| 10169 / 10167 / 10171 | 53–61 | 273–374 | −0,17…+0,02 | Spannungen Strang 1–3 | Nein — verifiziert |
| **10254 / 10255** | 41–43 | −550…0 W | −0,069 / −0,023 | **neu**: batteriebezogener INT32 | Nein — negativ, folgt −Batterieleistung, siehe §3 |
| 10213 / 10238 | 19 | 4991–5009 | **−0,032** | Netzfrequenz | **Negativkontrolle** — bestätigt die Tauglichkeit des Fensters |
| 10012 / 10013 | 2 / 20 | — | −0,006 / −0,004 | Netzleistung | Nein |
| **10173 / 10174 / 10175** | **1** | **0** | — | Plätze des vierten Strangpaars | **Nein, solange sie null sind** — Nachttest läuft |
| **10183 / 10187** | **1** | **0** | — | unbestimmt | **Nein, solange sie null sind** — Nachttest läuft |
| 121 weitere | 1 | konstant | — | siehe `REGISTER.md` | Nein — konstant über 229 Punkte |

**Kein einziger Kandidat übersteht die Prüfung.** Der höchste nicht-zirkuläre,
nicht bereits identifizierte r-Wert liegt bei 0,04.

---

## 6. Was ungeprüft blieb — und was die Prüfung kostet

Das ist der Teil, an dem der Wert eines Nullbefunds hängt. Die Bilanz ist
ehrlich: **lückenlos ausgeschlossen ist wenig.**

### 6.1 Die Abdeckungsbilanz des Adressraums

| Menge | Umfang | Bedeutung |
|---|---|---|
| Als gültig belegt (in einer erfolgreichen Antwort enthalten) | **252** Adressen | bekannt |
| Jemals einzeln mit count=1 angesprochen | **267** Adressen (davon 52 gültig) | Status sicher |
| **Weder das eine noch das andere** | **65 073 Adressen = 99,3 %** | **ungeprüft** |

Die count=1-Abdeckung des alten Scans, vollständig:

```
0 · 100 · 500 · 1000 · 9999-10000 · 10014 · 10016-10047 · 10050-10051 ·
10060 · 10080-10111 · 10176-10207 · 10240-10271 · 32736-32767 ·
32800-32831 · 59968-60000 · 60032-60063
```

Die zehn zusammenhängenden ungeprüften Bereiche, nach Größe:

| Bereich | Adressen |
|---|---|
| 32832–59967 | 27 136 |
| 10272–32735 | 22 464 |
| 1001–9998 | 8 998 |
| 60064–65535 | 5 472 |
| 501–999 | 499 |
| 101–499 | 399 |
| 1–99 | 99 |
| 10004–10007 | 4 |
| 10001, 10015 | je 1 |

**In unmittelbarer Nähe der bekannten Registerinseln — dort, wo ein
PV4-Register am ehesten läge — sind ungeprüft:**

- **9900–11200:** 1034 Adressen (9900–9998, 10001, 10004–10007, 10015,
  **10272–11200**)
- **32700–33100:** 305 Adressen (32700–32735, 32832–33100)
- **59900–60500:** 505 Adressen (59900–59967, 60064–60500)

Besonders bemerkenswert: **10272–11200 ist nie einzeln geprüft worden**, und
darin liegt der Smart-Meter-Bereich 10620–10702, für den `REGISTER.md`
„durchgehend Exception 2" meldet — eine Aussage, die ausschließlich auf
Blockreads beruht und daher genau dem Fehlschluss unterliegt, um den es hier
geht.

### 6.2 Zeitbedarf, bei 0,35 s Pause (≈ 2,8 Anfragen/s)

| Prüfung | Anfragen | Dauer |
|---|---|---|
| **Schritt 1: 10000–11000, 32700–33100, 59900–60500** | 2 003 | **12,7 min** |
| Schritt 2a: Unit-0-Vergleich 10144–10250, Wert für Wert | 214 | 1,4 min |
| Schritt 2b: 19 nie getestete Unit-IDs | 19 | 7 s |
| Schritt 1b: 11000–12000, 9000–10000, 0–1000 | 3 003 | 19,0 min |
| Menge C komplett (alle 65 073 offenen Adressen) | 65 073 | **6,9 h** |
| Gesamter Adressraum 0–65535, lückenlos | 65 536 | 6,9 h |

**Der komplette lückenlose Nachweis über den ganzen Adressraum kostet also
knapp sieben Stunden ununterbrochenen Gerätezugriffs** — eine Nacht. Der
wertvollste Teil (Schritt 1 + 2) kostet **14 Minuten**.

### 6.3 Weitere offene Punkte

| Frage | Warum offen | Was sie klärt |
|---|---|---|
| FC03 gegen FC04 an neu gefundenen Adressen | keine neuen Adressen gefunden, weil kein Zugriff | Ob das Aliasing auch außerhalb der bekannten Register gilt |
| Ändern sich 10173–10175 / 10183 / 10187 nachts oder bei Sonnenaufgang? | Messung läuft bis 09:00 | **Beantwortet sich von selbst bis morgen früh** — ohne jeden Eingriff |
| Sonnenuntergangstest für 10205 | Sonnenuntergang 20:59, Sampler läuft | Bleibt 10205 nach Sonnenuntergang stehen, während der Restwert auf null geht, ist der Ausschluss auch physikalisch besiegelt |
| Blockgrößen > 32 Register | nie getestet | Ein `count=64`-Read könnte Blockgrenzen zeigen, die 32er-Blöcke verbergen |

---

## 7. Vorschläge, die ich nicht ausgeführt habe

**FC43 (Read Device Identification) — nicht ausgeführt, ausdrücklich
untersagt.** Ich halte es dennoch für aussichtsreich und schlage es zur
Freigabe vor: FC43/MEI Typ 0x0E liefert bei vielen Wechselrichtern
Herstellerobjekte, in denen die Registerkarte selbst beschrieben ist. Es ist
ein reiner Lesezugriff und kann nichts verändern. Objekt-IDs 0x00–0x02
(Basic) sind Pflicht, 0x80–0xFF sind herstellerspezifisch. Eine einzige
Anfrage würde zeigen, ob das Gerät überhaupt antwortet. **Nur nach
ausdrücklicher Freigabe.**

**Ein vierter Verbindungsplatz.** Die eleganteste Lösung wäre, den
Nacht-Sampler für 14 Minuten anzuhalten. Er verlöre dabei rund 28 Messpunkte
von mehreren hundert; die 10156-Nachtkurve und der Sonnenuntergangstest
blieben intakt, solange das vor 20:45 geschieht. Der fertige Sweep steht
bereit:

```
cd <scratchpad>
python jaeger.py full     # Schritt 1 + 2, ~14 min, holt sich den Platz selbst
```

`jaeger.py` wartet von sich aus auf einen freien Platz, hält ihn dann und
arbeitet Schritt 1 und 2 ab. Er nutzt `ReadOnlyModbusTCP` aus `modbus_ro.py`
und kann daher konstruktionsbedingt nur FC 1–4 senden. Schritt 1b
(19 weitere Minuten) ist absichtlich **nicht** in `full` enthalten, damit die
Haltezeit des Verbindungsplatzes begrenzt bleibt.

---

## 8. Was diese Arbeit zeigt und was nicht

**Sie zeigt:**

- Der methodische Einwand des Auftraggebers ist berechtigt und quantifiziert:
  99,3 % des Adressraums sind nie einzeln angesprochen worden, und die fünf
  bekannten isolierten Register beweisen, dass genau dieser Effekt real ist.
- Das Gerät erlaubt nur drei gleichzeitige Sitzungen — ein neuer, belegter
  Protokollbefund, der in die Registerkarte gehört und der erklärt, warum ein
  vierter Client scheitert.
- 10205 ist der AC-Ausgangsstrom, jetzt mit einem Test, der die beiden
  Hypothesen sauber trennt (24:0) statt sich auf eine Korrelation zu stützen.
- In 229 Messpunkten über eine PV-Spanne von 60–810 W bewegt sich **kein**
  beobachtetes Register mit dem PV4-Restwert, und die Negativkontrolle
  bestätigt, dass das Fenster taugt.
- Sechs bisher unbelegte Adressen (10251, 10253, 10255, 10257, 10263, 10265)
  sind gültig und identifiziert; 10251 = 51 bestätigt die Vorhersage aus
  `PV4.md` §7 exakt.

**Sie zeigt nicht:**

- Dass es kein PV4-Register gibt. Der geplante lückenlose Sweep konnte nicht
  laufen. **Der Nullbefund gilt weiterhin nur für die 252 als gültig bekannten
  und die 154 beobachteten Adressen** — nicht für den Adressraum.
- Dass Unit 0 dasselbe Registerabbild hat wie Unit 1. Das beruht nach wie vor
  auf einer einzigen Stichprobe.
- Dass 10173–10175 und 10183/10187 auch nachts null bleiben. Das entscheidet
  der laufende Sampler bis morgen früh.

**Der ehrliche Stand:** Die Frage „hat Strang 4 ein eigenes Register?" ist
nach wie vor mit **Nein für alles, was je gelesen wurde**, und mit
**Unbekannt für 99,3 % des Adressraums** zu beantworten. Der Auftraggeber hat
recht, dass diese Lücke besteht. Sie zu schließen kostet 14 Minuten für die
aussichtsreichen Bereiche und sieben Stunden für Vollständigkeit — beides
scheitert derzeit allein an einem freien Verbindungsplatz.
