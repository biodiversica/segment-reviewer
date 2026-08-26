import csv

from conftest import goto_name, make_session, write_wav

FIRST = "PONTO_A/BOAALB/PONTO_A_20240115_053000_12.0_17.0_det1.wav"


def test_collect_skips_verdict_folders(segments_dir):
    write_wav(segments_dir / "true" / "S_20240101_000000_0.0_5.0.wav")
    write_wav(segments_dir / "verdadeiro" / "S_20240101_000000_0.0_5.0.wav")
    session = make_session(segments_dir)
    assert len(session.segments) == 3
    assert all("/true/" not in p and "/verdadeiro/" not in p for p in session.segments)


def test_counts(session):
    assert session.counts() == {"pending": 3, "true": 0, "false": 0, "multi": 0}


def test_the_view_reports_what_the_folder_and_name_say(session):
    goto_name(session, FIRST)
    view = session.view()
    assert view.label == "BOAALB"
    assert view.label_from == "folder"
    assert view.folder == "PONTO_A/BOAALB"
    assert view.site == "PONTO A"
    assert view.recorded_at == "2024-01-15 05:30:00"
    assert (view.det_start, view.det_end) == (12.0, 17.0)
    assert view.score is None


# ── labels offered ───────────────────────────────────────────────────────────
def test_label_choices_are_the_folder_names(session):
    assert session.label_choices() == ["BOAALB", "PHYLUT"]


def test_label_choices_put_configured_labels_first(segments_dir):
    session = make_session(segments_dir, labels=["rain", "BOAALB"])
    assert session.label_choices() == ["rain", "BOAALB", "PHYLUT"]


# ── where a verdict files a clip ─────────────────────────────────────────────
def test_true_keeps_the_clip_where_it_was_under_true(session, segments_dir):
    goto_name(session, FIRST)
    session.apply_verdict("true")
    assert (segments_dir / "true" / FIRST).exists()
    assert len(session.segments) == 2


def test_false_swaps_the_label_folder_and_keeps_the_rest_of_the_path(session, segments_dir):
    goto_name(session, FIRST)
    session.apply_verdict("false", ["TURDRU"])
    moved = segments_dir / "false" / "PONTO_A" / "TURDRU"
    # The file name is untouched: the label lives in the folder, not the name.
    assert [p.name for p in moved.glob("*.wav")] == [
        "PONTO_A_20240115_053000_12.0_17.0_det1.wav"
    ]


def test_several_labels_go_to_multi_under_a_joined_folder(segments_dir):
    session = make_session(segments_dir, multi_label=True)
    goto_name(session, FIRST)
    session.apply_verdict("true", ["BOAALB", "PHYLUT"])
    moved = segments_dir / "multi" / "PONTO_A" / "BOAALB_PHYLUT"
    assert [p.name for p in moved.glob("*.wav")] == [
        "PONTO_A_20240115_053000_12.0_17.0_det1.wav"
    ]


def test_a_clip_in_the_root_has_no_label_folder_to_keep(segments_dir):
    write_wav(segments_dir / "LOOSE_20240101_000000_0.0_5.0.wav")
    session = make_session(segments_dir)
    goto_name(session, "LOOSE_")
    session.apply_verdict("true")
    assert (segments_dir / "true" / "LOOSE_20240101_000000_0.0_5.0.wav").exists()


def test_a_root_clip_marked_false_is_filed_under_the_label_given(segments_dir):
    write_wav(segments_dir / "LOOSE_20240101_000000_0.0_5.0.wav")
    session = make_session(segments_dir)
    goto_name(session, "LOOSE_")
    session.apply_verdict("false", ["rain"])
    assert (segments_dir / "false" / "rain" / "LOOSE_20240101_000000_0.0_5.0.wav").exists()


def test_label_from_none_keeps_the_whole_path(segments_dir):
    session = make_session(segments_dir, label_from="none")
    goto_name(session, FIRST)
    assert session.view().label == ""
    session.apply_verdict("true")
    assert (segments_dir / "true" / FIRST).exists()


