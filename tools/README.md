# Messwerkzeuge der Registersuche

Diese Skripte haben die Befunde in `docs/PV4.md`, `docs/PV4-SUCHE.md`,
`docs/REGISTER.md` und `docs/UNBESTAETIGT.md` erzeugt. Sie lagen bis zum
12.08.2026 ausschließlich in einem Temp-Verzeichnis und wären mit dessen
Aufräumen verlorengegangen — zusammen mit der Wiederholbarkeit, die die
Dokumente zusichern. Deshalb liegen sie jetzt hier.

**Alle Zugriffe sind ausschließlich lesend.** `modbus_ro.py` kann das
konstruktionsbedingt nicht anders: `_request` wirft bei allem außer den
Funktionscodes 1 bis 4. Kein FC43, kein Schreibzugriff, keine Registeränderung.

## Voraussetzung

Das Gerät erlaubt **nur drei gleichzeitige Modbus-Sitzungen** (Beleg:
`docs/PV4-SUCHE.md` §7.1). Laufen die offizielle Anker-Integration,
`solarbank_pv` und ein Sampler, ist kein Platz mehr frei. `jaeger_lib.acquire()`
wartet dann, bis einer aufgibt — oder man deaktiviert `solarbank_pv`
vorübergehend in Home Assistant.

Die Geräteadresse steht in `jaeger_lib.py` (`HOST`).

## Die Dateien

| Datei | Zweck |
|---|---|
| `modbus_ro.py` | Read-only-Modbus-TCP-Client. Basis für alles Weitere |
| `jaeger_lib.py` | Verbindungsbeschaffung und Lesehilfe. Behandelt einen Timeout korrekt als gültige Antwort („antwortet nicht") statt als Verbindungsverlust |
| `fullsweep.py` | Einzeladress-Sweep über den Adressraum, wiederaufnahmefähig. Hat den Nullbefund erzeugt |
| `stichprobe.py` | Gegenprobe: zieht nachts negativ getestete Adressen und prüft sie unter Produktion erneut |
| `pv4_evening.py` | Messlauf über einen festen Registersatz, schreibt die Zeitreihe |
| `katalog.py` | Baut `docs/UNBESTAETIGT.md` aus der Zeitreihe neu |

## Datenformate

Die Läufe schreiben JSON Lines, eine Zeile je Ereignis. Zeitstempel sind
durchgehend ISO-8601 in UTC im Format `%Y-%m-%dT%H:%M:%SZ`. Synthetische
Beispielzeilen:

```jsonc
// fullsweep_progress.jsonl — eine Zeile je geprüfter Adresse
{"i": 0, "a": 11001, "exc": 2}                    // Modbus-Ausnahme
{"i": 1, "a": 11002, "ok": true, "v": 0}          // gültige Adresse
{"i": 2, "a": 11003, "err": "ConnectionReset"}    // Transportfehler

// fullsweep_hits.jsonl — nur Treffer
{"addr": 12345, "value": 0, "t": "2026-01-01T00:00:00Z"}

// stichprobe_result.jsonl — Probe und Positivkontrolle getrennt
{"kind": "probe",   "addr": 12345, "exc": 2}
{"kind": "control", "addr": 10002, "ok": true, "v": 0}

// pv4_evening.jsonl — ein Messpunkt je Zeile
{"t": "2026-01-01T00:00:00Z", "ok": true, "err": null, "pv_total": 0.0,
 "pv1": 0.0, "pv2": 0.0, "pv3": 0.0, "resid": 0.0, "regs": {"10167": 0}}
```

## Zwei Fallstricke, die Ergebnisse verfälscht haben

**Die Strangströme sind INT16, nicht UINT16** — im Skript behoben, in alten
Daten nicht. `pv4_evening.py` rechnete 10167–10172 zunächst vorzeichenlos und
produzierte dadurch in der Dämmerung Leistungen von +20 000 W und Restwerte
von −20 000 W. `derive()` verwendet inzwischen `to_int16()`, der Fehler ist
also raus (Commit `d6dabb4`).

**Aber:** Jede `pv4_evening.jsonl` aus einem Lauf **vor** dieser Korrektur
enthält die falschen Werte weiterhin, denn `resid` wird beim Schreiben
gerechnet, nicht beim Lesen. Wer solche Altdaten auswertet, muss Punkte mit
`|resid| > 1000` verwerfen oder aus `regs` neu rechnen. Belegt in
`docs/PV4-SUCHE.md` §7.2.

**Positivkontrollen müssen einzeln lesbar sein.** Das Gerät validiert die
Kombination aus Startadresse und Count, nicht jede Adresse für sich. 10173–10175
sind gültig, aber **nur innerhalb eines Blocks** — bei `count=1` werfen sie
zwangsläufig Exception 2. Als Kontrolle für einen `count=1`-Lauf sind sie
untauglich; das ist im Lauf vom 12.08. 08:53 Uhr genau so passiert
(`docs/PV4-SUCHE.md` §9.2a). Taugliche Kontrollen: 10002, 10014, 10156, 10167,
10171, 10172.
