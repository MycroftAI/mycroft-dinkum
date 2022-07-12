# Copyright 2021 Mycroft AI Inc.
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

from mycroft.util.time import to_local, now_local

##########################################################################
# TODO: Move to mycroft.util.format and support translation
def nice_relative_time(when, relative_to=None, lang=None):
    """Create a relative phrase to roughly describe a datetime

    Examples are "25 seconds", "tomorrow", "7 days".

    Args:
        when (datetime): Local timezone
        relative_to (datetime): Baseline for relative time, default is now()
        lang (str, optional): Defaults to "en-us".
    Returns:
        str: Relative description of the given time
    """
    if relative_to:
        now = relative_to
    else:
        now = now_local()
    delta = to_local(when) - now

    if delta.total_seconds() < 1:
        return "now"

    if delta.total_seconds() < 90:
        if delta.total_seconds() == 1:
            return "one second"
        else:
            return "{} seconds".format(int(delta.total_seconds()))

    minutes = int((delta.total_seconds() + 30) // 60)  # +30 to round minutes
    if minutes < 90:
        if minutes == 1:
            return "one minute"
        else:
            return "{} minutes".format(minutes)

    hours = int((minutes + 30) // 60)  # +30 to round hours
    if hours < 36:
        if hours == 1:
            return "one hour"
        else:
            return "{} hours".format(hours)

    # TODO: "2 weeks", "3 months", "4 years", etc
    days = int((hours + 12) // 24)  # +12 to round days
    if days == 1:
        return "1 day"
    else:
        return "{} days".format(days)
