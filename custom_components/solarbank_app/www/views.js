// views.js — die neun Ansichten der Solarbank-App.
//
// Reines ES-Modul, kein Build. Importiert nur die verbindliche Schnittstelle
// aus m3.js, tile.js und haus.js. Jede Ansicht ist ein Eintrag in VIEWS mit
// build(ctx) -> HTMLElement, ctx = { data, hass, go(id) }.
//
// Icon-Vokabular: m3.js kennt nachweislich genau die acht Kurznamen, die in
// VIEWS als Ansichts-Icon verwendet werden (home, chart, solar-power,
// battery, sun, tune, cog, shield). Ob m3.js daneben beliebige weitere Namen
// versteht, ist von hier aus nicht pruefbar - deshalb verwendet diese Datei
// ausschliesslich diese acht Namen, auch fuer Kacheln innerhalb der
// Ansichten, und ordnet sie dem inhaltlich naechstliegenden Thema zu.
import { icon, ripple } from './m3.js';
import { tile } from './tile.js';
import { buildHaus } from './haus.js';

// ---------------------------------------------------------------------------
// Entity-Namensraeume. Zentral gehalten, damit sich ein Tippfehler in einer
// der langen Anker-IDs nicht in jeder Ansicht einzeln wiederholen kann.
// ---------------------------------------------------------------------------
const ANKER = 'sensor.anker_solix_solarbank_4_e5000_pro_441';
const ANKER_SELECT_BETRIEBSMODUS =
  'select.anker_solix_solarbank_4_e5000_pro_441_betriebsmodus_gerat_lauft_im_drittanbieter_steuermodus';
const ANKER_NUMBER_LADEOBERGRENZE = 'number.anker_solix_solarbank_4_e5000_pro_441_ladeobergrenze';
const ANKER_NUMBER_ENTLADEGRENZE = 'number.anker_solix_solarbank_4_e5000_pro_441_entladegrenze';
const ANKER_NUMBER_NOTSTROMRESERVE = 'number.anker_solix_solarbank_4_e5000_pro_441_notstromreserve';

const LERNEN = 'sensor.pv_lernen';

const NE_AKTIV = 'input_boolean.nulleinspeisung_aktiv';
const NE_PRIO = 'input_boolean.nulleinspeisung_pv_prioritaetsladung';
const NE = 'input_number.nulleinspeisung';

const DIAGNOSE_GESAMTZUSTAND = 'sensor.solarbank_diagnose_gesamtzustand';
const DIAGNOSE_DB_GROESSE = 'sensor.diagnose_recorder_datenbankgroesse';

// ---------------------------------------------------------------------------
// Kleine DOM-Werkzeuge
// ---------------------------------------------------------------------------

/** Erzeugt ein Element mit Klasse, Text und Kindern - spart Boilerplate. */
function el(tag, { cls, text, attrs, children } = {}) {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  if (text != null) node.textContent = text;
  if (attrs) for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
  if (children) for (const c of children) if (c) node.appendChild(c);
  return node;
}

/** Kopfzeile einer Ansicht: Icon + Ueberschrift, optional Untertitel. */
function ansichtsKopf(titel, iconName, untertitel) {
  const kopf = el('div', { cls: 'sb-ansicht-kopf' });
  kopf.appendChild(icon(iconName));
  const texte = el('div');
  texte.appendChild(el('h1', { cls: 'headline', text: titel }));
  if (untertitel) texte.appendChild(el('p', { cls: 'body sb-kopf-untertitel', text: untertitel }));
  kopf.appendChild(texte);
  return kopf;
}

/** Ueberschrift eines Abschnitts innerhalb einer Ansicht. */
function abschnitt(titel, iconName) {
  const h = el('div', { cls: 'sb-abschnitt' });
  if (iconName) h.appendChild(icon(iconName));
  h.appendChild(el('h2', { cls: 'title', text: titel }));
  return h;
}

/** Kachel-Raster: legt beliebig viele Kinder nebeneinander/umbrechend. */
function raster(...kinder) {
  return el('div', { cls: 'sb-raster', children: kinder });
}

/** Chip zur Kennzeichnung, z.B. "nur lesend" oder "geschaetzt". */
function chip(text, art) {
  return el('span', { cls: `sb-chip sb-chip-${art}`, text });
}

/** Auffaelliger Hinweisblock. */
function hinweis(text, art = 'info') {
  const box = el('div', { cls: `sb-hinweis sb-hinweis-${art}` });
  box.appendChild(el('p', { cls: 'body', text }));
  return box;
}

/** Zeile, die sichtbar macht, worueber ein Bedienblock schreibt. */
function quelleZeile(text) {
  return el('p', { cls: 'label sb-quelle', text: `Schreibt ueber: ${text}` });
}

/** Grosse Kennzahl ("Held") fuer die wichtigste Zahl einer Ansicht. */
function heldenZahl({ titel, wert, subtitel, iconName, ton = 'neutral' }) {
  const box = el('div', { cls: `sb-held sb-held-${ton}` });
  if (iconName) box.appendChild(icon(iconName));
  const inhalt = el('div');
  inhalt.appendChild(el('div', { cls: 'display', text: wert }));
  inhalt.appendChild(el('div', { cls: 'title', text: titel }));
  if (subtitel) inhalt.appendChild(el('div', { cls: 'body sb-held-sub', text: subtitel }));
  box.appendChild(inhalt);
  return box;
}

/** Nicht aufklappbare Info-Zeile fuer statische Codewerte im Admin-Bereich. */
function infoZeile({ label, wert, quelle, hinweis: text }) {
  const row = el('div', { cls: 'sb-inforeihe' });
  row.appendChild(el('span', { cls: 'label sb-inforeihe-label', text: label }));
  row.appendChild(el('span', { cls: 'body sb-inforeihe-wert', text: wert }));
  row.appendChild(el('span', { cls: 'label sb-inforeihe-quelle', text: `Quelle: ${quelle}` }));
  if (text) row.appendChild(el('p', { cls: 'body sb-inforeihe-hinweis', text }));
  return row;
}

/** Balkenzeile fuer die Verschattungsansicht: Label, Prozentbalken, Wert. */
function balkenZeile(label, prozent) {
  const p = Math.max(0, Math.min(100, prozent));
  const row = el('div', { cls: 'sb-balkenzeile' });
  row.appendChild(el('span', { cls: 'label sb-balken-label', text: label }));
  const spur = el('div', { cls: 'sb-balken-spur' });
  const fuellung = el('div', { cls: 'sb-balken-fuellung' });
  fuellung.style.width = `${p}%`;
  spur.appendChild(fuellung);
  row.appendChild(spur);
  row.appendChild(el('span', { cls: 'body sb-balken-wert', text: `${p.toFixed(0).replace('.', ',')} %` }));
  return row;
}

