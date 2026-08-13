"""Konstanten der Lernprognose.

Dieses Modul ist bewusst dreigeteilt, weil die Betreibervorgabe lautet:
"Niemals irgendwas fix festlegen." Was hier trotzdem als Zahl steht, muss
sich rechtfertigen. Die drei Klassen sind:

  A) META - Parameter des Lernverfahrens selbst. Fensterlaengen, Schwellen,
     Robustheitsmasse. Sie beschreiben NICHT die Anlage, sondern wie gelernt
     wird. Ohne sie gibt es kein Verfahren. Jeder Wert ist unten einzeln
     begruendet.

  B) PHYSIK - Naturkonstanten und Groessen aus dem Modul-Datenblatt. Sie
     stehen auf keinem Register und aendern sich nur, wenn jemand Hardware
     tauscht.

  C) QUELLEN - Entity-IDs. Verdrahtung, keine Empirie. Jede Groesse hat eine
     Kette: faellt die erste Quelle aus, greift die naechste.

Alles Empirische - Hauslast, Pegel gegen Forecast.Solar, Tagesform,
Wirkungsgrad, Systemgain - steht NICHT hier, sondern wird in schaetzer.py
laufend aus der Historie geschaetzt. Alle Anlagenkennwerte - Kapazitaet,
AC-Grenze, Ladeleistung, SOC-Obergrenze - stehen NICHT hier, sondern werden
in kennwerte.py aus dem Geraet gelesen.
"""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "pv_lernprognose"
STORE_KEY: Final = f"{DOMAIN}.lernstand"
STORE_VERSION: Final = 1

CONF_NEIGUNG: Final = "neigung"
CONF_AZIMUT: Final = "azimut"

# Modulebene. Physisch am Dach festgelegt, aber nicht messbar - deshalb
# Konfigurationswerte statt Konstanten. Der Backtest vom 13.08.2026 hat
# gezeigt, dass Forecast.Solar auf 25/180 statt real 20/188 steht.
#
# Wichtig: Ein Fehler in diesen beiden Zahlen ist NICHT kritisch. Die
# gelernte Tagesform ist das Verhaeltnis Messung/Geometrie und schluckt
# jede systematische Schieflage der Geometrie mit. Falsche Neigung
# verschiebt nur, wieviel Arbeit die Form leisten muss.
DEFAULT_NEIGUNG: Final = 20.0   # Grad gegen die Horizontale
DEFAULT_AZIMUT: Final = 188.0   # Grad, 180 = Sued, im Uhrzeigersinn von Nord


# ==========================================================================
# A) META - Parameter des Lernverfahrens
# ==========================================================================

# --- Abtastung ------------------------------------------------------------
# 60 s. Der schnellste Quellsensor (Modbus-Gruppe "strings") liefert alle
# 30 s, die Cloud-Integration alle 60 s. Schneller abzutasten bringt keine
# neue Information, langsamer verliert die Wolkenerkennung ihre Aufloesung.
ABTASTUNG_S: Final = 60

# Wie oft der Lernstand auf Platte geschrieben wird. Ein Absturz darf
# hoechstens diesen Zeitraum an Rohdaten des laufenden Tages kosten.
SPEICHERN_S: Final = 900

# --- Fensterlaengen -------------------------------------------------------
# Alle Schaetzer laufen ueber ein gleitendes Fenster. Die Laenge ist der
# Kompromiss zwischen Rauschen (kurz ist schlecht) und Traegheit gegenueber
# echter Aenderung (lang ist schlecht).
#
# Hauslast 28 Tage: vier volle Wochen, damit jeder Wochentag gleich oft
# vorkommt und ein einzelner Waschtag nicht durchschlaegt. Kuerzer wuerde
# die Werktag/Wochenende-Trennung ausduennen.
FENSTER_HAUSLAST_TAGE: Final = 28

# Pegel 21 Tage: der Bias von Forecast.Solar driftet saisonal (Sonnenstand,
# bifazialer Anteil). Drei Wochen sind kurz genug, um die Drift mitzunehmen,
# und lang genug fuer eine belastbare Median-Stichprobe.
FENSTER_PEGEL_TAGE: Final = 21

