"""The ClaySmasher export with a special Sunday (Plan 17 x spec 2026-10-01 §4.1).

A special Sunday (the 3-Bird Shoot) counts only as an appearance, so its rounds never reach the
export: ClaySmasher would file a 60-target 3-bird score as a Sporting round.
"""

from typing import Any

from fastapi.testclient import TestClient

from sunday_clays.analytics.cache import clear_cache

SPECIAL = "2026-09-20"
STAMPS = ("generated_at", "updated_at")


def _get(client: TestClient, url: str) -> Any:
    clear_cache()
    response = client.get(url)
    assert response.status_code == 200, response.text
    return response.json()


def _id(client: TestClient, name: str) -> int:
    (match,) = [
        s
        for s in _get(client, f"/api/shooters?q={name.split(',')[0]}")
        if s["display_name"] == name
    ]
    return int(match["shooter_id"])


def _without_stamps(body: Any) -> Any:
    """generated_at/updated_at are wall-clock times that differ between the two worlds."""
    if isinstance(body, dict):
        return {k: _without_stamps(v) for k, v in body.items() if k not in STAMPS}
    if isinstance(body, list):
        return [_without_stamps(v) for v in body]
    return body


def test_the_export_leaves_the_special_sunday_out(
    fx_viewer_client: TestClient, fx_special_viewer_client: TestClient
) -> None:
    hadley = _id(fx_viewer_client, "Hadley, Ike")
    assert _id(fx_special_viewer_client, "Hadley, Ike") == hadley
    assert [
        s["event_date"] for s in _get(fx_special_viewer_client, f"/api/shooters/{hadley}/special")
    ] == [SPECIAL]

    base = _get(fx_viewer_client, f"/api/shooters/{hadley}/export")
    special = _get(fx_special_viewer_client, f"/api/shooters/{hadley}/export")

    assert SPECIAL not in {r["event_date"] for r in special["rounds"]}
    assert _without_stamps(special) == _without_stamps(base)


def test_a_special_only_shooter_exports_no_rounds(fx_special_viewer_client: TestClient) -> None:
    kim = _id(fx_special_viewer_client, "Kim, Pat")

    body = _get(fx_special_viewer_client, f"/api/shooters/{kim}/export")

    assert body["shooter"] == {"id": kim, "display_name": "Kim, Pat"}
    assert body["rounds"] == []
