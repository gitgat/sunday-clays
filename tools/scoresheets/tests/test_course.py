import json

import pytest
from PIL import Image

import pipeline
from tests.fixtures import (
    PDF_TEXT_IMAGE_BOTH,
    PDF_TEXT_IMAGE_COURSE,
    PDF_TEXT_NO_COURSE_PAGE,
    PDF_TEXT_RESULTS_THEN_SCANS,
)
from vlm import VlmError, VlmUnreachable

GOOD = {"stations": [{"stn": 1, "targets": 10}, {"stn": 2, "targets": 15}, {"stn": 3, "targets": 25}]}


def scan(tmp_path, monkeypatch, text, name="2026-05-31 Sunday Clays Update.pdf"):
    monkeypatch.setattr(pipeline, "run_pdftotext", lambda pdf: text)
    monkeypatch.setattr(pipeline, "render_page", lambda pdf, page: Image.new("RGB", (1700, 2200), "white"))
    pdf = tmp_path / name
    pdf.write_bytes(b"a")
    (result,) = pipeline.scan_pdfs([pdf], tmp_path / "out")
    root = tmp_path / "out" / "sundays" / "2026-05-31"
    return result, root, json.loads((root / "sunday.json").read_text())


def test_course_page_is_the_page_after_the_typed_results(tmp_path, monkeypatch):
    result, root, meta = scan(tmp_path, monkeypatch, PDF_TEXT_IMAGE_COURSE)
    assert meta["course_page"] == 2 and meta["layout"] == []
    assert meta["blocks"] == [f"p3-b{i}" for i in range(1, 7)]  # the course picture is not cut into shooter blocks
    assert (root / "course.png").exists()
    assert "no typed course" in result.note and "course page 2" in result.note


def test_when_the_results_are_pictures_too_the_course_is_the_second_picture_page(tmp_path, monkeypatch):
    _, root, meta = scan(tmp_path, monkeypatch, PDF_TEXT_IMAGE_BOTH)
    assert meta["course_page"] == 3 and meta["results_page"] == 2
    assert meta["blocks"] == [f"p4-b{i}" for i in range(1, 7)]
    assert (root / "course.png").exists()


def test_no_page_after_the_results_means_no_course_picture(tmp_path, monkeypatch):
    result, root, meta = scan(tmp_path, monkeypatch, PDF_TEXT_NO_COURSE_PAGE)
    assert meta["course_page"] is None and not (root / "course.png").exists()
    assert "no typed course and no course page found" in result.note


def test_a_blank_scoresheet_page_is_never_taken_for_the_course_picture(tmp_path, monkeypatch):
    result, root, meta = scan(tmp_path, monkeypatch, PDF_TEXT_RESULTS_THEN_SCANS)
    assert meta["course_page"] is None and not (root / "course.png").exists()
    assert meta["blocks"] == [f"p2-b{i}" for i in range(1, 7)] + [f"p3-b{i}" for i in range(1, 7)]
    assert "no typed course and no course page found" in result.note


def test_a_typed_course_has_no_course_page(tmp_path, monkeypatch):
    from tests.fixtures import PDF_TEXT

    _, root, meta = scan(tmp_path, monkeypatch, PDF_TEXT)
    assert meta["course_page"] is None and meta["results_page"] is None and not (root / "course.png").exists()


class Course:
    """Answers the course prompt from `replies`, one per attempt (the last repeats)."""

    def __init__(self, *replies):
        self.replies = replies
        self.calls: list[tuple[str, float, int]] = []

    def ask(self, _image, prompt, temperature, attempt=0):
        self.calls.append((prompt, temperature, attempt))
        value = self.replies[min(len(self.calls) - 1, len(self.replies) - 1)]
        if isinstance(value, Exception):
            raise value
        return value if isinstance(value, str) else json.dumps(value)


def image_course_root(tmp_path, **extra):
    root = tmp_path / "out" / "sundays" / "2026-05-31"
    root.mkdir(parents=True)
    Image.new("RGB", (10, 10), "white").save(root / "course.png")
    meta = {"date": "2026-05-31", "layout": [], "officials": [], "blocks": [], "course_page": 2, **extra}
    (root / "sunday.json").write_text(json.dumps(meta))
    return root


def meta_of(root):
    return json.loads((root / "sunday.json").read_text())


def test_a_valid_course_reply_is_stored_in_course_order(tmp_path):
    root = image_course_root(tmp_path)
    client = Course(GOOD)
    assert pipeline.read_course(root, client) is True  # type: ignore[arg-type]
    meta = meta_of(root)
    assert meta["layout"] == [[1, 10], [2, 15], [3, 25]] and meta["course_source"] == "image"
    assert "course_unreadable" not in meta
    assert client.calls[0][1:] == (pipeline.FIRST_TEMPERATURE, 0)
    assert "stations" in client.calls[0][0] and "targets" in client.calls[0][0]


