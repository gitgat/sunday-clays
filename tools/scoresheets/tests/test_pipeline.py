import json

import pytest
from PIL import Image

import checks
import pipeline
from tests.fixtures import PDF_TEXT, TYPED
from vlm import VlmError, VlmUnreachable

OFFICIALS = [
    {"name": "Testerson, Ann", "hits": 22},
    {"name": "Fakeman, Bo", "hits": 21},
    {"name": "Mockley, Cy", "hits": 20},
]
TARGETS = [7, 7, 8]
IMG = Image.new("RGB", (10, 10), "white")


class FakeClient:
    """Answers whole-block reads from `whole` and Tot reads from `tots` (one reply per attempt)."""

    def __init__(self, whole, tots):
        self.whole, self.tots = whole, tots
        self.calls: list[tuple[str, float, int]] = []

    def ask(self, _image, prompt, temperature, attempt=0):
        kind = "tot" if "Tot column" in prompt else "whole"
        self.calls.append((kind, temperature, attempt))
        source = self.tots if kind == "tot" else self.whole
        value = source[min(attempt, len(source) - 1)] if kind == "tot" else source
        if isinstance(value, Exception):
            raise value
        return value if isinstance(value, str) else json.dumps(value)


def whole(name="Ann Testerson", total=22):
    return {"name": name, "malf": "", "event_total": total}


def tots(values, total=None):
    return {"tots": values, "event_total": sum(values) if total is None else total}


def read(client, officials=OFFICIALS):
    return pipeline.read_block(client, IMG, IMG, TARGETS, officials)


def test_first_reading_passing_the_checks_is_kept_with_one_try():
    client = FakeClient(whole(), [tots([7, 7, 8])])
    record = read(client)
    assert record == {"name_read": "Ann Testerson", "tots": [7, 7, 8], "event_total": 22, "malf": "", "tries": 1}
    assert [c[0] for c in client.calls] == ["whole", "tot"]


def test_failed_reading_is_retried_at_high_temperature_until_one_passes():
    client = FakeClient(whole(), [tots([1, 7, 8], 22), tots([7, 6, 8], 22), tots([7, 7, 8]), tots([0, 0, 0])])
    record = read(client)
    assert record["tots"] == [7, 7, 8]
    assert record["tries"] == 3
    assert client.calls[1:] == [("tot", 0.2, 0), ("tot", 0.8, 1), ("tot", 0.8, 2)]


def test_first_reading_is_kept_when_no_retry_passes():
    client = FakeClient(whole(), [tots([1, 7, 8], 22)])
    record = read(client)
    assert record["tots"] == [1, 7, 8]
    assert record["tries"] == pipeline.RETRIES + 1
    assert sum(1 for c in client.calls if c[0] == "tot") == pipeline.RETRIES + 1


def test_unmatched_name_is_not_retried():
    client = FakeClient(whole("Zed Nobody"), [tots([7, 7, 8])])
    assert read(client)["tries"] == 1
    assert len(client.calls) == 2


def test_event_total_falls_back_to_the_whole_block_read():
    client = FakeClient(whole(total=22), [{"tots": [7, 7, 8]}])
    assert read(client)["event_total"] == 22


def test_string_numbers_and_junk_are_coerced():
    client = FakeClient(whole(), [{"tots": ["7", "x", True, 8.5], "event_total": "22"}])
    record = read(client)
    assert record["tots"] == [7, None, None, None]
    assert record["event_total"] == 22


def test_blank_block_is_none():
    client = FakeClient({"name": "", "event_total": None}, ["not json"])
    assert read(client) is None


def test_named_block_with_unreadable_tots_is_kept_for_review():
    client = FakeClient(whole(), ["garbage"])
    record = read(client)
    assert record["tots"] == [] and record["name_read"] == "Ann Testerson"


def test_server_error_flags_the_block_and_unreachable_stops_the_run():
    record = read(FakeClient(VlmError("model server answered 500"), []))
    assert record["error"] == "model server answered 500"
    with pytest.raises(VlmUnreachable):
        read(FakeClient(VlmUnreachable("down"), []))


def test_retry_errors_stop_retrying_but_keep_the_first_reading():
    client = FakeClient(whole(), [tots([1, 7, 8], 22), VlmError("boom")])
    record = read(client)
    assert record["tots"] == [1, 7, 8] and record["tries"] == 1
    with pytest.raises(VlmUnreachable):
        read(FakeClient(whole(), [tots([1, 7, 8], 22), VlmUnreachable("down")]))


