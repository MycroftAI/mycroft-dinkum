Feature: Current date
  User requests the current date

  Scenario Outline: what's the date
    Given an english speaking user
     When the user says "<current date request>"
     Then "date.mycroftai" should reply with dialog from "date.dialog"

  Examples:
    | current date request |
    | what date is it |
    | what's today's date |
    | what's the date |
    | what's the date today |
    | what day of the month is it |
    | today's date is what |
    | what day is it |
    | what day is it today |
    | what's today |
    | what is today |
    | what's the day |
    | today's day is what |
    | today is what day |
    | what is the day of the week |
    | what is the day of the month |
    | what is the day |

