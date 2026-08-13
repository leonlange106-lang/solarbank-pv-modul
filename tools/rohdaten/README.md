# Rohdaten der Registererschliessung

Diese Dateien sind die Belege hinter `docs/REGISTER.md` und
`docs/UNBESTAETIGT.md`. Sie lagen bis zum 13.08.2026 ausschliesslich in einem
temporaeren Job-Verzeichnis (`.claude/jobs/67707425/tmp/`) und waeren beim
naechsten Aufraeumen verloren gewesen. Der Code ist reproduzierbar, diese
Messreihen nicht - das Geraet laesst sich nicht in einen frueheren Zustand
zuruecksetzen.

| Datei | Inhalt |
|---|---|
| `pv4_tag.jsonl` | Tageslauf 12.08., voller Registersatz je Messpunkt, mit vorberechnetem `resid` (Strang 4 als Differenz) |
| `fullsweep_progress.jsonl` | Adressraumscan 0-65535, je Adresse Ergebnis oder Exception-Code |
| `raw_log.jsonl` | Request/Response-Paare des Scans |
| `abc_result.jsonl` | Auswertungslauf A/B/C |
| `d_fc43.jsonl` | Vergleich FC03 gegen FC04, Grundlage des Aliasing-Befunds |
| `sweep_log.jsonl` | Sweep 12.08. vormittags (64 KB, vollstaendiger als die frueher eingecheckte 39-KB-Fassung) |
| `sweep_log_mb125.jsonl` | Sweep aus dem Nebenlauf mb125 |
| `stichprobe_result.jsonl` | Stichprobe zur Deutungspruefung |
| `rest10.jsonl` | Restliche Einzeladressen |

## Format

`pv4_tag.jsonl` - eine Zeile je Messpunkt:

```json
{"t": "ISO-8601 UTC", "ok": true, "err": null,
 "pv_total": 680.0, "pv1": 162.5, "pv2": 167.5, "pv3": 170.1, "resid": 179.9,
 "regs": {"10002": 0, "10003": 680, "...": 0}}
```

`regs` enthaelt Rohwerte je Registeradresse, ungeskaliert und ohne Deutung.
`resid` ist `pv_total` minus der Summe der drei gemessenen Straenge.

`fullsweep_progress.jsonl` - eine Zeile je gepruefter Adresse:

```json
{"i": 0, "a": 11001, "exc": 2}
```

`exc` ist der Modbus-Exception-Code, `null` bei Erfolg.

## Zwei Deutungen, die sich hier unabhaengig belegen lassen

Beide wurden am 13.08. im laufenden Betrieb gefunden und lassen sich in der
ersten Zeile von `pv4_tag.jsonl` gegenpruefen:

- `10250: 0, 10251: 51` - die Nennkapazitaet ist ein UINT32 ueber beide
  Register, 51 * 0,1 = 5,1 kWh. Als UINT16 auf 10250 gelesen ergibt sich 0.
- `10252: 7682` - Highbyte 30, mal 10 sind 300, und `10156` steht exakt auf
  300. Bei /10 sind das 30,0 Grad C.

## Wofuer diese Daten weiterhin taugen

- **Verschattungsprofil (Teil 7.6):** `pv4_tag.jsonl` enthaelt den Tagesverlauf
  aller vier Straenge. Zusammen mit dem Sonnenstand laesst sich daraus die
  Schattenkante rekonstruieren, ohne vier Wochen neu zu messen.
- **Nachpruefung von Deutungen:** Jede spaetere These zu einem unbestimmten
  Register kann gegen den gespeicherten Tagesverlauf geprueft werden, statt
  auf neue Messungen zu warten.
