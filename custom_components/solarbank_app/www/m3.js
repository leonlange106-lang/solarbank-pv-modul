/**
 * m3.js — Material Design 3 für die Solarbank-App.
 *
 * Reines ES-Modul, kein Build-Schritt, keine Abhängigkeit. Liefert drei
 * Dinge:
 *
 *   M3_CSS  – vollständiges Stylesheet (Tokens + Basiskomponenten) als
 *             Template-String. Wird von app.js EINMAL in den Shadow Root
 *             der Panel-Shell injiziert. Alle `--md-sys-*`-Variablen
 *             werden auf `:host` gesetzt und vererben sich dadurch auch
 *             in verschachtelte Custom Elements (z. B. <sb-tile>) hinein –
 *             CSS-Variablen durchqueren Shadow-Grenzen entlang des
 *             tatsächlichen DOM-Baums.
 *   icon()  – liefert Icon-Markup (SVG als String) für einen Namen.
 *   ripple() – hängt State Layer (Hover/Pressed/Focus) und Ripple-Welle
 *              an ein beliebiges Element.
 *
 * Farbsystem: M3-Tonal-Palette aus Quellfarbe Solar-Amber (#F5A623) für
 * Primär, gedämpftes Blaugrau für Sekundär, ein zurückhaltendes Violett
 * für Tertiär. Die Tonwerte sind von Hand aus HSL abgeleitet (keine
 * Material-Color-Utilities verfügbar, da kein Build-Schritt/npm erlaubt
 * ist) – Rollen und Kontrastbeziehungen folgen aber genau dem M3-Schema.
 */

// -----------------------------------------------------------------------
// M3_CSS
// -----------------------------------------------------------------------

