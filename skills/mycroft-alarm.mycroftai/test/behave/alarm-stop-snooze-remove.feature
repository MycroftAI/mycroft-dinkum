Feature: Alarm - Stop, snooze, and remove

  Scenario Outline: user stops an expired alarm when beeping
    Given an english speaking user
     And no active alarms
     And an alarm is expired and beeping
     When the user says "<stop>"
     Then "mycroft-alarm" should stop beeping

  Examples: stop beeping
    | stop |
    | stop alarm |
    | disable alarm |
    | cancel alarm |
    | turn off alarm |
    | kill alarm |

  @xfail
  Scenario Outline: Failing user stops an expired alarm when beeping
    Given an english speaking user
     And no active alarms
     And an alarm is expired and beeping
     When the user says "<stop>"
     Then "mycroft-alarm" should stop beeping

  Examples: Failing stop beeping
    | stop |
    | stop |
    | cancel |
    | turn it off |
    | turn off |
    | silence |
    | abort |

  @xfail
  # Jira MS-72 https://mycroft.atlassian.net/browse/MS-72
  Scenario Outline: user snoozes a beeping alarm
    Given an english speaking user
     And no active alarms
     And an alarm is expired and beeping
     When the user says "<snooze>"
     Then "mycroft-alarm" should stop beeping and start beeping again 10 minutes

  Examples: snooze a beeping alarm
    | snooze |
    | snooze |
    | snooze alarm |
    | not yet |
    | 10 more minutes |
    | 10 minutes |
    | snooze for 10 minutes |
    | give me 10 minutes |
    | wake me up in 10 minutes |
    | remind me in 10 minutes |
    | let me sleep |

  @xfail
  # Jira MS-73 https://mycroft.atlassian.net/browse/MS-73
  Scenario Outline: user snoozes an beeping alarm for a specific time
    Given an english speaking user
     And no active alarms
     And an alarm is expired and beeping
     When the user says "<snooze for a time>"
     Then "mycroft-alarm" should stop beeping and start beeping again 5 minutes

  Examples: snooze a beeping alarm for a specific time
    | snooze for a time |
    | snooze for 5 minutes |
    | give me 10 minutes |

  Scenario Outline: user deletes an alarm when a single alarm is active
    Given an english speaking user
     And no active alarms
     And an alarm is set for 9:00 am tomorrow
     When the user says "<delete alarm>"
     Then "mycroft-alarm" should reply with dialog from "cancelled-single.dialog"

  Examples: delete an alarm when a single alarm is active
    | delete alarm |
    | delete alarm |
    | cancel alarm |
    | disable alarm |
    | turn off alarm |
    | stop alarm |
    | abort alarm |
    | remove alarm |

  @xfail
  # JIRA https://mycroft.atlassian.net/browse/SKILL-512
  Scenario Outline: user deletes an alarm when multiple alarms are active
    Given an english speaking user
     And no active alarms
     And an alarm is set for 9:00 am next monday
     And an alarm is set for 10:00 pm next friday
     When the user says "<delete alarm>"
     Then "mycroft-alarm" should reply with dialog from "ask-which-alarm-delete.dialog"
     And the user says "9:00 am"
     And "mycroft-alarm" should reply with dialog from "cancelled-single.dialog"

  Examples: delete an alarm when multiple alarm are active
    | delete alarm |
    | delete alarm |
    | cancel alarm |
    | disable alarm |
    | turn off alarm |
    | stop alarm |
    | abort alarm |
    | remove alarm |

  @xfail
  # Jira MS-75 https://mycroft.atlassian.net/browse/MS-75
  Scenario Outline: user deletes a specific alarm
    Given an english speaking user
     And no active alarms
     And an alarm is set for 9:00 am next monday
     And an alarm is set for 10:00 pm next friday
     When the user says "<delete specific alarm>"
     And "mycroft-alarm" should reply with dialog from "cancelled-single.dialog"

  Examples: delete an alarm when multiple alarm are active
    | delete specific alarm |
    | delete 9:00 am alarm |
    | cancel 9:00 am alarm |
    | disable 9:00 am alarm |
    | turn off 9:00 am alarm |
    | stop 9:00 am alarm |
    | abort 9:00 am alarm |
    | remove 9:00 am alarm |

  Scenario Outline: user deletes all alarms
    Given an english speaking user
     And no active alarms
     And an alarm is set for 9:00 am next monday
     And an alarm is set for 10:00 pm next friday
     When the user says "<delete all alarms>"
     Then "mycroft-alarm" should reply with dialog from "cancelled-multiple.dialog"

  Examples: delete an alarm when multiple alarm are active
    | delete all alarms |
    | delete all alarms |
    | cancel all alarms |
    | remove all alarms |
    | turn off all alarms |
    | stop all alarms |
    | abort all alarms |
    | remove all alarms |
    | remove every alarm |
    | delete every alarm |

@xfail
Scenario Outline: user snoozes an alarm and then plays the news
    Given an english speaking user
     And no active alarms
     And an alarm is expired and beeping
     When the user says "<snooze>"
     Then "mycroft-alarm" should stop beeping and start beeping again 10 minutes
     And the user says "play the news"
     And "skill-npr-news" should reply with dialog from "news.dialog"

  Examples: delete an alarm when multiple alarm are active
    | snooze |
    | snooze |
    | snooze alarm |
    | not yet |
    | 10 more minutes |
    | 10 minutes |
    | snooze for 10 minutes |
    | wake me up in 10 minutes |
    | remind me in 10 minutes |
    | let me sleep |