// ---------------------------------------------------------------------------
// Bestaetigungsdialog. Wird ausschliesslich fuer den Nulleinspeisungs-Block
// verwendet - dort steht es in der Aufgabenstellung, sonst nirgends. Die vier
// schreibbaren Anker-Bedienelemente schreiben direkt, ohne Dialog.
// ---------------------------------------------------------------------------
function bestaetigenUndSchreiben(titel, beschreibung, aktion) {
  const dlg = document.createElement('dialog');
  dlg.className = 'sb-dialog';
  dlg.appendChild(el('h2', { cls: 'title', text: titel }));
  dlg.appendChild(el('p', { cls: 'body', text: beschreibung }));
  const knoepfe = el('div', { cls: 'sb-dialog-knoepfe' });

  const abbrechen = document.createElement('button');
  abbrechen.type = 'button';
  abbrechen.className = 'sb-btn sb-btn-text';
  abbrechen.textContent = 'Abbrechen';
  ripple(abbrechen);
  abbrechen.addEventListener('click', () => dlg.close());

  const bestaetigen = document.createElement('button');
  bestaetigen.type = 'button';
  bestaetigen.className = 'sb-btn sb-btn-filled';
  bestaetigen.textContent = 'Bestaetigen';
  ripple(bestaetigen);
  bestaetigen.addEventListener('click', () => {
    aktion();
    dlg.close();
  });

  knoepfe.appendChild(abbrechen);
  knoepfe.appendChild(bestaetigen);
  dlg.appendChild(knoepfe);
  dlg.addEventListener('close', () => dlg.remove());
  document.body.appendChild(dlg);
  dlg.showModal();
}

// ---------------------------------------------------------------------------
// M3-Bedienelemente: Slider und Select fuer die vier schreibbaren
// Anker-Entities, dazu bestaetigungspflichtige Varianten fuer die
// Nulleinspeisung. m3.js liefert keine fertigen Slider/Select-Komponenten
// (nur icon() und ripple()), deshalb werden sie hier aus nativen
// Formularelementen gebaut und im M3-Look eingefaerbt.
// ---------------------------------------------------------------------------
function m3Select({ data, entity, label, iconName, quelle }) {
  const wrap = el('div', { cls: 'sb-control' });
  wrap.appendChild(quelleZeile(quelle));
  const kopf = el('div', { cls: 'sb-control-kopf' });
  kopf.appendChild(icon(iconName));
  kopf.appendChild(el('span', { cls: 'label', text: label }));
  wrap.appendChild(kopf);

  const select = document.createElement('select');
  select.className = 'sb-select';
  const optionen = data.attr(entity, 'options') || [];
  const aktuell = data.state(entity);
  for (const o of optionen) {
    const opt = document.createElement('option');
    opt.value = o;
    opt.textContent = o;
    if (o === aktuell) opt.selected = true;
    select.appendChild(opt);
  }
  select.addEventListener('change', () => {
    data.call('select', 'select_option', { entity_id: entity, option: select.value });
  });
  wrap.appendChild(select);
  return wrap;
}

/**
 * M3-Slider fuer eine number-Entity. Schreibt direkt beim Loslassen
 * (change), ohne Bestaetigung - gilt nur fuer die vier Anker-Stellgroessen.
 */
function m3Slider({ data, entity, label, iconName, quelle }) {
  const min = data.attr(entity, 'min') ?? 0;
  const max = data.attr(entity, 'max') ?? 100;
  const step = data.attr(entity, 'step') ?? 1;
  const einheit = data.unit(entity) || '';
  const startwert = data.num(entity, min);

  const wrap = el('div', { cls: 'sb-control' });
  wrap.appendChild(quelleZeile(quelle));
  const kopf = el('div', { cls: 'sb-control-kopf' });
  kopf.appendChild(icon(iconName));
  kopf.appendChild(el('span', { cls: 'label', text: label }));
  const anzeige = el('span', {
    cls: 'sb-control-wert',
    text: `${data.fmtNum(startwert, 0)} ${einheit}`.trim(),
  });
  kopf.appendChild(anzeige);
  wrap.appendChild(kopf);

  const slider = document.createElement('input');
  slider.type = 'range';
  slider.className = 'sb-slider';
  slider.min = String(min);
  slider.max = String(max);
  slider.step = String(step);
  slider.value = String(startwert);
  slider.addEventListener('input', () => {
    anzeige.textContent = `${data.fmtNum(parseFloat(slider.value), 0)} ${einheit}`.trim();
  });
  slider.addEventListener('change', () => {
    data.call('number', 'set_value', { entity_id: entity, value: parseFloat(slider.value) });
  });
  wrap.appendChild(slider);
  return wrap;
}

/**
 * M3-Slider fuer eine input_number-Entity mit Bestaetigungsdialog beim
 * Loslassen - fuer den Nulleinspeisungs-Block.
 */
function m3SliderBestaetigt({ data, entity, label, iconName }) {
  const min = data.attr(entity, 'min') ?? 0;
  const max = data.attr(entity, 'max') ?? 100;
  const step = data.attr(entity, 'step') ?? 1;
  const einheit = data.unit(entity) || '';
  const startwert = data.num(entity, min);

  const wrap = el('div', { cls: 'sb-control' });
  const kopf = el('div', { cls: 'sb-control-kopf' });
  kopf.appendChild(icon(iconName));
  kopf.appendChild(el('span', { cls: 'label', text: label }));
  const anzeige = el('span', {
    cls: 'sb-control-wert',
    text: `${data.fmtNum(startwert, 2)} ${einheit}`.trim(),
  });
  kopf.appendChild(anzeige);
  wrap.appendChild(kopf);

  const slider = document.createElement('input');
  slider.type = 'range';
  slider.className = 'sb-slider';
  slider.min = String(min);
  slider.max = String(max);
  slider.step = String(step);
  slider.value = String(startwert);
  slider.addEventListener('input', () => {
    anzeige.textContent = `${data.fmtNum(parseFloat(slider.value), 2)} ${einheit}`.trim();
  });
  slider.addEventListener('change', () => {
    const neu = parseFloat(slider.value);
    bestaetigenUndSchreiben(
      `${label} aendern?`,
      `Setzt ${entity} auf ${data.fmtNum(neu, 2)} ${einheit}. Wirkt sich sofort auf die laufende ` +
        'Nulleinspeisungsregelung aus.',
      () => data.call('input_number', 'set_value', { entity_id: entity, value: neu })
    );
  });
  wrap.appendChild(slider);
  return wrap;
}

/** M3-Schalter (Switch) fuer input_boolean, mit Bestaetigungsdialog. */
function m3SwitchBestaetigt({ data, entity, label, iconName, beschreibung }) {
  const zeile = el('div', { cls: 'sb-control-zeile' });
  zeile.appendChild(icon(iconName));
  zeile.appendChild(el('span', { cls: 'body sb-control-zeile-label', text: label }));

  const btn = document.createElement('button');
  btn.type = 'button';
  btn.className = 'sb-switch';
  btn.setAttribute('role', 'switch');
  const an = () => data.isOn(entity);
  const zeichne = () => {
    btn.setAttribute('aria-checked', String(an()));
    btn.classList.toggle('an', an());
  };
  zeichne();
  ripple(btn);
  btn.addEventListener('click', () => {
    const naechsterZustand = !an();
    bestaetigenUndSchreiben(
      `${label} ${naechsterZustand ? 'einschalten' : 'ausschalten'}?`,
      beschreibung,
      () => {
        data.call('input_boolean', naechsterZustand ? 'turn_on' : 'turn_off', { entity_id: entity });
        zeichne();
      }
    );
  });
  zeile.appendChild(btn);
  return zeile;
}

