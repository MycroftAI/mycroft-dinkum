@allure.suite:behave
Feature: automation
  Scenario: triger automation
    Given an English speaking user
    When the user says "activate the automation mycroft tracker automation"
	  Then "homeassistant" should reply with dialog from "homeassistant.automation.trigger.dialog"
