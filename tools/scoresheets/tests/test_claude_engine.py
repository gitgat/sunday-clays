"""The Claude engine: every test fakes `claude_engine.run_claude`; nothing runs the real CLI or a model server."""

import base64
import io
import json
import subprocess
from types import SimpleNamespace

import pytest
from PIL import Image

import checks
import claude_engine
import pipeline
from claude_engine import ClaudeClient, ClaudeError, ClaudeUnavailable, ScanOutdated
from vlm import VlmClient, VlmError, VlmUnreachable

OFFICIALS = [
    {"name": "Testerson, Ann", "hits": 22},
    {"name": "Fakeman, Bo", "hits": 21},
    {"name": "Mockley, Cy", "hits": 20},
]
META = {"date": "2026-05-31", "layout": [[2, 7], [4, 7], [7, 8]], "officials": OFFICIALS}


def envelope(text, cost=0.02, **extra):
    """The stream-json output: a few event lines, then the result line."""
    events = [{"type": "system", "subtype": "init", "tools": []}, {"type": "assistant", "message": {}}]
    result = {"type": "result", "is_error": False, "result": text, "total_cost_usd": cost, **extra}
    return "\n".join(json.dumps(item) for item in [*events, result]) + "\n"


def result_line(**fields):
    return json.dumps({"type": "result", **fields})


def sent_image(stdin):
    """The picture inside the one stream-json message a call sent."""
    (line,) = stdin.splitlines()
    content = json.loads(line)["message"]["content"]
    return Image.open(io.BytesIO(base64.b64decode(content[0]["source"]["data"]))).convert("RGB")


def done(stdout="", returncode=0, stderr=""):
    return SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)


def stations(values):
    return [{"stn": stn, "tot": tot} for stn, tot in zip((2, 4, 7), values, strict=False)]


def block(slot, name, values, total=None):
    return {
        "slot": slot,
        "name": name,
        "stations": stations(values),
        "malf": "",
        "event_total": sum(values) if total is None else total,
    }


def page(*blocks):
    return json.dumps({"blocks": list(blocks)})


class Runner:
    """A fake `run_claude`: replies come from a list (the last one repeats) or a function of the command."""

    def __init__(self, *replies):
        self.replies = list(replies)
        self.commands: list[list[str]] = []
        self.timeouts: list[float] = []
        self.inputs: list[str] = []
        self.cwds: list = []

    def __call__(self, cmd, timeout, stdin, cwd):
        self.commands.append(cmd)
        self.timeouts.append(timeout)
        self.inputs.append(stdin)
        self.cwds.append((cwd, cwd.is_dir(), list(cwd.iterdir())))
        reply = self.replies[min(len(self.commands) - 1, len(self.replies) - 1)]
        if callable(reply):
            reply = reply(cmd, stdin)
        if isinstance(reply, Exception):
            raise reply
        return reply


@pytest.fixture
def fake(monkeypatch):
    def install(*replies):
        runner = Runner(*replies)
        monkeypatch.setattr(claude_engine, "run_claude", runner)
        return runner

    return install


def img(color="white"):
    return Image.new("RGB", (8, 8), color)


# --- the CLI call and its JSON envelope ---------------------------------------------------------------------------


def test_the_command_is_the_briefed_no_tools_opus_call(tmp_path, fake, monkeypatch):
    monkeypatch.delenv("CLAUDE_BIN", raising=False)
    runner = fake(done(envelope("hello")))
    client = ClaudeClient(tmp_path / "cache")
    assert client.model == "opus" and client.ask(img(), "Do the thing.", 0.2) == "hello"
    (cmd,) = runner.commands
    assert cmd == [
        "claude",
        "-p",
        "--model",
        "opus",
        "--input-format",
        "stream-json",
        "--output-format",
        "stream-json",
        "--verbose",
        "--tools",
        "",
        "--strict-mcp-config",
        "--mcp-config",
        '{"mcpServers":{}}',
        "--setting-sources",
        "",
        "--system-prompt",
        "You transcribe handwritten clay-shooting scoresheets into JSON exactly as written.",
    ]
    assert runner.timeouts == [300]
    assert "Read" not in cmd and "--allowedTools" not in cmd


