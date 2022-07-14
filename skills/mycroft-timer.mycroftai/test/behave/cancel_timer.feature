Feature: Cancel Timers
  Timers can be canceled one at a time, by name, by duration or all at once

  Scenario Outline: cancel a timer when only one timer is active
    Given an english speaking user
    And an active 2 minute timer
    When the user says "<cancel timer request>"
    Then "mycroft-timer.mycroftai" should reply with dialog from "cancelled-single-timer"

    Examples: cancel a timer when only one timer is active
      | cancel timer request |
      | stop the timer |
      | end timer |
      | end the timer |
      | kill the timer |
      | disable timer |
      | disable the timer |
      | delete timer |
      | remove timer |


  Scenario Outline: cancel a timer when multiple timers are active using duration
    Given an english speaking user
    And multiple active timers
      | duration  |
      | 1 minute  |
      | 2 minutes |
      | 3 minutes |
    When the user says "<cancel timer request>"
    Then "mycroft-timer.mycroftai" should reply with dialog from "ask-which-timer-cancel"
    And the user replies "1 minute"
    And "mycroft-timer.mycroftai" should reply with dialog from "cancelled-timer-named"

    Examples: cancel a timer when two timers are active
      | cancel timer request |
      | stop the timer |
      | end timer |
      | end the timer |
      | kill the timer |
      | disable timer |
      | disable the timer |
      | delete timer |
      | remove timer |


  Scenario Outline: cancel a timer when multiple timers are active using name
    Given an english speaking user
    And multiple active timers
      | duration  |
      | 1 minute  |
      | 2 minutes |
      | 3 minutes |
    When the user says "<cancel timer request>"
    Then "mycroft-timer.mycroftai" should reply with dialog from "ask-which-timer-cancel"
    And the user replies "timer 1"
    And "mycroft-timer.mycroftai" should reply with dialog from "cancelled-timer-named"

    Examples: cancel timer with three active timer
      | cancel timer request |
      | cancel timer |
      | stop the timer |
      | end timer |
      | end the timer |
      | kill the timer |
      | disable timer |
      | disable the timer |
      | delete timer |
      | remove timer |


  Scenario Outline: abort canceling a timer
    Given an english speaking user
    And multiple active timers
      | duration  |
      | 1 minute  |
      | 2 minutes |
      | 3 minutes |
    When the user says "<abort cancel request>"
    Then "mycroft-timer.mycroftai" should reply with dialog from "ask-which-timer-cancel"
    And the user replies "nevermind"

    Examples: abort canceling a timer
      | abort cancel request |
      | cancel timer |
      | stop the timer |
      | end timer |

  Scenario Outline: attempt to cancel timer when there are no timers active
    Given an english speaking user
    And no active timers
    When the user says "<cancel timer request>"
    Then "mycroft-timer.mycroftai" should reply with dialog from "no-active-timer"

    Examples: attempt to cancel timer when there are no timers active
      | cancel timer request |
      | stop the timer |
      | end timer |
      | end the timer |
      | kill the timer |
      | disable timer |
      | disable the timer |
      | delete timer |
      | remove timer |

  Scenario Outline: cancel a timer specifying duration
    Given an english speaking user
    And multiple active timers
      | duration   |
      | 5 minutes  |
      | 10 minutes |
    When the user says "<cancel timer request>"
    Then "mycroft-timer.mycroftai" should reply with dialog from "cancelled-timer-named"

    Examples: cancel a timer specifying duration
      | cancel timer request |
      | stop the 5 minute timer |
      | cancel the 5 minute timer |
      | kill the 5 minute timer |
      | disable the 5 minute timer |
      | delete the 5 minute timer |
      | cancel timer one |

  @xfail
  # Jira MS-61 https://mycroft.atlassian.net/browse/MS-61
  Scenario Outline: Failing cancel a specific timer
    Given an english speaking user
    And multiple active timers
      | duration   |
      | 5 minutes  |
      | 10 minutes |
    When the user says "<cancel timer request>"
    Then "mycroft-timer.mycroftai" should reply with dialog from "cancelled-timer-named"

    Examples: cancel a specific timer
      | cancel timer request |
      | disable 5 minute timer |
      | end 5 minute timer |
      | end the 5 minute timer |

  Scenario Outline: cancel a timer specifying name
    Given an english speaking user
    And an active timer named pasta
    When the user says "<cancel timer request>"
    Then "mycroft-timer.mycroftai" should reply with dialog from "cancelled-timer-named"

    Examples: cancel a timer specifying name
      | cancel timer request |
      | cancel pasta timer |
      | stop the pasta timer |
      | kill the pasta timer |
      | disable pasta timer |
      | disable the pasta timer |
      | delete the pasta timer |
      | remove pasta timer |
      | end pasta timer |
      | end the pasta timer |

  Scenario Outline: cancel all active timers
    Given an english speaking user
    And multiple active timers
      | duration   |
      | 5 minutes  |
      | 10 minutes |
      | 15 minutes |
    When the user says "<cancel timer request>"
    Then "mycroft-timer.mycroftai" should reply with dialog from "cancel-all"

    Examples: cancel all timers
      | cancel timer request |
      | cancel all timers |
      | delete all timers |
      | remove all timers |
      | stop all timers |
      | kill all timers |
      | disable all timers |
      | turn off all timers |