def test_a_bad_reply_is_retried_up_to_three_times_then_the_sunday_is_unreadable(tmp_path):
    root = image_course_root(tmp_path)
    total_49 = {"stations": [{"stn": 1, "targets": 24}, {"stn": 2, "targets": 25}]}
    client = Course(total_49, "garbage", total_49, GOOD)
    assert pipeline.read_course(root, client) is False  # type: ignore[arg-type]
    assert len(client.calls) == pipeline.COURSE_TRIES == 3
    assert [c[1:] for c in client.calls] == [(0.2, 0), (0.8, 1), (0.8, 2)]
    meta = meta_of(root)
    assert meta["course_unreadable"] is True and meta["layout"] == []


def test_a_retry_that_passes_stops_and_clears_an_earlier_unreadable_mark(tmp_path):
    root = image_course_root(tmp_path, course_unreadable=True)
    client = Course("garbage", GOOD)
    assert pipeline.read_course(root, client) is True  # type: ignore[arg-type]
    assert len(client.calls) == 2
    assert "course_unreadable" not in meta_of(root)


@pytest.mark.parametrize(
    "reply",
    [
        {"stations": [{"stn": 1, "targets": 25}, {"stn": 1, "targets": 25}]},  # station repeated
        {"stations": [{"stn": "7A", "targets": 25}, {"stn": "7a", "targets": 25}]},  # the same label twice
        {"stations": [{"stn": "7AB", "targets": 25}, {"stn": 2, "targets": 25}]},  # not a label
        {"stations": [{"stn": "seven", "targets": 25}, {"stn": 2, "targets": 25}]},
        {"stations": [{"stn": 7.5, "targets": 25}, {"stn": 2, "targets": 25}]},
        {"stations": [{"stn": True, "targets": 25}, {"stn": 2, "targets": 25}]},
        {"stations": [{"stn": 0, "targets": 25}, {"stn": 2, "targets": 25}]},
        {"stations": [{"stn": 1, "targets": 25.5}, {"stn": 2, "targets": 24.5}]},
        {"stations": [{"stn": 1, "targets": 0}, {"stn": 2, "targets": 50}]},  # a station with no targets
        {"stations": [{"stn": 1}, {"stn": 2, "targets": 50}]},
        {"stations": ["x"]},
        {"stations": []},
        {"stations": "none"},
        {"nothing": 1},
        [],
    ],
)
def test_course_replies_that_break_the_rules_are_refused(tmp_path, reply):
    root = image_course_root(tmp_path)
    assert pipeline.read_course(root, Course(reply)) is False  # type: ignore[arg-type]


def test_a_failed_request_counts_as_a_try_and_unreachable_stops_the_run(tmp_path):
    root = image_course_root(tmp_path)
    client = Course(VlmError("boom"), GOOD)
    assert pipeline.read_course(root, client) is True  # type: ignore[arg-type]
    with pytest.raises(VlmUnreachable):
        pipeline.read_course(image_course_root(tmp_path / "x"), Course(VlmUnreachable("down")))  # type: ignore[arg-type]


def test_string_numbers_are_accepted(tmp_path):
    root = image_course_root(tmp_path)
    reply = {"stations": [{"stn": "1", "targets": "20"}, {"stn": 2, "targets": 30}]}
    assert pipeline.read_course(root, Course(reply)) is True  # type: ignore[arg-type]
    assert meta_of(root)["layout"] == [[1, 20], [2, 30]]


def test_a_lettered_station_is_kept_as_its_own_station_in_course_order(tmp_path):
    root = image_course_root(tmp_path)
    reply = {"stations": [{"stn": 6, "targets": 10}, {"stn": "7", "targets": 10}, {"stn": " 7a ", "targets": 30}]}
    assert pipeline.read_course(root, Course(reply)) is True  # type: ignore[arg-type]
    assert meta_of(root)["layout"] == [[6, 10], [7, 10], ["7A", 30]]


def test_the_course_prompt_allows_a_letter_on_a_station(tmp_path):
    root = image_course_root(tmp_path)
    client = Course(GOOD)
    pipeline.read_course(root, client)  # type: ignore[arg-type]
    assert "7A" in client.calls[0][0]


def test_course_needed(tmp_path):
    root = image_course_root(tmp_path)
    assert pipeline.course_needed(root) is True
    assert pipeline.course_needed(image_course_root(tmp_path / "y", layout=[[1, 50]])) is False
    (image_course_root(tmp_path / "z") / "course.png").unlink()
    assert pipeline.course_needed(tmp_path / "z" / "out" / "sundays" / "2026-05-31") is False
