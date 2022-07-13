Feature: Relative Date
  User requests a date relative to the current date. The date could be in the
  past or the future.

  Scenario Outline: User requests a date a number of days in the future
    Given an english speaking user
     When the user says "<future date request>"
     Then "date.mycroftai" should reply with dialog from "date-relative-future.dialog"

  Examples:
    | future date request |
    | what's the date in 2 days |
    | what is the date 5 days from now |
    | what is the date a week from now |
    | what is the date a week from today |
    | what is the date 5 days from today |

  Scenario Outline: what was the date a number of days in the past
    Given an english speaking user
     When the user says "<past date request>"
     Then "date.mycroftai" should reply with dialog from "date-relative-past.dialog"

  Examples:
    | past date request |
    | what was the date 2 days ago |
    | what was the date 5 days ago |

  Scenario Outline: failing what was the date a number of days in the past
    Given an english speaking user
     When the user says "<failing past date request>"
     Then "date.mycroftai" should reply with dialog from "date-relative-past.dialog"

  Examples:
    | failing past date request |
    | what was the date 2 days ago |
    | what was the date 5 days ago |

  Scenario Outline: when is a date in the future
    Given an english speaking user
     When the user says "<future date request>"
     Then "date.mycroftai" should reply with dialog from "date-relative-future.dialog"

  Examples:
    | future date request |
    | when is the 1st of september |
    | when is June 30th |
    | what's tomorrow's date |
    | what is the date tomorrow |
    | what date is next monday |
    | what day is september 1st 2028 |
    | what day is June 30th |

  Scenario Outline: when is a date in the past
    Given an english speaking user
     When the user says "<past date request>"
     Then "date.mycroftai" should reply with dialog from "date-relative-past.dialog"

  Examples:
    | past date request |
    | what day was it november 1st 1953 |
    | when was november 1st 1953 |
    | what was the date last monday |
    | what was yesterday's date |
    | what was the date yesterday |