export const M3_CSS = `
/* ==========================================================================
   1. Basis-Reset
   ========================================================================== */

:host, .md-app-shell {
  box-sizing: border-box;
}
:host *, :host *::before, :host *::after {
  box-sizing: inherit;
}
:host {
  display: block;
  font-family: "Roboto", "Segoe UI", system-ui, -apple-system, "Helvetica Neue", Arial, sans-serif;
  font-size: 14px;
  line-height: 1.4;
  color: var(--md-sys-color-on-surface);
  background: var(--md-sys-color-surface);
  -webkit-font-smoothing: antialiased;
  -webkit-tap-highlight-color: transparent;
}
:host *:focus-visible {
  outline: 2px solid var(--md-sys-color-primary);
  outline-offset: 2px;
}
button, input, select {
  font: inherit;
  color: inherit;
}

/* ==========================================================================
   2. Farbrollen — hell (Standard)
   Quellfarbe Primär: Solar-Amber #F5A623 (HSL ≈ 37°, 91 %, 55 %)
   Quellfarbe Sekundär: Blaugrau, Quellfarbe Tertiär: gedämpftes Violett
   ========================================================================== */

:host {
  --md-sys-color-primary: #C07B0C;
  --md-sys-color-on-primary: #FFFFFF;
  --md-sys-color-primary-container: #FCEBCF;
  --md-sys-color-on-primary-container: #301F03;

  --md-sys-color-secondary: #546378;
  --md-sys-color-on-secondary: #FFFFFF;
  --md-sys-color-secondary-container: #E1E5EA;
  --md-sys-color-on-secondary-container: #15191E;

  --md-sys-color-tertiary: #5E4983;
  --md-sys-color-on-tertiary: #FFFFFF;
  --md-sys-color-tertiary-container: #E4DEED;
  --md-sys-color-on-tertiary-container: #181221;

  --md-sys-color-error: #AF291D;
  --md-sys-color-on-error: #FFFFFF;
  --md-sys-color-error-container: #F8D6D3;
  --md-sys-color-on-error-container: #2C0A07;

  --md-sys-color-surface: #FAFAFA;
  --md-sys-color-on-surface: #1B1A18;
  --md-sys-color-surface-variant: #E8E6E3;
  --md-sys-color-on-surface-variant: #544E45;
  --md-sys-color-surface-dim: #E0DEDC;
  --md-sys-color-surface-bright: #FAFAFA;

  --md-sys-color-surface-container-lowest: #FFFFFF;
  --md-sys-color-surface-container-low: #F5F5F4;
  --md-sys-color-surface-container: #F0F0EF;
  --md-sys-color-surface-container-high: #ECEBEA;
  --md-sys-color-surface-container-highest: #E7E6E4;

  --md-sys-color-outline: #8C8273;
  --md-sys-color-outline-variant: #D1CDC7;

  --md-sys-color-inverse-surface: #363430;
  --md-sys-color-inverse-on-surface: #F3F2F2;
  --md-sys-color-inverse-primary: #F9D69F;

  --md-sys-color-shadow: #000000;
  --md-sys-color-scrim: #000000;

  /* Statusfarben (Ampel), unabhängig von der Markenfarbe, für den
     Gesamtzustand in der Kopfzeile und ähnliche Diagnoseanzeigen. */
  --md-status-ok: #2E7D32;
  --md-status-warnung: #ED6C02;
  --md-status-fehler: var(--md-sys-color-error);
}

/* ==========================================================================
   3. Farbrollen — dunkel
   ========================================================================== */

@media (prefers-color-scheme: dark) {
  :host {
    --md-sys-color-primary: #F9D69F;
    --md-sys-color-on-primary: #603D06;
    --md-sys-color-primary-container: #905C09;
    --md-sys-color-on-primary-container: #FCEBCF;

    --md-sys-color-secondary: #C3CAD5;
    --md-sys-color-on-secondary: #2A313C;
    --md-sys-color-secondary-container: #3F4A5A;
    --md-sys-color-on-secondary-container: #E1E5EA;

    --md-sys-color-tertiary: #C8BEDA;
    --md-sys-color-on-tertiary: #2F2541;
    --md-sys-color-tertiary-container: #473762;
    --md-sys-color-on-tertiary-container: #E4DEED;

    --md-sys-color-error: #F1ADA7;
    --md-sys-color-on-error: #58140E;
    --md-sys-color-error-container: #841F15;
    --md-sys-color-on-error-container: #F8D6D3;

    --md-sys-color-surface: #100F0F;
    --md-sys-color-on-surface: #E7E6E4;
    --md-sys-color-surface-variant: #544E45;
    --md-sys-color-on-surface-variant: #D1CDC7;
    --md-sys-color-surface-dim: #100F0F;
    --md-sys-color-surface-bright: #403E3A;

    --md-sys-color-surface-container-lowest: #0B0A0A;
    --md-sys-color-surface-container-low: #1B1A18;
    --md-sys-color-surface-container: #201F1D;
    --md-sys-color-surface-container-high: #2E2C29;
    --md-sys-color-surface-container-highest: #3B3935;

    --md-sys-color-outline: #A39B8F;
    --md-sys-color-outline-variant: #544E45;

    --md-sys-color-inverse-surface: #E7E6E4;
    --md-sys-color-inverse-on-surface: #363430;
    --md-sys-color-inverse-primary: #C07B0C;

    --md-status-ok: #7BC67E;
    --md-status-warnung: #FFB74D;
    --md-status-fehler: var(--md-sys-color-error);
  }
}

/* ==========================================================================
   4. Typografie-Skala
   ========================================================================== */

.md-display-small  { font-size: 36px; line-height: 44px; font-weight: 400; letter-spacing: 0; margin: 0; }
.md-headline-small { font-size: 24px; line-height: 32px; font-weight: 400; letter-spacing: 0; margin: 0; }
.md-title-large     { font-size: 22px; line-height: 28px; font-weight: 400; letter-spacing: 0; margin: 0; }
.md-title-medium    { font-size: 16px; line-height: 24px; font-weight: 500; letter-spacing: 0.15px; margin: 0; }
.md-body-medium      { font-size: 14px; line-height: 20px; font-weight: 400; letter-spacing: 0.25px; margin: 0; }
.md-body-small        { font-size: 12px; line-height: 16px; font-weight: 400; letter-spacing: 0.4px; margin: 0; }
.md-label-large      { font-size: 14px; line-height: 20px; font-weight: 500; letter-spacing: 0.1px; margin: 0; }
.md-label-medium     { font-size: 12px; line-height: 16px; font-weight: 500; letter-spacing: 0.5px; margin: 0; }

/* ==========================================================================
   5. Form, Elevation, Motion, Zustandsschicht-Opazitäten
   ========================================================================== */

:host {
  --md-sys-shape-corner-xs: 4px;
  --md-sys-shape-corner-s: 8px;
  --md-sys-shape-corner-m: 12px;
  --md-sys-shape-corner-l: 16px;
  --md-sys-shape-corner-xl: 28px;
  --md-sys-shape-corner-full: 999px;

  /* Aliase mit den ausgeschriebenen offiziellen M3-Namen, damit andere
     Module der App (z. B. tile.js) dieselben Tokens unter dem ihnen
     geläufigen Namen lesen können. */
  --md-sys-shape-corner-extra-small: var(--md-sys-shape-corner-xs);
  --md-sys-shape-corner-small: var(--md-sys-shape-corner-s);
  --md-sys-shape-corner-medium: var(--md-sys-shape-corner-m);
  --md-sys-shape-corner-large: var(--md-sys-shape-corner-l);
  --md-sys-shape-corner-extra-large: var(--md-sys-shape-corner-xl);

  --md-sys-elevation-level0: none;
  --md-sys-elevation-level1: 0 1px 2px rgba(0, 0, 0, 0.30), 0 1px 3px 1px rgba(0, 0, 0, 0.15);
  --md-sys-elevation-level2: 0 1px 2px rgba(0, 0, 0, 0.30), 0 2px 6px 2px rgba(0, 0, 0, 0.15);
  --md-sys-elevation-level3: 0 1px 3px rgba(0, 0, 0, 0.30), 0 4px 8px 3px rgba(0, 0, 0, 0.15);
  --md-sys-elevation-level4: 0 2px 3px rgba(0, 0, 0, 0.30), 0 6px 10px 4px rgba(0, 0, 0, 0.15);
  --md-sys-elevation-level5: 0 4px 4px rgba(0, 0, 0, 0.30), 0 8px 12px 6px rgba(0, 0, 0, 0.15);

  --md-sys-motion-easing-emphasized: cubic-bezier(0.2, 0, 0, 1);
  --md-sys-motion-easing-standard: cubic-bezier(0.2, 0, 0, 1);
  --md-sys-motion-duration-short: 200ms;
  --md-sys-motion-duration-medium: 300ms;
  --md-sys-motion-duration-long: 500ms;

  --md-sys-state-hover-opacity: 0.08;
  --md-sys-state-pressed-opacity: 0.12;
  --md-sys-state-focus-opacity: 0.12;
}

@media (prefers-reduced-motion: reduce) {
  :host *, :host *::before, :host *::after {
    animation-duration: 0.001ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.001ms !important;
    scroll-behavior: auto !important;
  }
}

/* ==========================================================================
   6. Zustandsschicht (State Layer) + Ripple
   Wird von der Funktion ripple() aus diesem Modul an Elemente angehängt.
   Hover 8 %, Pressed/Focus 12 % — Deckkraft über currentColor, damit die
   Schicht automatisch zur Textfarbe des jeweiligen Trägerelements passt.
   ========================================================================== */

.md-ripple-host {
  position: relative;
  overflow: hidden;
}
.md-state-layer {
  position: absolute;
  inset: 0;
  pointer-events: none;
  background-color: currentColor;
  opacity: 0;
  border-radius: inherit;
  transition: opacity 120ms var(--md-sys-motion-easing-standard);
}
.md-ripple-host:hover .md-state-layer {
  opacity: var(--md-sys-state-hover-opacity);
}
.md-ripple-host:active .md-state-layer,
.md-ripple-host.md-pressed .md-state-layer {
  opacity: var(--md-sys-state-pressed-opacity);
}
.md-ripple-host:focus-visible .md-state-layer {
  opacity: var(--md-sys-state-focus-opacity);
}
.md-ripple-wave {
  position: absolute;
  border-radius: 50%;
  background-color: currentColor;
  opacity: 0.16;
  transform: scale(0);
  pointer-events: none;
  animation: md-ripple-anim var(--md-sys-motion-duration-long) var(--md-sys-motion-easing-standard);
}
@keyframes md-ripple-anim {
  to { transform: scale(1); opacity: 0; }
}
@media (prefers-reduced-motion: reduce) {
  .md-ripple-wave { animation: none; display: none; }
}

/* ==========================================================================
   7. Komponenten
   ========================================================================== */

/* -- Card ------------------------------------------------------------- */
.md-card {
  background: var(--md-sys-color-surface-container);
  color: var(--md-sys-color-on-surface);
  border-radius: var(--md-sys-shape-corner-m);
  padding: 16px;
  box-shadow: var(--md-sys-elevation-level0);
  transition: box-shadow var(--md-sys-motion-duration-short) var(--md-sys-motion-easing-standard);
}
.md-card.elevated {
  background: var(--md-sys-color-surface-container-low);
  box-shadow: var(--md-sys-elevation-level1);
}
.md-card.elevated:hover {
  box-shadow: var(--md-sys-elevation-level2);
}

/* -- List --------------------------------------------------------------- */
.md-list {
  display: flex;
  flex-direction: column;
  background: var(--md-sys-color-surface-container-low);
  border-radius: var(--md-sys-shape-corner-m);
  overflow: hidden;
}
.md-list-item {
  display: flex;
  align-items: center;
  gap: 16px;
  min-height: 56px;
  padding: 8px 16px;
  color: var(--md-sys-color-on-surface);
  cursor: pointer;
}
.md-list-item + .md-list-item {
  border-top: 1px solid var(--md-sys-color-outline-variant);
}
.md-list-item-leading {
  flex: none;
  width: 24px;
  height: 24px;
  color: var(--md-sys-color-primary);
  display: flex;
  align-items: center;
  justify-content: center;
}
.md-list-item-body {
  flex: 1 1 auto;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.md-list-item-trailing {
  flex: none;
  color: var(--md-sys-color-on-surface-variant);
}

/* -- Divider -------------------------------------------------------------- */
.md-divider {
  border: none;
  border-top: 1px solid var(--md-sys-color-outline-variant);
  margin: 0;
  width: 100%;
}
.md-divider.vertical {
  border-top: none;
  border-left: 1px solid var(--md-sys-color-outline-variant);
  width: 0;
  height: 100%;
}

/* -- Switch --------------------------------------------------------------- */
.md-switch {
  position: relative;
  display: inline-flex;
  align-items: center;
  width: 52px;
  height: 32px;
  cursor: pointer;
  flex: none;
}
.md-switch::before {
  /* vergrößert die Tapp-Fläche unsichtbar auf mindestens 48 px */
  content: "";
  position: absolute;
  inset: -8px;
}
.md-switch-input {
  position: absolute;
  inset: 0;
  margin: 0;
  opacity: 0;
  cursor: pointer;
}
.md-switch-track {
  position: absolute;
  inset: 0;
  border-radius: var(--md-sys-shape-corner-full);
  background: var(--md-sys-color-surface-container-highest);
  border: 2px solid var(--md-sys-color-outline);
  transition: background-color var(--md-sys-motion-duration-short) var(--md-sys-motion-easing-standard),
              border-color var(--md-sys-motion-duration-short) var(--md-sys-motion-easing-standard);
}
.md-switch-thumb {
  position: absolute;
  top: 50%;
  left: 4px;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: var(--md-sys-color-outline);
  transform: translateY(-50%);
  transition: left var(--md-sys-motion-duration-short) var(--md-sys-motion-easing-emphasized),
              width var(--md-sys-motion-duration-short) var(--md-sys-motion-easing-emphasized),
              height var(--md-sys-motion-duration-short) var(--md-sys-motion-easing-emphasized),
              background-color var(--md-sys-motion-duration-short) var(--md-sys-motion-easing-standard);
}
.md-switch-input:checked ~ .md-switch-track {
  background: var(--md-sys-color-primary);
  border-color: var(--md-sys-color-primary);
}
.md-switch-input:checked ~ .md-switch-track .md-switch-thumb {
  left: 28px;
  width: 24px;
  height: 24px;
  top: 50%;
  background: var(--md-sys-color-on-primary);
}
.md-switch-input:disabled ~ .md-switch-track {
  opacity: 0.38;
  cursor: not-allowed;
}
.md-switch-input:focus-visible ~ .md-switch-track {
  outline: 2px solid var(--md-sys-color-primary);
  outline-offset: 2px;
}

/* -- Slider ---------------------------------------------------------------- */
.md-slider {
  -webkit-appearance: none;
  appearance: none;
  width: 100%;
  height: 40px;
  background: transparent;
  cursor: pointer;
}
.md-slider::-webkit-slider-runnable-track {
  height: 4px;
  border-radius: var(--md-sys-shape-corner-full);
  background: var(--md-sys-color-surface-container-highest);
}
.md-slider::-moz-range-track {
  height: 4px;
  border-radius: var(--md-sys-shape-corner-full);
  background: var(--md-sys-color-surface-container-highest);
}
.md-slider::-webkit-slider-thumb {
  -webkit-appearance: none;
  margin-top: -8px;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: var(--md-sys-color-primary);
  border: 2px solid var(--md-sys-color-on-primary);
  box-shadow: var(--md-sys-elevation-level1);
}
.md-slider::-moz-range-thumb {
  width: 20px;
  height: 20px;
  border: 2px solid var(--md-sys-color-on-primary);
  border-radius: 50%;
  background: var(--md-sys-color-primary);
  box-shadow: var(--md-sys-elevation-level1);
}
.md-slider:disabled {
  opacity: 0.38;
  cursor: not-allowed;
}

/* -- Segmented Button ------------------------------------------------------ */
.md-segmented {
  display: inline-flex;
  border: 1px solid var(--md-sys-color-outline);
  border-radius: var(--md-sys-shape-corner-full);
  overflow: hidden;
}
.md-segmented button {
  appearance: none;
  border: none;
  background: transparent;
  color: var(--md-sys-color-on-surface);
  padding: 0 16px;
  min-height: 48px;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 8px;
}
.md-segmented button + button {
  border-left: 1px solid var(--md-sys-color-outline);
}
.md-segmented button.active {
  background: var(--md-sys-color-secondary-container);
  color: var(--md-sys-color-on-secondary-container);
  font-weight: 500;
}

/* -- Chip -------------------------------------------------------------------- */
.md-chip {
  position: relative;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  height: 32px;
  padding: 0 12px;
  border-radius: var(--md-sys-shape-corner-s);
  border: 1px solid var(--md-sys-color-outline);
  background: transparent;
  color: var(--md-sys-color-on-surface-variant);
  cursor: pointer;
}
.md-chip::before {
  /* vergrößert die Tapp-Fläche unsichtbar auf mindestens 48 px */
  content: "";
  position: absolute;
  inset: -8px;
}
.md-chip.active {
  background: var(--md-sys-color-secondary-container);
  color: var(--md-sys-color-on-secondary-container);
  border-color: transparent;
}

/* -- FAB ----------------------------------------------------------------------- */
.md-fab {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  width: 56px;
  height: 56px;
  border: none;
  border-radius: var(--md-sys-shape-corner-l);
  background: var(--md-sys-color-primary-container);
  color: var(--md-sys-color-on-primary-container);
  box-shadow: var(--md-sys-elevation-level3);
  cursor: pointer;
  transition: box-shadow var(--md-sys-motion-duration-short) var(--md-sys-motion-easing-standard);
}
.md-fab:hover {
  box-shadow: var(--md-sys-elevation-level4);
}
.md-fab.small {
  width: 40px;
  height: 40px;
  border-radius: var(--md-sys-shape-corner-m);
}
.md-fab.extended {
  width: auto;
  padding: 0 20px;
}

/* -- Dialog ----------------------------------------------------------------------- */
.md-dialog-scrim {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.32);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}
.md-dialog {
  background: var(--md-sys-color-surface-container-high);
  color: var(--md-sys-color-on-surface);
  border-radius: var(--md-sys-shape-corner-xl);
  box-shadow: var(--md-sys-elevation-level3);
  padding: 24px;
  max-width: min(560px, 90vw);
  max-height: 85vh;
  overflow: auto;
}

/* -- Snackbar ----------------------------------------------------------------------- */
.md-snackbar {
  position: fixed;
  left: 50%;
  bottom: 24px;
  transform: translateX(-50%);
  display: flex;
  align-items: center;
  gap: 16px;
  min-height: 48px;
  padding: 0 16px;
  border-radius: var(--md-sys-shape-corner-xs);
  background: var(--md-sys-color-inverse-surface);
  color: var(--md-sys-color-inverse-on-surface);
  box-shadow: var(--md-sys-elevation-level3);
  z-index: 1100;
}
.md-snackbar-action {
  appearance: none;
  border: none;
  background: none;
  color: var(--md-sys-color-inverse-primary);
  font-weight: 500;
  cursor: pointer;
  padding: 0;
}

/* ==========================================================================
   8. Navigation — responsiv
   Nav-Bar unten ≤ 600 px · Nav-Rail links 601–1239 px ·
   erweiterter Rail/Drawer ≥ 1240 px
   ========================================================================== */

.md-nav-bar {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
  justify-content: space-around;
  align-items: stretch;
  height: 80px;
  padding: 4px 0;
  background: var(--md-sys-color-surface-container);
  border-top: 1px solid var(--md-sys-color-outline-variant);
  z-index: 20;
}
.md-nav-rail {
  position: fixed;
  left: 0;
  top: 0;
  bottom: 0;
  width: 80px;
  display: none;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding-top: 44px;
  background: var(--md-sys-color-surface);
  border-right: 1px solid var(--md-sys-color-outline-variant);
  overflow-y: auto;
  z-index: 20;
}

.md-nav-item {
  position: relative;
  display: flex;
  align-items: center;
  min-height: 48px;
  min-width: 48px;
  padding: 8px 12px;
  border: none;
  background: transparent;
  color: var(--md-sys-color-on-surface-variant);
  cursor: pointer;
}
.md-nav-bar .md-nav-item {
  flex-direction: column;
  justify-content: center;
  gap: 4px;
  flex: 1 1 0;
  padding: 8px 4px;
}
.md-nav-rail .md-nav-item {
  flex-direction: column;
  justify-content: center;
  gap: 4px;
  width: 64px;
}
.md-nav-item-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: var(--md-sys-shape-corner-xl);
  transition: background-color var(--md-sys-motion-duration-short) var(--md-sys-motion-easing-standard),
              color var(--md-sys-motion-duration-short) var(--md-sys-motion-easing-standard);
}
.md-nav-item-icon svg {
  width: 24px;
  height: 24px;
}
.md-nav-item-label {
  white-space: nowrap;
}
.md-nav-item.active .md-nav-item-icon {
  background: var(--md-sys-color-secondary-container);
  color: var(--md-sys-color-on-secondary-container);
}
.md-nav-item.active .md-nav-item-label {
  color: var(--md-sys-color-on-surface);
  font-weight: 500;
}

@media (max-width: 600px) {
  .md-nav-bar { display: flex; }
  .md-nav-rail { display: none; }
}
@media (min-width: 601px) {
  .md-nav-bar { display: none; }
  .md-nav-rail { display: flex; }
}
@media (min-width: 1240px) {
  .md-nav-rail {
    width: 220px;
    align-items: stretch;
    padding-left: 12px;
    padding-right: 12px;
  }
  .md-nav-rail .md-nav-item {
    flex-direction: row;
    justify-content: flex-start;
    width: auto;
    gap: 12px;
    border-radius: var(--md-sys-shape-corner-xl);
  }
}

/* ==========================================================================
   9. App-Shell — Kopfzeile, Datenschnitt-Banner, Hauptbereich, Fehlerkarte
   Ergänzende, nicht im Kernkatalog geforderte Klassen, die app.js für die
   Panel-Hülle benötigt. Nutzen ausschließlich die obigen Tokens.
   ========================================================================== */

.md-app-shell {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  background: var(--md-sys-color-surface);
  color: var(--md-sys-color-on-surface);
}
.md-app-bar {
  position: sticky;
  top: 0;
  z-index: 10;
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: 64px;
  padding: 0 20px;
  background: var(--md-sys-color-surface-container);
  border-bottom: 1px solid var(--md-sys-color-outline-variant);
}
.md-app-bar-back {
  display: inline-flex; align-items: center; justify-content: center;
  width: 48px; height: 48px; margin-right: 4px;
  border: none; background: none; cursor: pointer; padding: 0;
  color: var(--md-sys-color-on-surface);
  border-radius: 50%;
  /* Der Chevron zeigt nach rechts; fuer "zurueck" gespiegelt. */
  transform: rotate(180deg);
}
.md-app-bar-back:hover { background: color-mix(in srgb, var(--md-sys-color-on-surface) 8%, transparent); }
.md-app-bar-back[hidden] { display: none; }
.md-app-bar-title {
  color: var(--md-sys-color-on-surface);
}
.md-status-dot {
  flex: none;
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: var(--md-sys-color-outline);
}
.md-status-dot.ok { background: var(--md-status-ok); }
.md-status-dot.warnung { background: var(--md-status-warnung); }
.md-status-dot.fehler { background: var(--md-status-fehler); }

.md-banner {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 20px;
  background: var(--md-sys-color-tertiary-container);
  color: var(--md-sys-color-on-tertiary-container);
  border-bottom: 1px solid var(--md-sys-color-outline-variant);
}
.md-banner[hidden] {
  display: none;
}
.md-banner-icon {
  flex: none;
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.md-banner-icon svg {
  width: 24px;
  height: 24px;
}

.md-view {
  flex: 1 1 auto;
  padding: 16px;
  padding-bottom: calc(80px + 16px);
}
@media (min-width: 601px) {
  .md-view { padding: 16px; padding-left: calc(80px + 24px); }
}
@media (min-width: 1240px) {
  .md-view { padding-left: calc(220px + 24px); }
}

.md-error-card {
  border: 1px solid var(--md-sys-color-error);
  background: var(--md-sys-color-error-container);
  color: var(--md-sys-color-on-error-container);
}
.md-error-card-head {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 8px;
}
.md-error-card-icon {
  flex: none;
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.md-error-card-icon svg {
  width: 24px;
  height: 24px;
}
`;

