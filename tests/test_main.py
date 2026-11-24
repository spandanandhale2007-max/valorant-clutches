"""This plugin's tests. They run on your PC, never inside Clips Kitty:

    python -m pytest -q

They need the SDK's test extra (pip install "clipskitty-sdk[yaml,test]").
clipskitty_sdk.testing runs the plugin the way Clips Kitty would, on the
SDK's 40-second sample video, whose red banner shows at the top from 22 to
27 s with a loud sound, and whose transcript says "quark burst" there.
Valorant footage can't be shipped in a test, so the sample's banner stands in
for the kill feed: the tests point feed_region at it and the plugin counts it
changing exactly as it would count the feed. Without FFmpeg on PATH they are
skipped.
"""

from pathlib import Path

from clipskitty_sdk import samples, testing

PLUGIN = Path(__file__).resolve().parent.parent  # the folder holding clipskitty.yaml

# The sample's banner, in place of Valorant's kill feed, and a pair of
# changes (it shows, it goes) in place of a multi-kill.
BANNER = {"feed_region": "0.30,0.10,0.40,0.10", "feed_change": 3, "kills_for_multikill": 2}


def _run(tmp_path, **settings):
    video = testing.sample_video(tmp_path)  # skips the test without FFmpeg
    return testing.run_plugin(PLUGIN, video=video, transcript=samples.transcript_path(video),
                              settings={**BANNER, **settings}, tmp_path=tmp_path)


def test_a_burst_of_feed_changes_is_a_moment(tmp_path):
    run = _run(tmp_path)
    assert run.ok, run.error
    assert [m.label for m in run.moments] == ["multikill", "multikill"]
    # Scored above the floor, and the busier fight scores higher than the quieter one.
    assert run.moments[0].score > run.moments[1].score >= 40
    assert "the kill feed changes 3 times" in run.moments[0].reason
    assert "dB louder" in run.moments[0].reason


def test_the_moment_keeps_the_seconds_before_and_after(tmp_path):
    run = _run(tmp_path, lead_seconds=8, tail_seconds=4)
    assert run.ok, run.error
    first = run.moments[0]
    assert first.start < 22 < first.end  # the banner's own seconds are inside it


def test_what_the_streamer_says_makes_it_an_ace(tmp_path):
    run = _run(tmp_path, words_ace="quark burst")
    assert run.ok, run.error
    assert "ace" in [m.label for m in run.moments]
    assert 'the streamer says "quark burst"' in run.moments[0].reason


def test_what_the_streamer_says_makes_it_a_clutch(tmp_path):
    run = _run(tmp_path, words_ace="nothing said here", words_clutch="quark burst")
    assert run.ok, run.error
    assert "clutch" in [m.label for m in run.moments]


def test_enough_changes_at_once_is_an_ace_without_a_word(tmp_path):
    run = _run(tmp_path, words_ace="", words_clutch="", kills_for_ace=3)
    assert run.ok, run.error
    assert run.moments[0].label == "ace"


def test_ignoring_the_transcript_leaves_it_a_multikill(tmp_path):
    run = _run(tmp_path, use_transcript=False, words_ace="quark burst")
    assert run.ok, run.error
    assert [m.label for m in run.moments] == ["multikill", "multikill"]
    assert "the streamer says" not in run.moments[0].reason


def test_a_fight_without_a_loud_enough_sound_is_not_a_moment(tmp_path):
    run = _run(tmp_path, needs_loud=True, louder_by_db=30)
    assert run.ok, run.error
    assert run.moments == []
    assert "0 of them kept" in run.notes


def test_a_corner_that_never_changes_enough_finds_nothing(tmp_path):
    run = _run(tmp_path, feed_change=200)
    assert run.ok, run.error
    assert run.moments == []
    assert run.notes.startswith("The kill feed changes 0 time(s)")


def test_a_lone_change_is_not_a_fight(tmp_path):
    run = _run(tmp_path, kills_for_multikill=10)
    assert run.ok, run.error
    assert run.moments == []


def test_a_region_that_isnt_a_part_of_the_screen_fails(tmp_path):
    run = _run(tmp_path, feed_region="the top right bit")
    assert not run.ok
    assert "feed_region" in run.error
