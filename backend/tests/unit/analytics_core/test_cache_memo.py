import threading
import time
from collections.abc import Callable
from types import SimpleNamespace
from typing import Any, cast

import pandas as pd
import pytest

from sunday_clays.analytics import cache


class FakeSession:
    """Just enough of a Session for the memo key: bind URL database + data_version."""

    def __init__(self, database: str = "db1", data_version: int = 1) -> None:
        self.database = database
        self.data_version = data_version

    def get_bind(self) -> SimpleNamespace:
        url = SimpleNamespace(database=self.database)
        return SimpleNamespace(engine=SimpleNamespace(url=url))


@pytest.fixture(autouse=True)
def _fake_versions(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cache, "read_data_version", lambda s: s.data_version)


def _counted() -> tuple[list[int], Callable[..., pd.DataFrame]]:
    calls: list[int] = []

    @cache.cached_by_data_version
    def square(session: Any, x: Any) -> pd.DataFrame:
        calls.append(x)
        return pd.DataFrame({"x": [x * x]})

    return calls, square


def test_same_args_same_version_hits_memo() -> None:
    calls, square = _counted()
    assert square(FakeSession(), 3)["x"].tolist() == [9]
    assert square(FakeSession(), 3)["x"].tolist() == [9]
    assert calls == [3]


def test_new_data_version_or_database_or_args_recomputes() -> None:
    calls, square = _counted()
    square(FakeSession(), 3)
    square(FakeSession(data_version=2), 3)
    square(FakeSession(database="db1_fx"), 3)
    square(FakeSession(), 4)
    assert calls == [3, 3, 3, 4]


def test_returned_frames_are_copies() -> None:
    _, square = _counted()
    first = square(FakeSession(), 3)
    first.loc[0, "x"] = -1
    assert square(FakeSession(), 3)["x"].tolist() == [9]


def test_clear_cache_forces_recompute() -> None:
    calls, square = _counted()
    square(FakeSession(), 3)
    cache.clear_cache()
    square(FakeSession(), 3)
    assert calls == [3, 3]


def test_lru_evicts_oldest_beyond_256_entries() -> None:
    calls, square = _counted()
    for x in range(cache.MAX_ENTRIES + 1):
        square(FakeSession(), x)
    square(FakeSession(), cache.MAX_ENTRIES)  # newest: still cached
    square(FakeSession(), 0)  # oldest: evicted, recomputed
    assert calls.count(cache.MAX_ENTRIES) == 1
    assert calls.count(0) == 2


def test_scalar_values_round_trip() -> None:
    @cache.cached_by_data_version
    def label(session: Any, x: int) -> str:
        return f"v{x}"

    assert label(FakeSession(), 2) == "v2"
    assert label(FakeSession(), 2) == "v2"


def test_unhashable_argument_is_rejected() -> None:
    _, square = _counted()
    with pytest.raises(TypeError):
        square(FakeSession(), [1, 2])


def test_same_qualname_functions_never_share_entries() -> None:
    calls_a, square_a = _counted()
    calls_b, square_b = _counted()
    assert square_a.__qualname__ == square_b.__qualname__

    square_a(FakeSession(), 3)
    square_b(FakeSession(), 3)

    assert (calls_a, calls_b) == ([3], [3])


def test_container_values_are_independent_deep_copies() -> None:
    @cache.cached_by_data_version
    def table(session: Any, x: int) -> dict[str, list[int]]:
        return {"xs": [x]}

    first = table(FakeSession(), 1)
    first["xs"].append(99)
    second = table(FakeSession(), 1)
    second["xs"].append(98)

    assert first is not second
    assert table(FakeSession(), 1) == {"xs": [1]}


# --- single-flight: concurrent misses for one key share one computation ------------------------

TIMEOUT_S = 5.0  # only reached when a test is failing; every wait below is event-driven


