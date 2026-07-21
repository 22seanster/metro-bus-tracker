"""The bundled bitmap fonts are latin-1 only, so PIL raises UnicodeEncodeError on
anything above U+00FF. Spotify returns curly apostrophes and en-dashes in a large
share of real track titles, which made those tracks crash mid-render and silently
fall back to the clock screen.

Text is sanitised in the draw helpers rather than at the provider: the constraint
belongs to the font, so every present and future screen gets it for free.
"""

from datetime import datetime, timezone

import pytest
from PIL import Image, ImageDraw

from app import fonts
from app.providers.spotify import NowPlaying
from app.screens.spotify import SpotifyScreen
from app.textdraw import draw_marquee, draw_scaled_text, safe_text, text_width

NOW = datetime(2026, 7, 20, 20, 0, tzinfo=timezone.utc)
CURLY = "Don’t Stop Me Now"          # U+2019 right single quote
ENDASH = "Sigur Rós – Hopp"     # U+2013 en dash
DECOMPOSED = "Beyoncé"              # e + U+0301 combining acute
CJK = "あいう"                # あいう


@pytest.mark.parametrize("text", [CURLY, ENDASH, DECOMPOSED, CJK, "Motörhead", "Beyoncé"])
def test_measuring_never_raises(text):
    assert text_width(text, fonts.tiny()) >= 0


@pytest.mark.parametrize("text", [CURLY, ENDASH, DECOMPOSED, CJK])
def test_drawing_never_raises(text):
    img = Image.new("RGB", (64, 32))
    draw_marquee(img, (22, 11), text, fonts.tiny(), (255, 255, 255), 41)
    draw_scaled_text(img, (0, 0), text, fonts.tiny(), (255, 255, 255))


def test_smart_punctuation_becomes_its_ascii_equivalent():
    assert safe_text(CURLY) == "Don't Stop Me Now"
    assert safe_text("“Quoted”") == '"Quoted"'
    assert safe_text("a — b") == "a - b"
    assert safe_text("…") == "..."


def test_accents_survive_when_the_font_can_show_them():
    """latin-1 covers these, so they must not be flattened to ASCII."""
    assert safe_text("Motörhead") == "Motörhead"
    assert safe_text("Beyoncé") == "Beyoncé"
    assert safe_text(DECOMPOSED) == "Beyoncé"  # composed, not mangled


def test_unrenderable_accents_degrade_to_the_base_letter():
    assert safe_text("Sigur Rōs") == "Sigur Ros"  # ō -> o, not '?'


def test_untranslatable_text_degrades_rather_than_crashing():
    out = safe_text(CJK)
    assert len(out) == 3 and "あ" not in out


def test_ascii_is_returned_unchanged():
    assert safe_text("Texas Sun") == "Texas Sun"
    assert safe_text("") == ""


# --- the actual user-visible symptom -----------------------------------------


class Stub:
    def __init__(self, np):
        self._np = np

    def snapshot(self):
        return self._np

    def is_stale(self):
        return False


def test_track_with_a_curly_apostrophe_actually_renders():
    """Before the fix this raised inside render(), the engine caught it, and the
    track silently showed the clock instead."""
    np = NowPlaying(account="sean", track=CURLY, artists="Queen", art_url="u",
                    device_name="HomePod", is_playing=True, art=None)
    screen = SpotifyScreen(dwell_seconds=15, provider=Stub(np))

    assert screen.frame_interval_ms(NOW) == 50  # long -> scrolls, and doesn't raise
    img = Image.new("RGB", (64, 32))
    screen.render(img, ImageDraw.Draw(img), NOW, 2.0)
    assert sum(1 for v in img.convert("L").tobytes() if v) > 30  # text really drawn
