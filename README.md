# Segment Reviewer

[Português (Brasil) →](README.pt-BR.md)

A command-line tool that serves a **browser GUI for reviewing a folder of audio
segments**. Each clip is shown as a spectrogram with whatever its folder and file
name say about it; you listen to it and mark it **True** (correct) or **False**
(wrong, with the correct label). Reviewed clips are moved into `true/`, `false/`
or `multi/` inside the segments folder, and optionally recorded in an annotation
table.

It works on any collection of clips, however they were produced — a detector's
output, hand-cut examples, a classifier's predictions to be validated. The
segments folder can be **local** or **remote over SSH**, and the GUI can be
served to **another machine** on your LAN or Tailscale network. The interface is
available in **English** and **Português (Brasil)**.

---

## How a segment is read

Two independent sources, both configurable:

**The folder gives the label.** A reviewed collection is normally organised one
folder per class, so the folder a clip sits in is the label it currently carries:

```
segments/
├── PONTO_A/BOAALB/PONTO_A_20240115_053000_12.0_17.0_det1.wav   → label BOAALB
├── PONTO_A/PHYLUT/PONTO_A_20240115_061500_3.5_8.5_det2.wav     → label PHYLUT
└── chuva/POCA_20240116_200000_5.0_10.0_det4.wav                → label chuva
```

Any folders above the label are kept as they are — `2024/campo/PONTO_A/BOAALB/`
labels the clip `BOAALB` and remembers the three folders above it. A clip sitting
directly in the segments folder simply has no label yet.

**The file name gives the rest.** By default it is read as

```
[site]_[YYYYMMDD]_[HHMMSS]_[start]_[end]_*
     PONTO_A_20240115_053000_12.0_17.0_det1.wav
```

- `site` may contain underscores — the match is anchored on the date and time.
- `start`/`end` are the clip's position, in seconds, inside the recording it was
  cut from. Both separators work: `12.0_17.0` and `12.0-17.0s`.
- `_*` is anything else, shown in the GUI as *extra*.
- Every part after the site is optional, and **a name that matches nothing at all
  is still perfectly reviewable** — the GUI just shows less about it.

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
segment-reviewer ~/segments

# Portuguese interface, extra drop-down labels, annotation table
segment-reviewer ~/segments --lang pt-BR --labels "BOAALB, PHYLUT, chuva" --annotations

# Segments on a server, reviewed from your laptop
segment-reviewer ssh://user@fieldserver/data/segments

# Serve the GUI to the network (LAN, Tailscale, …)
segment-reviewer /data/segments --host 0.0.0.0 --port 8765
```

The command prints a summary and the URL to open. With `--host 0.0.0.0` it also
prints the address other machines should use.

### In the browser

| Control | What it does |
| --- | --- |
| **Label buttons** | One button per label. Click to pick it for this segment; click again to drop it. The segment's own label starts selected, so accepting it is a single click. <kbd>1</kbd>…<kbd>9</kbd> hit the first nine. |
| **✔ True** | The label is correct. The clip keeps its path, under `true/`. |
| **✘ False** | Wrong. Filed under the same selection, in `false/` instead of `true/` — so pick the correct label(s) first, then press it. With nothing selected the clip goes to `false/unknown/`. |
| **← Prev / Next →** | Browse without making a decision. |
| **Type / Min Hz / Max Hz / dB floor** | Redraw the spectrogram instantly — mel, linear-Hz or log-Hz frequency axis. The audio player is not touched, so a clip keeps playing while you change the view. |
| **✎** | Edit the label list itself: each button grows a **×** to drop it, and the box below adds a new one. Changes are saved to `labels.txt` in the segments folder. |
| **⟳** | Re-read the folder, e.g. after more segments arrive. |
| **Language** | Switch the interface between English and Português. |

Both verdicts read the same selection — the buttons say *what* the clip is, and
True or False only says which folder it lands in. Every segment is one pass:
adjust the labels if they need adjusting, press a verdict, and the next clip is
already on screen.

Several labels can be given to one segment — two species singing at once — which
is the default; `--no-multi-label` restricts each segment to one.

Keyboard: <kbd>←</kbd> <kbd>→</kbd> to browse, <kbd>T</kbd> / <kbd>F</kbd> for
true/false, <kbd>1</kbd>…<kbd>9</kbd> to toggle the first nine labels,
<kbd>Space</kbd> to play or pause.

### The label list

The buttons come from a list kept in **`labels.txt`** in the segments folder, one
label per line. The first time a collection is opened the list is seeded from
`--labels` and from the labels the collection already uses, and written out; from
then on that file *is* the list, and you edit it from the GUI (or by hand — blank
lines and `#` comments are ignored).

Nothing is ever added back behind your back: a rescan that finds a new folder
does not push its name onto the list. Trimming the list is safe, too — a clip's
own label always shows as a button whether or not it is on the list, and typing a
name into the box both adds it to the list and picks it for the segment on screen.

Use `--labels-file` to keep the list somewhere else, or `--no-labels-file` to make
edits last only for the session.

### Where a verdict puts a clip

A reviewed clip **keeps the path it had**, with its label folder swapped for the
one you confirmed. Nothing about its place in the collection is lost:

```
PONTO_A/BOAALB/clip.wav
   ├── ✔ True                    →  true/PONTO_A/BOAALB/clip.wav
   ├── ✘ False, corrected TURDRU →  false/PONTO_A/TURDRU/clip.wav
   └── two labels                →  multi/PONTO_A/BOAALB_PHYLUT/clip.wav
```

