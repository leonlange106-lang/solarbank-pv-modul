"""Erzeugt docs/UNBESTAETIGT.md aus den Messdaten.

Zweck: jeden Registerwert festhalten, der etwas aussagt, damit ihm spaeter die
richtige Funktion zugewiesen werden kann. Trennt Belegtes von Vermutetem und
gibt fuer jeden beweglichen Kandidaten die staerkste Korrelation zu einer
bekannten Groesse an.

Wiederholbar: einfach erneut laufen lassen, wenn mehr Messpunkte vorliegen.
"""
from __future__ import annotations

import json
import pathlib
import statistics as st

QUELLE = pathlib.Path(__file__).parent / "pv4_evening.jsonl"
ZIEL = pathlib.Path(r"C:/Users/User/solarbank-pv-modul/docs/UNBESTAETIGT.md")


def _pfade() -> tuple[pathlib.Path, pathlib.Path]:
    """Quelle und Ziel, per Kommandozeile ueberschreibbar.

    Ohne Argumente bleibt es beim bisherigen Verhalten. Mit Argumenten laesst
    sich der Katalog aus einem anderen Messlauf bauen, ohne das committete
    Dokument zu ueberschreiben - noetig, um zwei Betriebsregime (Laden gegen
    Entladen) nebeneinander zu vergleichen.
    """
    import argparse

    ap = argparse.ArgumentParser(description="Registerkatalog bauen")
    ap.add_argument("--quelle", default=str(QUELLE), help="jsonl des Messlaufs")
    ap.add_argument("--ziel", default=str(ZIEL), help="Markdown-Ausgabe")
    a = ap.parse_args()
    return pathlib.Path(a.quelle), pathlib.Path(a.ziel)


def i32(regs: dict, addr: int) -> int | None:
    hi, lo = regs.get(str(addr)), regs.get(str(addr + 1))
    if hi is None or lo is None:
        return None
    v = ((hi & 0xFFFF) << 16) | (lo & 0xFFFF)
    return v - 0x100000000 if v & 0x80000000 else v


def corr(x: list, y: list) -> float | None:
    paare = [(a, b) for a, b in zip(x, y) if a is not None and b is not None]
    if len(paare) < 10:
        return None
    xs, ys = zip(*paare)
    mx, my = st.mean(xs), st.mean(ys)
    num = sum((a - mx) * (b - my) for a, b in paare)
    den = (sum((a - mx) ** 2 for a in xs) * sum((b - my) ** 2 for b in ys)) ** 0.5
    return num / den if den else None


