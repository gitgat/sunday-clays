"""GET /api/shooters/{id}/summary (Plan 19 §3.6.1, §5.2)."""

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from sunday_clays.config import get_settings
from sunday_clays.domain.features import set_switch

URL = "/api/shooters/{id}/summary"


def _on(session: Session) -> None:
    set_switch(session, get_settings(), "summary_card", True)


def _id(session: Session, name: str) -> int:
    return int(
        session.execute(
            text("SELECT shooter_id FROM shooter_profiles WHERE display_name = :n"), {"n": name}
        ).scalar_one()
    )


def test_gated_404_for_a_viewer_and_200_for_an_admin(
    fx_viewer_client: TestClient, fx_admin_client: TestClient
) -> None:
    params = {"to": "2026-09-27"}
    assert fx_viewer_client.get(URL.format(id=3), params=params).json() == {"detail": "Not Found"}
    assert fx_admin_client.get(URL.format(id=3), params=params).status_code == 200


def test_a_special_only_shooter(
    fx_special_viewer_client: TestClient, fx_special_session: Session
) -> None:
    _on(fx_special_session)
    kim = _id(fx_special_session, "Kim, Pat")
    body = fx_special_viewer_client.get(
        URL.format(id=kim), params={"from": "2026-08-03", "to": "2026-09-27"}
    ).json()
    assert body["display_name"] == "Kim, Pat"
    assert (body["sundays"], body["special_sundays"], body["rounds"]) == (1, 1, 0)
    assert body["average"] is None
    assert body["best"] is None
    assert body["from"] == "2026-08-03"
    assert body["to"] == "2026-09-27"


def test_the_special_sunday_extends_a_streak(
    fx_viewer_client: TestClient,
    fx_session: Session,
    fx_special_viewer_client: TestClient,
    fx_special_session: Session,
) -> None:
    _on(fx_session)
    _on(fx_special_session)
    params = {"from": "2026-09-13", "to": "2026-09-27"}
    plain = fx_viewer_client.get(
        URL.format(id=_id(fx_session, "Hadley, Ike")), params=params
    ).json()
    special = fx_special_viewer_client.get(
        URL.format(id=_id(fx_special_session, "Hadley, Ike")), params=params
    ).json()
    assert special["sundays"] == plain["sundays"] + 1
    assert plain["longest_streak"] == 2
    assert special["longest_streak"] == 3  # the special Sunday extends the run by one
    assert special["rounds"] == plain["rounds"]


def test_from_omitted_is_an_open_start(fx_viewer_client: TestClient, fx_session: Session) -> None:
    _on(fx_session)
    open_start = fx_viewer_client.get(URL.format(id=3), params={"to": "2026-09-27"}).json()
    lifetime = fx_viewer_client.get("/api/shooters/3").json()["odometer"]
    assert open_start["from"] is None
    assert open_start["rounds"] == lifetime["rounds"]


def test_errors(fx_viewer_client: TestClient, fx_session: Session) -> None:
    _on(fx_session)
    assert fx_viewer_client.get(URL.format(id=3)).status_code == 422  # `to` is required
    bad = fx_viewer_client.get(URL.format(id=3), params={"from": "2026-09-27", "to": "2026-09-13"})
    assert bad.status_code == 400
    assert bad.json()["error"]["code"] == "invalid_range"
    missing = fx_viewer_client.get(URL.format(id=999999), params={"to": "2026-09-27"})
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "shooter_not_found"
