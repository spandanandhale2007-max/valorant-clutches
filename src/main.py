"""A Clips Kitty pipeline that finds Valorant multi-kills, aces and clutches.

Made from the game-events template of the Clips Kitty SDK.

1. It looks at the kill feed's corner of the screen (feed_region) 4 times a
   second, shrunk to a few pixels, and keeps the times that corner changes by
   at least feed_change. One banner sliding in spans several frames, so only
   the first of each run counts: those times are the feed updates.
2. Updates no more than window_seconds apart are one fight. A fight needs at
   least kills_for_multikill of them, and is called an ace at
   kills_for_ace.
3. With needs_loud, a fight counts only when the sound is at least
   louder_by_db louder than the half minute around it; either way a louder
   fight scores higher.
4. What the streamer says names the moment: words_ace makes it an ace,
   words_clutch makes it a clutch, when said within 15 seconds of the fight.
5. Each becomes a moment from lead_seconds before the first update to
   tail_seconds after the last, fitted to the clip lengths the creator chose.

It counts changes in one corner of the picture, not kills. It cannot read the
feed's names or text, so a HUD at another position or scale, a spectator or
replay UI, an overlay or a webcam in that corner, and a busy minimap all fool
it; a round whose feed never shows in view is missed. Ace and clutch are
named from the rate of those changes and from what is said, never from the
game's own state.

Clips Kitty runs it on its own Python, which has the Python standard library
and clipskitty_sdk and nothing else, so import only those, at the top of the
file. To try it, run `python -m clipskitty_sdk run . --sample` in the
plugin's folder (`py -m clipskitty_sdk` in PowerShell); it needs FFmpeg.
"""

from __future__ import annotations

import statistics

from clipskitty_sdk import media, run, signals, text

# ---- tuning that is not worth a setting -------------------------------------------------
FRAMES_PER_SECOND = 4        # how often to look at the kill feed
SAME_UPDATE_SECONDS = 0.75   # changes this close together are one banner, not two
SAID_NEAR_SECONDS = 15.0     # how far from a fight a word still describes it
# -----------------------------------------------------------------------------------------


def feed_updates(job, region, threshold: float) -> list[float]:
    """The second of each change in the kill feed's corner of the screen."""
    changed: list[float] = []
    previous = None
    for frame in media.frames(job, fps=FRAMES_PER_SECOND, region=region):
        if previous is not None and signals.difference(previous, frame) >= threshold:
            changed.append(frame.t)
        previous = frame
    # A banner slides in over several frames: keep the first time of each run.
    return [first for first, _ in signals.stretches(changed, gap=SAME_UPDATE_SECONDS, min_length=0)]


def fights(updates: list[float], window: float, least: int) -> list[tuple[float, float, int]]:
    """(first, last, how many) for each run of updates inside one window of
    `window` seconds holding at least `least` of them. Runs don't overlap:
    the longest one from each starting update is taken, then counting goes on
    after its end."""
    out: list[tuple[float, float, int]] = []
    i = 0
    while i < len(updates):
        last = i
        while last + 1 < len(updates) and updates[last + 1] - updates[i] <= window:
            last += 1
        if last - i + 1 >= least:
            out.append((updates[i], updates[last], last - i + 1))
            i = last + 1
        else:
            i += 1
    return out


def _near(said: list[tuple[float, float, str]], start: float, end: float) -> list[str]:
    """The words of `said` spoken within SAID_NEAR_SECONDS of start..end."""
    seen: list[str] = []
    for at, until, word in said:
        if until >= start - SAID_NEAR_SECONDS and at <= end + SAID_NEAR_SECONDS and word not in seen:
            seen.append(word)
    return seen


def main(job):
    try:
        region = media.Region.parse(job.settings.get("feed_region", "0.62,0.08,0.37,0.20"))
    except ValueError as e:
        job.fail(f"The feed_region setting isn't a part of the screen: {e}")
    threshold = float(job.settings.get("feed_change", 6))
    window = float(job.settings.get("window_seconds", 12))
    least = int(job.settings.get("kills_for_multikill", 3))
    for_ace = int(job.settings.get("kills_for_ace", 5))
    louder_by = float(job.settings.get("louder_by_db", 6))
    needs_loud = bool(job.settings.get("needs_loud", False))
    lead = float(job.settings.get("lead_seconds", 8))
    tail = float(job.settings.get("tail_seconds", 4))
    use_said = bool(job.settings.get("use_transcript", True)) and job.transcript is not None

    job.progress(0.1, "Watching the kill feed")
    updates = feed_updates(job, region, threshold)
    rounds = fights(updates, window, least)

    job.progress(0.7, "Listening for the gunfights")
    loudness = media.loudness(job) if rounds else []
    loud = set(signals.spikes(loudness, louder_by=louder_by))
    usual = statistics.median(loudness) if loudness else 0.0

    said_ace: list[tuple[float, float, str]] = []
    said_clutch: list[tuple[float, float, str]] = []
    if use_said and rounds:
        job.progress(0.85, "Reading what was said")
        said_ace = text.said(job, text.words_of(job.settings.get("words_ace", "")))
        said_clutch = text.said(job, text.words_of(job.settings.get("words_clutch", "")))

    found = 0
    for start, end, count in rounds:
        # The loud seconds from the second before the fight to the second after it.
        heard = [second for second in range(int(start) - 1, int(end) + 2)
                 if 0 <= second < len(loudness) and second in loud]
        if needs_loud and not heard:
            continue
        ace_words = _near(said_ace, start, end)
        clutch_words = _near(said_clutch, start, end)

        if count >= for_ace or ace_words:
            label = "ace"
        elif clutch_words:
            label = "clutch"
        else:
            label = "multikill"

        reason = f"the kill feed changes {count} times in {end - start:g} s"
        if heard:
            reason += f", and the sound gets {max(loudness[s] for s in heard) - usual:.0f} dB louder"
        words = ace_words if label == "ace" else clutch_words
        if words:
            reason += f', and the streamer says "{words[0]}"'

        score = 40 + 8 * (count - least)
        if ace_words or clutch_words:
            score += 15
        if heard:
            score += 10
        score = max(0.0, min(100.0, float(score)))

        first, last = signals.around(job, start, end, lead=lead, tail=tail)
        job.add_range(first, last, score=score, label=label, reason=reason)
        found += 1

    notes = (f"The kill feed changes {len(updates)} time(s): {len(rounds)} fight(s) of "
             f"{least} or more within {window:g} s, {found} of them kept.")
    job.finish(notes=notes)


if __name__ == "__main__":
    run(main)