# Tagesform 45 Tage: die Form wird nach Sonnenazimut indiziert, nicht nach
# Uhrzeit. Ein Azimutfach wird pro Tag nur wenige Minuten lang befuellt und
# nur bei klarer Sicht. 45 Tage sind noetig, damit auch bei durchwachsenem
# Wetter genug klare Momente je Fach zusammenkommen. Die Jahreszeitendrift
# faengt die Rezenzgewichtung ab (siehe HALBWERTSZEIT_TAGE).
FENSTER_FORM_TAGE: Final = 45

# Wirkungsgrad 21 Tage: je Tag genau ein Wert aus der Energiebilanz.
FENSTER_ETA_TAGE: Final = 21

# Rezenzgewichtung innerhalb des Fensters. Ein Wert von vor 14 Tagen zaehlt
# halb so viel wie einer von heute. Damit folgt die Tagesform der
# Sonnenbahn ueber die Jahreszeiten mit etwa zwei bis drei Wochen Nachlauf,
# statt ueber das ganze Fenster zu mitteln.
HALBWERTSZEIT_TAGE: Final = 14.0

# --- Wann gilt ein Schaetzer als eingeschwungen? --------------------------
# Darunter meldet er `gelernt: false` und liefert seinen Startwert. Die
# Schwellen sind so gesetzt, dass der Median nicht mehr von einem einzelnen
# Tag gekippt werden kann: ab n = 5 braucht es drei gleichgerichtete
# Ausreisser, um den Median zu verschieben.
MIN_TAGE_HAUSLAST: Final = 7      # je Stunde und Tagestyp
MIN_TAGE_PEGEL: Final = 5
MIN_TAGE_ETA: Final = 5
MIN_TAGE_FORM: Final = 4          # verschiedene Tage je Azimutfach
MIN_PROBEN_FORM: Final = 8        # Einzelmessungen je Azimutfach
MIN_FAECHER_GAIN: Final = 8       # belegte Faecher, bevor der Gain zaehlt

# --- Robustheit -----------------------------------------------------------
# Modifizierter z-Wert nach Iglewicz/Hoaglin: z = 0.6745*(x-median)/MAD.
# Der Schwellwert 3.5 ist der dort empfohlene; er entspricht bei
# normalverteilten Daten etwa 3.5 Standardabweichungen und wirft rund
# 0.05 Prozent gutartiger Werte weg. Genau dieses Sieb sortiert
# Reglertests und Drosselungstage aus, ohne dass sie jemand benennt.
MAD_FAKTOR: Final = 3.5
MAD_SKALIERUNG: Final = 0.6745

# --- Klarheitserkennung ---------------------------------------------------
# Ein Messpunkt geht nur dann in die Tagesform ein, wenn die Sonne in
# diesem Moment frei stand. Kriterium: die Abweichung der PV-Leistung von
# ihrem eigenen linearen Trend ueber das Fenster, relativ zum Mittelwert.
# Eine ungestoerte Klarhimmelkurve ist ueber 15 Minuten nahezu linear;
# Wolken erzeugen sofort mehrere Prozent Reststreuung.
#
# 0.05 wurde am 13.08.2026 an der gemessenen Streuung geeicht:
# sensor.*_pv_signal_streuung_5min lag bei klarer Sicht um 20-35 W auf
# 1300-1400 W Signal, also 1.5-2.7 Prozent. 5 Prozent laesst diese
# Momente durch und sperrt alles Wolkige.
KLARHEIT_FENSTER_MIN: Final = 15
KLARHEIT_SCHWELLE: Final = 0.05

# --- Zensurerkennung (Abregelung) -----------------------------------------
# Sobald der Speicher voll ist, drosselt die Nulleinspeisung die PV auf die
# Hauslast. Die Messung zeigt dann nicht mehr das Dargebot. Solche Punkte
# duerfen weder in die Tagesform noch in den Pegel eingehen.
#
# 1) SOC am oberen Anschlag, mit einem Prozentpunkt Sicherheitsabstand.
ZENSUR_SOC_ABSTAND: Final = 1.0
# 2) Leistung steht still, waehrend die Geometrie sich bewegt. Genau das
#    Muster des Drosselungstests vom 08.08.2026 (sechs Stunden konstant
#    798 W). Kein Datum, keine Handauswahl - reine Mustererkennung.
ZENSUR_FLACH_MIN: Final = 30        # Beobachtungsfenster in Minuten
ZENSUR_FLACH_STREUUNG: Final = 0.01  # relative Reststreuung, darunter "steht still"
ZENSUR_GEOMETRIE_HUB: Final = 0.10   # Klarhimmelerwartung aenderte sich um mehr als das

