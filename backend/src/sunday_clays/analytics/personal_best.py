"""The personal-best rule (C12), one source for the Sunday page's notables and the summary card
(Plan 19 D18). The insights milestone and the PB trophy keep their own copies; they are out of
Plan 19's scope and their tests pin the same 5."""

from typing import Final

PB_MIN_PRIOR_ROUNDS: Final = 5


def is_new_pb(score: int, previous_best: int | None, n_prior: int) -> bool:
    """A best round is a PB once at least 5 earlier rounds exist and it beats every one of them."""
    return n_prior >= PB_MIN_PRIOR_ROUNDS and previous_best is not None and score > previous_best
