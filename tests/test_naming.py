from datetime import datetime

from segment_reviewer.naming import (
    name_with_labels,
    parse,
    slug,
    source_key,
    split_labels,
)


def test_parse_full_name():
    info = parse("PONTO_A_20240115_053000_12.0-17.0s_0.873_BOAALB.wav")
    assert info.label == "BOAALB"
    assert info.score == 0.873
    assert info.site == "PONTO A"
    assert info.recorded_at == datetime(2024, 1, 15, 5, 30, 0)
    assert (info.det_start, info.det_end) == (12.0, 17.0)


def test_parse_site_with_underscores():
    info = parse("MATA_DO_MEIO_20240115_053000_1.0-6.0s_0.500_TURDRU.wav")
    assert info.site == "MATA DO MEIO"
    assert info.label == "TURDRU"


def test_parse_label_with_underscores_becomes_spaces():
    assert parse("S_20240115_053000_1.0-6.0s_0.5_Rufous_Hornero.wav").label == "Rufous Hornero"


def test_parse_unpatterned_name():
    info = parse("just-a-clip.wav")
    assert info.label == "just-a-clip"
    assert info.score is None
    assert info.site is None


def test_name_with_labels_replaces_the_model_label():
    out = name_with_labels("S_20240115_053000_1.0-6.0s_0.873_BOAALB.wav", ["TURDRU"])
    assert out == "S_20240115_053000_1.0-6.0s_0.873_TURDRU.wav"


def test_name_with_labels_appends_every_label():
    out = name_with_labels("S_20240115_053000_1.0-6.0s_0.873_BOAALB.wav", ["BOAALB", "PHYLUT"])
    assert out == "S_20240115_053000_1.0-6.0s_0.873_BOAALB_PHYLUT.wav"


def test_name_with_labels_leaves_unpatterned_names_alone():
    assert name_with_labels("clip.wav", ["X"]) == "clip.wav"


def test_split_labels_dedupes_and_keeps_order():
    assert split_labels(" b , a ,b ") == ["b", "a"]
    assert split_labels("", fallback="BOAALB") == ["BOAALB"]


def test_slug_is_filename_safe():
    assert slug("Rufous Hornero") == "Rufous_Hornero"
    assert slug("a/b") == "a-b"


def test_source_key_matches_across_accent_forms():
    import unicodedata

    composed = "POÇA_20240116_190000_0.0-5.0s_0.5_X.wav"
    decomposed = unicodedata.normalize("NFD", composed)
    assert source_key(composed) == source_key(decomposed)