# --- Untergrenzen, unterhalb derer Verhaeltnisse Rauschen sind ------------
MIN_POA_W: Final = 80.0        # W/m2 Klarhimmel-Modulebene
MIN_PV_W: Final = 50.0         # W gemessene Erzeugung
MIN_SONNENHOEHE: Final = 5.0   # Grad; darunter dominieren Horizont und IAM

# --- Tagesform ------------------------------------------------------------
# Facherbreite des Sonnenazimuts. 5 Grad entsprechen im Sommer rund 20
# Minuten und im Winter rund 25 Minuten Sonnenlauf - fein genug fuer die
# gemessene Verschattungskante (Abfall von 0.97 auf 0.62 in zweieinhalb
# Stunden), grob genug fuer eine tragfaehige Stichprobe je Fach.
AZIMUT_BIN: Final = 5.0
AZIMUT_VON: Final = 40.0
AZIMUT_BIS: Final = 320.0

# Die Form ist als Durchlassgrad definiert und kann nicht ueber 1 liegen.
# 1.10 als Klammer laesst Messrauschen und Randeffekte (Reflexionen an
# Wolkenkanten) zu, ohne dass ein Ausreisser die Normierung sprengt.
FORM_MAX: Final = 1.10
FORM_MIN: Final = 0.05

# Quantil, das den unverschatteten Plateauwert markiert. Der Systemgain
# ist definiert als das 0.90-Quantil ueber alle belegten Azimutfaecher:
# die Faecher oberhalb sind unverschattet, alles darunter ist Schatten.
# 0.90 statt 1.00, damit ein einzelnes Ausreisserfach die Normierung nicht
# verschiebt.
GAIN_QUANTIL: Final = 0.90

# --- Truebung (der ehemalige Faktor k) ------------------------------------
# Die Truebung ist jetzt ein reiner Bewoelkungsindex: gemessene Leistung
# geteilt durch Klarhimmelerwartung EINSCHLIESSLICH gelernter Verschattung.
# Damit misst sie das, wofuer k gedacht war - der Backtest hatte gezeigt,
# dass das alte k die Verschattung als Bewoelkung fehlinterpretierte.
#
# Die Klammer ist physikalisch, nicht empirisch: unter Wolken geht es
# beliebig weit herunter, ueber Klarhimmel kommt man nur durch
# Wolkenkantenreflexion, und die traegt keine 20 Prozent ueber den Tag.
TRUEBUNG_MIN: Final = 0.03
TRUEBUNG_MAX: Final = 1.20

# Gewicht der Live-Messung gegenueber der Wettervorhersage, als
# Halbwertszeit. Was jetzt gemessen wird, sagt ueber die naechste
# Viertelstunde viel und ueber den Abend weniger.
#
# Der Sweep in tools/pruefe_lernprognose.py ueber die vier Tage vom
# 09.-12.08.2026 ist monoton und flach: RMSE der SOC-Bahn 7.48 pp bei
# 15 min, 6.69 bei 90, 6.59 bei 120, 6.37 bei 360, 6.29 bei "nur
# Live-Messung". Laenger ist auf DIESEN Daten immer besser.
#
# Trotzdem nicht laenger. In der Stichprobe ist kein einziger bedeckter
# Tag. Was ein grosses tau anrichtet - vormittags klar messen und daraus
# einen klaren Nachmittag hochrechnen, waehrend eine Front hereinzieht -
# kann an diesen Daten gar nicht sichtbar werden. 120 Minuten liegt
# 0.3 pp ueber dem Sweep-Optimum und laesst die Wetterprognose ab etwa
# drei Stunden Vorlauf uebernehmen.
#
# Das ist der am schwaechsten belegte Meta-Parameter des Verfahrens.
# Sobald ein bedeckter Tag in der Historie liegt, gehoert der Sweep
# wiederholt.
TRUEBUNG_TAU_MIN: Final = 120.0

# --- Wirkungsgrad ---------------------------------------------------------
# Physikalische Klammer eines Lithium-Speichers mit Wechselrichter.
ETA_MIN: Final = 0.75
ETA_MAX: Final = 1.00

# --- Simulation -----------------------------------------------------------
SCHRITT_MIN: Final = 15          # Aufloesung der Vorwaertsrechnung
SCHRITT_NACHT_MIN: Final = 60    # nachts genuegt die Stunde


