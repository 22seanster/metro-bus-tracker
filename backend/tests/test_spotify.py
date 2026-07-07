from app.providers.spotify import NowPlaying, device_allowed, normalize_playback, select_playing

PLAYBACK = {
    "is_playing": True,
    "device": {"name": "Kitchen Speaker", "type": "Speaker"},
    "item": {
        "name": "Texas Sun",
        "artists": [{"name": "Khruangbin"}, {"name": "Leon Bridges"}],
        "album": {
            "name": "Texas Sun",
            "images": [
                {"url": "https://img/640", "width": 640, "height": 640},
                {"url": "https://img/300", "width": 300, "height": 300},
                {"url": "https://img/64", "width": 64, "height": 64},
            ],
        },
    },
}


def test_normalize_playback():
    np = normalize_playback("sean", PLAYBACK)
    assert np.account == "sean"
    assert np.track == "Texas Sun"
    assert np.artists == "Khruangbin, Leon Bridges"
    assert np.device_name == "Kitchen Speaker"
    assert np.is_playing is True
    assert np.art_url == "https://img/64"  # smallest image


def test_normalize_playback_handles_nothing_playing():
    assert normalize_playback("sean", None) is None
    assert normalize_playback("sean", {"is_playing": False, "item": None}) is None


def test_device_allowed_empty_allowlist_allows_all():
    assert device_allowed("Anything", [])


def test_device_allowed_matches_case_insensitive_substring():
    allow = ["kitchen speaker", "Living Room TV"]
    assert device_allowed("Kitchen Speaker", allow)
    assert device_allowed("LIVING ROOM TV (2)", allow)
    assert not device_allowed("Sean's iPhone", allow)


def _np(account, device="Kitchen Speaker"):
    return NowPlaying(account=account, track="t", artists="a", art_url="u",
                      device_name=device, is_playing=True)


def test_select_playing_prefers_config_order():
    states = {"sean": _np("sean"), "wife": _np("wife")}
    got = select_playing(["sean", "wife"], states, allowlist=[])
    assert got.account == "sean"


def test_select_playing_skips_disallowed_device():
    states = {"sean": _np("sean", device="Sean's iPhone"), "wife": _np("wife")}
    got = select_playing(["sean", "wife"], states, allowlist=["Kitchen"])
    assert got.account == "wife"


def test_select_playing_none_when_nobody_home():
    states = {"sean": None, "wife": _np("wife", device="Car")}
    assert select_playing(["sean", "wife"], states, allowlist=["Kitchen"]) is None
