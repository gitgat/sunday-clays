"""Overlay rules: typed payloads, creation with validation, deactivation, and loading (C5)."""

from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    SerializerFunctionWrapHandler,
    StringConstraints,
    ValidationError,
    model_serializer,
    model_validator,
)
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from sunday_clays.domain.diff import StagedScore, assign_ordinals
from sunday_clays.domain.errors import ConflictError, DomainError, NotFoundError
from sunday_clays.domain.identity import merge_map
from sunday_clays.domain.imports import active_scores_import
from sunday_clays.domain.round_type import RoundType
from sunday_clays.ingest import names
from sunday_clays.models import ImportScoreRow, Rule, Shooter
from sunday_clays.station_label import parse_label

NonEmpty = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
Score = Annotated[int, Field(ge=0, le=50)]


def _identity_key(key: str) -> str:
    """Accept only a key that identity_key(name_key(raw), event_date) could have produced.

    The lookup compares keys verbatim, so a raw spelling ("Hadley, Dik"), a one-token key without
    its "@YYYY-MM-DD" date, or a dated key of two or more tokens would never match a station row.
    """
    base = names.base_key(key)
    suffix = key[len(base) + 1 :]  # whatever follows the "@" base_key strips, if any
    try:
        day = date.fromisoformat(suffix)
    except ValueError:
        day = date.min  # no date: only a key of two or more tokens can still round-trip
    if base and names.name_key(base) == base and key == names.identity_key(base, day):
        return key
    raise ValueError(
        f"{key!r} is not an identity key: a normalized name_key, with '@YYYY-MM-DD' "
        "appended when it has one token"
    )


IdentityKey = Annotated[str, AfterValidator(_identity_key)]


class RuleType(StrEnum):
    MERGE_SHOOTER = "merge_shooter"
    RENAME_SHOOTER = "rename_shooter"
    SCORE_OVERRIDE = "score_override"
    HIDE_ROUND = "hide_round"
    ROUND_TYPE_OVERRIDE = "round_type_override"
    SET_STATUS = "set_status"
    STATION_RESET = "station_reset"
    ALIAS_NAME = "alias_name"


class _Payload(BaseModel):
    model_config = ConfigDict(extra="forbid")


class MergeShooterPayload(_Payload):
    source_shooter_id: int
    target_shooter_id: int


class RenameShooterPayload(_Payload):
    shooter_id: int
    display_name: NonEmpty


class ScoreOverridePayload(_Payload):
    event_date: date
    name_key: IdentityKey
    ordinal: Annotated[int, Field(ge=1)]
    raw_score: Score | None = None
    score: Score


class HideRoundPayload(_Payload):
    event_date: date
    name_key: IdentityKey
    ordinal: Annotated[int, Field(ge=1)]
    raw_score: Score | None = None


class RoundTypeOverridePayload(_Payload):
    event_date: date
    round_type: RoundType


class SetStatusPayload(_Payload):
    shooter_id: int
    status: Literal["member", "guest", "deceased"]


