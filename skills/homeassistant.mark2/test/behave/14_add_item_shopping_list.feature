@allure.suite:behave
Feature: shopping list
  Scenario: add item
    Given an English speaking user
    When the user says "add bread to the shopping list"
	  Then "homeassistant" should reply with dialog from "homeassistant.shopping.list.dialog"