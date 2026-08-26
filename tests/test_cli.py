from typer.testing import CliRunner

from segment_reviewer import __version__
from segment_reviewer.cli import _is_loopback, cli

runner = CliRunner()


def test_version():
    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout


def test_help_lists_the_main_options():
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    for flag in ("--lang", "--labels", "--multi-label", "--annotations", "--host",
                 "--token", "--ssh-key"):
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
