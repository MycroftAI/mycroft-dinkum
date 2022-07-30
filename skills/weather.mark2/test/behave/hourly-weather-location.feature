Feature: Mycroft Weather Skill hourly forecasts at a specified location

  Scenario Outline: User asks what the weather is later at a location
    Given an english speaking user
     When the user says "<what is the weather later>"
     Then "weather.mark2" should reply with dialog from "hourly-weather-location.dialog"

  Examples: What is the weather later
    | what is the weather later |
    | what is the weather in Baltimore later |
    | what is the weather in London later today |
