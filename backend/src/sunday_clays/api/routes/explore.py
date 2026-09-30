"""POST /api/explore (C8/C9): run a validated Explorer QuerySpec against the cached frames."""

from fastapi import APIRouter

from sunday_clays.db import SessionDep
from sunday_clays.explorer.engine import load_explorer_frames, run_query
from sunday_clays.explorer.spec import QueryResult, QuerySpec

router = APIRouter(tags=["explore"])


@router.post("/api/explore", response_model=QueryResult)
def explore(spec: QuerySpec, session: SessionDep) -> QueryResult:
    return run_query(load_explorer_frames(session), spec)
