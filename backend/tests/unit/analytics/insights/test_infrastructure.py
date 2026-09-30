"""Coverage for the shared helpers, chart builders and value types that kinds build on."""

import importlib
import pkgutil
from datetime import date, timedelta

import pytest

from sunday_clays.analytics.insights import charts, registry
from sunday_clays.analytics.insights.context import (
    anchor_days,
    crossed,
    held_only,
    in_year,
    jan1,
    run_back,
    run_start,
    sample_var,
    shot_recently,
    weeks,
)
from sunday_clays.analytics.insights.registry import Kind, validate
from sunday_clays.analytics.insights.templates import (
    Clause,
    Int,
    NameList,
    ShortDate,
    Slot,
    Station,
    T,
    TemplateError,
    TrophyName,
    Word,
    literal_texts,
    named,
    plain,
    render,
)
from sunday_clays.analytics.insights.types import (
    NO_HIGHLIGHT,
    Highlight,
    Page,
    ProofHow,
    Readiness,
    Requires,
    Scope,
    Window,
    cell,
    count_rows,
    diff,
    distinct,
    lead,
    max_before,
    mean_of,
    na,
    p_date,
    p_ids,
    p_int,
    p_str,
    rank_of,
    rows_total,
    run_length,
    share,
    total,
)
from sunday_clays.explorer.spec import Dim, Metric

LABEL = T(named("A chart"))


def test_chart_builders_carry_explicit_windows_and_no_round_type():
    end = date(2026, 9, 27)
    assert charts.recent(end) == Window(date(2026, 6, 27), end)
    assert charts.since(date(2026, 3, 31), end, months_before=1) == Window(date(2026, 2, 28), end)
    window = charts.recent(end)
    q = charts.spec(Metric.SCORE, "avg", Dim.SHOOTER, window=window, shooters=(1,), best=True)
    assert q.filters.date_from == window.start
    assert q.filters.shooter_ids == [1]
    link = charts.explorer(q, label=LABEL, hl=Highlight(dates=(end,)), ref=40.0)
    assert (link.type, link.window, link.ref) == ("explorer", window, 40.0)
    page = charts.profile_chart(7, "trend", label=LABEL, window=window, params={"k": "v"})
    assert (page.route, page.anchor, dict(page.params)) == ("/shooters/7", "trend", {"k": "v"})
    results = charts.results_chart(end, (3,), label=LABEL)
    assert results.route == "/events/2026-09-27"
    assert results.highlight.shooter_ids == (3,)
    assert charts.page("/x", "a", label=LABEL, window=window).highlight == NO_HIGHLIGHT


def test_an_explorer_spec_without_a_window_raises():
    q = charts.spec(Metric.SCORE, "avg", window=Window(date(2026, 1, 1), date(2026, 2, 1)))
    q.filters.date_from = None
    with pytest.raises(ValueError, match="explicit window"):
        charts.explorer(q, label=LABEL)


def test_value_types_serialise_and_readiness_reports_what_is_missing():
    d = date(2026, 1, 4)
    assert Window(d, d).to_json() == {"from": "2026-01-04", "to": "2026-01-04"}
    hl = Highlight(dates=(d,), shooter_ids=(1,), keys=("k",), span=(d, d))
    assert hl.to_json() == {
        "dates": ["2026-01-04"],
        "shooter_ids": [1],
        "keys": ["k"],
        "span": ["2026-01-04", "2026-01-04"],
    }
    assert NO_HIGHLIGHT.to_json() == {}
    assert Requires().unmet(Readiness(0, 0)) is None
    assert "needs 8 Sundays" in (Requires(station_sundays=8).unmet(Readiness(3, 0)) or "")
    assert Requires(trophy_awards=1).unmet(Readiness(9, 0)) == "needs at least one trophy award"


def test_proof_check_constructors():
    checks = [
        cell("a"),
        total("a"),
        mean_of("a"),
        count_rows("a"),
        run_length("a"),
        rank_of("a"),
        rows_total("a"),
        max_before("a"),
        share("a", 40),
        diff("a", "k", "o"),
        lead("a"),
        distinct("a", "col"),
        na("a", "why"),
    ]
    assert [c.how for c in checks] == [
        ProofHow.CELL,
        ProofHow.SUM,
        ProofHow.MEAN,
        ProofHow.COUNT,
        ProofHow.RUN,
        ProofHow.RANK,
        ProofHow.ROWS,
        ProofHow.MAX_BEFORE,
        ProofHow.SHARE,
        ProofHow.DIFF,
        ProofHow.LEAD,
        ProofHow.DISTINCT,
        ProofHow.NA,
    ]
    assert checks[8].threshold == 40
    assert checks[-1].reason == "why"


def test_typed_param_readers():
    params = {"i": 3.6, "f": 2, "d": date(2026, 1, 4), "s": "2026-01-04", "ids": [1, 2], "w": "x"}
    assert p_int(params, "i") == 4
    assert p_date(params, "d") == p_date(params, "s") == date(2026, 1, 4)
    assert p_ids(params, "ids") == (1, 2)
    assert p_str(params, "w") == "x"
    with pytest.raises(TypeError):
        p_int({"i": "x"}, "i")
    with pytest.raises(TypeError):
        p_date({"d": 1}, "d")
    with pytest.raises(TypeError):
        p_ids({"ids": 1}, "ids")


