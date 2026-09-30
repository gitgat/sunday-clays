import json

import review
from tests.helpers import make_out, record


def test_review_page_lists_flagged_blocks_only_with_inputs_and_save(tmp_path):
    out = make_out(tmp_path)
    path, count = review.build_review(out)
    page = path.read_text()
    assert path == out / "review.html" and count == 3
    assert page.count('class="card"') == 3
    assert 'data-id="p6-b1"' not in page  # the ok block is not listed
    assert 'data-id="p6-b2"' in page
    assert 'src="sundays/2026-05-31/blocks/p6-b2.png"' in page
    assert 'src="sundays/2026-05-31/blocks/p6-b2-tot.png"' in page
    assert page.count('type="number"') == 9  # three stations per card
    assert 'data-max="8"' in page
    assert 'id="save"' in page and "review-decisions.json" in page
    assert "Fakeman, Bo: 21" in page and "sheet_vs_official" in page
    assert "no matching results row" in page
    assert "Nobody &lt;b&gt;" in page and "<b>" not in page.split("<script>")[0].replace("<br>", "").replace(
        "<body>", ""
    )
    assert 'class="sum"' in page and "Accept" in page and "Skip" in page
    assert 'value=""' in page  # the missing tot is an empty input


def decisions_file(tmp_path, decisions):
    path = tmp_path / "review-decisions.json"
    path.write_text(json.dumps({"decisions": decisions}))
    return path


def readings_of(out):
    return {r["id"]: r for r in json.loads((out / "sundays" / "2026-05-31" / "readings.json").read_text())}


def d(block, action, name="Fakeman, Bo", tots=(7, 7, 3), date="2026-05-31"):
    return {"date": date, "id": f"p6-b{block}", "action": action, "name": name, "tots": list(tots)}


def test_accept_applies_edits_and_skip_marks_skipped(tmp_path):
    out = make_out(tmp_path)
    applied, problems = review.apply_review(
        out,
        decisions_file(
            tmp_path, [d(2, "accept", tots=(7, 7, 7)), d(3, "skip"), d(4, "accept", "mockley, cy", (7, 7, 6))]
        ),
    )
    assert (applied, problems) == (3, [])
    got = readings_of(out)
    assert got["p6-b2"]["status"] == "accepted" and got["p6-b2"]["tots"] == [7, 7, 7] and got["p6-b2"]["sum"] == 21
    assert got["p6-b2"]["official"] == 21  # the official score is untouched
    assert got["p6-b3"]["status"] == "skipped"
    assert got["p6-b4"]["matched"] == "Mockley, Cy" and got["p6-b4"]["official"] == 20


def test_accept_needs_station_totals_that_add_up_to_the_spreadsheet_score(tmp_path):
    out = make_out(tmp_path)
    applied, problems = review.apply_review(out, decisions_file(tmp_path, [d(2, "accept", tots=(7, 7, 4))]))
    assert applied == 0
    assert problems == ["2026-05-31 p6-b2: station totals add to 18, spreadsheet score is 21"]
    got = readings_of(out)["p6-b2"]
    assert got["status"] == "review" and got["tots"] == [7, 7, 3]  # unchanged


def test_accept_names_every_spreadsheet_score_a_two_round_shooter_could_have(tmp_path):
    out = make_out(tmp_path)
    sunday = out / "sundays" / "2026-05-31" / "sunday.json"
    meta = json.loads(sunday.read_text())
    meta["officials"] = [*meta["officials"], {"name": "Fakeman, Bo", "hits": 17, "note": None, "gauge": None}]
    sunday.write_text(json.dumps(meta))
    _, problems = review.apply_review(out, decisions_file(tmp_path, [d(2, "accept", tots=(7, 7, 4))]))
    assert problems == ["2026-05-31 p6-b2: station totals add to 18, spreadsheet score is 21 or 17"]


