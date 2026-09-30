"""POST /api/explore over the committed fixtures (`fx_viewer_client`, Plans 03 T6 and 04 T1).

Expected numbers were counted from the fixture workbooks with openpyxl/pandas.
"""

from typing import Any

import pytest
from fastapi.testclient import TestClient

ROUNDS_BY_YEAR = {2020: 843, 2021: 1047, 2022: 1078, 2023: 1083, 2024: 1193, 2025: 1267, 2026: 969}
# Class column: blank (incl. one whitespace-only cell) = unspecified; the one '29 Gauge' cell is
# read as 28 Gauge (ingest's typo correction, user decision 2026-09-28). Ties sort by key.
ROUNDS_BY_GAUGE = [
    ("unspecified", 7302),
    ("12 Gauge", 151),
    ("Sub-Gauge", 9),
    ("SxS", 9),
    ("28 Gauge", 8),
    ("20 Gauge", 1),
]
# station_no: (hits, targets) summed over the 37 linked station-sheet entries
HITS_BY_STATION = {
    4: (184, 259),
    5: (190, 259),
    6: (190, 259),
    7: (205, 259),
    8: (205, 259),
    9: (130, 259),
    10: (230, 296),
}


def _explore(client: TestClient, spec: dict[str, Any]) -> dict[str, Any]:
    response = client.post("/api/explore", json=spec)
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


def test_rounds_by_year(fx_viewer_client: TestClient) -> None:
    body = _explore(fx_viewer_client, {"metric": "rounds", "group_by": ["year"]})

    assert body["columns"] == [
        {"key": "year", "label": "Year", "type": "int"},
        {"key": "value", "label": "Rounds", "type": "int"},
        {"key": "n", "label": "n", "type": "int"},
    ]
    assert {row["year"]: row["value"] for row in body["rows"]} == ROUNDS_BY_YEAR
    assert body["n_rounds"] == 7480
    assert body["truncated"] is False


def test_rounds_by_gauge_keep_unspecified(fx_viewer_client: TestClient) -> None:
    body = _explore(
        fx_viewer_client, {"metric": "rounds", "group_by": ["gauge"], "sort": "value_desc"}
    )

    assert [(row["gauge"], row["value"]) for row in body["rows"]] == ROUNDS_BY_GAUGE


def test_hit_pct_by_station(fx_viewer_client: TestClient) -> None:
    body = _explore(fx_viewer_client, {"metric": "hit_pct", "group_by": ["station"]})

    assert {row["station"]: row["value"] for row in body["rows"]} == pytest.approx(
        {str(no): 100 * hits / targets for no, (hits, targets) in HITS_BY_STATION.items()}
    )
    assert {row["n"] for row in body["rows"]} == {37}
    assert body["n_rounds"] == 37


def test_invalid_query_is_a_400_with_the_error_envelope(fx_viewer_client: TestClient) -> None:
    response = fx_viewer_client.post(
        "/api/explore", json={"metric": "score", "group_by": ["station"]}
    )

    assert response.status_code == 400
    assert response.json() == {
        "error": {
            "code": "invalid_query",
            "message": "Grouping by station needs the Hit % metric",
        }
    }


def test_an_empty_database_answers_without_rows(viewer_client: TestClient) -> None:
    """A fresh install (no import yet) gets empty results or invalid_query, never a 500."""
    body = _explore(viewer_client, {"metric": "score", "group_by": ["status", "temp_band"]})
    assert body["rows"] == []
    assert body["n_rounds"] == 0

    response = viewer_client.post("/api/explore", json={"metric": "hit_pct"})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_query"


def test_more_than_two_dims_fail_validation(fx_viewer_client: TestClient) -> None:
    response = fx_viewer_client.post(
        "/api/explore", json={"metric": "rounds", "group_by": ["year", "month", "season"]}
    )

    assert response.status_code == 422
