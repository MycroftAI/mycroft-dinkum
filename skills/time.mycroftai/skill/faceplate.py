# Copyright 2021, Mycroft AI Inc.
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
"""Render the time on an Arduino faceplate, such as on the Mark I."""
ALARM_INDICATOR = "CIAACA"
CHARACTER_WIDTH = 4
FACEPLATE_WIDTH = 32
NINE_COLUMN_BLANK = "JIAAAAAAAAAAAAAAAAAA"
NO_ALARM_INDICATOR = "CIAAAA"
SEVEN_COLUMN_BLANK = "HIAAAAAAAAAAAAAA"


class FaceplateRenderer:
    """Display data on a Mark I or device with similar faceplate."""
    def __init__(self, enclosure, display_time: str):
        self.enclosure = enclosure
        self.display_time = display_time
        # Map characters to the display encoding for a Mark 1
        # (4x8 except colon, which is 2x8)
        self.character_codes = {
            ':': 'CIICAA',
            '0': 'EIMHEEMHAA',
            '1': 'EIIEMHAEAA',
            '2': 'EIEHEFMFAA',
            '3': 'EIEFEFMHAA',
            '4': 'EIMBABMHAA',
            '5': 'EIMFEFEHAA',
            '6': 'EIMHEFEHAA',
            '7': 'EIEAEAMHAA',
            '8': 'EIMHEFMHAA',
            '9': 'EIMBEBMHAA',
        }

    def render_time(self, alarm_is_set: bool):
        """Draw the time centered on the faceplate and an alarm indicator.

        Args:
            alarm_is_set: Indicates if the alarm skill has one or more active alarms
        """
        self._render_left_padding()
        self._render_time_characters()
        self._render_alarm_indicator(alarm_is_set)
        self._render_right_padding()

    def _render_left_padding(self):
        """Draw blanks to the left of the time.

        For 4-character times (e.g. 1:23), draw 9 blank columns.  For 5-character
        times (e.g. 12:34) draw 7 blank columns.
        """
        if len(self.display_time) == 4:
            image_code = NINE_COLUMN_BLANK
        else:
            image_code = SEVEN_COLUMN_BLANK
        self.enclosure.mouth_display(img_code=image_code, refresh=False)

    def _render_time_characters(self):
        """Draw the time, centered on display.

        Calculate the x_coordinate that represents where the first character of the
        time should be drawn for the time to appear centered.  Then draw the characters
        starting from that point.
        """
        time_width = (CHARACTER_WIDTH * len(self.display_time)) - 2
        x_coordinate = (FACEPLATE_WIDTH - time_width) / 2
        for character in self.display_time:
            self.enclosure.mouth_display(
                img_code=self.character_codes[character], x=x_coordinate, refresh=False
            )
            x_coordinate += 2 if character == ":" else 4

    def _render_right_padding(self):
        """Draw blanks to the right of the time.

        For 4-character times (e.g. 1:23), draw 9 blank columns.  For 5-character
        times (e.g. 12:34) draw 7 blank columns.
        """
        if len(self.display_time) == 4:
            image_code = NINE_COLUMN_BLANK
            x_coordinate = 22
        else:
            image_code = SEVEN_COLUMN_BLANK
            x_coordinate = 24
        self.enclosure.mouth_display(img_code=image_code, x=x_coordinate, refresh=False)

    def _render_alarm_indicator(self, alarm_is_set: bool):
        """Show a dot in the upper-left corner of the faceplate if an alarm is set.

        Args:
            alarm_is_set: indicates whether or not the alarm skill has active alarms.
        """
        if alarm_is_set:
            image_code = ALARM_INDICATOR
        else:
            image_code = NO_ALARM_INDICATOR
        self.enclosure.mouth_display(img_code=image_code, x=29, refresh=False)
