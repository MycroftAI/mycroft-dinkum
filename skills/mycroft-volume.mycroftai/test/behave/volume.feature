Feature: volume control

  Scenario Outline: turning up the volume
    Given an english speaking user
     And the volume is set to 5
     When the user says "<volume up>"
     Then the volume should be "6"

  Examples: turning up the volume
    | volume up |
    | increase volume |
    | turn it up |
    | volume up |
    | louder |
    | more sound |
    | more audio |
    | higher volume |
    | raise the volume |
    | boost volume |
    | turn up the volume |
    | make it louder |

  Scenario Outline: turning down the volume
    Given an english speaking user
     And the volume is set to 5
     When the user says "<volume down>"
     Then the volume should be "4"

  Examples: turning down the volume
    | volume down |
    | volume down |
    | decrease volume |
    | volume down |
    | turn it down |
    | quieter please |
    | less sound |
    | lower volume |
    | reduce volume |
    | quieter |
    | less volume |
    | lower sound |
    | make it quieter |
    | make it lower |
    | make it softer |

  Scenario Outline: change volume to a number between 1 and 10
    Given an english speaking user
     And the volume is set to 5
     When the user says "<change volume to a number>"
     Then "mycroft-volume" should reply with dialog from "set.volume.dialog"
      And the volume should be "<expected level>"

  Examples: change volume to a number between 0 and 10
    | change volume to a number | expected level |
    | change volume to 7 | 7 |
    | change volume to 8 | 8 |
    | set volume to 9 | 9 |
    | set audio to 6 | 6 |
    | decrease volume to 4 | 4 |
    | raise volume to 8 | 8 |
    | lower volume to 4 | 4 |
    | volume 8 | 8 |

  Scenario Outline: change volume to a percent of 100
    Given an english speaking user
     And the volume is set to 5
     When the user says "<change volume to a percent>"
     Then "mycroft-volume" should reply with dialog from "set.volume.percent.dialog"
      And the volume should be "<expected level>"

  Examples: change volume to a percent
    | change volume to a percent | expected level |
    | volume 80 percent | 8 |

  Scenario Outline: max volume
    Given an english speaking user
     And the volume is set to 5
     When the user says "<max volume>"
     Then "mycroft-volume" should reply with dialog from "max.volume.dialog"
      And the volume should be "10"

  Examples: max volume
    | max volume |
    | max volume |
    | maximum volume |
    | loudest volume |
    | max audio |
    | maximum audio |
    | max sound |
    | maximum sound |
    | turn it up all the way |
    | set volume to maximum |
    | highest volume |
    | raise volume to max |
    | raise volume all the way |
    | increase volume  to 10 |
    | crank it up |
    | crank volume |

  Scenario Outline: volume status
    Given an english speaking user
     And the volume is set to 5
     When the user says "<volume status>"
     Then "mycroft-volume" should reply with dialog from "volume.is.dialog"

  Examples: volume status
    | volume status |
    | volume status |
    | what's your volume |
    | what's your current volume level |
    | what’s your sound level |
    | what's your audio level |
    | volume level |
    | volume status |
    | what volume are you set to |
    | how loud is it |
    | how loud is the volume |
    | how loud is that |
    | how high is the volume |
    | how high is the sound |
    | how high is the audio |
    | how high is the sound level |
    | how high is the audio level |
    | how high is the volume level |
    | what's the volume at |
    | what's the current volume |
    | what's the volume set to |
    | what is the volume at |
    | what level is the volume set to |
    | what level is the volume at |

  @xfail
  # "Reset" is currently used synonymously with "unmute"
  # This test presumes a default volume, rather than pre-mute volume.
  Scenario Outline: reset volume
    Given an english speaking user
     And the volume is set to 10
     When the user says "<reset volume>"
     Then "mycroft-volume" should reply with dialog from "reset.volume.dialog"
      And the volume should be "5"

  Examples: reset volume
    | reset volume |
    | reset volume |
    | default volume |
    | go to default volume |
    | restore volume |
    | change volume to default volume |
    | set volume to default volume |

  Scenario Outline: mute audio
    Given an english speaking user
     And the volume is set to 5
     When the user says "<mute audio>"
     Then "mycroft-volume" should reply with dialog from "mute.volume.dialog"
      And the volume should be "0"

  Examples: mute audio
    | mute audio |
    | mute audio |
    | mute volume |
    | mute all audio |
    | mute the sound |
    | silence the audio |
    | shut up |
    | be quiet |

  Scenario Outline: unmute audio
    Given an english speaking user
     And the volume is set to 6
     And Mycroft audio is muted
     When the user says "<unmute audio>"
     Then "mycroft-volume" should reply with dialog from "reset.volume.dialog"
      And the volume should be "6"

  Examples: unmute audio
    | unmute audio |
    | unmute audio |
    | unmute all sound |
    | unmute the volume |

  Scenario Outline: Unmute audio - short explicit phrase
    Given an english speaking user
     And the volume is set to 4
     And Mycroft audio is muted
     When the user says "<unmute audio>"
     Then "mycroft-volume" should reply with dialog from "reset.volume.dialog"
      And the volume should be "4"

  Examples: unmute audio
    | unmute audio |
    | unmute |
    | turn sound back on |
    | turn on sound |
    | turn muting off |
    | turn mute off |