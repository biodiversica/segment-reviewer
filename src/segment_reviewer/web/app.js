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
    multiRow: $('multi-row'), multiPick: $('multi-pick'), multiInput: $('multi-input'),
    navRow: $('nav-row'), btnPrev: $('btn-prev'), btnTrue: $('btn-true'),
    btnFalse: $('btn-false'), btnNext: $('btn-next'),
    falseRow: $('false-row'), falsePrompt: $('false-prompt'),
    falsePick: $('false-pick'), falseInput: $('false-input'),
    btnConfirm: $('btn-confirm'), btnCancel: $('btn-cancel'),
    specType: $('spec-type'), specFmin: $('spec-fmin'), specFmax: $('spec-fmax'),
    specDb: $('spec-db'),
    btnRescan: $('btn-rescan'), btnHelp: $('btn-help'), help: $('help-dialog'),
  };

  const app = {
    bundle: {}, lang: 'en', multi: false, boot: null,
    state: { segment: null, counts: {}, labels: [], annotations: {} },
    busy: false, specToken: 0,
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

  // ── label helpers (mirror of the notebook's) ──────────────────────────────
  function splitLabels(text) {
    const out = [];
    for (const raw of String(text || '').split(',')) {
      const part = raw.trim();
      if (part && !out.includes(part)) out.push(part);
    }
    return out;
  }

  const addLabel = (current, extra) => {
    const labels = splitLabels(current);
    if (!labels.includes(extra)) labels.push(extra);
    return labels.join(', ');
  };

  function fillPicker(select, labels) {
    select.innerHTML = '';
    const head = new Option(t('labels.pick'), '');
    select.add(head);
    for (const label of labels) select.add(new Option(label, label));
    select.value = '';
    select.classList.toggle('hidden', labels.length === 0);
  }

  // ── rendering ─────────────────────────────────────────────────────────────
  function specParams(index) {
    const q = new URLSearchParams({
      index: String(index),
      type: el.specType.value,
      fmin: String(clamp(el.specFmin.value, 0, 96000, 0)),
      fmax: String(clamp(el.specFmax.value, 0, 96000, 0)),
      db: String(clamp(el.specDb.value, -120, -20, -80)),
    });
    return `/api/spectrogram?${q.toString()}`;
  }

  function clamp(value, lo, hi, fallback) {
    const n = Number.parseInt(value, 10);
    if (Number.isNaN(n)) return fallback;
    return Math.min(hi, Math.max(lo, n));
  }

  function loadSpectrogram() {
    const seg = app.state.segment;
    if (!seg) return;
    const token = ++app.specToken;
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
        await api(specParams(seg.index));
      } catch (err) {
        el.error.textContent = t('spec.error', { error: err.message });
      }
    };
    img.src = specParams(seg.index);
  }

  function loadAudio() {
    const seg = app.state.segment;
    if (!seg) { el.player.removeAttribute('src'); el.player.load(); return; }
    el.player.src = `/api/audio?index=${seg.index}&v=${encodeURIComponent(seg.name)}`;
    el.player.load();
  }

  function renderMeta(seg) {
    const unknown = t('meta_row.unknown');
    const bits = [
      `<b>${escapeHtml(seg.label)}</b>`,
      `${t('meta_row.score')}: <b>${seg.score === null ? unknown : seg.score.toFixed(3)}</b>`,
      `${t('meta_row.site')}: <b>${escapeHtml(seg.site || unknown)}</b>`,
      `${t('meta_row.date')}: <b>${escapeHtml(seg.recorded_at || unknown)}</b>`,
    ];
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
      el.ann.innerHTML = app.multi ? `<span class="warn">${t('annotations.multi_without_table')}</span>` : '';
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

  function render({ reloadMedia = true } = {}) {
    const seg = app.state.segment;
    renderCounts();
    fillPicker(el.multiPick, app.state.labels);
    fillPicker(el.falsePick, app.state.labels);
    el.falsePrompt.textContent = app.state.labels.length
      ? t('false_row.prompt_list') : t('false_row.prompt_free');

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
      el.multiRow.classList.add('hidden');
      el.falseRow.classList.add('hidden');
      renderAnnotations(true);
      return;
    }

    el.progress.className = 'progress';
    el.progress.innerHTML = t('progress.segment', { index: seg.index + 1, total: seg.total });
    el.controls.classList.remove('hidden');
    el.specWrap.classList.remove('hidden');
    el.player.classList.remove('hidden');
    el.navRow.classList.remove('hidden');
    el.falseRow.classList.add('hidden');
    el.error.textContent = '';
    renderMeta(seg);
    renderAnnotations(false);

    if (app.multi) {
      // Start from the label the segment already carries; only a second species
      // has to be typed in.
      el.multiInput.value = seg.label;
      el.multiRow.classList.remove('hidden');
    } else {
      el.multiRow.classList.add('hidden');
    }

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

  function currentLabels() {
    if (!app.multi) return null;
    const seg = app.state.segment;
    const labels = splitLabels(el.multiInput.value);
    return labels.length ? labels : (seg ? [seg.label] : null);
  }

  const markTrue = () => run(() => post('/api/verdict', { verdict: 'true', labels: currentLabels() }));

  function openFalseRow() {
    if (!app.state.segment) return;
    el.falseInput.value = '';
    el.falsePick.value = '';
    el.falseRow.classList.remove('hidden');
    el.multiRow.classList.add('hidden');   // one label box on screen at a time
    el.navRow.classList.add('hidden');
    el.falseInput.focus();
  }

  function closeFalseRow() {
    el.falseRow.classList.add('hidden');
    el.navRow.classList.remove('hidden');
    el.multiRow.classList.toggle('hidden', !app.multi);
  }

  function confirmFalse() {
    const labels = splitLabels(el.falseInput.value);
    const final = labels.length ? labels : [t('false_row.unknown')];
    closeFalseRow();
    return run(() => post('/api/verdict', { verdict: 'false', labels: final }));
  }

  async function setLanguage(code, { persist = true } = {}) {
    const data = await api(`/api/i18n/${encodeURIComponent(code)}`);
    app.lang = data.lang;
    app.bundle = data.bundle;
    if (persist) localStorage.setItem('segrev.lang', app.lang);
    el.lang.value = app.lang;
    applyI18n();
    render({ reloadMedia: false });
  }

  // ── wiring ────────────────────────────────────────────────────────────────
  el.btnPrev.addEventListener('click', () => nav(-1));
  el.btnNext.addEventListener('click', () => nav(+1));
  el.btnTrue.addEventListener('click', markTrue);
  el.btnFalse.addEventListener('click', openFalseRow);
  el.btnConfirm.addEventListener('click', confirmFalse);
  el.btnCancel.addEventListener('click', closeFalseRow);
  el.btnRescan.addEventListener('click', () => run(() => post('/api/rescan')));
  el.btnHelp.addEventListener('click', () => el.help.showModal());

  // The drop-down only fills the text box — the text stays editable, so a label
  // outside the list can still be typed.
  el.falsePick.addEventListener('change', () => {
    if (!el.falsePick.value) return;
    el.falseInput.value = app.multi
      ? addLabel(el.falseInput.value, el.falsePick.value)
      : el.falsePick.value;
    el.falsePick.value = '';   // reset so the same entry can be picked again
    el.falseInput.focus();
  });

  el.multiPick.addEventListener('change', () => {
    if (!el.multiPick.value) return;
    el.multiInput.value = addLabel(el.multiInput.value, el.multiPick.value);
    el.multiPick.value = '';
  });

  el.falseInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') { e.preventDefault(); confirmFalse(); }
    if (e.key === 'Escape') { e.preventDefault(); closeFalseRow(); }
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
    const keys = {
      ArrowLeft: () => nav(-1),
      ArrowRight: () => nav(+1),
      t: markTrue, T: markTrue,
      f: openFalseRow, F: openFalseRow,
    };
    if (e.key === ' ') {
      e.preventDefault();
      el.player.paused ? el.player.play().catch(() => {}) : el.player.pause();
      return;
    }
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
