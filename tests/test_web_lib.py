"""The client's pure helpers, run in node.

There is no browser in the suite, so the DOM-free half of the client is exercised
directly. Skipped when node is not installed.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

LIB = Path(__file__).resolve().parents[1] / "src" / "segment_reviewer" / "web" / "lib.js"
node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")


def run(script: str):
    result = subprocess.run(
        ["node", "-e", f"const lib = require({str(LIB)!r});\n{script}"],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


SEG_A = {"index": 0, "name": "a.wav", "relpath": "PONTO_A/BOAALB/a.wav"}
SEG_B = {"index": 0, "name": "b.wav", "relpath": "PONTO_A/PHYLUT/b.wav"}
VIEW = {"type": "mel", "fmin": "0", "fmax": "0", "db": "-80"}


@node
def test_two_clips_at_the_same_index_get_different_media_urls():
    """The regression: a verdict drops a clip and the next takes its index.

    If both requests carry the same URL the browser answers the second from
    cache and the view stays on the clip that was just filed away.
    """
    urls = run(f"""
      const a = {json.dumps(SEG_A)}, b = {json.dumps(SEG_B)}, v = {json.dumps(VIEW)};
      console.log(JSON.stringify({{
        specA: lib.spectrogramUrl(a, v), specB: lib.spectrogramUrl(b, v),
        audioA: lib.audioUrl(a),         audioB: lib.audioUrl(b),
      }}));
    """)
    assert urls["specA"] != urls["specB"]
    assert urls["audioA"] != urls["audioB"]
    # Same index in both: only the clip's identity separates them.
    assert "index=0" in urls["specA"] and "index=0" in urls["specB"]


@node
def test_the_same_clip_and_view_give_a_stable_url():
    """Redrawing must not bust the URL needlessly, or every render refetches."""
    urls = run(f"""
      const a = {json.dumps(SEG_A)}, v = {json.dumps(VIEW)};
      console.log(JSON.stringify([lib.spectrogramUrl(a, v), lib.spectrogramUrl(a, v)]));
    """)
    assert urls[0] == urls[1]


@node
def test_changing_a_spectrogram_setting_changes_the_url():
    urls = run(f"""
      const a = {json.dumps(SEG_A)};
      console.log(JSON.stringify([
        lib.spectrogramUrl(a, {json.dumps(VIEW)}),
        lib.spectrogramUrl(a, {json.dumps({**VIEW, "fmax": "8000"})}),
        lib.spectrogramUrl(a, {json.dumps({**VIEW, "type": "fft"})}),
      ]));
    """)
    assert len(set(urls)) == 3


@node
def test_every_spectrogram_type_survives_the_client():
    urls = run(f"""
      const a = {json.dumps(SEG_A)};
      console.log(JSON.stringify(lib.SPEC_TYPES.map(
        t => lib.spectrogramUrl(a, Object.assign({{}}, {json.dumps(VIEW)}, {{type: t}})))));
    """)
    assert [u.split("type=")[1].split("&")[0] for u in urls] == ["mel", "fft", "log"]


@node
def test_out_of_range_and_junk_settings_fall_back():
    url = run("""
      console.log(JSON.stringify(lib.spectrogramUrl(
        {index: 2, relpath: 'x.wav'},
        {type: 'wavelet', fmin: '-5', fmax: '999999', db: 'abc'})));
    """)
    assert "type=mel" in url and "fmin=0" in url and "fmax=96000" in url and "db=-80" in url


@node
def test_a_clip_without_a_relpath_still_gets_a_key():
    url = run("console.log(JSON.stringify(lib.audioUrl({index: 1, name: 'only-a-name.wav'})));")
    assert "only-a-name.wav" in url


@node
def test_label_helpers():
    out = run("""
      console.log(JSON.stringify({
        split: lib.splitLabels(' b , a ,b '),
        empty: lib.splitLabels(''),
        add: lib.addLabel('BOAALB', 'PHYLUT'),
        dedupe: lib.addLabel('BOAALB, PHYLUT', 'BOAALB'),
      }));
    """)
    assert out == {"split": ["b", "a"], "empty": [], "add": "BOAALB, PHYLUT",
                   "dedupe": "BOAALB, PHYLUT"}