class StationResetPayload(_Payload):
    """`station` is a number or a label such as "7A"; `station_no` is the older int spelling.

    A payload is stored as given (never both keys), so earlier releases keep reading it.
    """

    station_no: Annotated[int, Field(ge=1)] | None = None
    station: int | str | None = None
    effective_date: date
    note: str

    @model_validator(mode="after")
    def _one_station(self) -> "StationResetPayload":
        if (self.station_no is None) == (self.station is None):
            raise ValueError("give the station as `station` (a number or label such as 7A)")
        if self.station is not None:
            label = parse_label(self.station)
            if label is None:
                raise ValueError(f"{self.station!r} is not a station number or label like 7A")
            self.station = label
        return self

    @model_serializer(mode="wrap")
    def _without_unset_station(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
        data: dict[str, Any] = handler(self)
        return {k: v for k, v in data.items() if not (k in ("station_no", "station") and v is None)}

    @property
    def label(self) -> str:
        return self.station if isinstance(self.station, str) else str(self.station_no)


class AliasNamePayload(_Payload):
    name_key: IdentityKey
    shooter_id: int


PAYLOAD_MODELS: dict[RuleType, type[_Payload]] = {
    RuleType.MERGE_SHOOTER: MergeShooterPayload,
    RuleType.RENAME_SHOOTER: RenameShooterPayload,
    RuleType.SCORE_OVERRIDE: ScoreOverridePayload,
    RuleType.HIDE_ROUND: HideRoundPayload,
    RuleType.ROUND_TYPE_OVERRIDE: RoundTypeOverridePayload,
    RuleType.SET_STATUS: SetStatusPayload,
    RuleType.STATION_RESET: StationResetPayload,
    RuleType.ALIAS_NAME: AliasNamePayload,
}


@dataclass(frozen=True)
class ActiveRules:
    """Active rules applied by rebuild_live (merge and alias_name are read by domain.identity).

    renames and statuses map a rule's shooter_id to (rule_id, value) of its newest rule; rebuild
    re-keys them through merge_map, where the highest rule_id wins across a merged set.
    """

    score_overrides: list[tuple[int, ScoreOverridePayload]]
    hides: list[tuple[int, HideRoundPayload]]
    renames: dict[int, tuple[int, str]]
    statuses: dict[int, tuple[int, str]]
    round_types: dict[date, tuple[int, RoundType]]


def _require_shooter(session: Session, shooter_id: int) -> None:
    if session.get(Shooter, shooter_id) is None:
        raise NotFoundError("shooter_not_found", f"Shooter {shooter_id} does not exist")


def _live_raw_score(session: Session, event_date: date, name_key: str, ordinal: int) -> int:
    """Raw score at the key in the active scores import, the value rebuild targeting compares.

    Ordinals rank rows within one (event_date, name_key), so that pair's rows alone give the
    ordinal keyed_rows assigns over the whole import. No committed import matches no row.
    """
    rows = [
        StagedScore(*row)
        for row in session.execute(
            select(
                ImportScoreRow.id,
                ImportScoreRow.row_number,
                ImportScoreRow.raw_name,
                ImportScoreRow.name_key,
                ImportScoreRow.event_date,
                ImportScoreRow.score,
                ImportScoreRow.status,
                ImportScoreRow.gauge_class,
            ).where(
                ImportScoreRow.import_id == active_scores_import(session),
                ImportScoreRow.event_date == event_date,
                ImportScoreRow.name_key == name_key,
            )
        )
    ]
    ordinals = assign_ordinals(rows)
    for row in rows:
        if ordinals[row.row_id] == ordinal:
            return row.score
    raise NotFoundError(
        "round_not_found", f"No round {ordinal} for {name_key!r} on {event_date.isoformat()}"
    )


def _checked(session: Session, model: _Payload) -> _Payload:
    if isinstance(model, MergeShooterPayload):
        if model.source_shooter_id == model.target_shooter_id:
            raise DomainError("invalid_rule", "A shooter cannot be merged into itself")
        _require_shooter(session, model.source_shooter_id)
        _require_shooter(session, model.target_shooter_id)
    elif isinstance(model, RenameShooterPayload | SetStatusPayload | AliasNamePayload):
        _require_shooter(session, model.shooter_id)
    elif isinstance(model, ScoreOverridePayload | HideRoundPayload) and model.raw_score is None:
        raw = _live_raw_score(session, model.event_date, model.name_key, model.ordinal)
        return model.model_copy(update={"raw_score": raw})
    return model


def create_rule(
    session: Session, rule_type: RuleType, payload: dict[str, Any], note: str | None
) -> int:
    """Validate and store an active rule; returns its id. Callers enqueue the rebuild."""
    try:
        kind = RuleType(rule_type)
        model = PAYLOAD_MODELS[kind].model_validate(payload)
    except ValidationError as exc:
        error = exc.errors()[0]
        field = ".".join(str(part) for part in error["loc"])
        raise DomainError("invalid_rule", f"{field}: {error['msg']}") from None
    except ValueError:
        raise DomainError("invalid_rule", f"Unknown rule type {rule_type!r}") from None
    model = _checked(session, model)
    with session.begin_nested():
        rule = Rule(rule_type=kind.value, payload=model.model_dump(mode="json"), note=note)
        session.add(rule)
        session.flush()
        if kind is RuleType.MERGE_SHOOTER:
            merge_map(session)  # raises DomainError("merge_cycle"); the savepoint drops the rule
    return rule.id


def deactivate_rule(session: Session, rule_id: int) -> None:
    """Deactivate a rule; refused when an older merge rule would come back and close a cycle."""
    rule = session.get(Rule, rule_id)
    if rule is None:
        raise NotFoundError("rule_not_found", f"Rule {rule_id} does not exist")
    if not rule.active:
        raise ConflictError("rule_not_active", f"Rule {rule_id} is already inactive")
    with session.begin_nested():  # a merge cycle rolls this back; the rule stays active
        rule.active = False
        rule.deactivated_at = func.now()
        session.flush()
        if rule.rule_type == RuleType.MERGE_SHOOTER:
            merge_map(session)  # newest-per-source: an older rule for this source may return


def load_active_rules(session: Session) -> ActiveRules:
    """Active rules in id order, so the newest rule wins wherever two target the same thing."""
    rules = ActiveRules([], [], {}, {}, {})
    for rule_id, rule_type, payload in session.execute(
        select(Rule.id, Rule.rule_type, Rule.payload).where(Rule.active.is_(True)).order_by(Rule.id)
    ):
        if rule_type == RuleType.SCORE_OVERRIDE:
            rules.score_overrides.append((rule_id, ScoreOverridePayload.model_validate(payload)))
        elif rule_type == RuleType.HIDE_ROUND:
            rules.hides.append((rule_id, HideRoundPayload.model_validate(payload)))
        elif rule_type == RuleType.RENAME_SHOOTER:
            rename = RenameShooterPayload.model_validate(payload)
            rules.renames[rename.shooter_id] = (rule_id, rename.display_name)
        elif rule_type == RuleType.SET_STATUS:
            status = SetStatusPayload.model_validate(payload)
            rules.statuses[status.shooter_id] = (rule_id, status.status)
        elif rule_type == RuleType.ROUND_TYPE_OVERRIDE:
            override = RoundTypeOverridePayload.model_validate(payload)
            rules.round_types[override.event_date] = (rule_id, override.round_type)
    return rules
