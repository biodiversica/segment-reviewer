"""``segment-reviewer`` — start the reviewer and serve its GUI to a browser."""

from __future__ import annotations

import ipaddress
import os
import re
import secrets
import socket
import sys
import threading
import webbrowser
from typing import Optional

import typer
import uvicorn

from . import __version__, i18n
from .config import DEFAULT_LABELS_FILE, ReviewConfig
from .naming import DEFAULT_DATETIME_FORMAT, LABEL_SOURCES, PRESETS
from .review import ReviewSession
from .server import create_app
from .spectrogram import SPEC_TYPES
from .storage import open_backend

cli = typer.Typer(
    add_completion=False,
    context_settings={"help_option_names": ["-h", "--help"]},
    help=(
        "Review a folder of audio segments in the browser: listen to each clip, "
        "look at its spectrogram, and mark it true or false.\n\n"
        "By default a segment's label is the folder it sits in, and its file name "
        "is read as [site]_[YYYYMMDD]_[HHMMSS]_[start]_[end]_* — both are "
        "configurable with --label-from and --filename-pattern.\n\n"
        "SEGMENTS may be a local folder or a remote one over SSH:\n"
        "  segment-reviewer /data/segments\n"
        "  segment-reviewer ssh://user@host/data/segments"
    ),
)

LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"segment-reviewer {__version__}")
        raise typer.Exit()


def _pattern_has_label(pattern: str) -> bool:
    """True when the filename pattern captures a ``label`` group."""
    for expr in PRESETS.get(pattern, (pattern,)):
        try:
            if "label" in re.compile(expr).groupindex:
                return True
        except re.error:
            return False
    return False


