#!/usr/bin/env node
/*
 * Verschattungsprofil je Strang nach Sonnenazimut.
 *
 * Liest tools/rohdaten/pv4_tag.jsonl und schreibt die Profiltabelle nach
 * stdout. Belegt docs/VERSCHATTUNG-PROFIL.md und speist die Tagesansicht im
 * Dashboard pv-module.
 *
 * Keine Abhaengigkeiten. Aufruf aus dem Repo-Wurzelverzeichnis:
 *     node tools/verschattungsprofil.js
 *
 * Die Sonnenstandsrechnung ist ein Port von
 * custom_components/pv_lernprognose/sonne.py (NOAA). Gegen sun.sun geprueft,
 * Abweichung 0,3 Grad Azimut.
 *
 * Die zweite Quelle der Auswertung - die 5-Minuten-Statistik des Recorders
 * vom 12./13.08. - laesst sich nicht reproduzieren, sie verfaellt nach rund
 * zehn Tagen. Dieses Skript deckt daher nur den 12.08. ab. Die im Dashboard
 * hinterlegte Tabelle enthaelt zusaetzlich die Recorder-Haelfte; sie
 * unterscheidet sich in den Faechern 95-160 Grad um wenige Prozentpunkte.
 */

'use strict';

const fs = require('fs');
const path = require('path');

// --- Standort (Home Assistant zone.home) ---------------------------------
const LAT = 51.76193778594604;
const LON = 7.876596450805665;

// --- Parameter, bewusst gleich denen der Lernprognose ---------------------
const BIN = 5;          // AZIMUT_BIN
const VON = 40;         // AZIMUT_VON
const BIS = 320;        // AZIMUT_BIS
const MIN_PV_W = 50;    // MIN_PV_W
const MIN_HOEHE = 10;   // strenger als MIN_SONNENHOEHE (5): flache Sonne ist Rauschen
const SHADE_ON = 0.60;  // wie binary_sensor.pv_modul_N_verschattet
const SHADE_OFF = 0.70;
const MIN_N = 5;        // Faecher darunter werden nicht veroeffentlicht

// --- Sonnenstand, NOAA ----------------------------------------------------
const rad = (d) => (d * Math.PI) / 180;
const deg = (r) => (r * 180) / Math.PI;
const schaltjahr = (y) => y % 4 === 0 && (y % 100 !== 0 || y % 400 === 0);

function eqtimeDecl(d) {
  const y = d.getUTCFullYear();
  const tage = schaltjahr(y) ? 366 : 365;
  const n = Math.floor((Date.UTC(y, d.getUTCMonth(), d.getUTCDate()) - Date.UTC(y, 0, 1)) / 86400000) + 1;
  const g = ((2 * Math.PI) / tage) * (n - 1 + (d.getUTCHours() - 12) / 24);
  const eqtime = 229.18 * (0.000075 + 0.001868 * Math.cos(g) - 0.032077 * Math.sin(g)
    - 0.014615 * Math.cos(2 * g) - 0.040849 * Math.sin(2 * g));
  const decl = 0.006918 - 0.399912 * Math.cos(g) + 0.070257 * Math.sin(g)
    - 0.006758 * Math.cos(2 * g) + 0.000907 * Math.sin(2 * g)
    - 0.002697 * Math.cos(3 * g) + 0.001480 * Math.sin(3 * g);
  return [eqtime, decl];
}

function sonnenstand(d) {
  const [eqtime, decl] = eqtimeDecl(d);
  const minuten = d.getUTCHours() * 60 + d.getUTCMinutes() + d.getUTCSeconds() / 60;
  const ha = rad((minuten + eqtime + 4 * LON) / 4 - 180);
  const b = rad(LAT);
  let cosz = Math.sin(b) * Math.sin(decl) + Math.cos(b) * Math.cos(decl) * Math.cos(ha);
  cosz = Math.max(-1, Math.min(1, cosz));
  const zenit = Math.acos(cosz);
  const hoehe = 90 - deg(zenit);
  const sinz = Math.sin(zenit);
  if (sinz < 1e-6) return { hoehe, azimut: 180 };
  let cosaz = (Math.sin(decl) - Math.sin(b) * cosz) / (Math.cos(b) * sinz);
  cosaz = Math.max(-1, Math.min(1, cosaz));
  let azimut = deg(Math.acos(cosaz));
  if (ha > 0) azimut = 360 - azimut;
  return { hoehe, azimut };
}

const median = (a) => {
  if (!a.length) return null;
  const s = [...a].sort((x, y) => x - y);
  const m = s.length >> 1;
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
};

// --- Einlesen -------------------------------------------------------------
const datei = process.argv[2] || path.join(__dirname, 'rohdaten', 'pv4_tag.jsonl');
if (!fs.existsSync(datei)) {
  console.error('Nicht gefunden: ' + datei);
  process.exit(1);
}

