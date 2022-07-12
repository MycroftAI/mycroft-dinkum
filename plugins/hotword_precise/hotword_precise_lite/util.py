# Copyright 2022 Mycroft AI Inc.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
"""
Miscellaneous utility functions for things like audio loading
"""
import typing

import numpy as np

MAX_WAV_VALUE = 32768


def chunk_audio(
    audio: np.ndarray, chunk_size: int
) -> typing.Generator[np.ndarray, None, None]:
    for i in range(chunk_size, len(audio), chunk_size):
        yield audio[i - chunk_size : i]


def buffer_to_audio(audio_buffer: bytes) -> np.ndarray:
    """Convert a raw mono audio byte string to numpy array of floats"""
    return np.frombuffer(audio_buffer, dtype="<i2").astype(
        np.float32, order="C"
    ) / float(MAX_WAV_VALUE)


def audio_to_buffer(audio: np.ndarray) -> bytes:
    """Convert a numpy array of floats to raw mono audio"""
    return (audio * MAX_WAV_VALUE).astype("<i2").tobytes()