def test_the_image_goes_inline_as_one_stream_json_line_and_no_path_is_sent(tmp_path, fake):
    runner = fake(done(envelope("hello")))
    ClaudeClient(tmp_path / "cache").ask(img("red"), "Do the thing.", 0.2)
    (stdin,) = runner.inputs
    assert stdin.endswith("\n") and len(stdin.splitlines()) == 1
    message = json.loads(stdin)
    assert message["type"] == "user" and message["message"]["role"] == "user"
    image, text = message["message"]["content"]
    assert image["type"] == "image" and image["source"]["type"] == "base64"
    assert image["source"]["media_type"] == "image/png"
    assert text == {"type": "text", "text": "Do the thing."}
    assert sent_image(stdin).getpixel((0, 0)) == (255, 0, 0)
    assert ".png" not in stdin.replace(image["source"]["data"], "")  # no file path for the model to open
    assert not (tmp_path / "cache" / "images").exists()


def test_the_call_runs_in_an_empty_temp_folder_that_is_removed_afterwards(tmp_path, fake):
    runner = fake(done(envelope("x")))
    ClaudeClient(tmp_path / "cache").ask(img(), "p", 0.2)
    ((cwd, was_dir, contents),) = runner.cwds
    assert was_dir and contents == [] and not cwd.exists()
    assert not str(cwd).startswith(str(tmp_path))


def test_the_binary_is_configurable_with_claude_bin(tmp_path, fake, monkeypatch):
    monkeypatch.setenv("CLAUDE_BIN", "/opt/bin/claude")
    runner = fake(done(envelope("x")))
    ClaudeClient(tmp_path).ask(img(), "p", 0.2)
    assert runner.commands[0][0] == "/opt/bin/claude"


def test_a_repeat_is_served_from_disk_and_a_new_attempt_image_or_model_is_not(tmp_path, fake):
    runner = fake(done(envelope("one", cost=0.5)))
    client = ClaudeClient(tmp_path / "cache", model="opus")
    assert client.ask(img(), "p", 0.2) == "one"
    assert client.ask(img(), "p", 0.9) == "one"  # temperature is not part of the key
    assert len(runner.commands) == 1
    client.ask(img(), "p", 0.2, attempt=1)
    client.ask(img("black"), "p", 0.2)
    client.ask(img(), "other prompt", 0.2)
    ClaudeClient(tmp_path / "cache", model="sonnet").ask(img(), "p", 0.2)
    assert len(runner.commands) == 5
    assert (client.calls, client.cached, round(client.cost, 2)) == (4, 1, 2.0)
    ClaudeClient(tmp_path / "cache", model="opus").ask(img(), "p", 0.2)  # a fresh client resumes for free
    assert len(runner.commands) == 5


def test_a_torn_cache_entry_is_asked_again(tmp_path, fake):
    runner = fake(done(envelope("fresh")))
    client = ClaudeClient(tmp_path)
    client.ask(img(), "p", 0.2)
    for entry in tmp_path.glob("*.json"):
        entry.write_text("{torn")
    assert client.ask(img(), "p", 0.2) == "fresh"
    assert len(runner.commands) == 2


@pytest.mark.parametrize(
    ("reply", "error", "text"),
    [
        (done("not json\n\n"), ClaudeError, "no result line"),
        (done(json.dumps({"type": "assistant"})), ClaudeError, "no result line"),
        (done("[1]"), ClaudeError, "no result line"),
        (done(result_line(is_error=False)), ClaudeError, "no result text"),
        (done(result_line(is_error=False, result=5)), ClaudeError, "no result text"),
        (done(result_line(is_error=True, result="Overloaded")), ClaudeError, "Overloaded"),
        (
            done(result_line(is_error=True, result="Not logged in - Please run /login")),
            ClaudeUnavailable,
            "login",
        ),
        (done("", returncode=1, stderr="boom\n"), ClaudeError, "exited 1: boom"),
        (subprocess.TimeoutExpired(["claude"], 300), ClaudeError, "took too long"),
        (FileNotFoundError("claude"), ClaudeUnavailable, "cannot run claude"),
    ],
)
def test_bad_calls_raise(tmp_path, fake, reply, error, text):
    fake(reply)
    with pytest.raises(error, match=text):
        ClaudeClient(tmp_path).ask(img(), "p", 0.2)


def test_a_failed_call_is_not_cached(tmp_path, fake):
    runner = fake(done("not json"), done(envelope("ok")))
    client = ClaudeClient(tmp_path)
    with pytest.raises(ClaudeError):
        client.ask(img(), "p", 0.2)
    assert client.ask(img(), "p", 0.2) == "ok"
    assert len(runner.commands) == 2


