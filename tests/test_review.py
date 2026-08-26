import csv

from conftest import goto_name, make_session, write_wav


def test_collect_skips_verdict_folders(segments_dir):
    write_wav(segments_dir / "true" / "already_0.9_X.wav")
    write_wav(segments_dir / "verdadeiro" / "also_0.9_X.wav")
    session = make_session(segments_dir)
    assert len(session.segments) == 3
    assert all("/true/" not in p and "/verdadeiro/" not in p for p in session.segments)


def test_counts(session):
    counts = session.counts()
    assert counts["pending"] == 3
    assert counts["true"] == counts["false"] == 0


def test_label_choices_come_from_pending_segments(session):
    assert session.label_choices() == ["BOAALB", "PHYLUT"]


def test_label_choices_put_configured_labels_first(segments_dir):
    session = make_session(segments_dir, labels=["rain", "BOAALB"])
    assert session.label_choices() == ["rain", "BOAALB", "PHYLUT"]


def test_true_moves_into_true_folder(session, segments_dir):
    view = session.view()
    session.apply_verdict("true")
    moved = segments_dir / "true" / view.name
    assert moved.exists()
    assert len(session.segments) == 2


def test_false_files_under_the_corrected_label(session, segments_dir):
    goto_name(session, "PONTO_A_20240115_053000")
    session.apply_verdict("false", ["TURDRU"])
    out = segments_dir / "false" / "TURDRU"
    names = [p.name for p in out.glob("*.wav")]
    assert names == ["PONTO_A_20240115_053000_12.0-17.0s_0.873_TURDRU.wav"]


def test_multiple_labels_go_to_multi_with_every_label_in_the_name(segments_dir):
    session = make_session(segments_dir, multi_label=True)
    goto_name(session, "PONTO_A_20240115_053000")
    session.apply_verdict("true", ["BOAALB", "PHYLUT"])
    names = [p.name for p in (segments_dir / "multi").glob("*.wav")]
    assert names == ["PONTO_A_20240115_053000_12.0-17.0s_0.873_BOAALB_PHYLUT.wav"]


def test_a_collision_gets_a_suffix_instead_of_overwriting(segments_dir):
    # A file already reviewed under the name this verdict would produce.
    write_wav(segments_dir / "false" / "TURDRU"
              / "PONTO_A_20240115_053000_12.0-17.0s_0.873_TURDRU.wav")
    session = make_session(segments_dir)
    goto_name(session, "PONTO_A_20240115_053000")
    session.apply_verdict("false", ["TURDRU"])
    names = sorted(p.name for p in (segments_dir / "false" / "TURDRU").glob("*.wav"))
    assert names == [
        "PONTO_A_20240115_053000_12.0-17.0s_0.873_TURDRU.wav",
        "PONTO_A_20240115_053000_12.0-17.0s_0.873_TURDRU_2.wav",
    ]


def test_portuguese_session_uses_portuguese_folders(segments_dir):
    session = make_session(segments_dir, lang="pt-BR")
    session.apply_verdict("true")
    assert list((segments_dir / "verdadeiro").glob("*.wav"))
    assert not (segments_dir / "true").exists() or not list((segments_dir / "true").glob("*.wav"))


def test_custom_verdict_folders(segments_dir):
    session = make_session(segments_dir, true_dir="yes", false_dir="no")
    session.apply_verdict("true")
    assert list((segments_dir / "yes").glob("*.wav"))


def test_navigation_stays_in_range(session):
    session.navigate(-5)
    assert session.index == 0
    session.navigate(+99)
    assert session.index == len(session.segments) - 1


def test_rescan_keeps_the_current_segment(session, segments_dir):
    session.navigate(+1)
    current = session.view().name
    write_wav(segments_dir / "NEW" / "AAA_20240101_000000_0.0-5.0s_0.5_X.wav")
    session.rescan()
    assert session.view().name == current
    assert len(session.segments) == 4


def test_annotations_record_one_row_per_label(segments_dir):
    session = make_session(segments_dir, multi_label=True, save_annotations=True)
    goto_name(session, "PONTO_A_20240115_053000")
    session.apply_verdict("true", ["BOAALB", "PHYLUT"])
    rows = list(csv.DictReader((segments_dir / "annotations.csv").open()))
    assert [r["label"] for r in rows] == ["BOAALB", "PHYLUT"]
    assert {r["site"] for r in rows} == {"PONTO A"}
    # The manifest written by Step 5 names the recording this clip came from.
    assert {r["file"] for r in rows} == {"PONTO_A_20240115_053000.wav"}
    # A 5 s detection window padded out to a 0.5 s clip: the clip is centred on it.
    assert float(rows[0]["end_time"]) - float(rows[0]["start_time"]) == 0.5


def test_annotations_append_across_verdicts(segments_dir):
    session = make_session(segments_dir, save_annotations=True)
    goto_name(session, "PONTO_A_20240115_053000")
    session.apply_verdict("true")
    goto_name(session, "POCA_20240116_190000")
    session.apply_verdict("false", ["TURDRU"])
    rows = list(csv.DictReader((segments_dir / "annotations.csv").open()))
    assert [r["label"] for r in rows] == ["BOAALB", "TURDRU"]
    # Only the first clip is in the manifest, so the second row has no recording.
    assert rows[1]["file"] == ""
    assert session.annotations.state.rows_without_recording == 1


def test_annotations_disabled_without_a_path_is_reported(segments_dir):
    session = make_session(segments_dir, save_annotations=True, annotations_path="  ")
    # A blank path falls back to annotations.csv inside the segments folder.
    assert session.annotations.enabled
    assert session.annotations.state.path.endswith("annotations.csv")
