"""Robuste Statistik.

Jede gelernte Groesse wird ueber diese Funktionen gebildet, nie ueber den
arithmetischen Mittelwert. Der Grund steht in docs/PROGNOSE.md Abschnitt 3:
das alte Hauslastprofil war ein Mittelwert aus zwei Tagen, von denen einer
Reglertests enthielt - 14 Uhr stand deshalb auf 1008 W statt auf 501 W.
Ein Median haette diesen Fehler nicht gemacht.
"""

from __future__ import annotations

import math

from .const import MAD_FAKTOR, MAD_SKALIERUNG


def median(werte: list[float]) -> float | None:
    """Median. None bei leerer Liste."""
    if not werte:
        return None
    s = sorted(werte)
    n = len(s)
    mitte = n // 2
    if n % 2:
        return s[mitte]
    return (s[mitte - 1] + s[mitte]) / 2.0


def quantil(werte: list[float], q: float) -> float | None:
    """Empirisches Quantil mit linearer Interpolation."""
    if not werte:
        return None
    s = sorted(werte)
    if len(s) == 1:
        return s[0]
    pos = q * (len(s) - 1)
    unten = int(math.floor(pos))
    oben = min(unten + 1, len(s) - 1)
    rest = pos - unten
    return s[unten] * (1.0 - rest) + s[oben] * rest


def mad(werte: list[float], zentrum: float | None = None) -> float:
    """Mediane absolute Abweichung."""
    if not werte:
        return 0.0
    z = zentrum if zentrum is not None else median(werte)
    if z is None:
        return 0.0
    return median([abs(x - z) for x in werte]) or 0.0


def ausreisserfrei(werte: list[float], faktor: float = MAD_FAKTOR) -> list[float]:
    """Entfernt Werte mit modifiziertem z-Wert ueber `faktor`.

    z = 0.6745 * (x - Median) / MAD, nach Iglewicz/Hoaglin. Wenn die MAD
    null ist (mehr als die Haelfte der Werte identisch), wird nichts
    entfernt - dann gibt es keinen sinnvollen Streuungsmassstab, und ein
    hartes Kriterium wuerde alles Abweichende loeschen.
    """
    if len(werte) < 4:
        return list(werte)
    z = median(werte)
    if z is None:
        return list(werte)
    streuung = mad(werte, z)
    if streuung <= 0.0:
        return list(werte)
    grenze = faktor * streuung / MAD_SKALIERUNG
    behalten = [x for x in werte if abs(x - z) <= grenze]
    # Nie alles wegwerfen: wenn das Sieb zu scharf greift, ist das Modell
    # der Streuung falsch, nicht die Daten.
    return behalten if behalten else list(werte)


def robuster_median(werte: list[float], faktor: float = MAD_FAKTOR) -> float | None:
    """Median nach Ausreisserfilter."""
    return median(ausreisserfrei(werte, faktor))


def gewichteter_median(paare: list[tuple[float, float]]) -> float | None:
    """Median mit Gewichten. `paare` ist [(wert, gewicht), ...].

    Wird fuer die Rezenzgewichtung gebraucht: ein Messwert von heute soll
    schwerer wiegen als einer von vor vier Wochen, damit die Schaetzer der
    Jahreszeit und geaenderten Gewohnheiten folgen, ohne dass das Fenster
    hart abschneidet.
    """
    gefiltert = [(w, g) for w, g in paare if g > 0.0]
    if not gefiltert:
        return None
    gefiltert.sort(key=lambda p: p[0])
    gesamt = sum(g for _, g in gefiltert)
    halb = gesamt / 2.0
    laufend = 0.0
    for wert, gewicht in gefiltert:
        laufend += gewicht
        if laufend >= halb:
            return wert
    return gefiltert[-1][0]


def robuster_gewichteter_median(
    paare: list[tuple[float, float]], faktor: float = MAD_FAKTOR
) -> float | None:
    """Erst Ausreisser nach MAD entfernen, dann gewichteter Median.

    Das ist das Standardwerkzeug aller Tagesschaetzer: der Ausreisserfilter
    wirft Reglertests und Geraetestoerungen heraus, die Gewichtung laesst
    die juengere Vergangenheit schwerer zaehlen.
    """
    if not paare:
        return None
    werte = [w for w, _ in paare]
    behalten = set()
    for w in ausreisserfrei(werte, faktor):
        behalten.add(w)
    gesiebt = [(w, g) for w, g in paare if w in behalten]
    return gewichteter_median(gesiebt or paare)


def rezenzgewicht(alter_tage: float, halbwertszeit: float) -> float:
    """Exponentielles Gewicht nach Alter."""
    if halbwertszeit <= 0:
        return 1.0
    return 0.5 ** (max(alter_tage, 0.0) / halbwertszeit)


def entrendete_streuung(werte: list[float]) -> float | None:
    """Relative Reststreuung um die eigene Ausgleichsgerade.

    Das Klarheitsmass des Verfahrens. Eine ungestoerte Klarhimmelkurve ist
    ueber eine Viertelstunde nahezu linear; was nach Abzug der Geraden
    uebrig bleibt, ist Bewoelkung (oder Regelungsaktivitaet).

    Rueckgabe: Wurzel der mittleren quadratischen Residuen, geteilt durch
    den Mittelwert. None, wenn zu wenige Punkte oder Mittelwert bei null.
    """
    n = len(werte)
    if n < 4:
        return None
    mittel = sum(werte) / n
    if mittel <= 0.0:
        return None

    # x = 0, 1, ..., n-1
    sx = (n - 1) * n / 2.0
    sxx = (n - 1) * n * (2 * n - 1) / 6.0
    sy = sum(werte)
    sxy = sum(i * v for i, v in enumerate(werte))
    nenner = n * sxx - sx * sx
    if abs(nenner) < 1e-9:
        return None
    steigung = (n * sxy - sx * sy) / nenner
    achse = (sy - steigung * sx) / n

    quadrate = sum((v - (achse + steigung * i)) ** 2 for i, v in enumerate(werte))
    return math.sqrt(quadrate / n) / mittel


def steigung(werte: list[float]) -> float:
    """Steigung der Ausgleichsgeraden je Schritt."""
    n = len(werte)
    if n < 2:
        return 0.0
    sx = (n - 1) * n / 2.0
    sxx = (n - 1) * n * (2 * n - 1) / 6.0
    sy = sum(werte)
    sxy = sum(i * v for i, v in enumerate(werte))
    nenner = n * sxx - sx * sx
    if abs(nenner) < 1e-9:
        return 0.0
    return (n * sxy - sx * sy) / nenner
