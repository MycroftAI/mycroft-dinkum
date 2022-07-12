Feature: Future time

  Scenario Outline: what's the future time in the device's local time zone
    Given an english speaking user
     When the user says "<local future time request>"
     Then "time" should reply with dialog from "time-future-local.dialog"

  Examples:
    | local future time request |
    | what time will it be 8 hours from now |
    | give me the time 8 hours from now |
    | the time 8 hours from now please |
    | what's the time in 8 hours |
    | what will be the time in 8 hours |
    | when is it 8 hours from now |
    | in 8 hours what time will it be |
    | what time will it be in 36 hours |
    | what time will it be in 90 minutes |
    | in 97 minutes what time will it be |
    | what time will it be in 60 seconds |
    | what's the time 8 hours from now |

  Scenario Outline: what's the future time in a location
    Given an english speaking user
     When the user says "<future time request for location>"
     Then "time" should reply with dialog from "time-future-location.dialog"

  Examples:
     | future time request for location |
     | what time will it be in 8 hours in Berlin |
     | what time will it be 8 hours from now in Paris |
     | what's the time in Los Angeles 8 hours from now |
     | give me the time 8 hours from now in Baltimore |
     | what's the time in London in 8 hours |
     | what will be the time in Barcelona in 8 hours |
     | the time 8 hours from in New York City please |

  Scenario Outline: what's the future time in an imaginary location
    Given an english speaking user
     When the user says "<future time in location request>"
     Then "time" should reply with dialog from "location-not-found.dialog"

  Examples: what time examples
    | future time in location request |
    | what time will it be in 8 hours in Asgard |