class _Call:
    """`target()` run in a daemon thread, keeping its result or exception for the test."""

    def __init__(self, target: Callable[[], object]) -> None:
        self.result: object = None
        self.error: BaseException | None = None
        self._thread = threading.Thread(target=self._run, args=(target,), daemon=True)
        self._thread.start()

    def _run(self, target: Callable[[], object]) -> None:
        try:
            self.result = target()
        except BaseException as exc:
            self.error = exc

    def join(self) -> "_Call":
        self._thread.join(TIMEOUT_S)
        assert not self._thread.is_alive(), "call still blocked after the timeout (deadlock?)"
        return self


def _wait_until(condition: Callable[[], bool]) -> None:
    deadline = time.monotonic() + TIMEOUT_S
    while not condition():
        assert time.monotonic() < deadline, "condition never became true"
        time.sleep(0.001)


def _blocked_callers() -> int:
    """How many callers are waiting on another caller's in-flight computation right now."""
    with cache._lock:
        return len(cache._waiting_on)


def _gated() -> tuple[list[int], threading.Event, threading.Event, Callable[..., pd.DataFrame]]:
    """A memoized function whose calls report entry, then block until `release` is set."""
    calls: list[int] = []
    entered, release = threading.Event(), threading.Event()

    @cache.cached_by_data_version
    def slow_square(session: Any, x: int) -> pd.DataFrame:
        calls.append(x)
        entered.set()
        assert release.wait(TIMEOUT_S)
        return pd.DataFrame({"x": [x * x]})

    return calls, entered, release, slow_square


def test_concurrent_misses_for_one_key_compute_once() -> None:
    calls, entered, release, slow_square = _gated()
    leader = _Call(lambda: slow_square(FakeSession(), 3))
    assert entered.wait(TIMEOUT_S)
    followers = [_Call(lambda: slow_square(FakeSession(), 3)) for _ in range(7)]
    _wait_until(lambda: _blocked_callers() == len(followers))

    release.set()
    results = [call.join() for call in [leader, *followers]]

    assert calls == [3]
    assert [call.error for call in results] == [None] * 8
    frames = [cast(pd.DataFrame, call.result) for call in results]
    assert all(frame["x"].tolist() == [9] for frame in frames)
    assert len({id(frame) for frame in frames}) == 8  # every caller owns its copy
    assert cache._flights == {}
    assert _blocked_callers() == 0


def test_different_keys_compute_concurrently() -> None:
    both_inside = threading.Barrier(2, timeout=TIMEOUT_S)

    @cache.cached_by_data_version
    def meet(session: Any, x: int) -> int:
        both_inside.wait()  # passes only while both keys are computing at the same time
        return x * 10

    first = _Call(lambda: meet(FakeSession(), 1))
    second = _Call(lambda: meet(FakeSession(), 2))

    assert (first.join().error, second.join().error) == (None, None)
    assert (first.result, second.result) == (10, 20)


def test_failed_computation_raises_for_its_caller_and_waiters_retry() -> None:
    calls: list[int] = []
    entered, release = threading.Event(), threading.Event()

    @cache.cached_by_data_version
    def flaky(session: Any, x: int) -> int:
        calls.append(x)
        if len(calls) == 1:
            entered.set()
            assert release.wait(TIMEOUT_S)
            raise ValueError("boom")
        return x * 10

    leader = _Call(lambda: flaky(FakeSession(), 4))
    assert entered.wait(TIMEOUT_S)
    followers = [_Call(lambda: flaky(FakeSession(), 4)) for _ in range(3)]
    _wait_until(lambda: _blocked_callers() == len(followers))

    release.set()

    assert isinstance(leader.join().error, ValueError)
    assert [(f.join().error, f.result) for f in followers] == [(None, 40)] * 3
    assert calls == [4, 4]  # the failure, then one retry shared by every waiter
    assert flaky(FakeSession(), 4) == 40
    assert calls == [4, 4]
    assert cache._flights == {}


