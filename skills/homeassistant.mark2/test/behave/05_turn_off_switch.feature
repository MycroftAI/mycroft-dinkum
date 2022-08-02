@allure.suite:behave
Feature: turn off
  Scenario: turn off switch
    Given an English speaking user
    When the user says "can you turn off red switch please"
	  Then "homeassistant" should reply with dialog from "homeassistant.device.off.dialog"