def test_accept_problems_are_reported_and_leave_the_block_unchanged(tmp_path):
    out = make_out(tmp_path)
    applied, problems = review.apply_review(
        out,
        decisions_file(
            tmp_path,
            [
                d(2, "accept", tots=(7, 7)),
                d(2, "accept", tots=(7, 8, 3)),
                d(2, "accept", tots=(7, "x", 3)),
                d(2, "accept", tots=(True, 1, 1)),
                d(2, "accept", name="Nobody, Known"),
                d(2, "accept", name="Testerson, Ann"),  # already has an ok sheet
                d(9, "accept"),
                d(2, "maybe"),
                d(2, "accept", date="2025-01-05"),
            ],
        ),
    )
    assert applied == 0 and len(problems) == 9
    assert "needs 3 station numbers" in problems[0]
    assert all("outside 0 to its target count" in p for p in problems[1:4])
    assert "not a name in that Sunday's results" in problems[4]
    assert "already has a sheet" in problems[5]
    assert "no such block" in problems[6] and "unknown action" in problems[7] and "no readings" in problems[8]
    assert readings_of(out)["p6-b2"]["status"] == "review"


def test_accepting_a_non_list_of_tots_is_a_problem(tmp_path):
    out = make_out(tmp_path)
    decision = d(2, "accept")
    decision["tots"] = "7 7 3"
    assert review.apply_review(out, decisions_file(tmp_path, [decision]))[0] == 0


def decide(tmp_path, block, name="Testerson, Ann", tots=(7, 7, 3)):
    path = tmp_path / "d.json"
    decision = {"date": "2026-05-31", "id": block, "action": "accept", "name": name, "tots": list(tots)}
    path.write_text(json.dumps({"decisions": [decision]}))
    return path


def set_officials(out, change):
    sunday = out / "sundays" / "2026-05-31" / "sunday.json"
    meta = json.loads(sunday.read_text())
    change(meta["officials"])
    sunday.write_text(json.dumps(meta))


def test_a_second_round_by_the_same_shooter_can_be_accepted_against_the_other_row(tmp_path):
    from tests.helpers import OFFICIALS

    out = make_out(tmp_path)
    set_officials(out, lambda rows: rows.append({**OFFICIALS[0], "hits": 17}))
    assert review.apply_review(out, decide(tmp_path, "p6-b4")) == (1, [])
    record = next(
        r for r in json.loads((out / "sundays" / "2026-05-31" / "readings.json").read_text()) if r["id"] == "p6-b4"
    )
    assert record["official"] == 17 and record["matched"] == "Testerson, Ann"
    # a third sheet for a name that has only two rows is a clash
    applied, problems = review.apply_review(out, decide(tmp_path, "p6-b3"))
    assert applied == 0 and "already has" in problems[0]


def test_a_workbook_that_changed_since_an_accepted_sheet_still_uses_up_a_row(tmp_path):
    out = make_out(tmp_path)
    set_officials(out, lambda rows: rows[0].update(hits=99))  # p6-b1 was matched to Ann's row when it scored 22
    applied, problems = review.apply_review(out, decide(tmp_path, "p6-b4"))
    assert applied == 0 and "already has" in problems[0]


def test_review_page_shows_both_engines_readings(tmp_path):
    readings = [
        {
            **record(1, "Bo Fakeman", "Fakeman, Bo", 21, [7, 7, 7], "review", ["engines_disagree"]),
            "source": "claude",
            "gemma": {"tots": [7, 6, 8], "event_total": 21},
        },
        {
            **record(2, "Ann Testerson", "Testerson, Ann", 22, [7, 7, 8], "review", ["sheet_vs_official"]),
            "source": "gemma_second_opinion",
            "claude": {"tots": [7, 1, 8], "event_total": 16},
        },
        {**record(3, "Cy Mockley", "Mockley, Cy", 20, [7, 7, 6], "review", ["sheet_vs_official"]), "source": "claude"},
        record(4, "Di", None, None, [1], "review", ["no_official_match"]),
    ]
    page = review.build_review(make_out(tmp_path, readings=readings))[0].read_text()
    assert "Read by: claude. Gemma read: [7, 6, 8], Event Total 21" in page
    assert "Read by: gemma_second_opinion. Claude read: [7, 1, 8], Event Total 16" in page
    assert "Read by: claude. </p>" in page
    assert page.count('class="engines"') == 3  # a plain Gemma reading shows no engine line