- File names are **left exactly as they were found** — the label lives in the
  folder, so there is nothing in the name to correct.
- A segment given **more than one label** goes to `multi/` rather than `true/` or
  `false/`, under a folder naming every label.
- A clip with no label folder is filed straight under `true/`, or under
  `false/<label>/` once you name one.
- A name collision gets a `_2`, `_3`, … suffix — a reviewed file is never
  overwritten.
- Clips already inside `true/`, `false/` or `multi/` are excluded from the
  pending list, so a review can be spread over several sessions.

### The annotation table

With `--annotations`, every reviewed segment is appended to a CSV with columns
`site, file, label, start_time, end_time` — *true* segments with their own label,
*false* ones with the corrected label, and one row per label when a segment has
several. The times are the clip's position inside the recording it was cut from,
taken from its name and widened to the clip's real duration (so any padding is
included).

`file` names that source recording. A clip's own name rarely says which recording
it came from, so it is looked up in an optional `segment_sources.csv`
(`segment,recording`) beside the segments; without one the column is left empty
and the GUI says so under the buttons.

Rows are written as each verdict is given, and an existing table is appended to,
so reviews spread over several sessions add up.

---

## Reading other naming conventions

`--filename-pattern` takes a preset or **any regular expression with named
groups**. Recognised groups: `site`, `date`, `time`, `datetime`, `start`, `end`,
`label`, `score`, `extra` — all optional, matched against the file name without
its extension.

```bash
# label first, then site, then a 12-digit timestamp: BOAALB-siteA-202401150530.wav
segment-reviewer ~/segments \
    --filename-pattern '^(?P<label>[A-Z]+)-(?P<site>\w+)-(?P<datetime>\d{12})$' \
    --datetime-format '%Y%m%d%H%M'
```

`--label-from` chooses where the label comes from: `folder` (the default),
`filename` (the pattern's `label` group), or `none`. A pattern that captures a
`label` group switches to `filename` on its own unless you say otherwise.

### The vector-search preset

`--filename-pattern vector-search` reads
`SITE_YYYYMMDD_HHMMSS_START-ENDs_SCORE_LABEL.wav`, the names the bioacoustic
vector-search notebooks write, with the **label and similarity score in the name**:

```bash
segment-reviewer ~/vector_search_segments --filename-pattern vector-search --annotations
```

Because the label lives in the name there, that mode behaves as the notebook
does: clips are filed flat under `true/`, `false/<label>/` and `multi/`, and the
**file name is rewritten** to carry the labels you confirmed — a segment
corrected to `TURDRU` is saved as `..._0.873_TURDRU.wav`, one with two labels as
`..._0.873_BOAALB_PHYLUT.wav` — so a name never keeps the wrong label. The score
is shown next to the label in the GUI.

---

## Reviewing segments over SSH

Point the tool at a remote folder and it does everything over SFTP — listing,
reading clips, moving them into the verdict folders, writing the annotation
table. Clips are cached locally as they are opened, so scrolling back is instant.

```bash
segment-reviewer ssh://user@fieldserver:22/data/segments
segment-reviewer fieldserver:/data/segments          # scp-style
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
segment-reviewer /data/segments --host 0.0.0.0 --port 8765 --no-open
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
      --labels TEXT             Labels to seed the list with, comma-separated. Always
                                folded into a stored list
      --labels-file TEXT        Where the label list is kept, one per line
                                [default: <SEGMENTS>/labels.txt]
      --no-labels-file          Do not read or write it; edits last for this session
      --label-from TEXT         Where a segment's label is read from: folder, filename
                                or none  [default: folder]
      --filename-pattern TEXT   'default', 'vector-search', or a regex with the named
                                groups site, date, time, datetime, start, end, label,
                                score, extra  [default: default]
      --datetime-format TEXT    strptime format for the captured date and time
                                [default: %Y%m%d%H%M%S]
      --no-multi-label          Restrict each segment to one label (multi-label is on
                                by default; such clips go under multi/)
      --annotations             Write the annotation table
      --annotations-path TEXT   Where it lives  [default: <SEGMENTS>/annotations.csv]

      --spec-type [mel|fft|log] Initial frequency axis: mel scale, linear Hz, or
                                logarithmic Hz  [default: mel]
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

Starting in English files clips under `true/` and `false/`; starting in
Portuguese, under `verdadeiro/` and `falso/`. **Switching the language in the
browser does not rename the folders** — a review split over two sessions stays in
one consistent place. Override the names with `--true-dir` / `--false-dir` /
`--multi-dir`.

Folders written under *either* convention are always excluded from the pending
list, so a folder reviewed in English is not handed back for review in Portuguese.

---

## Development

```bash
uv venv && uv pip install -e ".[dev]"
uv run pytest
```

The suite covers the naming rules, the verdict layouts, the HTTP API and a full
review driven over an in-process SFTP server. The client's DOM-free helpers run
under node, and skip themselves when node is not installed.

Before pushing, it is worth one run as CI sees it:

```bash
GITHUB_ACTIONS=true uv run pytest
```

Rich colours Typer's help whenever it believes it is on a terminal, and it always
believes so on GitHub Actions — which changes the rendered output enough to break
a test that passes locally.

## License

MIT — see [LICENSE](LICENSE).
