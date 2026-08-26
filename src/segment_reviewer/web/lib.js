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

  /** Append a label picked from a drop-down without repeating it. */
  function addLabel(current, extra) {
    const labels = splitLabels(current);
    if (!labels.includes(extra)) labels.push(extra);
    return labels.join(', ');
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

  const lib = { SPEC_TYPES, splitLabels, addLabel, clampInt, mediaKey, spectrogramUrl, audioUrl };
  if (typeof module === 'object' && module.exports) module.exports = lib;
  else root.SegRev = lib;
})(typeof globalThis !== 'undefined' ? globalThis : this);
