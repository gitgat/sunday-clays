"""The ClaySmasher scores export with a special Sunday (Plan 17).

A special Sunday (the 3-Bird Shoot) counts only as an appearance, so its rounds never reach the
export: ClaySmasher would file a 60-target 3-bird score as a Sporting round.
"""

import io
import zipfile
from typing import Any

from fastapi.testclient import TestClient

from sunday_clays.analytics.cache import clear_cache

SPECIAL = "2026-09-20"
SPECIAL_US = "09/20/2026"


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


def _files(client: TestClient, shooter_id: int) -> dict[str, str]:
    clear_cache()
    response = client.get(f"/api/shooters/{shooter_id}/claysmasher-export")
    assert response.status_code == 200, response.text
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        return {name: archive.read(name).decode("utf-8") for name in archive.namelist()}


def test_the_export_leaves_the_special_sunday_out(
    fx_viewer_client: TestClient, fx_special_viewer_client: TestClient
) -> None:
    hadley = _id(fx_viewer_client, "Hadley, Ike")
    assert _id(fx_special_viewer_client, "Hadley, Ike") == hadley
    assert [
        s["event_date"] for s in _get(fx_special_viewer_client, f"/api/shooters/{hadley}/special")
    ] == [SPECIAL]

    base = _files(fx_viewer_client, hadley)
    special = _files(fx_special_viewer_client, hadley)

    assert all(SPECIAL_US not in text for text in special.values())
    assert special == base


def test_a_special_only_shooter_has_nothing_to_export(
    fx_special_viewer_client: TestClient,
) -> None:
    kim = _id(fx_special_viewer_client, "Kim, Pat")
    clear_cache()

    response = fx_special_viewer_client.get(f"/api/shooters/{kim}/claysmasher-export")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "no_exportable_rounds"
