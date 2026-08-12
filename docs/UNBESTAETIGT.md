# Registerkatalog — alle beobachteten Werte

Erzeugt aus **464 Messpunkten** des Laufs 2026-08-11T15:28:26Z bis 2026-08-11T19:20:26Z (UTC), Takt 30 s.
Anker SOLIX Solarbank 4 E5000 Pro, Unit-ID 1, Function Code 4, nur lesend.

Zweck: **jeden Registerwert festhalten, der etwas aussagt**, damit ihm später die
richtige Funktion zugewiesen werden kann. Die Spalte *Sicherheit* trennt Belegtes
von Vermutetem. Nichts hier ist geraten — wo die Deutung offen ist, steht das so.

Lowword-Adressen von 32-Bit-Größen sind ausgelassen, sie tragen keine eigene
Bedeutung. Ausführliche Belege stehen in `REGISTER.md`, `PV4.md` und `PV4-SUCHE.md`.

Diese Datei wird von `scratchpad/katalog.py` erzeugt und kann jederzeit mit mehr
Messdaten neu gebaut werden.

---

## 1. Gedeutete Register

| Adresse | jetzt | Bereich | Zustände | Deutung | Sicherheit | Beleg |
|---|---|---|---|---|---|---|
| 10002 | 0 | 0–0 | 1 | PV-Leistung gesamt, INT32, auf 10 W quantisiert | **sicher** | Hersteller-YAML, sekundengenau deckungsgleich mit HA |
| 10008 | 0 | 0–0 | 1 | Batterieleistung, INT32, negativ = laden | **sicher** | Hersteller-YAML |
| 10010 | 0 | 0–0 | 1 | Hauslast, INT32 | **sicher** | Hersteller-YAML |
| 10012 | 65535 | 0–65535 | 2 | Netzleistung, INT32, negativ = Einspeisung | **sicher** | Hersteller-YAML |
| 10014 | 75 | 75–100 | 26 | Ladezustand in Prozent | **sicher** | Hersteller-YAML, HA-Entity |
| 10041 | 19201 | 19201–25601 | 26 | Ladezustand in Prozent, Highbyte | **sicher** | 11 von 11 Stichproben deckungsgleich mit der HA-Recorder-Historie |
| 10060 | 27259 | 27259–27259 | 1 | Geraetezeit, UINT32 Unix-Sekunden UTC | **sicher** | auf 2 s gegen Wanduhr |
| 10064 | 0 | 0–0 | 1 | Betriebsmodus | **sicher** | Hersteller-YAML, deckt sich mit HA-Select |
| 10071 | 65535 | 0–65535 | 2 | Sollwert Batterieleistung, INT32 | **sicher** | Hersteller-YAML - NICHT ANFASSEN, Sollwert der Nulleinspeisung |
| 10130 | 19201 | 19201–25601 | 26 | Ladezustand in Prozent, Highbyte, Duplikat von 10041 | **sicher** | 4 Scanlesungen bei SOC 79/81/93/100 |
| 10156 | 340 | 340–360 | 3 | Stufenwert in 1,0-Schritten | **OFFEN** | Spannungsthese stark geschwaecht: 16 Prozentpunkte SOC-Abfall ohne Regung |
| 10167 | 151 | 58–366 | 103 | Strang 1 Spannung, /10 V | **sicher** | App-Vergleich, Abweichung 0,2 % |
| 10168 | 65535 | 0–65535 | 183 | Strang 1 Strom, /100 A, INT16 | **sicher** | App-Vergleich; wird in der Daemmerung leicht negativ |
| 10169 | 145 | 79–370 | 135 | Strang 2 Spannung, /10 V | **sicher** | App-Vergleich, Abweichung 2,2 % |
| 10170 | 2 | 0–65534 | 203 | Strang 2 Strom, /100 A, INT16 | **sicher** | App-Vergleich |
| 10171 | 143 | 79–374 | 127 | Strang 3 Spannung, /10 V | **sicher** | App-Vergleich, Abweichung 1,8 % |
| 10172 | 4 | 1–65533 | 202 | Strang 3 Strom, /100 A, INT16 | **sicher** | App-Vergleich |
| 10199 | 2392 | 2365–2410 | 46 | Netzspannung Messpunkt A, /10 V | **plausibel** | Wertebereich 240-244 V |
| 10202 | 2392 | 2365–2410 | 46 | Netzspannung Messpunkt B, /10 V | **plausibel** | Wertebereich 240-244 V |
| 10205 | 227 | 142–337 | 146 | AC-Ausgangsstrom, /100 A, INT16 | **sicher** | 24 von 24 Divergenzschritten folgt der AC-Leistung, 0 dem PV4-Restwert |
| 10208 | 0 | 0–0 | 1 | AC-Ausgangsleistung, INT32 | **sicher** | Hersteller-YAML |
| 10213 | 4999 | 4991–5009 | 19 | Netzfrequenz, /100 Hz | **sicher** | 49,94-50,05 Hz; dient als Negativkontrolle fuer Korrelationen |
| 10224 | 2390 | 2364–2410 | 47 | Netzspannung Messpunkt C, /10 V | **plausibel** | Wertebereich 240-244 V |
| 10227 | 2390 | 2364–2410 | 47 | Netzspannung Messpunkt D, /10 V | **plausibel** | Wertebereich 240-244 V |
| 10230 | 17 | 11–41 | 29 | Strom eines gekoppelten Paares, vermutlich /100 A | **OFFEN** | 10236 = 10230 x Netzspannung/1000, Abweichung +0,46 +- 1,78; These Blindstrom |
| 10236 | 43 | 24–99 | 63 | Leistung desselben Paares | **OFFEN** | Verhaeltnis 2,417 blieb bei 20 % Bereichserweiterung exakt erhalten |
| 10238 | 4999 | 4991–5009 | 19 | Netzfrequenz, /100 Hz, Zweitmessung | **sicher** | identischer Verlauf zu 10213 |
| 10250 | 0 | 0–0 | 1 | Nennkapazitaet, UINT32, /10 kWh | **sicher** | 10250/10251 ergibt 5,1 kWh |
| 10252 | 8705 | 8705–9216 | 4 | Highbyte mal 10 ist gleich 10156 | **sicher (nur die Kopplung)** | 311 von 312 Messpunkten; was die Groesse bedeutet, bleibt offen |
| 10256 | 75 | 75–100 | 26 | Ladezustand in Prozent | **sicher** | deckungsgleich mit 10014 |
| 10262 | 0 | 0–0 | 1 | Ladeenergie kumuliert, UINT32, /10 kWh | **sicher** | Hersteller-YAML |
| 10264 | 0 | 0–0 | 1 | Entladeenergie kumuliert, UINT32, /10 kWh | **sicher** | Hersteller-YAML |

