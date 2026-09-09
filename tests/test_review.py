import csv

from conftest import TEMPLATE, goto_name, make_session, write_wav

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


def test_configured_labels_are_the_only_ones_offered(segments_dir):
    session = make_session(segments_dir, labels=["rain", "BOAALB"])
    assert session.label_choices() == ["rain", "BOAALB"]


def test_site_subfolders_are_not_offered_as_labels(label_on_top_dir):
    """BOAALB/PONTO_A/clip.wav — the sites inside a class folder are not classes."""
    session = make_session(label_on_top_dir, label_depth=1)
    assert session.label_choices() == ["BOAALB", "PHYLUT"]


def test_without_the_depth_those_subfolders_would_be_taken_for_labels(label_on_top_dir):
    assert make_session(label_on_top_dir).label_choices() == ["PHYLUT", "POCA", "PONTO A"]


# ── a name shape no preset fits ──────────────────────────────────────────────
def test_a_template_fills_in_every_fact_the_gui_shows(templated_dir):
    """Without it the name half-matches and the GUI shows facts read off the
    wrong tokens; with it every field is the one it says it is."""
    session = make_session(templated_dir, filename_pattern=TEMPLATE, label_from="filename")
    goto_name(session, "BOAALB")
    view = session.view()
    assert view.label == "BOAALB"
    assert view.site == "PONTO A"
    assert view.recorded_at == "2024-01-15 05:30:00"
    assert (view.det_start, view.det_end) == (12.0, 17.0)
    assert view.score == 0.873
    assert view.extra is None


def test_a_verdict_on_a_templated_name_rewrites_the_label_in_it(templated_dir):
    session = make_session(templated_dir, filename_pattern=TEMPLATE, label_from="filename")
    goto_name(session, "BOAALB")
    session.apply_verdict("false", ["TURDRU"])
    assert (templated_dir / "false" / "TURDRU"
            / "PONTO_A_20240115T053000_REC_12.0_17.0_TURDRU_0.873.wav").exists()


def test_the_same_layout_read_by_its_folders_instead(templated_dir):
    """--label-from folder with --label-depth 1 labels by the top folder, and
    files the clip under that label alone: the site/day folders it was found in
    are not rebuilt, since the file name already carries both."""
    session = make_session(
        templated_dir, filename_pattern=TEMPLATE, label_from="folder", label_depth=1
    )
    assert session.label_choices() == ["BOAALB", "PHYLUT"]
    goto_name(session, "BOAALB")
    assert session.view().site == "PONTO A"      # still read from the name
    session.apply_verdict("true")
    moved = templated_dir / "true" / "BOAALB"
    assert [p.name for p in moved.rglob("*.wav")] == [
        "PONTO_A_20240115T053000_REC_12.0_17.0_BOAALB_0.873.wav"
    ]
    assert [p.name for p in moved.iterdir()] == [
        "PONTO_A_20240115T053000_REC_12.0_17.0_BOAALB_0.873.wav"
    ]


def test_a_correction_under_label_depth_drops_the_folders_below_the_label(templated_dir):
    session = make_session(
        templated_dir, filename_pattern=TEMPLATE, label_from="folder", label_depth=1
    )
    goto_name(session, "BOAALB")
    session.apply_verdict("false", ["TURDRU"])
    assert (templated_dir / "false" / "TURDRU"
            / "PONTO_A_20240115T053000_REC_12.0_17.0_TURDRU_0.873.wav").exists()


def test_a_pattern_that_fits_nothing_is_reported(templated_dir):
    """A wrong pattern shows up as clips with no site, time or score; the count
    of names it actually read is what says so at start-up."""
    session = make_session(templated_dir, filename_pattern="default", label_from="folder")
    matched, total, example = session.pattern_report()
    assert (matched, total) == (0, 2)
    assert example.endswith(".wav")


def test_a_pattern_that_fits_reports_every_name(templated_dir):
    session = make_session(templated_dir, filename_pattern=TEMPLATE, label_from="filename")
    assert session.pattern_report() == (2, 2, "")


# ── where the reviewed clips are written ─────────────────────────────────────
def test_output_sends_the_verdict_folders_elsewhere(segments_dir, tmp_path):
    out = tmp_path / "reviewed"
    session = make_session(segments_dir, output=str(out))
    goto_name(session, FIRST)
    session.apply_verdict("true")
    assert (out / "true" / "PONTO_A" / "BOAALB").is_dir()
    assert not (segments_dir / "true").exists()
    assert not (segments_dir / "PONTO_A" / "BOAALB").exists()   # emptied and pruned


