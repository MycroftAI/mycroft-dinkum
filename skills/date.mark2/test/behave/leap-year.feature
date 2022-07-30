Feature: Next Leap Year
  Respond to user request for the next leap year

  Scenario Outline: when is the next leap year
    Given an english speaking user
     When the user says "<leap year request>"
     Then "date.mark2" should reply with dialog from "next-leap-year.dialog"

  Examples:
    | leap year request |
    | when is the next leap year |
    | what year is the next leap year |
    | when is leap year |
