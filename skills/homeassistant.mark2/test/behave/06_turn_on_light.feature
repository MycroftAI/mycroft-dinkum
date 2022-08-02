@allure.suite:behave
Feature: turn on
  Scenario: turn on light
    Given an English speaking user
    When the user says "can you turn on Mycroft light please"
	  Then "homeassistant" should reply with dialog from "homeassistant.device.on.dialog"