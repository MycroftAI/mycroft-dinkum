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
import subprocess
from typing import Union, Optional, List, Iterable
from dataclasses import dataclass
from pathlib import Path
import random

from mycroft.util.log import LOG


@dataclass
class Song:
    artist: str
    album: str
    title: str
    duration_sec: int
    file_path: Path

    @property
    def uri(self) -> str:
        return f"file://{self.file_path.absolute()}"


class MpdClient:
    """Bare bones MPD client using command-line mpc tool"""

    def __init__(
        self,
        music_dir: Optional[Union[str, Path]] = None,
        host="127.0.0.1",
    ):
        self.host = host
        if music_dir:
            self.music_dir = Path(music_dir)
        else:
            self.music_dir = Path("/media")

    def update(self, wait: bool = True):
        """Updates MPD database"""
        cmd = ["mpc", "-h", self.host, "update"]
        if wait:
            cmd.append("--wait")

        LOG.info(cmd)
        subprocess.check_call(cmd)

    def random_play(self):
        """
        This finds all files and plays them in random order.
        This only gets triggered by the 'Play jukebox' case.
        """
        command_type = "listall"
        results = self._search(command_type)
        random.shuffle(results)
        for artist, album, title, time_str, relative_path in results:
            song_path = self.music_dir / relative_path
            if song_path.is_file():
                yield Song(
                    artist=artist,
                    album=album,
                    title=title,
                    duration_sec=self._time_to_seconds(time_str),
                    file_path=song_path,
                )
            else:
                LOG.warning("Missing file: %s", song_path)

    def search(self, query: str):
        """Searches by artist, album, then song title.

        Returns:
            playlist
        """
        command_type = "search"
        for query_type in ["artist", "album", "title"]:
            results = self._search(command_type, query_type, query)
            for artist, album, title, time_str, relative_path in results:
                song_path = self.music_dir / relative_path
                if song_path.is_file():
                    yield Song(
                        artist=artist,
                        album=album,
                        title=title,
                        duration_sec=self._time_to_seconds(time_str),
                        file_path=song_path,
                    )
                else:
                    LOG.warning("Missing file: %s", song_path)

    def _search(self, command_type: str, query_type: Optional[str] = None, query: Optional[str] = None) -> List[List[str]]:
        """
        This handles two cases. One: a search for a particular song, artist, etc.
        Two: a 'listall' command to return all music.
        """
        cmd = [
            "mpc",
            "-h",
            self.host,
            command_type,
            "--format",  # https://www.musicpd.org/doc/mpc/html/#cmdoption-f
            "%artist%\t%album%\t%title%\t%time%\t%file%",  # tab-separated
        ]
        if query_type:
            cmd.extend([query_type, query])
        LOG.debug(cmd)
        return [
            line.split("\t")
            for line in subprocess.check_output(
                cmd, universal_newlines=True
            ).splitlines()
            if line.strip()
        ]

    def _time_to_seconds(self, time_str: str) -> int:
        parts = time_str.split(":", maxsplit=2)
        assert parts
        hours, minutes, seconds = 0, 0, 0

        if len(parts) == 3:
            hours, minutes, seconds = int(parts[0]), int(parts[1]), int(parts[2])
        elif len(parts) == 2:
            minutes, seconds = int(parts[0]), int(parts[1])
        else:
            seconds = int(parts[0])

        return (hours * 60 * 60) + (minutes * 60) + seconds
