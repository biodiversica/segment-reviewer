import re

from typer.main import get_command
from typer.testing import CliRunner

from segment_reviewer import __version__
from segment_reviewer.cli import _is_loopback, _pattern_has_label, cli

runner = CliRunner()

_ANSI = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")


def plain(text: str) -> str:
    """Rendered output with its colour codes removed.

    Typer draws its help through rich, which colours the output whenever it
    thinks it is on a terminal — on GitHub Actions it always does. That splits a
    switch like ``--lang`` across escape sequences, so raw text is not something
    to assert against.
    """
    return _ANSI.sub("", text)


def declared_options() -> set[str]:
    """Every switch the command actually accepts, whatever the help looks like."""
    names: set[str] = set()
    for param in get_command(cli).params:
        names.update(param.opts)
        names.update(param.secondary_opts)
    return names


def test_version():
    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert __version__ in plain(result.stdout)


def test_help_renders():
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "Usage" in plain(result.stdout)
    assert "SEGMENTS" in plain(result.stdout)


def test_the_documented_options_are_all_accepted():
    """Checked against the command, not its rendering, which rich reflows and
    truncates depending on the terminal it believes it is writing to."""
    names = declared_options()
    for flag in ("--lang", "--labels", "--label-from", "--label-depth",
                 "--filename-pattern",
                 "--datetime-format", "--multi-label", "--no-multi-label",
                 "--labels-file", "--no-labels-file", "--annotations",
                 "--annotations-path", "--spec-type", "--fmin", "--fmax",
                 "--db-floor", "--true-dir", "--false-dir", "--multi-dir",
                 "--host", "--port", "--token", "--no-auth", "--open", "--no-open",
                 "--ssh-user", "--ssh-port", "--ssh-key", "--ssh-password",
                 "--known-hosts", "--accept-new-host-key", "--cache-dir",
                 "--version"):
        assert flag in names, flag


def test_missing_folder_exits_with_an_error(tmp_path):
    result = runner.invoke(cli, [str(tmp_path / "nope")])
    assert result.exit_code == 2


def test_bad_spec_type_is_rejected(tmp_path):
    result = runner.invoke(cli, [str(tmp_path), "--spec-type", "wavelet"])
    assert result.exit_code != 0


def test_loopback_detection():
    assert _is_loopback("127.0.0.1") and _is_loopback("localhost") and _is_loopback("::1")
    assert not _is_loopback("0.0.0.0") and not _is_loopback("100.64.0.5")


def test_bad_label_source_is_rejected(tmp_path):
    result = runner.invoke(cli, [str(tmp_path), "--label-from", "telepathy"])
    assert result.exit_code != 0


def test_bad_filename_pattern_is_rejected(tmp_path):
    result = runner.invoke(cli, [str(tmp_path), "--filename-pattern", "(unclosed"])
    assert result.exit_code != 0


def test_pattern_presets_say_whether_they_carry_a_label():
    # The default pattern reads no label, so the folder is used; the
    # vector-search preset does, so --label-from defaults to the file name.
    assert _pattern_has_label("default") is False
    assert _pattern_has_label("vector-search") is True
    assert _pattern_has_label(r"^(?P<label>\w+)_(?P<site>\w+)$") is True
    assert _pattern_has_label(r"^(?P<site>\w+)$") is False


def test_every_spectrogram_type_is_accepted(tmp_path):
    for spec_type in ("mel", "fft", "log"):
        result = runner.invoke(cli, [str(tmp_path / "nope"), "--spec-type", spec_type])
        # It gets past validation and fails on the missing folder instead.
        assert result.exit_code == 2, spec_type