# Deutung, Sicherheit, Beleg. Nur was belegt ist steht hier drin.
BEKANNT = {
    10001: ("battery_status", "sicher", "Hersteller-YAML, Wertetabelle 0-3"),
    10002: ("PV-Leistung gesamt, INT32, auf 10 W quantisiert", "sicher",
            "Hersteller-YAML, sekundengenau deckungsgleich mit HA"),
    10004: ("third_party_pv_power, INT32", "sicher", "Hersteller-YAML"),
    10008: ("Batterieleistung, INT32, negativ = laden", "sicher", "Hersteller-YAML"),
    10010: ("Hauslast, INT32", "sicher", "Hersteller-YAML"),
    10012: ("Netzleistung, INT32, negativ = Einspeisung", "sicher", "Hersteller-YAML"),
    10014: ("Ladezustand in Prozent", "sicher", "Hersteller-YAML, HA-Entity"),
    10015: ("Kandidat State of Health", "unbestaetigt",
            "in keiner Hersteller-YAML; liest 100 waehrend SOC 90-94"),
    10018: ("PV-Gesamtertrag, UINT32, /10 kWh", "sicher", "Hersteller-YAML"),
    10036: ("maximale Ladeleistung, INT32", "sicher", "Hersteller-YAML, gelesen 3000 W"),
    10038: ("AC-Ausgangslimit, INT32", "sicher",
            "Hersteller-YAML, deckt sich mit dem in der App gesetzten Limit"),
    10041: ("Ladezustand in Prozent, Highbyte", "sicher",
            "11 von 11 Stichproben deckungsgleich mit der HA-Recorder-Historie"),
    10060: ("Geraetezeit, UINT32 Unix-Sekunden UTC", "sicher", "auf 2 s gegen Wanduhr"),
    10064: ("Betriebsmodus", "sicher", "Hersteller-YAML, deckt sich mit HA-Select"),
    10071: ("Sollwert Batterieleistung, INT32", "sicher",
            "Hersteller-YAML - NICHT ANFASSEN, Sollwert der Nulleinspeisung"),
    10130: ("Ladezustand in Prozent, Highbyte, Duplikat von 10041", "sicher",
            "4 Scanlesungen bei SOC 79/81/93/100"),
    10156: ("Stufenwert in 1,0-Schritten", "OFFEN",
            "Spannungsthese stark geschwaecht: 16 Prozentpunkte SOC-Abfall ohne Regung"),
    10167: ("Strang 1 Spannung, /10 V", "sicher", "App-Vergleich, Abweichung 0,2 %"),
    10168: ("Strang 1 Strom, /100 A, INT16", "sicher",
            "App-Vergleich; wird in der Daemmerung leicht negativ"),
    10169: ("Strang 2 Spannung, /10 V", "sicher", "App-Vergleich, Abweichung 2,2 %"),
    10170: ("Strang 2 Strom, /100 A, INT16", "sicher", "App-Vergleich"),
    10171: ("Strang 3 Spannung, /10 V", "sicher", "App-Vergleich, Abweichung 1,8 %"),
    10172: ("Strang 3 Strom, /100 A, INT16", "sicher", "App-Vergleich"),
    10199: ("Netzspannung Messpunkt A, /10 V", "plausibel", "Wertebereich 240-244 V"),
    10202: ("Netzspannung Messpunkt B, /10 V", "plausibel", "Wertebereich 240-244 V"),
    10205: ("AC-Ausgangsstrom, /100 A, INT16", "sicher",
            "24 von 24 Divergenzschritten folgt der AC-Leistung, 0 dem PV4-Restwert"),
    10208: ("AC-Ausgangsleistung, INT32", "sicher", "Hersteller-YAML"),
    10213: ("Netzfrequenz, /100 Hz", "sicher",
            "49,94-50,05 Hz; dient als Negativkontrolle fuer Korrelationen"),
    10224: ("Netzspannung Messpunkt C, /10 V", "plausibel", "Wertebereich 240-244 V"),
    10227: ("Netzspannung Messpunkt D, /10 V", "plausibel", "Wertebereich 240-244 V"),
    10230: ("Strom eines gekoppelten Paares, vermutlich /100 A", "OFFEN",
            "10236 = 10230 x Netzspannung/1000, Abweichung +0,46 +- 1,78; These Blindstrom"),
    10236: ("Leistung desselben Paares", "OFFEN",
            "Verhaeltnis 2,417 blieb bei 20 % Bereichserweiterung exakt erhalten"),
    10238: ("Netzfrequenz, /100 Hz, Zweitmessung", "sicher", "identischer Verlauf zu 10213"),
    10250: ("Nennkapazitaet, UINT32, /10 kWh", "sicher", "10250/10251 ergibt 5,1 kWh"),
    10252: ("Highbyte mal 10 ist gleich 10156", "sicher (nur die Kopplung)",
            "311 von 312 Messpunkten; was die Groesse bedeutet, bleibt offen"),
    10256: ("Ladezustand in Prozent", "sicher", "deckungsgleich mit 10014"),
    10262: ("Ladeenergie kumuliert, UINT32, /10 kWh", "sicher", "Hersteller-YAML"),
    10264: ("Entladeenergie kumuliert, UINT32, /10 kWh", "sicher", "Hersteller-YAML"),
}

# Lowwords von 32-Bit-Groessen - tragen keine eigene Bedeutung.
LOWWORD = {10003, 10005, 10009, 10011, 10013, 10019, 10037, 10039, 10061,
           10072, 10209, 10251, 10253, 10255, 10257, 10263, 10265}


