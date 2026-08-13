/**
 * data.js — Brücke zum `hass`-Objekt.
 *
 * Kapselt alle Lesezugriffe auf Home Assistant: aktuelle Zustände,
 * Attribute, Kurz- und Langzeit-Historie sowie Service-Aufrufe zum
 * Schreiben. Reines ES-Modul, kein Build-Schritt, keine Abhängigkeit
 * außer dem vom Panel bereitgestellten `hass`-Objekt.
 *
 * Zustände wie 'unknown'/'unavailable' werden konsequent auf einen
 * Fallback abgebildet statt NaN oder Exceptions zu erzeugen — die
 * Solarbank liefert solche Zustände z. B. direkt nach einem Neustart.
 */

// Cache-Gültigkeit für Historie/Statistik in Millisekunden. 60 s deckt das
// wiederholte Auf- und Zuklappen einer Kachel ab, ohne bei jedem Klick eine
// neue WebSocket-Anfrage auszulösen.
const CACHE_TTL_MS = 60 * 1000;

export class Data {
  /**
   * @param {*} hass Das von Home Assistant gestellte hass-Objekt.
   */
  constructor(hass) {
    this._hass = hass || null;
    // Schlüssel "hist:<id>:<stunden>" bzw. "stat:<id>:<tage>" -> { zeit, daten }
    this._cache = new Map();
  }

  // -- hass-Zugriff --------------------------------------------------------
  // Das Panel setzt `hass` bei jedem Update neu (HA-Push-Modell). Die Referenz
  // wird einfach ausgetauscht, der Cache bleibt unabhängig davon bestehen.

  set hass(h) {
    this._hass = h;
  }

  get hass() {
    return this._hass;
  }

  // -- Rohzugriff auf Zustände und Attribute -------------------------------

  /** Roher Zustandsstring der Entity oder null, wenn sie nicht existiert. */
  state(id) {
    if (!id || !this._hass || !this._hass.states) return null;
    const st = this._hass.states[id];
    return st ? st.state : null;
  }

  /**
   * Numerischer Zustand oder `fallback`. 'unknown'/'unavailable' sowie
   * nicht-numerische Zustände liefern ebenfalls den Fallback statt NaN.
   */
  num(id, fallback = null) {
    const s = this.state(id);
    if (s === null || s === 'unknown' || s === 'unavailable') return fallback;
    const n = Number(s);
    return Number.isNaN(n) ? fallback : n;
  }

  /** Attributwert der Entity oder null, wenn Entity/Attribut fehlt. */
  attr(id, key) {
    if (!id || !this._hass || !this._hass.states) return null;
    const st = this._hass.states[id];
    if (!st || !st.attributes) return null;
    const v = st.attributes[key];
    return v === undefined ? null : v;
  }

  /** Einheit der Entity (`unit_of_measurement`) oder leerer String. */
  unit(id) {
    return this.attr(id, 'unit_of_measurement') || '';
  }

  /** Anzeigename der Entity (`friendly_name`) oder die Entity-ID als Rückfall. */
  name(id) {
    return this.attr(id, 'friendly_name') || id;
  }

  /** Zeitpunkt der letzten Zustandsänderung als Date oder null. */
  lastChanged(id) {
    if (!id || !this._hass || !this._hass.states) return null;
    const st = this._hass.states[id];
    if (!st || !st.last_changed) return null;
    const d = new Date(st.last_changed);
    return Number.isNaN(d.getTime()) ? null : d;
  }

  /** true, wenn der Zustand exakt 'on' ist. */
  isOn(id) {
    return this.state(id) === 'on';
  }

  // -- Deutsche Zahlen- und Zeitformatierung -------------------------------

  /** Leistung: unter 1000 W ganzzahlig in Watt, sonst in kW mit Komma. */
  fmtW(watt) {
    if (watt === null || watt === undefined || Number.isNaN(watt)) return '–';
    const n = Number(watt);
    if (Math.abs(n) < 1000) {
      return `${this.fmtNum(n, 0)} W`;
    }
    return `${this.fmtNum(n / 1000, 2)} kW`;
  }

  /** Energie in kWh mit deutschem Dezimalkomma, z. B. "9,56 kWh". */
  fmtKWh(v, digits = 2) {
    if (v === null || v === undefined || Number.isNaN(v)) return '–';
    return `${this.fmtNum(v, digits)} kWh`;
  }

  /** Zahl mit deutschem Dezimalkomma. null/NaN -> "–". */
  fmtNum(v, digits = 1) {
    if (v === null || v === undefined || Number.isNaN(v)) return '–';
    return Number(v).toLocaleString('de-DE', {
      minimumFractionDigits: digits,
      maximumFractionDigits: digits,
    });
  }