def test_an_always_failing_computation_runs_once_per_caller_in_series() -> None:
    """The documented retry bound: N callers of a computation that always fails run it N
    times, one at a time (the rest wait each time), and each caller gets its own exception."""
    gates: list[threading.Event] = []

    @cache.cached_by_data_version
    def broken(session: Any, x: int) -> int:
        gate = threading.Event()
        gates.append(gate)
        attempt = len(gates)
        assert gate.wait(TIMEOUT_S)
        raise ValueError(f"attempt {attempt}")

    n = 4
    callers = [_Call(lambda: broken(FakeSession(), 1)) for _ in range(n)]

    def at_attempt(i: int) -> Callable[[], bool]:
        return lambda: len(gates) == i and _blocked_callers() == n - i

    for i in range(1, n + 1):
        _wait_until(at_attempt(i))  # attempt i runs alone; the other n - i callers wait for it
        with cache._lock:
            assert len(cache._flights) == 1
        gates[-1].set()

    errors = [call.join().error for call in callers]
    assert all(isinstance(error, ValueError) for error in errors)
    assert sorted(map(str, errors)) == [f"attempt {i}" for i in range(1, n + 1)]
    assert len(gates) == n
    assert cache._flights == {}
    assert _blocked_callers() == 0


def test_a_failure_is_never_cached() -> None:
    attempts: list[int] = []

    @cache.cached_by_data_version
    def fails_once(session: Any, x: int) -> int:
        attempts.append(x)
        if len(attempts) == 1:
            raise ValueError("transient")
        return x

    with pytest.raises(ValueError, match="transient"):
        fails_once(FakeSession(), 5)
    assert fails_once(FakeSession(), 5) == 5
    assert attempts == [5, 5]
    assert cache._flights == {}


def test_nested_memoized_calls_share_flights_without_deadlock() -> None:
    inner_calls, entered, release, inner = _gated()
    outer_calls: list[int] = []

    @cache.cached_by_data_version
    def outer(session: Any, x: int) -> int:
        outer_calls.append(x)
        return int(inner(session, x)["x"].iloc[0]) + 1

    leader = _Call(lambda: outer(FakeSession(), 2))  # leads outer(2), then inner(2)
    assert entered.wait(TIMEOUT_S)
    outer_waiter = _Call(lambda: outer(FakeSession(), 2))
    inner_waiter = _Call(lambda: inner(FakeSession(), 2))
    _wait_until(lambda: _blocked_callers() == 2)

    release.set()

    assert (leader.join().result, outer_waiter.join().result) == (5, 5)
    assert cast(pd.DataFrame, inner_waiter.join().result)["x"].tolist() == [4]
    assert (outer_calls, inner_calls) == ([2], [2])


def test_reentering_the_same_key_raises_instead_of_deadlocking() -> None:
    depth: list[int] = []

    @cache.cached_by_data_version
    def recursive(session: Any, x: int) -> int:
        depth.append(x)
        if len(depth) == 1:
            return recursive(session, x) + 1  # same key, same thread
        return x

    call = _Call(lambda: recursive(FakeSession(), 7)).join()

    assert isinstance(call.error, RuntimeError)
    assert "waits on itself" in str(call.error)
    assert cache._flights == {}
    assert recursive(FakeSession(), 7) == 7  # the key is not poisoned


def test_a_cycle_across_threads_raises_instead_of_deadlocking() -> None:
    both_leading = threading.Barrier(2, timeout=TIMEOUT_S)
    entries: list[str] = []

    @cache.cached_by_data_version
    def f(session: Any, x: int) -> int:
        entries.append("f")
        if entries.count("f") == 1:
            both_leading.wait()
        return g(session, x) + 1

    @cache.cached_by_data_version
    def g(session: Any, x: int) -> int:
        entries.append("g")
        if entries.count("g") == 1:
            both_leading.wait()
        return f(session, x) + 1

    via_f = _Call(lambda: f(FakeSession(), 1))
    via_g = _Call(lambda: g(FakeSession(), 1))

    for call in (via_f.join(), via_g.join()):
        assert isinstance(call.error, RuntimeError)
        assert "waits on itself" in str(call.error)
    assert cache._flights == {}
    assert _blocked_callers() == 0


