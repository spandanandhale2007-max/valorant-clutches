# Valorant Clutches and Aces

A Clips Kitty pipeline that finds Valorant multi-kills, aces and clutches in a VOD.

There is no official Valorant pipeline: the [Awesome Clips Kitty](https://github.com/ColinGPT9/awesome-clips-kitty) list has Valorant under **Wanted**, as an idea rather than a project. This is that idea, built from the SDK's `game-events` template.

## What it does

1. It looks at the kill feed's corner of the screen (`feed_region`) 4 times a second, shrunk to a few pixels, and notes every time that corner changes by at least `feed_change`. A banner slides in over several frames, so only the first time of each run counts: those are the **feed updates**.
2. Updates no more than `window_seconds` apart are one fight. A fight needs at least `kills_for_multikill` of them, and is called an **ace** at `kills_for_ace`.
3. The sound decides nothing by default, but a fight the microphone and the gunfire get louder in (`louder_by_db` above the half minute around it) scores higher. With `needs_loud`, a quiet fight is dropped instead.
4. What you say names the moment: a word from `words_ace` within 15 seconds makes it an **ace**, one from `words_clutch` makes it a **clutch**. Turn that off with `use_transcript`.
5. Each fight becomes a moment from `lead_seconds` before the first update to `tail_seconds` after the last, fitted to the clip lengths you chose. Clips Kitty then cuts, frames and captions the clips as it does for every video.

Moments are scored 0-100: more updates in the window score higher, a confirming word adds 15, a loud fight adds 10.

## What it can't see

**It counts changes in one corner of the picture, not kills.** It cannot read the feed's names or text, so all of these fool it:

- a HUD at another position or scale, an ultrawide monitor, or a stream with a border — point `feed_region` at your own layout with the `frame` command below
- a spectator, replay or theatre UI, which moves the feed
- an overlay, alert, chat box or webcam sitting in that corner
- a busy minimap or any other animation inside the region

And it misses a round whose feed never shows in view. **Ace** and **clutch** come from the rate of those changes and from what you said, never from the game's own state: it does not know the round score, who is alive, or whether the spike was defused. A round you narrate quietly and win 1v3 reads as a plain `multikill`; one where you say "clutch" while losing reads as a `clutch`.

## Settings

| Setting | Default | |
|---|---|---|
| `feed_region` | `0.62,0.08,0.37,0.20` | Where the kill feed shows, as left, top, width, height (0 to 1) |
| `feed_change` | 6 | How much that corner must change to count as a feed update (0 to 255) |
| `window_seconds` | 12 | How close together the updates must be to be one fight |
| `kills_for_multikill` | 3 | Feed updates in that window before it is a moment |
| `kills_for_ace` | 5 | Feed updates in that window before it is called an ace |
| `use_transcript` | true | Also use what the streamer says to name the moment |
| `words_ace` | `ace, aced, team ace, five for five` | Words that mean an ace |
| `words_clutch` | `clutch, clutched, 1v3, 1v4, 1v5, defuse, retake, last alive, ...` | Words that mean a clutch |
| `louder_by_db` | 6 | How much louder the sound must get to count as a gunfight (dB) |
| `needs_loud` | false | Only when the sound gets louder too |
| `lead_seconds` | 8 | Seconds kept before the first feed update |
| `tail_seconds` | 4 | Seconds kept after the last one |

The default `feed_region` is Valorant's kill feed on a 16:9 1080p HUD at default scale. Check it against your own footage before you trust the results.

## Try it

You need Python 3.11 (the Python Clips Kitty runs plugins on) and FFmpeg. In the plugin's folder, in PowerShell:

```powershell
py -m pip install "clipskitty-sdk[yaml,test] @ git+https://github.com/ColinGPT9/clips-studio#subdirectory=sdk/python"
py -m clipskitty_sdk validate .
py -m clipskitty_sdk run . --sample --set "feed_region=0.30,0.10,0.40,0.10" --set "feed_change=3" --set "kills_for_multikill=2"
py -m clipskitty_sdk frame "$env:USERPROFILE\Videos\match.mp4" --at 60 --region "0.62,0.08,0.37,0.20" --out ..\frame.png
py -m clipskitty_sdk run . --video "$env:USERPROFILE\Videos\match.mp4"
py -m pytest -q
```

`validate` checks `clipskitty.yaml` and the code the way Clips Kitty does. The sample video has no kill feed, so `run . --sample` points `feed_region` at the sample's red banner instead and treats it showing and going as a two-update fight; that proves the plugin runs, not that the tuning is right. **`frame` is the one that matters**: it writes a frame of your own match with a box around the region, so you can see whether the box is really on your kill feed, and prints the region in pixels. It writes outside this folder, because Clips Kitty copies everything in the folder when it installs it. For the same reason, if you use a virtual environment, make it next to this folder, not inside it. `pytest` runs `tests/test_main.py`.

### Tuning it on your own VOD

1. `frame` at a second you know had a kill, until the box sits on the feed. Save that as `feed_region`.
2. Run on a 10-minute clip of a real match and read the `notes` line: it says how many feed updates and how many fights were found. Far too many updates means `feed_change` is too low (something else in the region is moving); none means it is too high or the region is wrong.
3. Raise `kills_for_multikill` if ordinary trades become clips; lower `window_seconds` if two separate fights get joined.

## Use it in Clips Kitty

In a Clips Kitty that runs plugins ([which release does](https://github.com/ColinGPT9/clips-studio/blob/main/docs/developers/versioning.md#which-release-runs-plugins)), open **Marketplace › Browse**, choose **For developers: install a pipeline you're writing** at the bottom, and pick this folder. Then choose it as the **Pipeline** when you add a video.

Clips Kitty already knows Valorant as a shooter (`config/gaming.yaml`), so the vertical gaming layout applies with or without this plugin. What this adds is the moment finding.

## Share it

Push this folder to GitHub as its own repository. Its id, `spandanandhale2007-max/valorant-clutches`, starts with `spandanandhale2007-max`: for a Marketplace listing, that must be the GitHub name that owns the repository. `.github/workflows/clipskitty-check.yml` then checks it on Linux and Windows with Python 3.11 on every push. How to get it listed in the Marketplace: [Marketplace publishing](https://github.com/ColinGPT9/clips-studio/blob/main/docs/developers/marketplace-publishing.md).

## Files

```text
clipskitty.yaml        what Clips Kitty reads about the plugin: its inputs, outputs, permissions and settings
src/main.py            the plugin: Clips Kitty starts it with a job folder
tests/test_main.py     its tests, on the SDK's sample video
LICENSE                your licence for the plugin
TEMPLATE-LICENSE.txt   the MIT licence of the code that came from the template
```

The SDK's helpers and the job's contract: [SDK](https://github.com/ColinGPT9/clips-studio/blob/main/docs/developers/sdk.md).
