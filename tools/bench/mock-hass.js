/**
 * Nachgebautes `hass`-Objekt fuer den Pruefstand.
 *
 * Bildet exakt die Form nach, die Home Assistant einem Custom Panel gibt:
 * `states` als Karte entity_id -> { state, attributes, last_changed, ... },
 * dazu `callWS` und `callService`.
 *
 * WICHTIG: Hier wird NICHTS an der echten Anlage gelesen oder geschrieben.
 * Alle Werte sind erfunden. `callService` protokolliert nur - so laesst sich
 * pruefen, dass die Steuerung die richtigen Dienste mit den richtigen Daten
 * aufruft, ohne dass jemals ein Register beschrieben wird.
 */

const ANKER = 'sensor.anker_solix_solarbank_4_e5000_pro_441';
const LERNEN = 'sensor.pv_lernen';
const NE = 'input_number.nulleinspeisung';

/** Baut einen Zustand im HA-Format. */
function z(state, attributes = {}) {
  const jetzt = new Date().toISOString();
  return { state: String(state), attributes, last_changed: jetzt, last_updated: jetzt, context: {} };
}

const W = { unit_of_measurement: 'W', device_class: 'power', state_class: 'measurement' };
const KWH = { unit_of_measurement: 'kWh', device_class: 'energy', state_class: 'total_increasing' };
const V = { unit_of_measurement: 'V', device_class: 'voltage' };
const A = { unit_of_measurement: 'A', device_class: 'current' };
const PCT = { unit_of_measurement: '%' };
const GRAD = { unit_of_measurement: '°C', device_class: 'temperature' };

/**
 * Drei Szenarien, damit die Ansichten nicht nur im Gutfall geprueft werden:
 *
 *   tag       Sonne, Verschattung an PV3, Speicher laedt
 *   nacht     alles null, Referenzrechnung gesperrt, Speicher entlaedt
 *   stoerung  Diagnose meldet Befunde, Werte teils unknown
 */