def test_a_missing_or_odd_cost_counts_as_zero(tmp_path, fake):
    fake(done(result_line(is_error=False, result="x", total_cost_usd="cheap")))
    client = ClaudeClient(tmp_path)
    client.ask(img(), "p", 0.2)
    assert client.cost == 0.0


def test_the_result_line_wins_over_earlier_events_and_junk(tmp_path, fake):
    noisy = (
        "warming up\n" + envelope("first", cost=0.1) + result_line(is_error=False, result="last", total_cost_usd=0.3)
    )
    fake(done(noisy))
    client = ClaudeClient(tmp_path)
    assert client.ask(img(), "p", 0.2) == "last" and round(client.cost, 2) == 0.3


def test_the_cache_entry_records_the_cost_of_the_call(tmp_path, fake):
    fake(done(envelope("hi", cost=0.06)))
    ClaudeClient(tmp_path).ask(img(), "p", 0.2)
    (entry,) = tmp_path.glob("*.json")
    assert json.loads(entry.read_text()) == {"content": "hi", "cost": 0.06}


def test_the_real_runner_uses_subprocess_with_input_a_timeout_and_a_folder(monkeypatch, tmp_path):
    seen = {}

    def fake_run(cmd, **kwargs):
        seen.update(cmd=cmd, **kwargs)
        return done("out")

    monkeypatch.setattr(claude_engine.subprocess, "run", fake_run)
    assert claude_engine.run_claude(["claude", "-p"], 12, "in", tmp_path).stdout == "out"
    assert seen == {
        "cmd": ["claude", "-p"],
        "input": "in",
        "capture_output": True,
        "text": True,
        "timeout": 12,
        "cwd": tmp_path,
    }


# --- the page reply ------------------------------------------------------------------------------------------------


def test_a_page_reply_maps_slots_and_tolerates_fences():
    text = "```json\n" + page(block(1, "Ann Testerson", [7, 7, 8]), block(4, "Bo Fakeman", [7, 7, 3])) + "\n```"
    found = claude_engine.parse_page(text)
    assert found is not None and sorted(found) == [1, 4]
    assert found[1] == {
        "name_read": "Ann Testerson",
        "tots": [7, 7, 8],
        "stns": [2, 4, 7],
        "event_total": 22,
        "malf": "",
    }
    assert found[4]["tots"] == [7, 7, 3]


def test_a_page_of_blank_slots_is_valid_and_empty():
    assert claude_engine.parse_page('{"blocks": []}') == {}


def test_a_slot_with_nothing_written_is_blank():
    found = claude_engine.parse_page(page({"slot": 3, "name": "", "stations": [], "malf": "", "event_total": None}))
    assert found == {3: None}


def test_station_numbers_are_coerced():
    item = {"slot": 2, "name": " Bo ", "stations": [{"tot": "7"}, {"tot": None}, {"tot": True}, "x", {}], "malf": None}
    found = claude_engine.parse_page(page(item))
    assert found is not None
    assert found[2] == {
        "name_read": "Bo",
        "tots": [7, None, None, None, None],
        "stns": [None] * 5,
        "event_total": None,
        "malf": "",
    }
    odd = claude_engine.parse_page(page({"slot": 2, "name": "Bo", "stations": "none", "event_total": "21"}))
    assert odd is not None and odd[2]["tots"] == [] and odd[2]["event_total"] == 21


@pytest.mark.parametrize(
    "text",
    [
        "no json at all",
        "[1]",
        '{"blocks": "x"}',
        '{"other": []}',
        '{"blocks": ["x"]}',
        '{"blocks": [{"slot": 0, "name": "A"}]}',
        '{"blocks": [{"slot": 7, "name": "A"}]}',
        '{"blocks": [{"slot": "x", "name": "A"}]}',
        '{"blocks": [{"slot": 1, "name": "A"}, {"slot": 1, "name": "B"}]}',
    ],
)
def test_malformed_page_replies_are_rejected(text):
    assert claude_engine.parse_page(text) is None


def test_the_prompt_names_the_slot_order_and_never_asks_to_reconcile():
    prompt = claude_engine.PAGE_PROMPT
    assert "left to right" in prompt and "top to bottom" in prompt
    assert "Do not correct or reconcile" in prompt and '"blocks"' in prompt


# --- one page: retry once, then engine_error ---------------------------------------------------------------------


