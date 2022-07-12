Feature: Current Time
  Reply to requests for the current time in the local and remote time zones.

  Scenario Outline: what time is it
    Given an english speaking user
     When the user says "<local current time request>"
     Then "time" should reply with dialog from "time-current-local.dialog"

  Examples:
    | local current time request |
    | clock |
    | time |
    | what's the time |
    | whats the time |
    | what time is it |
    | tell me the time |
    | the time please |
    | current time |
    | time please |
    | give me the time |
    | give me the current time |
    | tell me what time it is |
    | tell me the current time |
    | what time is it currently |
    | time right now |
    | what is the time |
    | what time is it now |
    | do you know what time it is |
    | could you tell me the time please |
    | excuse me what's the time |
    | what is the current time |
    | what's the current time |
    | what time |
    | check the time |
    | check time |
    | check clock |

  Scenario Outline: what's the time in a location
    Given an english speaking user
     When the user says "<current time in location request>"
     Then "time" should reply with dialog from "time-current-location.dialog"

  Examples: what time examples
    | current time in location request |
    | what's the time in paris |
    | what's the current time in london |
    | check the time in baltimore |
    | what time is it in sydney |

  @xfail
  # jira MS-100 https://mycroft.atlassian.net/browse/MS-100
  Scenario Outline: Failing what's the time in a location
    Given an english speaking user
     When the user says "<current time in location request>"
     Then "time" should reply with dialog from "time-current-location.dialog"

  Examples:
    | current time in location request |
    | check the time in Washington DC |
    | time in Toronto |

  Scenario Outline: what's the time in an imaginary location
    Given an english speaking user
     When the user says "<current time in location request>"
     Then "time" should reply with dialog from "location-not-found.dialog"

  Examples: what time examples
    | current time in location request |
    | what's the time in Asgard |
