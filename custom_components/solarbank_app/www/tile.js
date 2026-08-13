/**
 * tile.js — Kachel mit Aufklapp-Historie und Sparkline.
 *
 * Stellt das Custom Element <sb-tile> sowie die Factory-Funktion `tile()`
 * bereit. Zeigt Label, Wert und Einheit einer Entity; beim Antippen klappt
 * ein Bereich mit 24-h-/7-Tage-Verlauf, Min/Max/Mittel, letzter Änderung,
 * Entity-ID und Herkunftstext auf.
 *
 * Reines ES-Modul, kein Build-Schritt. Farben kommen ausschließlich aus den
 * global vom Panel gesetzten `--md-sys-color-*`-Variablen — hier wird
 * nichts an globalem CSS injiziert, nur lokal referenziert (mit defensiven
 * Rückfallwerten für den Fall, dass eine Kachel einmal isoliert getestet
 * wird).
 */

import { icon, ripple } from './m3.js';

// -- Konstanten --------------------------------------------------------------

const BEREICH_24H = '24h';
const BEREICH_7T = '7d';

// M3-Bewegungsvorgabe für das Aufklappen: "emphasized", 300 ms.
const MOTION_DAUER_MS = 300;
const MOTION_EASING = 'cubic-bezier(0.2, 0, 0, 1)';

// Innenmaße der Sparkline-Zeichenfläche (SVG-viewBox).
const CHART_BREITE = 300;
const CHART_HOEHE = 80;
const CHART_PADDING_Y = 6;

/**
 * Wandelt eine Punktfolge {x,y} in einen weichen SVG-Pfad um (kubische
 * Bézier-Kurven, Catmull-Rom-Näherung mit Spannung 1/6 — der Standardweg,
 * um ohne externe Bibliothek eine sanfte Kurve durch Messpunkte zu legen).
 */
function weicherPfad(punkte) {
  if (punkte.length === 0) return '';
  if (punkte.length === 1) return `M ${punkte[0].x} ${punkte[0].y}`;

  let d = `M ${punkte[0].x} ${punkte[0].y}`;
  for (let i = 0; i < punkte.length - 1; i++) {
    const p0 = punkte[i === 0 ? 0 : i - 1];
    const p1 = punkte[i];
    const p2 = punkte[i + 1];
    const p3 = punkte[i + 2 < punkte.length ? i + 2 : i + 1];

    const cp1x = p1.x + (p2.x - p0.x) / 6;
    const cp1y = p1.y + (p2.y - p0.y) / 6;
    const cp2x = p2.x - (p3.x - p1.x) / 6;
    const cp2y = p2.y - (p3.y - p1.y) / 6;

    d += ` C ${cp1x.toFixed(2)} ${cp1y.toFixed(2)}, ${cp2x.toFixed(2)} ${cp2y.toFixed(2)}, ${p2.x.toFixed(2)} ${p2.y.toFixed(2)}`;
  }
  return d;
}

