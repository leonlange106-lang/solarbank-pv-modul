// haus.js — Hausansicht: Platzhaltergrafik mit echter Fluss- und
// Schattenlogik.
//
// Reines ES-Modul, kein Build. Zeichnet ein schematisches Haus mit
// Satteldach und angebautem Carport als SVG (kein Bild). Die Geometrie ist
// bewusst ein Platzhalter - Fluss- und Schattenberechnung sind es nicht.
//
// Kontrakt: buildHaus(ctx) -> HTMLElement. Das Element traegt eine Funktion
// el.update(), die die App im eigenen Takt aufruft, um die Anzeige an neue
// hass-Zustaende anzupassen. ctx.data ist eine langlebige Bruecke, die bei
// jedem Aufruf ihrer Methoden (state/num/attr/...) den jeweils aktuellen
// Zustand liefert - update() liest deshalb ohne eigenes Zustandsgedaechtnis
// einfach erneut aus ctx.data.
import { icon } from './m3.js';

const ANKER = 'sensor.anker_solix_solarbank_4_e5000_pro_441';

// ---------------------------------------------------------------------------
// Belegtes Azimut-Profil (siehe VERSCHATTUNG-PROFIL.md): Azimut in Grad ->
// Anteil je PV1..PV4 in Prozent. Liefert NUR die Position/Ausdehnung des
// Schattenbands je Modul - die tatsaechliche Modulfarbe kommt separat aus
// dem aktuell GEMESSENEN Leistungsanteil (siehe modulHelligkeitSetzen).
// ---------------------------------------------------------------------------
const AZIMUT_PROFIL = {
  135: [57, 99, 100, 100],
  140: [18, 98, 100, 100],
  145: [58, 62, 100, 100],
  150: [59, 35, 100, 100],
  155: [91, 12, 100, 100],
  160: [100, 13, 85, 100],
  165: [100, 17, 66, 100],
  170: [100, 49, 52, 100],
  175: [100, 66, 24, 100],
  180: [100, 67, 23, 100],
  185: [100, 82, 24, 100],
  190: [100, 100, 38, 76],
  195: [100, 100, 34, 69],
  200: [100, 100, 57, 29],
  205: [100, 100, 67, 21],
  210: [100, 100, 81, 22],
  215: [99, 100, 100, 25],
  220: [99, 100, 100, 46],
  225: [98, 100, 100, 70],
};
const AZIMUT_SCHLUESSEL = Object.keys(AZIMUT_PROFIL)
  .map(Number)
  .sort((a, b) => a - b);
const AZIMUT_MIN = AZIMUT_SCHLUESSEL[0];
const AZIMUT_MAX = AZIMUT_SCHLUESSEL[AZIMUT_SCHLUESSEL.length - 1];

/**
 * Lineare Interpolation zwischen den beiden benachbarten Tabellenpunkten.
 * Liefert null ausserhalb der Tabelle oder bei zu niedriger Sonne - dann
 * gibt es planmaessig keine Schattenaussage (siehe Aufgabenstellung).
 */
function schattenAnteile(azimut, elevation) {
  if (azimut == null || elevation == null) return null;
  if (elevation < 10) return null;
  if (azimut < AZIMUT_MIN || azimut > AZIMUT_MAX) return null;

  let unten = AZIMUT_SCHLUESSEL[0];
  let oben = AZIMUT_SCHLUESSEL[AZIMUT_SCHLUESSEL.length - 1];
  for (let i = 0; i < AZIMUT_SCHLUESSEL.length - 1; i++) {
    if (azimut >= AZIMUT_SCHLUESSEL[i] && azimut <= AZIMUT_SCHLUESSEL[i + 1]) {
      unten = AZIMUT_SCHLUESSEL[i];
      oben = AZIMUT_SCHLUESSEL[i + 1];
      break;
    }
  }
  if (unten === oben) return AZIMUT_PROFIL[unten];
  const t = (azimut - unten) / (oben - unten);
  const u = AZIMUT_PROFIL[unten];
  const o = AZIMUT_PROFIL[oben];
  return u.map((v, i) => v + (o[i] - v) * t);
}

