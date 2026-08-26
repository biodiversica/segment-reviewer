from typer.testing import CliRunner

from segment_reviewer import __version__
from segment_reviewer.cli import _is_loopback, _pattern_has_label, cli

runner = CliRunner()


def test_version():
    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout


def test_help_lists_the_main_options():
    # A wide terminal, so the help does not truncate the longer flag names.
    result = runner.invoke(cli, ["--help"], env={"COLUMNS": "220"})
    assert result.exit_code == 0
    for flag in ("--lang", "--labels", "--label-from", "--filename-pattern",
                 "--multi-label", "--annotations", "--host", "--token", "--ssh-key"):
        assert flag in result.stdout


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
