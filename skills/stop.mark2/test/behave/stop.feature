Feature: mycroft-stop

    Scenario: stop
    Given an english speaking user
      When the user says "stop"
      Then mycroft should send the message "mycroft.stop"

    # DISABLED SO WE DONT CAUSE UNINTENDED CONSEQUENCES ON USER SYSTEMS
    # Scenario: reboot
    # Given an english speaking user
    #   When the user says "reboot"
    #   Then "mycroft-alarm" should reply with dialog from "confirm.reboot.dialog"
    #   And the user says "yes"
    #   Then mycroft should send the message "system.reboot"

    # Scenario: shutdown
    # Given an english speaking user
    #   When the user says "shut down"
    #   Then "mycroft-alarm" should reply with dialog from "confirm.shutdown.dialog"
    #   And the user says "yes"
    #   Then mycroft should send the message "system.shutdown"
