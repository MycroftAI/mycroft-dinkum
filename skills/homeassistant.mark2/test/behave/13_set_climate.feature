@allure.suite:behave
Feature: set climate
  Scenario: set climate temperature
    Given an English speaking user
    When the user says "change the mycroft climate temperature to 24 degrees"
	  Then "homeassistant" should reply with dialog from "homeassistant.set.thermostat.dialog"
