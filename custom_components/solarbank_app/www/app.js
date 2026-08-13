/**
 * app.js — Panel-Element, Router, Shell der Solarbank-App.
 *
 * Reines ES-Modul, kein Build-Schritt. Home Assistant lädt diese Datei als
 * `panel_custom`-Modul (siehe const.py: PANEL_MODULE = "app.js") und
 * instanziiert das hier definierte Element `solarbank-app`
 * (PANEL_ELEMENT). Kein iframe, kein Login, kein Token — HA setzt das
 * `hass`-Objekt direkt als Property auf das Element.
 *
 * Aufbau:
 *   - Shadow DOM, M3_CSS wird einmal injiziert.
 *   - Router über location.hash (#/system, #/pv, …), Fallback auf die
 *     erste Ansicht aus VIEWS.
 *   - `set hass` bleibt absichtlich billig: es hält nur die Referenz in
 *     der Data-Brücke aktuell und stößt _tick() an. _tick() aktualisiert
 *     Statuspunkt und Datenschnitt-Banner nur bei tatsächlicher Änderung
 *     und ruft — falls vorhanden — die leichtgewichtige update()-Methode
 *     der aktiven Ansicht auf, statt sie neu aufzubauen. Ein voller
 *     Neuaufbau (build()) passiert nur bei einem Navigationswechsel.
 */

import { M3_CSS, icon, ripple } from './m3.js';
import { Data } from './data.js';
import { VIEWS } from './views.js';

// Entity, aus der der Statuspunkt in der Kopfzeile abgeleitet wird.
const STATUS_ENTITY = 'sensor.solarbank_diagnose_gesamtzustand';

// Datenschnitt laut FOLGEAUFTRAG.md 7.23: Werte vor diesem Zeitpunkt sind
// nicht verwertbar. 14.08.2026, 00:00 Uhr lokal (Monat 0-indiziert: 7 = August).
const DATENSCHNITT_ENDE = new Date(2026, 7, 14, 0, 0, 0, 0).getTime();
const DATENSCHNITT_TEXT = 'Datenschnitt: Werte sind erst ab 14.08.2026 00:00 verwertbar.';

class SolarbankApp extends HTMLElement {
  constructor() {
    super();
    this._root = this.attachShadow({ mode: 'open' });

    // Data ist die einzige Brücke zu hass — siehe data.js. Sie existiert
    // unabhängig davon, ob schon ein hass-Objekt vorliegt.
    this._data = new Data();

    this._built = false;
    this._activeViewId = null;
    this._activeViewNode = null;

    // Zuletzt angewandte Werte, um bei jedem _tick() unnötige DOM-Schreiben
    // zu vermeiden (Kern der Effizienzanforderung an set hass).
    this._lastStatus = null;
    this._lastBannerShown = null;

    // Referenzen auf DOM-Knoten der Shell, in _buildShell() befüllt.
    this._statusDotEl = null;
    this._bannerEl = null;
    this._mainEl = null;
    this._navBarEl = null;
    this._navRailEl = null;
    this._navItems = [];

    this._onHashChange = this._onHashChange.bind(this);
  }

  // -------------------------------------------------------------------
  // Lifecycle
  // -------------------------------------------------------------------

  connectedCallback() {
    this._ensureBuilt();
    window.addEventListener('hashchange', this._onHashChange);
    this._route();
  }

  disconnectedCallback() {
    window.removeEventListener('hashchange', this._onHashChange);
  }

  /**
   * Von Home Assistant bei JEDEM State-Update aufgerufen — muss effizient
   * bleiben. Baut NICHT die Ansicht neu, sondern hält nur die Datenbrücke
   * aktuell und delegiert an _tick().
   */
  set hass(hass) {
    this._data.hass = hass;
    // Falls das erste hass-Objekt ankommt, bevor connectedCallback gefeuert
    // hat (Timing bei Custom-Element-Upgrades ist nicht garantiert), wird
    // die Hülle hier nachgeholt.
    this._ensureBuilt();
    // _route() ist idempotent (bricht sofort ab, wenn sich die Ziel-Ansicht
    // nicht geändert hat) — der Aufruf hier ist nur ein Sicherheitsnetz für
    // den Fall, dass connectedCallback noch nicht gelaufen ist.
    if (this.isConnected) this._route();
    this._tick();
  }

