@allure.suite:behave
Feature: decrease brightness
  Scenario: decrease light brightness
    Given an English speaking user
    When the user says "decrease the brightness of bathroom light please"
	  Then "homeassistant" should reply with dialog from "homeassistant.brightness.decreased"