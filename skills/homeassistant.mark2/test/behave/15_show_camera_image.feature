@allure.suite:behave
Feature: camera
  Scenario: show image of missing entity
    Given an English speaking user
    When the user says "show me the latest picture of Albert Einstein"
    Then "skill-homeassistant" should not reply

  Scenario: show image
    Given an English speaking user
    When the user says "show me the latest picture of Mycroft camera"
    Then "skill-homeassistant" should reply with dialog from "homeassistant.error.no_gui"