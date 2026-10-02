import json
import runpy
from io import BytesIO
from pathlib import Path

import httpx
import pytest
from PIL import Image

import cli

BASE = "https://imagen.test"
MANIFEST = """
style: "style"
defaults: {model: z-image, size: 64, seeds: [1, 2], negative: "n"}
metal_phrases: {bronze: b, silver: s, gold: g, platinum: p, diamond: d, one_off: o}
trophies:
  - {art_key: doubleheader, metals: [], prompt: "two clays"}
"""
OUTPUT = {"ordinal": 0, "asset_id": "a1", "thumb_url": "/t", "bytes_url": "/api/assets/a1/bytes"}


def png_bytes() -> bytes:
    out = BytesIO()
    Image.new("RGB", (64, 64), (200, 60, 40)).save(out, format="PNG")
    return out.getvalue()


@pytest.fixture
def paths(tmp_path):
    manifest = tmp_path / "manifest.yaml"
    manifest.write_text(MANIFEST)
    selection = tmp_path / "selection.json"
    selection.write_text("{}\n")
    return {"manifest": manifest, "selection": selection, "out": tmp_path / "out", "repo": tmp_path / "repo"}


def run(paths, *args: str) -> int:
    return cli.main(
        [
            "--out",
            str(paths["out"]),
            "--manifest",
            str(paths["manifest"]),
            "--selection",
            str(paths["selection"]),
            *args,
        ]
    )


@pytest.fixture
def imagen_env(monkeypatch):
    monkeypatch.setenv("IMAGEN_URL", BASE)
    monkeypatch.setenv("IMAGEN_USERNAME", "bryan")
    monkeypatch.setenv("IMAGEN_PASSWORD", "secret")


def mock_imagen(respx_mock, state="completed"):
    respx_mock.post("/api/auth/login", name="login").mock(
        return_value=httpx.Response(200, json={"id": "u1", "username": "bryan", "is_admin": False})
    )
    respx_mock.get("/api/models").mock(
        return_value=httpx.Response(
            200,
            json={
                "models": [
                    {
                        "key": "z-image",
                        "defaults": {"sampler": "euler", "scheduler": "normal", "steps": 30, "cfg": 4.0},
                    }
                ]
            },
        )
    )
    create = respx_mock.post("/api/generations").mock(
        return_value=httpx.Response(201, json={"id": "g1", "state": "queued", "outputs": []})
    )
    outputs = [OUTPUT] if state == "completed" else []
    respx_mock.get("/api/generations/g1").mock(
        return_value=httpx.Response(200, json={"id": "g1", "state": state, "outputs": outputs})
    )
    respx_mock.get("/api/assets/a1/bytes").mock(return_value=httpx.Response(200, content=png_bytes()))
    return create


@pytest.mark.respx(base_url=cli.DEFAULT_IMAGEN_URL, assert_all_called=False)
def test_generate_without_credentials_skips_login_and_uses_the_default_url(paths, monkeypatch, respx_mock):
    for name in ("IMAGEN_URL", "IMAGEN_USERNAME", "IMAGEN_PASSWORD"):
        monkeypatch.delenv(name, raising=False)
    create = mock_imagen(respx_mock)
    assert run(paths, "generate") == 0
    assert create.call_count == 2
    assert respx_mock["login"].call_count == 0
    assert sorted(p.name for p in (paths["out"] / "candidates" / "doubleheader").iterdir()) == ["1.png", "2.png"]


