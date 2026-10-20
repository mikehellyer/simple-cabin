# Simple-Cabin

A wooden cabin in a forest beside a lake. Most of the time you're indoors in
the warm, with a crackling log fire and a **grandfather clock** that keeps the
real time, ticks every second and chimes the hours (Westminster Quarters, then
the hour strikes). Now and then the view drifts outside to the lake. The sky,
the light and the scenery follow the **real local weather and time of day**:
sun, cloud, fog, rain on the lake and the window glass, snow on the roof,
thunderstorms, a frozen lake in deep winter, and stars and the moon at night.

Press **W** for the weather screen: a big clock with the current conditions,
the next 12 hours and the week ahead.

## Keys

| Key | What it does |
| --- | --- |
| Space / Tab | Switch between inside and outside |
| I / O | Go inside / outside |
| W | Weather and big clock screen (W or Esc to go back) |
| F / F11, double-click | Full screen |
| M | Mute |
| C | Ring the hour chime now |
| P | Preview each kind of weather (cycles back to live) |
| T | Preview dawn / day / dusk / night (cycles back to live) |
| D | Preview the seasonal decorations (cycles back to today's) |
| Q | Show the phone remote's QR code |
| R | Refresh the weather now |
| S | Settings: location, units, volumes, quarter chimes, view timings |
| Right-click | All of the above as a menu |

To open straight into full screen, tick **Start in full screen** in
Settings → Views, or run `simple-cabin --fullscreen`.

## Remote controls

**TV remote (HDMI-CEC).** On Linux (e.g. a Raspberry Pi behind the TV) the
app registers with the TV over HDMI, so the TV's own remote works:

| Button | Does |
| --- | --- |
| ◀ ▶ | Inside / outside |
| OK | Weather and clock screen |
| Back | Back to the cabin |
| ▲ ▼ | Next / previous weather preview |
| Red | Mute |
| Green | Ring the chime |
| Yellow | Next time-of-day preview |
| Blue | Show the phone remote's QR code |

Needs `cec-ctl` (package `v4l-utils`, installed with the .deb) and a TV with
HDMI-CEC switched on (Samsung "Anynet+", LG "SimpLink", Sony "Bravia Sync",
Panasonic "VIERA Link"…). Bluetooth clickers and air-mouse remotes that send
arrow keys work the same way.

**Phone remote.** Turn on *Phone remote* in Settings → Remote controls and
scan the QR code (shown there, or on screen with **Q** / the blue button).
The page works in any phone browser on the same Wi-Fi: views, weather and
time-of-day previews, decorations, volume, mute, chime and full screen. It
can be protected with a PIN.

## Seasonal decorations

The cabin dresses up for the time of year: **Halloween** (17–31 October:
jack-o'-lanterns, bunting, a spider, bats), **Christmas** (1 December to
Twelfth Night: a lit tree, stockings, a garland, roof lights), **Easter**
(Palm Sunday to Easter Monday: egg bunting, daffodils, a bunny) and **New
Year** (31 December and 1 January: a banner, balloons, champagne, and
fireworks over the lake after dark on New Year's Eve). Turn them off in
Settings → Views.

## Screen saver

While Simple-Cabin is open it asks the system not to start the screen
saver, blank the screen or lock: on Linux over D-Bus (freedesktop
screensaver, the desktop portal or GNOME), on macOS with `caffeinate`, on
Windows with `SetThreadExecutionState`. It all stops when the app closes.
Turn it off in Settings → Views.

## Raspberry Pi

Each release includes `simple-cabin_X.Y.Z_arm64.deb` for **64-bit
Raspberry Pi OS** (Bookworm or newer) on a Pi 4 or Pi 5:

```bash
sudo apt install ./simple-cabin_X.Y.Z_arm64.deb
```

On a Pi the app switches to *Light* graphics automatically (drawn at lower
resolution and 20 fps). Settings → Views → Graphics can change that. If the
screen still blanks, turn off *Screen Blanking* in Raspberry Pi
Configuration → Display.

## If a remote control doesn't work

Run `simple-cabin --remote-test` in a terminal (on the Pi). It checks
HDMI-CEC (registers with the TV, lists what the TV reports, then shows
which remote buttons the TV actually sends while you press them for 15
seconds) and the phone remote (this machine's addresses, the port, and
whether the page answers on each address).

## If you can't hear something

Run `simple-cabin --sound-test` in a terminal. It says which audio output
it's using, then plays the fire, the ticking clock, a chime and thunder in
turn. (All sound goes out as one mixed stream, so if the fire can be heard,
so can everything else.)

## Weather and location

Weather comes from [Open-Meteo](https://open-meteo.com/) (free, no API key).
By default your rough location comes from your internet address (via
ipwho.is). To pick a town instead, open Settings and search. The last
forecast is cached, so the cabin still has weather after a restart while
you're offline.

## Sound

The clock's tick-tock is a real grandfather clock: four beats (strong, weak,
strong, weak) cut from a recording by `tools/extract_recorded_tick.py` and
kept in `src/simple_cabin/sounds/`. Settings → Clock voice also offers three
synthesised voices (Classic, Bold, Deep).

The fire is a real recording too: a 40-second seamless loop made by
`tools/extract_fire_loop.py`.

Everything else (the rain, the thunder and the Westminster chimes) is
synthesised with numpy the first time it's needed, then cached as WAV
files in the app's cache folder. The fire sits well under the clock by
default. Settings has separate sliders for each.

## Running from source

```bash
python3.12 -m venv venv
venv/bin/pip install -r requirements-dev.txt
venv/bin/pip install -e .
venv/bin/simple-cabin
```

Tests: `venv/bin/pytest`

## Packaging

Tagging `vX.Y.Z` builds installers for Linux (.deb), macOS (.dmg) and
Windows (Inno Setup .exe) in GitHub Actions and attaches them to a release.
The app checks GitHub Releases on startup and offers an **Update** button.
It never updates on its own.
