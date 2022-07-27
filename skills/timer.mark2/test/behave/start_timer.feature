Feature: mycroft-timer

  Scenario Outline: set a timer for a specified duration
    Given an english speaking user
    And no active timers
    When the user says "<set timer request>"
    Then "mycroft-timer.mycroftai" should reply with dialog from "started-timer"

    Examples: set a timer for for a specified duration
      | set timer request |
      | set a timer for 5 minutes |
      | start a 1 minute timer |
      | start a timer for 1 minute and 30 seconds |
      | create a timer for 1 hour |
      | create a timer for 1 hour and 30 minutes |
      | ping me in 5 minutes |
      | begin timer 2 minutes |


  Scenario Outline: set a second timer for a specified duration
    Given an english speaking user
    And an active 90 minute timer
    When the user says "<set timer request>"
    Then "mycroft-timer.mycroftai" should reply with dialog from "started-timer-named"

    Examples: set a second timer for a specified duration
      | set timer request |
      | start another timer for 5 minutes |
      | set one more timer for 10 minutes |
      | set a timer for 2 minutes |


  Scenario Outline: set a named timer for for a specified duration
    Given an English speaking user
    And no active timers
    When the user says "<set timer request>"
    Then "mycroft-timer.mycroftai" should reply with dialog from "started-timer-named"

    Examples: set a named timer for a specified duration
      | set timer request |
      | set a 10 minute timer for pasta |
      | start a timer for 25 minutes called oven one |
      | start a timer for 15 minutes named oven two |


  Scenario Outline: set a second timer with the same duration as an existing timer
    Given an English speaking user
    And an active 10 minute timer
    When the user says "<set timer request>"
    Then "mycroft-timer.mycroftai" should reply with dialog from "started-timer-named"

    Examples: set a second timer with the same duration as an existing timer
      | set timer request |
      | set a timer for 10 minutes for pasta |


 