def test_clear_cache_detaches_a_computation_already_in_flight() -> None:
    calls: list[int] = []
    entered, release = threading.Event(), threading.Event()

    @cache.cached_by_data_version
    def versioned(session: Any, x: int) -> str:
        calls.append(x)
        if len(calls) == 1:
            entered.set()
            assert release.wait(TIMEOUT_S)
            return "before clear"
        return "after clear"

    stale = _Call(lambda: versioned(FakeSession(), 1))
    assert entered.wait(TIMEOUT_S)
    waiter = _Call(lambda: versioned(FakeSession(), 1))  # joins the flight before the clear
    _wait_until(lambda: _blocked_callers() == 1)
    cache.clear_cache()

    fresh = _Call(lambda: versioned(FakeSession(), 1)).join()  # never joins the stale flight
    release.set()

    assert (stale.join().result, fresh.result) == ("before clear", "after clear")
    assert waiter.join().result == "before clear"  # a detached flight still serves its waiters
    assert versioned(FakeSession(), 1) == "after clear"  # the stale value was never stored
    assert calls == [1, 1]
    assert cache._flights == {}
    assert _blocked_callers() == 0


def test_lru_eviction_while_a_key_is_in_flight_leaves_that_key_alone(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(cache, "MAX_ENTRIES", 2)
    calls: list[int] = []
    entered, release = threading.Event(), threading.Event()

    @cache.cached_by_data_version
    def square(session: Any, x: int) -> list[int]:
        calls.append(x)
        if x == 0:
            entered.set()
            assert release.wait(TIMEOUT_S)
        return [x * x]

    def stored_args() -> list[object]:
        """The memo's args, least recently used first."""
        with cache._lock:
            return [key[1] for key in cache._memo]

    leader = _Call(lambda: square(FakeSession(), 0))
    assert entered.wait(TIMEOUT_S)
    waiter = _Call(lambda: square(FakeSession(), 0))
    _wait_until(lambda: _blocked_callers() == 1)

    for x in (1, 2, 3, 4):  # fill the memo and evict around the in-flight key 0
        assert square(FakeSession(), x) == [x * x]
    assert stored_args() == [(3,), (4,)]
    assert (len(cache._flights), _blocked_callers()) == (1, 1)  # key 0 is still in flight

    release.set()

    assert (leader.join().result, waiter.join().result) == ([0], [0])
    assert stored_args() == [(4,), (0,)]  # 0 lands as the newest entry; 3, the oldest, goes
    assert (square(FakeSession(), 0), square(FakeSession(), 4)) == ([0], [16])  # hits
    assert square(FakeSession(), 3) == [9]  # evicted, so computed again
    assert calls == [0, 1, 2, 3, 4, 3]
    assert stored_args() == [(4,), (3,)]
    assert cache._flights == {}
    assert _blocked_callers() == 0


def test_a_waiter_of_a_finished_flight_does_not_count_as_blocked() -> None:
    """A thread woken by a finished flight but not yet deregistered closes no cycle."""
    me = threading.get_ident()
    woken = me + 1  # stands for another thread (a misaligned pthread id, so never a live one)
    finished = cache._Flight(owner=me)
    finished.done.set()
    target = cache._Flight(owner=woken)
    try:
        with cache._lock:
            cache._waiting_on[woken] = finished
            cache._join(target, me)
            assert cache._waiting_on[me] is target
    finally:
        with cache._lock:
            cache._waiting_on.pop(woken, None)
            cache._waiting_on.pop(me, None)
