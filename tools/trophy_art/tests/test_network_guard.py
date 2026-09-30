import httpx
import pytest


def test_unmocked_requests_never_leave_the_machine():
    with pytest.raises(httpx.ConnectError, match="network blocked"):
        httpx.get("https://imagen.thehalf.io/api/health")
