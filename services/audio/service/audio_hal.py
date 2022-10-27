# Copyright 2022 Mycroft AI Inc.
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
#
"""Audio hardware abstraction layer.

Used by the audio user interface (AUI) to play sound effects and streams.
"""
import ctypes
import os
import signal
import subprocess
import tempfile
from pathlib import Path
from threading import RLock
from typing import Dict, Iterable, Optional, Union

import numpy as np
import sdl2
import sdl2.sdlmixer as mixer
from mycroft.messagebus import Message
from mycroft.messagebus.client import MessageBusClient
from mycroft.util.log import get_mycroft_logger

_log = get_mycroft_logger(__name__)

ChannelType = int
HookMusicFunc = ctypes.CFUNCTYPE(
    None, ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint8), ctypes.c_int
)


class SDLException(Exception):
    """Exception generated when checking SDL calls"""


class AudioHAL:
    """Audio hardware abstraction layer.

    Provides access to the audio output device through VLC.
    Output "channels" are categorized as:

    * Foreground
      * Transient sounds effects or speech from text to speech
    * Background
      * Long-running audio stream

    Each channel may only have one media item at a time.
    """

    def __init__(
        self,
        audio_sample_rate: int = 48000,
        audio_channels: int = 2,
        audio_width: int = 4,
        audio_chunk_size: int = 2048,
    ):
        # Mixer settings
        self.audio_sample_rate = audio_sample_rate
        self.audio_channels = audio_channels
        self.audio_width = audio_width
        self.audio_chunk_size = audio_chunk_size

        # Mixer chunks to free
        self._fg_free: Dict[ChannelType, mixer.Mix_Chunk] = {}

        # Media ids by channel
        self._fg_media_ids: Dict[ChannelType, Optional[str]] = {}
        self._fg_session_ids: Dict[ChannelType, Optional[str]] = {}
        self._bg_media_id: Optional[str] = None

        # Background VLC process
        self._bg_proc: Optional[subprocess.Popen] = None
        self._bg_paused: bool = True
        self._bg_volume: float = 1.0
        self._bg_position: int = 0

        self._mixer_lock = RLock()

        # Callback must be defined inline in order to capture "self"
        @ctypes.CFUNCTYPE(None, ctypes.c_int)
        def fg_channel_finished(channel):
            """Callback when foreground media item is finished playing"""
            try:
                media_id = self._fg_media_ids.get(channel) or ""
                self.bus.emit(
                    Message(
                        "mycroft.audio.hal.media.ended",
                        data={
                            "channel": channel,
                            "media_id": media_id,
                            "mycroft_session_id": self._fg_session_ids.get(channel),
                        },
                    )
                )
            except Exception:
                _log.exception("Error finishing channel: %s", channel)

        self._fg_channel_finished = fg_channel_finished

        # Callback must be defined inline in order to capture "self"
        @HookMusicFunc
        def bg_music_hook(udata, stream, length):
            if self._bg_paused or (self._bg_proc is None):
                # Write silence
                ctypes.memset(stream, 0, length)
            else:
                if self._bg_proc.poll() is not None:
                    # Stream finished
                    self.stop_background()
                    self._bg_media_finished()
                else:
                    # Music data
                    data = self._bg_proc.stdout.read(length)

                    if 0 <= self._bg_volume < 1:
                        array = np.frombuffer(data, dtype=np.int32) * self._bg_volume
                        data = array.astype(np.int32).tobytes()

                    # ctypes.memset(stream, data, length)
                    for i in range(len(data)):
                        stream[i] = data[i]

                    self._bg_position += length

        self._bg_music_hook = bg_music_hook

        # We need to give VLC a playlist so we can add vlc://quit at the end and
        # have it actually terminate.
        self._bg_playlist_file = tempfile.NamedTemporaryFile(suffix=".m3u", mode="w+")

    def initialize(self, bus: MessageBusClient):
        """Starts audio HAL."""
        self.bus = bus

        _log.info("Initializing SDL mixer")

        ret = mixer.Mix_Init(
            mixer.MIX_INIT_MP3
            | mixer.MIX_INIT_FLAC
            | mixer.MIX_INIT_OGG
            | mixer.MIX_INIT_OPUS
        )
        self._check_sdl(ret)

        # TODO: Parameterize
        ret = mixer.Mix_OpenAudio(
            self.audio_sample_rate,
            sdl2.AUDIO_S32SYS if self.audio_width == 4 else sdl2.AUDIO_S16SYS,
            self.audio_channels,
            self.audio_chunk_size,
        )
        self._check_sdl(ret)

        mixer.Mix_ChannelFinished(self._fg_channel_finished)

        self._reset_caches()

    def shutdown(self):
        """Shuts down audio HAL."""
        self._reset_caches()

        self.stop_background()

        _log.info("Stopping SDL mixer")
        mixer.Mix_CloseAudio()
        mixer.Mix_Quit()

    def _reset_caches(self):
        """Clears all media caches."""
        self._fg_free = {}
        self._fg_media_ids = {}
        self._bg_media_id = None

    def _stop_bg_process(self):
        """Stops background VLC process if running."""
        if self._bg_proc is not None:
            if self._bg_proc.poll() is None:
                _log.info("Stopping background media process")
                self._bg_proc.terminate()

                try:
                    # Wait a bit before sending kill signal
                    self._bg_proc.communicate(timeout=0.5)
                except subprocess.TimeoutExpired:
                    self._bg_proc.kill()

                _log.info("Background media process stopped")

            self._bg_proc = None

    def _bg_media_finished(self):
        """Callback when background playlist is finished playing"""
        media_id = self._bg_media_id or ""
        _log.info("Finished playing background media: %s", media_id)

        self.bus.emit(
            Message(
                "mycroft.audio.hal.media.ended",
                data={"background": True, "media_id": media_id},
            )
        )

    def _check_sdl(self, ret: int):
        """Checks SDL call return value and raise exception if an error occurred."""
        if ret < 0:
            raise SDLException(self._get_mixer_error())

    def _get_mixer_error(self) -> str:
        """Returns the last mixer error string."""
        return mixer.Mix_GetError().decode("utf8")

    def play_foreground(
        self,
        channel: ChannelType,
        file_path: Union[str, Path],
        media_id: Optional[str] = None,
        volume: Optional[float] = None,
        mycroft_session_id: Optional[str] = None,
    ) -> float:
        """Plays an audio file on a foreground channel.

        Args:
            channel: audio channel playing the audio media
            file_path: absolute path to the audio media
            media_id: internal identifier of the audio media
            volume: loudness of the media playback
            mycroft_session_id: identifier of the session related to audio playback

        Returns:
            Duration of audio in seconds
        """
        file_path_str = str(file_path)
        _log.info("Playing audio file %s in foreground", file_path)

        # Need to load new chunk
        with self._mixer_lock:
            last_chunk: Optional[mixer.Mix_Chunk] = self._fg_free.pop(channel, None)
            if last_chunk is not None:
                # Free previously played audio chunk
                mixer.Mix_FreeChunk(last_chunk)

            chunk: Optional[mixer.Mix_Chunk] = mixer.Mix_LoadWAV(file_path_str.encode())

            if not chunk:
                raise SDLException(self._get_mixer_error())

            duration_sec = chunk.contents.alen / (
                self.audio_sample_rate * self.audio_channels * self.audio_width
            )

            self._fg_media_ids[channel] = media_id
            self._fg_session_ids[channel] = mycroft_session_id

            # Chunk will be freed when next sound is played on this channel
            self._fg_free[channel] = chunk

            if volume is not None:
                # Set channel volume
                mixer.Mix_Volume(channel, self._clamp_volume(volume))
            else:
                # Max volume
                mixer.Mix_Volume(channel, self._clamp_volume(1.0))

            mixer.Mix_HaltChannel(channel)
            ret = mixer.Mix_PlayChannel(channel, chunk, 0)  # 0 = no looping
            self._check_sdl(ret)

            return duration_sec

    def pause_foreground(self, channel: int = -1):
        """Pauses media on a foreground audio channel.

        Args:
            channel: Audio channel to pause (defaults to -1 for all)
        """
        with self._mixer_lock:
            mixer.Mix_Pause(channel)

    def resume_foreground(self, channel: int = -1):
        """Resumes media on a foreground audio channel.

        Args:
            channel: Audio channel to pause (defaults to -1 for all)
        """
        with self._mixer_lock:
            mixer.Mix_Resume(channel)

    def stop_foreground(self, channel: int = -1):
        """Stops media on a foreground audio channel.

        Args:
            channel: Audio channel to pause (defaults to -1 for all)
        """
        with self._mixer_lock:
            mixer.Mix_HaltChannel(channel)

    def set_foreground_volume(self, volume: float, channel: int = -1):
        """Sets volume of a foreground audio channel.

        Args:
            volume: value between zero and one representing playback volume
            channel: Audio channel to pause (defaults to -1 for all)
        """
        with self._mixer_lock:
            mixer.Mix_Volume(channel, self._clamp_volume(volume))

    def _clamp_volume(self, volume: float) -> int:
        """Converts volume to SDL volume in [0, 128)

        Args:
            volume: value between zero and one representing playback volume

        Returns:
            Value between zero and 128 representing SDL volume
        """
        volume_num = int(volume * mixer.MIX_MAX_VOLUME)
        volume_num = max(0, volume_num)
        volume_num = min(mixer.MIX_MAX_VOLUME, volume_num)

        return volume_num

    def start_background(
        self, uri_playlist: Iterable[str], media_id: Optional[str] = None
    ):
        """Starts a playlist playing on a background channel.

        Args:
            uri_playlist: sequence of URIs representing audio media
            media_id: internal identifier for the audio media
        """
        self._stop_bg_process()

        self._bg_playlist_file.truncate(0)

        for item in uri_playlist:
            print(item, file=self._bg_playlist_file)

        # Add quit URI to end of playlist so VLC will terminate when finished
        # playing.
        print("vlc://quit", file=self._bg_playlist_file)
        self._bg_playlist_file.seek(0)

        # Run VLC separately, reading raw audio chunks from its stdout and
        # playing in the music hook function.
        #
        # NOTE: The output format here must exactly match what we use in
        # Mix_OpenAudio.
        self._bg_proc = subprocess.Popen(
            [
                "vlc",
                "-I",
                "dummy",
                "--no-video",
                "--sout",
                f"#transcode{{acodec=s32l,samplerate={self.audio_sample_rate},channels={self.audio_channels}}}:std{{access=file,mux=wav,dst=-}}",  # noqa: E501
                self._bg_playlist_file.name,
            ],
            stdout=subprocess.PIPE,
        )

        self._bg_media_id = media_id
        self._bg_position = 0
        self._bg_paused = False

        with self._mixer_lock:
            mixer.Mix_HookMusic(self._bg_music_hook, None)

        _log.info("Playing playlist in background")

    def stop_background(self):
        """Stops audio playing on the background channel."""
        # Disable music hook.
        # HookMusicFunc() creates a NULL pointer
        with self._mixer_lock:
            mixer.Mix_HookMusic(HookMusicFunc(), None)

        self._stop_bg_process()
        self._bg_position = 0
        self._bg_media_id = None

    def pause_background(self):
        """Pauses the audio playing on the background channel."""
        self._bg_paused = True

        if self._bg_proc is not None:
            os.kill(self._bg_proc.pid, signal.SIGSTOP)

    def resume_background(self):
        """Resume the background channel"""
        if self._bg_proc is not None:
            os.kill(self._bg_proc.pid, signal.SIGCONT)

        self._bg_paused = False

    def set_background_volume(self, volume: float):
        """Sets the volume of the background music."""
        self._bg_volume = max(0, min(volume, 1))

    def get_background_time(self) -> int:
        """Returns position of background stream in milliseconds"""
        # Default: 48Khz, 32-bit stereo
        bytes_per_sample = self.audio_width
        bytes_per_ms = (
            self.audio_sample_rate * self.audio_channels * bytes_per_sample
        ) // 1000

        return self._bg_position // bytes_per_ms

    def is_background_playing(self):
        """Returns True if background stream is currently playing."""
        return not self._bg_paused
