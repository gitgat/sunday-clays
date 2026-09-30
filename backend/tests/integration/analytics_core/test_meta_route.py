from datetime import date
from typing import Any

from fastapi.testclient import TestClient


def test_meta_counts_seeded_world(seed: Any, viewer_client: TestClient) -> None:
    ann = seed.shooter("Oakley, Ann")
    bob = seed.shooter("Pratt, Bob")
    seed.event(date(2026, 8, 30), held=False, has_scores=False, head_count=5)
    seed.round(date(2026, 9, 6), ann, 40)
    seed.round(date(2026, 9, 6), bob, 35)
    seed.round(date(2026, 9, 13), ann, 42)
    seed.finish()

    body = viewer_client.get("/api/meta").json()

    assert body["data_version"] >= 1
    assert body["first_event_date"] == "2026-08-30"
    assert body["last_event_date"] == "2026-09-13"
    assert body["first_score_date"] == "2026-09-06"
    assert body["n_events"] == 3
    assert body["n_scored_events"] == 2
    assert body["n_held_events"] == 2
    assert body["n_rounds"] == 3
    assert body["n_shooters"] == 2


def test_meta_on_committed_fixtures(fx_viewer_client: TestClient) -> None:
    body = fx_viewer_client.get("/api/meta").json()

    assert body["first_event_date"] == "2018-12-30"
    assert body["last_score_date"] == "2026-09-27"
    assert body["n_events"] == 360
    assert body["n_scored_events"] == 311
    assert body["n_held_events"] == 310
    assert body["n_station_events"] == 2
    assert body["n_rounds"] == 7480
    assert body["n_shooters"] == 332
