@allure.suite:behave
Feature: turn on
  Scenario: turn on switch
    Given an English speaking user
    When the user says "can you turn on blue switch please"
	  Then "homeassistant" should reply with dialog from "homeassistant.device.on.dialog"