// ---------------------------------------------------------------------------
// Geometrie der vier PV-Module auf der (aus Suedwest sichtbaren) rechten
// Dachflaeche. Fest berechnet aus First (270,90) und Traufe (390,160):
// vier Positionen entlang der Dachschraege, jeweils um deren Neigungswinkel
// gedreht.
// ---------------------------------------------------------------------------
const DACH_FIRST = { x: 270, y: 90 };
const DACH_TRAUFE = { x: 390, y: 160 };
const DACH_WINKEL = (Math.atan2(DACH_TRAUFE.y - DACH_FIRST.y, DACH_TRAUFE.x - DACH_FIRST.x) * 180) / Math.PI;
const MODUL_T = [0.15, 0.38, 0.61, 0.84];
const MODUL_POSITIONEN = MODUL_T.map((t) => ({
  x: DACH_FIRST.x + t * (DACH_TRAUFE.x - DACH_FIRST.x),
  y: DACH_FIRST.y + t * (DACH_TRAUFE.y - DACH_FIRST.y),
}));

// Batterie-Fuellstandsflaeche (innerhalb des Symbols): oberer/unterer Rand.
const BATT_OBEN = 207;
const BATT_UNTEN = 241;

// Flusspfade: PV -> Speicher, PV -> Haus, Speicher -> Haus, Netz <-> Haus.
// Kubische Bezierkurven, handgesetzt fuer die Platzhaltergeometrie.
const PFAD_PV_SPEICHER = 'M320,148 C300,190 250,192 199,209';
const PFAD_PV_HAUS = 'M352,150 C345,188 305,202 272,206';
const PFAD_SPEICHER_HAUS = 'M199,224 C222,232 246,232 268,222';
const PFAD_NETZ_HAUS = 'M427,196 C382,182 320,192 274,206';

function svgEl(tag, attrs) {
  const node = document.createElementNS('http://www.w3.org/2000/svg', tag);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
  return node;
}

/**
 * Baut die drei Fliesspunkte fuer einen Pfad. Die Punkte laufen ueber die
 * CSS-Eigenschaft offset-path entlang der uebergebenen Pfad-Definition -
 * dieselbe 'd'-Zeichenkette wie die sichtbare Verbindungslinie, damit beide
 * garantiert deckungsgleich sind.
 */
function fliesspunkteBauen(gruppe, pfadD, cssKlasse) {
  const punkte = [];
  for (let i = 0; i < 3; i++) {
    const punkt = svgEl('circle', { r: 3.4, class: `sb-fliesspunkt ${cssKlasse}` });
    punkt.style.offsetPath = `path("${pfadD}")`;
    punkt.style.webkitOffsetPath = `path("${pfadD}")`;
    punkt.style.animationDelay = `${-(i * 0.9)}s`;
    gruppe.appendChild(punkt);
    punkte.push(punkt);
  }
  return punkte;
}

/**
 * Setzt Dicke, Sichtbarkeit, Tempo und Richtung eines Flusses anhand seines
 * Wertes in Watt. Negative Werte kehren die Laufrichtung der Fliesspunkte
 * um (genutzt fuer Netz <-> Haus: positiv = Bezug, negativ = Einspeisung).
 */
function flussSetzen(linie, punkte, wattWert) {
  const betrag = Math.abs(wattWert);
  const aktiv = betrag > 1;
  const dicke = Math.min(7, Math.max(1.5, betrag / 350));
  linie.style.strokeWidth = String(dicke);
  linie.style.opacity = aktiv ? '1' : '0.25';
  const dauerMs = Math.max(900, 5000 - betrag * 6);
  for (const p of punkte) {
    p.style.animationDuration = `${dauerMs}ms`;
    p.style.animationDirection = wattWert < 0 ? 'reverse' : 'normal';
    p.style.opacity = aktiv ? '1' : '0';
    p.style.animationPlayState = aktiv ? 'running' : 'paused';
  }
}


/** icon() aus m3.js liefert SVG-MARKUP ALS STRING, keinen Knoten.
 *
 *  Das direkt an appendChild zu geben wirft
 *  "Argument 1 ('node') to Node.appendChild must be an instance of Node"
 *  und riss beim ersten Aufruf jede Ansicht ab. Diese Huelle macht daraus
 *  einen Knoten - an einer Stelle, statt an neun.
 */