def test_an_invalid_first_reply_is_retried_once(tmp_path, fake):
    runner = fake(done(envelope("garbage")), done(envelope(page(block(1, "Ann", [7, 7, 8])))))
    parsed, tries, error = claude_engine.read_page(ClaudeClient(tmp_path), img())
    assert parsed is not None and tries == 2 and error == ""
    assert len(runner.commands) == 2


def test_a_failed_call_is_retried_and_two_failures_give_up(tmp_path, fake):
    fake(done("", returncode=1, stderr="boom"))
    parsed, tries, error = claude_engine.read_page(ClaudeClient(tmp_path), img())
    assert (parsed, tries) == (None, 2) and "exited 1" in error
    fake(done(envelope("still garbage")))
    parsed, tries, error = claude_engine.read_page(ClaudeClient(tmp_path / "b"), img())
    assert parsed is None and "expected JSON" in error


def test_claude_being_unavailable_is_not_retried(tmp_path, fake):
    runner = fake(FileNotFoundError("claude"))
    with pytest.raises(ClaudeUnavailable):
        claude_engine.read_page(ClaudeClient(tmp_path), img())
    assert len(runner.commands) == 1


# --- a whole Sunday through read_sunday ---------------------------------------------------------------------------


def sunday_with_pages(tmp_path, pages=(3,), sha="sha-1"):
    root = tmp_path / "sundays" / "2026-05-31"
    (root / "blocks").mkdir(parents=True)
    (root / "pages").mkdir()
    ids = []
    for number in pages:
        img().save(root / "pages" / f"p{number}.png")
        for slot in range(1, 7):
            ids.append(f"p{number}-b{slot}")
            for suffix in ("", "-tot"):
                img().save(root / "blocks" / f"p{number}-b{slot}{suffix}.png")
    (root / "sunday.json").write_text(json.dumps({**META, "sha256": sha, "blocks": ids}))
    return root


def read(root, client, gemma=None, jobs=1, log=lambda _m: None):
    return pipeline.read_sunday(
        root,
        client,
        jobs=jobs,
        log=log,
        reader=claude_engine.page_reader(client),
        refine=claude_engine.second_opinion(gemma, root),
    )


def readings_of(root):
    return {r["id"]: r for r in json.loads((root / "readings.json").read_text())}


def test_slots_map_to_block_ids_and_blank_slots_are_blank_blocks(tmp_path, fake):
    root = sunday_with_pages(tmp_path)
    reply = page(
        block(1, "Ann Testerson", [7, 7, 8]), block(2, "Bo Fakeman", [7, 7, 7]), block(6, "Cy Mockley", [7, 6, 6])
    )
    fake(done(envelope(reply)))
    counts = read(root, ClaudeClient(tmp_path / "cache"))
    assert counts == {"ok": 2, "review": 1, "skipped": 3, "kept": 0, "stale": 0}
    found = readings_of(root)
    assert list(found) == ["p3-b1", "p3-b2", "p3-b6"]  # slot 1..6 = block ids p3-b1..p3-b6, in crop order
    assert found["p3-b2"]["name_read"] == "Bo Fakeman" and (found["p3-b2"]["page"], found["p3-b2"]["block"]) == (3, 2)
    assert found["p3-b6"]["matched"] == "Mockley, Cy" and found["p3-b6"]["reasons"] == [checks.SHEET_VS_OFFICIAL]
    assert found["p3-b1"]["source"] == "claude" and found["p3-b1"]["tries"] == 1


def test_the_checks_apply_unchanged_to_a_claude_reading(tmp_path, fake):
    root = sunday_with_pages(tmp_path)
    fake(done(envelope(page(block(1, "Ann Testerson", [7, 7, 8], total=99), block(2, "Zed Nobody", [1, 1, 1])))))
    read(root, ClaudeClient(tmp_path / "cache"))
    found = readings_of(root)
    assert found["p3-b1"]["reasons"] == [checks.SUM_VS_EVENT_TOTAL]
    assert found["p3-b2"]["reasons"] == [checks.NO_OFFICIAL_MATCH]


def test_a_page_that_never_reads_flags_all_its_blocks_engine_error(tmp_path, fake):
    root = sunday_with_pages(tmp_path)
    fake(done("", returncode=1, stderr="boom"))
    counts = read(root, ClaudeClient(tmp_path / "cache"))
    assert counts["review"] == 6 and counts["ok"] == 0
    first = readings_of(root)["p3-b1"]
    assert first["reasons"] == [checks.ENGINE_ERROR] and first["status"] == "review" and first["tries"] == 2
    assert "error" not in first and "error_reason" not in first and first["source"] == "claude"