// ---------------------------------------------------------------------------
// PV-Strang-Karte (Ansicht "pv")
// ---------------------------------------------------------------------------
function pvStrangKarte(data, n) {
  const geschaetzt = n === 4;
  const karte = el('div', { cls: 'sb-karte' });
  const kopf = el('div', { cls: 'sb-karte-kopf' });
  kopf.appendChild(icon('solar-power'));
  kopf.appendChild(el('span', { cls: 'title', text: `PV-Strang ${n}` }));
  kopf.appendChild(chip(geschaetzt ? 'geschaetzt' : 'nur lesend', geschaetzt ? 'warnung' : 'lesend'));
  karte.appendChild(kopf);

  if (geschaetzt) {
    karte.appendChild(
      el('p', {
        cls: 'body sb-karte-hinweis',
        text:
          'Strang 4 hat kein eigenes Registerpaar: Leistung ist die exakte Differenz aus ' +
          'Gesamtleistung und Straengen 1-3, Spannung und Strom sind geschaetzt.',
      })
    );
  }

  const kacheln = raster(
    tile({
      data,
      entity: `sensor.pv_modul_${n}_leistung`,
      label: 'Leistung',
      icon: 'solar-power',
      format: 'watt',
      hint: geschaetzt
        ? 'Exakter Wert: Differenz aus Gesamtleistung und Straengen 1-3, nicht geschaetzt.'
        : 'Gemessen am Register des Strangs.',
    }),
    tile({
      data,
      entity: `sensor.pv_modul_${n}_leistungsanteil`,
      label: 'Anteil an Erwartung',
      icon: 'solar-power',
      format: 'num',
      digits: 0,
      unit: '%',
      hint: 'Anteil der aktuellen Leistung an der theoretisch erwartbaren Leistung dieses Strangs.',
    })
  );

  if (geschaetzt) {
    kacheln.appendChild(
      tile({
        data,
        entity: 'sensor.pv_modul_4_spannung_geschaetzt',
        label: 'Spannung (geschaetzt)',
        icon: 'solar-power',
        format: 'num',
        digits: 1,
        unit: 'V',
      })
    );
    kacheln.appendChild(
      tile({
        data,
        entity: 'sensor.pv_modul_4_strom_geschaetzt',
        label: 'Strom (geschaetzt)',
        icon: 'solar-power',
        format: 'num',
        digits: 2,
        unit: 'A',
      })
    );
  } else {
    kacheln.appendChild(
      tile({ data, entity: `sensor.pv_modul_${n}_spannung`, label: 'Spannung', icon: 'solar-power', format: 'num', digits: 1 })
    );
    kacheln.appendChild(
      tile({ data, entity: `sensor.pv_modul_${n}_strom`, label: 'Strom', icon: 'solar-power', format: 'num', digits: 2 })
    );
    kacheln.appendChild(
      tile({
        data,
        entity: `sensor.pv_modul_${n}_zelltemperatur`,
        label: 'Zelltemperatur',
        icon: 'solar-power',
        format: 'num',
        digits: 1,
        unit: '°C',
      })
    );
  }

  karte.appendChild(kacheln);
  return karte;
}

// ---------------------------------------------------------------------------
// Der Hinweis, der in Steuerung UND Admin sichtbar stehen muss.
// ---------------------------------------------------------------------------
function schreibHinweis() {
  return hinweis(
    'Schreibzugriffe laufen ausschliesslich ueber die offizielle Anker-Integration und ' +
      'Home-Assistant-Helfer. Die eigene Modbus-Integration solarbank_pv ist grundsaetzlich nur lesend ' +
      'und besitzt keinen Schreibpfad.',
    'warnung'
  );
}

