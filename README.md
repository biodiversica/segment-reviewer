# Segment Reviewer

[Português (Brasil) →](README.pt-BR.md)

A standalone version of **“Step 6 — Review Extracted Segments”** from the
[bioacoustic vector-search notebooks](https://github.com/biodiversica/bioacoustic-ipynbs):
a command-line tool that serves a browser GUI for reviewing the audio clips a
vector search extracted.

Each segment is shown as a spectrogram with its label, similarity score, site and
recording time. Listen to it, then mark it **True** (a genuine match) or **False**
(a false positive, with the correct label). Marked clips are moved into `true/`,
`false/<label>/` or `multi/` inside the segments folder, and optionally recorded
in an annotation table.

The segments folder can be a **local directory** or a **remote one over SSH**, and
the GUI can be served to **another machine** on your LAN or Tailscale network.
The interface is available in **English** and **Português (Brasil)**, switchable
while you work.

---

## Install

### With [uv](https://docs.astral.sh/uv/) (recommended)

Run it without installing anything permanently:

```bash
uvx --from git+https://github.com/biodiversica/segment-reviewer segment-reviewer /path/to/segments
```

Or install it as a tool:

```bash
uv tool install git+https://github.com/biodiversica/segment-reviewer
segment-reviewer /path/to/segments
```

From a clone, for development:

```bash
git clone https://github.com/biodiversica/segment-reviewer
cd segment-reviewer
uv venv
uv pip install -e ".[dev]"
uv run segment-reviewer /path/to/segments
```

### With pip

```bash
python -m venv .venv && source .venv/bin/activate
pip install git+https://github.com/biodiversica/segment-reviewer
segment-reviewer /path/to/segments
```

Python 3.10 or newer. The audio stack (librosa, soundfile) needs `libsndfile`,
which ships with the wheels on Linux, macOS and Windows.

---

## Use

```bash
# A local folder, GUI on this machine
segment-reviewer ~/vector_search_segments

# Portuguese interface, drop-down labels, annotation table
segment-reviewer ~/vector_search_segments \
    --lang pt-BR \
    --labels "BOAALB, PHYLUT, chuva" \
    --annotations

# Segments on a server, reviewed from your laptop
segment-reviewer ssh://user@fieldserver/data/vector_search_segments

# Serve the GUI to the network (LAN, Tailscale, …)
segment-reviewer /data/vector_search_segments --host 0.0.0.0 --port 8765
```

The command prints a summary and the URL to open. With `--host 0.0.0.0` it also
prints the address other machines should use.

### In the browser

| Control | What it does |
| --- | --- |
| **✔ True** | The match is genuine. The clip moves to `true/`. |
| **✘ False** | A false positive. Pick or type the correct label, then **Confirm** — the clip moves to `false/<label>/` and its file name is rewritten to carry the label you confirmed, so a name never keeps the wrong one. |
| **← Prev / Next →** | Browse without making a decision. |
| **Type / Min Hz / Max Hz / dB floor** | Redraw the spectrogram instantly. The audio player is not touched, so a clip keeps playing while you change the view. |
| **Labels** (with `--multi-label`) | Give one segment several labels — two species singing at once. Pre-filled with the segment's own label; the drop-down adds to it instead of replacing it. |
| **⟳** | Re-read the folder, e.g. after extracting more segments. |
| **Language** | Switch the interface between English and Português. |

Keyboard: <kbd>←</kbd> <kbd>→</kbd> to browse, <kbd>T</kbd> / <kbd>F</kbd> for
true/false, <kbd>Space</kbd> to play or pause, <kbd>Enter</kbd> to confirm a
typed label, <kbd>Esc</kbd> to cancel.

### What happens to the files

Given the naming convention Step 5 writes,
`SITE_YYYYMMDD_HHMMSS_START-ENDs_SCORE_LABEL.wav`:

```
segments/
├── PONTO_A/BOAALB/PONTO_A_20240115_053000_12.0-17.0s_0.873_BOAALB.wav   ← waiting
├── true/       PONTO_A_20240115_053000_12.0-17.0s_0.873_BOAALB.wav      ← confirmed
├── false/TURDRU/PONTO_A_20240115_061500_3.5-8.5s_0.712_TURDRU.wav       ← corrected
├── multi/      POCA_20240116_190000_40.0-45.0s_0.655_BOAALB_PHYLUT.wav  ← two labels
├── segment_sources.csv   ← written by Step 5; maps each clip to its recording
└── annotations.csv       ← written here, with --annotations
```

- A segment given **more than one label** goes to `multi/` rather than
  `true/` or `false/`, and carries every label in its name.
- A name collision after renaming gets a `_2`, `_3`, … suffix — a reviewed file
  is never overwritten.
- Clips already inside `true/`, `false/` or `multi/` are excluded from the
  pending list, so a review can be spread over several sessions.

### The annotation table

With `--annotations`, every reviewed segment is appended to a CSV with columns
`site, file, label, start_time, end_time` — *true* segments with their own label,
*false* ones with the corrected label, and one row per label when a segment has
several. `file` is the **original recording** the clip was cut from, and the times
are the clip's position inside it (padding included).

That link comes from `segment_sources.csv`, which Step 5 writes into the segments
folder. Clips extracted before that file existed leave the `file` column empty
until Step 5 is run again; the GUI says so under the buttons when it happens.

Rows are written as each verdict is given, and an existing table is appended to,
so reviews spread over several sessions add up.

---

## Reviewing segments over SSH

Point the tool at a remote folder and it does everything over SFTP — listing,
reading clips, moving them into the verdict folders, writing the annotation
table. Clips are cached locally as they are opened, so scrolling back is instant.

```bash
segment-reviewer ssh://user@fieldserver:22/data/vector_search_segments
segment-reviewer fieldserver:/data/vector_search_segments      # scp-style
segment-reviewer ssh://fieldserver/data/segments --ssh-key ~/.ssh/id_field
```

Host aliases, users, ports and identity files from `~/.ssh/config` are honoured,
and an SSH agent is used when one is running. An unknown host key is refused
unless you pass `--accept-new-host-key`.

Nothing is written outside the segments folder, and no clip is deleted — files
are only moved between subfolders of the folder you named.

---

## Running on a server

The GUI is a normal web page, so the tool can run wherever the audio is and be
used from anywhere:

```bash
segment-reviewer /data/vector_search_segments --host 0.0.0.0 --port 8765 --no-open
```

When you bind a non-loopback address, an **access token** is generated and
embedded in the printed URL; open that URL once and the token is stored in a
cookie. Pass `--token mysecret` to choose it, or `--no-auth` to serve without one.

The token keeps a casual passer-by out of your files; it is not TLS. On an
untrusted network, prefer Tailscale (bind to the Tailscale address, or to
`0.0.0.0` with the machine only reachable over the tailnet) or an SSH tunnel:

```bash
# on the server
segment-reviewer /data/segments --port 8765 --no-open
# on your laptop
ssh -N -L 8765:127.0.0.1:8765 user@server   # then open http://127.0.0.1:8765
```

One reviewer at a time: the pending list and the current position live in the
server, so two browsers pointed at the same instance drive the same session.

---

## Options

```
segment-reviewer SEGMENTS [OPTIONS]

  SEGMENTS                      Local path, or ssh://[user@]host[:port]/path

  -l, --lang TEXT               Interface language at start: en, pt-BR  [default: en]
      --labels TEXT             Drop-down labels, comma-separated. Blank → the labels
                                the pending segments carry
      --multi-label             Allow several labels per segment (files under multi/)
      --annotations             Write the annotation table
      --annotations-path TEXT   Where it lives  [default: <SEGMENTS>/annotations.csv]

      --spec-type [mel|fft]     Initial spectrogram type  [default: mel]
      --fmin INTEGER            Initial minimum frequency, Hz  [default: 0]
      --fmax INTEGER            Initial maximum frequency, Hz; 0 = Nyquist  [default: 0]
      --db-floor INTEGER        Initial dB floor  [default: -80]

      --true-dir TEXT           Folder for accepted segments  [default: per --lang]
      --false-dir TEXT          Folder for rejected segments  [default: per --lang]
      --multi-dir TEXT          Folder for multi-label segments  [default: multi]

      --host TEXT               Address to bind  [default: 127.0.0.1]
  -p, --port INTEGER            Port  [default: 8765]
      --token TEXT              Access token for the GUI
      --no-auth                 Serve without an access token
      --open / --no-open        Open a browser on start  [default: open]

      --ssh-user / --ssh-port / --ssh-key / --ssh-password
      --known-hosts TEXT        Extra known_hosts file to trust
      --accept-new-host-key     Accept an unknown SSH host key
      --cache-dir TEXT          Where remote clips are cached  [default: a temp folder]

      --version                 Show the version and exit
```

### Verdict folder names and language

The English notebook files clips under `true/` and `false/`; the Portuguese one
under `verdadeiro/` and `falso/`. This tool follows whichever you start with
(`--lang`), and **switching the language in the browser does not rename the
folders** — a review split over two sessions stays in one consistent place.
Override the names with `--true-dir` / `--false-dir` / `--multi-dir`.

Folders written under *either* convention are always excluded from the pending
list, so a folder reviewed in English is not handed back for review in Portuguese.

---

## Differences from the notebook

The behaviour, file layout, naming and annotation format are the same. Two things
differ because this is a web page rather than a Colab widget:

- The label, score, site and time are shown as text above the spectrogram rather
  than drawn into the image, so they stay crisp and re-localize instantly.
- Spectrogram settings and the interface language are remembered in the browser
  between sessions.

---

## Development

```bash
uv venv && uv pip install -e ".[dev]"
uv run pytest
```

## License

MIT — see [LICENSE](LICENSE).