export class SbTile extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });

    // -- Properties (per JS gesetzt, siehe Getter/Setter unten) -----------
    this._data = null;
    this._entity = null;
    this._label = '';
    this._unit = null; // null = aus Data ableiten, sonst Override
    this._digits = null; // null = Format-Standard nutzen (fmtNum/fmtKWh)
    this._icon = null;
    this._hint = '';
    this._readonly = true;
    this._format = 'num';

    // -- interner Zustand ---------------------------------------------------
    this._expanded = false;
    this._loadedOnce = false;
    this._loading = false;
    this._range = BEREICH_24H;
    this._points = null; // geladene {t, v}-Punkte des aktuellen Fensters
    this._loadToken = 0; // verwirft veraltete asynchrone Antworten (Entity-Wechsel während des Ladens)
    this._listenersBound = false;
    this._built = false;

    this._buildDom();
  }

  // ---------------------------------------------------------------------
  // Properties
  // ---------------------------------------------------------------------

  get data() {
    return this._data;
  }

  set data(v) {
    this._data = v;
    this.update();
  }

  get entity() {
    return this._entity;
  }

  set entity(v) {
    if (v === this._entity) return;
    this._entity = v;
    // Entity gewechselt: bereits geladene Historie gehört zur alten Entity.
    this._points = null;
    this._loadedOnce = false;
    this.update();
    this._renderChart();
    this._renderStats();
    if (this._expanded) {
      // Bereits aufgeklappt: sofort für die neue Entity nachladen, statt
      // erst beim nächsten Zu-/Aufklappen (siehe _onToggle-Logik).
      this._loadedOnce = true;
      this._loadRange(this._range);
    }
  }

  get label() {
    return this._label;
  }

  set label(v) {
    this._label = v || '';
    this.update();
  }

  get unit() {
    return this._unit;
  }

  set unit(v) {
    this._unit = v;
    this.update();
  }

  get digits() {
    return this._digits;
  }

  set digits(v) {
    this._digits = v;
    this.update();
  }

  get icon() {
    return this._icon;
  }

  set icon(v) {
    this._icon = v;
    this._renderIcon();
  }

  get hint() {
    return this._hint;
  }

  set hint(v) {
    this._hint = v || '';
    this._renderHint();
  }

  get readonly() {
    return this._readonly;
  }

  set readonly(v) {
    this._readonly = !!v;
    this.toggleAttribute('readonly', this._readonly);
    this._renderEditIndicator();
  }

  get format() {
    return this._format;
  }

  set format(v) {
    this._format = v || 'num';
    this.update();
  }

  // ---------------------------------------------------------------------
  // Lifecycle
  // ---------------------------------------------------------------------

  connectedCallback() {
    if (!this._listenersBound) {
      this._bindEvents();
      this._listenersBound = true;
      // Ripple auf allen Tap-Zielen, wie im M3-Plan gefordert. ripple()
      // kommt aus m3.js — falls dessen Vertrag abweicht, bleibt die Kachel
      // ohne visuellen Ripple trotzdem voll bedienbar.
      try {
        ripple(this._header);
        ripple(this._seg24);
        ripple(this._seg7);
      } catch (e) {
        /* ripple() optional */
      }
    }
    this._renderIcon();
    this._renderHint();
    this._renderEditIndicator();
    this.update();
  }

  // ---------------------------------------------------------------------
  // Öffentliche API
  // ---------------------------------------------------------------------

  /**
   * Liest den aktuellen Zustand aus `data` neu und aktualisiert die
   * Anzeige. Die App ruft dies im Takt auf — die Methode fasst nur
   * bereits vorhandene Daten an, löst nie selbst einen Netzzugriff aus.
   */
  update() {
    if (!this._built) return;

    this._labelEl.textContent = this._label || (this._data && this._entity ? this._data.name(this._entity) : '');

    if (this._data && this._entity) {
      const { zahl, einheit } = this._formatiereHauptwert();
      this._valueEl.textContent = zahl;
      this._unitEl.textContent = einheit;
      this._entityIdEl.textContent = this._entity;
      this._changedEl.textContent = this._data.fmtZeit(this._data.lastChanged(this._entity));
    } else {
      this._valueEl.textContent = '–';
      this._unitEl.textContent = '';
      this._entityIdEl.textContent = this._entity || '–';
      this._changedEl.textContent = '–';
    }

    // Min/Max/Mittel aus bereits geladenen Punkten neu berechnen — kein
    // Netzzugriff, daher unbedenklich bei jedem Takt.
    this._renderStats();
  }

  // ---------------------------------------------------------------------
  // Aufbau des Shadow DOM (einmalig im Konstruktor)
  // ---------------------------------------------------------------------

  _buildDom() {
    this.shadowRoot.innerHTML = `
      <style>
        * { box-sizing: border-box; }

        :host {
          display: block;
          font-family: inherit;
          color: var(--md-sys-color-on-surface, #1c1b1f);
        }

        .tile {
          border-radius: var(--md-sys-shape-corner-large, 16px);
          background: var(--md-sys-color-surface-container, #f3edf7);
          overflow: hidden;
        }

        .header {
          display: flex;
          align-items: center;
          gap: 12px;
          min-height: 48px;
          padding: 12px 16px;
          cursor: pointer;
          user-select: none;
          position: relative;
        }

        .header:focus-visible {
          outline: 2px solid var(--md-sys-color-primary, #6750a4);
          outline-offset: -2px;
          border-radius: var(--md-sys-shape-corner-large, 16px);
        }

        .header:hover {
          background: color-mix(in srgb, var(--md-sys-color-on-surface, #1c1b1f) 8%, transparent);
        }

        .icon {
          flex: none;
          width: 24px;
          height: 24px;
          display: flex;
          align-items: center;
          justify-content: center;
          color: var(--md-sys-color-primary, #6750a4);
        }
        .icon[hidden] { display: none; }
        .icon svg, .icon ha-icon { width: 100%; height: 100%; }

        .text {
          flex: 1 1 auto;
          min-width: 0;
          display: flex;
          flex-direction: column;
          gap: 2px;
        }

        .label {
          font-size: 0.8125rem;
          line-height: 1.2;
          color: var(--md-sys-color-on-surface-variant, #49454f);
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }

        .value-row {
          display: flex;
          align-items: baseline;
          gap: 4px;
        }

        .value {
          font-size: 1.375rem;
          font-weight: 500;
          line-height: 1.2;
        }

        .unit {
          font-size: 0.8125rem;
          color: var(--md-sys-color-on-surface-variant, #49454f);
        }

        .edit-indicator {
          flex: none;
          width: 8px;
          height: 8px;
          border-radius: 50%;
          background: var(--md-sys-color-primary, #6750a4);
        }
        .edit-indicator[hidden] { display: none; }

        .chevron {
          flex: none;
          width: 24px;
          height: 24px;
          display: flex;
          align-items: center;
          justify-content: center;
          color: var(--md-sys-color-on-surface-variant, #49454f);
          transition: transform ${MOTION_DAUER_MS}ms ${MOTION_EASING};
        }
        .chevron.is-open { transform: rotate(180deg); }

        /* Aufklapp-Animation ohne Höhenmessung per JS: Grid-Zeile von 0fr
           auf 1fr, darin ein Container mit overflow: hidden. */
        .details-outer {
          display: grid;
          grid-template-rows: 0fr;
          transition: grid-template-rows ${MOTION_DAUER_MS}ms ${MOTION_EASING};
        }
        .details-outer.is-open {
          grid-template-rows: 1fr;
        }
        .details-inner {
          overflow: hidden;
          min-height: 0;
        }

        .details-content {
          padding: 4px 16px 16px 16px;
          border-top: 1px solid var(--md-sys-color-outline-variant, #cac4d0);
          display: flex;
          flex-direction: column;
          gap: 14px;
        }

        .range-switch {
          display: inline-flex;
          align-self: flex-start;
          border: 1px solid var(--md-sys-color-outline, #79747e);
          border-radius: 999px;
          overflow: hidden;
          margin-top: 12px;
        }

        .seg {
          appearance: none;
          border: none;
          background: transparent;
          color: var(--md-sys-color-on-surface, #1c1b1f);
          font: inherit;
          font-size: 0.8125rem;
          padding: 6px 16px;
          min-height: 32px;
          cursor: pointer;
          position: relative;
        }
        .seg + .seg {
          border-left: 1px solid var(--md-sys-color-outline, #79747e);
        }
        .seg.is-selected {
          background: var(--md-sys-color-secondary-container, #e8def8);
          color: var(--md-sys-color-on-secondary-container, #1d192b);
          font-weight: 500;
        }
        .seg:focus-visible {
          outline: 2px solid var(--md-sys-color-primary, #6750a4);
          outline-offset: -2px;
        }

        .chart-wrap {
          position: relative;
          width: 100%;
          height: ${CHART_HOEHE}px;
        }

        .chart {
          width: 100%;
          height: 100%;
          display: block;
        }

        .chart-area {
          fill: var(--md-sys-color-primary, #6750a4);
          fill-opacity: 0.12;
          stroke: none;
        }

        .chart-line {
          fill: none;
          stroke: var(--md-sys-color-primary, #6750a4);
          stroke-width: 2;
          stroke-linecap: round;
          stroke-linejoin: round;
        }

        .chart-empty,
        .chart-loading {
          position: absolute;
          inset: 0;
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 0.8125rem;
          color: var(--md-sys-color-on-surface-variant, #49454f);
        }
        .chart-empty[hidden],
        .chart-loading[hidden] { display: none; }

        .spinner {
          width: 14px;
          height: 14px;
          margin-right: 8px;
          border-radius: 50%;
          border: 2px solid var(--md-sys-color-outline-variant, #cac4d0);
          border-top-color: var(--md-sys-color-primary, #6750a4);
          display: inline-block;
          animation: sb-tile-spin 0.8s linear infinite;
        }
        @keyframes sb-tile-spin {
          to { transform: rotate(360deg); }
        }

        .stats {
          display: grid;
          grid-template-columns: repeat(2, minmax(0, 1fr));
          gap: 10px 16px;
          margin: 0;
        }
        .stat { display: flex; flex-direction: column; gap: 2px; }
        .stat dt {
          font-size: 0.75rem;
          color: var(--md-sys-color-on-surface-variant, #49454f);
        }
        .stat dd {
          margin: 0;
          font-size: 0.9375rem;
          font-weight: 500;
        }

        .meta-row {
          display: flex;
          align-items: baseline;
          gap: 8px;
          font-size: 0.8125rem;
        }
        .meta-row[hidden] { display: none; }
        .meta-label {
          flex: none;
          color: var(--md-sys-color-on-surface-variant, #49454f);
        }
        .entity-id {
          font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
          font-size: 0.75rem;
          word-break: break-all;
        }
        .hint-text {
          color: var(--md-sys-color-on-surface-variant, #49454f);
        }

        /* Barrierefreiheit: reduzierte Bewegung respektieren (M3-Plan §3). */
        @media (prefers-reduced-motion: reduce) {
          .chevron, .details-outer { transition-duration: 0.01ms; }
        }
      </style>

      <div class="tile" part="tile">
        <div class="header" tabindex="0" role="button" aria-expanded="false" aria-controls="details">
          <span class="icon" hidden aria-hidden="true"></span>
          <span class="text">
            <span class="label"></span>
            <span class="value-row">
              <span class="value">–</span>
              <span class="unit"></span>
            </span>
          </span>
          <span class="edit-indicator" hidden title="beschreibbar" aria-hidden="true"></span>
          <span class="chevron" aria-hidden="true">
            <svg viewBox="0 0 24 24"><path d="M7 10l5 5 5-5z" fill="currentColor"/></svg>
          </span>
        </div>

        <div class="details-outer" id="details">
          <div class="details-inner">
            <div class="details-content">
              <div class="range-switch" role="group" aria-label="Zeitfenster">
                <button type="button" class="seg seg-24h is-selected" aria-pressed="true">24 h</button>
                <button type="button" class="seg seg-7d" aria-pressed="false">7 Tage</button>
              </div>

              <div class="chart-wrap">
                <svg class="chart" viewBox="0 0 ${CHART_BREITE} ${CHART_HOEHE}" preserveAspectRatio="none" aria-hidden="true">
                  <path class="chart-area" d=""></path>
                  <path class="chart-line" d=""></path>
                </svg>
                <div class="chart-empty" hidden>Kein Verlauf im Fenster</div>
                <div class="chart-loading" hidden><span class="spinner"></span>Lade Verlauf …</div>
              </div>

              <dl class="stats">
                <div class="stat"><dt>Min</dt><dd class="stat-min">–</dd></div>
                <div class="stat"><dt>Max</dt><dd class="stat-max">–</dd></div>
                <div class="stat"><dt>Mittel</dt><dd class="stat-mean">–</dd></div>
                <div class="stat"><dt>Geändert</dt><dd class="stat-changed">–</dd></div>
              </dl>

              <div class="meta-row">
                <span class="meta-label">Entity</span>
                <code class="entity-id"></code>
              </div>
              <div class="meta-row hint-row" hidden>
                <span class="meta-label">Herkunft</span>
                <span class="hint-text"></span>
              </div>
            </div>
          </div>
        </div>
      </div>
    `;

    // Referenzen einsammeln, statt bei jedem Render neu zu suchen.
    this._header = this.shadowRoot.querySelector('.header');
    this._iconEl = this.shadowRoot.querySelector('.icon');
    this._labelEl = this.shadowRoot.querySelector('.label');
    this._valueEl = this.shadowRoot.querySelector('.value');
    this._unitEl = this.shadowRoot.querySelector('.unit');
    this._editIndicatorEl = this.shadowRoot.querySelector('.edit-indicator');
    this._chevronEl = this.shadowRoot.querySelector('.chevron');
    this._detailsOuter = this.shadowRoot.querySelector('.details-outer');
    this._seg24 = this.shadowRoot.querySelector('.seg-24h');
    this._seg7 = this.shadowRoot.querySelector('.seg-7d');
    this._svgEl = this.shadowRoot.querySelector('.chart');
    this._areaPath = this.shadowRoot.querySelector('.chart-area');
    this._linePath = this.shadowRoot.querySelector('.chart-line');
    this._emptyEl = this.shadowRoot.querySelector('.chart-empty');
    this._loadingEl = this.shadowRoot.querySelector('.chart-loading');
    this._statMinEl = this.shadowRoot.querySelector('.stat-min');
    this._statMaxEl = this.shadowRoot.querySelector('.stat-max');
    this._statMeanEl = this.shadowRoot.querySelector('.stat-mean');
    this._changedEl = this.shadowRoot.querySelector('.stat-changed');
    this._entityIdEl = this.shadowRoot.querySelector('.entity-id');
    this._hintRowEl = this.shadowRoot.querySelector('.hint-row');
    this._hintTextEl = this.shadowRoot.querySelector('.hint-text');

    this._built = true;
  }

  // ---------------------------------------------------------------------
  // Ereignisse
  // ---------------------------------------------------------------------

  _bindEvents() {
    this._header.addEventListener('click', () => this._onToggle());
    this._header.addEventListener('keydown', (ev) => {
      if (ev.key === 'Enter' || ev.key === ' ' || ev.key === 'Spacebar') {
        ev.preventDefault();
        this._onToggle();
      }
    });

    this._seg24.addEventListener('click', (ev) => {
      ev.stopPropagation(); // nicht zusätzlich den Header togglen
      this._waehleBereich(BEREICH_24H);
      this._loadRange(BEREICH_24H);
    });
    this._seg7.addEventListener('click', (ev) => {
      ev.stopPropagation();
      this._waehleBereich(BEREICH_7T);
      this._loadRange(BEREICH_7T);
    });
  }

  _onToggle() {
    this._expanded = !this._expanded;
    this._header.setAttribute('aria-expanded', String(this._expanded));
    this._detailsOuter.classList.toggle('is-open', this._expanded);
    this._chevronEl.classList.toggle('is-open', this._expanded);

    if (this._expanded && !this._loadedOnce) {
      this._loadedOnce = true;
      this._loadRange(this._range);
    }
  }

  _waehleBereich(range) {
    this._range = range;
    const ist24h = range === BEREICH_24H;
    this._seg24.classList.toggle('is-selected', ist24h);
    this._seg24.setAttribute('aria-pressed', String(ist24h));
    this._seg7.classList.toggle('is-selected', !ist24h);
    this._seg7.setAttribute('aria-pressed', String(!ist24h));
  }

  // ---------------------------------------------------------------------
  // Historie laden
  // ---------------------------------------------------------------------

  async _loadRange(range) {
    if (!this._data || !this._entity) {
      this._points = [];
      this._renderChart();
      this._renderStats();
      return;
    }

    this._range = range;
    this._setLoading(true);
    const token = ++this._loadToken;

    let punkte = [];
    try {
      punkte = range === BEREICH_7T
        ? await this._data.statistics(this._entity, 7)
        : await this._data.history(this._entity, 24);
    } catch (e) {
      // Data.history/statistics werfen laut Vertrag nie — dies ist nur
      // eine zusätzliche Absicherung gegen unerwartete Fehler.
      punkte = [];
    }

    if (token !== this._loadToken) return; // Entity/Bereich hat sich zwischenzeitlich geändert

    this._points = Array.isArray(punkte) ? punkte : [];
    this._setLoading(false);
    this._renderChart();
    this._renderStats();
  }

  _setLoading(istAmLaden) {
    this._loading = istAmLaden;
    this._loadingEl.hidden = !istAmLaden;
    if (istAmLaden) {
      this._emptyEl.hidden = true;
      this._svgEl.style.visibility = 'hidden';
    }
  }

  // ---------------------------------------------------------------------
  // Sparkline zeichnen
  // ---------------------------------------------------------------------

  _renderChart() {
    if (this._loading) return; // während des Ladens keine (halb-)fertige Grafik zeigen

    const punkte = this._points || [];
    if (punkte.length === 0) {
      this._emptyEl.hidden = false;
      this._svgEl.style.visibility = 'hidden';
      this._areaPath.setAttribute('d', '');
      this._linePath.setAttribute('d', '');
      return;
    }

    this._emptyEl.hidden = true;
    this._svgEl.style.visibility = 'visible';

    const t0 = punkte[0].t.getTime();
    const t1 = punkte[punkte.length - 1].t.getTime();
    const zeitspanne = Math.max(1, t1 - t0);

    let minV = Infinity;
    let maxV = -Infinity;
    for (const p of punkte) {
      if (p.v < minV) minV = p.v;
      if (p.v > maxV) maxV = p.v;
    }
    if (minV === maxV) {
      // Flache Linie: Wertebereich künstlich aufspreizen, sonst Division durch 0.
      minV -= 1;
      maxV += 1;
    }

    const xy = punkte.map((p) => {
      const x = punkte.length === 1
        ? CHART_BREITE / 2
        : ((p.t.getTime() - t0) / zeitspanne) * CHART_BREITE;
      const y = CHART_PADDING_Y + (1 - (p.v - minV) / (maxV - minV)) * (CHART_HOEHE - 2 * CHART_PADDING_Y);
      return { x, y };
    });

    const linienPfad = weicherPfad(xy);
    this._linePath.setAttribute('d', linienPfad);

    const erster = xy[0];
    const letzter = xy[xy.length - 1];
    const flaechenPfad = `${linienPfad} L ${letzter.x.toFixed(2)} ${CHART_HOEHE} L ${erster.x.toFixed(2)} ${CHART_HOEHE} Z`;
    this._areaPath.setAttribute('d', flaechenPfad);
  }

  // ---------------------------------------------------------------------
  // Min/Max/Mittel
  // ---------------------------------------------------------------------

  _renderStats() {
    const punkte = this._points;
    if (!punkte || punkte.length === 0) {
      this._statMinEl.textContent = '–';
      this._statMaxEl.textContent = '–';
      this._statMeanEl.textContent = '–';
      return;
    }

    let min = Infinity;
    let max = -Infinity;
    let summe = 0;
    for (const p of punkte) {
      if (p.v < min) min = p.v;
      if (p.v > max) max = p.v;
      summe += p.v;
    }
    const mittel = summe / punkte.length;

    this._statMinEl.textContent = this._formatiereZahlFuerStatistik(min);
    this._statMaxEl.textContent = this._formatiereZahlFuerStatistik(max);
    this._statMeanEl.textContent = this._formatiereZahlFuerStatistik(mittel);
  }

  // ---------------------------------------------------------------------
  // Formatierung
  // ---------------------------------------------------------------------

  /**
   * Formatiert den aktuellen Entity-Zustand gemäß `format` und liefert
   * Zahl und Einheit getrennt, damit sie im Markup unterschiedlich groß
   * dargestellt werden können.
   */
  _formatiereHauptwert() {
    const roh = this._data.state(this._entity);

    switch (this._format) {
      case 'watt': {
        const n = this._data.num(this._entity, null);
        if (n === null) return { zahl: '–', einheit: '' };
        return this._teileFormatiertenText(this._data.fmtW(n));
      }
      case 'kwh': {
        const n = this._data.num(this._entity, null);
        if (n === null) return { zahl: '–', einheit: '' };
        return this._teileFormatiertenText(this._data.fmtKWh(n, this._digits ?? 2));
      }
      case 'zeit':
        return { zahl: this._data.fmtZeit(roh), einheit: '' };
      case 'raw':
        return { zahl: roh === null || roh === undefined ? '–' : String(roh), einheit: '' };
      case 'num':
      default: {
        const n = this._data.num(this._entity, null);
        return { zahl: this._data.fmtNum(n, this._digits ?? 1), einheit: this._effektiveEinheit() };
      }
    }
  }

  /** Zerlegt z. B. "1,34 kW" in { zahl: "1,34", einheit: "kW" } für die zweispaltige Anzeige. */
  _teileFormatiertenText(text) {
    if (!text || text === '–') return { zahl: text || '–', einheit: '' };
    const idx = text.lastIndexOf(' ');
    if (idx === -1) return { zahl: text, einheit: '' };
    return { zahl: text.slice(0, idx), einheit: text.slice(idx + 1) };
  }

  _effektiveEinheit() {
    if (this._unit !== null && this._unit !== undefined) return this._unit;
    if (!this._data || !this._entity) return '';
    return this._data.unit(this._entity);
  }

  /** Formatiert eine beliebige Zahl (Min/Max/Mittel) nach demselben Format wie der Hauptwert. */
  _formatiereZahlFuerStatistik(n) {
    if (n === null || n === undefined || Number.isNaN(n)) return '–';
    switch (this._format) {
      case 'watt':
        return this._data.fmtW(n);
      case 'kwh':
        return this._data.fmtKWh(n, this._digits ?? 2);
      default: {
        const text = this._data.fmtNum(n, this._digits ?? 1);
        const einheit = this._effektiveEinheit();
        return einheit ? `${text} ${einheit}` : text;
      }
    }
  }

  // ---------------------------------------------------------------------
  // Icon / Hinweis / Schreibindikator
  // ---------------------------------------------------------------------

  _renderIcon() {
    if (!this._iconEl) return;
    this._iconEl.innerHTML = '';
    if (!this._icon) {
      this._iconEl.hidden = true;
      return;
    }
    this._iconEl.hidden = false;
    try {
      const ergebnis = icon(this._icon);
      if (ergebnis instanceof Node) {
        this._iconEl.appendChild(ergebnis);
      } else if (typeof ergebnis === 'string') {
        this._iconEl.innerHTML = ergebnis;
      }
    } catch (e) {
      // icon() aus m3.js nicht verfügbar oder Name unbekannt — die Kachel
      // bleibt auch ohne Icon voll nutzbar.
    }
  }

  _renderHint() {
    if (!this._hintRowEl) return;
    if (this._hint) {
      this._hintRowEl.hidden = false;
      this._hintTextEl.textContent = this._hint;
    } else {
      this._hintRowEl.hidden = true;
    }
  }

  _renderEditIndicator() {
    if (!this._editIndicatorEl) return;
    // Sichtbarer Punkt nur, wenn die Kachel NICHT schreibgeschützt ist —
    // macht auf einen Blick den Unterschied zu reinen solarbank_pv-Werten,
    // die laut Sicherheitsregel in docs/APP-PLAN.md §2 immer readonly sind.
    this._editIndicatorEl.hidden = this._readonly;
  }
}

customElements.define('sb-tile', SbTile);

/**
 * Factory: erzeugt eine <sb-tile> und überträgt `opts` als Properties
 * (nicht als HTML-Attribute — das Element erwartet echte JS-Werte wie die
 * Data-Instanz).
 */
export function tile(opts = {}) {
  const el = document.createElement('sb-tile');
  for (const [key, value] of Object.entries(opts)) {
    el[key] = value;
  }
  return el;
}