  get hass() {
    return this._data.hass;
  }

  // -------------------------------------------------------------------
  // Aufbau der Hülle (einmalig)
  // -------------------------------------------------------------------

  _ensureBuilt() {
    if (this._built) return;
    this._buildShell();
    this._built = true;
  }

  _buildShell() {
    const style = document.createElement('style');
    style.textContent = M3_CSS;
    this._root.appendChild(style);

    const shell = document.createElement('div');
    shell.className = 'md-app-shell';

    shell.appendChild(this._buildAppBar());
    shell.appendChild(this._buildBanner());

    this._buildNav();
    shell.appendChild(this._navRailEl);

    const main = document.createElement('main');
    main.className = 'md-view';
    this._mainEl = main;
    shell.appendChild(main);

    shell.appendChild(this._navBarEl);

    this._root.appendChild(shell);
  }

  _buildAppBar() {
    const bar = document.createElement('header');
    bar.className = 'md-app-bar';

    // Zurueck-Pfeil, nur in Unteransichten sichtbar (M3 Top App Bar mit
    // Navigation Icon). Fuehrt zur uebergeordneten Ansicht, nicht in die
    // Browser-Historie - der Weg ist dadurch immer vorhersagbar.
    const zurueck = document.createElement('button');
    zurueck.type = 'button';
    zurueck.className = 'md-app-bar-back';
    zurueck.setAttribute('aria-label', 'Zurueck');
    zurueck.innerHTML = icon('chevron');
    zurueck.hidden = true;
    zurueck.addEventListener('click', () => {
      const aktuell = VIEWS.find((v) => v.id === this._activeViewId);
      const ziel = (aktuell && aktuell.parent) || (VIEWS[0] && VIEWS[0].id);
      if (ziel) location.hash = `#/${ziel}`;
    });
    this._backEl = zurueck;

    const title = document.createElement('span');
    title.className = 'md-app-bar-title md-title-large';
    title.textContent = 'Solarbank';
    this._titleEl = title;

    const statusDot = document.createElement('span');
    statusDot.className = 'md-status-dot';
    statusDot.title = 'Systemzustand: unbekannt';
    this._statusDotEl = statusDot;

    bar.append(zurueck, title, statusDot);
    return bar;
  }

  _buildBanner() {
    const banner = document.createElement('div');
    banner.className = 'md-banner';
    banner.hidden = true;

    const bannerIcon = document.createElement('span');
    bannerIcon.className = 'md-banner-icon';
    bannerIcon.innerHTML = icon('info');

    const bannerText = document.createElement('span');
    bannerText.className = 'md-banner-text md-body-medium';
    bannerText.textContent = DATENSCHNITT_TEXT;

    banner.append(bannerIcon, bannerText);
    this._bannerEl = banner;
    return banner;
  }

  /** Baut Nav-Bar (mobil) und Nav-Rail (Tablet/Desktop) aus VIEWS. Beide
   *  existieren gleichzeitig im DOM; welche sichtbar ist, entscheidet
   *  ausschließlich CSS (siehe M3_CSS Abschnitt 8) je nach Viewport. */
  _buildNav() {
    const bar = document.createElement('nav');
    bar.className = 'md-nav-bar';
    bar.setAttribute('aria-label', 'Hauptnavigation (mobil)');

    const rail = document.createElement('nav');
    rail.className = 'md-nav-rail';
    rail.setAttribute('aria-label', 'Hauptnavigation');

    this._navItems = [];
    // Nur oberste Ziele. Ansichten mit `parent` sind Unteransichten und
    // werden ueber Einstiegskarten erreicht, nicht ueber die Leiste.
    // Faellt die Markierung ganz weg, zeigen wir alles - sonst waere die
    // App nach einem Fehler in views.js unbedienbar.
    const zieleOben = VIEWS.filter((v) => v && v.top);
    const ziele = zieleOben.length ? zieleOben : VIEWS;
    for (const view of ziele) {
      const barItem = this._makeNavItem(view);
      const railItem = this._makeNavItem(view);
      bar.appendChild(barItem);
      rail.appendChild(railItem);
      this._navItems.push({ id: view.id, els: [barItem, railItem] });
    }

    this._navBarEl = bar;
    this._navRailEl = rail;
  }