---

## 2. Unbestätigt, aber beweglich — die aussichtsreichen Kandidaten

Diese Register **ändern sich** und tragen damit Information. Angegeben ist die
stärkste Korrelation zu einer bekannten Größe, sofern ihr Betrag über 0,7 liegt.

**Warnung zur Deutung:** Über ein Fenster mit monotonem Verlauf korreliert alles
mit allem. Register 10213 (Netzfrequenz) ist die Negativkontrolle — taucht es in
einer Korrelationsliste weit oben auf, ist das Fenster untauglich und die Zahl wertlos.

| Adresse | jetzt | Bereich | Zustände | stärkste Korrelation | Status |
|---|---|---|---|---|---|
| 10234 | 2 | 0–7 | 8 | — | **unbestätigt** |
| 10254 | 65535 | 0–65535 | 2 | — | **unbestätigt** |

---

## 3. Unbestätigt und konstant

Über den gesamten Lauf unveränderlich. Ein konstanter Wert ungleich null ist meist
eine Kennung, ein Grenzwert oder ein Ausstattungsmerkmal.

### Konstant, Wert ungleich null

| Adresse | Wert | hex |
|---|---|---|
| 10040 | 257 | 0x0101 |
| 10112 | 12590 | 0x312E |
| 10113 | 12334 | 0x302E |
| 10114 | 12846 | 0x322E |
| 10115 | 13104 | 0x3330 |
| 10118 | 11825 | 0x2E31 |
| 10119 | 11824 | 0x2E30 |
| 10120 | 11826 | 0x2E32 |
| 10121 | 12339 | 0x3033 |
| 10124 | 18772 | 0x4954 |
| 10125 | 57356 | 0xE00C |
| 10133 | 9480 | 0x2508 |

### Konstant null — 96 Adressen

Gültig lesbar, aber durchgehend null. Entweder unbelegte Reservefelder oder
Funktionen, die diese Anlage nicht besitzt: kein Erweiterungsakku, kein
angeschlossener Smart Meter, keine Fremdanlage.

```
   10042  10043  10044  10045  10046  10047  10048  10049  10050  10051  10052  10053
   10054  10055  10056  10057  10058  10059  10062  10063  10065  10066  10067  10068
   10069  10070  10116  10117  10122  10123  10126  10127  10128  10129  10131  10132
   10134  10135  10136  10137  10138  10139  10140  10141  10142  10143  10144  10145
   10146  10147  10148  10149  10150  10151  10152  10153  10154  10155  10157  10158
   10159  10160  10161  10162  10163  10164  10165  10166  10173  10174  10175  10183
   10187  10210  10211  10212  10214  10215  10216  10217  10218  10219  10220  10221
   10222  10223  10225  10226  10228  10229  10231  10232  10233  10235  10237  10239
```

---

## 4. Wie ein Kandidat bestätigt wird

Drei Hürden, und alle drei müssen genommen werden:

1. **Auflösung.** Ein echter Messwert nimmt über einen Tag viele Zustände an. Die
   bestätigten Strangströme kommen auf 80 bis 161. Ein Register mit weniger als
   etwa 30 Zuständen kann keine feine Messgröße sein, egal wie gut es korreliert.
2. **Negativkontrolle.** Die Korrelation muss sich von der der Netzfrequenz
   absetzen. Korreliert 10213 mit, misst man den Tagestrend und nicht das Register.
3. **Divergenztest.** Es braucht Zeitpunkte, an denen die vermutete Größe und ihre
   Alternative **auseinanderlaufen**. Nur dort trennt sich die Frage. So wurde 10205
   entschieden: In 24 solchen Schritten folgte es 24 mal der AC-Leistung und null
   mal dem PV4-Restwert.
