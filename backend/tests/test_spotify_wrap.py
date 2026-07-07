from app.screens.spotify import wrap_track


def test_wrap_preserves_word_order():
    # "If You Want" overflows line 1; everything after the break must stay in order
    line1, line2 = wrap_track("If You Want To", max_w=41)
    assert (line1 + " " + line2).strip() == "If You Want To"


def test_wrap_short_title_single_line():
    line1, line2 = wrap_track("Yesterday", max_w=41)
    assert line1 == "Yesterday"
    assert line2 == ""


def test_wrap_long_second_line_truncated():
    line1, line2 = wrap_track("Supercalifragilistic Expialidocious Extended Anniversary Mix", max_w=41)
    assert line2.endswith("..")