# ==========================================================================
# B) PHYSIK - Naturkonstanten und Datenblatt
# ==========================================================================

SOLARKONSTANTE: Final = 1361.0   # W/m2
# Atmosphaerische Truebung des Klarhimmelmodells (Meinel). Der Absolutwert
# ist unkritisch: der gelernte Systemgain normiert ihn weg. Relevant ist
# allein der Verlauf ueber Sonnenhoehe und Jahreszeit.
ATMOSPHAERE_TAU: Final = 0.70
DIFFUSANTEIL_KLAR: Final = 0.10  # Diffusstrahlung als Anteil des Direktstrahls
ALBEDO: Final = 0.20             # Bodenreflexion, Standardwert Gras/Ziegel

# Modul Sakete SKT500M12-108D4, Doppelglas, bifazial. Datenblattwerte.
# Sie stehen auf keinem Register und aendern sich nur beim Modultausch.
# Der bifaziale Mehrertrag wird NICHT modelliert - er steckt vollstaendig
# im gelernten Systemgain und ist genau einer der Gruende, warum
# Forecast.Solar (nur Vorderseite) diese Anlage unterschaetzt.
MODUL_VMP_STC: Final = 33.18     # V
MODUL_VOC_STC: Final = 39.90     # V
MODUL_TEMP_KOEFF: Final = 0.0025  # 1/K, gilt fuer Voc wie Vmp


# ==========================================================================
# C) QUELLEN - Entity-Ketten
# ==========================================================================
# Erste Quelle gewinnt. Faellt sie aus (unavailable/unknown), rutscht die
# Kette weiter. Steht am Ende keine Quelle, greift der Ersatzwert der
# jeweiligen Groesse und der Zustand wird im Attribut ausgewiesen.

QUELLE_PV_W: Final = (
    "sensor.solarbank_dc_straenge_441_pv_leistung_gesamt_modbus",
    "sensor.anker_solix_solarbank_4_e5000_pro_441_solarstrom",
)
QUELLE_SOC: Final = (
    "sensor.anker_solix_solarbank_4_e5000_pro_441_soc",
    "sensor.solarbank_dc_straenge_441_pv_ladezustand_modbus",
)
QUELLE_HAUSLAST_W: Final = (
    "sensor.anker_solix_solarbank_4_e5000_pro_441_startseite_last",
    "sensor.solarbank_dc_straenge_441_pv_hauslast_modbus",
)

# Kaltstartquelle des Hauslastprofils - NUR fuer den Bootstrap, niemals
# laufend. Der IR-Lesekopf misst die Leistung direkt am Zaehler. Solange es
# weder PV noch Speicher gab, ist der Netzbezug identisch mit der Hauslast;
# danach misst derselbe Sensor den Bezug NACH PV und Speicher und hat mit
# der Hauslast nichts mehr zu tun.
#
# Deshalb steht diese Entity bewusst NICHT in QUELLE_HAUSLAST_W. Der
# Bootstrap bestimmt die Gueltigkeitsgrenze selbst am Vorzeichen (siehe
# BOOTSTRAP_RUECKLAUF_W) und schneidet dort hart ab. Ein Datum steht
# absichtlich nirgends - es wuerde beim naechsten Anlagenumbau stillschweigend
# falsch werden.
QUELLE_HAUSLAST_BOOTSTRAP: Final = ("sensor.stromleser_emh_power",)

# Ein Stundenminimum unterhalb dieser Schwelle beweist Rueckspeisung ins
# Netz und damit eine laufende Erzeugungsanlage. Ab der ersten solchen
# Stunde ist der Zaehlerwert keine Hauslast mehr, und der Bootstrap bricht
# ab. Null waere die exakte Grenze; -5 W laesst Messrauschen und
# Nulldurchgaenge des Lesekopfs zu, ohne echte Einspeisung durchzulassen
# (die erste gemessene lag bei -423 W).
BOOTSTRAP_RUECKLAUF_W: Final = -5.0

# Ein Tag geht nur mit mindestens so vielen Stunden in das Startprofil ein.
BOOTSTRAP_MIN_STUNDEN: Final = 20

