"""Club-event copy never uses he/she/his/her/him/hers/himself/herself or "class" (Plan 20 §5.8,
owner rules), checked with the insights lint codes Plan 19 reuses (`lint_text`). Pronouns are
checked on the whole source; "class" on string literals only (not docstrings), since Python's
`class` keyword is not copy. The globs pick up every club-event module as later tasks add them."""

import ast
from pathlib import Path

from sunday_clays.analytics.insights.lints import lint_text

SRC = Path(__file__).resolve().parents[2] / "src" / "sunday_clays"
BANNED_CODES = ("pronoun", "class")


def _files() -> list[Path]:
    found = {*SRC.glob("**/*club_event*.py"), *SRC.glob("api/routes/admin_shooter_contacts.py")}
    return sorted(found)


def _literals(source: str) -> list[str]:
    """Every string literal (f-string parts included) except docstrings."""
    tree = ast.parse(source)
    docstrings = {
        id(node.body[0].value)
        for node in ast.walk(tree)
        if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef)
        and node.body
        and isinstance(node.body[0], ast.Expr)
        and isinstance(node.body[0].value, ast.Constant)
    }
    return [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and id(node) not in docstrings
    ]


def _problems(source: str) -> list[str]:
    found = [p for p in lint_text(source, named=False) if p.startswith("pronoun")]
    for text in _literals(source):
        found += [p for p in lint_text(text, named=False) if p.startswith(BANNED_CODES)]
    return found


def test_club_event_copy_never_uses_gendered_pronouns_or_class() -> None:
    files = _files()
    assert SRC / "domain" / "club_events.py" in files
    found = {f.name: _problems(f.read_text(encoding="utf-8")) for f in files}
    assert {name: problems for name, problems in found.items() if problems} == {}


def test_the_lint_used_here_catches_both_words() -> None:
    # Kills a mutation that filters on the wrong codes or skips the literals.
    assert _problems('MESSAGE = "Her spot"\n')
    assert _problems('MESSAGE = f"A class of {n} shooters"\n')
    assert not _problems('class Row:\n    """A row class."""\n')
