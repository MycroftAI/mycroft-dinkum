# Jukebox Skill 

## Play local music files on the Mark 2.

The Jukebox skill can play any common audio file (mp3, FLAC, Ogg Vorbis, WAV, etc.) 
which is located on any drive mounted to your Mycroft device. 

Files do not have to be placed in any particular directory; this skill will find
them automatically. They need not be organized in any particular way.

The Jukebox skill searches for audio files to play based on their metadata, not 
directory structures or file names. Most music files in the wild already have 
metadata for things like artist, track name, album, etc. Jukebox will search each 
of these for matches based on your command. For instance, you might say:

* Hey Mycroft, play The Beatles
* Hey Mycroft, play Here Comes the Sun

Currently, it is not recommended to use Jukebox with local STT turned on. 

If you have problems playing files which you know are on a connected drive, try
the following:

1) Reboot Mycroft. Sometimes when drives are inserted they are not immediately read.
2) Check your metadata. 
3) Say: "Hey Mycroft, show speech to text". This will show you how Mycroft 
    interpreted your last few utterances.

Mycroft Jukebox is an interface to the [Music Player Daemon (MPD)](https://www.musicpd.org/).