def _is_loopback(host: str) -> bool:
    if host in LOOPBACK_HOSTS:
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _lan_address() -> str:
    """This machine's address on the network it routes through, for the hint line."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("10.255.255.255", 1))
        return sock.getsockname()[0]
    except OSError:
        return socket.gethostbyname(socket.gethostname())
    finally:
        sock.close()


def _summary(session: ReviewSession, config: ReviewConfig, t) -> str:
    counts = session.counts()
    freq = f"{config.freq_min_hz} – " + (
        "Nyquist" if config.freq_max_hz == 0 else f"{config.freq_max_hz} Hz"
    )
    rows = [
        (t("cli.folder"), session.backend.display),
        (t("cli.pending"), str(counts["pending"])),
        (t("cli.already_true"), str(counts["true"])),
        (t("cli.already_false"), str(counts["false"])),
        (t("cli.already_multi"), str(counts["multi"])),
        (t("cli.label_from"), config.label_from),
        (t("cli.pattern"), config.filename_pattern),
        (t("cli.labels"), ", ".join(session.label_choices()) or t("cli.labels_none")),
        (t("cli.labels_file"),
         session.labels.path if session.labels.persisted else t("cli.off")),
        (t("cli.multi"), t("cli.on") if config.multi_label else t("cli.off")),
        (t("cli.annotations"),
         session.annotations.state.path if session.annotations.enabled else t("cli.off")),
        (t("cli.verdict_dirs"), "  ".join(f"{k}/ → {v}/" for k, v in session.dirs.items())),
        (t("cli.spec_type"), config.spec_type),
        (t("cli.freq_range"), freq),
        (t("cli.db_floor"), f"{config.db_min} dB"),
    ]
    width = max(len(name) for name, _ in rows)
    return "\n".join(f"{name.ljust(width)} : {value}" for name, value in rows)


@cli.command()
def review(
    segments: str = typer.Argument(
        ...,
        metavar="SEGMENTS",
        help="Segments folder: a local path, or ssh://[user@]host[:port]/path.",
    ),
    lang: str = typer.Option(
        "en", "--lang", "-l",
        help=f"Interface language at start: {', '.join(i18n.available())}.",
    ),
    labels: str = typer.Option(
        "", "--labels",
        help="Labels offered in the drop-downs, comma-separated (e.g. 'BOAALB, PHYLUT, rain'). "
             "Left blank, the labels the pending segments already carry are offered instead.",
    ),
    label_from: Optional[str] = typer.Option(
        None, "--label-from",
        help="Where a segment's label is read from: 'folder' (the folder it sits in), "
             "'filename' (captured by --filename-pattern) or 'none'.  [default: folder]",
    ),
    filename_pattern: str = typer.Option(
        "default", "--filename-pattern",
        help="How file names are read: 'default' for "
             "[site]_[YYYYMMDD]_[HHMMSS]_[start]_[end]_*, 'vector-search' for names that "
             "also carry a score and label, or a regular expression with any of the named "
             "groups site, date, time, datetime, start, end, label, score, extra.",
    ),
    datetime_format: str = typer.Option(
        DEFAULT_DATETIME_FORMAT, "--datetime-format",
        help="strptime format for the date and time captured from a file name.",
    ),
    multi_label: bool = typer.Option(
        True, "--multi-label/--no-multi-label",
        help="Allow several labels per segment; such clips are filed under multi/. "
             "On by default; --no-multi-label restricts each segment to one label.",
    ),
    labels_file: Optional[str] = typer.Option(
        None, "--labels-file",
        help="Where the editable label list is kept, one label per line. Relative "
             "paths are inside the segments folder.  [default: <SEGMENTS>/labels.txt]",
    ),
    no_labels_file: bool = typer.Option(
        False, "--no-labels-file",
        help="Do not read or write a label list file; edits last for this session only.",
    ),
    annotations: bool = typer.Option(
        False, "--annotations/--no-annotations",
        help="Write one row per reviewed label to a CSV table.",
    ),
    annotations_path: str = typer.Option(
        "", "--annotations-path",
        help="Where that table lives. Relative paths are inside the segments folder. "
             "[default: <segments>/annotations.csv]",
    ),
    spec_type: str = typer.Option(
        "mel", "--spec-type",
        help="Initial spectrogram type: 'mel' (mel scale), 'fft' (linear Hz) or "
             "'log' (logarithmic Hz).",
    ),
    fmin: int = typer.Option(0, "--fmin", min=0, max=96000, help="Initial minimum frequency, in Hz."),
    fmax: int = typer.Option(0, "--fmax", min=0, max=96000, help="Initial maximum frequency in Hz; 0 = Nyquist."),
    db_floor: int = typer.Option(-80, "--db-floor", min=-120, max=-20, help="Initial dB floor of the colour scale."),
    true_dir: str = typer.Option("", "--true-dir", help="Folder name for accepted segments. [default: per --lang]"),
    false_dir: str = typer.Option("", "--false-dir", help="Folder name for rejected segments. [default: per --lang]"),
    multi_dir: str = typer.Option("", "--multi-dir", help="Folder name for multi-label segments. [default: multi]"),
    host: str = typer.Option(
        "127.0.0.1", "--host",
        help="Address to bind. Use 0.0.0.0 to reach the GUI from another machine.",
    ),
    port: int = typer.Option(8765, "--port", "-p", min=1, max=65535, help="Port to listen on."),
    token: Optional[str] = typer.Option(
        None, "--token",
        help="Access token required by the GUI. One is generated when binding a "
             "non-loopback address; use --no-auth to serve without it.",
    ),
    no_auth: bool = typer.Option(False, "--no-auth", help="Serve without an access token."),
    open_browser: bool = typer.Option(
        True, "--open/--no-open", help="Open the GUI in a browser on start."
    ),
    ssh_user: Optional[str] = typer.Option(None, "--ssh-user", help="SSH user, when not in the URL."),
    ssh_port: Optional[int] = typer.Option(None, "--ssh-port", help="SSH port, when not in the URL."),
    ssh_key: Optional[str] = typer.Option(None, "--ssh-key", help="Private key file for the SSH connection."),
    ssh_password: Optional[str] = typer.Option(
        None, "--ssh-password",
        envvar="SEGMENT_REVIEWER_SSH_PASSWORD",
        help="SSH password. Prefer keys or an agent; reads $SEGMENT_REVIEWER_SSH_PASSWORD.",
    ),
    known_hosts: Optional[str] = typer.Option(
        None, "--known-hosts", help="Extra known_hosts file to trust."
    ),
    accept_new_host_key: bool = typer.Option(
        False, "--accept-new-host-key",
        help="Accept an unknown SSH host key instead of refusing to connect.",
    ),
    cache_dir: Optional[str] = typer.Option(
        None, "--cache-dir", help="Where remote clips are cached locally. [default: a temp folder]"
    ),
    _version: bool = typer.Option(
        None, "--version", callback=_version_callback, is_eager=True,
        help="Show the version and exit.",
    ),
) -> None:
    """Open SEGMENTS in the browser reviewer."""
    if spec_type not in SPEC_TYPES:
        raise typer.BadParameter(
            f"must be one of {', '.join(SPEC_TYPES)}", param_hint="--spec-type"
        )
    if label_from is not None and label_from not in LABEL_SOURCES:
        raise typer.BadParameter(
            f"must be one of {', '.join(LABEL_SOURCES)}", param_hint="--label-from"
        )
    if filename_pattern not in PRESETS:
        try:
            re.compile(filename_pattern)
        except re.error as exc:
            raise typer.BadParameter(f"not a valid regular expression: {exc}",
                                     param_hint="--filename-pattern") from exc
    # A pattern that puts the label in the file name implies reading it from
    # there, unless --label-from says otherwise.
    if label_from is None:
        label_from = "filename" if _pattern_has_label(filename_pattern) else "folder"
    language = i18n.normalize(lang)
    if language != lang:
        typer.secho(
            f"Unknown language {lang!r}; using {language!r}. "
            f"Available: {', '.join(i18n.available())}",
            fg=typer.colors.YELLOW, err=True,
        )
    t = i18n.Translator(language)

    config = ReviewConfig(
        segments=segments,
        lang=language,
        labels=[x.strip() for x in labels.split(",") if x.strip()],
        labels_file="" if no_labels_file else (labels_file or DEFAULT_LABELS_FILE),
        persist_labels=not no_labels_file,
        label_from=label_from,
        filename_pattern=filename_pattern,
        datetime_format=datetime_format,
        multi_label=multi_label,
        save_annotations=annotations,
        annotations_path=annotations_path,
        spec_type=spec_type,
        freq_min_hz=fmin,
        freq_max_hz=fmax,
        db_min=db_floor,
        true_dir=true_dir,
        false_dir=false_dir,
        multi_dir=multi_dir,
    )

    try:
        backend = open_backend(
            segments,
            ssh_user=ssh_user,
            ssh_port=ssh_port,
            ssh_key=ssh_key,
            ssh_password=ssh_password,
            known_hosts=known_hosts,
            accept_new_host_key=accept_new_host_key,
            cache_dir=cache_dir,
        )
    except Exception as exc:  # noqa: BLE001 - a connection or path problem, not a bug
        typer.secho(f"Could not open {segments!r}: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2) from exc

    if not backend.isdir(backend.root):
        typer.secho(f"Not a folder: {backend.display}", fg=typer.colors.RED, err=True)
        backend.close()
        raise typer.Exit(code=2)

    session = ReviewSession(backend, config)

    access_token: Optional[str] = None
    if not no_auth:
        access_token = token or (None if _is_loopback(host) else secrets.token_urlsafe(16))

    app = create_app(session, config, access_token)

    shown_host = "127.0.0.1" if host in ("0.0.0.0", "::") else host
    suffix = f"?token={access_token}" if access_token else ""
    url = f"http://{shown_host}:{port}/{suffix}"

    typer.echo(_summary(session, config, t))
    typer.echo("")
    typer.secho(f'{t("cli.serving")}  {url}', fg=typer.colors.GREEN, bold=True)
    if host in ("0.0.0.0", "::"):
        typer.echo(f"  http://{_lan_address()}:{port}/{suffix}")
        typer.echo(f"  {t('cli.network_hint')}")
    if access_token:
        typer.echo(f"  {t('cli.token_hint')}")
    typer.echo(f"  {t('cli.stop_hint')}")

    if open_browser and not os.environ.get("SEGMENT_REVIEWER_NO_BROWSER"):
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()

    try:
        uvicorn.run(app, host=host, port=port, log_level="warning", access_log=False)
    finally:
        backend.close()


def main() -> None:
    try:
        cli()
    except KeyboardInterrupt:  # pragma: no cover - user pressed Ctrl+C
        sys.exit(130)


if __name__ == "__main__":
    main()
