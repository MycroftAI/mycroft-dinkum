Feature: mycroft-pairing

  Scenario: Let's pair
    Given an english speaking user
     When the user says "let's pair my device"
     Then "mycroft-pairing.mycroftai" should reply with dialog from "already.paired.dialog"

  Scenario: register my device
    Given an english speaking user
     When the user says "register my device"
     Then "mycroft-pairing.mycroftai" should reply with dialog from "already.paired.dialog"