function iconEl(name, cls) {
  const span = document.createElement('span');
  span.className = cls ? `sb-icon ${cls}` : 'sb-icon';
  span.setAttribute('aria-hidden', 'true');
  try {
    span.innerHTML = icon(name);
  } catch (e) {
    span.textContent = '';
  }
  return span;
}

export function buildHaus(ctx) {
  const wrap = document.createElement('div');
  wrap.className = 'sb-haus';

  // Deutlich sichtbarer Platzhalter-Hinweis.
  const chip = document.createElement('div');
  chip.className = 'sb-haus-chip';
  chip.appendChild(iconEl('home'));
  chip.appendChild(
    Object.assign(document.createElement('span'), {
      textContent:
        'Platzhalter — echtes Haus folgt, sobald Fotos und Masse vorliegen. Fluss und Schatten sind bereits echt.',
    })
  );
  wrap.appendChild(chip);

  const bild = document.createElement('div');
  bild.className = 'sb-haus-bild';
  wrap.appendChild(bild);

  const svg = svgEl('svg', {
    viewBox: '0 0 480 300',
    role: 'img',
    'aria-label': 'Schematische Hausansicht mit Energiefluss und Schattenwurf, Blick aus Suedwest',
  });
  bild.appendChild(svg);

  // Himmel/Boden.
  svg.appendChild(svgEl('rect', { x: 0, y: 0, width: 480, height: 300, class: 'sb-himmel' }));
  svg.appendChild(svgEl('rect', { x: 0, y: 250, width: 480, height: 50, class: 'sb-boden' }));

  // Carport, angebaut links am Haus: flaches Schrägdach auf zwei Stuetzen.
  svg.appendChild(
    svgEl('polygon', { points: '15,150 156,144 156,164 15,176', class: 'sb-carport-dach' })
  );
  svg.appendChild(svgEl('rect', { x: 24, y: 176, width: 8, height: 58, class: 'sb-carport-stuetze' }));
  svg.appendChild(svgEl('rect', { x: 140, y: 168, width: 8, height: 62, class: 'sb-carport-stuetze' }));

  // Hauswand und Satteldach.
  svg.appendChild(svgEl('rect', { x: 160, y: 160, width: 220, height: 90, rx: 3, class: 'sb-wand' }));
  svg.appendChild(
    svgEl('polygon', {
      points: `150,160 ${DACH_FIRST.x},${DACH_FIRST.y} ${DACH_TRAUFE.x},${DACH_TRAUFE.y}`,
      class: 'sb-dach',
    })
  );
  // Tuer und Fenster, rein dekorativ.
  svg.appendChild(svgEl('rect', { x: 258, y: 208, width: 26, height: 42, rx: 2, class: 'sb-oeffnung' }));
  svg.appendChild(svgEl('rect', { x: 195, y: 178, width: 26, height: 22, rx: 2, class: 'sb-oeffnung' }));
  svg.appendChild(svgEl('rect', { x: 320, y: 178, width: 26, height: 22, rx: 2, class: 'sb-oeffnung' }));

  // PV-Module auf der Dachschraege: je Modul drei uebereinanderliegende
  // Rechtecke (Grundflaeche, Helligkeit aus Messwert, Schattenband aus
  // Azimutprofil) plus Kontur.
  const modulHellRects = [];
  const modulSchattenRects = [];
  const modulBeschriftungen = [];
  MODUL_POSITIONEN.forEach((pos, i) => {
    const g = svgEl('g', { transform: `translate(${pos.x},${pos.y}) rotate(${DACH_WINKEL.toFixed(2)})` });
    g.appendChild(svgEl('rect', { x: -15, y: -8, width: 30, height: 16, rx: 2, class: 'sb-modul-basis' }));
    const hell = svgEl('rect', { x: -15, y: -8, width: 30, height: 16, rx: 2, class: 'sb-modul-hell' });
    g.appendChild(hell);
    const schatten = svgEl('rect', { x: -15, y: -8, width: 30, height: 100, class: 'sb-modul-schatten' });
    schatten.style.transform = 'scaleY(0)';
    g.appendChild(schatten);
    g.appendChild(svgEl('rect', { x: -15, y: -8, width: 30, height: 16, rx: 2, class: 'sb-modul-kontur' }));
    svg.appendChild(g);
    modulHellRects.push(hell);
    modulSchattenRects.push(schatten);

    const label = svgEl('text', { x: pos.x, y: pos.y - 14, class: 'sb-modul-label', 'text-anchor': 'middle' });
    label.textContent = `PV${i + 1}`;
    svg.appendChild(label);
    modulBeschriftungen.push(label);
  });

  // Speichersymbol (Batterie) mit fuellstandsabhaengiger Anzeige.
  svg.appendChild(svgEl('rect', { x: 195, y: 199, width: 6, height: 6, class: 'sb-batt-nub' }));
  svg.appendChild(svgEl('rect', { x: 185, y: BATT_OBEN, width: 26, height: BATT_UNTEN - BATT_OBEN, rx: 4, class: 'sb-batt-huelle' }));
  const battFuellung = svgEl('rect', { x: 187, y: BATT_UNTEN, width: 22, height: 0, class: 'sb-batt-fuellung' });
  svg.appendChild(battFuellung);
  svg.appendChild(svgEl('rect', { x: 185, y: BATT_OBEN, width: 26, height: BATT_UNTEN - BATT_OBEN, rx: 4, class: 'sb-batt-kontur' }));

  // Netzsymbol (Hausanschluss/Zaehler) am rechten Bildrand.
  svg.appendChild(svgEl('rect', { x: 412, y: 176, width: 30, height: 30, rx: 6, class: 'sb-netz-kasten' }));
  svg.appendChild(
    svgEl('path', {
      d: 'M424,182 L419,192 L426,192 L421,202 L433,188 L425,188 Z',
      class: 'sb-netz-blitz',
    })
  );

  // Flusspfade: sichtbare Linie plus Fliesspunkte je Verbindung. Bewusst als
  // letzte Gruppe angehaengt (liegt damit optisch ueber Haus und Modulen) -
  // eine Platzierung dahinter wirkte im Test unruhig, weil Wand und Dach
  // die Linien an mehreren Stellen zerschnitten.
  const fluesseGruppe = svgEl('g', { class: 'sb-fluesse' });
  svg.appendChild(fluesseGruppe);

  const linieBauen = (d, cssKlasse) => {
    const linie = svgEl('path', { d, class: `sb-fluss-linie ${cssKlasse}`, fill: 'none' });
    fluesseGruppe.appendChild(linie);
    return linie;
  };

  const linePvSpeicher = linieBauen(PFAD_PV_SPEICHER, 'sb-fluss-pv');
  const punktePvSpeicher = fliesspunkteBauen(fluesseGruppe, PFAD_PV_SPEICHER, 'sb-fluss-pv');
  const linePvHaus = linieBauen(PFAD_PV_HAUS, 'sb-fluss-pv');
  const punktePvHaus = fliesspunkteBauen(fluesseGruppe, PFAD_PV_HAUS, 'sb-fluss-pv');
  const lineSpeicherHaus = linieBauen(PFAD_SPEICHER_HAUS, 'sb-fluss-speicher');
  const punkteSpeicherHaus = fliesspunkteBauen(fluesseGruppe, PFAD_SPEICHER_HAUS, 'sb-fluss-speicher');
  const lineNetzHaus = linieBauen(PFAD_NETZ_HAUS, 'sb-fluss-netz');
  const punkteNetzHaus = fliesspunkteBauen(fluesseGruppe, PFAD_NETZ_HAUS, 'sb-fluss-netz');

  // Kompass-Andeutung der Blickrichtung (Suedwest).
  const kompass = svgEl('g', { class: 'sb-kompass' });
  kompass.appendChild(svgEl('circle', { cx: 36, cy: 36, r: 16 }));
  kompass.appendChild(svgEl('line', { x1: 36, y1: 36, x2: 47, y2: 47 }));
  const swLabel = svgEl('text', { x: 51, y: 51, class: 'sb-kompass-label' });
  swLabel.textContent = 'SW';
  kompass.appendChild(swLabel);
  svg.appendChild(kompass);

  // Schatten-Hinweistext (nur sichtbar, wenn ausserhalb des Profils).
  const schattenHinweis = document.createElement('p');
  schattenHinweis.className = 'sb-haus-schatten-hinweis';
  schattenHinweis.textContent =
    'Kein Schattenprofil fuer den aktuellen Sonnenstand (Azimut ausserhalb 135°–225° oder Elevation unter 10°).';
  schattenHinweis.hidden = true;
  bild.appendChild(schattenHinweis);

  // Textliche Kurzfassung des Flusses - fuer Screenreader und zur
  // Nachvollziehbarkeit, da die SVG-Animation selbst nicht vorlesbar ist.
  const legende = document.createElement('dl');
  legende.className = 'sb-haus-legende';
  const legendeFeld = (bezeichnung) => {
    const dt = document.createElement('dt');
    dt.className = 'label';
    dt.textContent = bezeichnung;
    const dd = document.createElement('dd');
    legende.appendChild(dt);
    legende.appendChild(dd);
    return dd;
  };
  const legPvSpeicher = legendeFeld('PV → Speicher');
  const legPvHaus = legendeFeld('PV → Haus');
  const legSpeicherHaus = legendeFeld('Speicher → Haus');
  const legNetz = legendeFeld('Netz ↔ Haus');
  wrap.appendChild(legende);

  /**
   * Aktualisiert Modulfarben, Schattenband, Flussanimation und Speicher-
   * fuellstand aus dem aktuellen ctx.data. Wird von der App im eigenen Takt
   * aufgerufen; ein einmaliger Aufruf direkt nach dem Bau sorgt fuer einen
   * korrekt gefuellten Erstzustand.
   */
  const update = () => {
    const data = ctx.data;

    // Modulhelligkeit: 100 % gemessener Leistungsanteil = hell, 0 % = dunkel.
    for (let i = 0; i < 4; i++) {
      const anteil = Math.min(100, Math.max(0, data.num(`sensor.pv_modul_${i + 1}_leistungsanteil`, 0)));
      modulHellRects[i].style.fillOpacity = String(0.12 + (anteil / 100) * 0.88);
      modulBeschriftungen[i].textContent = `PV${i + 1} ${data.fmtNum(anteil, 0)} %`;
    }

    // Schattenband aus Sonnenstand (sun.sun) und belegtem Azimutprofil.
    const azimut = data.attr('sun.sun', 'azimuth');
    const elevation = data.attr('sun.sun', 'elevation');
    const anteile = schattenAnteile(azimut, elevation);
    if (anteile) {
      schattenHinweis.hidden = true;
      for (let i = 0; i < 4; i++) {
        const abdeckung = 16 * ((100 - anteile[i]) / 100);
        modulSchattenRects[i].style.transform = `scaleY(${(abdeckung / 100).toFixed(4)})`;
        modulSchattenRects[i].style.opacity = '1';
      }
    } else {
      schattenHinweis.hidden = false;
      for (const r of modulSchattenRects) r.style.opacity = '0';
    }

    // Flusslogik. Es gibt keinen Sensor je Kante des Diagramms, nur die vier
    // Summenwerte unten - die Aufteilung ist eine plausible Naeherung fuer
    // die Anzeige (PV laedt zuerst den Speicher, der Rest geht ins Haus),
    // keine gemessene oder bilanzierte Groesse.
    const pv = Math.max(0, data.num(`${ANKER}_solarstrom`, 0));
    const battLade = Math.max(0, data.num(`${ANKER}_batterieladeleistung`, 0));
    const battEntlade = Math.max(0, data.num(`${ANKER}_batterieentladeleistung`, 0));
    const netzBezug = Math.max(0, data.num(`${ANKER}_netzbezugsleistung`, 0));
    const netzEinspeisung = Math.max(0, data.num(`${ANKER}_netzeinspeiseleistung`, 0));

    const pvZuSpeicher = Math.min(pv, battLade);
    const pvZuHaus = Math.max(0, pv - battLade);
    const speicherZuHaus = battEntlade;
    const netzRichtungHaus = netzBezug >= netzEinspeisung ? netzBezug : -netzEinspeisung;

    flussSetzen(linePvSpeicher, punktePvSpeicher, pvZuSpeicher);
    flussSetzen(linePvHaus, punktePvHaus, pvZuHaus);
    flussSetzen(lineSpeicherHaus, punkteSpeicherHaus, speicherZuHaus);
    flussSetzen(lineNetzHaus, punkteNetzHaus, netzRichtungHaus);

    legPvSpeicher.textContent = data.fmtW(pvZuSpeicher);
    legPvHaus.textContent = data.fmtW(pvZuHaus);
    legSpeicherHaus.textContent = data.fmtW(speicherZuHaus);
    legNetz.textContent =
      netzRichtungHaus >= 0 ? `Bezug ${data.fmtW(netzRichtungHaus)}` : `Einspeisung ${data.fmtW(-netzRichtungHaus)}`;

    // Speicherfuellstand am Symbol.
    const soc = Math.min(100, Math.max(0, data.num(`${ANKER}_soc`, 0)));
    // Volle Hoehe fest, Fuellstand ueber scaleY vom unteren Rand aus.
    // Geometrie und y bleiben konstant, animiert wird nur die Transformation.
    const voll = BATT_UNTEN - BATT_OBEN - 4;
    battFuellung.setAttribute('height', voll.toFixed(1));
    battFuellung.setAttribute('y', (BATT_UNTEN - 2 - voll).toFixed(1));
    battFuellung.style.transform = `scaleY(${(soc / 100).toFixed(4)})`;
  };

  wrap.update = update;
  update();
  return wrap;
}

