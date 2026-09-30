import pytest

from sunday_clays.api.routes.admin_imports import clean_filename


@pytest.mark.parametrize(
    ("raw", "cleaned"),
    [
        ("a\x00b.xlsx", "ab.xlsx"),  # NUL: PostgreSQL text rejects it (500 before the fix)
        ("a\x1b[31mb.xlsx", "a[31mb.xlsx"),  # terminal escape
        ("\u202eabc.xlsx", "abc.xlsx"),  # RIGHT-TO-LEFT OVERRIDE (Cf)
        ("a\nb.xlsx", "ab.xlsx"),  # newline (Cc)
        ("a\u2028b\u00a0c.xlsx", "abc.xlsx"),  # line separator (Zl), non-ASCII space (Zs)
        ("abc.xlsx \x00", "abc.xlsx"),  # dropped before stripping, so the suffix survives
        ("\u202e abc.xlsx", "abc.xlsx"),
        ("dir/\x07sub\\Station\tScores.xlsx", "StationScores.xlsx"),
    ],
)
def test_clean_filename_drops_non_printable_characters(raw: str, cleaned: str) -> None:
    assert clean_filename(raw) == cleaned


@pytest.mark.parametrize("raw", [None, "", "\x00\u202e\n", " \x1b "])
def test_clean_filename_of_nothing_printable_is_empty(raw: str | None) -> None:
    # "" fails the suffix check, so the upload is refused with 400 unsupported_file_type.
    assert clean_filename(raw) == ""
