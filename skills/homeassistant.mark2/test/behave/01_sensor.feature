@allure.suite:behave
Feature: sensor
  Scenario: read sensor
    Given an English speaking user
    When the user says "give me the value of Mycroft sensor please"
    Then mycroft reply should contain "122"