META = {"date": "2026-05-31", "layout": [[2, 7], [4, 7], [7, 8]], "officials": OFFICIALS}


def rec(name, values, total=None, **extra):
    return {"name_read": name, "tots": values, "event_total": sum(values) if total is None else total, **extra}


def test_resolve_matches_one_to_one_and_sets_status_and_reasons():
    readings = [
        rec("Ann Testerson", [7, 7, 8]),
        rec("Bo Fakeman", [7, 7, 3]),  # official 21, sheet 17: sheet_vs_official
        rec("Ann Testerson", [7, 7, 8]),  # second sheet for the same row: no match
        rec("Cy Mockley", [7, 7], 14, error="boom"),
    ]
    out = pipeline.resolve(META, readings)
    assert [r["status"] for r in out] == ["ok", "review", "review", "review"]
    assert out[0]["matched"] == "Testerson, Ann" and out[0]["official"] == 22 and out[0]["sum"] == 22
    assert out[1]["reasons"] == [checks.SHEET_VS_OFFICIAL]
    assert out[2]["matched"] is None and out[2]["reasons"] == [checks.NO_OFFICIAL_MATCH]
    assert out[3]["reasons"] == [checks.MODEL_ERROR] and "error" not in out[3]


def sunday_files(tmp_path, blocks=("p3-b1", "p3-b2"), sha="sha-1"):
    root = tmp_path / "sundays" / "2026-05-31"
    (root / "blocks").mkdir(parents=True)
    for block_id in blocks:
        IMG.save(root / "blocks" / f"{block_id}.png")
        IMG.save(root / "blocks" / f"{block_id}-tot.png")
    (root / "sunday.json").write_text(json.dumps({**META, "sha256": sha, "blocks": list(blocks)}))
    return root


@pytest.mark.parametrize("jobs", [1, 3])
def test_read_sunday_writes_readings_and_counts(tmp_path, jobs):
    root = sunday_files(tmp_path, ("p3-b1", "p3-b2", "p3-b3"))

    class Client:
        def ask(self, image, prompt, temperature, attempt=0):
            return json.dumps(tots([7, 7, 8]) if "Tot column" in prompt else whole())

    messages: list[str] = []
    counts = pipeline.read_sunday(root, Client(), jobs=jobs, log=messages.append)  # type: ignore[arg-type]
    # the same name three times: one match, two flagged
    assert counts == {"ok": 1, "review": 2, "skipped": 0, "kept": 0, "stale": 0}
    readings = json.loads((root / "readings.json").read_text())
    assert [r["id"] for r in readings] == ["p3-b1", "p3-b2", "p3-b3"]
    assert (readings[0]["page"], readings[0]["block"]) == (3, 1)
    assert len(messages) == 3


def test_read_sunday_counts_blank_blocks(tmp_path):
    root = sunday_files(tmp_path, ("p3-b1",))

    class Blank:
        def ask(self, image, prompt, temperature, attempt=0):
            return "{}"

    counts = pipeline.read_sunday(root, Blank())  # type: ignore[arg-type]
    assert counts == {"ok": 0, "review": 0, "skipped": 1, "kept": 0, "stale": 0}
    assert json.loads((root / "readings.json").read_text()) == []


def test_scan_pdfs_parses_dedupes_and_cuts_blocks(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline, "run_pdftotext", lambda pdf: PDF_TEXT if "bad" not in pdf.name else "nothing")
    monkeypatch.setattr(pipeline, "render_page", lambda pdf, page: Image.new("RGB", (1700, 2200), "white"))
    first = tmp_path / "2026-05-31 Sunday Clays Update.pdf"
    first.write_bytes(b"one")
    same = tmp_path / "2026-05-31 Sunday Clays Update (1).pdf"
    same.write_bytes(b"one")
    other = tmp_path / "again.pdf"
    other.write_bytes(b"two")
    bad = tmp_path / "bad.pdf"
    bad.write_bytes(b"x")
    out = tmp_path / "out"
    results = pipeline.scan_pdfs([first, same, other, bad], out)
    assert [r.sunday for r in results] == ["2026-05-31", "2026-05-31", "2026-05-31", None]
    assert results[0].note == "7 results, 3 stations (22 targets), 6 blocks, scoresheet pages: 1"
    assert "identical copy" in results[1].note
    assert "different file" in results[2].note
    assert "no Sunday date" in results[3].note
    root = out / "sundays" / "2026-05-31"
    meta = json.loads((root / "sunday.json").read_text())
    assert meta["layout"] == [[2, 7], [4, 7], [7, 8]]
    assert meta["blocks"] == [f"p2-b{i}" for i in range(1, 7)]
    assert meta["officials"][0] == {"name": "Testerson, Ann", "hits": 22, "note": None, "gauge": None}
    assert meta["presentations"]["4"][1]["reps"] == 3
    assert (root / "blocks" / "p2-b6-tot.png").exists()
    assert meta["pdf"] == first.name and len(meta["sha256"]) == 64


