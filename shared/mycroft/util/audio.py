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
import audioop


def debiased_energy(audio_data: bytes, sample_width: int) -> float:
    """Compute RMS of debiased audio."""
    # Thanks to the speech_recognition library!
    # https://github.com/Uberi/speech_recognition/blob/master/speech_recognition/__init__.py
    energy = -audioop.rms(audio_data, sample_width)
    energy_bytes = bytes([energy & 0xFF, (energy >> 8) & 0xFF])
    debiased_energy = audioop.rms(
        audioop.add(
            audio_data, energy_bytes * (len(audio_data) // sample_width), sample_width
        ),
        sample_width,
    )

    return debiased_energy