// ---------------------------------------------------------------------------
// Die neun Ansichten
// ---------------------------------------------------------------------------
export const VIEWS = [
  {
    id: 'start',
    label: 'Start',
    icon: 'home',
    build(ctx) {
      const wrap = el('div', { cls: 'sb-view sb-view-start' });
      wrap.appendChild(buildHaus(ctx));
      wrap.appendChild(abschnitt('Auf einen Blick', 'chart'));
      wrap.appendChild(
        raster(
          tile({ data: ctx.data, entity: `${ANKER}_solarstrom`, label: 'PV', icon: 'solar-power', format: 'watt' }),
          tile({ data: ctx.data, entity: `${ANKER}_soc`, label: 'Speicher', icon: 'battery', format: 'num', digits: 0, unit: '%' }),
          tile({ data: ctx.data, entity: `${ANKER}_startseite_last`, label: 'Haus', icon: 'home', format: 'watt' }),
          tile({
            data: ctx.data,
            entity: `${ANKER}_netzbezugsleistung`,
            label: 'Netz',
            icon: 'chart',
            format: 'watt',
            hint: 'Netzbezug; Einspeisung siehe Ansicht Gesamtsystem.',
          })
        )
      );
      return wrap;
    },
  },

  {
    id: 'system',
    label: 'Gesamtsystem',
    icon: 'chart',
    build(ctx) {
      const { data } = ctx;
      const wrap = el('div', { cls: 'sb-view' });
      wrap.appendChild(ansichtsKopf('Gesamtsystem', 'chart', 'Erzeugung, Speicher, Hauslast, Netz und Tageswerte.'));

      wrap.appendChild(abschnitt('Erzeugung', 'solar-power'));
      wrap.appendChild(
        raster(
          tile({ data, entity: `${ANKER}_solarstrom`, label: 'PV-Leistung', icon: 'solar-power', format: 'watt' }),
          tile({
            data,
            entity: 'sensor.solarbank_dc_straenge_441_pv_leistung_gesamt_modbus',
            label: 'PV-Leistung (Modbus)',
            icon: 'solar-power',
            format: 'watt',
            hint: 'Nur lesend. Quervergleich zur offiziellen Integration, eigene Modbus-Abfrage.',
          }),
          tile({ data, entity: `${ANKER}_ac_ausgang`, label: 'AC-Ausgang', icon: 'chart', format: 'watt' })
        )
      );

      wrap.appendChild(abschnitt('Speicher', 'battery'));
      wrap.appendChild(
        raster(
          tile({ data, entity: `${ANKER}_soc`, label: 'Ladezustand', icon: 'battery', format: 'num', digits: 0, unit: '%' }),
          tile({ data, entity: `${ANKER}_batterieladeleistung`, label: 'Ladeleistung', icon: 'battery', format: 'watt' }),
          tile({ data, entity: `${ANKER}_batterieentladeleistung`, label: 'Entladeleistung', icon: 'battery', format: 'watt' }),
          tile({
            data,
            entity: 'sensor.solarbank_dc_straenge_441_pv_batterieleistung_modbus',
            label: 'Batterieleistung (Modbus)',
            icon: 'battery',
            format: 'watt',
            hint: 'Nur lesend. Quervergleich zur offiziellen Integration.',
          })
        )
      );

      wrap.appendChild(abschnitt('Hauslast und Netz', 'chart'));
      wrap.appendChild(
        raster(
          tile({ data, entity: `${ANKER}_startseite_last`, label: 'Hauslast', icon: 'home', format: 'watt' }),
          tile({ data, entity: `${ANKER}_netzbezugsleistung`, label: 'Netzbezug', icon: 'chart', format: 'watt' }),
          tile({ data, entity: `${ANKER}_netzeinspeiseleistung`, label: 'Netzeinspeisung', icon: 'chart', format: 'watt' })
        )
      );

      wrap.appendChild(abschnitt('Tageswerte', 'chart'));
      wrap.appendChild(
        raster(
          tile({ data, entity: `${ANKER}_gesamte_solarstromerzeugung`, label: 'Solarerzeugung gesamt', icon: 'solar-power', format: 'kwh' }),
          tile({ data, entity: 'sensor.pv_ertrag_tag', label: 'PV-Ertrag heute', icon: 'solar-power', format: 'kwh', hint: 'Nur lesend, eigene Integration.' }),
          tile({ data, entity: 'sensor.pv_nutzungsgrad_heute', label: 'Nutzungsgrad heute', icon: 'chart', format: 'num', digits: 0, unit: '%', hint: 'Nur lesend.' }),
          tile({ data, entity: 'sensor.pv_ersparnis_gesamt', label: 'Ersparnis gesamt', icon: 'chart', format: 'num', digits: 2, hint: 'Nur lesend.' })
        )
      );

      wrap.appendChild(abschnitt('Systemstatus (nur lesend, eigene Modbus-Integration)', 'shield'));
      wrap.appendChild(
        raster(
          tile({ data, entity: 'sensor.pv_batteriestatus', label: 'Batteriestatus', icon: 'battery', format: 'raw' }),
          tile({ data, entity: 'sensor.pv_betriebsmodus', label: 'Betriebsmodus (Geraet)', icon: 'cog', format: 'raw' }),
          tile({ data, entity: 'sensor.pv_ac_ausgangslimit', label: 'AC-Ausgangslimit', icon: 'chart', format: 'watt' }),
          tile({ data, entity: 'sensor.pv_ac_ausgangsstrom', label: 'AC-Ausgangsstrom', icon: 'chart', format: 'num', digits: 2, unit: 'A' }),
          tile({ data, entity: 'sensor.pv_maximale_ladeleistung', label: 'Maximale Ladeleistung', icon: 'battery', format: 'watt' }),
          tile({
            data,
            entity: 'sensor.pv_unbekannt_stufenwert_1',
            label: 'Geraetetemperatur',
            icon: 'chart',
            format: 'num',
            digits: 1,
            unit: '°C',
            hint: 'Registerbedeutung nicht vollstaendig gesichert, siehe Admin/Diagnose.',
          }),
          tile({ data, entity: 'binary_sensor.pv_abregelung_erkannt', label: 'Abregelung erkannt', icon: 'shield', format: 'raw' }),
          tile({ data, entity: 'sensor.pv_drosselung_leistung', label: 'Drosselung, aktuell', icon: 'chart', format: 'watt' }),
          tile({ data, entity: 'sensor.pv_drosselung_tag', label: 'Drosselung heute', icon: 'chart', format: 'kwh' })
        )
      );

      return wrap;
    },
  },

  {
    id: 'pv',
    label: 'PV',
    icon: 'solar-power',
    build(ctx) {
      const { data } = ctx;
      const wrap = el('div', { cls: 'sb-view' });
      wrap.appendChild(
        ansichtsKopf('PV', 'solar-power', 'Vier Straenge einzeln. Strang 4 hat kein eigenes Registerpaar und ist als geschaetzt markiert.')
      );
      wrap.appendChild(pvStrangKarte(data, 1));
      wrap.appendChild(pvStrangKarte(data, 2));
      wrap.appendChild(pvStrangKarte(data, 3));
      wrap.appendChild(pvStrangKarte(data, 4));

      wrap.appendChild(abschnitt('Theoretische Leistung und Verschattungsverlust', 'sun'));
      wrap.appendChild(
        raster(
          tile({
            data,
            entity: 'sensor.pv_theoretische_leistung',
            label: 'Theoretische Leistung',
            icon: 'sun',
            format: 'watt',
            hint: 'Rechenwert aus Sonnenstand ohne Verschattung, nicht gemessen.',
          }),
          tile({ data, entity: 'sensor.pv_theoretische_energie_tag', label: 'Theoretischer Ertrag heute', icon: 'sun', format: 'kwh' }),
          tile({ data, entity: 'sensor.pv_verschattungsverlust', label: 'Verschattungsverlust', icon: 'sun', format: 'watt' }),
          tile({ data, entity: 'sensor.pv_verschattungsverlust_tag', label: 'Verschattungsverlust heute', icon: 'sun', format: 'kwh' })
        )
      );
      return wrap;
    },
  },

  {
    id: 'akku',
    label: 'Akku',
    icon: 'battery',
    build(ctx) {
      const { data } = ctx;
      const wrap = el('div', { cls: 'sb-view' });
      wrap.appendChild(ansichtsKopf('Akku', 'battery'));

      wrap.appendChild(
        heldenZahl({
          titel: 'Ladezustand (SOC)',
          wert: `${data.fmtNum(data.num(`${ANKER}_soc`, 0), 0)} %`,
          iconName: 'battery',
          ton: 'primaer',
        })
      );

      wrap.appendChild(abschnitt('Leistung und Status', 'battery'));
      wrap.appendChild(
        raster(
          tile({ data, entity: `${ANKER}_batterieladeleistung`, label: 'Ladeleistung', icon: 'battery', format: 'watt' }),
          tile({ data, entity: `${ANKER}_batterieentladeleistung`, label: 'Entladeleistung', icon: 'battery', format: 'watt' }),
          tile({ data, entity: `${ANKER}_geratestatus`, label: 'Geraetestatus', icon: 'battery', format: 'raw' }),
          tile({ data, entity: `${ANKER}_akkukapazitat`, label: 'Kapazitaet', icon: 'battery', format: 'kwh' })
        )
      );

      wrap.appendChild(abschnitt('Kumulierte Energien', 'battery'));
      wrap.appendChild(
        raster(
          tile({ data, entity: `${ANKER}_batterie_ladeenergie`, label: 'Ladeenergie gesamt', icon: 'battery', format: 'kwh' }),
          tile({ data, entity: `${ANKER}_batterie_entladeenergie`, label: 'Entladeenergie gesamt', icon: 'battery', format: 'kwh' })
        )
      );

      wrap.appendChild(abschnitt('Prognose', 'sun'));
      wrap.appendChild(
        raster(
          tile({
            data,
            entity: `${LERNEN}_ziel_erreicht_um`,
            label: 'Ziel erreicht um',
            icon: 'battery',
            format: 'zeit',
            hint: 'Auflösung 15 Minuten - die Prognose springt in 15-Minuten-Schritten, keine Sekundengenauigkeit.',
          })
        )
      );
      return wrap;
    },
  },

  {
    id: 'prognose',
    label: 'Prognose',
    icon: 'sun',
    build(ctx) {
      const { data } = ctx;
      const wrap = el('div', { cls: 'sb-view' });
      wrap.appendChild(ansichtsKopf('Prognose', 'sun'));

      const lernstand = data.state(`${LERNEN}_lernstand`) || '—';
      const eingeschwungen = lernstand.startsWith('4 von 4');
      wrap.appendChild(
        heldenZahl({
          titel: 'Lernstand',
          wert: lernstand,
          subtitel: eingeschwungen
            ? 'Alle vier Schaetzer eingeschwungen - Prognosen beruhen auf gelernten Werten.'
            : 'Noch nicht alle Schaetzer eingeschwungen: Solange hier nicht "4 von 4" steht, sind alle ' +
              'Prognosen Startwerte, keine gelernten Werte.',
          iconName: 'sun',
          ton: eingeschwungen ? 'ok' : 'warnung',
        })
      );

      wrap.appendChild(abschnitt('Lernkennwerte', 'sun'));
      wrap.appendChild(
        raster(
          tile({ data, entity: `${LERNEN}_pegelfaktor`, label: 'Pegelfaktor', icon: 'sun', format: 'num', digits: 2 }),
          tile({ data, entity: `${LERNEN}_tagesform`, label: 'Tagesform', icon: 'sun', format: 'num', digits: 2 }),
          tile({ data, entity: `${LERNEN}_systemgain`, label: 'Systemgain', icon: 'sun', format: 'num', digits: 2 }),
          tile({ data, entity: `${LERNEN}_truebung`, label: 'Truebung', icon: 'sun', format: 'num', digits: 2 }),
          tile({ data, entity: `${LERNEN}_klarhimmelleistung`, label: 'Klarhimmelleistung', icon: 'sun', format: 'watt' }),
          tile({ data, entity: `${LERNEN}_hauslast`, label: 'Gelernte Hauslast', icon: 'home', format: 'watt' }),
          tile({ data, entity: `${LERNEN}_speicherwirkungsgrad`, label: 'Speicherwirkungsgrad', icon: 'battery', format: 'num', digits: 0, unit: '%' })
        )
      );

      wrap.appendChild(abschnitt('Forecast.Solar (extern, zum Vergleich)', 'sun'));
      wrap.appendChild(
        raster(
          tile({ data, entity: 'sensor.power_production_now', label: 'Leistung jetzt', icon: 'sun', format: 'watt' }),
          tile({ data, entity: 'sensor.energy_production_today', label: 'Ertrag heute', icon: 'sun', format: 'kwh' }),
          tile({ data, entity: 'sensor.energy_production_today_remaining', label: 'Ertrag heute, Rest', icon: 'sun', format: 'kwh' }),
          tile({ data, entity: 'sensor.energy_production_tomorrow', label: 'Ertrag morgen', icon: 'sun', format: 'kwh' })
        )
      );
      return wrap;
    },
  },

  {
    id: 'schatten',
    label: 'Verschattung',
    icon: 'sun',
    build(ctx) {
      const { data } = ctx;
      const wrap = el('div', { cls: 'sb-view' });
      wrap.appendChild(ansichtsKopf('Verschattung', 'sun', 'Fahrplan gegen Messung, je Strang.'));

      wrap.appendChild(
        hinweis(
          'Belegter Bias des Verschattungsprofils: Es basiert auf nur vier Messpunkten und endet real rund ' +
            '15 Minuten frueher, als das Profil annimmt. Das Profil sagt deshalb tendenziell zu wenig ' +
            'Verschattung voraus - bei Grenzentscheidungen eher von mehr realer Verschattung ausgehen.',
          'warnung'
        )
      );

      const az = data.attr('sun.sun', 'azimuth');
      const elev = data.attr('sun.sun', 'elevation');
      if (az != null && elev != null) {
        wrap.appendChild(
          el('p', {
            cls: 'body sb-sonnenstand',
            text: `Aktueller Sonnenstand: Azimut ${data.fmtNum(az, 0)}°, Elevation ${data.fmtNum(elev, 0)}°.`,
          })
        );
      }

      wrap.appendChild(abschnitt('Aktueller Leistungsanteil je Strang', 'sun'));
      const balken = el('div', { cls: 'sb-karte' });
      for (let n = 1; n <= 4; n++) {
        balken.appendChild(balkenZeile(`PV-Strang ${n}`, data.num(`sensor.pv_modul_${n}_leistungsanteil`, 0)));
      }
      wrap.appendChild(balken);

      wrap.appendChild(abschnitt('Verlauf je Strang', 'sun'));
      wrap.appendChild(
        raster(
          tile({ data, entity: 'sensor.pv_modul_1_leistungsanteil', label: 'PV-Strang 1, Anteil', icon: 'sun', format: 'num', digits: 0, unit: '%' }),
          tile({ data, entity: 'sensor.pv_modul_2_leistungsanteil', label: 'PV-Strang 2, Anteil', icon: 'sun', format: 'num', digits: 0, unit: '%' }),
          tile({ data, entity: 'sensor.pv_modul_3_leistungsanteil', label: 'PV-Strang 3, Anteil', icon: 'sun', format: 'num', digits: 0, unit: '%' }),
          tile({ data, entity: 'sensor.pv_modul_4_leistungsanteil', label: 'PV-Strang 4, Anteil', icon: 'sun', format: 'num', digits: 0, unit: '%' })
        )
      );
      return wrap;
    },
  },

  {
    id: 'steuerung',
    label: 'Steuerung',
    icon: 'tune',
    build(ctx) {
      const { data } = ctx;
      const wrap = el('div', { cls: 'sb-view' });
      wrap.appendChild(ansichtsKopf('Steuerung', 'tune'));
      wrap.appendChild(schreibHinweis());

      wrap.appendChild(abschnitt('Anker-Solix, offizielle Integration', 'tune'));
      const ankerBlock = el('div', { cls: 'sb-karte' });
      ankerBlock.appendChild(
        m3Select({
          data,
          entity: ANKER_SELECT_BETRIEBSMODUS,
          label: 'Betriebsmodus',
          iconName: 'tune',
          quelle: 'select.anker_solix_... (offizielle Integration)',
        })
      );
      ankerBlock.appendChild(
        m3Slider({
          data,
          entity: ANKER_NUMBER_LADEOBERGRENZE,
          label: 'Ladeobergrenze',
          iconName: 'battery',
          quelle: 'number.anker_solix_..._ladeobergrenze (offizielle Integration)',
        })
      );
      ankerBlock.appendChild(
        m3Slider({
          data,
          entity: ANKER_NUMBER_ENTLADEGRENZE,
          label: 'Entladegrenze',
          iconName: 'battery',
          quelle: 'number.anker_solix_..._entladegrenze (offizielle Integration)',
        })
      );
      ankerBlock.appendChild(
        m3Slider({
          data,
          entity: ANKER_NUMBER_NOTSTROMRESERVE,
          label: 'Notstromreserve',
          iconName: 'battery',
          quelle: 'number.anker_solix_..._notstromreserve (offizielle Integration)',
        })
      );
      wrap.appendChild(ankerBlock);

      // Klar abgesetzter Block: Nulleinspeisung als Rueckfallebene.
      wrap.appendChild(abschnitt('Nulleinspeisung (Rueckfallebene)', 'tune'));
      wrap.appendChild(
        hinweis(
          'Eingriffe hier wirken auf die laufende Nulleinspeisungsregelung und werden erst nach ' +
            'Bestaetigung geschrieben.',
          'warnung'
        )
      );
      const neBlock = el('div', { cls: 'sb-karte sb-karte-abgesetzt' });
      neBlock.appendChild(quelleZeile('input_boolean.* / input_number.nulleinspeisung_* (Home-Assistant-Helfer)'));

      neBlock.appendChild(
        m3SwitchBestaetigt({
          data,
          entity: NE_AKTIV,
          label: 'Nulleinspeisung aktiv',
          iconName: 'tune',
          beschreibung: `Schreibt auf ${NE_AKTIV} ueber input_boolean.turn_on/turn_off.`,
        })
      );
      neBlock.appendChild(
        m3SwitchBestaetigt({
          data,
          entity: NE_PRIO,
          label: 'PV-Prioritaetsladung',
          iconName: 'battery',
          beschreibung: `Schreibt auf ${NE_PRIO} ueber input_boolean.turn_on/turn_off.`,
        })
      );

      const parameter = [
        ['regelziel', 'Regelziel'],
        ['totband', 'Totband'],
        ['kp', 'Kp'],
        ['kp_ab', 'Kp (abwaerts)'],
        ['stoerschwelle', 'Stoerschwelle'],
        ['soc_freigabe', 'SOC-Freigabe'],
        ['soc_untergrenze', 'SOC-Untergrenze'],
        ['max_entladeleistung', 'Maximale Entladeleistung'],
        ['prioritaetsladung_max_soc', 'Prioritaetsladung, maximaler SOC'],
        ['speicher_wirkungsgrad', 'Speicherwirkungsgrad (Regelmodell)'],
      ];
      for (const [schluessel, label] of parameter) {
        neBlock.appendChild(
          m3SliderBestaetigt({ data, entity: `${NE}_${schluessel}`, label, iconName: 'tune' })
        );
      }
      wrap.appendChild(neBlock);

      wrap.appendChild(abschnitt('Zustand der Regelung (nur lesend)', 'shield'));
      wrap.appendChild(
        raster(
          tile({ data, entity: 'sensor.nulleinspeisung_regelabweichung', label: 'Regelabweichung', icon: 'shield', format: 'num', digits: 1 }),
          tile({ data, entity: 'sensor.nulleinspeisung_regelfehler', label: 'Regelfehler', icon: 'shield', format: 'num', digits: 3 }),
          tile({ data, entity: 'binary_sensor.nulleinspeisung_regelung_versagt', label: 'Regelung versagt', icon: 'shield', format: 'raw' }),
          tile({ data, entity: 'binary_sensor.nulleinspeisung_zaehler_ok', label: 'Zaehler OK', icon: 'shield', format: 'raw' })
        )
      );
      return wrap;
    },
  },

  {
    id: 'admin',
    label: 'Parameter',
    icon: 'cog',
    build(ctx) {
      const { data } = ctx;
      const wrap = el('div', { cls: 'sb-view' });
      wrap.appendChild(ansichtsKopf('Parameter', 'cog', 'Alle Stellgroessen und Meta-Parameter an einer Stelle.'));
      wrap.appendChild(schreibHinweis());

      wrap.appendChild(abschnitt('Stellgroessen: Anker-Solix (schreibbar)', 'cog'));
      wrap.appendChild(
        raster(
          tile({
            data,
            entity: ANKER_SELECT_BETRIEBSMODUS,
            label: 'Betriebsmodus',
            icon: 'cog',
            format: 'raw',
            hint: 'Herkunft: offizielle Anker-Integration. Bedienung in Ansicht Steuerung.',
          }),
          tile({
            data,
            entity: ANKER_NUMBER_LADEOBERGRENZE,
            label: 'Ladeobergrenze',
            icon: 'cog',
            format: 'num',
            digits: 0,
            hint: 'Herkunft: offizielle Anker-Integration. Bedienung in Ansicht Steuerung.',
          }),
          tile({
            data,
            entity: ANKER_NUMBER_ENTLADEGRENZE,
            label: 'Entladegrenze',
            icon: 'cog',
            format: 'num',
            digits: 0,
            hint: 'Herkunft: offizielle Anker-Integration. Bedienung in Ansicht Steuerung.',
          }),
          tile({
            data,
            entity: ANKER_NUMBER_NOTSTROMRESERVE,
            label: 'Notstromreserve',
            icon: 'cog',
            format: 'num',
            digits: 0,
            hint: 'Herkunft: offizielle Anker-Integration. Bedienung in Ansicht Steuerung.',
          })
        )
      );

      wrap.appendChild(abschnitt('Stellgroessen: Nulleinspeisung (Home-Assistant-Helfer)', 'cog'));
      const neParamRaster = raster(
        tile({
          data,
          entity: NE_AKTIV,
          label: 'Nulleinspeisung aktiv',
          icon: 'cog',
          format: 'raw',
          hint: 'Herkunft: input_boolean. Belegstelle: packages/ (Helper-Definition). Bedienung in Ansicht Steuerung.',
        }),
        tile({
          data,
          entity: NE_PRIO,
          label: 'PV-Prioritaetsladung',
          icon: 'cog',
          format: 'raw',
          hint: 'Herkunft: input_boolean. Bedienung in Ansicht Steuerung.',
        })
      );
      const paramLabels = {
        regelziel: 'Regelziel',
        totband: 'Totband',
        kp: 'Kp',
        kp_ab: 'Kp (abwaerts)',
        stoerschwelle: 'Stoerschwelle',
        soc_freigabe: 'SOC-Freigabe',
        soc_untergrenze: 'SOC-Untergrenze',
        max_entladeleistung: 'Maximale Entladeleistung',
        prioritaetsladung_max_soc: 'Prioritaetsladung, maximaler SOC',
        speicher_wirkungsgrad: 'Speicherwirkungsgrad (Regelmodell)',
      };
      for (const [schluessel, label] of Object.entries(paramLabels)) {
        neParamRaster.appendChild(
          tile({
            data,
            entity: `${NE}_${schluessel}`,
            label,
            icon: 'cog',
            format: 'num',
            digits: 2,
            hint: 'Herkunft: input_number. Bedienung in Ansicht Steuerung.',
          })
        );
      }
      wrap.appendChild(neParamRaster);

      wrap.appendChild(abschnitt('Statische Codewerte (nicht aufklappbar)', 'cog'));
      const statisch = el('div', { cls: 'sb-karte' });
      statisch.appendChild(
        infoZeile({
          label: 'Verschattungsschwellen (Hysterese)',
          wert: `${data.fmtNum(0.6, 2)} / ${data.fmtNum(0.7, 2)}`,
          quelle: 'custom_components/solarbank_pv/const.py (SHADE_ON, SHADE_OFF)',
          hinweis: 'Unter 0,60 gilt ein Strang als verschattet, erst ueber 0,70 wieder als frei.',
        })
      );
      statisch.appendChild(
        infoZeile({
          label: 'Schwachlichtsperre (Hysterese)',
          wert: `${data.fmtNum(30, 0)} W / ${data.fmtNum(60, 0)} W`,
          quelle: 'custom_components/solarbank_pv/const.py (SCHWACHLICHT_SPERRE_W, SCHWACHLICHT_FREI_W)',
          hinweis: 'Unter 30 W wird die Referenzrechnung gesperrt, erst ueber 60 W wieder freigegeben.',
        })
      );
      statisch.appendChild(
        infoZeile({
          label: 'Plausibilitaetsklammer, Batterieleistung',
          wert: `${data.fmtNum(6000, 0)} W`,
          quelle: 'custom_components/solarbank_pv/const.py (BATTERIE_PLAUSIBEL_W)',
        })
      );
      statisch.appendChild(
        infoZeile({
          label: 'Wirkungsgradkurve',
          wert: `η(P) = ${data.fmtNum(0.9572, 4)} − ${data.fmtNum(54.3, 1)} / P`,
          quelle: 'custom_components/solarbank_pv/const.py (Regressionskennwerte), angewendet in physik.py',
        })
      );
      statisch.appendChild(
        infoZeile({
          label: 'Truebungs-Halbwertszeit',
          wert: `${data.fmtNum(120, 0)} min`,
          quelle: 'custom_components/pv_lernprognose/modell.py',
        })
      );
      statisch.appendChild(
        infoZeile({
          label: 'E_FS-Daempfung',
          wert: `${data.fmtNum(20, 0)} min`,
          quelle: 'custom_components/pv_lernprognose/modell.py',
        })
      );
      wrap.appendChild(statisch);

      return wrap;
    },
  },

  {
    id: 'diagnose',
    label: 'Diagnose',
    icon: 'shield',
    build(ctx) {
      const { data } = ctx;
      const wrap = el('div', { cls: 'sb-view' });
      wrap.appendChild(ansichtsKopf('Diagnose', 'shield'));

      const zustand = data.state(DIAGNOSE_GESAMTZUSTAND) || 'unbekannt';
      const ton = zustand === 'ok' ? 'ok' : zustand === 'warnung' ? 'warnung' : 'stoerung';
      wrap.appendChild(
        heldenZahl({
          titel: 'Gesamtzustand',
          wert: zustand.charAt(0).toUpperCase() + zustand.slice(1),
          iconName: 'shield',
          ton,
        })
      );

      wrap.appendChild(abschnitt('Befunde', 'shield'));
      const befunde = data.attr(DIAGNOSE_GESAMTZUSTAND, 'befunde') || [];
      const liste = el('div', { cls: 'sb-karte' });
      if (befunde.length === 0) {
        liste.appendChild(el('p', { cls: 'body', text: 'Keine Befunde - alle zehn Pruefungen unauffaellig.' }));
      } else {
        const ul = document.createElement('ul');
        ul.className = 'sb-befunde';
        for (const b of befunde) {
          const li = document.createElement('li');
          li.className = 'body';
          li.textContent = b;
          ul.appendChild(li);
        }
        liste.appendChild(ul);
      }
      wrap.appendChild(liste);

      wrap.appendChild(abschnitt('Recorder', 'shield'));
      wrap.appendChild(
        raster(tile({ data, entity: DIAGNOSE_DB_GROESSE, label: 'Datenbankgroesse', icon: 'shield', format: 'num', digits: 1 }))
      );

      wrap.appendChild(abschnitt('Geraet', 'shield'));
      wrap.appendChild(
        raster(
          tile({ data, entity: `${ANKER}_firmware_version`, label: 'Firmware', icon: 'shield', format: 'raw' }),
          tile({ data, entity: `${ANKER}_gerate_seriennummer`, label: 'Seriennummer', icon: 'shield', format: 'raw' })
        )
      );

      return wrap;
    },
  },
];

