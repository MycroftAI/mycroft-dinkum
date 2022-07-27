Feature: Alarm - Set a recurring alarm

  Scenario Outline: user sets a recurring alarm
    Given an english speaking user
     And no active alarms
     When the user says "<set recurring alarm request>"
     Then "mycroft-alarm" should reply with dialog from "alarm-scheduled-recurring"

  Examples:
    | set recurring alarm request |
    | wake me up every weekday at 7:30 am |
    | set an alarm for weekends at 3 pm |
    | set an alarm for 3 pm every weekend |

  @xfail @cifailonly
  Scenario Outline: Failing user sets a recurring alarm
    Given an english speaking user
     And no active alarms
     When the user says "<set recurring alarm request>"
     Then "mycroft-alarm" should reply with dialog from "alarm-scheduled-recurring"

  Examples:
    | set recurring alarm request |
    | set alarm every weekday at 7:30 am |
    | set an alarm every wednesday at 11 am |
    | wake me up every day at 7:30 am except on the weekends |

  @xfail
  # This is unsupported behaviour. Was the request to create an alarm or check the
  # status of an existing alarm? It's ambiguous and requires more UX research.
  Scenario Outline: User mentions an alarm but does not include any verb like 'set'
    Given an english speaking user
      And no active alarms
     When the user says "<recurring alarm request with no verb>"
     Then "mycroft-alarm" should reply with dialog from "alarm-scheduled-recurring"

  Examples:
    | recurring alarm request with no verb |
    | alarm every weekday at 7:30 am |

  Scenario Outline: user sets a recurring alarm without saying a time
    Given an english speaking user
     And no active alarms
     When the user says "<set recurring alarm request>"
     Then "mycroft-alarm" should reply with dialog from "ask-alarm-time"
     And the user says "<time>"
     And "mycroft-alarm" should reply with dialog from "alarm-scheduled-recurring"

  Examples:
    | set recurring alarm request | time |
    | set a recurring alarm for mondays | 8 am |
    | set a recurring alarm for tuesday | 9 am |
    | create a repeating alarm for weekdays | 7 am |

  Scenario Outline: user sets a recurring alarm without saying a day
    Given an english speaking user
     And no active alarms
     When the user says "<set recurring alarm request>"
     Then "mycroft-alarm" should reply with dialog from "ask-alarm-recurrence"
     And the user says "<days>"
     And "mycroft-alarm" should reply with dialog from "alarm-scheduled-recurring"

  Examples:
    | set recurring alarm request | days |
    | set a recurring alarm for 8 am | weekdays |
    | set a recurring alarm for 12 pm | tuesday |
    | create a repeating alarm for 10 pm | monday |

  Scenario Outline: user sets a recurring alarm for weekends
    Given an english speaking user
     And no active alarms
     When the user says "<set recurring alarm request>"
     Then "mycroft-alarm" should reply with dialog from "ask-alarm-time"
     And the user says "<time>"
     And "mycroft-alarm" should reply with dialog from "alarm-scheduled-recurring"

  Examples:
    | set recurring alarm request | time |
    | set a recurring alarm for weekends | 10 am |

  Scenario Outline: user sets recurring named alarm
    Given an english speaking user
     And no active alarms
     When the user says "<set recurring named alarm request>"
     Then "mycroft-alarm" should reply with dialog from "ask-alarm-recurrence"
     And the user says "<days>"
     And "mycroft-alarm" should reply with dialog from "alarm-scheduled-recurring"

  Examples:
   | set recurring named alarm request | days |
   | set a recurring alarm named lunch for 1 pm | every day |
   | set a recurring alarm named wake up for 8 am | weekdays |
   | set a recurring alarm for 12 pm | tuesday |
   | create a repeating alarm for 10 pm | monday |

