"""Per-process memo for pure loaders/aggregations, keyed by data_version (C7).

Concurrent misses are single-flight: while one caller computes a key, other callers for
that key in this process wait for it and reuse its result instead of computing it again.
"""

import copy
import functools
import threading
from collections import OrderedDict
from collections.abc import Callable, Hashable
from dataclasses import dataclass, field
from typing import Concatenate, cast

import pandas as pd
from sqlalchemy.orm import Session

from sunday_clays.analytics.pipeline import get_data_version

MAX_ENTRIES = 256

type _Key = tuple[Hashable, ...]


@dataclass(eq=False)
class _Flight:
    """One computation in progress: its leader thread, and its outcome once `done` is set."""

    owner: int = field(default_factory=threading.get_ident)
    done: threading.Event = field(default_factory=threading.Event)
    ok: bool = False
    value: object = None


_memo: OrderedDict[_Key, object] = OrderedDict()
_flights: dict[_Key, _Flight] = {}
_waiting_on: dict[int, _Flight] = {}  # thread ident -> the flight that thread is waiting for
_lock = threading.Lock()  # guards the three dicts above; never held while computing or copying


def read_data_version(session: Session) -> int:
    """Current `app_state.data_version`; 0 before the first rebuild.

    Delegates to Plan 03 T7's `pipeline.get_data_version`, the single reader of the
    counter that `bump_data_version` writes. The memo, the ETag middleware and
    `/api/meta` look it up on this module at call time (`cache.read_data_version(...)`),
    so monkeypatching `cache.read_data_version` reaches all three.
    """
    return get_data_version(session)


def clear_cache() -> None:
    """Drop every memoized value in this process and detach every computation in flight.

    A detached computation still returns its value to its own caller and to callers already
    waiting for it, but never stores it, so a call that starts after this never receives a
    value whose computation started before it.
    """
    with _lock:
        _memo.clear()
        _flights.clear()


def _database_name(session: Session) -> str:
    return str(session.get_bind().engine.url.database)


def _copy_out(value: object) -> object:
    """A copy the caller owns: `.copy()` for DataFrames/Series, `deepcopy` for the rest."""
    if isinstance(value, pd.DataFrame | pd.Series):
        return value.copy()
    return copy.deepcopy(value)


def _join(flight: _Flight, me: int) -> None:
    """Record that thread `me` waits for `flight`, unless that closes a wait cycle.

    Following owner -> the flight that owner waits for -> its owner ... back to `me` means
    the flight can only finish after `me` does, so waiting would deadlock (a key cycle, which
    is infinite recursion without the memo too). A thread still listed as waiting for a
    flight that is already done is about to wake, so the chain stops there. Called with
    `_lock` held.
    """
    owner = flight.owner
    while owner != me:
        blocking = _waiting_on.get(owner)
        if blocking is None or blocking.done.is_set():
            _waiting_on[me] = flight
            return
        owner = blocking.owner
    raise RuntimeError("memoized call waits on itself: its key recurses into its own computation")


def _land(key: _Key, flight: _Flight) -> bool:
    """Retire `flight` for `key`; False if `clear_cache` detached it meanwhile. `_lock` held."""
    if _flights.get(key) is not flight:
        return False
    del _flights[key]
    return True


def _lead(key: _Key, flight: _Flight, compute: Callable[[], object]) -> object:
    """Run `compute` for `flight`, which this thread registered for `key`, then retire it.

    On success the value is stored (evicting the least recently used entries beyond
    `MAX_ENTRIES`) unless `clear_cache` detached the flight meanwhile, then handed to the
    flight's waiters. If `compute` raises, nothing is stored, the waiters wake to retry, and
    the exception propagates to this caller alone. Called without `_lock`.
    """
    try:
        value = compute()
    except BaseException:
        with _lock:
            _land(key, flight)
        flight.done.set()
        raise
    with _lock:
        if _land(key, flight):
            _memo[key] = value
            while len(_memo) > MAX_ENTRIES:
                _memo.popitem(last=False)
    flight.value, flight.ok = value, True
    flight.done.set()
    return value


def _get_or_compute(key: _Key, compute: Callable[[], object]) -> object:
    """The value for `key`, shared with every other caller: callers must copy it out."""
    me = threading.get_ident()
    while True:
        with _lock:
            if key in _memo:
                _memo.move_to_end(key)
                return _memo[key]
            flight = _flights.get(key)
            leading = flight is None
            if flight is None:
                flight = _flights[key] = _Flight()
            else:
                _join(flight, me)
        if leading:
            return _lead(key, flight, compute)
        try:
            flight.done.wait()
        finally:
            with _lock:
                del _waiting_on[me]
        if flight.ok:
            return flight.value
        # The leader raised; its exception is its own. Retry: hit, join a newer flight or lead.


def cached_by_data_version[**P, R](
    fn: Callable[Concatenate[Session, P], R],
) -> Callable[Concatenate[Session, P], R]:
    """Memoize `fn(session, *args, **kwargs)` per (fn, args, kwargs, database, data_version).

    Contract for every decorated function (C7):
    - It is pure: the result depends only on its arguments and on the live tables that
      `data_version` versions. Forecast-dependent code also takes
      `forecast_cache.fetched_at` as an argument, since `data_version` does not version it.
    - Arguments after the session are hashable (pass tuples, never lists), and date
      arguments are already resolved (never None). An unhashable argument raises TypeError.
    - The key holds the function object itself, so two functions never share entries,
      even nested functions or lambdas with the same `__qualname__`.
    - Every call returns a copy the caller may mutate: DataFrames/Series via `.copy()`,
      any other value via `copy.deepcopy`, on the first call and on every hit alike.
    - At most `MAX_ENTRIES` (256) values are kept per process; the least recently used
      entry is evicted first.
    - Single-flight per key: while one call computes a key, other calls for that key in
      this process wait for it and each get a copy of its value. Different keys compute in
      parallel, and a decorated function may call other decorated functions. If the
      computation raises, only its own caller sees the exception; nothing is stored, and
      each waiting call retries (one of them computes, the rest wait for it again). Retries
      run one at a time, so N concurrent calls of a computation that always fails run it
      up to N times in series, and the last of them waits about N times as long as one
      failure takes. Waiting has no timeout: a computation that hangs also hangs every call
      waiting for it. A call whose wait would close a cycle (a key needing itself) raises
      RuntimeError instead of deadlocking.
    """

    @functools.wraps(fn)
    def wrapper(session: Session, /, *args: P.args, **kwargs: P.kwargs) -> R:
        key: _Key = (
            fn,
            args,
            tuple(sorted(kwargs.items())),
            _database_name(session),
            read_data_version(session),
        )
        value = _get_or_compute(key, lambda: fn(session, *args, **kwargs))
        return cast(R, _copy_out(value))

    return wrapper