def test_scan_pdfs_skip_date(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline, "run_pdftotext", lambda pdf: TYPED)
    pdf = tmp_path / "a.pdf"
    pdf.write_bytes(b"a")
    (result,) = pipeline.scan_pdfs([pdf], tmp_path / "out", ["2026-05-31"])
    assert result.note == "skipped by request"
    assert not (tmp_path / "out").exists()


def test_scan_page_detection_ignores_the_trailing_form_feed(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline, "run_pdftotext", lambda pdf: TYPED + "\f")
    pdf = tmp_path / "a.pdf"
    pdf.write_bytes(b"a")
    (result,) = pipeline.scan_pdfs([pdf], tmp_path / "out")
    assert result.note.endswith("0 blocks, scoresheet pages: 0")


def test_run_pdftotext_and_render_page_call_poppler(tmp_path, monkeypatch):
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        if cmd[0] == "pdftoppm":
            Image.new("RGB", (4, 4), "white").save(cmd[-1] + ".png")

        class Done:
            stdout = "text"

        return Done()

    monkeypatch.setattr(pipeline.subprocess, "run", fake_run)
    assert pipeline.run_pdftotext(tmp_path / "a.pdf") == "text"
    assert calls[0][:3] == ["pdftotext", "-layout", str(tmp_path / "a.pdf")]
    assert pipeline.render_page(tmp_path / "a.pdf", 7).size == (4, 4)
    assert calls[1][:6] == ["pdftoppm", "-r", "200", "-f", "7", "-l"]


def test_text_without_a_trailing_form_feed_keeps_its_last_page(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline, "run_pdftotext", lambda pdf: TYPED)
    pdf = tmp_path / "a.pdf"
    pdf.write_bytes(b"a")
    (result,) = pipeline.scan_pdfs([pdf], tmp_path / "out")
    assert result.note.endswith("0 blocks, scoresheet pages: 0")


def test_date_falls_back_to_the_file_name(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline, "run_pdftotext", lambda pdf: "commentary only, no header")
    monkeypatch.setattr(pipeline, "render_page", lambda pdf, page: Image.new("RGB", (1700, 2200), "white"))
    named = tmp_path / "2026-09-06 Sunday Clays Update.pdf"
    named.write_bytes(b"a")
    impossible = tmp_path / "2026-13-45 Sunday Clays Update.pdf"
    impossible.write_bytes(b"b")
    results = pipeline.scan_pdfs([named, impossible], tmp_path / "out")
    assert results[0].sunday == "2026-09-06"
    assert results[1].sunday is None


def test_typed_data_missing(tmp_path):
    root = sunday_files(tmp_path)
    assert pipeline.typed_data_missing(root) is False
    meta = json.loads((root / "sunday.json").read_text())
    for key in ("layout", "officials"):
        (root / "sunday.json").write_text(json.dumps({**meta, key: []}))
        assert pipeline.typed_data_missing(root) is True


class Reads:
    """Reads every block as Ann Testerson, sheet matching the official 22."""

    def __init__(self):
        self.calls = 0

    def ask(self, image, prompt, temperature, attempt=0):
        self.calls += 1
        return json.dumps(tots([7, 7, 8]) if "Tot column" in prompt else whole())