  _makeNavItem(view) {
    const el = document.createElement('button');
    el.type = 'button';
    el.className = 'md-nav-item';
    el.dataset.viewId = view.id;
    el.setAttribute('aria-current', 'false');

    const iconWrap = document.createElement('span');
    iconWrap.className = 'md-nav-item-icon';
    iconWrap.innerHTML = icon(view.icon);

    const label = document.createElement('span');
    label.className = 'md-nav-item-label md-label-medium';
    label.textContent = view.label;

    el.append(iconWrap, label);
    el.addEventListener('click', () => {
      location.hash = `#/${view.id}`;
    });
    ripple(el);
    return el;
  }

  // -------------------------------------------------------------------
  // Router
  // -------------------------------------------------------------------

  _onHashChange() {
    this._route();
  }

  /** Ermittelt die Ziel-Ansicht aus dem Hash, mit Rückfall auf die erste
   *  Ansicht aus VIEWS, wenn der Hash leer ist oder auf keine bekannte
   *  Ansicht zeigt. */
  _resolveViewId() {
    const raw = location.hash.replace(/^#\/?/, '').trim();
    const gefunden = Array.isArray(VIEWS) ? VIEWS.find((v) => v.id === raw) : null;
    if (gefunden) return gefunden.id;
    return Array.isArray(VIEWS) && VIEWS[0] ? VIEWS[0].id : null;
  }

  /** Idempotent: wechselt nur die Ansicht, wenn sich die Ziel-ID geändert
   *  hat. Wird sowohl bei hashchange als auch — als Sicherheitsnetz — bei
   *  set hass aufgerufen, kostet im unveränderten Fall aber nur einen
   *  String-Vergleich. */
  _route() {
    const id = this._resolveViewId();
    if (id === this._activeViewId) return;
    this._activeViewId = id;
    this._renderView(id);
    this._updateNavSelection(id);
  }

  _updateNavSelection(activeId) {
    for (const item of this._navItems) {
      const aktiv = item.id === activeId;
      for (const el of item.els) {
        el.classList.toggle('active', aktiv);
        el.setAttribute('aria-current', aktiv ? 'page' : 'false');
      }
    }
  }

  // -------------------------------------------------------------------
  // Ansicht rendern
  // -------------------------------------------------------------------

  _makeCtx() {
    return {
      data: this._data,
      hass: this._data.hass,
      go: (id) => {
        location.hash = `#/${id}`;
      },
    };
  }

  _renderView(id) {
    if (!this._mainEl) return;

    // Alte Ansicht sauber entfernen, bevor die neue aufgebaut wird.
    while (this._mainEl.firstChild) {
      this._mainEl.firstChild.remove();
    }
    this._activeViewNode = null;

    const view = Array.isArray(VIEWS) ? VIEWS.find((v) => v.id === id) : null;
    if (!view) {
      this._mainEl.appendChild(
        this._errorCard('Ansicht nicht gefunden.', `Es gibt keine Ansicht mit der Kennung "${id}".`)
      );
      return;
    }

    // Titel und Zurueck-Pfeil an die Ansicht anpassen.
    if (this._backEl) this._backEl.hidden = !view.parent;
    if (this._titleEl) {
      this._titleEl.textContent = view.parent ? view.label || 'Solarbank' : 'Solarbank';
    }

    const ctx = this._makeCtx();
    try {
      const node = view.build(ctx);
      if (node instanceof Node) {
        this._mainEl.appendChild(node);
        this._activeViewNode = node;
      } else if (node !== undefined && node !== null) {
        // build() hat etwas zurückgegeben, das kein DOM-Knoten ist — das
        // ist ein Programmierfehler in der Ansicht, darf die App aber
        // nicht mitreißen.
        this._mainEl.appendChild(
          this._errorCard(
            `Ansicht "${view.label || id}" liefert kein DOM-Element.`,
            'build(ctx) muss einen Node zurückgeben.'
          )
        );
      }
    } catch (err) {
      console.error(`[solarbank-app] Fehler beim Aufbau der Ansicht "${id}":`, err);
      this._mainEl.appendChild(
        this._errorCard(
          `Ansicht "${view.label || id}" konnte nicht geladen werden.`,
          err && err.message ? err.message : String(err)
        )
      );
    }
  }

  _errorCard(title, detail) {
    const card = document.createElement('div');
    card.className = 'md-card elevated md-error-card';

    const head = document.createElement('div');
    head.className = 'md-error-card-head';

    const iconWrap = document.createElement('span');
    iconWrap.className = 'md-error-card-icon';
    iconWrap.innerHTML = icon('warning');

    const titleEl = document.createElement('span');
    titleEl.className = 'md-title-medium';
    titleEl.textContent = title;

    head.append(iconWrap, titleEl);

    const detailEl = document.createElement('p');
    detailEl.className = 'md-body-medium';
    detailEl.textContent = detail;

    card.append(head, detailEl);
    return card;
  }

  // -------------------------------------------------------------------
  // Leichtgewichtiges Update bei jedem hass-Takt
  // -------------------------------------------------------------------

  _tick() {
    if (!this._built) return;
    this._updateStatusDot();
    this._updateBanner();

    // Die aktive Ansicht darf eine leichtgewichtige update()-Methode am
    // von build() zurückgegebenen Knoten anbieten, um sich ohne kompletten
    // Neuaufbau zu aktualisieren. Bietet sie das nicht an, bleibt sie bis
    // zum nächsten Navigationswechsel unverändert stehen — auch das ist
    // korrekt, denn ein Neuaufbau bei jedem hass-Takt ist genau das, was
    // vermieden werden soll.
    const node = this._activeViewNode;
    if (node && typeof node.update === 'function') {
      try {
        node.update(this._makeCtx());
      } catch (err) {
        console.error('[solarbank-app] Fehler beim Aktualisieren der aktiven Ansicht:', err);
      }
    }
  }

  _updateStatusDot() {
    const status = this._statusClassFor(this._data.state(STATUS_ENTITY));
    if (status === this._lastStatus) return; // keine Änderung -> keine DOM-Arbeit
    this._lastStatus = status;
    if (!this._statusDotEl) return;
    this._statusDotEl.className = `md-status-dot ${status}`;
    this._statusDotEl.title = `Systemzustand: ${status}`;
  }

  /** grün "ok", orange "warnung", rot sonst (auch bei fehlender/unbekannter Entity). */
  _statusClassFor(state) {
    const wert = String(state || '').toLowerCase();
    if (wert === 'ok') return 'ok';
    if (wert === 'warnung') return 'warnung';
    return 'fehler';
  }

  _updateBanner() {
    const anzeigen = Date.now() < DATENSCHNITT_ENDE;
    if (anzeigen === this._lastBannerShown) return; // keine Änderung -> keine DOM-Arbeit
    this._lastBannerShown = anzeigen;
    if (!this._bannerEl) return;
    this._bannerEl.hidden = !anzeigen;
  }
}

// Schützt vor "already defined", falls das Modul (z. B. während der
// Entwicklung durch einen Panel-Neuladevorgang ohne vollen Seiten-Reload)
// mehrfach im selben Dokumentkontext ausgeführt wird.
if (!customElements.get('solarbank-app')) {
  customElements.define('solarbank-app', SolarbankApp);
}
