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
import pickle
from datetime import date, datetime
from pathlib import Path
from typing import Callable, Iterable, List, Optional, Union

from mycroft.util.time import now_local

from .alarm import Alarm
from .repeat import determine_next_occurrence


class Alarms:
    """Collection of unique alarms"""

    def __init__(self, alarms: Optional[Iterable[Alarm]] = None):
        self.alarms: List[Alarm] = list(alarms) if alarms is not None else list()

    def __iter__(self):
        return iter(self.alarms)

    def __len__(self):
        return len(self.alarms)

    def __getitem__(self, index):
        return self.alarms[index]

    @property
    def expired(self) -> Iterable[Alarm]:
        for alarm in self.alarms:
            if alarm.expired:
                yield alarm

    def clear_expired(self):
        """Remove expired alarms from the list of active alarms."""
        alarms_to_keep = []
        for alarm in self.alarms:
            if alarm.expired:
                if alarm.repeat_rule is not None:
                    alarm.date_time = determine_next_occurrence(
                        alarm.repeat_rule, alarm.date_time
                    )
                    alarms_to_keep.append(alarm)
            else:
                alarms_to_keep.append(alarm)

        self.alarms = sorted(alarms_to_keep, key=lambda a: a.date_time)

    def is_duplicate(self, alarm: Alarm) -> bool:
        for other_alarm in self.alarms:
            if (alarm.name == other_alarm.name) or (
                (alarm.date_time == other_alarm.date_time)
                and (alarm.repeat_rule == other_alarm.repeat_rule)
            ):
                return True

        return False

    def is_duplicate_name(self, alarm_name: Optional[str]) -> bool:
        if alarm_name:
            return any(alarm.name == alarm_name for alarm in self.alarms)

        return False

    def add_alarm(self, alarm: Alarm, build_description: Callable[[Alarm], str]):
        if not alarm.has_name:
            alarm.name = self._assign_alarm_name(build_description)

        alarm.description = build_description(alarm)
        self.alarms.append(alarm)
        self.alarms.sort(key=lambda a: a.date_time)

    def remove_alarm(self, alarm: Alarm):
        self.alarms = sorted(
            filter(lambda a: a.name != alarm.name, self.alarms),
            key=lambda a: a.date_time,
        )

    def _assign_alarm_name(self, build_description: Callable[[Alarm], str]) -> str:
        """Assign a name to a alarm when the user does not specify one.

        All alarms will have a name. If the user does not request one, assign a name
        using the "Alarm <unnamed alarm number>" convention.

        When there is only one alarm active and it is assigned a name, the name
        "Alarm" will be used.  If another alarm without a requested name is added,
        the alarm named "Alarm" will have its name changed to "Alarm 1" and the new
        alarm will be named "Alarm 2"

        Returns:
            The name assigned to the alarm.
        """
        if self.alarms:
            max_assigned_number = 0
            for alarm in self.alarms:
                if alarm.name == "alarm":
                    # Change existing alarm to alarm 1
                    alarm.name = "alarm 1"
                    alarm.description = build_description(alarm)
                    max_assigned_number = 1
                elif (alarm.name is not None) and alarm.name.startswith("alarm "):
                    _, name_number = alarm.name.split()
                    name_number = int(name_number)
                    if name_number > max_assigned_number:
                        max_assigned_number = name_number
            new_alarm_number = max_assigned_number + 1
            alarm_name = "alarm " + str(new_alarm_number)
        else:
            alarm_name = "alarm"

        return alarm_name

    @staticmethod
    def is_alarm_in_past(utterance: str, alarm_datetime: datetime, translations):
        alarm_in_past = False
        if alarm_datetime <= now_local():
            if alarm_datetime.date() == date.today():
                today_in_utterance = (
                    translations.today[0] in utterance
                    or translations.tonight[0] in utterance
                )
                if today_in_utterance:
                    alarm_in_past = True
            else:
                alarm_in_past = True

        return alarm_in_past

    @staticmethod
    def load(load_path: Union[str, Path]) -> "Alarms":
        load_path = Path(load_path)
        alarms = list()
        if load_path.exists():
            with open(load_path, "rb") as data_file:
                alarms = pickle.load(data_file)

        return Alarms(alarms)

    def save(self, save_path: Union[str, Path]):
        if self.alarms:
            with open(save_path, "wb") as data_file:
                pickle.dump(self.alarms, data_file, pickle.HIGHEST_PROTOCOL)
        else:
            save_path = Path(save_path)
            if save_path.exists():
                save_path.unlink()
