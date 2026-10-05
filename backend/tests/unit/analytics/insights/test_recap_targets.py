"""Busy-Sunday targets fix: per-shooter Clays Broken sentences, never the stored roll-up."""

from sunday_clays.analytics.recap_insights import milestone_sentences, recap_text_problems


def test_two_shooters_crossing_on_one_sunday_each_get_their_own_sentence(make_world, sun) -> None:
    world = (
        make_world()
        .shooter(1, "Hadley, Ike")
        .shooter(2, "Kaplan, Noel")
        .series(1, 0, [40] * 99 + [50])  # 3,960 + 50 = 4,010 on sunday(99)
        .series(2, 80, [50] * 19 + [60])  # 950 + 60 = 1,010 on sunday(99)
    )
    got = milestone_sentences(world.frames(), sun(99))
    assert got == [
        (1, "Ike Hadley has now broken 4,000 targets on Sundays: 4,010 in all."),
        (2, "Noel Kaplan has now broken 1,000 targets on Sundays: 1,010 in all."),
    ]
    assert not any("New thousand-target marks" in line for _, line in got)
    assert all(recap_text_problems(line) == [] for _, line in got)


def test_only_the_requested_sunday_is_reported(make_world, sun) -> None:
    world = make_world().series(1, 0, [40] * 26)  # 1,000 on sunday(24)
    fr = world.frames()
    assert milestone_sentences(fr, sun(25)) == []
    assert len(milestone_sentences(fr, sun(24))) == 1
