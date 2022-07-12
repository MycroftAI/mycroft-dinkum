# Copyright 2018 Mycroft AI Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import os, re, glob, time, json
from threading import Thread, Event
from pytube import YouTube

# this is a hack to try to filter 
# out streams and videos that are
# too long to download while a user
# is waiting. 
MAX_SONG_LEN_IN_SECONDS = 3000

class FileLoaderThread(Thread):
    def __init__(self):
        Thread.__init__(self)
        self.url = ''
        self.img_url = ''
        self.img_filename = ''
        self.mp3_filename = ''
        self.img_ctr = 0
        self.request = False
        self.finished = False

    def run(self):
        while True:
            if self.request:
                self.request = False
                self.finished = False

                # clean up after yourself
                if self.mp3_filename != '':
                    os.system("rm -f %s" % (self.mp3_filename,))  
                if self.img_filename != '':
                    os.system("rm -f %s" % (self.img_filename,)) 

                # grab image
                self.img_ctr += 1
                img_filename = "/tmp/music_img%s" % (self.img_ctr,)
                if self.img_url.endswith(".jpg"):
                    img_filename += ".jpg"
                elif self.img_url.endswith(".gif"):
                    img_filename += ".gif"
                else:
                    img_filename += ".png"

                self.img_filename = img_filename

                cmd = "wget -O %s %s" % (img_filename, self.img_url)
                os.system(cmd)

                # grab the mp4
                mp4_filename = "/tmp/ytvid.mp4"
                video_url = "https://www.youtube.com/watch?v=%s" % (self.url,)
                yt = YouTube(video_url)
                yt.streams.first().download()
                os.rename(yt.streams.first().default_filename, mp4_filename)

                # convert to mp3
                cmd = "ffmpeg -i %s -q:a 0 -map a %s" % (mp4_filename, self.mp3_filename)
                os.system(cmd)
                os.system("rm -f %s" % (mp4_filename,))  # clean up

                self.finished = True
            time.sleep(1)

def get_seconds(duration):
    # note - we do not error check
    secs = 0
    mins = 0
    hrs = 0
    da = duration.split(":")

    if len(da) == 3:
        hrs = int( da[0] ) * 3600
        mins = int( da[1] ) * 60
        secs = int( da[2] )

    if len(da) == 2:
        mins = int( da[0] ) * 60
        secs = int( da[1] )

    if len(da) == 1:
        secs = int( da[0] ) 

    return hrs + mins + secs


def get_json():
    fh = open("/tmp/search_results.html")
    tag = 'var ytInitialData ='
    for line in fh:
        if line.find(tag) != -1:
            la = line.split("</script>")
            ctr = 0
            for l in la:
                ctr += 1
                if l.find(tag) != -1:
                    start_indx = l.find(tag) + len(tag) + 1
                    fh.close()
                    return l[start_indx:-1]
    fh.close()
    return ''

def process_vr(rend):
    # TODO replace try/except with gets
    thumb = ''

    try:
        thumb = rend['thumbnails'][0]['thumbnails']
        thumb = thumb[len(thumb)-1]       # the last is usually the largest
    except:
        pass

    thumb = rend['thumbnail']['thumbnails'][0]
    if thumb == '':
        try:
            thumb = rend['thumbnail']['thumbnails'][0]
        except:
            pass

    title = ''
    try:
        title = rend['title']['simpleText']
    except:
        pass

    if title == '':
        try:
            title = rend['title']['runs'][0]['text']
        except:
            pass

    song_len = 0
    try:
        song_len = get_seconds( rend['videos'][0]['childVideoRenderer']['lengthText']['simpleText'] )
    except:
        pass

    if song_len == 0:
        try:
            song_len = get_seconds( rend['lengthText']['simpleText'] )
        except:
            pass

    video_id = ''
    try:
        video_id = rend['videos'][0]['childVideoRenderer']['videoId']
    except:
        pass

    if video_id == '':
        try:
            video_id = rend['videoId']
        except:
            pass

    img_url = thumb['url']
    ia = img_url.split("?")
    img_url = ia[0]

    return video_id, title, img_url, song_len

def get_url():
    play_list = []
    # the caller might want to try/catch calls to this method
    vid_json = json.loads( get_json() )
    contents = vid_json['contents']
    rend = contents['twoColumnSearchResultsRenderer']
    rend = rend['primaryContents']
    rend = rend['sectionListRenderer']
    rend = rend['contents']
    rend = rend[0]
    rend = rend['itemSectionRenderer']
    rend = rend['contents']

    # could be videoRenderer or a playListRenderer
    # or a channelRenderer ... so many renderers
    video_id = ''
    thumb = ''
    title = ''
    img_url = ''
    song_len = 0

    for thing in rend:
        if thing.get('videoRenderer', '') != '':
            video_id, title, img_url, song_len = process_vr( thing['videoRenderer'] )
            # could just break here
            if song_len > 0 and song_len < MAX_SONG_LEN_IN_SECONDS:
                play_list.append({
                    'video_id':video_id,
                    'title':title, 
                    'img_url':img_url, 
                    'song_len':song_len
                    })

    if len(play_list) == 0:
        # could not find a suitable video
        return '', '', '', '', 0

    # we could create a playlist but for 
    # now we just take the first song
    video_id = play_list[0]['video_id']
    title = play_list[0]['title']
    img_url = play_list[0]['img_url']
    song_len = play_list[0]['song_len']

    # sometimes we have artist and song
    ta = title.split(" - ")
    artist = ta[0]
    song = artist
    if len(ta) > 1:
        # sometimes separated by '-'
        song = ta[1]

    if song == artist:
        # sometimes separated by 'by'
        ta = title.split(" by ")
        artist = ta[0]
        song = artist
        if len(ta) > 1:
            song = ta[1]

    # remove everything in parens
    # might be a bit harsh
    artist = re.sub(r'\([^)]*\)', '', artist)
    song = re.sub(r'\([^)]*\)', '', song)

    # finally, decide what to ultimately show
    # this should probably be done by the caller
    if artist == song:
        artist = ''

    return video_id, img_url, artist, song, song_len

