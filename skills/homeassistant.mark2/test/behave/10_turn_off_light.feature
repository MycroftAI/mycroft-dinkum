@allure.suite:behave
Feature: turn off
  Scenario: turn off light
    Given an English speaking user
    When the user says "can you turn off stairs light please"
	  Then "homeassistant" should reply with dialog from "homeassistant.device.off.dialog"