// -----------------------------------------------------------------------
// icon()
// -----------------------------------------------------------------------

// Innere Pfad-/Formmarkup je Icon, jeweils für ein 24x24-viewBox gedacht.
// Die meisten sind gefüllt (erben fill="currentColor" vom umschließenden
// <svg>), einige (chevron, close, warning, info) zeichnen bewusst mit
// Konturlinien, damit sie bei jeder Größe klar lesbar bleiben.
const ICON_PATHS = {
  home: '<path d="M10 20v-6h4v6h5v-8h3L12 3 2 12h3v8z"/>',

  'solar-power':
    '<path d="M4 8h16v10H4z" fill="none" stroke="currentColor" stroke-width="1.6"/>' +
    '<path d="M4 13h16M9.33 8v10M14.67 8v10" fill="none" stroke="currentColor" stroke-width="1.2"/>' +
    '<path d="M7 5.5 5.5 3.5M17 5.5 18.5 3.5M12 5V2.2" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>',

  battery:
    '<rect x="4" y="6" width="14" height="12" rx="2" fill="none" stroke="currentColor" stroke-width="1.6"/>' +
    '<rect x="18.5" y="10" width="2" height="4" rx="1"/>' +
    '<rect x="6.5" y="8.5" width="7" height="7" rx="1"/>',

  grid:
    '<path d="M12 3 18 21H6Z" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/>' +
    '<path d="M8.4 13h7.2M7.2 17h9.6" stroke="currentColor" stroke-width="1.4"/>' +
    '<circle cx="12" cy="3" r="1.1"/>',

  chart:
    '<rect x="4" y="13" width="4" height="7"/>' +
    '<rect x="10" y="7" width="4" height="13"/>' +
    '<rect x="16" y="10" width="4" height="10"/>',

  tune:
    '<line x1="3" y1="6" x2="21" y2="6" stroke="currentColor" stroke-width="1.6"/>' +
    '<line x1="3" y1="12" x2="21" y2="12" stroke="currentColor" stroke-width="1.6"/>' +
    '<line x1="3" y1="18" x2="21" y2="18" stroke="currentColor" stroke-width="1.6"/>' +
    '<circle cx="9" cy="6" r="2.4"/><circle cx="16" cy="12" r="2.4"/><circle cx="11" cy="18" r="2.4"/>',

  shield: '<path d="M12 2 4 5 4 11 12 21 20 11 20 5Z"/>',

  sun:
    '<circle cx="12" cy="12" r="4.5"/>' +
    '<g stroke="currentColor" stroke-width="1.6" stroke-linecap="round">' +
    '<line x1="12" y1="2" x2="12" y2="4.5"/><line x1="12" y1="19.5" x2="12" y2="22"/>' +
    '<line x1="2" y1="12" x2="4.5" y2="12"/><line x1="19.5" y1="12" x2="22" y2="12"/>' +
    '<line x1="4.9" y1="4.9" x2="6.6" y2="6.6"/><line x1="17.4" y1="17.4" x2="19.1" y2="19.1"/>' +
    '<line x1="4.9" y1="19.1" x2="6.6" y2="17.4"/><line x1="17.4" y1="6.6" x2="19.1" y2="4.9"/>' +
    '</g>',

  cog:
    '<circle cx="12" cy="12" r="6" fill="none" stroke="currentColor" stroke-width="2.2"/>' +
    '<circle cx="12" cy="12" r="2.1"/>' +
    '<g fill="currentColor">' +
    '<rect x="10.9" y="2.2" width="2.2" height="2.9" rx="0.5"/>' +
    '<rect x="10.9" y="2.2" width="2.2" height="2.9" rx="0.5" transform="rotate(45 12 12)"/>' +
    '<rect x="10.9" y="2.2" width="2.2" height="2.9" rx="0.5" transform="rotate(90 12 12)"/>' +
    '<rect x="10.9" y="2.2" width="2.2" height="2.9" rx="0.5" transform="rotate(135 12 12)"/>' +
    '<rect x="10.9" y="2.2" width="2.2" height="2.9" rx="0.5" transform="rotate(180 12 12)"/>' +
    '<rect x="10.9" y="2.2" width="2.2" height="2.9" rx="0.5" transform="rotate(225 12 12)"/>' +
    '<rect x="10.9" y="2.2" width="2.2" height="2.9" rx="0.5" transform="rotate(270 12 12)"/>' +
    '<rect x="10.9" y="2.2" width="2.2" height="2.9" rx="0.5" transform="rotate(315 12 12)"/>' +
    '</g>',

  chevron: '<path d="M9 6l6 6-6 6" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>',

  close: '<path d="M6 6l12 12M18 6 6 18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>',

  // Zusätzliche Icons über die geforderte Mindestmenge hinaus, von app.js
  // für Fehlerkarte und Datenschnitt-Banner genutzt.
  warning:
    '<path d="M12 3 22 20H2Z" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/>' +
    '<rect x="11" y="9" width="2" height="5.5" rx="1"/><rect x="11" y="16" width="2" height="2" rx="1"/>',

  info:
    '<circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" stroke-width="1.8"/>' +
    '<rect x="11" y="10.5" width="2" height="6.5" rx="1"/><rect x="11" y="6.5" width="2" height="2" rx="1"/>',
};