def test_a_relative_output_is_read_against_the_segments_folder(segments_dir):
    session = make_session(segments_dir, output="reviewed")
    goto_name(session, FIRST)
    session.apply_verdict("true")
    assert (segments_dir / "reviewed" / "true" / "PONTO_A" / "BOAALB").is_dir()


def test_an_output_inside_the_segments_folder_is_not_offered_for_review(segments_dir):
    """Its own reviewed clips must not come back as pending on the next scan."""
    session = make_session(segments_dir, output="reviewed")
    goto_name(session, FIRST)
    session.apply_verdict("true")
    session.rescan()
    assert session.counts() == {"pending": 2, "true": 1, "false": 0, "multi": 0}


def test_resuming_counts_what_an_earlier_run_wrote_to_the_output(segments_dir, tmp_path):
    out = tmp_path / "reviewed"
    make_session(segments_dir, output=str(out)).apply_verdict("true")
    resumed = make_session(segments_dir, output=str(out))
    assert resumed.counts() == {"pending": 2, "true": 1, "false": 0, "multi": 0}


def test_the_annotation_table_is_written_to_the_output_folder(segments_dir, tmp_path):
    out = tmp_path / "reviewed"
    session = make_session(segments_dir, output=str(out), save_annotations=True)
    goto_name(session, FIRST)
    session.apply_verdict("true")
    assert (out / "annotations.csv").exists()
    assert not (segments_dir / "annotations.csv").exists()


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


def test_a_site_folder_under_the_label_is_not_rebuilt(label_on_top_dir):
    """BOAALB/PONTO_A/det1.wav corrected to TURDRU lands in false/TURDRU/ — the
    site folder is not carried over; the clip's name already names the site."""
    session = make_session(label_on_top_dir, label_depth=1)
    goto_name(session, "det1")
    assert session.view().label == "BOAALB"
    session.apply_verdict("false", ["TURDRU"])
    moved = label_on_top_dir / "false" / "TURDRU"
    assert [p.name for p in moved.iterdir()] == [
        "PONTO_A_20240115_053000_12.0_17.0_det1.wav"
    ]


def test_the_folders_a_clip_leaves_behind_are_removed(label_on_top_dir):
    """The last clip out of BOAALB/PONTO_A takes the empty folder with it."""
    session = make_session(label_on_top_dir, label_depth=1)
    goto_name(session, "det1")
    session.apply_verdict("true")
    assert not (label_on_top_dir / "BOAALB" / "PONTO_A").exists()
    assert (label_on_top_dir / "BOAALB" / "POCA").is_dir()   # still has its clip


def test_pruning_stops_at_the_segments_root(segments_dir):
    """Reviewing the last pending clip empties the tree but keeps the root."""
    session = make_session(segments_dir)
    while session.segments:
        session.apply_verdict("true")
    assert segments_dir.is_dir()
    assert not (segments_dir / "PONTO_A").exists()
    assert not (segments_dir / "POCA").exists()


def test_a_folder_holding_anything_else_is_left_alone(segments_dir):
    """A folder that still holds a pending clip, or any other file, stays."""
    (segments_dir / "PONTO_A" / "BOAALB" / "notes.txt").write_text("keep me")
    session = make_session(segments_dir)
    goto_name(session, FIRST)
    session.apply_verdict("true")
    assert (segments_dir / "PONTO_A" / "BOAALB" / "notes.txt").exists()


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
    session = make_session(segments_dir)
    assert session.label_choices() == ["BOAALB", "PHYLUT"]
    assert (segments_dir / "labels.txt").read_text().split() == ["BOAALB", "PHYLUT"]


def test_a_stored_list_wins_over_what_the_collection_uses(segments_dir):
    (segments_dir / "labels.txt").write_text("rain\nTURDRU\n", encoding="utf-8")
    session = make_session(segments_dir)
    assert session.label_choices() == ["rain", "TURDRU"]


def test_labels_named_on_the_command_line_replace_a_stored_list(segments_dir):
    (segments_dir / "labels.txt").write_text("rain\n", encoding="utf-8")
    session = make_session(segments_dir, labels=["chuva"])
    assert session.label_choices() == ["chuva"]
    assert (segments_dir / "labels.txt").read_text().split() == ["chuva"]


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
