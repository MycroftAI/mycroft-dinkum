# skill-mycroft-radio

Initial version which needs some clean up. 

Currently the vocab and dialog trees are copied from the npr news skill
and only the ones necessary to get the skill working have been modified
so these will need to be cleaned up, but for now the skill should play
music which was the goal. 

Uses a free user contributed radio station index (see code for endpoint)
to stream radio channels using standard audio service.

radio help or help radio will speak options.

basically play music, or play radio will select a random genre.

play jazz or play soft rock will play that genre.

next station or previous station will change the station in the current channel.

next channel or previous channel will change the current channel.

there is limited artist support, so for example play pink floyd or play 
dean martin will work, but play the turtles or play louie louie typically
do not. 

