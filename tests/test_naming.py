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


def test_label_depth_reads_the_label_from_the_top_folder():
    """A collection filed class-first, with sites inside: BOAALB/PONTO_A/x.wav."""
    info = SegmentParser(label_depth=1).parse(f"{ROOT}/BOAALB/PONTO_A/x.wav", ROOT)
    assert info.label == "BOAALB"
    assert info.prefix == ()
    assert info.suffix == ("PONTO_A",)   # kept, and put back under the new label


def test_label_depth_counts_down_from_the_segments_root():
    info = SegmentParser(label_depth=2).parse(f"{ROOT}/2024/BOAALB/PONTO_A/x.wav", ROOT)
    assert info.label == "BOAALB"
    assert info.prefix == ("2024",)
    assert info.suffix == ("PONTO_A",)


def test_a_clip_shallower_than_the_depth_is_labelled_by_its_own_folder():
    """A mixed tree — some classes with site folders, some without — still labels
    every clip rather than leaving the shallow ones blank."""
    info = SegmentParser(label_depth=2).parse(f"{ROOT}/PHYLUT/x.wav", ROOT)
    assert info.label == "PHYLUT"
    assert info.prefix == () and info.suffix == ()


def test_the_default_depth_is_the_folder_the_clip_sits_in(parser):
    info = parser.parse(f"{ROOT}/PONTO_A/BOAALB/x.wav", ROOT)
    assert (info.label, info.prefix, info.suffix) == ("BOAALB", ("PONTO_A",), ())


def test_a_negative_depth_is_rejected():
    with pytest.raises(ValueError):
        SegmentParser(label_depth=-1)


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


# ── name templates ───────────────────────────────────────────────────────────
def test_a_template_reads_a_name_the_presets_do_not_fit():
    """Label before the score, a T in the stamp, a literal REC in the middle."""
    parser = SegmentParser(
        "[site]_YYYYMMDDTHHMMSS_REC_[start_time]_[end_time]_[label]_[score]",
        label_from="filename",
    )
    info = parser.parse(
        f"{ROOT}/BOAALB/PONTO_A_20240115/PONTO_A_20240115T053000_REC_12.0_17.0_BOAALB_0.873.wav",
        ROOT,
    )
    assert info.label == "BOAALB" and info.label_in_filename
    assert info.site == "PONTO A"
    assert info.recorded_at == datetime(2024, 1, 15, 5, 30)
    assert (info.det_start, info.det_end) == (12.0, 17.0)
    assert info.score == 0.873


def test_a_site_keeps_its_own_underscores_in_a_template():
    info = SegmentParser("[site]_YYYYMMDD_HHMMSS_[extra]").parse(
        f"{ROOT}/x/MATA_DO_MEIO_20240115_053000_det1.wav", ROOT
    )
    assert info.site == "MATA DO MEIO"
    assert info.extra == "det1"


def test_a_star_matches_anything_without_capturing_it():
    info = SegmentParser("[site]_YYYYMMDD_HHMMSS_*_[score]").parse(
        f"{ROOT}/x/POCA_20240116_190000_whatever_here_0.655.wav", ROOT
    )
    assert info.site == "POCA" and info.score == 0.655


def test_a_datetime_placeholder_takes_the_stamp_in_one_piece():
    info = SegmentParser(
        "[site]_[datetime]_[start]_[end]", datetime_format="%Y%m%dT%H%M%S"
    ).parse(f"{ROOT}/x/POCA_20240116T190000_1.0_2.0.wav", ROOT)
    assert info.recorded_at == datetime(2024, 1, 16, 19, 0)


def test_a_template_must_match_the_whole_name():
    """Half-matching would fill the GUI with facts read off the wrong tokens."""
    info = SegmentParser("[site]_YYYYMMDD_HHMMSS").parse(
        f"{ROOT}/x/POCA_20240116_190000_and_more.wav", ROOT
    )
    assert info.site is None and info.recorded_at is None


def test_a_template_rewrites_the_label_it_captured():
    parser = SegmentParser("[site]_YYYYMMDD_HHMMSS_[label]_[score]", label_from="filename")
    assert parser.replace_label("POCA_20240116_190000_BOAALB_0.655.wav", ["TURDRU"]) == (
        "POCA_20240116_190000_TURDRU_0.655.wav"
    )


def test_an_unknown_placeholder_is_rejected():
    with pytest.raises(ValueError, match="unknown placeholder"):
        SegmentParser("[site]_[speceis]")


def test_a_placeholder_used_twice_is_rejected():
    with pytest.raises(ValueError, match="more than once"):
        SegmentParser("[site]_[site]")


def test_a_hand_written_expression_is_never_read_as_a_template():
    parser = SegmentParser(r"^(?P<label>[a-z]+)\[site\]$")
    assert parser.pattern_name == "custom"
    assert parser.parse(f"{ROOT}/x/rain[site].wav", ROOT).label == "x"


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
