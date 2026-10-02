from pathlib import Path

import pytest
import yaml

from manifest import ManifestError, Target, load_manifest, split_stem

SAMPLE = """
style: "house style"
defaults: {model: z-image, size: 1024, seeds: [101, 202], negative: "no text"}
metal_phrases:
  bronze: "warm bronze finish"
  silver: "polished silver finish"
  gold: "gleaming gold finish"
  platinum: "brushed platinum finish"
  diamond: "platinum set with diamonds"
  one_off: "copper with orange enamel"
trophies:
  - {art_key: clays_broken, metals: [bronze, gold], prompt: "a shattered clay"}
  - {art_key: doubleheader, metals: [], prompt: "two clays", seeds: [7], negative: "blurry"}
"""

FAMILY_METALS = {
    "clays_broken": ("bronze", "silver", "gold", "platinum", "diamond"),
    "clays_thrown": ("bronze", "silver", "gold", "platinum", "diamond"),
    "events": ("bronze", "silver", "gold", "platinum", "diamond"),
    "years_active": ("bronze", "silver", "gold", "platinum"),
    "big_year": ("bronze", "silver", "gold"),
    "iron_streak": ("bronze", "silver", "gold", "platinum"),
    "round_score": ("bronze", "silver", "gold", "platinum", "diamond"),
    "station_cleaner": ("bronze", "silver", "gold", "platinum"),
    "personal_bests": ("bronze", "silver", "gold"),
}
ONE_OFFS = (
    "doubleheader",
    "new_year",
    "anniversary_1",
    "anniversary_5",
    "welcome_back",
    "joined_club",
    "both_disciplines",
    "four_seasons",
    "three_bird_shoot",
    "perfect_month",
    "sub_gauge",
    "rain",
    "cold",
    "heat",
    "wind",
    "all_weather",
    "mudder",
    "comeback",
    "above_average_3",
    "first_win",
    "podium",
    "station_top_gun",
    "hardest_station_clean",
)
HOUSE_STYLE = (
    "enamel-and-metal clay-shooting trophy medallion, centered, flat studio lighting, "
    "dark forest-green backdrop, no text"
)


def write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "manifest.yaml"
    path.write_text(text)
    return path


def test_targets_expand_metals_and_apply_defaults(tmp_path):
    assert load_manifest(write(tmp_path, SAMPLE)) == [
        Target(
            "clays_broken",
            "bronze",
            "house style, warm bronze finish, a shattered clay",
            "no text",
            "z-image",
            (101, 202),
            1024,
        ),
        Target(
            "clays_broken",
            "gold",
            "house style, gleaming gold finish, a shattered clay",
            "no text",
            "z-image",
            (101, 202),
            1024,
        ),
        Target(
            "doubleheader", None, "house style, copper with orange enamel, two clays", "blurry", "z-image", (7,), 1024
        ),
    ]


def test_stems_add_the_metal_suffix_only_for_tiers(tmp_path):
    assert [t.stem for t in load_manifest(write(tmp_path, SAMPLE))] == [
        "clays_broken-bronze",
        "clays_broken-gold",
        "doubleheader",
    ]


def test_unknown_metal_is_rejected(tmp_path):
    with pytest.raises(ManifestError, match="unknown metal 'copper'"):
        load_manifest(write(tmp_path, SAMPLE.replace("[bronze, gold]", "[copper]")))


def test_duplicate_target_is_rejected(tmp_path):
    with pytest.raises(ManifestError, match="duplicate target doubleheader"):
        load_manifest(write(tmp_path, SAMPLE + '  - {art_key: doubleheader, metals: [], prompt: "again"}\n'))


@pytest.mark.parametrize(
    ("stem", "expected"),
    [
        ("clays_broken-gold", ("clays_broken", "gold")),
        ("doubleheader", ("doubleheader", None)),
        ("above_average_3", ("above_average_3", None)),
    ],
)
def test_split_stem(stem, expected):
    assert split_stem(stem) == expected


def test_real_manifest_covers_every_c12_art_target():
    manifest = Path(__file__).resolve().parents[1] / "manifest.yaml"
    targets = load_manifest(manifest)
    expected = {(k, m) for k, metals in FAMILY_METALS.items() for m in metals} | {(k, None) for k in ONE_OFFS}
    assert len(expected) == 61
    assert {(t.art_key, t.metal) for t in targets} == expected
    # Re-rolled after the user rejected every first-round candidate (2026-09-29): new prompts, six fresh seeds.
    rerolled = {"clays_thrown", "sub_gauge", "rain"}
    for t in targets:
        want = (505, 606, 707, 808, 909, 1010) if t.art_key in rerolled else (101, 202, 303, 404)
        model = "krea2-turbo" if t.art_key in {"clays_thrown", "rain"} else "z-image-turbo"
        assert (t.seeds, t.model, t.size) == (want, model, 1024), t.art_key
    # Entries with their own `style` (the krea2-turbo rerolls) start with it instead of the house style.
    own_style = yaml.safe_load(manifest.read_text())["trophies"]
    styles = {e["art_key"]: e["style"] for e in own_style if "style" in e}
    assert styles
    for t in targets:
        assert t.prompt.startswith(styles.get(t.art_key, HOUSE_STYLE)), t.stem


def test_sampling_overrides_come_from_defaults_and_entries(tmp_path):
    text = SAMPLE.replace(
        'defaults: {model: z-image, size: 1024, seeds: [101, 202], negative: "no text"}',
        'defaults: {model: z-image, size: 1024, seeds: [101, 202], negative: "no text", '
        "steps: 20, cfg: 3, sampler: euler}",
    ).replace("{art_key: doubleheader,", "{art_key: doubleheader, scheduler: karras, steps: 8,")
    targets = load_manifest(write(tmp_path, text))
    assert [(t.steps, t.cfg, t.sampler, t.scheduler) for t in targets] == [
        (20, 3.0, "euler", None),
        (20, 3.0, "euler", None),
        (8, 3.0, "euler", "karras"),
    ]


def test_entry_style_overrides_house_style(tmp_path: Path) -> None:
    path = tmp_path / "m.yaml"
    path.write_text(
        'style: "house"\n'
        'defaults: {model: z-image, size: 1024, seeds: [1], negative: "n"}\n'
        "metal_phrases: {bronze: b, silver: s, gold: g, platinum: p, diamond: d, one_off: o}\n"
        "trophies:\n"
        '  - {art_key: rain, prompt: "cloud", style: "plain badge"}\n'
        '  - {art_key: cold, prompt: "snow"}\n'
    )
    rain, cold = load_manifest(path)
    assert rain.prompt == "plain badge, o, cloud"
    assert cold.prompt == "house, o, snow"