@pytest.mark.parametrize("jobs", [1, 4])
def test_pages_read_in_parallel_keep_block_order_and_the_same_result(tmp_path, fake, jobs):
    root = sunday_with_pages(tmp_path, pages=(3, 4, 5))

    def same_for_every_page(_cmd, _stdin):
        return done(envelope(page(block(1, "Ann Testerson", [7, 7, 8]))))

    runner = fake(same_for_every_page)
    messages: list[str] = []
    counts = read(root, ClaudeClient(tmp_path / "cache"), jobs=jobs, log=messages.append)
    # the same image for all three pages is one cache entry; the answer is the same sheet each time
    assert counts["ok"] + counts["review"] == 3 and counts["skipped"] == 15
    assert list(readings_of(root)) == ["p3-b1", "p4-b1", "p5-b1"]
    assert len(messages) == 3 and 1 <= len(runner.commands) <= 3


def test_different_pages_get_their_own_replies_in_order(tmp_path, fake):
    root = sunday_with_pages(tmp_path, pages=(3, 4))
    Image.new("RGB", (8, 8), "black").save(root / "pages" / "p4.png")

    def by_colour(_cmd, stdin):
        black = sent_image(stdin).getpixel((0, 0)) == (0, 0, 0)
        return done(envelope(page(block(2, "Bo Fakeman" if black else "Ann Testerson", [7, 7, 8]))))

    fake(by_colour)
    read(root, ClaudeClient(tmp_path / "cache"), jobs=2)
    found = readings_of(root)
    assert found["p3-b2"]["name_read"] == "Ann Testerson" and found["p4-b2"]["name_read"] == "Bo Fakeman"


def test_a_rerun_is_free_and_decisions_are_kept(tmp_path, fake):
    root = sunday_with_pages(tmp_path)
    runner = fake(done(envelope(page(block(1, "Ann Testerson", [7, 7, 8]), block(2, "Bo Fakeman", [7, 7, 3])))))
    client = ClaudeClient(tmp_path / "cache")
    read(root, client)
    decided = json.loads((root / "readings.json").read_text())
    decided[1].update(status="accepted", tots=[7, 7, 7], sum=21)
    (root / "readings.json").write_text(json.dumps(decided))
    counts = read(root, client)
    assert counts["kept"] == 1 and 1 <= len(runner.commands) <= 3
    assert readings_of(root)["p3-b2"]["status"] == "accepted"


def test_a_kept_page_is_not_asked_for_again(tmp_path, fake):
    root = sunday_with_pages(tmp_path)
    runner = fake(done(envelope(page(block(1, "Ann Testerson", [7, 7, 8])))))
    read(root, ClaudeClient(tmp_path / "cache"))
    decided = json.loads((root / "readings.json").read_text())
    decided[0]["status"] = "skipped"
    (root / "readings.json").write_text(json.dumps(decided))
    runner.commands.clear()
    (root / "sunday.json").write_text(json.dumps({**META, "sha256": "sha-1", "blocks": ["p3-b1"]}))
    read(root, ClaudeClient(tmp_path / "cache2"))
    assert runner.commands == []  # every block of the page was decided: nothing to read


def test_a_scan_without_page_images_asks_for_a_new_scan(tmp_path, fake):
    root = sunday_with_pages(tmp_path)
    (root / "pages" / "p3.png").unlink()
    runner = fake(done(envelope("{}")))
    with pytest.raises(ScanOutdated, match="scan"):
        read(root, ClaudeClient(tmp_path / "cache"))
    assert runner.commands == []


# --- second opinion from a cached Gemma reading ------------------------------------------------------------------


class Gemma:
    """A cached Gemma reading for every block: replies by block name, like a cache holding its answers."""

    def __init__(self, whole_name="Ann Testerson", tots=(7, 7, 8), total=22, fail=False):
        self.name, self.tots, self.total, self.fail = whole_name, list(tots), total, fail

    def ask(self, _image, prompt, _temperature, attempt=0):
        if self.fail:
            raise VlmError("not in the cache")
        if "Tot column" in prompt:
            return json.dumps({"tots": self.tots, "event_total": self.total})
        return json.dumps({"name": self.name, "malf": "", "event_total": self.total})