// ---------------------------------------------------------------------------
// Styling der Hausansicht. Einmalig beim Laden des Moduls eingefuegt,
// dieselben M3-Tokens (mit Fallbacks) wie in views.js.
// ---------------------------------------------------------------------------
// Styles werden NICHT mehr in document.head gelegt, sondern als String
// exportiert. Die App rendert im Shadow DOM, und Regeln aus document.head
// ueberqueren diese Grenze nicht - die Ansichten waeren komplett ungestylt
// gewesen. app.js haengt sie zusammen mit M3_CSS in den Shadow Root.
export const HAUS_CSS = `
    .sb-haus {
      --sb-surface-container: var(--surface-container, #f3ecdf);
      --sb-surface-container-high: var(--surface-container-high, #ede4d3);
      --sb-surface-container-low: var(--surface-container-low, #faf3e6);
      --sb-on-surface: var(--on-surface, #1f1b13);
      --sb-on-surface-variant: var(--on-surface-variant, #4d4639);
      --sb-primary: var(--primary, #825500);
      --sb-on-primary-container: var(--on-primary-container, #2a1700);
      --sb-primary-container: var(--primary-container, #ffddb1);
      --sb-secondary: var(--secondary, #6f5b40);
      --sb-outline: var(--outline, #7d7667);
      --sb-outline-variant: var(--outline-variant, #cec5b4);
      --sb-corner-l: var(--corner-l, 16px);
      --sb-corner-xl: var(--corner-xl, 28px);
      display: flex;
      flex-direction: column;
      gap: 10px;
      font-family: Roboto, system-ui, sans-serif;
      color: var(--sb-on-surface);
    }
    @media (prefers-color-scheme: dark) {
      .sb-haus {
        --sb-surface-container: var(--surface-container, #251f13);
        --sb-surface-container-high: var(--surface-container-high, #302918);
        --sb-surface-container-low: var(--surface-container-low, #1f1b10);
        --sb-on-surface: var(--on-surface, #ebe1d4);
        --sb-on-surface-variant: var(--on-surface-variant, #d0c5b4);
        --sb-primary: var(--primary, #ffb951);
        --sb-on-primary-container: var(--on-primary-container, #ffddb1);
        --sb-primary-container: var(--primary-container, #633f00);
        --sb-secondary: var(--secondary, #dbc3a4);
        --sb-outline: var(--outline, #988f7f);
        --sb-outline-variant: var(--outline-variant, #4d4639);
      }
    }

    .sb-haus-chip {
      display: flex;
      align-items: center;
      gap: 8px;
      align-self: flex-start;
      background: var(--sb-primary-container);
      color: var(--sb-on-primary-container);
      border-radius: var(--sb-corner-xl);
      padding: 8px 16px;
      font-size: 0.85rem;
      font-weight: 500;
      max-width: 100%;
    }

    .sb-haus-bild {
      background: var(--sb-surface-container-low);
      border-radius: var(--sb-corner-l);
      overflow: hidden;
      position: relative;
    }
    .sb-haus-bild svg { width: 100%; height: auto; display: block; }

    .sb-himmel { fill: var(--sb-surface-container-low); }
    .sb-boden { fill: var(--sb-surface-container); }
    .sb-carport-dach { fill: var(--sb-outline-variant); }
    .sb-carport-stuetze { fill: var(--sb-outline); }
    .sb-wand { fill: var(--sb-surface-container-high); stroke: var(--sb-outline-variant); stroke-width: 1; }
    .sb-dach { fill: var(--sb-secondary); }
    .sb-oeffnung { fill: var(--sb-surface-container-low); stroke: var(--sb-outline-variant); stroke-width: 1; }

    .sb-modul-basis { fill: var(--sb-outline-variant); }
    .sb-modul-hell { fill: var(--sb-primary); transition: fill-opacity 600ms ease; }
    /* scaleY statt height: eine Geometrieaenderung zwingt den Renderer zum
       Neuaufbau, eine Transformation laeuft auf dem Compositor. Die Hoehe
       bleibt fest, skaliert wird von der Oberkante nach unten. */
    .sb-modul-schatten { fill: rgba(10, 8, 4, 0.55);
      transform-origin: top; transition: transform 600ms ease; }
    .sb-modul-kontur { fill: none; stroke: var(--sb-outline); stroke-width: 0.75; }
    .sb-modul-label { font-size: 8px; fill: var(--sb-on-surface-variant); }

    .sb-batt-huelle, .sb-batt-kontur { fill: none; stroke: var(--sb-outline); stroke-width: 1.2; }
    .sb-batt-nub { fill: var(--sb-outline); }
    /* Wie beim Schatten: skalieren statt Geometrie animieren. Ursprung
       unten, damit die Fuellung von unten waechst - das ersetzt zugleich
       die y-Animation. */
    .sb-batt-fuellung { fill: var(--sb-primary);
      transform-origin: bottom; transition: transform 600ms ease; }

    .sb-netz-kasten { fill: var(--sb-surface-container-high); stroke: var(--sb-outline-variant); stroke-width: 1; }
    .sb-netz-blitz { fill: var(--sb-secondary); }

    .sb-fluss-linie { stroke-linecap: round; transition: stroke-width 400ms ease, opacity 400ms ease; }
    .sb-fluss-pv { stroke: var(--sb-primary); }
    .sb-fluss-speicher { stroke: var(--sb-secondary); }
    .sb-fluss-netz { stroke: var(--sb-outline); }

    .sb-fliesspunkt {
      fill: var(--sb-primary);
      animation-name: sb-fliessen;
      animation-timing-function: linear;
      animation-iteration-count: infinite;
      transition: opacity 300ms ease;
    }
    @keyframes sb-fliessen {
      from { offset-distance: 0%; }
      to { offset-distance: 100%; }
    }
    @media (prefers-reduced-motion: reduce) {
      .sb-fliesspunkt { animation-play-state: paused !important; }
    }

    .sb-kompass circle { fill: var(--sb-surface-container-high); stroke: var(--sb-outline); stroke-width: 1; }
    .sb-kompass line { stroke: var(--sb-outline); stroke-width: 1.5; }
    .sb-kompass-label { font-size: 10px; fill: var(--sb-on-surface-variant); }

    .sb-haus-schatten-hinweis {
      position: absolute;
      left: 12px;
      bottom: 12px;
      right: 12px;
      margin: 0;
      font-size: 0.78rem;
      color: var(--sb-on-surface-variant);
      background: var(--sb-surface-container-high);
      border-radius: 8px;
      padding: 6px 10px;
    }

    .sb-haus-legende {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
      gap: 8px 16px;
      margin: 0;
      padding: 12px 16px;
      background: var(--sb-surface-container);
      border-radius: var(--sb-corner-l);
    }
    .sb-haus-legende dt { font-size: 0.72rem; color: var(--sb-on-surface-variant); }
    .sb-haus-legende dd { margin: 0; font-size: 1rem; font-weight: 600; }
`;