def main() -> None:
    quelle, ziel = _pfade()
    rows = []
    for line in quelle.open(encoding="utf-8"):
        if not line.strip():
            continue
        r = json.loads(line)
        if r.get("ok") and r.get("regs"):
            rows.append(r)
    print(f"{len(rows)} Messpunkte geladen")

    ref = {
        "PV gesamt": [i32(r["regs"], 10002) for r in rows],
        "Batterie": [i32(r["regs"], 10008) for r in rows],
        "SOC": [r["regs"].get("10014") for r in rows],
        "AC out": [i32(r["regs"], 10208) for r in rows],
        "Zeit": list(range(len(rows))),
    }

    adressen = sorted({int(a) for r in rows for a in r["regs"]})
    bek, var, konst = [], [], []

    for a in adressen:
        werte = [r["regs"][str(a)] for r in rows if str(a) in r["regs"]]
        if not werte:
            continue
        n, lo, hi, jetzt = len(set(werte)), min(werte), max(werte), werte[-1]

        korr = ""
        if n > 3:
            cs = [(k, corr(werte, ref[k])) for k in ref]
            cs = [(k, c) for k, c in cs if c is not None and abs(c) > 0.7]
            cs.sort(key=lambda t: -abs(t[1]))
            korr = "; ".join(f"{k} r={c:+.2f}" for k, c in cs[:2])

        if a in BEKANNT:
            deutung, sicher, beleg = BEKANNT[a]
            bek.append(f"| {a} | {jetzt} | {lo}–{hi} | {n} | {deutung} | **{sicher}** | {beleg} |")
        elif a in LOWWORD:
            continue
        elif n == 1:
            konst.append((a, jetzt))
        else:
            var.append(f"| {a} | {jetzt} | {lo}–{hi} | {n} | {korr or '—'} | **unbestätigt** |")

    nz = [(a, w) for a, w in konst if w != 0]
    null = [a for a, w in konst if w == 0]

    L: list[str] = []
    add = L.append
    add("# Registerkatalog — alle beobachteten Werte\n")
    add(f"Erzeugt aus **{len(rows)} Messpunkten** des Laufs {rows[0]['t']} bis "
        f"{rows[-1]['t']} (UTC), Takt 30 s.")
    add("Anker SOLIX Solarbank 4 E5000 Pro, Unit-ID 1, Function Code 4, nur lesend.\n")
    add("Zweck: **jeden Registerwert festhalten, der etwas aussagt**, damit ihm später die")
    add("richtige Funktion zugewiesen werden kann. Die Spalte *Sicherheit* trennt Belegtes")
    add("von Vermutetem. Nichts hier ist geraten — wo die Deutung offen ist, steht das so.\n")
    add("Lowword-Adressen von 32-Bit-Größen sind ausgelassen, sie tragen keine eigene")
    add("Bedeutung. Ausführliche Belege stehen in `REGISTER.md`, `PV4.md` und `PV4-SUCHE.md`.\n")
    add("Diese Datei wird von `scratchpad/katalog.py` erzeugt und kann jederzeit mit mehr")
    add("Messdaten neu gebaut werden.\n")
    add("---\n")

    add("## 1. Gedeutete Register\n")
    add("| Adresse | jetzt | Bereich | Zustände | Deutung | Sicherheit | Beleg |")
    add("|---|---|---|---|---|---|---|")
    L.extend(bek)

    add("\n---\n")
    add("## 2. Unbestätigt, aber beweglich — die aussichtsreichen Kandidaten\n")
    add("Diese Register **ändern sich** und tragen damit Information. Angegeben ist die")
    add("stärkste Korrelation zu einer bekannten Größe, sofern ihr Betrag über 0,7 liegt.\n")
    add("**Warnung zur Deutung:** Über ein Fenster mit monotonem Verlauf korreliert alles")
    add("mit allem. Register 10213 (Netzfrequenz) ist die Negativkontrolle — taucht es in")
    add("einer Korrelationsliste weit oben auf, ist das Fenster untauglich und die Zahl wertlos.\n")
    add("| Adresse | jetzt | Bereich | Zustände | stärkste Korrelation | Status |")
    add("|---|---|---|---|---|---|")
    L.extend(var if var else ["| — | | | | keine beweglichen Unbekannten | |"])

    add("\n---\n")
    add("## 3. Unbestätigt und konstant\n")
    add("Über den gesamten Lauf unveränderlich. Ein konstanter Wert ungleich null ist meist")
    add("eine Kennung, ein Grenzwert oder ein Ausstattungsmerkmal.\n")
    add("### Konstant, Wert ungleich null\n")
    add("| Adresse | Wert | hex |")
    add("|---|---|---|")
    for a, w in nz:
        add(f"| {a} | {w} | 0x{w:04X} |")
    add(f"\n### Konstant null — {len(null)} Adressen\n")
    add("Gültig lesbar, aber durchgehend null. Entweder unbelegte Reservefelder oder")
    add("Funktionen, die diese Anlage nicht besitzt: kein Erweiterungsakku, kein")
    add("angeschlossener Smart Meter, keine Fremdanlage.\n")
    add("```")
    for i in range(0, len(null), 12):
        add("  " + " ".join(f"{x:>6}" for x in null[i:i + 12]))
    add("```\n")

    add("---\n")
    add("## 4. Wie ein Kandidat bestätigt wird\n")
    add("Drei Hürden, und alle drei müssen genommen werden:\n")
    add("1. **Auflösung.** Ein echter Messwert nimmt über einen Tag viele Zustände an. Die")
    add("   bestätigten Strangströme kommen auf 80 bis 161. Ein Register mit weniger als")
    add("   etwa 30 Zuständen kann keine feine Messgröße sein, egal wie gut es korreliert.")
    add("2. **Negativkontrolle.** Die Korrelation muss sich von der der Netzfrequenz")
    add("   absetzen. Korreliert 10213 mit, misst man den Tagestrend und nicht das Register.")
    add("3. **Divergenztest.** Es braucht Zeitpunkte, an denen die vermutete Größe und ihre")
    add("   Alternative **auseinanderlaufen**. Nur dort trennt sich die Frage. So wurde 10205")
    add("   entschieden: In 24 solchen Schritten folgte es 24 mal der AC-Leistung und null")
    add("   mal dem PV4-Restwert.\n")

    ziel.write_text("\n".join(L), encoding="utf-8")
    print(f"geschrieben: {ziel}")
    print(f"  gedeutet {len(bek)} · unbestaetigt beweglich {len(var)} · "
          f"konstant ungleich null {len(nz)} · konstant null {len(null)}")


if __name__ == "__main__":
    main()
