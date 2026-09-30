from contact_sheet import build_sheet


def test_sheet_lists_every_candidate_with_its_select_command(tmp_path):
    for stem, seeds in {"clays_broken-gold": [202, 101], "doubleheader": [101]}.items():
        (tmp_path / stem).mkdir()
        for seed in seeds:
            (tmp_path / stem / f"{seed}.png").write_bytes(b"x")
    html = build_sheet(tmp_path)
    assert html.index("candidates/clays_broken-gold/101.png") < html.index("candidates/clays_broken-gold/202.png")
    assert "python cli.py select clays_broken gold 101" in html
    assert "python cli.py select doubleheader - 101" in html


def test_sheet_escapes_names(tmp_path):
    (tmp_path / "<b>x").mkdir()
    (tmp_path / "<b>x" / "1.png").write_bytes(b"x")
    html = build_sheet(tmp_path)
    assert "<b>x" not in html
    assert "&lt;b&gt;x" in html
