from datetime import datetime

import pytest

from segment_reviewer.naming import (
    SegmentParser,
    slug,
    source_key,
    split_labels,
)

ROOT = "/seg"


@pytest.fixture
def parser():
    return SegmentParser()          # the defaults: label from the folder


# ── the default file-name pattern ────────────────────────────────────────────
def test_default_pattern_reads_site_time_and_window(parser):
    info = parser.parse(f"{ROOT}/PONTO_A/BOAALB/PONTO_A_20240115_053000_12.0_17.0_det1.wav", ROOT)
    assert info.site == "PONTO A"
    assert info.recorded_at == datetime(2024, 1, 15, 5, 30)
    assert (info.det_start, info.det_end) == (12.0, 17.0)
    assert info.extra == "det1"


def test_default_pattern_accepts_the_dash_form_too(parser):
    info = parser.parse(f"{ROOT}/x/S_20240115_053000_12.0-17.0s_more.wav", ROOT)
    assert (info.det_start, info.det_end) == (12.0, 17.0)
    assert info.extra == "more"


def test_start_and_end_are_optional(parser):
    info = parser.parse(f"{ROOT}/x/MATA_DO_MEIO_20240115_053000.wav", ROOT)
    assert info.site == "MATA DO MEIO"
    assert info.recorded_at == datetime(2024, 1, 15, 5, 30)
    assert info.det_start is None and info.det_end is None


def test_a_name_that_matches_nothing_is_still_readable(parser):
    info = parser.parse(f"{ROOT}/rain/whatever.wav", ROOT)
    assert info.label == "rain"          # the folder still names it
    assert info.site is None and info.recorded_at is None


def test_no_score_or_label_is_taken_from_the_name_by_default(parser):
    info = parser.parse(f"{ROOT}/A/B/S_20240115_053000_1.0_2.0_0.873_BOAALB.wav", ROOT)
    assert info.score is None
    assert info.label == "B"             # the folder, not the name
    assert info.label_in_filename is False


# ── where the label comes from ───────────────────────────────────────────────
def test_label_is_the_folder_the_clip_sits_in(parser):
    info = parser.parse(f"{ROOT}/PONTO_A/BOAALB/x_20240115_053000.wav", ROOT)
    assert info.label == "BOAALB"
    assert info.prefix == ("PONTO_A",)   # the folders above the label


def test_a_clip_directly_in_the_root_has_no_label(parser):
    info = parser.parse(f"{ROOT}/x_20240115_053000.wav", ROOT)
    assert info.label == ""
    assert info.prefix == ()


def test_deeply_nested_clip_keeps_every_folder_above_its_label(parser):
    info = parser.parse(f"{ROOT}/2024/campo/PONTO_A/BOAALB/x.wav", ROOT)
    assert info.label == "BOAALB"
    assert info.prefix == ("2024", "campo", "PONTO_A")


def test_label_from_none_ignores_the_folders():
    info = SegmentParser(label_from="none").parse(f"{ROOT}/PONTO_A/BOAALB/x.wav", ROOT)
    assert info.label == ""
    assert info.prefix == ("PONTO_A", "BOAALB")


def test_unknown_label_source_is_rejected():
    with pytest.raises(ValueError):
        SegmentParser(label_from="telepathy")


# ── the vector-search preset ─────────────────────────────────────────────────
@pytest.fixture
def vs():
    return SegmentParser("vector-search", label_from="filename")


def test_vector_search_preset_reads_the_score_and_label(vs):
    info = vs.parse(f"{ROOT}/PONTO_A/BOAALB/PONTO_A_20240115_053000_12.0-17.0s_0.873_BOAALB.wav", ROOT)
    assert (info.label, info.score, info.site) == ("BOAALB", 0.873, "PONTO A")
    assert (info.det_start, info.det_end) == (12.0, 17.0)
    assert info.label_in_filename is True


def test_vector_search_preset_reads_a_name_without_the_site_prefix(vs):
    info = vs.parse(f"{ROOT}/anything_0.5_TURDRU.wav", ROOT)
    assert (info.label, info.score) == ("TURDRU", 0.5)
    assert info.site is None


def test_underscores_in_a_captured_label_become_spaces(vs):
    info = vs.parse(f"{ROOT}/S_20240115_053000_1.0-6.0s_0.5_Rufous_Hornero.wav", ROOT)
    assert info.label == "Rufous Hornero"


# ── custom patterns ──────────────────────────────────────────────────────────
def test_a_custom_pattern_with_named_groups():
    parser = SegmentParser(
        pattern=r"^(?P<label>[A-Z]+)-(?P<site>\w+)-(?P<datetime>\d{12})$",
        label_from="filename",
        datetime_format="%Y%m%d%H%M",
    )
    info = parser.parse(f"{ROOT}/BOAALB-siteA-202401150530.wav", ROOT)
    assert info.label == "BOAALB"
    assert info.site == "siteA"
    assert info.recorded_at == datetime(2024, 1, 15, 5, 30)


def test_a_datetime_that_does_not_fit_the_format_is_dropped_not_fatal():
    parser = SegmentParser(datetime_format="%d%m%Y%H%M%S")
    info = parser.parse(f"{ROOT}/x/S_99999999_999999_1.0_2.0.wav", ROOT)
    assert info.recorded_at is None
    assert (info.det_start, info.det_end) == (1.0, 2.0)


# ── rewriting names ──────────────────────────────────────────────────────────
def test_replace_label_rewrites_a_name_that_carries_one(vs):
    out = vs.replace_label("S_20240115_053000_1.0-6.0s_0.873_BOAALB.wav", ["TURDRU"])
    assert out == "S_20240115_053000_1.0-6.0s_0.873_TURDRU.wav"


def test_replace_label_appends_every_label(vs):
    out = vs.replace_label("S_20240115_053000_1.0-6.0s_0.873_BOAALB.wav", ["BOAALB", "PHYLUT"])
    assert out == "S_20240115_053000_1.0-6.0s_0.873_BOAALB_PHYLUT.wav"


def test_replace_label_leaves_a_folder_labelled_name_alone(parser):
    name = "PONTO_A_20240115_053000_12.0_17.0_det1.wav"
    assert parser.replace_label(name, ["TURDRU"]) == name


def test_replace_label_with_no_labels_changes_nothing(vs):
    name = "S_20240115_053000_1.0-6.0s_0.873_BOAALB.wav"
    assert vs.replace_label(name, []) == name


# ── small helpers ────────────────────────────────────────────────────────────
def test_split_labels_dedupes_and_keeps_order():
    assert split_labels(" b , a ,b ") == ["b", "a"]
    assert split_labels("", fallback="BOAALB") == ["BOAALB"]


def test_slug_is_filename_safe():
    assert slug("Rufous Hornero") == "Rufous_Hornero"
    assert slug("a/b") == "a-b"


def test_source_key_matches_across_accent_forms():
    import unicodedata

    composed = "POÇA_20240116_190000_0.0_5.0.wav"
    assert source_key(composed) == source_key(unicodedata.normalize("NFD", composed))