def one_block(tmp_path, fake, claude_tots, total=None, name="Ann Testerson"):
    root = sunday_with_pages(tmp_path)
    fake(done(envelope(page(block(1, name, claude_tots, total)))))
    return root


def test_gemma_is_adopted_when_claude_fails_gemma_passes_and_the_event_totals_agree(tmp_path, fake):
    root = one_block(tmp_path, fake, [7, 1, 8], total=22)  # claude: sum 16 vs written 22 -> sum_vs_event_total
    read(root, ClaudeClient(tmp_path / "c"), Gemma())
    record = readings_of(root)["p3-b1"]
    assert (record["status"], record["reasons"], record["source"]) == ("ok", [], "gemma_second_opinion")
    assert record["tots"] == [7, 7, 8] and record["event_total"] == 22 and record["sum"] == 22
    assert record["claude"] == {"tots": [7, 1, 8], "event_total": 22}


def test_gemma_is_declined_when_the_event_totals_differ(tmp_path, fake):
    root = one_block(tmp_path, fake, [7, 1, 8], total=23)
    read(root, ClaudeClient(tmp_path / "c"), Gemma())
    record = readings_of(root)["p3-b1"]
    assert record["status"] == "review" and record["source"] == "claude"
    assert record["tots"] == [7, 1, 8] and record["gemma"] == {"tots": [7, 7, 8], "event_total": 22}


def test_gemma_is_declined_when_it_fails_the_checks_too(tmp_path, fake):
    root = one_block(tmp_path, fake, [7, 1, 8], total=22)
    read(root, ClaudeClient(tmp_path / "c"), Gemma(tots=(7, 7, 7), total=22))
    record = readings_of(root)["p3-b1"]
    assert record["status"] == "review" and record["source"] == "claude"


def test_gemma_cannot_rescue_an_unmatched_name_or_a_missing_event_total(tmp_path, fake):
    root = one_block(tmp_path, fake, [7, 7, 8], name="Zed Nobody")
    read(root, ClaudeClient(tmp_path / "c"), Gemma())
    assert readings_of(root)["p3-b1"]["reasons"] == [checks.NO_OFFICIAL_MATCH]
    root = sunday_with_pages(tmp_path / "x")
    item = block(1, "Ann Testerson", [7, 1, 8])
    item["event_total"] = None
    fake(done(envelope(page(item))))
    read(root, ClaudeClient(tmp_path / "c2"), Gemma())
    record = readings_of(root)["p3-b1"]
    assert record["status"] == "review" and record["source"] == "claude"


def test_both_passing_and_disagreeing_on_a_station_goes_to_review(tmp_path, fake):
    root = one_block(tmp_path, fake, [7, 7, 7], name="Bo Fakeman")
    read(root, ClaudeClient(tmp_path / "c"), Gemma(whole_name="Bo Fakeman", tots=(7, 6, 8), total=21))
    record = readings_of(root)["p3-b1"]
    assert (record["status"], record["reasons"]) == ("review", [checks.ENGINES_DISAGREE])
    assert record["tots"] == [7, 7, 7] and record["gemma"] == {"tots": [7, 6, 8], "event_total": 21}
    assert record["source"] == "claude"


def test_both_passing_and_agreeing_stays_ok(tmp_path, fake):
    root = one_block(tmp_path, fake, [7, 7, 8])
    read(root, ClaudeClient(tmp_path / "c"), Gemma())
    record = readings_of(root)["p3-b1"]
    assert record["status"] == "ok" and "gemma" not in record


def test_no_cached_gemma_reading_changes_nothing(tmp_path, fake):
    root = one_block(tmp_path, fake, [7, 7, 8])
    read(root, ClaudeClient(tmp_path / "c"), Gemma(fail=True))
    assert readings_of(root)["p3-b1"]["status"] == "ok"
    root = one_block(tmp_path / "y", fake, [7, 1, 8], total=22)
    read(root, ClaudeClient(tmp_path / "c2"), None)  # no Gemma cache at all
    assert readings_of(root)["p3-b1"]["status"] == "review"