def test_a_collision_gets_a_suffix_instead_of_overwriting(segments_dir):
    write_wav(segments_dir / "false" / "PONTO_A" / "TURDRU"
              / "PONTO_A_20240115_053000_12.0_17.0_det1.wav")
    session = make_session(segments_dir)
    goto_name(session, FIRST)
    session.apply_verdict("false", ["TURDRU"])
    names = sorted(p.name for p in (segments_dir / "false" / "PONTO_A" / "TURDRU").glob("*.wav"))
    assert names == [
        "PONTO_A_20240115_053000_12.0_17.0_det1.wav",
        "PONTO_A_20240115_053000_12.0_17.0_det1_2.wav",
    ]


# ── the vector-search preset keeps the notebook's layout ─────────────────────
def test_vector_search_preset_reads_the_label_from_the_name(vector_search_dir):
    session = make_session(vector_search_dir,
                           filename_pattern="vector-search", label_from="filename")
    goto_name(session, "PONTO_A_20240115_053000")
    view = session.view()
    assert (view.label, view.score, view.label_from) == ("BOAALB", 0.873, "filename")


def test_vector_search_preset_files_flat_and_rewrites_the_name(vector_search_dir):
    session = make_session(vector_search_dir,
                           filename_pattern="vector-search", label_from="filename")
    goto_name(session, "PONTO_A_20240115_053000")
    session.apply_verdict("false", ["TURDRU"])
    out = vector_search_dir / "false" / "TURDRU"
    assert [p.name for p in out.glob("*.wav")] == [
        "PONTO_A_20240115_053000_12.0-17.0s_0.873_TURDRU.wav"
    ]


def test_vector_search_multi_label_lists_every_label_in_the_name(vector_search_dir):
    session = make_session(vector_search_dir, multi_label=True,
                           filename_pattern="vector-search", label_from="filename")
    goto_name(session, "PONTO_A_20240115_053000")
    session.apply_verdict("true", ["BOAALB", "PHYLUT"])
    assert [p.name for p in (vector_search_dir / "multi").glob("*.wav")] == [
        "PONTO_A_20240115_053000_12.0-17.0s_0.873_BOAALB_PHYLUT.wav"
    ]


# ── verdict folder naming ────────────────────────────────────────────────────
def test_portuguese_session_uses_portuguese_folders(segments_dir):
    session = make_session(segments_dir, lang="pt-BR")
    session.apply_verdict("true")
    assert list((segments_dir / "verdadeiro").rglob("*.wav"))


def test_custom_verdict_folders(segments_dir):
    session = make_session(segments_dir, true_dir="yes", false_dir="no")
    session.apply_verdict("true")
    assert list((segments_dir / "yes").rglob("*.wav"))


# ── navigation ───────────────────────────────────────────────────────────────
def test_navigation_stays_in_range(session):
    session.navigate(-5)
    assert session.index == 0
    session.navigate(+99)
    assert session.index == len(session.segments) - 1


def test_rescan_keeps_the_current_segment(session, segments_dir):
    session.navigate(+1)
    current = session.view().name
    write_wav(segments_dir / "NEW" / "AAA_20240101_000000_0.0_5.0.wav")
    session.rescan()
    assert session.view().name == current
    assert len(session.segments) == 4
    # A rescan finds the new folder's label but does not push it onto the list:
    # the list is the reviewer's to edit, so nothing is added behind their back.
    assert "NEW" in session.discovered_labels()
    assert "NEW" not in session.label_choices()


# ── annotations ──────────────────────────────────────────────────────────────
def test_annotations_record_one_row_per_label(segments_dir):
    session = make_session(segments_dir, multi_label=True, save_annotations=True)
    goto_name(session, FIRST)
    session.apply_verdict("true", ["BOAALB", "PHYLUT"])
    rows = list(csv.DictReader((segments_dir / "annotations.csv").open()))
    assert [r["label"] for r in rows] == ["BOAALB", "PHYLUT"]
    assert {r["site"] for r in rows} == {"PONTO A"}
    # The manifest names the recording this clip came from.
    assert {r["file"] for r in rows} == {"PONTO_A_20240115_053000.wav"}
    # A 5 s window padded out to a 0.5 s clip: the clip is centred on the window.
    assert float(rows[0]["end_time"]) - float(rows[0]["start_time"]) == 0.5


