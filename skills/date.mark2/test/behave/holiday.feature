# Feature: User requests information about a past or future holiday.

#   @xfail
#   # Jira 104 https://mycroft.atlassian.net/browse/MS-105
#   Scenario Outline: when is a holiday
#     Given an english speaking user
#      When the user says "<when is new year's day>"
#      Then "date.mark2" should reply with dialog from "date.dialog"

#   Examples: when is a holiday
#     | when is new year's day |
#     | when is christmas |
#     | when is christmas 2020 |
#     | when is christmas 2030 |
#     | when is thanksgiving 2020 |
#     | how many days until christmas |
#     | how many days until christmas |
#     | how long until thanksgiving |
#     | what day is thanksgiving this year |
#     | when is ramadan 2020 |
