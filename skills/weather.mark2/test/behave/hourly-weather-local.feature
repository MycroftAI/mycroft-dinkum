Feature: Mycroft Weather Skill local hourly forecasts

  Scenario Outline: what is the weather later
    Given an english speaking user
     When the user says "<what is the weather later>"
     Then "weather.mark2" should reply with dialog from "hourly-weather-local.dialog"

  Examples: What is the weather later
    | what is the weather later |
    | what is the weather later |
    | what's the weather later today |
