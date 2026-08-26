/* Pure helpers shared by the client — no DOM, no globals of their own.
 *
 * Kept apart from app.js so they can be exercised directly by the test suite,
 * which has no browser to drive.
 */
(function (root) {
  'use strict';

  /** Frequency axes the server can draw; anything else falls back to the first. */
  const SPEC_TYPES = ['mel', 'fft', 'log'];

  /** Split a comma-separated label box into a clean list, keeping the order. */
  function splitLabels(text) {
    const out = [];
    for (const raw of String(text === undefined || text === null ? '' : text).split(',')) {
      const part = raw.trim();
      if (part && !out.includes(part)) out.push(part);
    }
    return out;
  }

  /** Read a number out of an input, clamped, falling back when it is not one. */
  function clampInt(value, lo, hi, fallback) {
    const n = Number.parseInt(value, 10);
    if (Number.isNaN(n)) return fallback;
    return Math.min(hi, Math.max(lo, n));
  }

  /* A segment's position in the pending list is not a stable identity: giving a
   * verdict drops the current clip, so the next one takes the very same index.
   * Keying the media URLs on the clip's path as well keeps two different clips
   * from sharing one URL — otherwise the browser answers the second request
   * with the first clip's image, and the view appears frozen. */
  function mediaKey(segment) {
    return (segment && (segment.relpath || segment.name)) || '';
  }

  /** URL of the spectrogram for *segment*, drawn with the settings in *view*. */
  function spectrogramUrl(segment, view) {
    const query = new URLSearchParams({
      index: String(segment.index),
      type: SPEC_TYPES.includes(view.type) ? view.type : SPEC_TYPES[0],
      fmin: String(clampInt(view.fmin, 0, 96000, 0)),
      fmax: String(clampInt(view.fmax, 0, 96000, 0)),
      db: String(clampInt(view.db, -120, -20, -80)),
      v: mediaKey(segment),
    });
    return `/api/spectrogram?${query.toString()}`;
  }

  /** URL of the audio for *segment*. */
  function audioUrl(segment) {
    const query = new URLSearchParams({
      index: String(segment.index),
      v: mediaKey(segment),
    });
    return `/api/audio?${query.toString()}`;
  }

  /** Toggle a label in a selection; with `single`, it replaces the selection. */
  function toggleLabel(selection, label, single) {
    if (single) return selection.length === 1 && selection[0] === label ? [] : [label];
    return selection.includes(label)
      ? selection.filter((x) => x !== label)
      : selection.concat([label]);
  }

  /* The buttons on screen: the list the reviewer curates, plus any label the
   * current selection uses that is not on it — a clip whose own label has been
   * trimmed away from the list must still show, or its verdict would silently
   * change what it is labelled. */
  function buttonLabels(list, selection) {
    const out = (list || []).slice();
    for (const label of selection || []) if (!out.includes(label)) out.push(label);
    return out;
  }

  const lib = {
    SPEC_TYPES, splitLabels, clampInt, mediaKey,
    spectrogramUrl, audioUrl, toggleLabel, buttonLabels,
  };
  if (typeof module === 'object' && module.exports) module.exports = lib;
  else root.SegRev = lib;
})(typeof globalThis !== 'undefined' ? globalThis : this);