def test_reading_again_keeps_accepted_and_skipped_decisions(tmp_path):
    root = sunday_files(tmp_path, ("p3-b1", "p3-b2", "p3-b3"))
    pipeline.read_sunday(root, Reads())  # type: ignore[arg-type]
    path = root / "readings.json"
    readings = json.loads(path.read_text())
    readings[1].update(status="accepted", tots=[7, 7, 7], sum=21, matched="Fakeman, Bo", official=21)
    readings[2]["status"] = "skipped"
    path.write_text(json.dumps(readings))
    client = Reads()
    counts = pipeline.read_sunday(root, client)  # type: ignore[arg-type]
    again = json.loads(path.read_text())
    assert [r["id"] for r in again] == ["p3-b1", "p3-b2", "p3-b3"]
    assert [r["status"] for r in again] == ["ok", "accepted", "skipped"]
    assert again[1]["tots"] == [7, 7, 7] and again[1]["matched"] == "Fakeman, Bo"
    assert counts == {"ok": 1, "review": 0, "skipped": 0, "kept": 2, "stale": 0}
    assert client.calls == 2  # only the undecided block is read again


def test_a_kept_decision_keeps_its_official_row_away_from_a_fresh_reading(tmp_path):
    root = sunday_files(tmp_path, ("p3-b1", "p3-b2"))
    path = root / "readings.json"
    kept = {"id": "p3-b1", "page": 3, "block": 1, "name_read": "Ann T", "tots": [7, 7, 8], "event_total": 22}
    kept.update(malf="", tries=1, matched="Testerson, Ann", official=22, sum=22, status="accepted", reasons=[])
    path.write_text(json.dumps([kept]))
    pipeline.read_sunday(root, Reads())  # type: ignore[arg-type]
    again = json.loads(path.read_text())
    assert [r["status"] for r in again] == ["accepted", "review"]
    assert again[1]["reasons"] == ["no_official_match"]


# --- follow-ups: official scores from the workbook ---------------------------------------------------------------

WORKBOOK_ROWS = {
    "2026-05-31": [
        {"name": "Workbook, Wanda", "hits": 22, "note": None, "gauge": None},
        {"name": "Sheet, Sam", "hits": 21, "note": None, "gauge": None},
    ]
}


def fake_pdf(tmp_path, monkeypatch, text=PDF_TEXT, name="a.pdf"):
    monkeypatch.setattr(pipeline, "run_pdftotext", lambda pdf: text)
    monkeypatch.setattr(pipeline, "render_page", lambda pdf, page: Image.new("RGB", (1700, 2200), "white"))
    pdf = tmp_path / name
    pdf.write_bytes(b"a")
    return pdf


def test_workbook_rows_are_the_official_scores_for_their_sunday(tmp_path, monkeypatch):
    pdf = fake_pdf(tmp_path, monkeypatch)
    (result,) = pipeline.scan_pdfs([pdf], tmp_path / "out", officials=WORKBOOK_ROWS)
    meta = json.loads((tmp_path / "out" / "sundays" / "2026-05-31" / "sunday.json").read_text())
    assert meta["officials"] == WORKBOOK_ROWS["2026-05-31"] and meta["officials_source"] == "workbook"
    assert result.note.startswith("2 results (from the scores workbook), 3 stations (22 targets)")


def test_typed_results_are_the_fallback_when_the_workbook_has_no_rows_for_the_date(tmp_path, monkeypatch):
    pdf = fake_pdf(tmp_path, monkeypatch)
    other = {"2026-06-07": WORKBOOK_ROWS["2026-05-31"]}
    (result,) = pipeline.scan_pdfs([pdf], tmp_path / "out", officials=other)
    meta = json.loads((tmp_path / "out" / "sundays" / "2026-05-31" / "sunday.json").read_text())
    assert meta["officials_source"] == "typed" and meta["officials"][0]["name"] == "Testerson, Ann"
    assert result.note.startswith("7 results, 3 stations")


def test_2025_11_16_is_skipped_by_default_because_it_has_no_scores(tmp_path, monkeypatch):
    pdf = fake_pdf(tmp_path, monkeypatch, text="commentary only", name="2025-11-16 Sunday Clays Update.pdf")
    (result,) = pipeline.scan_pdfs([pdf], tmp_path / "out")
    assert result.sunday == "2025-11-16" and "no scores" in result.note and not result.note[0].isdigit()
    assert not (tmp_path / "out").exists()


