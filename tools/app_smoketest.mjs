/**
 * Smoke-Test der Solarbank-App ohne Browser.
 *
 * WARUM ES DAS GIBT
 * -----------------
 * Die Oberflaeche laesst sich hier nicht rendern: Chrome ist nicht
 * installiert, und das Puppet-Add-on rendert nur Lovelace-Dashboards, keine
 * Custom Panels. Der erste Test lief deshalb auf dem Handy des Betreibers -
 * und fand sofort einen Fehler, den eine Syntaxpruefung nicht sehen kann:
 *
 *     Argument 1 ('node') to Node.appendChild must be an instance of Node
 *
 * Ursache war eine Schnittstellenluecke. `icon()` liefert SVG-Markup als
 * STRING, `views.js` gab es direkt an `appendChild`. Syntaktisch einwandfrei,
 * zur Laufzeit toedlich - und es riss jede einzelne Ansicht ab.
 *
 * Dieser Test baut ein minimales DOM nach und ruft jede Ansicht wirklich auf.
 * Er ersetzt keinen Blick auf die Oberflaeche, aber er faengt die Klasse von
 * Fehlern ab, die eine ganze Ansicht unbenutzbar macht.
 *
 * Aufruf:  node tools/app_smoketest.mjs
 */

// --- minimales DOM ------------------------------------------------------

class Klassenliste {
  constructor() { this._s = new Set(); }
  add(...n) { n.forEach((x) => x && this._s.add(x)); }
  remove(...n) { n.forEach((x) => this._s.delete(x)); }
  toggle(n, an) { if (an === undefined) an = !this._s.has(n); an ? this._s.add(n) : this._s.delete(n); return an; }
  contains(n) { return this._s.has(n); }
}

class Knoten {
  constructor(tag) {
    this.tagName = String(tag || '').toUpperCase();
    this.children = [];
    this.childNodes = this.children;
    this.parentNode = null;
    this.style = new Proxy({}, { get: (t, k) => t[k] ?? '', set: (t, k, v) => { t[k] = v; return true; } });
    this.dataset = {};
    this.classList = new Klassenliste();
    this._attrs = {};
    this._text = '';
    this._html = '';
    this.hidden = false;
    this.type = '';
  }
  get className() { return this._cls || ''; }
  set className(v) { this._cls = v; String(v || '').split(/\s+/).forEach((c) => c && this.classList.add(c)); }
  get textContent() { return this._text; }
  set textContent(v) { this._text = String(v ?? ''); }
  get innerHTML() { return this._html; }
  set innerHTML(v) { this._html = String(v ?? ''); }
  get firstChild() { return this.children[0] || null; }

  appendChild(k) {
    // GENAU DIE PRUEFUNG, DIE DER BROWSER MACHT. Sie ist der Kern des Tests.
    if (!(k instanceof Knoten)) {
      throw new TypeError(
        `Argument 1 ('node') to Node.appendChild must be an instance of Node ` +
        `- bekommen: ${typeof k}${typeof k === 'string' ? ` (${k.slice(0, 60)}...)` : ''}`
      );
    }
    k.parentNode = this;
    this.children.push(k);
    return k;
  }
  append(...ks) { ks.forEach((k) => this.appendChild(k)); }
  prepend(...ks) {
    for (const k of ks.reverse()) {
      if (!(k instanceof Knoten)) throw new TypeError('prepend: kein Knoten');
      k.parentNode = this; this.children.unshift(k);
    }
  }
  replaceChildren(...ks) { this.children.length = 0; this.append(...ks); }
  contains(k) { return this.children.includes(k); }
  insertBefore(neu, ref) {
    if (!(neu instanceof Knoten)) throw new TypeError('insertBefore: kein Knoten');
    const i = this.children.indexOf(ref);
    this.children.splice(i < 0 ? this.children.length : i, 0, neu);
    neu.parentNode = this;
    return neu;
  }
  removeChild(k) { const i = this.children.indexOf(k); if (i >= 0) this.children.splice(i, 1); return k; }
  remove() { if (this.parentNode) this.parentNode.removeChild(this); }
  setAttribute(n, v) { this._attrs[n] = String(v); }
  getAttribute(n) { return n in this._attrs ? this._attrs[n] : null; }
  removeAttribute(n) { delete this._attrs[n]; }
  hasAttribute(n) { return n in this._attrs; }
  addEventListener() {}
  removeEventListener() {}
  querySelector() { return null; }
  querySelectorAll() { return []; }
  attachShadow() { const s = new Knoten('#shadow'); this.shadowRoot = s; return s; }
  getBoundingClientRect() { return { width: 320, height: 120, top: 0, left: 0, right: 320, bottom: 120 }; }
  focus() {}
  click() {}
  closest() { return null; }
}