@pytest.mark.parametrize("present", ["IMAGEN_USERNAME", "IMAGEN_PASSWORD"])
def test_generate_rejects_half_set_credentials(paths, monkeypatch, capsys, present):
    for name in ("IMAGEN_USERNAME", "IMAGEN_PASSWORD"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv(present, "x")
    assert run(paths, "generate") == 2
    assert "set both IMAGEN_USERNAME and IMAGEN_PASSWORD, or neither" in capsys.readouterr().err
    assert not paths["out"].exists()


@pytest.mark.respx(base_url=BASE, assert_all_called=False)
def test_generate_saves_each_seed_and_resumes(paths, imagen_env, respx_mock):
    create = mock_imagen(respx_mock)
    assert run(paths, "generate") == 0
    saved = sorted(p.name for p in (paths["out"] / "candidates" / "doubleheader").iterdir())
    assert saved == ["1.png", "2.png"]
    assert create.call_count == 2
    assert respx_mock["login"].call_count == 1  # both credentials set: one session login per run
    assert run(paths, "generate", "--only", "doubleheader") == 0
    assert create.call_count == 2  # existing candidates are never regenerated


@pytest.mark.respx(base_url=BASE, assert_all_called=False)
def test_generate_only_rejects_an_unknown_art_key(paths, imagen_env, respx_mock, capsys):
    create = mock_imagen(respx_mock)
    assert run(paths, "generate", "--only", "rain") == 2
    assert "no manifest target has art_key rain" in capsys.readouterr().err
    assert create.call_count == 0
    assert respx_mock["login"].call_count == 0


@pytest.mark.respx(base_url=BASE, assert_all_called=False)
def test_generate_reports_failures_and_continues(paths, imagen_env, respx_mock, capsys):
    mock_imagen(respx_mock, state="failed")
    assert run(paths, "generate") == 1
    assert capsys.readouterr().err.count("ended failed") == 2


@pytest.mark.respx(base_url=BASE, assert_all_called=False)
def test_generate_stops_when_login_fails(paths, imagen_env, respx_mock, capsys):
    respx_mock.post("/api/auth/login").mock(return_value=httpx.Response(401))
    assert run(paths, "generate") == 2
    assert "login failed" in capsys.readouterr().err


def test_sheet_requires_candidates(paths):
    assert run(paths, "sheet") == 1


def test_sheet_writes_the_contact_sheet(paths):
    target = paths["out"] / "candidates" / "doubleheader"
    target.mkdir(parents=True)
    (target / "1.png").write_bytes(png_bytes())
    assert run(paths, "sheet") == 0
    assert "candidates/doubleheader/1.png" in (paths["out"] / "contact_sheet.html").read_text()


def test_select_records_a_pick(paths):
    target = paths["out"] / "candidates" / "clays_broken-gold"
    target.mkdir(parents=True)
    (target / "202.png").write_bytes(png_bytes())
    assert run(paths, "select", "clays_broken", "gold", "202") == 0
    assert json.loads(paths["selection"].read_text()) == {
        "clays_broken-gold": {"art_key": "clays_broken", "metal": "gold", "seed": 202}
    }


def test_select_can_reuse_another_selection(paths):
    paths["selection"].write_text(json.dumps({"doubleheader": {"art_key": "doubleheader", "metal": None, "seed": 1}}))
    assert run(paths, "select", "bonus", "-", "--reuse", "doubleheader") == 0
    assert json.loads(paths["selection"].read_text())["bonus"] == {
        "art_key": "bonus",
        "metal": None,
        "reuse": "doubleheader",
    }


def test_select_reuse_needs_an_existing_plain_selection(paths):
    paths["selection"].write_text(
        json.dumps(
            {
                "doubleheader": {"art_key": "doubleheader", "metal": None, "seed": 1},
                "bonus": {"art_key": "bonus", "metal": None, "reuse": "doubleheader"},
            }
        )
    )
    assert run(paths, "select", "other", "-", "--reuse", "missing") == 1
    assert run(paths, "select", "other", "-", "--reuse", "bonus") == 1
    assert run(paths, "select", "other", "-") == 2
    assert run(paths, "select", "other", "-", "5", "--reuse", "doubleheader") == 2


def _select_doubleheader_and_bonus(paths):
    target = paths["out"] / "candidates" / "doubleheader"
    target.mkdir(parents=True)
    (target / "1.png").write_bytes(png_bytes())
    assert run(paths, "select", "doubleheader", "-", "1") == 0
    assert run(paths, "select", "bonus", "-", "--reuse", "doubleheader") == 0


def _gen(paths) -> str:
    return (paths["repo"] / "frontend" / "src" / "features" / "achievements" / "trophyArt.gen.ts").read_text()


def test_build_points_a_reused_key_at_its_sources_files_without_new_art(paths):
    _select_doubleheader_and_bonus(paths)
    assert run(paths, "build", "--repo-root", str(paths["repo"])) == 0
    public = paths["repo"] / "frontend" / "public" / "trophies"
    assert not (public / "bonus.webp").exists()
    assert not (public / "bonus@128.webp").exists()
    assert (
        "  bonus: {\n    src: '/trophies/doubleheader.webp',\n    src128: '/trophies/doubleheader@128.webp',\n  },\n"
    ) in _gen(paths)


def test_manifest_command_rebuilds_the_ts_from_built_files_without_candidates(paths):
    _select_doubleheader_and_bonus(paths)
    assert run(paths, "build", "--repo-root", str(paths["repo"])) == 0
    built = _gen(paths)
    gen = paths["repo"] / "frontend" / "src" / "features" / "achievements" / "trophyArt.gen.ts"
    gen.write_text("stale\n")
    assert run(paths, "manifest", "--repo-root", str(paths["repo"])) == 0
    assert _gen(paths) == built


def test_manifest_command_fails_when_a_referenced_file_is_missing(paths):
    _select_doubleheader_and_bonus(paths)
    assert run(paths, "manifest", "--repo-root", str(paths["repo"])) == 1
    public = paths["repo"] / "frontend" / "public" / "trophies"
    public.mkdir(parents=True)
    (public / "doubleheader.webp").write_bytes(b"x")
    assert run(paths, "manifest", "--repo-root", str(paths["repo"])) == 1
    (public / "doubleheader@128.webp").write_bytes(b"x")
    assert run(paths, "manifest", "--repo-root", str(paths["repo"])) == 0


def test_build_fails_when_a_reused_source_is_not_selected(paths):
    paths["selection"].write_text(json.dumps({"bonus": {"art_key": "bonus", "metal": None, "reuse": "gone"}}))
    assert run(paths, "build", "--repo-root", str(paths["repo"])) == 1


def test_select_rejects_missing_candidates_and_unknown_metals(paths):
    assert run(paths, "select", "doubleheader", "-", "9") == 1
    assert run(paths, "select", "doubleheader", "copper", "9") == 2


def test_build_writes_webp_pairs_and_the_ts_manifest(paths):
    target = paths["out"] / "candidates" / "doubleheader"
    target.mkdir(parents=True)
    (target / "1.png").write_bytes(png_bytes())
    assert run(paths, "select", "doubleheader", "-", "1") == 0
    assert run(paths, "build", "--repo-root", str(paths["repo"])) == 0
    public = paths["repo"] / "frontend" / "public" / "trophies"
    with Image.open(public / "doubleheader.webp") as large, Image.open(public / "doubleheader@128.webp") as small:
        assert (large.size, small.size) == ((256, 256), (128, 128))
    generated = (paths["repo"] / "frontend" / "src" / "features" / "achievements" / "trophyArt.gen.ts").read_text()
    assert (
        "  doubleheader: {\n"
        "    src: '/trophies/doubleheader.webp',\n"
        "    src128: '/trophies/doubleheader@128.webp',\n"
        "  },\n"
    ) in generated


def test_build_fails_when_a_selected_candidate_is_missing(paths):
    paths["selection"].write_text(json.dumps({"rain": {"art_key": "rain", "metal": None, "seed": 5}}))
    assert run(paths, "build", "--repo-root", str(paths["repo"])) == 1


def test_render_manifest_ts_without_art_is_an_empty_record():
    assert cli.render_manifest_ts([]) == (
        "// Generated by tools/trophy_art/cli.py build. Do not edit by hand.\n"
        "export const trophyArt: Record<string, { src: string; src128: string }> = {};\n"
    )


def test_render_manifest_ts_is_already_in_prettier_form():
    # The frontend runs `prettier --check .` (quoteProps as-needed, printWidth 100) over the committed file,
    # so keys are quoted only when they are not identifiers and every entry is expanded.
    assert cli.render_manifest_ts(["rain", "clays_broken-gold", "above_average_3"]) == (
        "// Generated by tools/trophy_art/cli.py build. Do not edit by hand.\n"
        "export const trophyArt: Record<string, { src: string; src128: string }> = {\n"
        "  above_average_3: {\n"
        "    src: '/trophies/above_average_3.webp',\n"
        "    src128: '/trophies/above_average_3@128.webp',\n"
        "  },\n"
        "  'clays_broken-gold': {\n"
        "    src: '/trophies/clays_broken-gold.webp',\n"
        "    src128: '/trophies/clays_broken-gold@128.webp',\n"
        "  },\n"
        "  rain: {\n"
        "    src: '/trophies/rain.webp',\n"
        "    src128: '/trophies/rain@128.webp',\n"
        "  },\n"
        "};\n"
    )


def test_check_reports_missing_targets(paths, tmp_path, capsys):
    keys = tmp_path / "keys.json"
    keys.write_text(json.dumps([["doubleheader", None], ["rain", None]]))
    assert run(paths, "check", str(keys)) == 1
    assert "missing manifest entry: rain -" in capsys.readouterr().out
    keys.write_text(json.dumps([["doubleheader", None]]))
    assert run(paths, "check", str(keys)) == 0


def test_default_paths_point_inside_the_tool():
    args = cli.build_parser().parse_args(["sheet"])
    assert args.manifest == Path(cli.__file__).resolve().parent / "manifest.yaml"


def test_running_the_script_exits_with_the_command_status(paths, tmp_path, monkeypatch):
    keys = tmp_path / "keys.json"
    keys.write_text(json.dumps([["doubleheader", None]]))
    monkeypatch.setattr("sys.argv", ["cli.py", "--manifest", str(paths["manifest"]), "check", str(keys)])
    with pytest.raises(SystemExit) as exited:
        runpy.run_path(cli.__file__, run_name="__main__")
    assert exited.value.code == 0


@pytest.mark.parametrize("name", ["IMAGEN_USERNAME", "IMAGEN_PASSWORD"])
def test_an_empty_credential_counts_as_unset(paths, monkeypatch, capsys, name):
    other = "IMAGEN_PASSWORD" if name == "IMAGEN_USERNAME" else "IMAGEN_USERNAME"
    monkeypatch.setenv(name, "")
    monkeypatch.setenv(other, "x")
    assert run(paths, "generate") == 2
    assert "set both IMAGEN_USERNAME and IMAGEN_PASSWORD, or neither" in capsys.readouterr().err


@pytest.mark.respx(base_url=cli.DEFAULT_IMAGEN_URL, assert_all_called=False)
def test_empty_credentials_and_url_mean_anonymous_on_the_default_host(paths, monkeypatch, respx_mock):
    for name in ("IMAGEN_URL", "IMAGEN_USERNAME", "IMAGEN_PASSWORD"):
        monkeypatch.setenv(name, "")
    create = mock_imagen(respx_mock)
    assert run(paths, "generate") == 0
    assert create.call_count == 2
    assert respx_mock["login"].call_count == 0


@pytest.mark.respx(base_url=BASE, assert_all_called=False)
def test_retry_uses_a_new_idempotency_key(paths, imagen_env, respx_mock):
    create = mock_imagen(respx_mock)
    assert run(paths, "generate") == 0
    for seed_file in (paths["out"] / "candidates" / "doubleheader").iterdir():
        seed_file.unlink()
    assert run(paths, "generate", "--retry", "1") == 0
    keys = [call.request.headers["Idempotency-Key"] for call in create.calls]
    assert len(keys) == 4
    assert len(set(keys)) == 4  # the retry keys differ from the first run's


@pytest.mark.respx(base_url=BASE, assert_all_called=False)
def test_generate_exits_cleanly_when_imagen_is_unreachable(paths, imagen_env, respx_mock, capsys):
    respx_mock.post("/api/auth/login").mock(return_value=httpx.Response(200, json={}))
    mock_imagen(respx_mock).mock(side_effect=httpx.ConnectError("refused"))
    assert run(paths, "generate") == 2
    err = capsys.readouterr().err
    assert "cannot reach imagen" in err
    assert "Traceback" not in err


@pytest.mark.respx(base_url=BASE, assert_all_called=False)
def test_generate_prints_the_servers_validation_detail_on_422(paths, imagen_env, respx_mock, capsys):
    create = mock_imagen(respx_mock)
    create.mock(return_value=httpx.Response(422, json={"detail": [{"msg": "steps: must be >= 1"}]}))
    assert run(paths, "generate") == 1
    assert "HTTP 422: [{'msg': 'steps: must be >= 1'}]" in capsys.readouterr().err