def test_template_readers_and_remaining_slots():
    assert plain(render(T(named(ShortDate("d"))), {"d": "2026-01-04"}, {})) == "Jan 4"
    with pytest.raises(TemplateError, match="must be a date"):
        render(T(named(ShortDate("d"))), {"d": 3}, {})
    with pytest.raises(TemplateError, match="list of shooter ids"):
        render(T(named(NameList("ids"))), {"ids": "x"}, {})
    with pytest.raises(TemplateError, match="must be a number"):
        render(T(named(Int("n"))), {"n": True}, {})
    with pytest.raises(NotImplementedError):
        Slot("p").segments({}, {})
    t = T(named(TrophyName("t"), " ", Station("n")))
    assert plain(render(t, {"t": "Ace", "n": 7}, {})) == "Ace Station 7"
    assert plain(render(t, {"t": "Ace", "n": 7.0}, {})) == "Ace Station 7"
    assert plain(render(t, {"t": "Ace", "n": "7a"}, {})) == "Ace Station 7A"
    with pytest.raises(TemplateError, match="station number or label"):
        render(t, {"t": "Ace", "n": "seven"}, {})
    with pytest.raises(TemplateError, match="station number or label"):
        render(t, {"t": "Ace", "n": 7.4}, {})
    word = Word("w", (("a", "in the rain"),))
    assert literal_texts(Clause("named", ("x ", word))) == ["x ", "in the rain"]
    empty = render(T(named("", Word("w", (("a", ""),)))), {"w": "a"}, {})
    assert empty == []


def test_context_helpers(make_world, sun):
    fr = make_world().series(1, 0, [30, 41, 36]).crowd(sun(1), [20, 30]).frames()
    days = fr.histories[1]
    assert fr.sunday(sun(1)) is not None
    assert fr.sunday(sun(50)) is None
    assert fr.held_between(sun(0), sun(2)) == 2
    assert fr.names[1] == "Pat Shooter1"
    assert days[0].prior_mean is None
    assert days[1].prior_mean == 30
    assert [d.date for d in held_only(days)] == [sun(0), sun(1), sun(2)]
    assert shot_recently(days, sun(3))
    assert not shot_recently(days, sun(3) + timedelta(weeks=20))
    assert not shot_recently((), sun(3))
    assert sample_var([1.0]) == 0.0
    assert jan1(date(2026, 9, 27)) == date(2026, 1, 1)
    assert weeks(2) == timedelta(days=14)
    assert crossed(38, 41, (35, 40, 45)) == 40
    assert crossed(41, 42, (35, 40, 45)) is None
    assert run_back(days, lambda d: d.score >= 36) == 2
    assert run_back(days, lambda d: None if d.score == 41 else d.score >= 30) == 2
    assert run_back(days, lambda d: d.score >= 40) == 0
    assert run_start(days, lambda d: True, 2).date == sun(1)
    assert [d.date for d in in_year(days, 2024)] == [sun(0), sun(1), sun(2)]
    scope = Scope(sundays=frozenset({sun(1)}), as_of=sun(2))
    assert [(i, len(ds)) for i, ds in anchor_days(fr, scope)] == [
        (1, 3),
        (0, 1),
        (0, 1),
    ]  # shooter 1 anchors at index 1; two fillers at 0


def test_anchor_days_skip_deceased_shooters(make_world, sun):
    world = make_world().shooter(1, status="deceased").series(1, 0, [30, 31]).series(2, 0, [30, 31])
    scope = Scope(sundays=frozenset({sun(1)}), as_of=sun(1))
    assert [days[0].shooter_id for _i, days in anchor_days(world.frames(), scope)] == [2]


def test_registry_lookup_and_remaining_rules(good, monkeypatch):
    monkeypatch.setattr(registry, "load_all", lambda: None)
    monkeypatch.setattr(registry, "_REGISTRY", {})
    with pytest.raises(KeyError, match="unknown insight kind"):
        registry.get("pf.nope")
    assert registry.all_kinds() == []
    kind = good()
    assert kind.care_for("") == 3
    assert Kind is type(kind)
    assert any("1-3 templates" in p for p in validate(good(templates={"": ()})))
    assert "no templates" in validate(good(templates={}))
    assert any("only shooter kinds" in p for p in validate(_club_with_you(good)))
    assert any("'how' bullet needs" in p for p in validate(good(how={"": (T(named("x")),)})))
    assert Page.PROFILE in kind.pages


def _club_with_you(good):
    from sunday_clays.analytics.insights.types import SubjectType

    return good(
        id="cl.test-kind",
        subject=SubjectType.CLUB,
        templates={"": (T(named("Club shot."), you=named("You shot.")),)},
        how={"": (T(named("Counted.")),)},
        labels=(LABEL,),
    )


def test_load_all_imports_kind_modules_and_skips_infrastructure(monkeypatch):
    fake = pkgutil.ModuleInfo(None, "pf_fake", False)
    real_iter = pkgutil.iter_modules
    asked: list[str] = []
    monkeypatch.setattr(registry.pkgutil, "iter_modules", lambda path: [*real_iter(path), fake])
    real_import = importlib.import_module

    def spy(name):
        if name == registry._PACKAGE:
            return real_import(name)
        asked.append(name)
        return None

    monkeypatch.setattr(registry.importlib, "import_module", spy)
    registry.load_all()
    leaves = [n.rsplit(".", 1)[-1] for n in asked]
    assert f"{registry._PACKAGE}.pf_fake" in asked
    assert not set(leaves) & set(registry._SKIP_MODULES)
    assert not any(leaf.startswith("_") for leaf in leaves)
    assert {"registry", "templates"} <= {
        m.name for m in real_iter(real_import(registry._PACKAGE).__path__)
    }


def test_run_start_rejects_a_run_that_does_not_exist(make_world, sun):
    days = make_world().series(1, 0, [30, 31]).frames().histories[1]
    for length in (0, -1, 3):
        with pytest.raises(ValueError, match="run length"):
            run_start(days, lambda d: True, length)