def test_multi_round_sunday_matches_each_block_to_its_own_row_one_to_one():
    officials = [
        {"name": "Testerson, Ann", "hits": 25},
        {"name": "Fakeman, Bo", "hits": 21},
        {"name": "Testerson, Ann", "hits": 22},
    ]
    meta = {"date": "2026-05-31", "layout": [[2, 7], [4, 7], [7, 8]], "officials": officials}
    readings = [rec("Ann Testerson", [7, 7, 8]), rec("Ann Testerson", [8, 8, 9])]  # sums 22 and 25
    out = pipeline.resolve(meta, readings)
    assert [(r["official"], r["matched"]) for r in out] == [(22, "Testerson, Ann"), (25, "Testerson, Ann")]
    assert out[0]["status"] == "ok" and out[1]["reasons"] == [checks.TOT_OUT_OF_RANGE]  # 8 > 7 on station 2
    third = pipeline.resolve(
        meta, [rec("Ann Testerson", [7, 7, 8]) for _ in range(3)]
    )  # only two rows for three sheets
    assert sorted(str(r["matched"]) for r in third) == ["None", "Testerson, Ann", "Testerson, Ann"]
    assert [r["official"] for r in third if r["matched"]] == [22, 25]


def test_multi_round_reading_is_checked_against_the_row_that_agrees_with_the_sheet():
    officials = [{"name": "Testerson, Ann", "hits": 25}, {"name": "Testerson, Ann", "hits": 22}]
    client = FakeClient(whole(), [tots([7, 7, 8])])
    record = read(client, officials)
    assert record["tries"] == 1 and len(client.calls) == 2  # 22 is one of Ann's two official scores


# --- follow-ups: no retry when the sheet is self-consistent ------------------------------------------------------


def test_self_consistent_sheet_that_disagrees_with_the_official_score_is_not_retried():
    client = FakeClient(whole(), [tots([7, 7, 3])])  # sums to 17 = event total, official 22
    record = read(client)
    assert record["tots"] == [7, 7, 3] and record["tries"] == 1
    assert len(client.calls) == 2


def test_sheet_vs_official_plus_another_failure_is_still_retried():
    client = FakeClient(whole(), [tots([7, 7, 3], 20), tots([7, 7, 8])])  # first: sum 17 vs written 20
    record = read(client)
    assert record["tots"] == [7, 7, 8] and record["tries"] == 2


def test_a_retry_that_becomes_consistent_is_kept_when_its_total_agrees_with_the_whole_block_read():
    client = FakeClient(whole(total=18), [tots([7, 7, 3], 20), tots([7, 7, 4])])  # retry sum 18 = total 18 != official
    record = read(client)
    assert record["tots"] == [7, 7, 4] and record["tries"] == 2 and record["event_total"] == 18


def test_a_retry_that_becomes_consistent_is_kept_when_its_total_agrees_with_the_first_reading():
    client = FakeClient(whole(), [tots([7, 7, 3], 18), tots([7, 7, 4])])  # first: sum 17 vs written 18
    record = read(client)
    assert record["tots"] == [7, 7, 4] and record["tries"] == 2


def test_a_retry_that_is_consistent_only_because_it_misread_the_total_too_is_not_adopted():
    # first sum 17 vs written 20; the retry's tots and total both changed, matching neither earlier total (20, 22)
    client = FakeClient(whole(), [tots([7, 7, 3], 20), tots([7, 7, 4])])
    record = read(client)
    assert record["tots"] == [7, 7, 3] and record["event_total"] == 20 and record["tries"] == pipeline.RETRIES + 1


def test_a_reading_that_passes_no_check_is_retried_and_the_first_kept_otherwise():
    client = FakeClient(whole(), [tots([1, 7, 8], 30)])  # never consistent
    record = read(client)
    assert record["tots"] == [1, 7, 8] and record["tries"] == pipeline.RETRIES + 1


# --- follow-ups: stale decisions ---------------------------------------------------------------------------------


def decided_readings(sha):
    kept = {"id": "p3-b1", "page": 3, "block": 1, "name_read": "Ann T", "tots": [7, 7, 8], "event_total": 22}
    kept.update(malf="", tries=1, matched="Testerson, Ann", official=22, sum=22, status="accepted", reasons=[])
    if sha is not None:
        kept["pdf_sha256"] = sha
    return [kept]


def test_readings_carry_the_pdf_sha256(tmp_path):
    root = sunday_files(tmp_path, ("p3-b1",), sha="aa")
    pipeline.read_sunday(root, Reads())  # type: ignore[arg-type]
    assert json.loads((root / "readings.json").read_text())[0]["pdf_sha256"] == "aa"


