@allure.suite:behave
Feature: set brightness
  Scenario: set light brightness
    Given an English speaking user
    When the user says "set the brightness of bathroom light to 20%"
	  Then "homeassistant" should reply with dialog from "homeassistant.brightness.dimmed"