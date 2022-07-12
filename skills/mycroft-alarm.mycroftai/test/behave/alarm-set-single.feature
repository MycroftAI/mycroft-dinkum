Feature: Alarm - Set a non-recurring alarm

  Scenario Outline: user sets an alarm for a specified time
    Given an english speaking user
     And no active alarms
     When the user says "<set alarm request>"
     Then "mycroft-alarm" should reply with dialog from "alarm-scheduled"

  Examples:
    | set alarm request |
    | set alarm for 8 am |
    | set an alarm for 7:30 am |
    | create an alarm for 7:30 am |
    | let me know when it's 8:30 pm |
    | wake me up at 7 tomorrow morning |
    | start an alarm for 6:30 am |

  Scenario Outline: user sets an alarm without saying a time
    Given an english speaking user
     And no active alarms
     When the user says "<set alarm request>"
     Then "mycroft-alarm" should reply with dialog from "ask-alarm-time"
     And the user replies "8:00 am"
     And "mycroft-alarm" should reply with dialog from "alarm-scheduled"

  Examples:
    | set alarm request |
    | set alarm |
    | set an alarm |
    | create an alarm |
    | wake me up tomorrow |

  @xfail
  # Jira MS-65 https://mycroft.atlassian.net/browse/MS-65
  Scenario Outline: Failing user sets an alarm without saying a time
    Given an english speaking user
     And no active alarms
     When the user says "<set alarm request>"
     Then "mycroft-alarm" should reply with dialog from "ask-alarm-time"
     And the user replies "8:00 am"
     And "mycroft-alarm" should reply with dialog from "alarm-scheduled"

  Examples:
    | set alarm request |
    | set an alarm for tomorrow morning |

  Scenario Outline: User sets an alarm without saying a time but then cancels
    Given an english speaking user
     And no active alarms
     When the user says "<set alarm request>"
     Then "mycroft-alarm" should reply with dialog from "ask-alarm-time"
     And the user replies "<dismissal request>"
     And "mycroft-alarm" should reply with dialog from "alarm-not-scheduled"

  Examples:
    | set alarm request | dismissal request |
    | set an alarm | nevermind |
    | create an alarm | cancel |
    | set an alarm | forget about it |
    | set an alarm | stop |

  Scenario Outline: user sets an alarm with a name with a time
    Given an english speaking user
     And no active alarms
     When the user says "<set a named alarm for a time>"
     Then "mycroft-alarm" should reply with dialog from "alarm-scheduled"

  Examples: user sets an alarm with a name with a time
    | set a named alarm for a time |
    | set an alarm named sandwich for 12 pm |
    | set an alarm for 10 am for stretching |
    | set an alarm for stretching 10 am |
    | set an alarm named brunch for 11 am |
    | set an alarm called brunch for 11 am |
    | set an alarm named workout for 11 am |

  Scenario Outline: user sets an alarm without specifying am or pm
    Given an english speaking user
     And no active alarms
     When the user says "<set alarm request>"
     Then "mycroft-alarm" should reply with dialog from "alarm-scheduled"

  Examples:
    | set alarm request |
    | set an alarm for 6:30 |
    | set an alarm for 7 |
    | wake me up at 6:30 |
    | let me know when it's 6 |

  Scenario Outline: Failing set an alarm for a duration instead of a time
    Given an english speaking user
     And no active alarms
     When the user says "<set an alarm for a duration>"
     Then "mycroft-alarm" should reply with dialog from "alarm-scheduled"

  Examples:
    | set an alarm for a duration |
    | set an alarm for 30 minutes |
    | set an alarm 8 hours from now |
    | set an alarm 8 hours and 30 minutes from now |

  Scenario Outline: user sets a named alarm without saying a time
    Given an english speaking user
     And no active alarms
     When the user says "<set alarm request>"
     Then "mycroft-alarm" should reply with dialog from "ask-alarm-time"
     And the user replies "8 am"
     And "mycroft-alarm" should reply with dialog from "alarm-scheduled"

  Examples: set a named alarm without saying a time
    | set alarm request |
    | set an alarm for sandwich |
    | set an alarm for stretching |
    | set an alarm named meeting |

