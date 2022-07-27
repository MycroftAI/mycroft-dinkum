# <img src='https://raw.githack.com/FortAwesome/Font-Awesome/master/svgs/solid/play.svg' card_color='#22a7f0' width='50' height='50' style='vertical-align:bottom'/> Playback Control
Common playback control system

## About
This Skill doesn't do anything by itself, but it provides an important common
language for audio playback skills.  By handling simple phrases like
'pause', this one Skill can turn around and rebroadcast the [messagebus](https://mycroft.ai/documentation/message-bus/)
command `mycroft.audio.service.pause`, allowing several music services to share
common terminology such as "pause".

Additionally, this implements the common Play handler.  This allows playback
services to negotiate which is best suited to play back a specific request.
This capability is used by the [Spotify](https://github.com/forslund/spotify-skill) and [Pandora](https://github.com/mycroftai/pianobar-skill) Skills, among others.

## Examples
* "Play my summer playlist"
* "Play Pandora"
* "Pause"
* "Resume"
* "Next song"
* "Next track"
* "Previous track"
* "Previous song"

## Credits
Mycroft AI (@MycroftAI)

## Category
**Music**

## Tags
#music
#play
#playback
#pause
#resume
#next
#system