globalThis.Node = Knoten;
globalThis.HTMLElement = class extends Knoten { constructor() { super('div'); } };
globalThis.customElements = { define() {}, get() { return undefined; } };
globalThis.document = {
  createElement: (t) => new Knoten(t),
  createElementNS: (_ns, t) => new Knoten(t),
  createTextNode: (t) => Object.assign(new Knoten('#text'), { _text: String(t) }),
  createDocumentFragment: () => new Knoten('#fragment'),
  adoptedStyleSheets: [],
  documentElement: new Knoten('html'),
  head: new Knoten('head'),
  body: new Knoten('body'),
  addEventListener() {},
};
globalThis.window = { addEventListener() {}, matchMedia: () => ({ matches: false, addEventListener() {} }), location: { hash: '' } };
globalThis.location = globalThis.window.location;
globalThis.requestAnimationFrame = (f) => { f(0); return 1; };
globalThis.cancelAnimationFrame = () => {};
globalThis.getComputedStyle = () => ({ getPropertyValue: () => '' });
globalThis.CSS = { supports: () => true };

// --- Datenattrappe ------------------------------------------------------

/** Liefert plausible Werte, damit die Ansichten echte Pfade durchlaufen. */
const attrappe = {
  hass: { states: {}, callWS: async () => ({}), callService: async () => {} },
  state: () => '42',
  num: () => 42,
  attr: (_id, k) => (k === 'befunde' ? ['Beispielbefund'] : k === 'azimuth' ? 180 : k === 'elevation' ? 30 : null),
  unit: () => 'W',
  name: (id) => id,
  lastChanged: () => new Date(),
  isOn: () => false,
  fmtW: (w) => `${w} W`,
  fmtKWh: (v) => `${v} kWh`,
  fmtNum: (v) => String(v ?? '-'),
  fmtZeit: () => '17:20',
  history: async () => [],
  statistics: async () => [],
  call: async () => {},
};

// --- Testlauf -----------------------------------------------------------

const { VIEWS } = await import('../custom_components/solarbank_app/www/views.js');

const ctx = { data: attrappe, hass: attrappe.hass, go() {} };
let fehler = 0;

console.log(`${VIEWS.length} Ansichten gefunden\n`);
for (const v of VIEWS) {
  const ebene = v.top ? 'oben' : `unter ${v.parent}`;
  try {
    const node = v.build(ctx);
    if (!(node instanceof Knoten)) throw new TypeError('build() liefert keinen Knoten');
    console.log(`  ok    ${v.id.padEnd(10)} ${ebene.padEnd(14)} ${v.label}`);
  } catch (e) {
    fehler++;
    console.log(`  FEHL  ${v.id.padEnd(10)} ${ebene.padEnd(14)} ${e.message}`);
  }
}

const oben = VIEWS.filter((v) => v.top).length;
console.log(`\nNavigationsziele: ${oben} (M3 empfiehlt 3 bis 5)`);
console.log(fehler === 0 ? 'Alle Ansichten bauen durch.' : `${fehler} Ansicht(en) defekt.`);
process.exit(fehler === 0 && oben >= 3 && oben <= 5 ? 0 : 1);
