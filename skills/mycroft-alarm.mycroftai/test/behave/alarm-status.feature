Feature: Alarm - Check status

  Scenario Outline: user asks for alarm status of a single alarm
    Given an english speaking user
    And no active alarms
    And an alarm is set for 9:00 am tomorrow
    When the user says "<alarm status>"
    Then "mycroft-alarm" should reply with dialog from "single-active-alarm.dialog"

  Examples: status of a single alarm
    | alarm status |
    | alarm status |
    | do I have any alarms |
    | what alarms do I have |

  Scenario Outline: user asks for alarm status of multiple alarms
    Given an english speaking user
     And no active alarms
     And an alarm is set for 9:00 am tomorrow
     And an alarm is set for 6:00 pm tomorrow
     When the user says "<alarm status>"
     Then "mycroft-alarm" should reply with dialog from "multiple-active-alarms.dialog"

  Examples: status of multiple alarms
    | alarm status |
    | what alarms do I have |
    | show me my alarms |
    | when's my alarm |

  Scenario Outline: user asks for alarm status of a single recurring alarm
    Given an english speaking user
    And no active alarms
    And an alarm is set for 9:00 am on weekdays
    When the user says "<alarm status>"
    Then "mycroft-alarm" should reply with dialog from "single-active-alarm.dialog"

  Examples: status of a single alarm
    | alarm status |
    | tell me my alarms |
    | are there any alarms set |
    | what time is my alarm set to |
    | is there an alarm set |

  Scenario Outline: user asks for alarm status of multiple recurring alarms
    Given an english speaking user
     And no active alarms
     And an alarm is set for 9:00 am on weekdays
     And an alarm is set for 6:00 pm next wednesday
     When the user says "<alarm status>"
     Then "mycroft-alarm" should reply with dialog from "multiple-active-alarms.dialog"

  Examples: status of multiple alarms
    | alarm status |
    | alarm status |
    | show me my alarms |
    | when will my alarm go off |
    | when's my alarm |
    | are there any alarms set |

  Scenario Outline: user asks for alarm status when no alarms are sets
    Given an english speaking user
     And no active alarms
     When the user says "<alarm status>"
     Then "mycroft-alarm" should reply with dialog from "no-active-alarms.dialog"

  Examples: status when no alarms are set
     | alarm status |
     | alarm status |
     | what alarms do I have |
     | when will my alarm go off |
     | are there any alarms set for this evening |
     | is there an alarm set |
     | tell me my alarms |
