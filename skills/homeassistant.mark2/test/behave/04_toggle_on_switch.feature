@allure.suite:behave
Feature: toggle
  Scenario: toggle on switch
    Given an English speaking user
    When the user says "can you toggle pink switch"
	  Then "homeassistant" should reply with dialog from "homeassistant.device.on.dialog"
