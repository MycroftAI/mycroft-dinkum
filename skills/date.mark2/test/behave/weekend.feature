Feature: Respond to user requests for weekend dates
  User can request the weekend prior to the current date or the weekend subsequent to
  the current date.

  Scenario Outline: what is the date next weekend
    Given an english speaking user
     When the user says "<upcoming weekend request>"
     Then "date.mark2" should reply with dialog from "date-future-weekend.dialog"

  Examples: what is the date next weekend
     | upcoming weekend request |
     | what date is next weekend |
     | what dates are next weekend |
     | what is the date next weekend |

  Scenario Outline: what was the date last weekend
    Given an english speaking user
     When the user says "<prior weekend request>"
     Then "date.mark2" should reply with dialog from "date-last-weekend.dialog"

  Examples: what was the date last weekend
    | prior weekend request |
    | what was the date last weekend |
    | what dates were last weekend |
    | what date was it last weekend |