# Wieviele Tage der Bootstrap hoechstens zurueckliest.
BOOTSTRAP_TAGE_MAX: Final = 120
QUELLE_LADEENERGIE_KWH: Final = (
    "sensor.anker_solix_solarbank_4_e5000_pro_441_batterie_ladeenergie",
    "sensor.solarbank_dc_straenge_441_pv_ladeenergie_kumuliert_modbus",
)
QUELLE_ENTLADEENERGIE_KWH: Final = (
    "sensor.anker_solix_solarbank_4_e5000_pro_441_batterie_entladeenergie",
    "sensor.solarbank_dc_straenge_441_pv_entladeenergie_kumuliert_modbus",
)
QUELLE_DROSSELUNG_W: Final = ("sensor.pv_drosselung_leistung",)

# --- Anlagenkennwerte, aus dem Geraet gelesen -----------------------------
# Reihenfolge nach Vertrauenswuerdigkeit. Die offizielle Integration zuerst,
# der eigene Modbus-Sensor als Rueckfall.
QUELLE_KAPAZITAET_KWH: Final = (
    "sensor.anker_solix_solarbank_4_e5000_pro_441_akkukapazitat",
    "sensor.solarbank_dc_straenge_441_pv_nennkapazitaet_modbus",
)
QUELLE_AC_GRENZE_W: Final = ("sensor.pv_ac_ausgangslimit",)          # Register 10038
QUELLE_MAX_LADELEISTUNG_W: Final = ("sensor.pv_maximale_ladeleistung",)  # Register 10036
QUELLE_SOC_MAX: Final = (
    "number.anker_solix_solarbank_4_e5000_pro_441_ladeobergrenze",     # Register 60000
    "sensor.solarbank_dc_straenge_441_pv_ladeobergrenze_modbus",
)
# Betreibereinstellung, kein Messwert - darf gesetzt bleiben.
QUELLE_SOC_MIN: Final = ("input_number.nulleinspeisung_soc_untergrenze",)
QUELLE_ZIEL_SOC: Final = ("input_number.nulleinspeisung_prioritaetsladung_max_soc",)

# --- Forecast.Solar -------------------------------------------------------
QUELLE_FS_HEUTE_KWH: Final = ("sensor.energy_production_today",)
QUELLE_FS_REST_KWH: Final = ("sensor.energy_production_today_remaining",)
QUELLE_FS_MORGEN_KWH: Final = ("sensor.energy_production_tomorrow",)
QUELLE_FS_JETZT_W: Final = ("sensor.power_production_now",)

# --- Plausibilitaetsbereiche der Kennwerte --------------------------------
# Ein kurzer Geraeteausfall darf die Prognose nicht kippen. Liest ein
# Kennwert ausserhalb dieses Bereichs, gilt er als ungueltig und der letzte
# gute Wert wird gehalten. Die Bereiche sind absichtlich weit: sie sollen
# Nullen und Registermuell abfangen, nicht eine Aufruestung verhindern.
BEREICH_KAPAZITAET_KWH: Final = (1.0, 100.0)
BEREICH_AC_GRENZE_W: Final = (100.0, 20000.0)
BEREICH_MAX_LADELEISTUNG_W: Final = (200.0, 20000.0)
BEREICH_SOC_MAX: Final = (50.0, 100.0)
BEREICH_SOC_MIN: Final = (0.0, 60.0)

# --- Ersatzwerte, falls noch nie ein gueltiger Wert gelesen wurde ---------
# Nur fuer den Kaltstart. Sobald einmal ein plausibler Wert vom Geraet kam,
# wird dieser gehalten und der Ersatzwert nie wieder benutzt.
ERSATZ_KAPAZITAET_KWH: Final = 5.1
ERSATZ_AC_GRENZE_W: Final = 800.0
ERSATZ_MAX_LADELEISTUNG_W: Final = 3000.0
ERSATZ_SOC_MAX: Final = 100.0
ERSATZ_SOC_MIN: Final = 12.0