def test_a_blank_gemma_block_and_an_engine_error_are_left_alone(tmp_path, fake):
    root = one_block(tmp_path, fake, [7, 1, 8], total=22)
    blank = Gemma(whole_name="")
    blank.tots, blank.total = [], None
    read(root, ClaudeClient(tmp_path / "c"), blank)
    assert readings_of(root)["p3-b1"]["status"] == "review"
    root = sunday_with_pages(tmp_path / "z")
    fake(done("", returncode=1))
    read(root, ClaudeClient(tmp_path / "c3"), Gemma())
    assert readings_of(root)["p3-b1"]["reasons"] == [checks.ENGINE_ERROR]


def test_an_unreachable_gemma_client_is_never_called_over_the_network(tmp_path):
    cache = tmp_path / "cache"
    client = VlmClient(cache, offline=True)
    with pytest.raises(VlmError, match="cache"):
        client.ask(img(), "p", 0.2)
    with pytest.raises(VlmUnreachable):
        raise VlmUnreachable("x")  # the offline error is the ordinary kind: the block is just skipped
    online = VlmClient(cache)
    assert online.http is not None
    client.close()
    online.close()


def test_an_offline_client_serves_what_is_cached(tmp_path, monkeypatch):
    import vlm

    cache = tmp_path / "cache"
    png = vlm.image_png(img())
    path = cache / f"{vlm.cache_key(png, 'p', vlm.DEFAULT_MODEL, 0.2, 0)}.json"
    cache.mkdir()
    path.write_text(json.dumps({"content": "cached"}))
    monkeypatch.delenv("VLM_MODEL", raising=False)
    assert VlmClient(cache, offline=True).ask(img(), "p", 0.2) == "cached"


# --- the course picture -------------------------------------------------------------------------------------------


COURSE_GOOD = {"stations": [{"stn": 1, "targets": 20}, {"stn": 2, "targets": 30}]}


def course_root(tmp_path):
    root = tmp_path / "sundays" / "2026-05-31"
    root.mkdir(parents=True)
    (root / "sunday.json").write_text(json.dumps({**META, "layout": [], "blocks": []}))
    img().save(root / "course.png")
    return root


def test_the_course_picture_is_read_with_the_same_acceptance_rules(tmp_path, fake):
    root = course_root(tmp_path)
    runner = fake(done(envelope(json.dumps(COURSE_GOOD))))
    assert pipeline.read_course(root, ClaudeClient(tmp_path / "c")) is True  # type: ignore[arg-type]
    meta = json.loads((root / "sunday.json").read_text())
    assert meta["layout"] == [[1, 20], [2, 30]] and meta["course_source"] == "image"
    assert len(runner.commands) == 1 and "Tgts column" in json.loads(runner.inputs[0])["message"]["content"][1]["text"]


def test_a_bad_course_reply_is_asked_again_as_a_new_attempt(tmp_path, fake):
    root = course_root(tmp_path)
    bad = {"stations": [{"stn": 1, "targets": 20}]}
    runner = fake(done(envelope(json.dumps(bad))), done(envelope(json.dumps(COURSE_GOOD))))
    assert pipeline.read_course(root, ClaudeClient(tmp_path / "c")) is True  # type: ignore[arg-type]
    assert len(runner.commands) == 2
    runner = fake(done(envelope(json.dumps(bad))))
    assert pipeline.read_course(root, ClaudeClient(tmp_path / "d")) is False  # type: ignore[arg-type]
    assert len(runner.commands) == pipeline.COURSE_TRIES
    assert json.loads((root / "sunday.json").read_text())["course_unreadable"] is True


def test_a_failed_course_call_counts_as_a_try_and_claude_missing_stops_the_run(tmp_path, fake):
    root = course_root(tmp_path)
    fake(done("", returncode=1), done(envelope(json.dumps(COURSE_GOOD))))
    assert pipeline.read_course(root, ClaudeClient(tmp_path / "c")) is True  # type: ignore[arg-type]
    fake(FileNotFoundError("claude"))
    with pytest.raises(ClaudeUnavailable):
        pipeline.read_course(root, ClaudeClient(tmp_path / "d"))  # type: ignore[arg-type]


# --- fix round 1 ---------------------------------------------------------------------------------------------------


def test_a_login_error_wins_over_a_non_zero_exit(tmp_path, fake):
    login = result_line(is_error=True, result="Not logged in - Please run /login")
    fake(done(login, returncode=1))
    with pytest.raises(ClaudeUnavailable, match="login"):
        ClaudeClient(tmp_path).ask(img(), "p", 0.2)