// Neutrales Platzhalter-Symbol für unbekannte Namen — lieber ein stiller
// Kreis als ein falsch gedeutetes Symbol.
const FALLBACK_ICON = '<circle cx="12" cy="12" r="8"/>';

/**
 * Liefert Icon-Markup als SVG-String (viewBox 0 0 24 24, fill="currentColor").
 * Unbekannte Namen liefern einen neutralen Platzhalter statt eine Exception.
 * @param {string} name eines der bekannten Icons (siehe ICON_PATHS)
 * @returns {string} vollständiges <svg>…</svg>-Markup
 */
export function icon(name) {
  const body = (name && ICON_PATHS[name]) || FALLBACK_ICON;
  return `<svg viewBox="0 0 24 24" width="24" height="24" fill="currentColor" aria-hidden="true" focusable="false">${body}</svg>`;
}

// -----------------------------------------------------------------------
// ripple()
// -----------------------------------------------------------------------

/**
 * Hängt eine M3-Zustandsschicht (Hover 8 %, Pressed 12 %, Focus 12 %) und
 * eine Ripple-Welle an ein Element. Hover/Pressed/Focus werden rein über
 * CSS (:hover/:active/:focus-visible auf `.md-ripple-host`, siehe M3_CSS
 * Abschnitt 6) gesteuert; diese Funktion ergänzt nur die dafür nötige
 * Kindstruktur sowie die on-tap-Ripple-Animation, die CSS allein nicht
 * leisten kann (sie muss vom tatsächlichen Zeigerpunkt ausgehen).
 *
 * Idempotent: mehrfacher Aufruf auf demselben Element hängt die Struktur
 * nur einmal an.
 *
 * @param {HTMLElement} el Trägerelement (z. B. Button, Listeneintrag, Tab)
 */
