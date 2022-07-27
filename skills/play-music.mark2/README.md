# skill-music-demo

A simple demo of music on the Mark II

If you specifiy an artist and song you should get 
the song. If you just specifiy an artist, sometimes
you get a playlist which takes a bit to download 
and convert (an hour and a half Joe Cocker playlist
takes about a minute or so to download). 

If a match is found, the skill initiates a download 
even if it is not selected to ultimately play the
media for performance purposes.

Even though you may see comments like 'streaming' or
'stream', and even though there is actually a text 
label that says 'Streaming', you should read the code
and not the comments. This is not a streaming 
application. It simply downloads the video in its 
entirety, then uses ffmpeg to strip out the audio and 
then it plays that. 

Files are deleted after being played. Files are not
cached by design. This is an example of a simple single 
file music player, not a true playlist type application. 