def test_annotations_use_the_label_the_reviewer_confirmed(segments_dir):
    session = make_session(segments_dir, save_annotations=True)
    goto_name(session, FIRST)
    session.apply_verdict("true")
    goto_name(session, "POCA_20240116_190000")
    session.apply_verdict("false", ["TURDRU"])
    rows = list(csv.DictReader((segments_dir / "annotations.csv").open()))
    assert [r["label"] for r in rows] == ["BOAALB", "TURDRU"]
    # Only the first clip is in the manifest, so the second row names no recording.
    assert rows[1]["file"] == ""
    assert session.annotations.state.rows_without_recording == 1


def test_a_blank_annotations_path_falls_back_inside_the_segments_folder(segments_dir):
    session = make_session(segments_dir, save_annotations=True, annotations_path="  ")
    assert session.annotations.enabled
    assert session.annotations.state.path.endswith("annotations.csv")


# ── the editable label list ──────────────────────────────────────────────────
def test_the_list_is_seeded_from_the_collection_and_written(segments_dir):
    session = make_session(segments_dir, labels=["chuva"])
    assert session.label_choices() == ["chuva", "BOAALB", "PHYLUT"]
    assert (segments_dir / "labels.txt").read_text().split() == ["chuva", "BOAALB", "PHYLUT"]


def test_a_stored_list_wins_over_what_the_collection_uses(segments_dir):
    (segments_dir / "labels.txt").write_text("rain\nTURDRU\n", encoding="utf-8")
    session = make_session(segments_dir)
    assert session.label_choices() == ["rain", "TURDRU"]


def test_labels_named_on_the_command_line_are_folded_into_a_stored_list(segments_dir):
    (segments_dir / "labels.txt").write_text("rain\n", encoding="utf-8")
    session = make_session(segments_dir, labels=["chuva"])
    assert session.label_choices() == ["rain", "chuva"]
    assert (segments_dir / "labels.txt").read_text().split() == ["rain", "chuva"]


def test_comments_and_blank_lines_are_ignored(segments_dir):
    (segments_dir / "labels.txt").write_text("# my labels\n\nrain\n  TURDRU  \n", encoding="utf-8")
    assert make_session(segments_dir).label_choices() == ["rain", "TURDRU"]


def test_editing_the_list_persists(segments_dir):
    session = make_session(segments_dir)
    session.labels.add("TURDRU")
    session.labels.remove("PHYLUT")
    assert session.label_choices() == ["BOAALB", "TURDRU"]
    assert make_session(segments_dir).label_choices() == ["BOAALB", "TURDRU"]


def test_replacing_the_list_dedupes_and_keeps_order(segments_dir):
    session = make_session(segments_dir)
    assert session.labels.replace([" b ", "a", "b", ""]) == ["b", "a"]


def test_a_removed_label_still_works_when_a_clip_carries_it(segments_dir):
    """Trimming the list must never block a verdict on a clip that uses the label."""
    session = make_session(segments_dir)
    session.labels.replace([])
    goto_name(session, FIRST)
    assert session.view().label == "BOAALB"          # from its folder, not the list
    session.apply_verdict("true")
    assert (segments_dir / "true" / FIRST).exists()


def test_persistence_can_be_switched_off(segments_dir):
    session = make_session(segments_dir, persist_labels=False, labels_file="")
    session.labels.add("TURDRU")
    assert "TURDRU" in session.label_choices()
    assert not (segments_dir / "labels.txt").exists()


def test_a_folder_that_cannot_be_written_is_reported_not_fatal(segments_dir, monkeypatch):
    session = make_session(segments_dir)
    monkeypatch.setattr(session.backend, "write_bytes",
                        lambda *a, **k: (_ for _ in ()).throw(OSError("read-only")))
    session.labels.add("TURDRU")
    assert "TURDRU" in session.label_choices()       # the session carries on
    assert "read-only" in session.labels.error
    assert session.labels.persisted is False


def test_multi_label_is_on_by_default(segments_dir):
    session = make_session(segments_dir)
    assert session.config.multi_label is True
    assert (segments_dir / "multi").is_dir()
