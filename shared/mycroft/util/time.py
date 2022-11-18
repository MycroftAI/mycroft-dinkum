#
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
#
"""Time utils for getting and converting datetime objects.

This time is based on the setting in the Mycroft config and may or
may not match the system locale.
"""
from datetime import datetime, tzinfo
from typing import Optional

from dateutil.tz import gettz, tzlocal


def default_timezone() -> tzinfo:
    """Get the default timezone

    Based on user location settings location.timezone.code or
    the default system value if no setting exists.

    Returns:
        Definition of the default timezone
    """
    try:
        # Obtain from user's configurated settings
        #   location.timezone.code (e.g. "America/Chicago")
        #   location.timezone.name (e.g. "Central Standard Time")
        #   location.timezone.offset (e.g. -21600000)
        from mycroft.configuration import Configuration

        config = Configuration.get()
        code = config["location"]["timezone"]["code"]

        return gettz(code)
    except Exception:
        # Just go with system default timezone
        return tzlocal()


def now_utc() -> datetime:
    """Retrieve the current time in UTC

    Returns:
        The current time in Universal Time, aka GMT
    """
    return to_utc(datetime.utcnow())


def now_local(tz: Optional[tzinfo] = None) -> datetime:
    """Retrieve the current time

    Args:
        tz: Timezone, default to user's settings

    Returns:
        The current time
    """
    if not tz:
        tz = default_timezone()
    return datetime.now(tz)


def to_utc(dt: datetime) -> datetime:
    """Convert a datetime with timezone info to a UTC datetime

    Args:
        dt: The date and time to be converted (presumably in some local zone)
    Returns:
        time converted to UTC
    """
    tz_utc = gettz("UTC")
    if dt.tzinfo:
        return dt.astimezone(tz_utc)
    else:
        return dt.replace(tzinfo=gettz("UTC")).astimezone(tz_utc)


def to_local(dt: datetime) -> datetime:
    """Convert a datetime to the user's local timezone

    Args:
        dt: The date and time to be converted (if no timezone, defaults to UTC)
    Returns:
        time converted to the local timezone
    """
    tz = default_timezone()
    if dt.tzinfo:
        return dt.astimezone(tz)
    else:
        return dt.replace(tzinfo=gettz("UTC")).astimezone(tz)


def to_system(dt: datetime) -> datetime:
    """Convert a datetime to the system's local timezone

    Args:
        dt: The date and time to be converted (if no timezone, assumed to be UTC)
    Returns:
        time converted to the operation system's timezone
    """
    tz = tzlocal()
    if dt.tzinfo:
        return dt.astimezone(tz)
    else:
        return dt.replace(tzinfo=gettz("UTC")).astimezone(tz)
