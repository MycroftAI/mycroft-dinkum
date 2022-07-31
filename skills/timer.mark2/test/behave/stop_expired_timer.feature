Feature: Stop an expired timer
  After a timer expires, a beeping alarm is played.  Stop the beeping and cancel the
  expired timer.  This can be done in two ways.  First is the generic "stop" command.
  Second is using one of the accepted timer cancel utterances.

  Scenario Outline: stop an expired timer using a "stop" command
    Given an english speaking user
    And an expired timer
    When the user says "<stop request>"
    Then the expired timer should stop beeping
    And timers are stopped

    Examples:
      | stop request |
      | stop |
      | cancel |
      | turn it off |
      | silence |
      | shut up |
      | I got it |
      | mute |
      | disable |
      | that's enough |

  Scenario Outline: stop an expired timer using a "cancel" command.
    Given an english speaking user
    And an expired timer
    When the user says "<cancel request>"
    Then the expired timer should stop beeping
    And "timer.mark2" should reply with dialog from "cancelled-single-timer"
    And timers are stopped

    Examples:
      | cancel request |
      | stop timer |
      | end timer |
      | cancel all timers |
      | cancel the timers |
      | cancel timers |