def test_an_other_error_result_with_a_non_zero_exit_is_an_ordinary_failure(tmp_path, fake):
    fake(done(result_line(is_error=True, result="Overloaded"), returncode=1, stderr="bad\n"))
    with pytest.raises(ClaudeError, match="exited 1: bad"):
        ClaudeClient(tmp_path).ask(img(), "p", 0.2)


def test_a_good_result_line_is_used_even_when_the_exit_code_is_non_zero(tmp_path, fake):
    fake(done(envelope("fine"), returncode=1))
    assert ClaudeClient(tmp_path).ask(img(), "p", 0.2) == "fine"


def test_a_reply_that_is_not_page_json_is_not_kept_in_the_cache(tmp_path, fake):
    runner = fake(done(envelope("garbage")))
    client = ClaudeClient(tmp_path)
    assert claude_engine.read_page(client, img())[0] is None
    assert list(tmp_path.glob("*.json")) == []
    assert claude_engine.read_page(client, img())[0] is None  # a rerun asks again instead of replaying the junk
    assert len(runner.commands) == 4


def test_a_good_page_reply_stays_cached(tmp_path, fake):
    runner = fake(done(envelope(page(block(1, "Ann", [7, 7, 8])))))
    client = ClaudeClient(tmp_path)
    claude_engine.read_page(client, img())
    claude_engine.read_page(client, img())
    assert len(runner.commands) == 1 and len(list(tmp_path.glob("*.json"))) == 1


def test_discarding_an_entry_that_is_not_there_is_fine(tmp_path):
    ClaudeClient(tmp_path).discard(img(), "p", 0)


def test_the_stations_read_are_kept_for_the_check_against_the_course():
    found = claude_engine.parse_page(page(block(1, "Ann", [7, 7, 8])))
    assert found is not None and found[1]["stns"] == [2, 4, 7]


def test_a_station_list_that_does_not_match_the_course_goes_to_review(tmp_path, fake):
    root = sunday_with_pages(tmp_path)
    skipped = block(1, "Ann Testerson", [7, 8, 7])
    skipped["stations"] = [{"stn": 2, "tot": 7}, {"stn": 7, "tot": 8}, {"stn": 4, "tot": 7}]  # 4 and 7 swapped
    fake(done(envelope(page(skipped, block(2, "Bo Fakeman", [7, 7, 7])))))
    read(root, ClaudeClient(tmp_path / "cache"))
    found = readings_of(root)
    assert found["p3-b1"]["reasons"] == [checks.STATION_MISMATCH] and found["p3-b1"]["status"] == "review"
    assert found["p3-b1"]["tots"] == [7, 8, 7]
    assert found["p3-b2"]["status"] == "ok"


def test_a_lettered_station_is_read_as_its_own_label(tmp_path, fake):
    root = sunday_with_pages(tmp_path)
    meta = json.loads((root / "sunday.json").read_text())
    meta["layout"] = [[2, 7], [4, 7], ["7A", 8]]
    (root / "sunday.json").write_text(json.dumps(meta))
    item = block(1, "Ann Testerson", [7, 7, 8])
    item["stations"] = [{"stn": "2", "tot": 7}, {"stn": 4, "tot": 7}, {"stn": " 7a", "tot": 8}]
    wrong = block(2, "Bo Fakeman", [7, 7, 7])
    wrong["stations"] = [{"stn": 2, "tot": 7}, {"stn": 4, "tot": 7}, {"stn": 7, "tot": 7}]  # 7 is not 7A
    fake(done(envelope(page(item, wrong))))
    read(root, ClaudeClient(tmp_path / "cache"))
    found = readings_of(root)
    assert found["p3-b1"]["status"] == "ok"
    assert found["p3-b2"]["reasons"] == [checks.STATION_MISMATCH]
    assert "7A" in claude_engine.PAGE_PROMPT


def test_missing_station_numbers_are_not_a_mismatch(tmp_path, fake):
    root = sunday_with_pages(tmp_path)
    item = block(1, "Ann Testerson", [7, 7, 8])
    item["stations"] = [{"tot": 7}, {"stn": None, "tot": 7}, {"tot": 8}]
    fake(done(envelope(page(item))))
    read(root, ClaudeClient(tmp_path / "cache"))
    assert readings_of(root)["p3-b1"]["status"] == "ok"


def test_an_offline_client_does_not_open_a_connection(tmp_path):
    client = VlmClient(tmp_path, offline=True)
    assert client.http is None
    client.close()
