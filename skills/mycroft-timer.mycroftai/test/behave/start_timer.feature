Feature: mycroft-timer


  Scenario Outline: set a timer without specifying duration
    Given an english speaking user
    And no active timers
    When the user says "<set timer request>"
    Then "mycroft-timer.mycroftai" should reply with dialog from "ask-how-long"
    And the user replies with "5 minutes"
    And "mycroft-timer.mycroftai" should reply with dialog from "started-timer"

    Examples: set a timer without specifying duration
      | set timer request |
      | set a timer |