// ---------------------------------------------------------------------------
// M3-Styling der Ansichten. Einmalig beim Laden des Moduls eingefuegt. Nutzt
// die in APP-PLAN.md beschriebenen CSS-Custom-Properties (--surface,
// --primary, --outline-variant, Corner-Tokens, Motion-Dauern) mit
// eigenstaendigen Fallbacks, damit die Ansichten auch dann lesbar bleiben,
// wenn m3.js einzelne Tokens (noch) nicht setzt.
// ---------------------------------------------------------------------------
if (!document.head.querySelector('style[data-sb-style="views"]')) {
  const style = document.createElement('style');
  style.setAttribute('data-sb-style', 'views');
  style.textContent = `
    .sb-view {
      --sb-surface: var(--surface, #fffbf3);
      --sb-surface-container: var(--surface-container, #f3ecdf);
      --sb-surface-container-high: var(--surface-container-high, #ede4d3);
      --sb-surface-container-low: var(--surface-container-low, #faf3e6);
      --sb-on-surface: var(--on-surface, #1f1b13);
      --sb-on-surface-variant: var(--on-surface-variant, #4d4639);
      --sb-primary: var(--primary, #825500);
      --sb-on-primary: var(--on-primary, #ffffff);
      --sb-primary-container: var(--primary-container, #ffddb1);
      --sb-on-primary-container: var(--on-primary-container, #2a1700);
      --sb-secondary: var(--secondary, #6f5b40);
      --sb-outline: var(--outline, #7d7667);
      --sb-outline-variant: var(--outline-variant, #cec5b4);
      --sb-error: var(--error, #ba1a1a);
      --sb-corner-xs: var(--corner-xs, 4px);
      --sb-corner-s: var(--corner-s, 8px);
      --sb-corner-m: var(--corner-m, 12px);
      --sb-corner-l: var(--corner-l, 16px);
      --sb-corner-xl: var(--corner-xl, 28px);
      --sb-motion-standard: var(--motion-standard, 200ms);
      --sb-motion-emphasized: var(--motion-emphasized, 300ms);
      display: flex;
      flex-direction: column;
      gap: 20px;
      padding: 16px;
      max-width: 1100px;
      margin: 0 auto;
      color: var(--sb-on-surface);
      font-family: Roboto, system-ui, sans-serif;
    }
    @media (prefers-color-scheme: dark) {
      .sb-view {
        --sb-surface: var(--surface, #16130c);
        --sb-surface-container: var(--surface-container, #251f13);
        --sb-surface-container-high: var(--surface-container-high, #302918);
        --sb-surface-container-low: var(--surface-container-low, #1f1b10);
        --sb-on-surface: var(--on-surface, #ebe1d4);
        --sb-on-surface-variant: var(--on-surface-variant, #d0c5b4);
        --sb-primary: var(--primary, #ffb951);
        --sb-on-primary: var(--on-primary, #452b00);
        --sb-primary-container: var(--primary-container, #633f00);
        --sb-on-primary-container: var(--on-primary-container, #ffddb1);
        --sb-secondary: var(--secondary, #dbc3a4);
        --sb-outline: var(--outline, #988f7f);
        --sb-outline-variant: var(--outline-variant, #4d4639);
      }
    }
    .sb-view .display { font-size: 2.5rem; font-weight: 500; line-height: 1.15; margin: 0; }
    .sb-view .headline { font-size: 1.7rem; font-weight: 500; margin: 0; }
    .sb-view .title { font-size: 1.1rem; font-weight: 500; margin: 0; }
    .sb-view .body { font-size: 0.95rem; line-height: 1.4; margin: 0; color: var(--sb-on-surface-variant); }
    .sb-view .label { font-size: 0.8rem; font-weight: 500; letter-spacing: 0.02em; color: var(--sb-on-surface-variant); }

    .sb-ansicht-kopf { display: flex; align-items: center; gap: 12px; }
    .sb-kopf-untertitel { margin-top: 2px; }

    .sb-abschnitt { display: flex; align-items: center; gap: 8px; margin-top: 8px; }

    .sb-raster { display: flex; flex-wrap: wrap; gap: 12px; }

    .sb-karte {
      background: var(--sb-surface-container);
      border-radius: var(--sb-corner-l);
      padding: 16px;
      display: flex;
      flex-direction: column;
      gap: 12px;
    }
    .sb-karte-abgesetzt {
      border: 1.5px solid var(--sb-outline-variant);
      background: var(--sb-surface-container-high);
    }
    .sb-karte-kopf { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
    .sb-karte-hinweis { font-style: italic; }

    .sb-chip {
      font-size: 0.72rem;
      font-weight: 600;
      padding: 2px 10px;
      border-radius: var(--sb-corner-xl);
      letter-spacing: 0.02em;
    }
    .sb-chip-lesend { background: var(--sb-surface-container-high); color: var(--sb-on-surface-variant); }
    .sb-chip-warnung { background: var(--sb-primary-container); color: var(--sb-on-primary-container); }

    .sb-hinweis {
      border-radius: var(--sb-corner-m);
      padding: 12px 16px;
      background: var(--sb-surface-container-high);
      border-left: 4px solid var(--sb-outline);
    }
    .sb-hinweis-warnung { border-left-color: var(--sb-primary); }
    .sb-hinweis-info { border-left-color: var(--sb-outline); }

    .sb-quelle { display: block; margin-bottom: 4px; opacity: 0.85; }

    .sb-held {
      display: flex;
      align-items: center;
      gap: 16px;
      background: var(--sb-primary-container);
      color: var(--sb-on-primary-container);
      border-radius: var(--sb-corner-xl);
      padding: 20px 24px;
    }
    .sb-held .display, .sb-held .title { color: inherit; }
    .sb-held-sub { margin-top: 4px; max-width: 46ch; }
    .sb-held-ok { background: var(--sb-surface-container-high); color: #2e7d32; }
    .sb-held-warnung { background: var(--sb-surface-container-high); color: #8a5300; }
    .sb-held-stoerung { background: var(--sb-surface-container-high); color: var(--sb-error); }
    @media (prefers-color-scheme: dark) {
      .sb-held-ok { color: #8bd88f; }
      .sb-held-warnung { color: #ffb951; }
    }

    .sb-inforeihe {
      display: grid;
      grid-template-columns: 1fr auto;
      column-gap: 12px;
      row-gap: 2px;
      padding: 8px 0;
      border-bottom: 1px solid var(--sb-outline-variant);
    }
    .sb-inforeihe:last-child { border-bottom: none; }
    .sb-inforeihe-wert { font-weight: 600; text-align: right; }
    .sb-inforeihe-quelle { grid-column: 1 / -1; opacity: 0.75; }
    .sb-inforeihe-hinweis { grid-column: 1 / -1; }

    .sb-balkenzeile { display: grid; grid-template-columns: 110px 1fr 64px; align-items: center; gap: 10px; padding: 4px 0; }
    .sb-balken-spur { height: 12px; border-radius: var(--sb-corner-xl); background: var(--sb-surface-container-high); overflow: hidden; }
    .sb-balken-fuellung { height: 100%; background: var(--sb-primary); transition: width var(--sb-motion-emphasized) ease; }
    .sb-balken-wert { text-align: right; }
    .sb-sonnenstand { opacity: 0.85; }

    .sb-control { background: var(--sb-surface-container-high); border-radius: var(--sb-corner-m); padding: 12px 16px; display: flex; flex-direction: column; gap: 8px; }
    .sb-control-kopf { display: flex; align-items: center; gap: 8px; }
    .sb-control-kopf .label { flex: 1; }
    .sb-control-wert { font-weight: 600; color: var(--sb-on-surface); }
    .sb-select { padding: 8px 10px; border-radius: var(--sb-corner-s); border: 1px solid var(--sb-outline); background: var(--sb-surface); color: var(--sb-on-surface); min-height: 48px; }
    .sb-slider { width: 100%; accent-color: var(--sb-primary); min-height: 24px; }

    .sb-control-zeile { display: flex; align-items: center; gap: 10px; min-height: 48px; }
    .sb-control-zeile-label { flex: 1; }
    .sb-switch {
      position: relative;
      width: 52px;
      height: 32px;
      border-radius: var(--sb-corner-xl);
      border: 2px solid var(--sb-outline);
      background: var(--sb-surface-container-high);
      cursor: pointer;
      transition: background var(--sb-motion-standard) ease, border-color var(--sb-motion-standard) ease;
      overflow: hidden;
    }
    .sb-switch::after {
      content: '';
      position: absolute;
      top: 3px; left: 3px;
      width: 22px; height: 22px;
      border-radius: 50%;
      background: var(--sb-outline);
      transition: transform var(--sb-motion-standard) ease, background var(--sb-motion-standard) ease;
    }
    .sb-switch.an { background: var(--sb-primary); border-color: var(--sb-primary); }
    .sb-switch.an::after { transform: translateX(20px); background: var(--sb-on-primary); }

    .sb-dialog {
      border: none;
      border-radius: var(--sb-corner-xl);
      padding: 24px;
      max-width: 420px;
      background: var(--sb-surface-container-high);
      color: var(--sb-on-surface);
    }
    .sb-dialog::backdrop { background: rgba(0, 0, 0, 0.4); }
    .sb-dialog-knoepfe { display: flex; justify-content: flex-end; gap: 8px; margin-top: 20px; }
    .sb-btn { min-height: 48px; padding: 0 20px; border-radius: var(--sb-corner-xl); border: none; font-weight: 600; cursor: pointer; }
    .sb-btn-text { background: transparent; color: var(--sb-primary); }
    .sb-btn-filled { background: var(--sb-primary); color: var(--sb-on-primary); }

    .sb-befunde { margin: 0; padding-left: 20px; display: flex; flex-direction: column; gap: 6px; }

    @media (prefers-reduced-motion: reduce) {
      .sb-balken-fuellung, .sb-switch, .sb-switch::after { transition: none; }
    }
  `;
  document.head.appendChild(style);
}