def test_decisions_from_a_different_pdf_are_dropped_and_read_again(tmp_path):
    root = sunday_files(tmp_path, ("p3-b1",), sha="new")
    (root / "readings.json").write_text(json.dumps(decided_readings("old")))
    client = Reads()
    counts = pipeline.read_sunday(root, client)  # type: ignore[arg-type]
    assert counts == {"ok": 1, "review": 0, "skipped": 0, "kept": 0, "stale": 1}
    assert client.calls == 2  # the block was read again
    again = json.loads((root / "readings.json").read_text())
    assert again[0]["status"] == "ok" and again[0]["pdf_sha256"] == "new"


def test_decisions_from_the_same_pdf_or_from_before_shas_were_stored_are_kept(tmp_path):
    for sha in ("same", None):
        root = sunday_files(tmp_path / str(sha), ("p3-b1",), sha="same")
        (root / "readings.json").write_text(json.dumps(decided_readings(sha)))
        client = Reads()
        counts = pipeline.read_sunday(root, client)  # type: ignore[arg-type]
        assert counts["kept"] == 1 and counts["stale"] == 0 and client.calls == 0


def test_a_decision_saved_before_shas_were_stored_gets_the_current_sha_and_can_then_go_stale(tmp_path):
    root = sunday_files(tmp_path, ("p3-b1",), sha="same")
    (root / "readings.json").write_text(json.dumps(decided_readings(None)))
    pipeline.read_sunday(root, Reads())  # type: ignore[arg-type]
    assert json.loads((root / "readings.json").read_text())[0]["pdf_sha256"] == "same"
    meta = json.loads((root / "sunday.json").read_text())
    (root / "sunday.json").write_text(json.dumps({**meta, "sha256": "other"}))
    counts = pipeline.read_sunday(root, Reads())  # type: ignore[arg-type]
    assert counts["stale"] == 1 and counts["kept"] == 0


def test_a_kept_decision_uses_up_only_one_of_two_same_name_rows(tmp_path):
    root = tmp_path / "sundays" / "2026-05-31"
    (root / "blocks").mkdir(parents=True)
    for block_id in ("p3-b1", "p3-b2"):
        IMG.save(root / "blocks" / f"{block_id}.png")
        IMG.save(root / "blocks" / f"{block_id}-tot.png")
    officials = [{"name": "Testerson, Ann", "hits": 25}, {"name": "Testerson, Ann", "hits": 22}]
    (root / "sunday.json").write_text(json.dumps({**META, "officials": officials, "blocks": ["p3-b1", "p3-b2"]}))
    (root / "readings.json").write_text(json.dumps(decided_readings(None)))  # kept: Ann, official 22
    pipeline.read_sunday(root, Reads())  # type: ignore[arg-type]
    again = json.loads((root / "readings.json").read_text())
    assert [r["status"] for r in again] == ["accepted", "review"]
    assert again[1]["matched"] == "Testerson, Ann" and again[1]["official"] == 25


def test_a_decision_whose_official_row_is_gone_frees_nothing(tmp_path):
    root = sunday_files(tmp_path, ("p3-b1", "p3-b2"))
    kept = decided_readings(None)
    kept[0]["official"] = 99  # the workbook row it used no longer exists
    (root / "readings.json").write_text(json.dumps(kept))
    pipeline.read_sunday(root, Reads())  # type: ignore[arg-type]
    again = json.loads((root / "readings.json").read_text())
    assert [r["status"] for r in again] == ["accepted", "ok"]  # Ann's only row is still free for the new sheet


def test_scan_keeps_each_whole_page_for_the_claude_engine_and_drops_stale_ones(tmp_path, monkeypatch):
    pdf = fake_pdf(tmp_path, monkeypatch)
    out = tmp_path / "out"
    stale = out / "sundays" / "2026-05-31" / "pages" / "p9.png"
    stale.parent.mkdir(parents=True)
    IMG.save(stale)
    pipeline.scan_pdfs([pdf], out)
    pages = out / "sundays" / "2026-05-31" / "pages"
    assert [p.name for p in pages.iterdir()] == ["p2.png"]  # the scan page only; nothing left from an older scan
    with Image.open(pages / "p2.png") as page:
        assert page.size == (1700, 2200)


def test_an_error_reason_on_a_reading_is_the_reason_resolve_reports():
    out = pipeline.resolve(META, [rec("", [], None, error="boom", error_reason=checks.ENGINE_ERROR)])
    assert out[0]["reasons"] == [checks.ENGINE_ERROR]