# --- Startwerte des Hauslastprofils ---------------------------------------
# Median je Stunde aus sensor.stromleser_emh_power, 23.06. bis 07.08.2026.
# In diesem Fenster gab es keine PV und keinen Speicher - der Zaehler misst
# reinen Netzbezug, und der ist dort identisch mit der Hauslast. 43 Tage
# mit mindestens 20 Stunden Abdeckung, davon 31 Werktage und 12
# Wochenendtage. Index 0 = 00 Uhr.
#
# Diese Konstanten sind der LETZTE Rueckfall. Im Betrieb ermittelt der
# Coordinator dasselbe Profil beim Kaltstart selbst aus der
# Langzeitstatistik (siehe QUELLE_HAUSLAST_BOOTSTRAP) - damit stimmt es
# auch dann, wenn sich der Haushalt seit August 2026 geaendert hat.
#
# Beides sind Startwerte, keine gelernten Werte. Der Schaetzer weist sie
# als solche aus (gelernt: false), bis genug eigene Tage vorliegen.
START_HAUSLAST_W: Final = (
    324, 310, 287, 276, 294, 327,
    543, 529, 372, 387, 354, 386,
    433, 677, 532, 534, 667, 557,
    522, 595, 517, 560, 509, 371,
)
START_HAUSLAST_WE_W: Final = (
    450, 359, 320, 277, 285, 338,
    353, 326, 469, 551, 426, 444,
    617, 583, 563, 507, 494, 579,
    590, 689, 581, 549, 581, 500,
)

# Startwert des Pegels gegen Forecast.Solar.
#
# ACHTUNG, nicht die 1.30 aus docs/PROGNOSE.md Abschnitt 2. Jene Zahl ist
# ist_rest/rohrest - und ist_rest ist durch die Abregelung nach oben
# zensiert, also eine Untergrenze. Der Pegelschaetzer misst anders: er
# vergleicht zwei Truebungsindizes und benutzt nur unzensierte
# Abschnitte. In dieser Metrik ergeben dieselben vier Tage
#
#     09.08. 1.662   10.08. 1.488   11.08. 1.258   12.08. 1.360
#
# also Median 1.42 bei einer Spanne von 1.26 bis 1.66. Hergeleitet in
# tools/pruefe_lernprognose.py, Abschnitt 2b. Der Startwert MUSS in
# derselben Metrik stehen wie das, was der Schaetzer spaeter lernt -
# sonst springt die Prognose an dem Tag, an dem er einschwingt.
START_PEGEL: Final = 1.42

# Startwert des Speicherwirkungsgrads. Bisheriger fester Wert des Sensors.
START_ETA: Final = 0.95

# --- Lastabhaengiger Ladewirkungsgrad (FOLGEAUFTRAG 7.2) -------------------
#
# Ein KONSTANTER Wirkungsgrad ist widerlegt. tools/korrelation_10254.py haelt
# 10254 (Ladeleistung nach Wandlung) gegen 10008 (davor), 882 Messpunkte des
# 12.08. im selben Abfragezyklus:
#
#     10254 = -0.9572 * 10008 - 54.3 W     r = -0.982
#
# Das ist kein prozentualer Verlust, sondern ein FESTER SOCKEL von 54 W plus
# 4,3 % proportional - die Signatur eines Wandlungspfads mit Eigenverbrauch.
# Daraus folgt eta(P) = 0.9572 - 54.3 / P:
#
#     200 W -> 0.686      1000 W -> 0.903
#     380 W -> 0.814      2000 W -> 0.930
#
# Der bisherige Festwert 0.95 wird also erst oberhalb von rund 3,7 kW erreicht
# und liegt bei den real auftretenden Ladeleistungen deutlich zu hoch. Genau
# das erklaert einen Teil des Prognose-Optimismus.
#
# NUR FUERS LADEN. Im Entladeregime bricht der Zusammenhang zusammen
# (r = -0.148, n = 364) - dort bleibt es beim gelernten Wirkungsgrad.
ETA_STEIGUNG: Final = 0.9572     # proportionaler Anteil
ETA_SOCKEL_W: Final = 54.3       # fester Eigenverbrauch des Wandlungspfads

# Startwert des Systemgains in W je W/m2 Modulebene. Gemessen an den vier
# Tagen vom 09.-12.08.2026: 2.065.
#
# Unabhaengige Gegenprobe: mit diesem Gain sagt das Klarhimmelmodell fuer
# einen klaren Augusttag EINSCHLIESSLICH der gelernten Verschattung
# 11.96 kWh vorher. docs/PROGNOSE.md Abschnitt 2 hatte auf voellig
# anderem Weg - Eichung des Systemwirkungsgrads am unverschatteten
# Vormittag - 12.0 kWh gerechnet. Die beiden Rechnungen wissen nichts
# voneinander.
START_GAIN: Final = 2.06
BEREICH_GAIN: Final = (0.3, 6.0)