  /** Uhrzeit im Format "17:20". Ungültige/leere Eingabe -> "–". */
  fmtZeit(dateOrIso) {
    if (!dateOrIso) return '–';
    const d = dateOrIso instanceof Date ? dateOrIso : new Date(dateOrIso);
    if (Number.isNaN(d.getTime())) return '–';
    return d.toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' });
  }

  // -- Cache-Hilfsfunktionen ------------------------------------------------

  _cacheGet(key) {
    const entry = this._cache.get(key);
    if (!entry) return null;
    if (Date.now() - entry.zeit > CACHE_TTL_MS) {
      this._cache.delete(key);
      return null;
    }
    return entry.daten;
  }

  _cacheSet(key, daten) {
    this._cache.set(key, { zeit: Date.now(), daten });
  }

  // -- Historie und Statistik ------------------------------------------------

  /**
   * Kurzzeit-Historie über `history/history_during_period`.
   * @returns {Promise<Array<{t: Date, v: number}>>} Nie ein Throw, im
   *   Fehlerfall immer ein leeres Array.
   */
  async history(id, hours = 24) {
    if (!id || !this._hass || typeof this._hass.callWS !== 'function') return [];

    const key = `hist:${id}:${hours}`;
    const cached = this._cacheGet(key);
    if (cached) return cached;

    try {
      const end = new Date();
      const start = new Date(end.getTime() - hours * 60 * 60 * 1000);
      const antwort = await this._hass.callWS({
        type: 'history/history_during_period',
        start_time: start.toISOString(),
        end_time: end.toISOString(),
        entity_ids: [id],
        minimal_response: true,
        no_attributes: true,
        significant_changes_only: false,
      });

      const zeilen = (antwort && antwort[id]) || [];
      const punkte = [];
      for (const zeile of zeilen) {
        // Neuere HA-Versionen liefern kurze Schlüssel (s/lu) im
        // minimal_response-Modus, ältere die ausgeschriebenen
        // (state/last_changed). Beide Formen werden toleriert.
        const rohZustand = zeile.s !== undefined ? zeile.s : zeile.state;
        const rohZeit = zeile.lu !== undefined ? zeile.lu * 1000 : zeile.last_changed;

        if (rohZustand === undefined || rohZustand === null) continue;
        if (rohZustand === 'unknown' || rohZustand === 'unavailable') continue;

        const v = Number(rohZustand);
        if (Number.isNaN(v)) continue; // nicht-numerische Zustände überspringen

        const t = new Date(rohZeit);
        if (Number.isNaN(t.getTime())) continue;

        punkte.push({ t, v });
      }

      this._cacheSet(key, punkte);
      return punkte;
    } catch (e) {
      return [];
    }
  }

  /**
   * Langzeit-Statistik über `recorder/statistics_during_period` (Stundenmittel).
   * @returns {Promise<Array<{t: Date, v: number}>>} Nie ein Throw, im
   *   Fehlerfall immer ein leeres Array.
   */
  async statistics(id, days = 7) {
    if (!id || !this._hass || typeof this._hass.callWS !== 'function') return [];

    const key = `stat:${id}:${days}`;
    const cached = this._cacheGet(key);
    if (cached) return cached;

    try {
      const end = new Date();
      const start = new Date(end.getTime() - days * 24 * 60 * 60 * 1000);
      const antwort = await this._hass.callWS({
        type: 'recorder/statistics_during_period',
        start_time: start.toISOString(),
        end_time: end.toISOString(),
        statistic_ids: [id],
        period: 'hour',
      });

      const zeilen = (antwort && antwort[id]) || [];
      const punkte = [];
      for (const zeile of zeilen) {
        if (zeile.mean === undefined || zeile.mean === null) continue;
        const v = Number(zeile.mean);
        if (Number.isNaN(v)) continue;

        const t = new Date(zeile.start);
        if (Number.isNaN(t.getTime())) continue;

        punkte.push({ t, v });
      }

      this._cacheSet(key, punkte);
      return punkte;
    } catch (e) {
      return [];
    }
  }

  // -- Schreiben ausschließlich über HA-Services -----------------------------

  /**
   * Ruft einen HA-Service auf. Wirft im Fehlerfall (im Gegensatz zu
   * history/statistics) — der Aufrufer entscheidet, wie er das dem
   * Betreiber meldet (z. B. Snackbar).
   */
  async call(domain, service, data) {
    if (!this._hass || typeof this._hass.callService !== 'function') {
      throw new Error('hass ist nicht verfügbar – Service kann nicht aufgerufen werden');
    }
    return this._hass.callService(domain, service, data);
  }
}
