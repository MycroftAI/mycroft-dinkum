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
"""Standardize logger setup.

Standardizations:
    * applications logs go into a /var/log/mycroft/<application_name>.log file
        be sure that whatever host you are logging on has the /var/log/mycroft
        directory, which is owned by the application user.
    * log files contain all log messages of all levels by default.  this can be
        very handy to debug issues with an application but won't clog up a
        console log viewer
    * log files will be rotated on a daily basis at midnight.  this makes logs
        easier to manage and use, especially when debug messages are included
    * log messages at warning level and above will be streamed to the console
        by default.  this will bring attention to any issues or potential
        issues without clogging up the console with a potentially massive
        amount of log messages.
    * log messages will be formatted as such:
        YYYY-MM-DD HH:MM:SS,FFF | LEVEL | PID | LOGGER | LOG MESSAGE

Any of the above standardizations can be overridden by changing an instance
attribute on the LoggingConfig class.  In general, this should not be done.
Possible exceptions include increasing verbosity for debugging.
"""

import logging.config
import logging

LOG = logging.getLogger(__package__)


def _generate_log_config(log_file_name: str) -> dict:
    """Uses Python's dictionary config for logging to configure Mycroft logs.

    Args:
        log_file_name: the name of the log file, usually a service or application name

    Returns:
        The logging configuration in dictionary format.
    """
    log_format = (
        "{asctime} | {levelname:8} | {process:5} | {name}.{funcName} | {message}"
    )
    default_formatter = {"format": log_format, "style": "{"}
    console_handler = {
        "class": "logging.StreamHandler",
        "formatter": "default",
        "level": "INFO",
        "stream": "ext://sys.stdout",
    }
    file_handler = {
        "backupCount": 14,
        "class": "logging.handlers.TimedRotatingFileHandler",
        "formatter": "default",
        "filename": f"/var/log/mycroft/{log_file_name}.log",
        "when": "midnight",
    }

    return {
        "version": 1,
        "formatters": {"default": default_formatter},
        "handlers": {"console": console_handler, "file": file_handler},
        "root": {"level": "DEBUG", "handlers": ["file"]},
    }


def configure_mycroft_logger(log_file_name: str):
    """Configures the base logger for any Mycroft service or application.

    Args:
        log_file_name: the name of the log file, usually a service or application name
    """
    log_config = _generate_log_config(log_file_name)
    mycroft_logger = {
        "mycroft": {"level": "DEBUG", "handlers": ["file"], "propagate": 0}
    }
    log_config["loggers"] = mycroft_logger
    logging.config.dictConfig(log_config)
    logging.getLogger("mycroft")


def get_mycroft_logger(module_name: str):
    """Returns a logger instance based on the Mycroft logger.

    Args:
        module_name: The name of the Python module producing the log message
    """
    return logging.getLogger("mycroft." + module_name)