export function erzeugeHass(szenario = 'tag') {
  const tag = szenario === 'tag';
  const stoerung = szenario === 'stoerung';
  const u = (wert) => (stoerung ? 'unknown' : wert);

  const pv = tag ? [412, 428, 268, 396] : [0.8, 1.1, 4.2, 2.6];
  const pvGesamt = pv.reduce((a, b) => a + b, 0);
  const anteile = tag ? [100, 100, 64, 96] : [19, 26, 100, 62];

  const states = {
    'sun.sun': z(tag ? 'above_horizon' : 'below_horizon', {
      azimuth: tag ? 198.4 : 322.1,
      elevation: tag ? 41.6 : -18.3,
      friendly_name: 'Sonne',
    }),

    // --- offizielle Anker-Integration ---------------------------------
    [`${ANKER}_solarstrom`]: z(u(Math.round(pvGesamt)), { ...W, friendly_name: 'Solarstrom' }),
    [`${ANKER}_soc`]: z(tag ? 74 : 48, { ...PCT, device_class: 'battery', friendly_name: 'Ladezustand' }),
    [`${ANKER}_startseite_last`]: z(tag ? 610 : 480, { ...W, friendly_name: 'Startseite Last' }),
    [`${ANKER}_netzbezugsleistung`]: z(0, { ...W, friendly_name: 'Netzbezug' }),
    [`${ANKER}_netzeinspeiseleistung`]: z(tag ? 0 : 10, { ...W, friendly_name: 'Netzeinspeisung' }),
    [`${ANKER}_ac_ausgang`]: z(tag ? 600 : 480, { ...W, friendly_name: 'AC-Ausgang' }),
    [`${ANKER}_batterieladeleistung`]: z(tag ? 890 : 0, { ...W, friendly_name: 'Ladeleistung' }),
    [`${ANKER}_batterieentladeleistung`]: z(tag ? 0 : 480, { ...W, friendly_name: 'Entladeleistung' }),
    [`${ANKER}_batterie_ladeenergie`]: z(26.1, { ...KWH, friendly_name: 'Ladeenergie' }),
    [`${ANKER}_batterie_entladeenergie`]: z(25.5, { ...KWH, friendly_name: 'Entladeenergie' }),
    [`${ANKER}_akkukapazitat`]: z(5.1, { unit_of_measurement: 'kWh', friendly_name: 'Kapazitaet' }),
    [`${ANKER}_geratestatus`]: z(tag ? 'charging' : 'discharging', { friendly_name: 'Geraetestatus' }),
    [`${ANKER}_gesamte_solarstromerzeugung`]: z(60.6, { ...KWH, friendly_name: 'Gesamterzeugung' }),
    [`${ANKER}_firmware_version`]: z('1.0.2.30', { friendly_name: 'Firmware' }),
    [`${ANKER}_gerate_seriennummer`]: z('AK7DN7M0G21100441', { friendly_name: 'Seriennummer' }),

    'select.anker_solix_solarbank_4_e5000_pro_441_betriebsmodus_gerat_lauft_im_drittanbieter_steuermodus':
      z('self_consumption', { options: ['self_consumption', 'manual', 'backup'], friendly_name: 'Betriebsmodus' }),
    'number.anker_solix_solarbank_4_e5000_pro_441_ladeobergrenze':
      z(100, { min: 50, max: 100, step: 1, ...PCT, friendly_name: 'Ladeobergrenze' }),
    'number.anker_solix_solarbank_4_e5000_pro_441_entladegrenze':
      z(5, { min: 5, max: 50, step: 1, ...PCT, friendly_name: 'Entladegrenze' }),
    'number.anker_solix_solarbank_4_e5000_pro_441_notstromreserve':
      z(stoerung ? 'unknown' : 5, { min: 0, max: 50, step: 1, ...PCT, friendly_name: 'Notstromreserve' }),

    // --- eigene Modbus-Integration, nur lesend --------------------------
    'sensor.solarbank_dc_straenge_441_pv_leistung_gesamt_modbus':
      z(u(Math.round(pvGesamt)), { ...W, modbus_address: 10002, friendly_name: 'PV gesamt (Modbus)' }),
    'sensor.solarbank_dc_straenge_441_pv_batterieleistung_modbus':
      z(tag ? -890 : 480, { ...W, modbus_address: 10008, plausibel_bis_w: 6000, verworfene_werte: 0, friendly_name: 'Batterieleistung (Modbus)' }),
    'sensor.pv_batteriestatus':
      z(tag ? 1 : 2, { modbus_address: 10001, bedeutung: '0=standby, 1=laden, 2=entladen, 3=sleep', friendly_name: 'Batteriestatus' }),
    'sensor.pv_betriebsmodus':
      z(0, { modbus_address: 10064, bedeutung: '0=self_consumption; andere Werte siehe Hersteller-YAML', friendly_name: 'Betriebsmodus (Modbus)' }),
    'sensor.pv_unbekannt_stufenwert_1': z(36, { ...GRAD, modbus_address: 10156, deutung_sicher: false, friendly_name: 'Geraetetemperatur' }),
    'sensor.pv_ac_ausgangslimit': z(800, { ...W, modbus_address: 10038, friendly_name: 'AC-Ausgangslimit' }),
    'sensor.pv_ac_ausgangsstrom': z(2.5, { ...A, modbus_address: 10205, friendly_name: 'AC-Ausgangsstrom' }),
    'sensor.pv_maximale_ladeleistung': z(3000, { ...W, modbus_address: 10036, friendly_name: 'Max. Ladeleistung' }),
    'sensor.pv_theoretische_leistung': tag
      ? z(1712, { ...W, grund: 'ok', traeger_straenge: 3, referenzstrang: 'Modul 2', anteil_klarhimmel: 0.82, mindestleistung_w: 15, sperre_unter_w: 30, freigabe_ueber_w: 60, sperre_aktiv: false, verworfene_zyklen: 0, friendly_name: 'Theoretische Leistung' })
      : z('unknown', { grund: 'Einstrahlung zu schwach', sperre_aktiv: true, verworfene_zyklen: 143, mindestleistung_w: 15, friendly_name: 'Theoretische Leistung' }),
    'sensor.pv_verschattungsverlust': tag
      ? z(208, { ...W, grund: 'ok', rohdifferenz_w: 208, auf_null_geklemmt: false, friendly_name: 'Verschattungsverlust' })
      : z('unknown', { grund: 'Einstrahlung zu schwach', friendly_name: 'Verschattungsverlust' }),
    'sensor.pv_verschattungsverlust_tag': z(0.992, { ...KWH, friendly_name: 'Verschattungsverlust heute' }),
    'sensor.pv_theoretische_energie_tag': z(5.901, { ...KWH, friendly_name: 'Theoretische Energie heute' }),
    'sensor.pv_ertrag_tag': z(10.9, { ...KWH, friendly_name: 'Ertrag heute' }),
    'sensor.pv_nutzungsgrad_heute': z(84, { ...PCT, friendly_name: 'Nutzungsgrad heute' }),
    'sensor.pv_drosselung_leistung': z(0, { ...W, friendly_name: 'Drosselung jetzt' }),
    'sensor.pv_drosselung_tag': z(0.0, { ...KWH, friendly_name: 'Drosselung heute' }),
    'sensor.pv_ersparnis_gesamt': z(41.3, { unit_of_measurement: 'EUR', friendly_name: 'Ersparnis gesamt' }),
    'binary_sensor.pv_abregelung_erkannt': z('off', { friendly_name: 'Abregelung erkannt' }),

    // --- Lernprognose ---------------------------------------------------
    [`${LERNEN}_lernstand`]: z('0 von 4 eingeschwungen', { friendly_name: 'Lernstand' }),
    [`${LERNEN}_pegelfaktor`]: z(1.3, { gelernt: false, friendly_name: 'Pegelfaktor' }),
    [`${LERNEN}_tagesform`]: z(0.94, { gelernt: false, friendly_name: 'Tagesform' }),
    [`${LERNEN}_systemgain`]: z(1.12, { gelernt: false, friendly_name: 'Systemgain' }),
    [`${LERNEN}_truebung`]: z(tag ? 0.78 : 1.0, { friendly_name: 'Truebung' }),
    [`${LERNEN}_klarhimmelleistung`]: z(tag ? 1840 : 0, { ...W, poa: tag ? 712 : 0, friendly_name: 'Klarhimmelleistung' }),
    [`${LERNEN}_hauslast`]: z(430, { ...W, friendly_name: 'Hauslast' }),
    [`${LERNEN}_speicherwirkungsgrad`]: z(0.95, { gelernt: false, friendly_name: 'Speicherwirkungsgrad' }),
    [`${LERNEN}_ziel_erreicht_um`]: z(tag ? new Date(Date.now() + 42 * 60000).toISOString() : 'unknown',
      { device_class: 'timestamp', ziel_soc: 85, soc: tag ? 74 : 48, friendly_name: 'Ziel erreicht um' }),

    // --- Forecast.Solar --------------------------------------------------
    'sensor.energy_production_today': z(9.563, { ...KWH, friendly_name: 'Prognose heute' }),
    'sensor.energy_production_today_remaining': z(tag ? 3.21 : 0.0, { ...KWH, friendly_name: 'Prognose Rest heute' }),
    'sensor.energy_production_tomorrow': z(7.753, { ...KWH, friendly_name: 'Prognose morgen' }),
    'sensor.power_production_now': z(tag ? 1520 : 0, { ...W, friendly_name: 'Prognose jetzt' }),

    // --- Nulleinspeisung -------------------------------------------------
    'input_boolean.nulleinspeisung_aktiv': z('off', { friendly_name: 'Nulleinspeisung aktiv' }),
    'input_boolean.nulleinspeisung_pv_prioritaetsladung': z('off', { friendly_name: 'PV-Prioritaetsladung' }),
    'sensor.nulleinspeisung_regelabweichung': z(-1.0, { ...W, friendly_name: 'Regelabweichung' }),
    'sensor.nulleinspeisung_regelfehler': z(-4.0, { ...W, friendly_name: 'Regelfehler' }),
    'binary_sensor.nulleinspeisung_regelung_versagt': z(stoerung ? 'on' : 'off', { friendly_name: 'Regelung versagt' }),
    'binary_sensor.nulleinspeisung_zaehler_ok': z(stoerung ? 'off' : 'on', { friendly_name: 'Zaehler ok' }),

    // --- Diagnose --------------------------------------------------------
    'sensor.solarbank_diagnose_gesamtzustand': stoerung
      ? z('stoerung', { anzahl: 2, befunde: ['Lesekopf seit 14 min ohne Wert', 'Sollzustand verletzt: Betriebsart weicht ab'], friendly_name: 'Gesamtzustand' })
      : z('ok', { anzahl: 0, befunde: [], friendly_name: 'Gesamtzustand' }),
    'sensor.diagnose_recorder_datenbankgroesse': z(1208.4, { unit_of_measurement: 'MiB', friendly_name: 'Datenbankgroesse' }),
  };

  // Strangwerte
  const spannungen = tag ? [28.9, 29.1, 31.4, 29.0] : [3.1, 3.4, 6.8, 4.2];
  const stroeme = tag ? [14.26, 14.71, 8.54, 13.66] : [0.26, 0.32, 0.62, 0.62];
  for (let i = 0; i < 4; i++) {
    const n = i + 1;
    states[`sensor.pv_modul_${n}_leistung`] = z(pv[i].toFixed(1), { ...W, friendly_name: `Modul ${n} Leistung` });
    states[`sensor.pv_modul_${n}_leistungsanteil`] = z(anteile[i], { ...PCT, friendly_name: `Modul ${n} Leistungsanteil` });
    if (n < 4) {
      states[`sensor.pv_modul_${n}_spannung`] = z(spannungen[i], { ...V, modbus_address: 10166 + n * 2 - 1, friendly_name: `Modul ${n} Spannung` });
      states[`sensor.pv_modul_${n}_strom`] = z(stroeme[i], { ...A, modbus_address: 10166 + n * 2, friendly_name: `Modul ${n} Strom` });
      states[`sensor.pv_modul_${n}_stromanteil`] = z(anteile[i], { ...PCT, friendly_name: `Modul ${n} Stromanteil` });
      states[`sensor.pv_modul_${n}_zelltemperatur`] = z(tag ? 54 - i * 6 : 18, { ...GRAD, friendly_name: `Modul ${n} Zelltemperatur` });
    }
  }
  states['sensor.pv_modul_4_spannung_geschaetzt'] = z(spannungen[3], { ...V, gemessen: false, schaetzfehler_prozent: 1.0, friendly_name: 'Modul 4 Spannung (geschaetzt)' });
  states['sensor.pv_modul_4_strom_geschaetzt'] = z(stroeme[3], { ...A, gemessen: false, schaetzfehler_prozent: 10.0, friendly_name: 'Modul 4 Strom (geschaetzt)' });

  // Nulleinspeisungs-Parameter
  const params = {
    regelziel: [50, 0, 300, 5, 'W'], totband: [45, 0, 200, 5, 'W'],
    kp: [0.05, 0, 1, 0.01, ''], kp_ab: [0.12, 0, 1, 0.01, ''],
    stoerschwelle: [150, 0, 1000, 10, 'W'], soc_freigabe: [20, 0, 100, 1, '%'],
    soc_untergrenze: [12, 0, 100, 1, '%'], max_entladeleistung: [800, 0, 2500, 50, 'W'],
    max_ac_ladeleistung: [0, 0, 3000, 50, 'W'], min_schreibdelta: [1, 0, 50, 1, 'W'],
    prioritaetsladung_max_soc: [85, 50, 100, 1, '%'], speicher_wirkungsgrad: [0.95, 0.5, 1, 0.01, ''],
  };
  for (const [name, [wert, min, max, step, unit]] of Object.entries(params)) {
    states[`${NE}_${name}`] = z(wert, { min, max, step, unit_of_measurement: unit, mode: 'slider', friendly_name: name });
  }

  return {
    states,
    themes: { darkMode: true },
    language: 'de',
    locale: { language: 'de', number_format: 'comma_decimal' },
    config: { unit_system: { temperature: '°C' } },

    /** Historie und Statistik: plausible Kurven, damit Sparklines etwas zeigen. */
    async callWS(msg) {
      if (msg && msg.type === 'history/history_during_period') {
        const id = (msg.entity_ids || [])[0];
        const basis = parseFloat((states[id] || {}).state) || 100;
        const n = 96;
        const jetzt = Date.now();
        const punkte = Array.from({ length: n }, (_, i) => ({
          s: String(Math.max(0, basis * (0.55 + 0.45 * Math.sin((i / n) * Math.PI)) + (i % 7) * 2).toFixed(2)),
          lu: (jetzt - (n - i) * 15 * 60000) / 1000,
        }));
        return { [id]: punkte };
      }
      if (msg && msg.type === 'recorder/statistics_during_period') {
        const id = (msg.statistic_ids || [])[0];
        const basis = parseFloat((states[id] || {}).state) || 100;
        const jetzt = Date.now();
        return {
          [id]: Array.from({ length: 168 }, (_, i) => ({
            start: jetzt - (168 - i) * 3600000,
            mean: basis * (0.6 + 0.4 * Math.sin(i / 12)),
          })),
        };
      }
      return {};
    },

    /** Protokolliert statt zu schreiben. Der Prueflauf liest window.__benchAufrufe. */
    async callService(domain, service, data) {
      window.__benchAufrufe = window.__benchAufrufe || [];
      window.__benchAufrufe.push({ domain, service, data });
      console.log('[bench] callService', domain, service, JSON.stringify(data));
      return {};
    },
  };
}
