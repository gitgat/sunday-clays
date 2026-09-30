"""Session-scoped real-workbook fixtures for the ingest unit tests.

Loading a fixture takes ~0.6 s, so each is loaded once per pytest run and
shared by every test. The parsers never change a cell value, but openpyxl's
``cell()`` and ``iter_rows()`` create a cell object on every access, which can
grow ``max_row``/``max_column`` on these shared workbooks. Parsers therefore
must not depend on those bounds being pristine: they bound their own scans and
skip blank cells.
"""

from pathlib import Path

import pytest

from sunday_clays.ingest.workbook import LoadedWorkbook, load_workbook_bytes

FIXTURES_DIR = Path(__file__).resolve().parents[2] / "fixtures"


@pytest.fixture(scope="session")
def scores_file_bytes() -> bytes:
    return (FIXTURES_DIR / "scores_2026-09-27.xlsx").read_bytes()


@pytest.fixture(scope="session")
def stations_file_bytes() -> bytes:
    return (FIXTURES_DIR / "stations_2026-09-27.xlsx").read_bytes()


@pytest.fixture(scope="session")
def scores_lw(scores_file_bytes: bytes) -> LoadedWorkbook:
    return load_workbook_bytes(scores_file_bytes)


@pytest.fixture(scope="session")
def stations_lw(stations_file_bytes: bytes) -> LoadedWorkbook:
    return load_workbook_bytes(stations_file_bytes)
