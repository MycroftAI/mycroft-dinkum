Feature: mycroft-support 

  Scenario: create a support ticket then cancel
    Given an english speaking user
    When the user says "contact support"
    Then "mycroft-support" should reply with dialog from "confirm.support.dialog"
    And the user replies with "no"
    And "mycroft-support" should reply with dialog from "cancelled.dialog"

  Scenario: create a support ticket
    Given an english speaking user
    When the user says "contact support"
    Then "mycroft-support" should reply with dialog from "confirm.support.dialog"
    And the user replies with "yes"
    And "mycroft-support" should reply with dialog from "ask.description.dialog"
    And the user replies with "lupDujHomwIj luteb gharghmey"
    And "mycroft-support" should reply with dialog from "complete.dialog"