const punkte = [];
let verworfenLeistung = 0;
let verworfenSonne = 0;

for (const zeile of fs.readFileSync(datei, 'utf8').split('\n')) {
  if (!zeile.trim()) continue;
  let o;
  try { o = JSON.parse(zeile); } catch { continue; }
  if (!o.ok || typeof o.pv_total !== 'number') continue;
  const p = [o.pv1, o.pv2, o.pv3, o.resid];
  if (p.some((x) => typeof x !== 'number')) continue;
  if (o.pv_total < MIN_PV_W) { verworfenLeistung++; continue; }
  const t = new Date(o.t);
  const st = sonnenstand(t);
  if (st.hoehe < MIN_HOEHE) { verworfenSonne++; continue; }
  punkte.push({ az: st.azimut, p, tag: o.t.slice(0, 10) });
}

const tage = [...new Set(punkte.map((x) => x.tag))].sort();
console.log('Quelle: ' + datei);
console.log('Brauchbare Punkte: ' + punkte.length
  + '  (verworfen: PV<' + MIN_PV_W + 'W ' + verworfenLeistung
  + ', Sonne<' + MIN_HOEHE + ' Grad ' + verworfenSonne + ')');
console.log('Kalendertage: ' + tage.join(', '));

// --- Binning --------------------------------------------------------------
const bins = new Map();
for (const pt of punkte) {
  if (pt.az < VON || pt.az > BIS) continue;
  const key = Math.floor((pt.az - VON) / BIN) * BIN + VON;
  if (!bins.has(key)) bins.set(key, { m: [[], [], [], []], n: 0, unbrauchbar: 0, tage: new Set() });
  const b = bins.get(key);
  b.n++;
  b.tage.add(pt.tag);
  // Der Bezug bricht zusammen, wenn zwei Straenge gleichzeitig tief liegen.
  const sortiert = [...pt.p].sort((a, c) => a - c);
  if (sortiert[1] < 0.25 * sortiert[3]) { b.unbrauchbar++; continue; }
  for (let i = 0; i < 4; i++) {
    const uebrige = pt.p.filter((_, j) => j !== i);
    const med = median(uebrige);
    if (med === null || med < 15) continue;
    b.m[i].push(pt.p[i] / med);
  }
}

const keys = [...bins.keys()].sort((a, b) => a - b);
const profil = {};

console.log('\nAzimut | n   | unbr | PV1  PV2  PV3  PV4   (Anteil in %, gedeckelt auf 100)');
console.log('-------+-----+------+---------------------');
for (const k of keys) {
  const b = bins.get(k);
  const brauchbar = b.n >= MIN_N && b.unbrauchbar < b.n * 0.5;
  const meds = b.m.map((a) => (brauchbar && a.length >= MIN_N ? median(a) : null));
  profil[k] = meds.map((x) => (x === null ? null : Math.round(Math.min(x, 1) * 100)));
  const f = (x) => (x === null ? ' -- ' : String(x).padStart(4));
  const mk = meds.map((x) => (x === null ? ' ' : x < SHADE_ON ? '*' : x < SHADE_OFF ? '+' : ' ')).join('');
  console.log(String(k).padStart(6) + ' |' + String(b.n).padStart(4) + ' |' + String(b.unbrauchbar).padStart(5)
    + ' |' + profil[k].map(f).join('') + '   ' + mk + (brauchbar ? '' : '  [Fach verworfen]'));
}
console.log('\n* unter ' + SHADE_ON * 100 + ' % verschattet    + unter ' + SHADE_OFF * 100 + ' % Teilschatten');
console.log('Werte ueber 100 % heissen nur, dass die Nachbarn verschattet sind; sie sind gedeckelt.');

// --- Fenster --------------------------------------------------------------
console.log('\nFenster je Strang (alle getrennten Einbrueche unter ' + SHADE_ON * 100 + ' %):');
const namen = ['PV1 (ganz rechts)', 'PV2', 'PV3', 'PV4 (ganz links)'];
for (let i = 0; i < 4; i++) {
  const fenster = [];
  let start = null;
  let tief = 100;
  for (const k of keys) {
    const v = profil[k][i];
    const sh = v !== null && v < SHADE_ON * 100;
    if (sh) { if (start === null) { start = k; tief = v; } else tief = Math.min(tief, v); }
    else if (start !== null) { fenster.push(start + '-' + k + ' Grad (min ' + tief + ' %)'); start = null; tief = 100; }
  }
  if (start !== null) fenster.push(start + '-' + (keys[keys.length - 1] + BIN) + ' Grad (min ' + tief + ' %)');
  console.log('  ' + namen[i].padEnd(18) + (fenster.length ? fenster.join('   |   ') : 'kein Fenster'));
}

console.log('\nMehrere getrennte Fenster je Strang sind moeglich und werden gefunden -');
console.log('siehe docs/DIAGNOSE.md: es gibt mindestens zwei Schattenwerfer.');
