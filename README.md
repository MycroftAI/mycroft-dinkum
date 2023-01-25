# Mycroft Dinkum

Mycroft Dinkum is a consumer ready version of Mycroft created specifically for the Mark II. It is a substantial refactoring of the Mycroft Core code into what we’ve dubbed Mycroft Dinkum (after the thinkum dinkum in The Moon is a Harsh Mistress). 

## Why?

Bugfixes and new features in the existing verions of Mycroft have been difficult due to the highly inter-connected nature of the code base. Doing so required significant breaking changes from previous versions of Mycroft, and we know that those versions are in use by a range of projects. 

At launch, Dinkum splits [Classic Core](https://github.com/mycroftai/mycroft-core) into services, and removes anything that does not support the default Skills on a Mark II. 

## Architecture of Dinkum

Dinkum breaks Core into distinct services:

* audio
    * Audio playback using SDL2 mixer
    * Music streaming using VLC
    * Text to speech using Mimic 3
* enclosure
    * Wi-Fi and pairing
* gui
    * QML-based interface
* intent
    * Intent registration and matching
    * Session management
* hal
    * LED animations
    * Buttons and switches
    * Volume
* messagebus
    * Websocket-based message broadcast
* skills
    * Each Skill is loaded as a separate service instance
* voice
    * Microphone input, silence detection, speech to text


---


## Services

Each Dinkum service is run as a systemd unit. The `sdnotify` Python package is used to inform systemd when the service has successfully started, and maintain a watchdog.

The `scripts/generate-systemd-units.py` script will write `.service` and `.target` files to `/etc/systemd/system` (sudo required). For example:

``` sh
cd mycroft-dinkum/
sudo scripts/generate-systemd-units.py \
        --user pi \
        --service 0 services/messagebus \
        --service 1 services/hal \
        --service 1 services/audio \
        --service 1 services/gui \
        --service 1 services/intent \
        --service 1 services/voice \
        --service 2 services/skills \
        --service 3 services/enclosure \
        --skill skills/alarm.mark2 \
        --skill skills/date.mark2 \
        --skill skills/fallback-query.mark2 \
        --skill skills/fallback-unknown.mark2 \
        --skill skills/homescreen.mark2 \
        --skill skills/ip.mark2 \
        --skill skills/news.mark2 \
        --skill skills/query-duck-duck-go.mark2 \
        --skill skills/query-wiki.mark2 \
        --skill skills/query-wolfram-alpha.mark2 \
        --skill skills/settings.mark2 \
        --skill skills/stop.mark2 \
        --skill skills/time.mark2 \
        --skill skills/timer.mark2 \
        --skill skills/volume.mark2 \
        --skill skills/weather.mark2
```

will start most of the default Services and Skills. The `--service` arguments have a priority number that controls the order the services will start. Higher numbers start *later*, and depend on the lower-numbered services. Skills will all start whenever `services/skills` is listed.

After generating systemd units, make sure to `sudo systemctl daemon-reload` and then you can `sudo systemctl start dinkum.target`

All logs go into journalctl, so they can be viewed in realtime with `sudo journalctl -f -xe`

You can also view individual Service or Skill logs:

* `sudo journalctl -f -u dinkum-audio.service`
* `sudo journalctl -f -u dinkum-skill-homescreen.mark2.service`

Leave off the `-f` to see the complete history of a service's log.

See `dinkum*` in `/etc/systemd/system` for available units. `dinkum.target` is the root unit.


---


## Sessions

A unique feature of Dinkum is sessions. These are managed by the intent service, and allow for centralized deconfliction of the GUI and TTS systems.

With sessions, Skill intent handlers change from:

``` python
def handle_intent(self):
    self.speak_dialog("my-dialog", data={"x": 1})
    self.gui["y"] = 2
    self.gui.show_page("my-page.qml")
```

to this:

``` python
def handle_intent(self):
    return self.end_session(
        dialog=("my-dialog", {"x": 1}),
        gui=("my-page.qml", {"y": 2})
    )
```

Rather than executing commands to control the GUI and TTS, the Skill is returning a message that expresses what it *wants* to do. The session manager (intent service) can then decide whether or not to do it.

A new session begins when an utterance is received, and is usually ended by a Skill's intent handler (`self.end_session()`). When the session is over, the GUI returns to the home screen after all TTS has been spoken.

Exceptions to the default flow include:

* Using `self.continue_session(expect_response=True)` to get a response from the user.
    * The Skill's `raw_utterance` method is called with the utterance
* Common Query/Play
    * The parent Skill uses `continue_session` and expects the child Skill to end it


---


## Skills

Each Skill is loaded and run individually by the `skills` Service. Skills have a `skill_id`, which is always the name of their code directory (e.g., `alarm.mark2` for `skills/alarm.mark2`).

The following core Skills are available:

* alarm.mark2
    * Can set alarms for specific times, or recurring, with an optional name
* date.mark2
    * Speaks the current date, or past/future dates
* fallback-query.mark2
    * Forwards questions to `query-*` skills
* fallback-unknown.mark2
    * Catches utterances that fail to match any other skill
    * Say "show me what I said" to see past utterances
* homescreen.mark2
    * The default (idle) screen
    * Shows the current time, date, weather, etc.
* ip.mark2
    * Reports the Mark II's IP address(es)
* news.mark2
    * Plays news broadcasts from various stations
* query-duck-duck-go.mark2
    * Forwards questions to DuckDuckGo
* query-wiki.mark2
    * Forwards questions to Wikipedia
* query-wolfram-alpha.mark2
    * Forwards questions to Wolfram Alpha
* settings.mark2
    * Shows settings GUI pages
* stop.mark2
    * Triggers `mycroft.stop` when user says "stop" (handled in intent service)
* time.mark2
    * Speaks the local time, or for other locations
* timer.mark2
    * Can set multiple timers, optionally with a name
* volume.mark2
    * Allows the user to change the volume or mute/unmute
* weather.mark2
    * Speaks the local weather forecast, or for other locations