export function ripple(el) {
  if (!el || el.dataset.mdRippleReady) return;
  el.dataset.mdRippleReady = '1';
  el.classList.add('md-ripple-host');

  const layer = document.createElement('span');
  layer.className = 'md-state-layer';
  layer.setAttribute('aria-hidden', 'true');
  el.prepend(layer);

  el.addEventListener('pointerdown', (ev) => {
    // Nur die primäre Taste bzw. Touch/Stift lösen eine Welle aus.
    if (typeof ev.button === 'number' && ev.button !== 0) return;

    const rect = el.getBoundingClientRect();
    const durchmesser = Math.max(rect.width, rect.height) * 2;
    const wave = document.createElement('span');
    wave.className = 'md-ripple-wave';
    wave.style.width = `${durchmesser}px`;
    wave.style.height = `${durchmesser}px`;
    wave.style.left = `${ev.clientX - rect.left - durchmesser / 2}px`;
    wave.style.top = `${ev.clientY - rect.top - durchmesser / 2}px`;
    el.appendChild(wave);

    const entfernen = () => wave.remove();
    wave.addEventListener('animationend', entfernen);
    // Sicherheitsnetz, falls animationend nicht feuert (z. B. bei
    // prefers-reduced-motion, wo die Animation abgeschaltet ist).
    setTimeout(entfernen, 600);
  });
}
