/* Segment Reviewer — browser client.
 *
 * The server owns the pending list and the files; this file only draws it and
 * sends verdicts back. Spectrogram controls redraw the image alone — the audio
 * element is never touched by them, so a clip keeps playing while the view
 * changes.
 */
(() => {
  'use strict';

  const $ = (id) => document.getElementById(id);
  const el = {
    folder: $('folder'), counts: $('counts'), lang: $('lang-select'),
    progress: $('progress'), meta: $('meta'), controls: $('controls'),
    specWrap: $('spec-wrap'), spec: $('spec'), player: $('player'),
    error: $('error'), ann: $('ann'),
    labelsPanel: $('labels-panel'), labelsTitle: $('labels-title'),
    labelButtons: $('label-buttons'), labelInput: $('label-input'),
    btnAddLabel: $('btn-add-label'), btnManage: $('btn-manage'),
    labelsNote: $('labels-note'),
    navRow: $('nav-row'), btnPrev: $('btn-prev'), btnTrue: $('btn-true'),
    btnFalse: $('btn-false'), btnNext: $('btn-next'),

    specType: $('spec-type'), specFmin: $('spec-fmin'), specFmax: $('spec-fmax'),
    specDb: $('spec-db'),
    btnRescan: $('btn-rescan'), btnHelp: $('btn-help'), help: $('help-dialog'),
  };

  const app = {
    bundle: {}, lang: 'en', multi: true, boot: null,
    state: { segment: null, counts: {}, labels: [], label_store: {}, annotations: {} },
    busy: false, specToken: 0,
    //: labels chosen for the segment on screen
    selection: [],
    //: true while the label list itself is being edited
    managing: false,
  };

  // ── i18n ──────────────────────────────────────────────────────────────────
  const t = (key, vars) => {
    let out = key.split('.').reduce((n, k) => (n && n[k] !== undefined ? n[k] : null), app.bundle);
    if (out === null || typeof out !== 'string') return key;
    if (vars) for (const [k, v] of Object.entries(vars)) out = out.split(`{${k}}`).join(v);
    return out;
  };

  function applyI18n() {
    document.documentElement.lang = app.lang;
    document.title = t('app.title');
    for (const node of document.querySelectorAll('[data-i18n]')) node.innerHTML = t(node.dataset.i18n);
    for (const node of document.querySelectorAll('[data-i18n-title]')) node.title = t(node.dataset.i18nTitle);
    for (const node of document.querySelectorAll('[data-i18n-ph]')) node.placeholder = t(node.dataset.i18nPh);
  }

  // ── HTTP ──────────────────────────────────────────────────────────────────
  async function api(path, options) {
    const res = await fetch(path, {
      headers: { 'Content-Type': 'application/json' },
      credentials: 'same-origin',
      ...options,
    });
    if (res.status === 401) throw new Error(t('errors.unauthorized'));
    if (!res.ok) {
      let detail = res.statusText;
      try { detail = (await res.json()).detail || detail; } catch (_) { /* keep statusText */ }
      throw new Error(detail);
    }
    return res.json();
  }

  const post = (path, body) => api(path, { method: 'POST', body: JSON.stringify(body || {}) });

  // ── label helpers ─────────────────────────────────────────────────────────
  const { splitLabels, spectrogramUrl, audioUrl, toggleLabel, buttonLabels } = window.SegRev;

  // ── the label panel ───────────────────────────────────────────────────────
  function renderLabels() {
    const labels = buttonLabels(app.state.labels, app.selection);
    el.labelsTitle.textContent = t('labels.selected');
    el.labelsPanel.classList.toggle('managing', app.managing);
    el.btnManage.classList.toggle('active', app.managing);
    el.btnManage.title = t(app.managing ? 'labels.manage_on' : 'labels.manage');

    el.labelButtons.innerHTML = '';
    labels.forEach((label, i) => {
      const chip = document.createElement('span');
      chip.className = 'chip' + (app.selection.includes(label) ? ' on' : '');

      const pick = document.createElement('button');
      pick.type = 'button';
      pick.className = 'chip-pick';
      // The first nine get a number, matching the 1…9 keyboard shortcuts.
      pick.innerHTML = (i < 9 ? `<kbd>${i + 1}</kbd>` : '') + escapeHtml(label);
      pick.addEventListener('click', () => pickLabel(label));
      chip.appendChild(pick);

      const drop = document.createElement('button');
      drop.type = 'button';
      drop.className = 'chip-drop';
      drop.textContent = '×';
      drop.title = t('labels.remove', { label });
      drop.addEventListener('click', () => editList({ remove: label }));
      chip.appendChild(drop);

      el.labelButtons.appendChild(chip);
    });
    if (!labels.length) {
      el.labelButtons.innerHTML = `<span class="hint">${t('labels.empty')}</span>`;
    }
    renderLabelsNote();
  }

  function renderLabelsNote() {
    const store = app.state.label_store || {};
    if (store.error) {
      el.labelsNote.innerHTML =
        `<span class="bad">${t('labels.not_saved', { error: escapeHtml(store.error) })}</span>`;
    } else if (!app.managing) {
      el.labelsNote.textContent = '';
    } else if (store.persisted) {
      el.labelsNote.textContent = t('labels.saved_to', { path: store.path });
    } else {
      el.labelsNote.textContent = t('labels.session_only');
    }
  }

  function pickLabel(label) {
    // One label at a time unless multi-label is on.
    app.selection = toggleLabel(app.selection, label, !app.multi);
    renderLabels();
  }

  async function editList(change) {
    try {
      const data = await post('/api/labels', change);
      app.state = data.state;
      renderLabels();
    } catch (err) {
      el.error.textContent = err.message || t('errors.network');
    }
  }

  function addTypedLabel() {
    const typed = splitLabels(el.labelInput.value);
    if (!typed.length) return;
    el.labelInput.value = '';
    // Typing a label both puts it on the list and picks it for this segment,
    // so a new class costs one action rather than two.
    for (const label of typed) {
      if (!app.selection.includes(label)) app.selection.push(label);
    }
    editList({ labels: buttonLabels(app.state.labels, typed) });
  }

  // ── rendering ─────────────────────────────────────────────────────────────
  const specView = () => ({
    type: el.specType.value,
    fmin: el.specFmin.value,
    fmax: el.specFmax.value,
    db: el.specDb.value,
  });

  function loadSpectrogram() {
    const seg = app.state.segment;
    if (!seg) return;
    const token = ++app.specToken;
    const url = spectrogramUrl(seg, specView());
    el.specWrap.classList.add('loading');
    const img = new Image();
    img.onload = () => {
      if (token !== app.specToken) return;   // a newer request already won
      el.spec.src = img.src;
      el.specWrap.classList.remove('loading');
    };
    img.onerror = async () => {
      if (token !== app.specToken) return;
      el.specWrap.classList.remove('loading');
      el.spec.removeAttribute('src');
      // The PNG endpoint answers errors as JSON; ask again to show the reason.
      try {
        await api(url);
      } catch (err) {
        el.error.textContent = t('spec.error', { error: err.message });
      }
    };
    img.src = url;
  }

  function loadAudio() {
    const seg = app.state.segment;
    if (!seg) { el.player.removeAttribute('src'); el.player.load(); return; }
    el.player.src = audioUrl(seg);
    el.player.load();
  }

  function renderMeta(seg) {
    // Only what this segment actually carries: a collection named by another
    // convention simply shows fewer facts rather than a row of question marks.
    const bits = [seg.label
      ? `<b>${escapeHtml(seg.label)}</b>`
      : `<i>${t('meta_row.no_label')}</i>`];
    const add = (key, value) => {
      if (value !== null && value !== undefined && value !== '') {
        bits.push(`${t(`meta_row.${key}`)}: <b>${escapeHtml(value)}</b>`);
      }
    };
    if (seg.score !== null) add('score', seg.score.toFixed(3));
    add('site', seg.site);
    add('date', seg.recorded_at);
    add('folder', seg.folder);
    add('extra', seg.extra);
    el.meta.innerHTML = bits.join(' &nbsp;|&nbsp; ');
  }

  function renderCounts() {
    const c = app.state.counts || {};
    el.counts.textContent = t('progress.counts', {
      pending: c.pending ?? 0, true: c.true ?? 0, false: c.false ?? 0, multi: c.multi ?? 0,
    });
  }

  function renderAnnotations(final) {
    const a = app.state.annotations || {};
    if (a.no_path) {
      el.ann.innerHTML = `<span class="bad">${t('annotations.label')}: ${t('annotations.no_path')}</span>`;
      return;
    }
    if (a.error) {
      el.ann.innerHTML = `<span class="bad">${t('annotations.label')}: ${escapeHtml(a.error)}</span>`;
      return;
    }
    if (!a.enabled) {
      el.ann.textContent = '';
      return;
    }
    let warn = '';
    if (a.read_error) {
      warn = ` — <span class="warn">${t('annotations.read_error', { error: escapeHtml(a.read_error) })}</span>`;
    } else if (a.rows_without_recording) {
      const why = a.have_sources ? t('annotations.why_unlisted') : t('annotations.why_missing');
      warn = ` — <span class="warn">${t('annotations.norec', { count: a.rows_without_recording, why })}</span>`;
    }
    el.ann.innerHTML = `${final ? '✔ ' : ''}${t('annotations.label')}: ${t('annotations.rows', {
      count: `<b>${a.rows}</b>`, path: escapeHtml(a.path),
    })}${warn}`;
  }

  const escapeHtml = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
  ));

  function render({ reloadMedia = true, keepSelection = false } = {}) {
    const seg = app.state.segment;
    renderCounts();

    if (!seg) {
      // Hide the viewer rather than leaving an empty frame in place.
      const done = (app.state.counts.true || app.state.counts.false || app.state.counts.multi);
      el.progress.className = 'progress done';
      el.progress.innerHTML = done ? t('progress.done') : t('progress.empty');
      el.meta.textContent = '';
      el.error.textContent = '';
      el.controls.classList.add('hidden');
      el.specWrap.classList.add('hidden');
      el.player.classList.add('hidden');
      el.player.pause();
      el.navRow.classList.add('hidden');
      el.labelsPanel.classList.add('hidden');
      renderAnnotations(true);
      return;
    }

    el.progress.className = 'progress';
    el.progress.innerHTML = t('progress.segment', { index: seg.index + 1, total: seg.total });
    el.controls.classList.remove('hidden');
    el.specWrap.classList.remove('hidden');
    el.player.classList.remove('hidden');
    el.error.textContent = '';
    renderMeta(seg);
    renderAnnotations(false);

    if (!keepSelection) {
      // Start from the label the segment already carries: accepting it is then
      // a single click, and only a correction or a second species needs more.
      app.selection = seg.label ? [seg.label] : [];
    }
    el.labelsPanel.classList.remove('hidden');
    el.navRow.classList.remove('hidden');
    renderLabels();

    el.btnPrev.disabled = seg.index <= 0;
    el.btnNext.disabled = seg.index >= seg.total - 1;

    loadSpectrogram();
    if (reloadMedia) loadAudio();
  }

  // ── actions ───────────────────────────────────────────────────────────────
  async function run(fn) {
    if (app.busy) return;
    app.busy = true;
    try {
      app.state = await fn();
      render();
    } catch (err) {
      el.error.textContent = err.message || t('errors.network');
    } finally {
      app.busy = false;
    }
  }

  const nav = (delta) => run(() => post('/api/nav', { delta }));

  /** The labels to file the current segment under.

   * The buttons are the whole answer for both verdicts: whatever is selected is
   * what the clip is labelled, and True or False only decides which folder it
   * lands in. Clearing the selection is how a rejection says "not this, and I
   * cannot say what it is".
   */
  function chosenLabels(kind) {
    if (app.selection.length) return app.selection.slice();
    const seg = app.state.segment;
    if (kind === 'false') return [t('labels.unknown')];
    return seg && seg.label ? [seg.label] : [];
  }

  function verdict(kind) {
    if (!app.state.segment) return;
    const labels = chosenLabels(kind);
    return run(() => post('/api/verdict', { verdict: kind, labels }));
  }

  const markTrue = () => verdict('true');
  const markFalse = () => verdict('false');

  async function setLanguage(code, { persist = true } = {}) {
    const data = await api(`/api/i18n/${encodeURIComponent(code)}`);
    app.lang = data.lang;
    app.bundle = data.bundle;
    if (persist) localStorage.setItem('segrev.lang', app.lang);
    el.lang.value = app.lang;
    applyI18n();
    render({ reloadMedia: false, keepSelection: true });
  }

  // ── wiring ────────────────────────────────────────────────────────────────
  el.btnPrev.addEventListener('click', () => nav(-1));
  el.btnNext.addEventListener('click', () => nav(+1));
  el.btnTrue.addEventListener('click', markTrue);
  el.btnFalse.addEventListener('click', markFalse);
  el.btnRescan.addEventListener('click', () => run(() => post('/api/rescan')));
  el.btnHelp.addEventListener('click', () => el.help.showModal());

  el.btnManage.addEventListener('click', () => {
    app.managing = !app.managing;
    renderLabels();
  });
  el.btnAddLabel.addEventListener('click', addTypedLabel);
  el.labelInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') { e.preventDefault(); addTypedLabel(); }
    if (e.key === 'Escape') { e.preventDefault(); el.labelInput.value = ''; el.labelInput.blur(); }
  });

  for (const control of [el.specType, el.specFmin, el.specFmax, el.specDb]) {
    control.addEventListener('change', () => {
      localStorage.setItem('segrev.spec', JSON.stringify({
        type: el.specType.value, fmin: el.specFmin.value,
        fmax: el.specFmax.value, db: el.specDb.value,
      }));
      loadSpectrogram();     // the audio player is deliberately left alone
    });
  }

  el.lang.addEventListener('change', () => setLanguage(el.lang.value));

  document.addEventListener('keydown', (e) => {
    if (e.target.matches('input, select, textarea') || el.help.open) return;
    if (e.metaKey || e.ctrlKey || e.altKey) return;

    if (e.key === ' ') {
      e.preventDefault();
      el.player.paused ? el.player.play().catch(() => {}) : el.player.pause();
      return;
    }
    // 1…9 toggle the first nine labels, which is the whole point of the buttons.
    if (/^[1-9]$/.test(e.key)) {
      const labels = buttonLabels(app.state.labels, app.selection);
      const label = labels[Number(e.key) - 1];
      if (label) { e.preventDefault(); pickLabel(label); }
      return;
    }
    const keys = {
      ArrowLeft: () => nav(-1),
      ArrowRight: () => nav(+1),
      t: markTrue, T: markTrue,
      f: markFalse, F: markFalse,
    };
    const action = keys[e.key];
    if (action) { e.preventDefault(); action(); }
  });

  // ── start ─────────────────────────────────────────────────────────────────
  (async function start() {
    try {
      const boot = await api('/api/bootstrap');
      app.boot = boot;
      app.multi = boot.multi_label;
      app.state = boot.state;

      el.folder.textContent = boot.folder;
      el.folder.title = boot.folder;

      el.lang.innerHTML = '';
      for (const lang of boot.languages) el.lang.add(new Option(lang.name, lang.code));

      const spec = { ...boot.spec_defaults, ...safeParse(localStorage.getItem('segrev.spec')) };
      el.specType.value = spec.type || 'mel';
      el.specFmin.value = spec.fmin ?? 0;
      el.specFmax.value = spec.fmax ?? 0;
      el.specDb.value = spec.db ?? -80;

      await setLanguage(localStorage.getItem('segrev.lang') || boot.lang, { persist: false });
      loadAudio();
    } catch (err) {
      document.body.innerHTML = `<main><div class="error">${escapeHtml(err.message)}</div></main>`;
    }
  })();

  function safeParse(text) {
    try { return text ? JSON.parse(text) : {}; } catch (_) { return {}; }
  }
})();
